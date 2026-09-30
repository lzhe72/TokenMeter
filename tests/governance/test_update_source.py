"""Fixture transport/oracle tests; no App or Sparkle execution is simulated."""
import base64
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest import mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("update_fixture", ROOT / "tests/e2e/update_source.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class UnitTunnel:
    def __init__(self):
        self.stdout = io.StringIO("Temporary URL: https://example.trycloudflare.com\n")
        self.terminated = False

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


def start_unit_source(source):
    """Drive only the fixture handler; this is not a product E2E."""
    source.url = "https://example.trycloudflare.com"
    source.tunnel = UnitTunnel()
    source.thread = threading.Thread(target=source.server.serve_forever, daemon=True)
    source.thread.start()


class UpdateSourceTests(unittest.TestCase):
    def test_appcast_records_exact_url_signature_size_and_version(self):
        signature = base64.b64encode(bytes(range(64))).decode()
        tree = ET.fromstring(fixture.appcast("https://localhost:1234/update.zip", signature, 12))
        item = tree.find("channel/item")
        self.assertEqual(item.find("{http://www.andymatuschak.org/xml-namespaces/sparkle}version").text, "101")
        enclosure = item.find("enclosure")
        self.assertEqual(enclosure.attrib["url"], "https://localhost:1234/update.zip")
        self.assertEqual(enclosure.attrib["{http://www.andymatuschak.org/xml-namespaces/sparkle}edSignature"], signature)
        self.assertEqual(enclosure.attrib["length"], "12")

    def test_control_requires_nonce_and_never_exposes_private_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = fixture.UpdateSource(root / "secrets", root)
            package = root / "unit-only-package.zip"
            package.write_bytes(b"Synthetic transport unit fixture, not a signed App")
            start_unit_source(source)
            source.publish(package, base64.b64encode(bytes(range(64))).decode())
            try:
                # The handler is tested over HTTP here; prepare() creates TLS for
                # product execution and no production code disables TLS checks.
                url = f"http://127.0.0.1:{source.server.server_port}"
                with urlopen(url + "/appcast.xml") as response:
                    invalid = response.read()
                with urlopen(url + "/update.zip") as response:
                    response.read()
                for path in ("/server.key", "/../secrets/server.key"):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(url + path)
                    self.assertEqual(caught.exception.code, 404)
                with self.assertRaises(HTTPError) as caught:
                    urlopen(Request(url + "/control/valid", method="POST"))
                self.assertEqual(caught.exception.code, 403)
                with urlopen(Request(url + "/control/valid", method="POST", headers={"Authorization": "Bearer " + source.token})) as response:
                    self.assertEqual(response.status, 200)
                with urlopen(url + "/appcast.xml") as response:
                    self.assertNotEqual(invalid, response.read())
                with self.assertRaises(RuntimeError):
                    source.verify_exchange()  # A valid feed without download is insufficient.
                with urlopen(url + "/update.zip") as response:
                    response.read()
                source.verify_exchange()
            finally:
                source.close()
            self.assertNotIn(source.token, (root / "update-requests.json").read_text())

    def test_verify_waits_until_the_response_write_is_recorded(self):
        """A client can read bytes before the handler finishes recording them."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = fixture.UpdateSource(root / "secrets", root)
            payload = b"isolated update transport payload"
            package = root / "update.zip"
            package.write_bytes(payload)
            start_unit_source(source)
            source.publish(package, base64.b64encode(bytes(range(64))).decode())
            entered = threading.Event()
            release = threading.Event()
            verification_started = threading.Event()
            verification_done = threading.Event()
            errors = []
            handler_type = source.server.RequestHandlerClass
            original_get = handler_type.do_GET

            class DelayedWriter:
                def __init__(self, wrapped):
                    self.wrapped = wrapped

                def write(self, data):
                    result = self.wrapped.write(data)
                    if data == payload:
                        entered.set()
                        if not release.wait(5):
                            raise TimeoutError("Controlled response write was not released")
                    return result

                def __getattr__(self, name):
                    return getattr(self.wrapped, name)

            def delayed_get(handler):
                if handler.path == "/update.zip" and source.valid:
                    handler.wfile = DelayedWriter(handler.wfile)
                return original_get(handler)

            def verify():
                verification_started.set()
                try:
                    source.verify_exchange()
                except Exception as error:
                    errors.append(error)
                finally:
                    verification_done.set()

            try:
                url = f"http://127.0.0.1:{source.server.server_port}"
                with urlopen(url + "/appcast.xml") as response:
                    response.read()
                with urlopen(url + "/update.zip") as response:
                    response.read()
                with urlopen(Request(url + "/control/valid", method="POST",
                                     headers={"Authorization": "Bearer " + source.token})) as response:
                    self.assertEqual(response.status, 200)
                with urlopen(url + "/appcast.xml") as response:
                    response.read()
                with mock.patch.object(handler_type, "do_GET", delayed_get):
                    with urlopen(url + "/update.zip") as response:
                        self.assertEqual(response.read(), payload)
                    self.assertTrue(entered.wait(2))
                    verifier = threading.Thread(target=verify, daemon=True)
                    verifier.start()
                    self.assertTrue(verification_started.wait(2))
                    try:
                        self.assertFalse(verification_done.wait(0.3),
                                         "Verification must await in-flight response accounting")
                    finally:
                        release.set()
                    self.assertTrue(verification_done.wait(5))
                    verifier.join(timeout=1)
                    if errors:
                        raise errors[0]
            finally:
                release.set()
                source.close()

    def test_tunnel_refuses_regular_developer_machine_before_start(self):
        with tempfile.TemporaryDirectory() as directory:
            source = fixture.UpdateSource(Path(directory) / "secrets", Path(directory))
            try:
                with mock.patch.dict("os.environ", {}, clear=True), self.assertRaises(RuntimeError):
                    source.start_tunnel()
                self.assertIsNone(source.tunnel)
                self.assertIsNone(source.thread)
            finally:
                source.close()

    def test_tunnel_uses_pinned_binary_tls_origin_ca_and_public_https_check(self):
        with tempfile.TemporaryDirectory() as directory:
            source = fixture.UpdateSource(Path(directory) / "secrets", Path(directory))
            tunnel = UnitTunnel()
            binary = Path(directory) / "tokenmeter-tools/cloudflared"
            binary.parent.mkdir()
            binary.write_text("unit-only binary placeholder")
            binary.chmod(0o700)
            with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "RUNNER_TEMP": directory,
                                               "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS",
                                               "TM_E2E_SIGNING_P12_PASSWORD": "sentinel-secret"}, clear=True), \
                 mock.patch.object(fixture.Path, "home", return_value=Path(directory)), \
                 mock.patch.object(fixture.subprocess, "Popen", return_value=tunnel) as spawned, \
                 mock.patch.object(source, "_dns_publication", return_value=(True, {"cloudflare": "published", "google": "published"})) as dns, \
                 mock.patch.object(source, "_probe_public_health", return_value=(True, "HTTP 200 verified")) as verified:
                self.assertEqual(source.start_tunnel(), "https://example.trycloudflare.com")
                source.close()
            args = spawned.call_args.args[0]
            self.assertEqual(args[0], str(binary))
            self.assertIn("--origin-ca-pool", args)
            self.assertIn(str(source.private / "ca.pem"), args)
            self.assertIn(source.origin_url, args)
            self.assertNotIn("--no-tls-verify", args)
            self.assertNotIn("TM_E2E_SIGNING_P12_PASSWORD", spawned.call_args.kwargs["env"])
            dns.assert_called_once_with("example.trycloudflare.com")
            verified.assert_called_once_with("https://example.trycloudflare.com/healthz")
            self.assertTrue(tunnel.terminated)

    def test_dns_publication_requires_both_verified_doh_answers(self):
        with tempfile.TemporaryDirectory() as directory:
            source = fixture.UpdateSource(Path(directory) / "secrets", Path(directory))
            published = subprocess.CompletedProcess([], 0, b'{"Status":0,"Answer":[{"name":"example.trycloudflare.com.","type":1,"data":"104.16.230.132"}]}', b"")
            missing = subprocess.CompletedProcess([], 0, b'{"Status":3}', b"")
            malformed = subprocess.CompletedProcess([], 0, b'{"Status":0,"Answer":7}', b"")
            boolean_status = subprocess.CompletedProcess([], 0, b'{"Status":false,"Answer":[{"name":"example.trycloudflare.com.","type":1,"data":"104.16.230.132"}]}', b"")
            boolean_type = subprocess.CompletedProcess([], 0, b'{"Status":0,"Answer":[{"name":"example.trycloudflare.com.","type":true,"data":"104.16.230.132"}]}', b"")
            empty = subprocess.CompletedProcess([], 0, b'{"Status":0,"Answer":[]}', b"")
            bad_ip = subprocess.CompletedProcess([], 0, b'{"Status":0,"Answer":[{"name":"example.trycloudflare.com.","type":1,"data":"not-an-ip"}]}', b"")
            wrong_name = subprocess.CompletedProcess([], 0, b'{"Status":0,"Answer":[{"name":"unrelated.example.","type":1,"data":"104.16.230.132"}]}', b"")
            try:
                with mock.patch.object(fixture.subprocess, "run", side_effect=[
                    missing, published, malformed, published, boolean_status, published,
                    boolean_type, published, empty, published, bad_ip, published, wrong_name, published,
                    published, published,
                ]) as called:
                    self.assertEqual(source._dns_publication("example.trycloudflare.com"),
                                     (False, {"cloudflare": "NXDOMAIN", "google": "published"}))
                    self.assertEqual(source._dns_publication("example.trycloudflare.com"),
                                     (False, {"cloudflare": "invalid-dns-response", "google": "published"}))
                    self.assertEqual(source._dns_publication("example.trycloudflare.com"),
                                     (False, {"cloudflare": "invalid-dns-response", "google": "published"}))
                    self.assertEqual(source._dns_publication("example.trycloudflare.com"),
                                     (False, {"cloudflare": "no-matching-A-record", "google": "published"}))
                    self.assertEqual(source._dns_publication("example.trycloudflare.com"),
                                     (False, {"cloudflare": "no-matching-A-record", "google": "published"}))
                    self.assertEqual(source._dns_publication("example.trycloudflare.com"),
                                     (False, {"cloudflare": "no-matching-A-record", "google": "published"}))
                    self.assertEqual(source._dns_publication("example.trycloudflare.com"),
                                     (False, {"cloudflare": "no-matching-A-record", "google": "published"}))
                    self.assertEqual(source._dns_publication("example.trycloudflare.com"),
                                     (True, {"cloudflare": "published", "google": "published"}))
                commands = [call.args[0] for call in called.call_args_list]
                self.assertEqual(len(commands), 16)
                self.assertTrue(all(command[:2] == ["/usr/bin/curl", "--disable"] for command in commands))
                self.assertTrue(all("--insecure" not in command and "-k" not in command for command in commands))
                self.assertTrue(any("cloudflare-dns.com" in command[-1] for command in commands))
                self.assertTrue(any("dns.google" in command[-1] for command in commands))
            finally:
                source.close()

    def test_tunnel_does_not_touch_system_dns_before_publication(self):
        for publishes in (True, False):
            with self.subTest(publishes=publishes), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = fixture.UpdateSource(root / "secrets", root)
                tunnel = UnitTunnel()
                binary = root / "tokenmeter-tools/cloudflared"
                binary.parent.mkdir()
                binary.write_text("unit-only binary placeholder")
                binary.chmod(0o700)
                clock = [0.0]
                system_probes = []

                def publication(hostname):
                    self.assertEqual(hostname, "example.trycloudflare.com")
                    ready = publishes and clock[0] >= 12
                    return ready, {"cloudflare": "published" if ready else "NXDOMAIN",
                                   "google": "published"}

                def system_probe(url):
                    system_probes.append((clock[0], url))
                    return True, "HTTP 200 verified"

                output = io.StringIO()
                try:
                    with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "RUNNER_TEMP": directory,
                                                       "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS"},
                                         clear=True), \
                         mock.patch.object(fixture.Path, "home", return_value=root), \
                         mock.patch.object(fixture.subprocess, "Popen", return_value=tunnel), \
                         mock.patch.object(source, "_dns_publication", side_effect=publication), \
                         mock.patch.object(source, "_probe_public_health", side_effect=system_probe), \
                         mock.patch.object(fixture.time, "monotonic", side_effect=lambda: clock[0]), \
                         mock.patch.object(fixture.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)), \
                         contextlib.redirect_stdout(output):
                        if publishes:
                            self.assertEqual(source.start_tunnel(), "https://example.trycloudflare.com")
                        else:
                            with self.assertRaisesRegex(RuntimeError, "DNS publication unavailable.*NXDOMAIN"):
                                source.start_tunnel()
                finally:
                    source.close()
                self.assertIn('"operation": "public DNS publication"', output.getvalue())
                if publishes:
                    self.assertEqual(system_probes, [(12.0, "https://example.trycloudflare.com/healthz")])
                else:
                    self.assertEqual(system_probes, [])
                    self.assertGreaterEqual(clock[0], 180)
                self.assertTrue(tunnel.terminated)

    def test_dns_and_system_health_share_one_bounded_readiness_window(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = fixture.UpdateSource(root / "secrets", root)
            tunnel = UnitTunnel()
            binary = root / "tokenmeter-tools/cloudflared"
            binary.parent.mkdir()
            binary.write_text("unit-only binary placeholder")
            binary.chmod(0o700)
            clock = [0.0]
            system_probes = []

            def publication(_hostname):
                ready = clock[0] >= 170
                return ready, {"cloudflare": "published" if ready else "NXDOMAIN", "google": "published"}

            def system_probe(_url):
                system_probes.append(clock[0])
                return False, "curl exit 6; HTTP 000"

            try:
                with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "RUNNER_TEMP": directory,
                                                   "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS"}, clear=True), \
                     mock.patch.object(fixture.Path, "home", return_value=root), \
                     mock.patch.object(fixture.subprocess, "Popen", return_value=tunnel), \
                     mock.patch.object(source, "_dns_publication", side_effect=publication), \
                     mock.patch.object(source, "_probe_public_health", side_effect=system_probe), \
                     mock.patch.object(source, "_record_dns_diagnostic") as diagnosed, \
                     mock.patch.object(fixture.time, "monotonic", side_effect=lambda: clock[0]), \
                     mock.patch.object(fixture.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)), \
                     contextlib.redirect_stdout(io.StringIO()), \
                     self.assertRaisesRegex(RuntimeError, "public TLS and origin checks"):
                    source.start_tunnel()
            finally:
                source.close()
            self.assertTrue(system_probes)
            diagnosed.assert_called_once_with("example.trycloudflare.com", "curl exit 6; HTTP 000", 9.0)
            self.assertGreaterEqual(system_probes[0], 170)
            self.assertLessEqual(clock[0], 182)
            self.assertTrue(tunnel.terminated)

    def test_public_health_uses_system_trust_and_reports_tls_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            source = fixture.UpdateSource(Path(directory) / "secrets", Path(directory))
            try:
                healthy = subprocess.CompletedProcess([], 0, b"ready\n200", b"")
                untrusted = subprocess.CompletedProcess([], 60, b"\n000", b"curl: (60) certificate problem")
                with mock.patch.object(fixture.subprocess, "run", side_effect=[healthy, untrusted]) as called:
                    self.assertEqual(source._probe_public_health("https://example.trycloudflare.com/healthz"),
                                     (True, "HTTP 200 verified"))
                    self.assertEqual(source._probe_public_health("https://example.trycloudflare.com/healthz"),
                                     (False, "curl exit 60; HTTP 000"))
                args = called.call_args.args[0]
                self.assertEqual(args[0], "/usr/bin/curl")
                self.assertEqual(args[1], "--disable")  # Ignore any runner ~/.curlrc TLS overrides.
                self.assertIn("--proto", args)
                self.assertIn("=https", args)
                self.assertIn("--fail", args)
                self.assertNotIn("--insecure", args)
                self.assertNotIn("-k", args)
                self.assertNotIn("--cacert", args)
            finally:
                source.close()

    def test_first_system_dns_failure_records_bounded_read_only_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = fixture.UpdateSource(root / "secrets", root)
            hostname = "example.trycloudflare.com"
            commands = []

            def command(argv, **kwargs):
                commands.append((argv, kwargs))
                stdout = (b"resolver #1\n  nameserver[0] : 1.1.1.1\n"
                          b"  search domain[0] : private.example\n"
                          b"resolver #2\n  domain : trycloudflare.com\n") if argv[0] == "/usr/sbin/scutil" else b"test output\n"
                return subprocess.CompletedProcess(argv, 0, stdout, b"")

            try:
                with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "RUNNER_TEMP": directory,
                                                   "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS"}, clear=True), \
                     mock.patch.object(fixture.subprocess, "run", side_effect=command):
                    source._record_dns_diagnostic(hostname, "curl exit 6; HTTP 000")
                report = json.loads((root / "update-dns-diagnostic.json").read_text())
                self.assertEqual(report["hostname"], hostname)
                self.assertEqual(report["trigger"], "curl exit 6; HTTP 000")
                self.assertEqual(len(commands), 10)
                self.assertTrue(all(kwargs["timeout"] <= 5 for _, kwargs in commands))
                self.assertTrue(all(kwargs["capture_output"] and not kwargs["check"] for _, kwargs in commands))
                self.assertTrue(all(not any(key.startswith("TM_E2E_SIGNING_") for key in kwargs["env"])
                                    for _, kwargs in commands))
                self.assertNotIn("private.example", json.dumps(report))
                self.assertIn("search domain[0]: <unrelated>", json.dumps(report))
                self.assertIn("domain : trycloudflare.com", json.dumps(report))
                argv = [args for args, _ in commands]
                self.assertIn(["/usr/bin/dscacheutil", "-q", "host", "-a", "name", hostname], argv)
                self.assertEqual(sum(args[0] == "/usr/bin/dig" for args in argv), 6)
                self.assertTrue(all("+stats" in args for args in argv if args[0] == "/usr/bin/dig"))
                self.assertEqual(sum("AAAA" in args for args in argv), 3)
                self.assertEqual(sum("A" in args for args in argv), 3)
                self.assertTrue(any(args[0] == "/usr/bin/curl" and "--ipv4" in args for args in argv))
                self.assertTrue(all("--insecure" not in args and "--resolve" not in args for args in argv))
            finally:
                source.close()

    def test_dns_diagnostic_uses_only_remaining_readiness_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = fixture.UpdateSource(root / "secrets", root)
            clock = [100.0]
            calls = []
            def command(argv, **kwargs):
                calls.append(kwargs["timeout"])
                clock[0] += kwargs["timeout"]
                return subprocess.CompletedProcess(argv, 0, b"", b"")
            try:
                with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "RUNNER_TEMP": directory,
                                                   "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS"}, clear=True), \
                     mock.patch.object(fixture.time, "monotonic", side_effect=lambda: clock[0]), \
                     mock.patch.object(fixture.subprocess, "run", side_effect=command):
                    source._record_dns_diagnostic("example.trycloudflare.com", "curl exit 6; HTTP 000", 2)
                report = json.loads((root / "update-dns-diagnostic.json").read_text())
                self.assertEqual(report["budget_seconds"], 2)
                self.assertLessEqual(sum(calls), 2)
                self.assertTrue(any(item.get("status") == "skipped-budget" for item in report["commands"]))
            finally:
                source.close()

    def test_dns_diagnostics_refuse_non_hosted_macs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = fixture.UpdateSource(root / "secrets", root)
            try:
                with mock.patch.dict("os.environ", {}, clear=True), \
                     mock.patch.object(fixture.subprocess, "run") as run:
                    source._record_dns_diagnostic("example.trycloudflare.com", "curl exit 6; HTTP 000")
                run.assert_not_called()
                self.assertFalse((root / "update-dns-diagnostic.json").exists())
            finally:
                source.close()

    def test_tunnel_keeps_same_hostname_during_dns_propagation_and_has_a_bound(self):
        for recovers in (True, False):
            with self.subTest(recovers=recovers), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = fixture.UpdateSource(root / "secrets", root)
                tunnel = UnitTunnel()
                binary = root / "tokenmeter-tools/cloudflared"
                binary.parent.mkdir()
                binary.write_text("unit-only binary placeholder")
                binary.chmod(0o700)
                clock = [0.0]
                probed = []

                def probe(url):
                    probed.append((clock[0], url))
                    if recovers and clock[0] >= 70:
                        return True, "HTTP 200 verified"
                    return False, "curl exit 6; HTTP 000"

                output = io.StringIO()
                try:
                    with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "RUNNER_TEMP": directory,
                                                       "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS"},
                                         clear=True), \
                         mock.patch.object(fixture.Path, "home", return_value=root), \
                         mock.patch.object(fixture.subprocess, "Popen", return_value=tunnel), \
                         mock.patch.object(source, "_dns_publication", return_value=(True, {"cloudflare": "published", "google": "published"})), \
                         mock.patch.object(source, "_probe_public_health", side_effect=probe), \
                         mock.patch.object(source, "_record_dns_diagnostic", side_effect=RuntimeError("diagnostic failed")) as diagnosed, \
                         mock.patch.object(fixture.time, "monotonic", side_effect=lambda: clock[0]), \
                         mock.patch.object(fixture.time, "sleep", side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds)), \
                         contextlib.redirect_stdout(output):
                        if recovers:
                            self.assertEqual(source.start_tunnel(), "https://example.trycloudflare.com")
                        else:
                            with self.assertRaisesRegex(RuntimeError, "curl exit 6; HTTP 000"):
                                source.start_tunnel()
                finally:
                    source.close()
                self.assertEqual({url for _, url in probed}, {"https://example.trycloudflare.com/healthz"})
                diagnosed.assert_called_once_with("example.trycloudflare.com", "curl exit 6; HTTP 000", 180.0)
                self.assertIn('"operation": "system DNS diagnostics", "state": "FAILED"', output.getvalue())
                self.assertIn('"state": "WAITING"', output.getvalue())
                self.assertGreaterEqual(clock[0], 70 if recovers else 180)
                self.assertLess(clock[0], 180 if recovers else 182)
                self.assertTrue(tunnel.terminated)

    def test_tunnel_refuses_self_hosted_runner_and_timeout_names_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = fixture.UpdateSource(Path(directory) / "secrets", Path(directory))
            try:
                with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "RUNNER_TEMP": directory,
                                                   "RUNNER_ENVIRONMENT": "self-hosted", "RUNNER_OS": "macOS"}, clear=True), \
                     mock.patch.object(fixture.subprocess, "Popen") as spawned:
                    with self.assertRaises(RuntimeError):
                        source.start_tunnel()
                    spawned.assert_not_called()
                with mock.patch.object(fixture.subprocess, "run", side_effect=fixture.subprocess.TimeoutExpired(["tool", "secret"], 60)), \
                     self.assertRaisesRegex(RuntimeError, "test CA timed out") as caught:
                    source._run(["tool", "secret"], "test CA")
                self.assertNotIn("secret", str(caught.exception))
            finally:
                source.close()

    def test_tunnel_cleanup_stops_process_even_if_socket_close_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            source = fixture.UpdateSource(Path(directory) / "secrets", Path(directory))
            start_unit_source(source)
            with mock.patch.object(source.server, "server_close", side_effect=RuntimeError("synthetic failure")), \
                 self.assertRaises(RuntimeError):
                source.close()
            self.assertTrue(source.tunnel.terminated)
            source.server.server_close()
