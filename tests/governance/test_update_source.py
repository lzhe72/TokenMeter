"""Fixture transport/oracle tests; no App or Sparkle execution is simulated."""
import base64
import importlib.util
import io
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
                                               "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS"}, clear=True), \
                 mock.patch.object(fixture.Path, "home", return_value=Path(directory)), \
                 mock.patch.object(fixture.subprocess, "Popen", return_value=tunnel) as spawned, \
                 mock.patch.object(source, "_probe_public_health", return_value=(True, "HTTP 200 verified")) as verified:
                self.assertEqual(source.start_tunnel(), "https://example.trycloudflare.com")
                source.close()
            args = spawned.call_args.args[0]
            self.assertEqual(args[0], str(binary))
            self.assertIn("--origin-ca-pool", args)
            self.assertIn(str(source.private / "ca.pem"), args)
            self.assertIn(source.origin_url, args)
            self.assertNotIn("--no-tls-verify", args)
            verified.assert_called_once_with("https://example.trycloudflare.com/healthz")
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
