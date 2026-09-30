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

    def test_hosted_runner_creates_only_a_private_identity_and_signs_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            calls = []
            def run(args, operation):
                calls.append((args, operation))
                if operation == "create keychain":
                    identity.keychain.touch()
                if operation == "delete signing keychain":
                    identity.keychain.unlink()
                if operation in ("read keychain list", "verify restored keychain list"):
                    return '"/isolated/login.keychain-db"'
                if operation == "certificate fingerprint":
                    return "SHA1 Fingerprint=" + ":".join(["AB"] * 20)
                if operation == "find signing identity":
                    return "AB" * 20
                return ""
            with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "RUNNER_TEMP": directory,
                                               "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS"}), \
                 mock.patch.object(identity, "create_private_bundle", return_value=Path(directory) / "bundle.p12"), \
                 mock.patch.object(identity, "_run", side_effect=run):
                self.assertEqual(identity.prepare(), "AB" * 20)
                identity.close()
            operations = [name for _args, name in calls]
            self.assertIn("sign identity probe", operations)
            self.assertIn("verify identity probe", operations)
            signed = next(args for args, operation in calls if operation == "sign identity probe")
            self.assertEqual(signed[signed.index("--sign") + 1], "AB" * 20)
            self.assertEqual(signed[signed.index("--keychain") + 1], str(identity.keychain))
            self.assertNotIn("trust ephemeral code-signing certificate", operations)
            self.assertFalse(any(args[0] == "sudo" or "trusted-cert" in " ".join(args)
                                 or "/Library/Keychains/System.keychain" in args for args, _name in calls))

    def test_import_uses_same_private_bundle_password_without_logging_it(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            calls = []
            def run(args, operation):
                calls.append((args, operation))
                if operation == "create keychain":
                    identity.keychain.touch()
                if operation == "delete signing keychain":
                    identity.keychain.unlink()
                if operation in ("read keychain list", "verify restored keychain list"):
                    return '"/isolated/login.keychain-db"'
                if operation == "certificate fingerprint":
                    return "SHA1 Fingerprint=" + ":".join(["AB"] * 20)
                if operation == "find signing identity":
                    return "AB" * 20
                return ""
            with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "RUNNER_TEMP": directory,
                                               "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS"}), \
                 mock.patch.object(identity, "create_private_bundle", return_value=Path(directory) / "bundle.p12"), \
                 mock.patch.object(identity, "_run", side_effect=run):
                identity.prepare()
                identity.close()
            arguments = next(args for args, operation in calls if operation == "import identity")
            self.assertEqual(arguments[arguments.index("-P") + 1], identity.bundle_password)
            self.assertTrue(identity.bundle_password)
            self.assertEqual(arguments[arguments.index("-k") + 1], str(identity.keychain))
            lookup = next(args for args, operation in calls if operation == "find signing identity")
            self.assertEqual(lookup, ["security", "find-identity", "-p", "codesigning", str(identity.keychain)])
            self.assertIn((["security", "delete-keychain", str(identity.keychain)], "delete signing keychain"), calls)

    def test_self_hosted_runner_cannot_mutate_keychain(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "RUNNER_TEMP": directory,
                                               "RUNNER_ENVIRONMENT": "self-hosted", "RUNNER_OS": "macOS"}, clear=True), \
                 mock.patch.object(identity, "_run") as run:
                with self.assertRaises(RuntimeError):
                    identity.prepare()
            run.assert_not_called()

    def test_timeout_has_safe_operation_name_without_secret_argv(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            arguments = ["security", "import", "-P", identity.password]
            with mock.patch.object(fixture.subprocess, "run", side_effect=subprocess.TimeoutExpired(arguments, 60)), \
                 self.assertRaisesRegex(RuntimeError, "import identity timed out") as caught:
                identity._run(arguments, "import identity")
            self.assertNotIn(identity.password, str(caught.exception))

    def test_regular_developer_machine_cannot_modify_keychain(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            with mock.patch.dict("os.environ", {}, clear=True), mock.patch.object(identity, "_run") as run:
                with self.assertRaises(RuntimeError):
                    identity.prepare()
                identity.close()
            run.assert_not_called()

    def test_cleanup_restores_previous_keychains_even_when_delete_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            identity.previous_keychains = ["/isolated/login.keychain-db"]
            identity.keychain_created = True
            identity.keychain.touch()
            calls = []

            def run(args, operation):
                calls.append(args)
                if operation == "delete signing keychain":
                    raise RuntimeError("Synthetic cleanup error")
                if operation == "verify restored keychain list":
                    return '"/isolated/login.keychain-db"'
                return ""

            with mock.patch.object(identity, "_run", side_effect=run), self.assertRaises(RuntimeError):
                identity.close()
            self.assertIn(["security", "list-keychains", "-d", "user", "-s", "/isolated/login.keychain-db"], calls)
            self.assertIn(["security", "delete-keychain", str(identity.keychain)], calls)
            self.assertFalse(any("delete-keychain" in args and "/isolated/login.keychain-db" in args for args in calls))

    def test_cleanup_reports_unrestored_keychain_search_list(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            identity.previous_keychains = ["/isolated/login.keychain-db"]
            identity.keychain_created = True
            identity.keychain.touch()
            calls = []
            def run(arguments, operation):
                calls.append(arguments)
                if operation == "verify restored keychain list":
                    return '"/wrong.keychain-db"'
                if operation == "delete signing keychain":
                    identity.keychain.unlink()
                return ""
            with mock.patch.object(identity, "_run", side_effect=run), self.assertRaisesRegex(RuntimeError, "search list"):
                identity.close()
            self.assertIn(["security", "delete-keychain", str(identity.keychain)], calls)

    def test_partial_keychain_creation_with_no_file_needs_no_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            identity.previous_keychains = ["/isolated/login.keychain-db"]
            identity.keychain_created = True
            calls = []
            def run(arguments, operation):
                calls.append(operation)
                if operation == "verify restored keychain list":
                    return '"/isolated/login.keychain-db"'
                return ""
            with mock.patch.object(identity, "_run", side_effect=run):
                identity.close()
            self.assertNotIn("delete signing keychain", calls)
            self.assertFalse(identity.keychain_created)

    def test_failed_probe_still_restores_and_deletes_owned_keychain(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            calls = []
            def run(arguments, operation):
                calls.append(operation)
                if operation == "read keychain list" or operation == "verify restored keychain list":
                    return '"/isolated/login.keychain-db"'
                if operation == "certificate fingerprint":
                    return "SHA1 Fingerprint=" + ":".join(["AB"] * 20)
                if operation == "find signing identity":
                    return "AB" * 20
                if operation == "create keychain":
                    identity.keychain.touch()
                if operation == "sign identity probe":
                    raise RuntimeError("Synthetic signing failure")
                if operation == "delete signing keychain":
                    identity.keychain.unlink()
                return ""
            with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true", "RUNNER_TEMP": directory,
                                               "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS"}), \
                 mock.patch.object(identity, "create_private_bundle", return_value=Path(directory) / "bundle.p12"), \
                 mock.patch.object(identity, "_run", side_effect=run):
                with self.assertRaisesRegex(RuntimeError, "Synthetic signing failure"):
                    identity.prepare()
                identity.close()
            self.assertIn("restore keychain list", calls)
            self.assertIn("delete signing keychain", calls)
            self.assertFalse(identity.keychain.exists())

    def test_failing_tool_does_not_echo_private_password(self):
        with tempfile.TemporaryDirectory() as directory:
            identity = fixture.SigningIdentity(Path(directory) / "signing")
            result = mock.Mock(returncode=1, stdout=identity.password, stderr=identity.password)
            with mock.patch.object(fixture.subprocess, "run", return_value=result), self.assertRaises(RuntimeError) as caught:
                identity._run(["security", "create-keychain", "-p", identity.password], "create keychain")
            self.assertNotIn(identity.password, str(caught.exception))
