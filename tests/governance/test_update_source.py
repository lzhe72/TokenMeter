"""Fixture transport/oracle tests; no App or Sparkle execution is simulated."""
import base64
import hashlib
from http.client import HTTPConnection
import importlib.util
import inspect
import json
from pathlib import Path
import socket
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


def start_unit_source(source):
    """Drive only the fixture handler; this is not a product E2E."""
    with mock.patch.object(source, "_run", return_value=base64.b64encode(bytes(range(32))).decode()):
        source.prepare()
    source.start()


class UpdateSourceTests(unittest.TestCase):
    def test_appcast_records_exact_url_signature_size_and_version(self):
        signature = base64.b64encode(bytes(range(64))).decode()
        tree = ET.fromstring(fixture.appcast("http://127.0.0.1:1234/update.zip", signature, 12))
        item = tree.find("channel/item")
        self.assertEqual(item.find("{http://www.andymatuschak.org/xml-namespaces/sparkle}version").text, "101")
        enclosure = item.find("enclosure")
        self.assertEqual(enclosure.attrib["url"], "http://127.0.0.1:1234/update.zip")
        self.assertEqual(enclosure.attrib["{http://www.andymatuschak.org/xml-namespaces/sparkle}edSignature"], signature)
        self.assertEqual(enclosure.attrib["length"], "12")

    def test_control_requires_nonce_and_never_exposes_private_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = fixture.UpdateSource(root / "secrets", root, port=0)
            package = root / "unit-only-package.zip"
            package.write_bytes(b"Synthetic transport unit fixture, not a signed App")
            start_unit_source(source)
            source.publish(package, base64.b64encode(bytes(range(64))).decode())
            try:
                url = source.url
                with urlopen(url + "/appcast.xml") as response:
                    invalid = response.read()
                with urlopen(url + "/update.zip") as response:
                    response.read()
                for path in ("/sparkle-seed.txt", "/../secrets/sparkle-seed.txt"):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(url + path)
                    self.assertEqual(caught.exception.code, 404)
                with self.assertRaises(HTTPError) as caught:
                    urlopen(Request(url + "/control/valid", method="POST"))
                self.assertEqual(caught.exception.code, 403)
                def control(mode):
                    with urlopen(Request(url + "/control/" + mode, method="POST",
                                         headers={"Authorization": "Bearer " + source.token})) as response:
                        self.assertEqual(response.status, 200)

                control("forbidden")
                with urlopen(url + "/appcast.xml") as response:
                    response.read()
                control("redirect")
                with urlopen(url + "/appcast.xml") as response:
                    response.read()
                connection = HTTPConnection("127.0.0.1", source.server.server_port, timeout=3)
                try:
                    connection.request("GET", "/redirect.zip")
                    self.assertEqual(connection.getresponse().status, 302)
                finally:
                    connection.close()
                control("invalid")
                with urlopen(url + "/appcast.xml") as response:
                    response.read()
                with urlopen(url + "/update.zip") as response:
                    response.read()
                control("valid")
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
            source = fixture.UpdateSource(root / "secrets", root, port=0)
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
                url = source.url
                def control(mode):
                    with urlopen(Request(url + "/control/" + mode, method="POST",
                                         headers={"Authorization": "Bearer " + source.token})) as response:
                        self.assertEqual(response.status, 200)

                control("forbidden")
                with urlopen(url + "/appcast.xml") as response:
                    response.read()
                control("redirect")
                with urlopen(url + "/appcast.xml") as response:
                    response.read()
                connection = HTTPConnection("127.0.0.1", source.server.server_port, timeout=3)
                try:
                    connection.request("GET", "/redirect.zip")
                    self.assertEqual(connection.getresponse().status, 302)
                finally:
                    connection.close()
                control("invalid")
                with urlopen(url + "/appcast.xml") as response:
                    response.read()
                with urlopen(url + "/update.zip") as response:
                    response.read()
                control("valid")
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



class LoopbackUpdateSourceTests(unittest.TestCase):
    """The local source's transport and ownership checks, not product E2E."""

    @staticmethod
    def prepared_source(root: Path, port: int = 0):
        root.mkdir(parents=True, exist_ok=True)
        source = fixture.UpdateSource(root / "secrets", root, port=port)
        with mock.patch.object(source, "_run", return_value=base64.b64encode(bytes(range(32))).decode()) as run:
            public = source.prepare()
        assert public == base64.b64encode(bytes(range(32))).decode()
        assert run.call_count == 1
        return source

    def test_default_is_reserved_loopback_port_and_port_zero_runs_real_http(self):
        self.assertEqual(inspect.signature(fixture.UpdateSource).parameters["port"].default, 49177)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.prepared_source(root)
            try:
                with mock.patch.object(fixture.subprocess, "Popen", side_effect=AssertionError("no tunnel allowed")):
                    self.assertIsNone(source.start())
                self.assertEqual(source.url, source.origin_url)
                self.assertEqual(source.url, f"http://127.0.0.1:{source.server.server_port}")
                self.assertEqual(source.source_nonce_sha256, hashlib.sha256(source.source_nonce.encode()).hexdigest())
                with urlopen(source.url + "/healthz", timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(source.source_nonce.encode(), response.read())
                self.assertFalse((source.private / "ca.pem").exists())
                self.assertFalse((source.private / "server.pem").exists())
                self.assertEqual((source.private / "sparkle-seed.txt").stat().st_mode & 0o777, 0o600)
            finally:
                source.close()

    def test_occupied_port_blocks_without_using_the_existing_listener(self):
        with tempfile.TemporaryDirectory() as directory, socket.socket() as foreign:
            foreign.bind(("127.0.0.1", 0))
            foreign.listen(1)
            occupied = foreign.getsockname()[1]
            with self.assertRaisesRegex(RuntimeError, f"{occupied}.*(occupied|unavailable)"):
                fixture.UpdateSource(Path(directory) / "secrets", Path(directory), port=occupied)
            # The unrelated listener remains untouched and owns its socket.
            with socket.create_connection(("127.0.0.1", occupied), timeout=2):
                pass

    def test_health_redirect_and_wrong_source_body_do_not_mark_ready(self):
        for status in (302, 200):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                source = self.prepared_source(Path(directory))
                handler = source.server.RequestHandlerClass

                def forged_health(request):
                    request.send_response(status)
                    if status == 302:
                        request.send_header("Location", "http://127.0.0.1:9/healthz")
                    request.send_header("Content-Length", "5")
                    request.end_headers()
                    request.wfile.write(b"ready")

                try:
                    with mock.patch.object(handler, "do_GET", forged_health):
                        with self.assertRaisesRegex(RuntimeError, "health|source"):
                            source.start()
                    self.assertIsNone(source.url)
                finally:
                    source.close()

    def test_close_releases_original_port_and_records_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.prepared_source(root / "first")
            try:
                first.start()
                port = first.server.server_port
                with urlopen(first.url + "/healthz", timeout=3) as response:
                    self.assertEqual(response.status, 200)
            finally:
                first.close()
            events = json.loads((root / "first" / "update-requests.json").read_text())
            self.assertTrue(any(item["path"] == "/healthz" for item in events))
            second = self.prepared_source(root / "second", port=port)
            try:
                second.start()
                self.assertEqual(second.server.server_port, port)
            finally:
                second.close()

    def test_cleanup_error_still_releases_bound_port_and_saves_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.prepared_source(root)
            source.start()
            port = source.server.server_port
            real_close = source.server.server_close

            def close_then_fail():
                real_close()
                raise RuntimeError("synthetic close report failure")

            with mock.patch.object(source.server, "server_close", side_effect=close_then_fail):
                with self.assertRaisesRegex(RuntimeError, "socket cleanup"):
                    source.close()
            self.assertTrue((root / "update-requests.json").is_file())
            replacement = fixture.UpdateSource(root / "replacement-secrets", root, port=port)
            replacement.close()

    def test_public_key_length_and_subprocess_secret_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = fixture.UpdateSource(root / "secrets", root, port=0)
            try:
                with mock.patch.object(source, "_run", return_value=base64.b64encode(bytes(31)).decode()):
                    with self.assertRaisesRegex(RuntimeError, "Invalid generated EdDSA public key"):
                        source.prepare()
                self.assertEqual((source.private / "sparkle-seed.txt").stat().st_mode & 0o777, 0o600)
                with mock.patch.dict("os.environ", {"TM_E2E_SIGNING_P12_PASSWORD": "sentinel-secret"}), \
                     mock.patch.object(fixture.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "ok", "")) as called:
                    self.assertEqual(source._run(["xcrun", "swift", "public-key.swift"], "EdDSA public key"), "ok")
                self.assertNotIn("TM_E2E_SIGNING_P12_PASSWORD", called.call_args.kwargs["env"])
                self.assertNotIn("sentinel-secret", json.dumps(called.call_args.kwargs))
            finally:
                source.close()

    def test_forbidden_url_and_redirect_are_real_local_responses_before_signed_package_phases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.prepared_source(root)
            package = root / "update.zip"
            package.write_bytes(b"Synthetic package for transport governance only")
            signature = base64.b64encode(bytes(range(64))).decode()
            source.start()
            source.publish(package, signature)
            try:
                for mode in ("forbidden", "redirect", "invalid", "valid"):
                    request = Request(source.url + "/control/" + mode, method="POST",
                                      headers={"Authorization": "Bearer " + source.token})
                    with urlopen(request, timeout=3) as response:
                        self.assertEqual(response.status, 200)
                    with urlopen(source.url + "/appcast.xml", timeout=3) as response:
                        enclosure = ET.fromstring(response.read()).find("channel/item/enclosure")
                    self.assertIsNotNone(enclosure)
                    if mode == "forbidden":
                        self.assertEqual(enclosure.attrib["url"], "http://example.invalid/update.zip")
                    elif mode == "redirect":
                        self.assertEqual(enclosure.attrib["url"], source.url + "/redirect.zip")
                        connection = HTTPConnection("127.0.0.1", source.server.server_port, timeout=3)
                        try:
                            connection.request("GET", "/redirect.zip")
                            response = connection.getresponse()
                            self.assertEqual(response.status, 302)
                            self.assertEqual(response.getheader("Location"), "http://example.invalid/update.zip")
                            response.read()
                        finally:
                            connection.close()
                    else:
                        self.assertEqual(enclosure.attrib["url"], source.url + "/update.zip")
                        with urlopen(source.url + "/update.zip", timeout=3) as response:
                            self.assertEqual(response.read(), package.read_bytes())
                source.verify_exchange()
                events = source.events
                self.assertFalse(any(item["path"] == "/update.zip" and item.get("mode") == "forbidden"
                                     for item in events))
                self.assertTrue(any(item["path"] == "/redirect.zip" and item["status"] == 302
                                    and item.get("mode") == "redirect" for item in events))
                self.assertNotIn(source.token, json.dumps(events))
            finally:
                source.close()

    def test_control_phases_are_authenticated_and_forbidden_package_request_blocks_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.prepared_source(root)
            package = root / "update.zip"
            package.write_bytes(b"Synthetic package for transport governance only")
            source.start()
            source.publish(package, base64.b64encode(bytes(range(64))).decode())
            try:
                for mode in ("forbidden", "redirect", "invalid", "valid"):
                    with self.assertRaises(HTTPError) as denied:
                        urlopen(Request(source.url + "/control/" + mode, method="POST"), timeout=3)
                    self.assertEqual(denied.exception.code, 403)
                with urlopen(Request(source.url + "/control/forbidden", method="POST",
                                     headers={"Authorization": "Bearer " + source.token}), timeout=3):
                    pass
                with urlopen(source.url + "/appcast.xml", timeout=3):
                    pass
                with urlopen(source.url + "/update.zip", timeout=3):
                    pass
                with self.assertRaisesRegex(RuntimeError, "[Ff]orbidden.*package"):
                    source.verify_exchange()
            finally:
                source.close()
