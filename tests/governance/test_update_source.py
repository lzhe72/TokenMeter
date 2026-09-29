"""Fixture transport/oracle tests; no App or Sparkle execution is simulated."""
import base64
import importlib.util
from pathlib import Path
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

    def test_ca_trust_refuses_regular_developer_machine(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as directory:
            source = fixture.UpdateSource(Path(directory) / "secrets", Path(directory))
            try:
                with mock.patch.dict("os.environ", {}, clear=True), self.assertRaises(RuntimeError):
                    source.trust_on_ephemeral_ci()
            finally:
                source.close()

    def test_ca_trust_and_cleanup_use_noninteractive_admin_domain_and_exact_certificate(self):
        with tempfile.TemporaryDirectory() as directory:
            source = fixture.UpdateSource(Path(directory) / "secrets", Path(directory))
            calls = []
            def run(arguments, operation):
                calls.append(arguments)
                return "sha1 Fingerprint=" + ":".join(["AB"] * 20) if operation == "CA identity" else ""
            with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "RUNNER_TEMP": directory,
                                               "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS"}, clear=True), \
                 mock.patch.object(source, "_run", side_effect=run):
                source.trust_on_ephemeral_ci()
                source.close()
            self.assertIn(["sudo", "-n", "/usr/bin/security", "add-trusted-cert", "-d", "-r", "trustRoot", "-p", "ssl",
                           "-s", "localhost", "-k", "/Library/Keychains/System.keychain", str(source.private / "ca.pem")], calls)
            self.assertIn(["sudo", "-n", "/usr/bin/security", "remove-trusted-cert", "-d", str(source.private / "ca.pem")], calls)
            self.assertIn(["sudo", "-n", "/usr/bin/security", "delete-certificate", "-Z", "AB" * 20,
                           "/Library/Keychains/System.keychain"], calls)

    def test_ca_trust_refuses_self_hosted_runner_and_timeout_names_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = fixture.UpdateSource(Path(directory) / "secrets", Path(directory))
            try:
                with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "RUNNER_TEMP": directory,
                                                   "RUNNER_ENVIRONMENT": "self-hosted", "RUNNER_OS": "macOS"}, clear=True), \
                     mock.patch.object(source, "_run") as run:
                    with self.assertRaises(RuntimeError):
                        source.trust_on_ephemeral_ci()
                    run.assert_not_called()
                with mock.patch.object(fixture.subprocess, "run", side_effect=fixture.subprocess.TimeoutExpired(["tool", "secret"], 60)), \
                     self.assertRaisesRegex(RuntimeError, "temporary CA trust timed out") as caught:
                    source._run(["tool", "secret"], "temporary CA trust")
                self.assertNotIn("secret", str(caught.exception))
            finally:
                with mock.patch.object(source, "_run"):
                    source.close()

    def test_failed_trust_removal_still_attempts_certificate_removal(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as directory:
            source = fixture.UpdateSource(Path(directory) / "secrets", Path(directory))
            source.trusted = source.certificate_added = True
            source.keychain = "isolated-test-keychain"
            operations = []

            def operation(args, name):
                operations.append(name)
                if name == "remove test CA trust":
                    raise RuntimeError("Synthetic failed trust cleanup")
                return "sha1 Fingerprint=AA:BB" if name == "CA identity" else ""

            with mock.patch.object(source, "_run", side_effect=operation), self.assertRaises(RuntimeError):
                source.close()
            self.assertIn("remove test CA certificate", operations)
            self.assertFalse(source.certificate_added)
