"""Input/secret handling checks only; these tests do not build or sign an App."""
import base64
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import plistlib
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
        self.credentials = self.root / "credentials"
        self.credentials.mkdir(mode=0o700)
        self.args = {
            "derived-data": str(self.root / "derived"), "output": str(self.root / "output"),
            "feed-url": "https://localhost:8443/appcast.xml", "public-key": base64.b64encode(bytes(32)).decode(),
            "private-key-file": str(self.key), "api-url": "http://127.0.0.1:8765", "run-id": "unit-input-check",
            "build-version": "101", "code-sign-identity": "a" * 40, "signing-keychain": str(self.keychain),
            "credentials-dir": str(self.credentials),
        }

    def run_invalid(self, use_default_feed=False, **changes):
        args = dict(self.args, **changes)
        argv = ["build_update_fixture.py"]
        for name, value in args.items():
            argv.extend(["--" + name, value])
        if use_default_feed:
            argv.append("--use-default-feed")
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

    def test_nonloopback_http_update_feed_is_rejected(self):
        self.run_invalid(**{"feed-url": "http://updates.example.com/appcast.xml"})

    def test_loopback_http_feed_reaches_real_build_boundary(self):
        variants = [
            ("http://127.0.0.1:49177/appcast.xml", False),
            ("http://127.0.0.1:49177/appcast.xml", True),
            ("http://localhost:8443/appcast.xml", False),
            ("http://[::1]:8443/appcast.xml", False),
            ("https://updates.example.com/appcast.xml", False),
        ]
        for index, (feed, use_default) in enumerate(variants):
            with self.subTest(feed=feed, default=use_default):
                args = dict(self.args, **{"feed-url": feed, "output": str(self.root / str(index))})
                argv = ["build_update_fixture.py"]
                for name, value in args.items():
                    argv.extend(["--" + name, value])
                if use_default:
                    argv.append("--use-default-feed")
                selected = subprocess.CompletedProcess(["xcode-select", "-p"], 0,
                                                       "/Applications/Xcode.app/Contents/Developer\n", "")
                failed_build = subprocess.CompletedProcess(["xcodebuild"], 65)
                with patch.object(MODULE.platform, "system", return_value="Darwin"), \
                     patch.object(MODULE.sys, "argv", argv), \
                     patch.object(MODULE.subprocess, "run", side_effect=[selected, failed_build]) as run, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(MODULE.main(), 1)
                self.assertEqual(run.call_count, 2, "Valid input must reach the build, never skip signature checks")
                command = run.call_args_list[1].args[0]
                self.assertEqual(command[0], "xcodebuild")
                self.assertIn("TM_UPDATE_FEED_URL=" + ("" if use_default else feed), command)
                self.assertIn("TM_UPDATE_PUBLIC_KEY=" + self.args["public-key"], command)

    def test_unsafe_feed_inputs_are_rejected_before_build(self):
        for feed in ["https://", "https://:443", "https://@localhost/appcast.xml",
                     "http://localhost:/appcast.xml", "http://127.0.0.1:0/appcast.xml",
                     "http://127.0.0.1:65536/appcast.xml", "http://localhost.evil.example/appcast.xml",
                     "file:///tmp/appcast.xml", "http://127.1/appcast.xml",
                     "https://example.com/appcast.xml?", "https://example.com/appcast.xml#",
                     "https://user:secret@example.com/appcast.xml"]:
            with self.subTest(feed=feed):
                self.run_invalid(**{"feed-url": feed})

    def test_default_feed_flag_rejects_every_other_prepared_source(self):
        for feed in ["http://localhost:49177/appcast.xml", "http://127.0.0.1:49178/appcast.xml",
                     "https://updates.example.com/appcast.xml", "http://127.0.0.1:49177/other.xml"]:
            with self.subTest(feed=feed):
                self.run_invalid(use_default_feed=True, **{"feed-url": feed})

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

    def test_credential_directory_must_be_private_owned_and_within_run(self):
        self.credentials.chmod(0o755)
        self.run_invalid()
        self.credentials.chmod(0o1700)
        self.run_invalid()
        self.credentials.chmod(0o700)
        alias = self.root / "credentials-alias"
        alias.symlink_to(self.credentials)
        self.run_invalid(**{"credentials-dir": str(alias)})
        self.run_invalid(**{"credentials-dir": "relative/credentials"})
        outside = self.root / "other" / "credentials"
        outside.mkdir(parents=True, mode=0o700)
        self.run_invalid(**{"credentials-dir": str(outside)})

    def test_update_fixture_rejects_production_credential_directory(self):
        production = self.root / "Library/Application Support/TokenMeter/credentials"
        production.mkdir(parents=True, mode=0o700)
        with patch.object(MODULE.Path, "home", return_value=self.root):
            self.run_invalid(**{"credentials-dir": str(production),
                                "output": str(production.parent / "output"),
                                "derived-data": str(production.parent / "derived")})

    def test_existing_output_is_preserved(self):
        output = self.root / "output"
        output.mkdir()
        marker = output / "evidence.json"
        marker.write_text("keep evidence")
        self.run_invalid()
        self.assertEqual(marker.read_text(), "keep evidence")

    def test_unsupported_host_architecture_stops_before_build(self):
        with patch.object(MODULE.platform, "machine", return_value="unknown"):
            self.run_invalid()

    def test_build_failure_never_signs_and_uses_host_destination(self):
        for architecture in ("arm64", "x86_64"):
            with self.subTest(architecture=architecture):
                args = dict(self.args, output=str(self.root / architecture))
                argv = ["build_update_fixture.py"]
                for name, value in args.items():
                    argv.extend(["--" + name, value])
                selected = subprocess.CompletedProcess(["xcode-select", "-p"], 0,
                                                       "/Applications/Xcode.app/Contents/Developer\n", "")
                failed_build = subprocess.CompletedProcess(["xcodebuild"], 65)
                output = io.StringIO()
                with patch.object(MODULE.platform, "system", return_value="Darwin"), \
                     patch.object(MODULE.platform, "machine", return_value=architecture), \
                     patch.object(MODULE.sys, "argv", argv), \
                     patch.object(MODULE.subprocess, "run", side_effect=[selected, failed_build]) as run, \
                     contextlib.redirect_stdout(output):
                    self.assertEqual(MODULE.main(), 1)
                # A failed build must stop before signing or packaging any candidate.
                self.assertEqual(run.call_count, 2)
                build_command = run.call_args_list[1].args[0]
                self.assertEqual(build_command[build_command.index("-destination") + 1],
                                 "platform=macOS,arch=" + architecture)
                self.assertIn("TM_TEST_CREDENTIALS_DIR=" + str(self.credentials), build_command)
                self.assertEqual(json.loads(output.getvalue())["status"], "FAIL")
                self.assertFalse((self.root / architecture / "signature.json").exists())

    def test_update_build_rejects_wrong_embedded_credential_directory_before_packaging(self):
        argv = ["build_update_fixture.py"]
        for name, value in self.args.items():
            argv.extend(["--" + name, value])
        selected = subprocess.CompletedProcess(["xcode-select", "-p"], 0,
                                               "/Applications/Xcode.app/Contents/Developer\n", "")
        calls = []
        def run(arguments, **_kwargs):
            calls.append(arguments)
            if arguments[0] == "xcode-select":
                return selected
            if arguments[0] == "xcodebuild":
                app = self.root / "derived/Build/Products/UITesting/TokenMeter.app/Contents"
                app.mkdir(parents=True)
                (app / "Info.plist").write_bytes(plistlib.dumps({
                    "TMTestRunID": self.args["run-id"],
                    "TMTestCredentialsDirectory": str(self.root / "wrong-credentials"),
                }))
                return subprocess.CompletedProcess(arguments, 0)
            raise AssertionError("No packaging command should run after a wrong Info.plist")
        output = io.StringIO()
        with patch.object(MODULE.platform, "system", return_value="Darwin"), \
             patch.object(MODULE.sys, "argv", argv), \
             patch.object(MODULE.subprocess, "run", side_effect=run), \
             contextlib.redirect_stdout(output):
            self.assertEqual(MODULE.main(), 1)
        self.assertEqual(len(calls), 2)
        self.assertIn("wrong credential directory", output.getvalue())
        self.assertFalse((self.root / "output/signature.json").exists())

    def test_update_build_verifies_embedded_feed_key_and_validation_before_signing(self):
        variants = [
            ({"SUFeedURL": "https://wrong.example.com/appcast.xml"}, False),
            ({"SUFeedURL": "http://127.0.0.1:49177/appcast.xml"}, True),
            ({"SUPublicEDKey": base64.b64encode(bytes(range(32))).decode()}, True),
            ({"SUVerifyUpdateBeforeExtraction": False}, True),
        ]
        for index, (wrong, use_default) in enumerate(variants):
            with self.subTest(wrong=next(iter(wrong)), default=use_default):
                args = dict(self.args, **{"output": str(self.root / ("info-output-" + str(index))),
                                         "derived-data": str(self.root / ("info-derived-" + str(index))),
                                         "feed-url": "http://127.0.0.1:49177/appcast.xml"})
                argv = ["build_update_fixture.py"]
                for name, value in args.items():
                    argv.extend(["--" + name, value])
                if use_default:
                    argv.append("--use-default-feed")
                calls = []
                def run(arguments, **_kwargs):
                    calls.append(arguments)
                    if arguments[0] == "xcode-select":
                        return subprocess.CompletedProcess(arguments, 0, "/Applications/Xcode.app/Contents/Developer\n", "")
                    if arguments[0] == "xcodebuild":
                        contents = Path(args["derived-data"]) / "Build/Products/UITesting/TokenMeter.app/Contents"
                        contents.mkdir(parents=True)
                        info = {"TMTestRunID": args["run-id"], "TMTestCredentialsDirectory": str(self.credentials),
                                "SUFeedURL": "" if use_default else args["feed-url"],
                                "SUPublicEDKey": args["public-key"], "SUVerifyUpdateBeforeExtraction": True}
                        info.update(wrong)
                        (contents / "Info.plist").write_bytes(plistlib.dumps(info))
                        return subprocess.CompletedProcess(arguments, 0)
                    raise AssertionError("Invalid embedded update configuration must stop before signing")
                with patch.object(MODULE.platform, "system", return_value="Darwin"), \
                     patch.object(MODULE.sys, "argv", argv), \
                     patch.object(MODULE.subprocess, "run", side_effect=run), \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(MODULE.main(), 1)
                self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
