"""Isolated HTTPS Sparkle fixture. The App uses ordinary TLS and EdDSA checks."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
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
from xml.sax.saxutils import escape


def _subprocess_env() -> dict[str, str]:
    """Do not pass signing credentials to TLS, DNS, or tunnel processes."""
    return {key: value for key, value in os.environ.items()
            if not key.startswith("TM_E2E_SIGNING_")}


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
            result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=60,
                                    env=_subprocess_env())
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

    def _probe_public_health(self, url: str) -> tuple[bool, str]:
        """Verify the public endpoint with the macOS system TLS client.

        Python may use a CA store different from macOS. The App uses macOS trust,
        so the environment probe must use that trust without disabling TLS.
        """
        try:
            result = subprocess.run(
                ["/usr/bin/curl", "--disable", "--silent", "--show-error", "--fail", "--proto", "=https",
                 "--max-time", "8", "--max-filesize", "1024", "--write-out", "\n%{http_code}", url],
                capture_output=True, timeout=10, check=False, env=_subprocess_env(),
            )
        except subprocess.TimeoutExpired:
            return False, "system curl timed out"
        except OSError as exc:
            return False, f"system curl unavailable (errno={exc.errno})"
        body, separator, status = result.stdout.rpartition(b"\n")
        if not separator or not re.fullmatch(rb"[0-9]{3}", status):
            return False, f"curl exit {result.returncode}; invalid HTTP status output"
        http_status = status.decode("ascii")
        if result.returncode:
            return False, f"curl exit {result.returncode}; HTTP {http_status}"
        if http_status != "200":
            return False, f"HTTP {http_status}"
        if body != b"ready":
            return False, "HTTP 200 with unexpected body"
        return True, "HTTP 200 verified"

    def _dns_publication(self, hostname: str) -> tuple[bool, dict[str, str]]:
        """Wait for DNS publication before the Mac's resolver can cache NXDOMAIN.

        DoH is only a readiness signal. The App and the final health probe still
        resolve the hostname normally and use the macOS TLS trust policy.
        """
        if re.fullmatch(r"[a-z0-9-]+\.trycloudflare\.com", hostname) is None:
            raise RuntimeError("Temporary update hostname is invalid")
        resolvers = {
            "cloudflare": f"https://cloudflare-dns.com/dns-query?name={hostname}&type=A",
            "google": f"https://dns.google/resolve?name={hostname}&type=A",
        }
        statuses: dict[str, str] = {}
        for name, url in resolvers.items():
            try:
                result = subprocess.run(
                    ["/usr/bin/curl", "--disable", "--silent", "--show-error", "--fail",
                     "--proto", "=https", "--max-time", "8", "--max-filesize", "8192",
                     "--header", "accept: application/dns-json", url],
                    capture_output=True, timeout=10, check=False, env=_subprocess_env(),
                )
            except subprocess.TimeoutExpired:
                statuses[name] = "curl-timeout"
                continue
            except OSError as exc:
                statuses[name] = f"curl-unavailable-{exc.errno}"
                continue
            if result.returncode:
                statuses[name] = f"curl-exit-{result.returncode}"
                continue
            try:
                payload = json.loads(result.stdout)
            except (ValueError, UnicodeError):
                statuses[name] = "invalid-json"
                continue
            if not isinstance(payload, dict) or type(payload.get("Status")) is not int:
                statuses[name] = "invalid-dns-response"
            elif payload["Status"] == 3:
                statuses[name] = "NXDOMAIN"
            elif payload["Status"] != 0:
                statuses[name] = f"dns-status-{payload['Status']}"
            else:
                answers = payload.get("Answer", [])
                if not isinstance(answers, list) or not all(isinstance(answer, dict) for answer in answers):
                    statuses[name] = "invalid-dns-response"
                    continue
                names = {hostname}
                # DNS may return a CNAME chain before the A record. Accept only
                # records linked to the requested temporary hostname.
                for _ in answers:
                    for answer in answers:
                        owner = answer.get("name")
                        target = answer.get("data")
                        if (type(answer.get("type")) is int and answer["type"] == 5 and isinstance(owner, str)
                                and isinstance(target, str) and owner.rstrip(".").lower() in names):
                            names.add(target.rstrip(".").lower())
                valid_address = False
                for answer in answers:
                    owner = answer.get("name")
                    address = answer.get("data")
                    if (type(answer.get("type")) is not int or answer["type"] != 1 or not isinstance(owner, str)
                            or owner.rstrip(".").lower() not in names or not isinstance(address, str)):
                        continue
                    try:
                        ipaddress.IPv4Address(address)
                    except ipaddress.AddressValueError:
                        continue
                    valid_address = True
                    break
                statuses[name] = "published" if valid_address else "no-matching-A-record"
        return all(status == "published" for status in statuses.values()), statuses

    def _record_dns_diagnostic(self, hostname: str, trigger: str, remaining_budget: float = 60) -> None:
        """Capture one read-only resolver snapshot after system curl cannot resolve.

        This is restricted to the synthetic hosted-Mac fixture and never changes
        the App's DNS path, TLS verification, or the readiness verdict.
        """
        if (os.environ.get("GITHUB_ACTIONS") != "true" or not os.environ.get("RUNNER_TEMP")
                or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"
                or os.environ.get("RUNNER_OS") != "macOS"
                or re.fullmatch(r"[a-z0-9-]+\.trycloudflare\.com", hostname) is None):
            return
        commands: list[tuple[str, list[str]]] = [
            ("macos-resolvers", ["/usr/sbin/scutil", "--dns"]),
            ("macos-host-cache", ["/usr/bin/dscacheutil", "-q", "host", "-a", "name", hostname]),
        ]
        for resolver, prefix in (("default", []), ("cloudflare-udp", ["@1.1.1.1"]),
                                 ("google-udp", ["@8.8.8.8"])):
            for record_type in ("A", "AAAA"):
                commands.append((f"dig-{resolver}-{record_type.lower()}",
                                 ["/usr/bin/dig", "+time=2", "+tries=1", "+noall", "+answer", "+comments", "+stats",
                                  *prefix, hostname + ".", record_type]))
        commands.extend([
            ("curl-version", ["/usr/bin/curl", "--disable", "--version"]),
            ("curl-ipv4-diagnostic", ["/usr/bin/curl", "--disable", "--ipv4", "--silent", "--show-error",
                                      "--fail", "--proto", "=https", "--max-time", "4", "--max-filesize", "1024",
                                      "--write-out", "\n%{http_code}", f"https://{hostname}/healthz"]),
        ])
        started = time.monotonic()
        budget = min(60, max(0.0, remaining_budget))
        deadline = started + budget
        report = {"scope": "github_hosted_mac_update_fixture", "hostname": hostname, "trigger": trigger,
                  "budget_seconds": round(budget, 3), "commands": []}
        try:
            resolv = Path("/etc/resolv.conf").read_text(errors="replace")
            report["resolv_conf"] = [line.strip() for line in resolv.splitlines()
                                     if line.strip().startswith(("nameserver ", "options "))][:20]
        except OSError as exc:
            report["resolv_conf_error"] = f"errno={exc.errno}"
        for name, argv in commands:
            remaining = deadline - time.monotonic()
            item: dict = {"name": name, "argv": argv}
            if remaining <= 0:
                item["status"] = "skipped-budget"
                report["commands"].append(item)
                continue
            try:
                result = subprocess.run(argv, capture_output=True, check=False, timeout=min(5, remaining),
                                        env=_subprocess_env())
                item["exit_code"] = result.returncode
                lines = result.stdout[:16384].decode("utf-8", "replace").splitlines()
                if name == "macos-resolvers":
                    allowed = ("resolver #", "nameserver[", "flags", "reach", "if_index", "options", "order", "port", "timeout")
                    filtered = []
                    for line in lines:
                        line = line.strip()
                        domain = re.fullmatch(r"(search domain(?:\[\d+\])?|domain)\s*:\s*(\S+)", line)
                        if domain:
                            suffix = domain.group(2).rstrip(".").lower()
                            filtered.append(line if hostname == suffix or hostname.endswith("." + suffix)
                                            else f"{domain.group(1)}: <unrelated>")
                        elif line.startswith(allowed):
                            filtered.append(line)
                    lines = filtered
                elif name == "macos-host-cache":
                    lines = [line.strip() for line in lines
                             if line.strip().startswith(("name:", "ip_address:", "ipv6_address:"))]
                item["stdout"] = "\n".join(lines)[:8192]
                item["stderr"] = result.stderr[:1024].decode("utf-8", "replace")
            except subprocess.TimeoutExpired:
                item["status"] = "timeout"
            except OSError as exc:
                item["status"] = f"unavailable-errno-{exc.errno}"
            report["commands"].append(item)
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
        try:
            (self.evidence / "update-dns-diagnostic.json").write_text(json.dumps(report, indent=2) + "\n")
        except OSError as exc:
            print(json.dumps({"event": "fixture_operation", "fixture": "update_source",
                              "operation": "system DNS diagnostics", "state": "FAILED",
                              "hostname": hostname, "errno": exc.errno}), flush=True)
        else:
            print(json.dumps({"event": "fixture_operation", "fixture": "update_source",
                              "operation": "system DNS diagnostics", "state": "RECORDED",
                              "hostname": hostname, "elapsed_seconds": report["elapsed_seconds"],
                              "evidence": "update-dns-diagnostic.json"}), flush=True)

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
            cwd=self.private, env=_subprocess_env(),
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
        hostname = self.url.removeprefix("https://")
        readiness_started = time.monotonic()
        readiness_deadline = readiness_started + 180
        publication_started = readiness_started
        next_publication_progress = publication_started
        dns_status: dict[str, str] = {}
        while time.monotonic() < readiness_deadline:
            if self.tunnel.poll() is not None:
                raise RuntimeError("Temporary HTTPS tunnel exited during DNS publication")
            published, dns_status = self._dns_publication(hostname)
            now = time.monotonic()
            if published:
                print(json.dumps({"event": "fixture_operation", "fixture": "update_source",
                                  "operation": "public DNS publication", "state": "SUCCEEDED",
                                  "hostname": hostname, "elapsed_seconds": round(now - publication_started, 1),
                                  "resolvers": dns_status}), flush=True)
                break
            if now >= next_publication_progress:
                print(json.dumps({"event": "fixture_operation", "fixture": "update_source",
                                  "operation": "public DNS publication", "state": "WAITING",
                                  "hostname": hostname, "elapsed_seconds": round(now - publication_started, 1),
                                  "resolvers": dns_status}), flush=True)
                next_publication_progress = now + 20
            time.sleep(3)
        else:
            raise RuntimeError(f"Temporary HTTPS tunnel DNS publication unavailable for {hostname}: {dns_status}")
        # Keep the same tunnel alive while the normal macOS resolver catches up;
        # DoH results never replace the App's DNS or the public TLS/health check.
        # Both stages share one bound to fit the independent environment probe.
        started = time.monotonic()
        deadline = readiness_deadline
        next_progress = started
        last_probe = "public endpoint was not checked"
        dns_diagnosed = False
        while time.monotonic() < deadline:
            if self.tunnel.poll() is not None:
                raise RuntimeError("Temporary HTTPS tunnel exited during TLS verification")
            healthy, last_probe = self._probe_public_health(self.url + "/healthz")
            if healthy:
                return self.url
            if not dns_diagnosed and last_probe == "curl exit 6; HTTP 000":
                dns_diagnosed = True
                try:
                    self._record_dns_diagnostic(hostname, last_probe, max(0.0, deadline - time.monotonic()))
                except Exception as exc:
                    # Diagnostics cannot turn the original DNS blocker into a
                    # different result or hide a subsequent successful probe.
                    print(json.dumps({"event": "fixture_operation", "fixture": "update_source",
                                      "operation": "system DNS diagnostics", "state": "FAILED",
                                      "hostname": hostname, "error_type": type(exc).__name__}), flush=True)
            now = time.monotonic()
            if now >= next_progress:
                print(json.dumps({"event": "fixture_operation", "fixture": "update_source",
                                  "operation": "public TLS and origin check", "state": "WAITING",
                                  "hostname": hostname, "elapsed_seconds": round(now - started, 1),
                                  "last_probe": last_probe}), flush=True)
                next_progress = now + 30
            time.sleep(2)
        raise RuntimeError(f"Temporary HTTPS tunnel did not pass public TLS and origin checks ({last_probe})")

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
