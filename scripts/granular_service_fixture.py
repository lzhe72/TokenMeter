"""Owned loopback transport fixture that forwards to the real FastAPI service.

Successful responses always come from the real backend. Only transport failure
and deliberate 503 responses are injected. Audit records never contain tokens.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import socket
import threading
import time
from urllib.parse import urlsplit


class ServiceFixture:
    def __init__(self, upstream: str, *, restart=None):
        target = urlsplit(upstream)
        if target.scheme != "http" or target.hostname != "127.0.0.1" or not target.port:
            raise ValueError("Transport fixture requires an owned loopback upstream")
        self.upstream = upstream
        self.token = secrets.token_urlsafe(32)
        self.mode = "normal"
        self.route = "*"
        self.requests: list[dict] = []
        self.controls: list[dict] = []
        self.stop = threading.Event()
        self.release_delayed = threading.Event()
        self.release_delayed.set()
        self.lock = threading.Lock()
        fixture = self

        def timestamp():
            return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return

            def do_GET(self): self.forward()
            def do_POST(self): self.forward()
            def do_PUT(self): self.forward()
            def do_PATCH(self): self.forward()
            def do_DELETE(self): self.forward()

            def forward(self):
                mode = fixture.mode if fixture.route in ("*", self.path) else "normal"
                auth = self.headers.get("Authorization", "")
                record = {"method": self.command, "route": self.path.split("?", 1)[0],
                          "received_at": timestamp(), "mode": mode, "forwarded": False,
                          "probe": self.headers.get("X-TM-Test-Probe") == "1",
                          "authorization_sha256": hashlib.sha256(auth.encode()).hexdigest() if auth else None}
                with fixture.lock:
                    fixture.requests.append(record)
                if mode == "offline":
                    record.update(status=0, finished_at=timestamp())
                    self.close_connection = True
                    try: self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError: pass
                    return
                if mode == "unavailable":
                    body = b'{"error":{"code":"service_unavailable"}}'
                    self.send_response(503)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    record.update(status=503, finished_at=timestamp())
                    return
                if mode == "delay":
                    started = time.monotonic()
                    while not fixture.stop.is_set() and not fixture.release_delayed.is_set() and time.monotonic() - started < 45:
                        fixture.stop.wait(0.1)
                    record["delayed_seconds"] = round(time.monotonic() - started, 3)
                if fixture.stop.is_set():
                    record.update(status=0, finished_at=timestamp())
                    return
                size = int(self.headers.get("Content-Length", "0"))
                if size < 0 or size > 1048576:
                    self.send_error(413)
                    record.update(status=413, finished_at=timestamp())
                    return
                body = self.rfile.read(size) if size else None
                headers = {name: value for name, value in self.headers.items()
                           if name.lower() not in ("host", "connection", "content-length", "x-tm-test-probe")}
                connection = http.client.HTTPConnection(target.hostname, target.port, timeout=30)
                try:
                    record["forwarded"] = True
                    connection.request(self.command, self.path, body=body, headers=headers)
                    response = connection.getresponse()
                    data = response.read()
                    self.send_response(response.status)
                    for name, value in response.getheaders():
                        if name.lower() not in ("connection", "transfer-encoding", "content-length"):
                            self.send_header(name, value)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    try: self.wfile.write(data)
                    except (BrokenPipeError, ConnectionResetError): record["client_disconnected"] = True
                    record.update(status=response.status, finished_at=timestamp())
                except (OSError, http.client.HTTPException):
                    record.update(status=0, finished_at=timestamp())
                    self.close_connection = True
                finally:
                    connection.close()

        class Control(BaseHTTPRequestHandler):
            def log_message(self, *_args): return

            def authorized(self):
                return self.headers.get("Authorization") == "Bearer " + fixture.token

            def reply(self, status: int, value: dict):
                body = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if not self.authorized(): self.reply(403, {"error": "forbidden"}); return
                with fixture.lock:
                    self.reply(200, {"mode": fixture.mode, "route": fixture.route,
                                     "requests": list(fixture.requests), "controls": list(fixture.controls)})

            def do_POST(self):
                if not self.authorized(): self.reply(403, {"error": "forbidden"}); return
                if self.path == "/release-delayed":
                    fixture.release_delayed.set()
                    fixture.controls.append({"action": "release-delayed", "timestamp": timestamp()})
                    self.reply(200, {"released": True})
                    return
                if self.path == "/restart-backend":
                    if restart is None: self.reply(404, {"error": "unavailable"}); return
                    try:
                        result = restart()
                        fixture.controls.append({"action": "restart-backend", "timestamp": timestamp(), "result": result})
                        self.reply(200, result)
                    except Exception:
                        self.reply(500, {"error": "restart_failed"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length < 4096: raise ValueError("Invalid length")
                    value = json.loads(self.rfile.read(length))
                    mode, route = value["mode"], value.get("route", "*")
                    if mode not in ("normal", "offline", "unavailable", "delay") or not isinstance(route, str):
                        raise ValueError("Invalid transport mode")
                    if route != "*" and (not route.startswith("/v1/") or "?" in route):
                        raise ValueError("Invalid route")
                    fixture.mode, fixture.route = mode, route
                    if mode == "delay": fixture.release_delayed.clear()
                    elif value.get("release_delayed", True): fixture.release_delayed.set()
                    fixture.controls.append({"mode": mode, "route": route, "timestamp": timestamp()})
                    self.reply(200, {"mode": mode, "route": route})
                except (ValueError, KeyError, TypeError):
                    self.reply(400, {"error": "invalid_control"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = False
        self.control = ThreadingHTTPServer(("127.0.0.1", 0), Control)
        self.control.daemon_threads = False
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.control_url = f"http://127.0.0.1:{self.control.server_port}"
        self.threads = [threading.Thread(target=server.serve_forever, daemon=True)
                        for server in (self.server, self.control)]
        for thread in self.threads: thread.start()

    def close(self) -> bool:
        self.stop.set()
        for server in (self.server, self.control):
            server.shutdown()
            server.server_close()
        for thread in self.threads: thread.join(timeout=5)
        return all(not thread.is_alive() for thread in self.threads)
