"""Isolated loopback Sparkle fixture with real EdDSA update packages."""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading
import time
from xml.sax.saxutils import escape


def _subprocess_env() -> dict[str, str]:
    """Do not pass signing credentials to the Swift key generation helper."""
    return {key: value for key, value in os.environ.items()
            if not key.startswith("TM_E2E_SIGNING_")}


def appcast(url: str, signature: str, size: int, build: str = "101") -> bytes:
    return (f'<?xml version="1.0" encoding="utf-8"?>\n'
            f'<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle"><channel>'
            f'<title>TokenMeter isolated update</title><item><title>Isolated build {escape(build)}</title>'
            f'<sparkle:version>{escape(build)}</sparkle:version><sparkle:shortVersionString>0.1.0</sparkle:shortVersionString>'
            f'<sparkle:minimumSystemVersion>15.0</sparkle:minimumSystemVersion>'
            f'<enclosure url="{escape(url)}" sparkle:edSignature="{escape(signature)}" length="{size}" type="application/octet-stream" />'
            f'</item></channel></rss>\n').encode()


def empty_appcast() -> bytes:
    """A valid no-update feed until the first controlled release-test stage."""
    return (b'<?xml version="1.0" encoding="utf-8"?>\n'
            b'<rss version="2.0"><channel><title>TokenMeter isolated update</title></channel></rss>\n')


class UpdateSource:
    """Private material stays in a temporary directory excluded from artifacts."""

    def __init__(self, private: Path, evidence: Path, port: int = 49177):
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("Update fixture port must be an integer between 0 and 65535")
        self.private, self.evidence = private, evidence
        self.private.mkdir(mode=0o700)
        self.token = secrets.token_urlsafe(32)
        self.source_nonce = secrets.token_urlsafe(32)
        self.source_nonce_sha256 = hashlib.sha256(self.source_nonce.encode()).hexdigest()
        self._health_body = ("TokenMeter isolated update source " + self.source_nonce).encode()
        self.mode = "invalid"
        self.valid = False
        self.payloads: dict[str, bytes] = {}
        self.events: list[dict] = []
        self._events_condition = threading.Condition()
        self._active_gets = 0
        source = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass  # Never log Authorization or test fixture secrets.

            def do_GET(self):
                with source._events_condition:
                    source._active_gets += 1
                    mode = source.mode
                try:
                    route = self.path.split("?", 1)[0]
                    key = f"/{mode}.xml" if route == "/appcast.xml" else route
                    redirect = route == "/redirect.zip" and mode == "redirect"
                    payload = (b"" if redirect else
                               source._health_body if key == "/healthz" else source.payloads.get(key))
                    status = 302 if redirect else 200 if payload is not None else 404
                    event = {"at": datetime.now(timezone.utc).isoformat(), "path": route,
                             "status": status, "mode": mode, "served_bytes": 0}
                    with source._events_condition:
                        source.events.append(event)
                    self.send_response(status)
                    if redirect:
                        self.send_header("Location", "http://example.invalid/update.zip")
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
                mode = self.path.removeprefix("/control/") if self.path.startswith("/control/") else ""
                if mode not in {"forbidden", "redirect", "invalid", "valid"} or not authorized:
                    self.send_response(403)
                else:
                    with source._events_condition:
                        source.mode = mode
                        source.valid = mode == "valid"
                        source.events.append({"at": datetime.now(timezone.utc).isoformat(),
                                              "path": self.path, "status": 200})
                    self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

        server = ThreadingHTTPServer(("127.0.0.1", port), Handler, bind_and_activate=False)
        try:
            server.server_bind()
            server.server_activate()
        except OSError as exc:
            server.server_close()
            raise RuntimeError(f"Loopback update fixture port {port} unavailable (errno={exc.errno})") from exc
        self.server = server
        self.server.daemon_threads = True
        self.origin_url = f"http://127.0.0.1:{self.server.server_port}"
        self.url: str | None = None
        self.thread: threading.Thread | None = None

    def _run(self, args: list[str], name: str) -> str:
        started = time.monotonic()
        def progress(state: str, **details) -> None:
            print(json.dumps({"event": "fixture_operation", "fixture": "update_source", "operation": name,
                              "state": state, "elapsed_seconds": round(time.monotonic() - started, 3), **details}), flush=True)
        progress("STARTED")
        try:
            result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=60,
                                    env=_subprocess_env())
        except subprocess.TimeoutExpired as exc:
            progress("TIMED_OUT")
            raise RuntimeError(f"Isolated update fixture {name} timed out after 60 seconds") from exc
        except OSError as exc:
            progress("FAILED", errno=exc.errno)
            raise RuntimeError(f"Isolated update fixture {name} unavailable (errno={exc.errno})") from exc
        # Never include command output or the EdDSA seed in the diagnostic.
        if result.returncode:
            progress("FAILED", exit_code=result.returncode)
            raise RuntimeError(f"Isolated update fixture {name} failed ({result.returncode})")
        progress("SUCCEEDED")
        return result.stdout.strip()

    def prepare(self) -> str:
        if hasattr(self, "public_key"):
            raise RuntimeError("Loopback update fixture public key is already prepared")
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
        self.public_key = public
        return public

    def prepare_existing_public_key(self, public_key: str) -> str:
        """Serve a package signed upstream without importing its private key."""
        if hasattr(self, "public_key"):
            raise RuntimeError("Loopback update fixture public key is already prepared")
        if not isinstance(public_key, str):
            raise ValueError("Expected a base64 32-byte Ed25519 public key")
        try:
            decoded = base64.b64decode(public_key, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Expected a base64 32-byte Ed25519 public key") from exc
        if len(decoded) != 32:
            raise ValueError("Expected a base64 32-byte Ed25519 public key")
        self.public_key = public_key
        # The production bundle checks automatically. Do not expose build 101
        # before the UI test explicitly selects one of its four test stages.
        self.mode = "idle"
        self.payloads["/idle.xml"] = empty_appcast()
        return public_key

    def start(self) -> None:
        """Start the bound source and verify this exact instance over loopback HTTP.

        HTTPConnection connects directly to the bound IPv4 address. It neither
        consults a proxy nor follows a redirect. The random response binds the
        readiness check to this run's source, rather than another local server.
        """
        if not hasattr(self, "public_key"):
            raise RuntimeError("Loopback update fixture EdDSA key is not prepared")
        if self.thread is not None:
            raise RuntimeError("Loopback update fixture was already started")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request("GET", "/healthz")
            response = connection.getresponse()
            body = response.read(1025)
        except (OSError, TimeoutError) as exc:
            raise RuntimeError(f"Loopback update fixture health check unavailable ({type(exc).__name__})") from exc
        finally:
            connection.close()
        if response.status != 200 or body != self._health_body:
            raise RuntimeError(f"Loopback update fixture health/source check failed (HTTP {response.status})")
        if not self.thread.is_alive():
            raise RuntimeError("Loopback update fixture stopped during health check")
        self.url = self.origin_url
        print(json.dumps({"event": "fixture_operation", "fixture": "update_source",
                          "operation": "loopback source health", "state": "SUCCEEDED",
                          "origin_url": self.origin_url, "transport": "loopback_http",
                          "source_nonce_sha256": self.source_nonce_sha256}), flush=True)

    def publish(self, package: Path, signature: str) -> None:
        if self.url != self.origin_url or self.thread is None or not self.thread.is_alive():
            raise RuntimeError("Loopback update fixture is not ready")
        if len(base64.b64decode(signature, validate=True)) != 64:
            raise ValueError("Expected a real EdDSA signature")
        payload = package.read_bytes()
        self.payloads = {
            **({"/idle.xml": empty_appcast()} if self.mode == "idle" else {}),
            "/update.zip": payload,
            "/valid.xml": appcast(self.url + "/update.zip", signature, len(payload)),
            "/invalid.xml": appcast(self.url + "/update.zip", base64.b64encode(bytes(64)).decode(), len(payload)),
            "/forbidden.xml": appcast("http://example.invalid/update.zip", signature, len(payload)),
            "/redirect.xml": appcast(self.url + "/redirect.zip", signature, len(payload)),
        }
        (self.evidence / "update-fixture.json").write_text(json.dumps({
            "kind": "controlled-signed-update", "build": "101", "package_sha256": hashlib.sha256(payload).hexdigest(),
            "valid_feed_sha256": hashlib.sha256(self.payloads["/valid.xml"]).hexdigest(),
            "invalid_feed_sha256": hashlib.sha256(self.payloads["/invalid.xml"]).hexdigest(),
            "forbidden_feed_sha256": hashlib.sha256(self.payloads["/forbidden.xml"]).hexdigest(),
            "redirect_feed_sha256": hashlib.sha256(self.payloads["/redirect.xml"]).hexdigest(),
            "transport": "loopback_http", "origin_url": self.origin_url,
            "source_nonce_sha256": self.source_nonce_sha256, "private_key_archived": False,
        }, indent=2) + "\n")

    def verify_exchange(self) -> None:
        """Verify forbidden/redirect rejection and both signed-package attempts."""
        with self._events_condition:
            if not self._events_condition.wait_for(lambda: self._active_gets == 0, timeout=30):
                raise RuntimeError("Update fixture response accounting did not finish")
            events = [dict(event) for event in self.events]
        controls = [(index, event["path"].removeprefix("/control/")) for index, event in enumerate(events)
                    if event["path"].startswith("/control/") and event["status"] == 200]
        for position, (index, mode) in enumerate(controls):
            if mode != "forbidden":
                continue
            following = controls[position + 1][0] if position + 1 < len(controls) else len(events)
            if any(event["path"] == "/update.zip" for event in events[index + 1:following]):
                raise RuntimeError("Forbidden update URL phase requested a local package")
        expected = ["forbidden", "redirect", "invalid", "valid"]
        if [mode for _, mode in controls] != expected:
            raise RuntimeError("Expected one authenticated forbidden, redirect, invalid and valid fixture switch in order")
        phases = {mode: events[index + 1:(controls[position + 1][0] if position + 1 < len(controls)
                                          else len(events))]
                  for position, (index, mode) in enumerate(controls)}
        for mode in ("forbidden", "redirect"):
            phase_events = phases[mode]
            if not any(event["path"] == "/appcast.xml" and event["status"] == 200
                       and event.get("mode") == mode and event.get("served_bytes", 0) > 0
                       for event in phase_events):
                raise RuntimeError(f"Missing real {mode} update feed exchange")
            if any(event["path"] == "/update.zip" for event in phase_events):
                raise RuntimeError(f"{mode.capitalize()} update URL phase requested a local package")
        if not any(event["path"] == "/redirect.zip" and event["status"] == 302
                   and event.get("mode") == "redirect" for event in phases["redirect"]):
            raise RuntimeError("Missing real redirect response from the loopback source")
        for mode in ("invalid", "valid"):
            phase_events = phases[mode]
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
        try:
            if self.thread is not None:
                self.server.shutdown()
                self.thread.join(timeout=10)
                if self.thread.is_alive():
                    errors.append("Loopback update fixture did not stop")
        except (OSError, RuntimeError) as exc:
            errors.append(f"Loopback update fixture shutdown: {exc}")
        try:
            self.server.server_close()
        except (OSError, RuntimeError) as exc:
            errors.append(f"Loopback update fixture socket cleanup: {exc}")
        (self.evidence / "update-requests.json").write_text(json.dumps(self.events, indent=2) + "\n")
        if errors:
            raise RuntimeError("; ".join(errors))
