"""Isolated release-DMG tool tests; Apple notarization is mocked here."""

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("package_release_dmg", ROOT / "scripts/package_release_dmg.py")
release_dmg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_dmg)

TEAM_ID = "ABCDE12345"
AUTHORITY = f"Developer ID Application: TokenMeter Dev ({TEAM_ID})"
APP_SIGNATURE = ("Identifier=org.tokenmeter.TokenMeter\n"
                 "CodeDirectory v=20500 flags=0x10000(runtime) hashes=1\n"
                 f"Authority={AUTHORITY}\n"
                 "Authority=Developer ID Certification Authority G2\n"
                 "Authority=Apple Root CA\n"
                 "Timestamp=Sep 29, 2026 at 12:00:00 PM\n"
                 f"TeamIdentifier={TEAM_ID}\n")
DMG_SIGNATURE = (f"Authority={AUTHORITY}\n"
                 "Authority=Developer ID Certification Authority G2\n"
                 "Authority=Apple Root CA\n"
                 "Timestamp=Sep 29, 2026 at 12:00:00 PM\n"
                 f"TeamIdentifier={TEAM_ID}\n")


def make_app(directory, **overrides):
    app = Path(directory) / "TokenMeter.app"
    contents = app / "Contents"
    contents.mkdir(parents=True)
    info = {"CFBundleIdentifier": release_dmg.PRODUCTION_BUNDLE_ID,
            "CFBundlePackageType": "APPL", "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "100", "SUFeedURL": "https://updates.example.org/appcast.xml",
            "SUPublicEDKey": base64.b64encode(b"k" * 32).decode("ascii")}
    info.update(overrides)
    with (contents / "Info.plist").open("wb") as stream:
        plistlib.dump(info, stream)
    (contents / "MacOS").mkdir()
    (contents / "MacOS" / "TokenMeter").write_bytes(b"signed app payload")
    return app


class PackagingPreflightTests(unittest.TestCase):
    def test_rejects_uitesting_bundle_before_codesign(self):
        with tempfile.TemporaryDirectory() as directory:
            app = make_app(directory, CFBundleIdentifier="org.tokenmeter.TokenMeter.UITesting")
            with mock.patch.object(release_dmg, "require_tools"), mock.patch.object(
                    release_dmg, "run_command") as command:
                with self.assertRaisesRegex(release_dmg.PackagingError, "UITesting"):
                    release_dmg.preflight(app)
            command.assert_not_called()

    def test_rejects_empty_or_local_update_configuration(self):
        cases = ({"SUFeedURL": ""}, {"SUFeedURL": "http://127.0.0.1:5000/appcast.xml"},
                 {"SUFeedURL": "https://updates.example.org:bad/appcast.xml"},
                 {"SUPublicEDKey": ""}, {"SUPublicEDKey": "Zm9v"})
        with tempfile.TemporaryDirectory() as directory:
            for index, overrides in enumerate(cases):
                case = Path(directory) / str(index)
                case.mkdir()
                app = make_app(case, **overrides)
                with self.subTest(overrides=overrides), mock.patch.object(release_dmg, "require_tools"):
                    with self.assertRaises(release_dmg.PackagingError):
                        release_dmg.preflight(app)

    def test_rejects_ad_hoc_missing_runtime_and_wrong_authority(self):
        bad = (APP_SIGNATURE.replace("0x10000(runtime)", "0x10002(adhoc,runtime)"),
               APP_SIGNATURE.replace("0x10000(runtime)", "0x0(none)"),
               APP_SIGNATURE.replace("Developer ID Application:", "Apple Development:"),
               APP_SIGNATURE.replace("Timestamp=Sep 29, 2026 at 12:00:00 PM", "Timestamp=none"))
        with tempfile.TemporaryDirectory() as directory:
            app = make_app(directory)
            for details in bad:
                with self.subTest(details=details.splitlines()[1]), mock.patch.object(
                        release_dmg, "require_tools"), mock.patch.object(
                            release_dmg, "run_command", side_effect=["", details]):
                    with self.assertRaises(release_dmg.PackagingError):
                        release_dmg.preflight(app)

    def test_valid_production_preflight_records_app_tree_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            app = make_app(directory)
            with mock.patch.object(release_dmg, "require_tools"), mock.patch.object(
                    release_dmg, "run_command", side_effect=["", APP_SIGNATURE]):
                result = release_dmg.preflight(app)
            self.assertEqual(result["authority"], AUTHORITY)
            self.assertEqual(result["bundle_id"], release_dmg.PRODUCTION_BUNDLE_ID)
            self.assertEqual(result["app_tree_sha256"], release_dmg.tree_sha256(app))

    def test_preflight_does_not_print_feed_query_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            app = make_app(directory, SUFeedURL="https://updates.example.org/appcast.xml?token=private-value")
            with mock.patch.object(release_dmg, "require_tools"), mock.patch.object(
                    release_dmg, "run_command", side_effect=["", APP_SIGNATURE]):
                result = release_dmg.preflight(app)
            self.assertNotIn("private-value", json.dumps(result))
            self.assertEqual(len(result["update_feed_sha256"]), 64)

    def test_tool_failure_does_not_echo_captured_secret(self):
        failed = subprocess.CompletedProcess(["xcrun", "notarytool"], 1, "",
                                             "secret-password-from-keychain")
        with mock.patch.object(release_dmg.subprocess, "run", return_value=failed):
            with self.assertRaises(release_dmg.PackagingBlocked) as caught:
                release_dmg.run_command(["xcrun", "notarytool"], "Notarization submission",
                                        blocked_on_failure=True)
        self.assertNotIn("secret-password", str(caught.exception))


class PackagingFlowTests(unittest.TestCase):
    def command_simulator(self, app, *, notary_status="Accepted", fail_label=None):
        state = {"commands": [], "stage": None}

        def invoke(args, label, **_options):
            state["commands"].append((tuple(args), label))
            if label == fail_label:
                raise release_dmg.PackagingError(f"{label} failed")
            if args[:2] == ["xcrun", "--find"]:
                return "/usr/bin/tool\n"
            if args[:2] == ["ditto", str(app)]:
                shutil.copytree(app, Path(args[2]), symlinks=True)
                return ""
            if args[:2] == ["hdiutil", "create"]:
                state["stage"] = Path(args[3])
                Path(args[-1]).write_bytes(b"signed mock disk image")
                return ""
            if args[:2] == ["hdiutil", "attach"]:
                mount = Path(args[args.index("-mountpoint") + 1])
                shutil.copytree(state["stage"] / "TokenMeter.app", mount / "TokenMeter.app",
                                symlinks=True)
                (mount / "Applications").symlink_to("/Applications")
                return ""
            if args[:3] == ["xcrun", "stapler", "staple"]:
                with Path(args[3]).open("ab") as stream:
                    stream.write(b"stapled mock ticket")
                return ""
            if args[:3] == ["xcrun", "notarytool", "submit"]:
                return json.dumps({"id": "submission-123", "status": notary_status})
            if args[:3] == ["xcrun", "notarytool", "info"]:
                return json.dumps({"id": "submission-123", "status": notary_status})
            if args[:2] == ["codesign", "--display"]:
                return APP_SIGNATURE if str(args[-1]).endswith(".app") else DMG_SIGNATURE
            if args[0] == "spctl":
                return "source=Notarized Developer ID\n"
            return ""

        return state, invoke

    def test_rejected_notarization_never_publishes_a_dmg_or_report(self):
        with tempfile.TemporaryDirectory() as directory:
            app = make_app(directory)
            output = Path(directory) / "TokenMeter.dmg"
            report = Path(directory) / "package.json"
            state, invoke = self.command_simulator(app, notary_status="Invalid")
            with mock.patch.object(release_dmg, "require_tools"), mock.patch.object(
                    release_dmg, "run_command", side_effect=invoke):
                with self.assertRaisesRegex(release_dmg.PackagingError, "not accepted"):
                    release_dmg.package(app, output, report, "ci-profile", AUTHORITY)
            self.assertFalse(output.exists())
            self.assertFalse(report.exists())
            self.assertFalse(any(args[:3] == ("xcrun", "stapler", "staple")
                                 for args, _label in state["commands"]))

    def test_package_refuses_uitesting_before_notary_tool_lookup(self):
        with tempfile.TemporaryDirectory() as directory:
            app = make_app(directory, CFBundleIdentifier="org.tokenmeter.TokenMeter.UITesting")
            output = Path(directory) / "TokenMeter.dmg"
            report = Path(directory) / "package.json"
            with mock.patch.object(release_dmg, "require_tools"), mock.patch.object(
                    release_dmg, "run_command") as command:
                with self.assertRaisesRegex(release_dmg.PackagingError, "UITesting"):
                    release_dmg.package(app, output, report, "ci-profile", AUTHORITY)
            command.assert_not_called()

    def test_notary_info_must_confirm_the_submission(self):
        with mock.patch.object(release_dmg, "run_command", side_effect=[
                json.dumps({"id": "submission-123", "status": "Accepted"}),
                json.dumps({"id": "another-submission", "status": "Accepted"})]):
            with self.assertRaisesRegex(release_dmg.PackagingError, "does not match"):
                release_dmg.notarize(Path("/tmp/candidate.dmg"), "ci-profile")

    def test_failed_ticket_validation_never_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            app = make_app(directory)
            output = Path(directory) / "TokenMeter.dmg"
            report = Path(directory) / "package.json"
            _state, invoke = self.command_simulator(app, fail_label="Stapled ticket verification")
            with mock.patch.object(release_dmg, "require_tools"), mock.patch.object(
                    release_dmg, "run_command", side_effect=invoke):
                with self.assertRaisesRegex(release_dmg.PackagingError, "Stapled ticket"):
                    release_dmg.package(app, output, report, "ci-profile", AUTHORITY)
            self.assertFalse(output.exists())
            self.assertFalse(report.exists())

    def test_gatekeeper_must_confirm_notarized_developer_id(self):
        with tempfile.TemporaryDirectory() as directory:
            app = make_app(directory)
            output = Path(directory) / "TokenMeter.dmg"
            report = Path(directory) / "package.json"
            _state, invoke = self.command_simulator(app)

            def unnotarized(args, label, **options):
                if args[0] == "spctl":
                    return "source=Developer ID\n"
                return invoke(args, label, **options)

            with mock.patch.object(release_dmg, "require_tools"), mock.patch.object(
                    release_dmg, "run_command", side_effect=unnotarized):
                with self.assertRaisesRegex(release_dmg.PackagingError, "Gatekeeper"):
                    release_dmg.package(app, output, report, "ci-profile", AUTHORITY)
            self.assertFalse(output.exists())
            self.assertFalse(report.exists())

    def test_mocked_complete_path_publishes_hash_bound_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            app = make_app(directory)
            output = Path(directory) / "TokenMeter.dmg"
            report = Path(directory) / "package.json"
            state, invoke = self.command_simulator(app)
            with mock.patch.object(release_dmg, "require_tools"), mock.patch.object(
                    release_dmg, "run_command", side_effect=invoke):
                result = release_dmg.package(app, output, report, "ci-profile", AUTHORITY)
            self.assertTrue(output.is_file())
            self.assertEqual(result, json.loads(report.read_text()))
            self.assertEqual(result["dmg_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual(result["app_tree_sha256"], release_dmg.tree_sha256(app))
            self.assertEqual(result["notarization"]["submission_id"], "submission-123")
            self.assertFalse(result["release_eligible"])
            labels = [label for _args, label in state["commands"]]
            self.assertLess(labels.index("DMG Developer ID signing"),
                            labels.index("Notarization submission"))
            self.assertLess(labels.index("Notarization status confirmation"),
                            labels.index("Notarization ticket stapling"))
            self.assertLess(labels.index("Stapled ticket verification"),
                            labels.index("Gatekeeper DMG assessment"))

    def test_existing_output_is_refused_before_notary_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            app = make_app(directory)
            output = Path(directory) / "TokenMeter.dmg"
            output.write_bytes(b"existing")
            report = Path(directory) / "package.json"
            with mock.patch.object(release_dmg, "require_tools"), mock.patch.object(
                    release_dmg, "run_command") as command:
                with self.assertRaisesRegex(release_dmg.PackagingError, "already exists"):
                    release_dmg.package(app, output, report, "ci-profile", AUTHORITY)
            self.assertEqual(output.read_bytes(), b"existing")
            command.assert_not_called()

    def test_output_inside_source_app_is_refused_before_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            app = make_app(directory)
            output = app / "TokenMeter.dmg"
            report = Path(directory) / "package.json"
            original_hash = release_dmg.tree_sha256(app)
            with mock.patch.object(release_dmg, "require_tools"), mock.patch.object(
                    release_dmg, "run_command", side_effect=["", APP_SIGNATURE]) as command:
                with self.assertRaisesRegex(release_dmg.PackagingError, "outside the source app"):
                    release_dmg.package(app, output, report, "ci-profile", AUTHORITY)
            self.assertEqual(command.call_count, 2)
            self.assertEqual(release_dmg.tree_sha256(app), original_hash)


if __name__ == "__main__":
    unittest.main()
