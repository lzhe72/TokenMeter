"""Isolated HTTPS Sparkle fixture. The App uses ordinary TLS and EdDSA checks."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import threading
import time
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
        self.trusted = False
        self.certificate_added = False
        source = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass  # Never log Authorization or test fixture secrets.

            def do_GET(self):
                route = self.path.split("?", 1)[0]
                key = ("/valid.xml" if source.valid else "/invalid.xml") if route == "/appcast.xml" else route
                payload = source.payloads.get(key)
                status = 200 if payload is not None else 404
                event = {"at": datetime.now(timezone.utc).isoformat(), "path": route,
                         "status": status, "mode": "valid" if source.valid else "invalid", "served_bytes": 0}
                source.events.append(event)
                self.send_response(status)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload or b"")))
                self.send_header("Content-Type", "application/xml" if route.endswith(".xml") else "application/octet-stream")
                self.end_headers()
                if payload is not None:
                    try:
                        self.wfile.write(payload)
                        event["served_bytes"] = len(payload)
                    except OSError as exc:
                        event["transport_error"] = type(exc).__name__

            def do_POST(self):
                authorized = secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + source.token)
                if self.path != "/control/valid" or not authorized:
                    self.send_response(403)
                else:
                    source.valid = True
                    source.events.append({"at": datetime.now(timezone.utc).isoformat(), "path": "/control/valid", "status": 200})
                    self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"https://localhost:{self.server.server_port}"
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

    def trust_on_ephemeral_ci(self) -> None:
        if (os.environ.get("GITHUB_ACTIONS") != "true" or not os.environ.get("RUNNER_TEMP")
                or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted" or os.environ.get("RUNNER_OS") != "macOS"):
            raise RuntimeError("Update fixture CA trust is permitted only on an isolated GitHub runner")
        self._run(["sudo", "-n", "/usr/bin/true"], "check noninteractive administrator access")
        self.keychain = "/Library/Keychains/System.keychain"
        # A tool can fail after a partial import. Mark cleanup as required before
        # the mutation so the caller always attempts both trust and cert removal.
        self.trusted = self.certificate_added = True
        self._run(["sudo", "-n", "/usr/bin/security", "add-trusted-cert", "-d", "-r", "trustRoot", "-p", "ssl", "-s", "localhost", "-k", self.keychain,
                   str(self.private / "ca.pem")], "temporary CA trust")

    def publish(self, package: Path, signature: str) -> None:
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
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def verify_exchange(self) -> None:
        """Both UI update attempts must reach the real fixture and download bytes."""
        switches = [index for index, event in enumerate(self.events) if event["path"] == "/control/valid" and event["status"] == 200]
        if len(switches) != 1:
            raise RuntimeError("Expected one authenticated invalid-to-valid fixture switch")
        boundary = switches[0]
        for mode, events in (("invalid", self.events[:boundary]), ("valid", self.events[boundary + 1:])):
            feed_positions = [index for index, event in enumerate(events)
                              if event["path"] == "/appcast.xml" and event["status"] == 200
                              and event.get("mode") == mode and event.get("served_bytes", 0) > 0]
            downloaded = [index for index, event in enumerate(events)
                          if event["path"] == "/update.zip" and event["status"] == 200
                          and event.get("mode") == mode
                          and event.get("served_bytes", 0) == len(self.payloads["/update.zip"])]
            if not feed_positions or not downloaded or min(downloaded) <= min(feed_positions):
                raise RuntimeError(f"Missing real {mode} feed and complete update archive exchange")

    def close(self) -> None:
        errors = []
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
        if self.trusted:
            try:
                self._run(["sudo", "-n", "/usr/bin/security", "remove-trusted-cert", "-d", str(self.private / "ca.pem")], "remove test CA trust")
                self.trusted = False
            except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                errors.append(str(exc))
        if self.certificate_added:
            try:
                fingerprint = self._run(["openssl", "x509", "-in", str(self.private / "ca.pem"), "-noout", "-fingerprint", "-sha1"], "CA identity").split("=", 1)[1].replace(":", "")
                self._run(["sudo", "-n", "/usr/bin/security", "delete-certificate", "-Z", fingerprint, self.keychain], "remove test CA certificate")
                self.certificate_added = False
            except (RuntimeError, OSError, subprocess.SubprocessError, IndexError) as exc:
                errors.append(str(exc))
        (self.evidence / "update-requests.json").write_text(json.dumps(self.events, indent=2) + "\n")
        if errors:
            raise RuntimeError("; ".join(errors))
