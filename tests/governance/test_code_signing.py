"""Safety tests for temporary CI signing; these do not generate a real identity."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("signing_fixture", ROOT / "tests/e2e/code_signing.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class SigningFixtureTests(unittest.TestCase):
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
