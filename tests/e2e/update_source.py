"""Isolated HTTPS Sparkle fixture. The App uses ordinary TLS and EdDSA checks."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import re
import secrets
import ssl
import subprocess
import threading
import time
from urllib.request import urlopen
from xml.sax.saxutils import escape


def appcast(url: str, signature: str, size: int, build: str = "101") -> bytes:
    return (f'<?xml version="1.0" encoding="utf-8"?>\n'
            f'<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle"><channel>'
            f'<title>TokenMeter isolated update</title><item><title>Isolated build {escape(build)}</title>'
            f'<sparkle:version>{escape(build)}</sparkle:version><sparkle:shortVersionString>0.1.1</sparkle:shortVersionString>'
            f'<sparkle:minimumSystemVersion>14.0</sparkle:minimumSystemVersion>'
            f'<enclosure url="{escape(url)}" sparkle:edSignature="{escape(signature)}" length="{size}" type="application/octet-stream" />'
            f'</item></channel></rss>\n').encode()


class UpdateSource:
    """Private material stays in a temporary directory excluded from artifacts."""

    def __init__(self, private: Path, evidence: Path):
        self.private, self.evidence = private, evidence
        self.private.mkdir(mode=0o700)
        self.token = secrets.token_urlsafe(32)
        self.valid = False
        self.payloads: dict[str, bytes] = {}
        self.events: list[dict] = []
        self._events_condition = threading.Condition()
        self._active_gets = 0
        self.tunnel: subprocess.Popen | None = None
        self.tunnel_reader: threading.Thread | None = None
        self.tunnel_lines: queue.Queue[str] = queue.Queue()
        source = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass  # Never log Authorization or test fixture secrets.

            def do_GET(self):
                with source._events_condition:
                    source._active_gets += 1
                    valid = source.valid
                try:
                    route = self.path.split("?", 1)[0]
                    key = ("/valid.xml" if valid else "/invalid.xml") if route == "/appcast.xml" else route
                    payload = b"ready" if key == "/healthz" else source.payloads.get(key)
                    status = 200 if payload is not None else 404
                    event = {"at": datetime.now(timezone.utc).isoformat(), "path": route,
                             "status": status, "mode": "valid" if valid else "invalid", "served_bytes": 0}
                    with source._events_condition:
                        source.events.append(event)
                    self.send_response(status)
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload or b"")))
                    self.send_header("Content-Type", "application/xml" if route.endswith(".xml") else
                                     ("text/plain" if route == "/healthz" else "application/octet-stream"))
                    self.end_headers()
                    if payload is not None:
                        try:
                            self.wfile.write(payload)
                            with source._events_condition:
                                event["served_bytes"] = len(payload)
                        except OSError as exc:
                            with source._events_condition:
                                event["transport_error"] = type(exc).__name__
                finally:
                    with source._events_condition:
                        source._active_gets -= 1
                        source._events_condition.notify_all()

            def do_POST(self):
                authorized = secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + source.token)
                if self.path != "/control/valid" or not authorized:
                    self.send_response(403)
                else:
                    with source._events_condition:
                        source.valid = True
                        source.events.append({"at": datetime.now(timezone.utc).isoformat(), "path": "/control/valid", "status": 200})
                    self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.origin_url = f"https://localhost:{self.server.server_port}"
        self.url: str | None = None
        self.thread: threading.Thread | None = None

    def _run(self, args: list[str], name: str) -> str:
        started = time.monotonic()
        def progress(state: str, **details) -> None:
            print(json.dumps({"event": "fixture_operation", "fixture": "update_source", "operation": name,
                              "state": state, "elapsed_seconds": round(time.monotonic() - started, 3), **details}), flush=True)
        progress("STARTED")
        try:
            result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=60)
        except subprocess.TimeoutExpired as exc:
            progress("TIMED_OUT")
            raise RuntimeError(f"Isolated update fixture {name} timed out after 60 seconds") from exc
        except OSError as exc:
            progress("FAILED", errno=exc.errno)
            raise RuntimeError(f"Isolated update fixture {name} unavailable (errno={exc.errno})") from exc
        # Tool output contains certificates' metadata, never private key file contents.
        if result.returncode:
            progress("FAILED", exit_code=result.returncode)
            raise RuntimeError(f"Isolated update fixture {name} failed ({result.returncode})")
        progress("SUCCEEDED")
        return result.stdout.strip()

    def prepare(self) -> str:
        seed = self.private / "sparkle-seed.txt"
        seed.write_text(base64.b64encode(os.urandom(32)).decode() + "\n")
        seed.chmod(0o600)
        swift = self.private / "public-key.swift"
        swift.write_text('import Foundation\nimport CryptoKit\n'
                         'let encoded = try String(contentsOfFile: CommandLine.arguments[1]).trimmingCharacters(in: .whitespacesAndNewlines)\n'
                         'let key = try Curve25519.Signing.PrivateKey(rawRepresentation: Data(base64Encoded: encoded)!)\n'
                         'print(key.publicKey.rawRepresentation.base64EncodedString())\n')
        public = self._run(["xcrun", "swift", str(swift), str(seed)], "EdDSA public key")
        if len(base64.b64decode(public, validate=True)) != 32:
            raise RuntimeError("Invalid generated EdDSA public key")
        cn = "TokenMeter-E2E-" + secrets.token_hex(12)
        config = self.private / "tls.cnf"
        config.write_text(f"[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=ca\n"
                          f"[dn]\nCN={cn}\n[ca]\nbasicConstraints=critical,CA:TRUE\n"
                          "keyUsage=critical,keyCertSign,cRLSign\n"
                          "[server]\nbasicConstraints=critical,CA:FALSE\n"
                          "keyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n"
                          "subjectAltName=DNS:localhost,IP:127.0.0.1\n")
        ca, ca_key = self.private / "ca.pem", self.private / "ca.key"
        key, csr, cert = self.private / "server.key", self.private / "server.csr", self.private / "server.pem"
        self._run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-sha256",
                   "-keyout", str(ca_key), "-out", str(ca), "-config", str(config)], "test CA")
        self._run(["openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes", "-sha256", "-subj", "/CN=localhost",
                   "-keyout", str(key), "-out", str(csr)], "server key")
        self._run(["openssl", "x509", "-req", "-in", str(csr), "-CA", str(ca), "-CAkey", str(ca_key),
                   "-CAcreateserial", "-days", "1", "-sha256", "-extfile", str(config), "-extensions", "server", "-out", str(cert)], "server certificate")
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2
        self.context.load_cert_chain(str(cert), str(key))
        self.server.socket = self.context.wrap_socket(self.server.socket, server_side=True)
        return public

    def start_tunnel(self) -> str:
        """Expose only the isolated HTTPS fixture through a public-trust test URL.

        cloudflared validates the localhost origin against this run's CA. The App
        validates the public HTTPS endpoint with the normal macOS trust policy.
        Neither process writes to the machine's certificate trust settings.
        """
        if (os.environ.get("GITHUB_ACTIONS") != "true" or not os.environ.get("RUNNER_TEMP")
                or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted" or os.environ.get("RUNNER_OS") != "macOS"):
            raise RuntimeError("Temporary update tunnel requires an isolated GitHub Mac runner")
        if self.tunnel is not None or self.thread is not None:
            raise RuntimeError("Temporary update tunnel is already started")
        binary = Path(os.environ["RUNNER_TEMP"]) / "tokenmeter-tools/cloudflared"
        if binary.is_symlink() or not binary.is_file() or not os.access(binary, os.X_OK):
            raise RuntimeError("Pinned cloudflared binary is unavailable")
        config_directory = Path.home() / ".cloudflared"
        if any((config_directory / name).exists() for name in ("config.yml", "config.yaml")):
            raise RuntimeError("GitHub Mac runner has a Cloudflare configuration that prevents Quick Tunnel isolation")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.tunnel = subprocess.Popen(
            [str(binary), "tunnel", "--no-autoupdate", "--url", self.origin_url,
             "--origin-ca-pool", str(self.private / "ca.pem"), "--origin-server-name", "localhost",
             "--metrics", "127.0.0.1:0", "--loglevel", "info"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            cwd=self.private,
        )
        assert self.tunnel.stdout is not None
        self.tunnel_reader = threading.Thread(
            target=lambda: [self.tunnel_lines.put(line) for line in self.tunnel.stdout], daemon=True)
        self.tunnel_reader.start()
        deadline = time.monotonic() + 90
        pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com\b")
        while time.monotonic() < deadline:
            if self.tunnel.poll() is not None:
                raise RuntimeError("Temporary HTTPS tunnel exited before becoming ready")
            try:
                line = self.tunnel_lines.get(timeout=1)
            except queue.Empty:
                continue
            match = pattern.search(line)
            if match:
                self.url = match.group()
                break
        if self.url is None:
            raise RuntimeError("Temporary HTTPS tunnel did not provide a URL within 90 seconds")
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if self.tunnel.poll() is not None:
                raise RuntimeError("Temporary HTTPS tunnel exited during TLS verification")
            try:
                with urlopen(self.url + "/healthz", timeout=8) as response:
                    if response.status == 200 and response.read() == b"ready":
                        return self.url
            except (OSError, ValueError):
                pass
            time.sleep(2)
        raise RuntimeError("Temporary HTTPS tunnel did not pass public TLS and origin checks")

    def publish(self, package: Path, signature: str) -> None:
        if self.url is None or self.thread is None or self.tunnel is None or self.tunnel.poll() is not None:
            raise RuntimeError("Temporary HTTPS tunnel is not ready")
        if len(base64.b64decode(signature, validate=True)) != 64:
            raise ValueError("Expected a real EdDSA signature")
        payload = package.read_bytes()
        self.payloads = {
            "/update.zip": payload,
            "/valid.xml": appcast(self.url + "/update.zip", signature, len(payload)),
            "/invalid.xml": appcast(self.url + "/update.zip", base64.b64encode(bytes(64)).decode(), len(payload)),
        }
        (self.evidence / "update-fixture.json").write_text(json.dumps({
            "kind": "controlled-signed-update", "build": "101", "package_sha256": hashlib.sha256(payload).hexdigest(),
            "valid_feed_sha256": hashlib.sha256(self.payloads["/valid.xml"]).hexdigest(),
            "invalid_feed_sha256": hashlib.sha256(self.payloads["/invalid.xml"]).hexdigest(),
            "https": True, "private_key_archived": False,
        }, indent=2) + "\n")

    def verify_exchange(self) -> None:
        """Both UI update attempts must reach the real fixture and download bytes."""
        with self._events_condition:
            if not self._events_condition.wait_for(lambda: self._active_gets == 0, timeout=30):
                raise RuntimeError("Update fixture response accounting did not finish")
            events = [dict(event) for event in self.events]
        switches = [index for index, event in enumerate(events) if event["path"] == "/control/valid" and event["status"] == 200]
        if len(switches) != 1:
            raise RuntimeError("Expected one authenticated invalid-to-valid fixture switch")
        boundary = switches[0]
        for mode, phase_events in (("invalid", events[:boundary]), ("valid", events[boundary + 1:])):
            feed_positions = [index for index, event in enumerate(phase_events)
                              if event["path"] == "/appcast.xml" and event["status"] == 200
                              and event.get("mode") == mode and event.get("served_bytes", 0) > 0]
            downloaded = [index for index, event in enumerate(phase_events)
                          if event["path"] == "/update.zip" and event["status"] == 200
                          and event.get("mode") == mode
                          and event.get("served_bytes", 0) == len(self.payloads["/update.zip"])]
            if not feed_positions or not downloaded or min(downloaded) <= min(feed_positions):
                raise RuntimeError(f"Missing real {mode} feed and complete update archive exchange")

    def close(self) -> None:
        errors = []
        if self.tunnel is not None:
            try:
                if self.tunnel.poll() is None:
                    self.tunnel.terminate()
                try:
                    self.tunnel.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.tunnel.kill()
                    self.tunnel.wait(timeout=5)
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                errors.append(f"HTTPS tunnel shutdown: {type(exc).__name__}")
            if self.tunnel_reader is not None:
                self.tunnel_reader.join(timeout=3)
                if self.tunnel_reader.is_alive():
                    errors.append("HTTPS tunnel log reader did not stop")
        try:
            if self.thread is not None:
                self.server.shutdown()
                self.thread.join(timeout=10)
                if self.thread.is_alive():
                    errors.append("HTTPS fixture did not stop")
        except (OSError, RuntimeError) as exc:
            errors.append(f"HTTPS fixture shutdown: {exc}")
        try:
            self.server.server_close()
        except (OSError, RuntimeError) as exc:
            errors.append(f"HTTPS fixture socket cleanup: {exc}")
        (self.evidence / "update-requests.json").write_text(json.dumps(self.events, indent=2) + "\n")
        if errors:
            raise RuntimeError("; ".join(errors))
