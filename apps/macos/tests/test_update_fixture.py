"""Input/secret handling checks only; these tests do not build or sign an App."""
import base64
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("update_fixture", Path(__file__).parents[1] / "build_update_fixture.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class UpdateFixtureInputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.key = self.root / "secret.txt"
        self.key.write_text(base64.b64encode(bytes(range(32))).decode())
        self.key.chmod(0o600)
        self.keychain = self.root / "test.keychain-db"
        self.keychain.write_text("unit-test sentinel, not a real keychain")
        self.args = {
            "derived-data": str(self.root / "derived"), "output": str(self.root / "output"),
            "feed-url": "https://localhost:8443/appcast.xml", "public-key": base64.b64encode(bytes(32)).decode(),
            "private-key-file": str(self.key), "api-url": "http://127.0.0.1:8765", "run-id": "unit-input-check",
            "build-version": "101", "code-sign-identity": "a" * 40, "signing-keychain": str(self.keychain),
        }

    def run_invalid(self, **changes):
        args = dict(self.args, **changes)
        argv = ["build_update_fixture.py"]
        for name, value in args.items():
            argv.extend(["--" + name, value])
        output = io.StringIO()
        selected = subprocess.CompletedProcess(["xcode-select", "-p"], 0, "/Applications/Xcode.app/Contents/Developer\n", "")
        with patch.object(MODULE.platform, "system", return_value="Darwin"), \
             patch.object(MODULE.sys, "argv", argv), \
             patch.object(MODULE.subprocess, "run", return_value=selected) as run, \
             contextlib.redirect_stdout(output):
            self.assertEqual(MODULE.main(), 1)
            # Invalid inputs must be rejected before xcodebuild/codesign/sign_update.
            run.assert_called_once_with(["xcode-select", "-p"], text=True, capture_output=True)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["release_eligible"])
        self.assertFalse((self.root / "derived").exists())
        return output.getvalue()

    def test_plain_http_update_feed_is_rejected(self):
        self.run_invalid(**{"feed-url": "http://localhost:8443/appcast.xml"})

    def test_ad_hoc_identity_is_rejected(self):
        self.run_invalid(**{"code-sign-identity": "-"})

    def test_nonlocal_http_api_is_rejected(self):
        self.run_invalid(**{"api-url": "http://team.example.com"})

    def test_world_readable_signing_seed_is_rejected(self):
        self.key.chmod(0o644)
        self.run_invalid()

    def test_malformed_signing_seed_is_never_echoed(self):
        secret = "DO-NOT-ECHO-secret-invalid-base64!"
        self.key.write_text(secret)
        self.assertNotIn(secret, self.run_invalid())

    def test_symlinked_seed_is_rejected(self):
        alias = self.root / "linked-secret.txt"
        alias.symlink_to(self.key)
        self.run_invalid(**{"private-key-file": str(alias)})

    def test_existing_output_is_preserved(self):
        output = self.root / "output"
        output.mkdir()
        marker = output / "evidence.json"
        marker.write_text("keep evidence")
        self.run_invalid()
        self.assertEqual(marker.read_text(), "keep evidence")


if __name__ == "__main__":
    unittest.main()
