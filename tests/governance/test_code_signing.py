"""Isolated signing fixture checks; no test modifies a real Keychain."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("signing_fixture", ROOT / "tests/e2e/code_signing.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class SigningFixtureTests(unittest.TestCase):
    def test_private_bundle_uses_compatible_wrapping_and_requires_nonempty_password(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            bundle = identity.create_private_bundle()
            self.assertGreater(len(identity.bundle_password), 20)
            self.assertEqual(identity.bundle_password_file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(bundle.stat().st_mode & 0o777, 0o600)
            result = subprocess.run(["openssl", "pkcs12", "-in", str(bundle), "-info", "-noout",
                                     "-passin", "file:" + str(identity.bundle_password_file)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            information = result.stderr.lower()
            self.assertIn("sha1", information)
            self.assertEqual(information.count("pbewithsha1and3-keytripledes-cbc"), 2)
            self.assertNotIn("aes", information)
            empty = subprocess.run(["openssl", "pkcs12", "-in", str(bundle), "-noout", "-passin", "pass:"],
                                   capture_output=True, text=True, check=False)
            self.assertNotEqual(empty.returncode, 0)
            certificate = subprocess.run(["openssl", "x509", "-in", str(identity.certificate), "-text", "-noout"],
                                         capture_output=True, text=True, check=True).stdout
            self.assertIn("sha256WithRSAEncryption", certificate)

    def test_import_uses_same_private_bundle_password_without_logging_it(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            calls = []
            def run(args, operation):
                calls.append((args, operation))
                if operation == "read keychain list":
                    return '"/isolated/login.keychain-db"'
                if operation == "certificate fingerprint":
                    return "SHA1 Fingerprint=" + ":".join(["AB"] * 20)
                if operation == "verify identity":
                    return "AB" * 20
                return ""
            with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "RUNNER_TEMP": directory}), \
                 mock.patch.object(identity, "create_private_bundle", return_value=Path(directory) / "bundle.p12"), \
                 mock.patch.object(identity, "_run", side_effect=run):
                identity.prepare()
            arguments = next(args for args, operation in calls if operation == "import identity")
            self.assertEqual(arguments[arguments.index("-P") + 1], identity.bundle_password)
            self.assertTrue(identity.bundle_password)

    def test_regular_developer_machine_cannot_modify_keychain(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            with mock.patch.dict("os.environ", {}, clear=True), mock.patch.object(identity, "_run") as run:
                with self.assertRaises(RuntimeError):
                    identity.prepare()
                identity.close()
            run.assert_not_called()

    def test_cleanup_restores_previous_keychains_and_deletes_own_even_when_trust_removal_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            identity.previous_keychains = ["/isolated/login.keychain-db"]
            identity.trust_attempted = identity.keychain_created = True
            calls = []

            def run(args, operation):
                calls.append(args)
                if operation == "remove signing trust":
                    raise RuntimeError("Synthetic cleanup error")
                return ""

            with mock.patch.object(identity, "_run", side_effect=run), self.assertRaises(RuntimeError):
                identity.close()
            self.assertIn(["security", "list-keychains", "-d", "user", "-s", "/isolated/login.keychain-db"], calls)
            self.assertIn(["security", "delete-keychain", str(identity.keychain)], calls)
            self.assertFalse(any("delete-keychain" in args and "/isolated/login.keychain-db" in args for args in calls))

    def test_failing_tool_does_not_echo_private_password(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            result = mock.Mock(returncode=1, stdout=identity.password, stderr=identity.password)
            with mock.patch.object(fixture.subprocess, "run", return_value=result), self.assertRaises(RuntimeError) as caught:
                identity._run(["security", "create-keychain", "-p", identity.password], "create keychain")
            self.assertNotIn(identity.password, str(caught.exception))
