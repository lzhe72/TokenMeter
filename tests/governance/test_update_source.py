"""Fixture transport/oracle tests; no App or Sparkle execution is simulated."""
import base64
import importlib.util
from pathlib import Path
import tempfile
import unittest
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

    def test_ca_trust_refuses_regular_developer_machine(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as directory:
            source = fixture.UpdateSource(Path(directory) / "secrets", Path(directory))
            try:
                with mock.patch.dict("os.environ", {}, clear=True), self.assertRaises(RuntimeError):
                    source.trust_on_ephemeral_ci()
            finally:
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
