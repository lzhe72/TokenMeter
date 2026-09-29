"""Negative checks for native evidence; these synthetic objects are not App E2E."""
import copy
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import plistlib
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("native_e2e", ROOT / "scripts/native_e2e.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "releases/v0.1.0-20260929T074814Z").mkdir(parents=True)
        (self.root / "tests").mkdir()
        self.write("releases/current.json", {"release_id": "v0.1.0-20260929T074814Z"})
        self.write("releases/v0.1.0-20260929T074814Z/00-manifest.json", {"feature_ids": ["TM-001"]})
        self.features = [
            {"id": "TM-001", "status": "planned", "cases": [{"id": "E2E-TM001-001", "native_test": "TokenMeterUITests/TM001AccountUITests/testE2E_TM001_001"}]},
            {"id": "TM-002", "status": "implemented", "cases": [{"id": "E2E-TM002-001", "native_test": "TokenMeterUITests/TM002UITests/testE2E_TM002_001"}]},
            {"id": "TM-003", "status": "planned", "cases": [{"id": "E2E-TM003-001"}]},
        ]
        self.write("tests/feature_matrix.json", {"features": self.features})
        self.tree = {"testNodes": [{"nodeType": "Test Bundle", "name": "TokenMeterUITests", "children": [
            {"nodeType": "Test Suite", "name": "TM001AccountUITests", "children": [
                {"nodeType": "Test Case", "name": "testE2E_TM001_001()", "nodeIdentifier": "TM001AccountUITests/testE2E_TM001_001()", "result": "Passed"}
            ]}
        ]}]}
        self.summary = {"totalTestCount": 1, "passedTests": 1, "failedTests": 0, "skippedTests": 0, "testFailures": [], "result": "Passed"}
        self.identity = "TokenMeterUITests/TM001AccountUITests/testE2E_TM001_001"

    def write(self, path, value):
        (self.root / path).write_text(json.dumps(value))

    def test_target_planned_is_not_excluded_and_delivered_is_regressed(self):
        self.assertEqual(set(native.required_cases(self.root)), {"E2E-TM001-001", "E2E-TM002-001"})

    def test_unknown_target_empty_or_duplicate_native_binding_fails(self):
        for mutation in ("unknown", "empty", "duplicate"):
            with self.subTest(mutation=mutation):
                features = copy.deepcopy(self.features)
                if mutation == "unknown":
                    features.pop(0)
                elif mutation == "empty":
                    features[0]["cases"] = []
                else:
                    features[1]["cases"][0]["native_test"] = self.identity
                self.write("tests/feature_matrix.json", {"features": features})
                with self.assertRaises(native.Blocked):
                    native.required_cases(self.root)

    def test_native_tree_and_summary_require_exact_one_pass(self):
        self.assertEqual(native.check_native_result(self.tree, self.summary, self.identity), [self.identity])

    def test_xcode_16_4_ui_bundle_name_is_preserved_and_original_failure_stays_failed(self):
        tree = json.loads((ROOT / "tests/e2e/fixtures/xcresult-16.4-native-tests.json").read_text())
        summary = json.loads((ROOT / "tests/e2e/fixtures/xcresult-16.4-native-summary.json").read_text())
        with self.assertRaises(native.EvidenceError) as caught:
            native.check_native_result(tree, summary, self.identity)
        self.assertIn(self.identity, str(caught.exception))
        self.assertNotIn("('/TM001", str(caught.exception))
        # Synthetic passing format variant tests parsing only, not product behavior.
        def mark_nodes(node):
            node["result"] = "Passed"
            for child in node.get("children", []):
                mark_nodes(child)
        for node in tree["testNodes"]:
            mark_nodes(node)
        summary.update(result="Passed", failedTests=0, passedTests=1, testFailures=[])
        self.assertEqual(native.check_native_result(tree, summary, self.identity), [self.identity])
        tree["testNodes"][0]["children"][0]["name"] = "WrongUITestBundle"
        with self.assertRaises(native.EvidenceError):
            native.check_native_result(tree, summary, self.identity)

    def test_native_destination_architecture_family_must_match_requested_architecture(self):
        summary = json.loads((ROOT / "tests/e2e/fixtures/xcresult-16.4-native-summary.json").read_text())
        observed = native.native_destination(summary, "arm64", "15.7.9")
        self.assertEqual(observed["architecture"], "arm64e")
        self.assertEqual(observed["architecture_family"], "arm64")
        intel = copy.deepcopy(summary)
        intel["devicesAndConfigurations"][0]["device"]["architecture"] = "x86_64h"
        self.assertEqual(native.native_destination(intel, "x86_64", "15.7.9")["architecture_family"], "x86_64")
        with self.assertRaises(native.EvidenceError):
            native.native_destination(summary, "x86_64", "15.7.9")
        for field, bad in (("platform", "iOS"), ("architecture", "unknown"), ("osVersion", "14.0")):
            mutated = copy.deepcopy(summary)
            mutated["devicesAndConfigurations"][0]["device"][field] = bad
            with self.subTest(field=field), self.assertRaises(native.EvidenceError):
                native.native_destination(mutated, "arm64", "15.7.9")

    def test_failed_skipped_unknown_and_duplicate_native_cases_rejected(self):
        for status in ("Failed", "Skipped", "Expected Failure", "Unknown", "Passed"):
            tree = copy.deepcopy(self.tree)
            leaf = tree["testNodes"][0]["children"][0]["children"][0]
            leaf["result"] = status
            if status == "Passed":
                tree["testNodes"][0]["children"][0]["children"].append(copy.deepcopy(leaf))
            with self.subTest(status=status), self.assertRaises(native.EvidenceError):
                native.check_native_result(tree, self.summary, self.identity)

    def test_missing_and_wrong_native_case_rejected(self):
        for tree in ({"testNodes": []}, {"passed": True}, self.tree):
            with self.assertRaises(native.EvidenceError):
                native.check_native_result(tree, self.summary, self.identity + "Wrong")

    def test_summary_must_not_hide_failure_skip_zero_or_unrecognized_counts(self):
        for field, value in (("totalTestCount", 0), ("passedTests", 0), ("failedTests", 1), ("skippedTests", 1), ("result", "Failed"), ("testFailures", [{"message": "failed"}])):
            summary = dict(self.summary, **{field: value})
            with self.subTest(field=field), self.assertRaises(native.EvidenceError):
                native.check_native_result(self.tree, summary, self.identity)

    def test_bundle_hash_changes_with_contents_and_rejects_symlinks(self):
        bundle = self.root / "result.xcresult"
        bundle.mkdir()
        (bundle / "Info.plist").write_text("first")
        first = native.tree_digest(bundle)
        (bundle / "Info.plist").write_text("second")
        self.assertNotEqual(first, native.tree_digest(bundle))
        (bundle / "external").symlink_to(self.root / "tests")
        with self.assertRaises(native.EvidenceError):
            native.tree_digest(bundle)

    def test_run_directory_must_be_new_and_confined(self):
        self.assertTrue(native.new_run_directory(self.root, "test-123").is_dir())
        with self.assertRaises((native.EvidenceError, FileExistsError)):
            native.new_run_directory(self.root, "test-123")
        for bad in ("../escape", "/tmp/escape", "has space"):
            with self.assertRaises(native.EvidenceError):
                native.new_run_directory(self.root, bad)

    def test_xctestrun_environment_is_only_bound_to_real_ui_target(self):
        products = self.root / "derived/Build/Products"
        products.mkdir(parents=True)
        document = {"TestConfigurations": [{"TestTargets": [{"BlueprintName": "TokenMeterUITests", "EnvironmentVariables": {"existing": "yes"}}]}]}
        (products / "TokenMeter.xctestrun").write_bytes(plistlib.dumps(document))
        output = native.test_configuration(self.root / "derived", {"TM_TEST_RUN_ID": "isolated"})
        environment = plistlib.loads(output.read_bytes())["TestConfigurations"][0]["TestTargets"][0]["EnvironmentVariables"]
        self.assertEqual(environment, {"existing": "yes", "TM_TEST_RUN_ID": "isolated"})
        document["TestConfigurations"][0]["TestTargets"][0]["BlueprintName"] = "OtherTarget"
        (products / "TokenMeter.xctestrun").write_bytes(plistlib.dumps(document))
        with self.assertRaises(native.Blocked):
            native.test_configuration(self.root / "derived", {})

    def test_build_options_are_supported_by_actual_xcode_16_4_help(self):
        # Independent option set from both failed platform jobs in CI run
        # 36541990316. That native usage output has no macOS concurrency option.
        supported = {"-project", "-scheme", "-configuration", "-derivedDataPath",
                     "-destination", "-parallel-testing-enabled"}
        arguments = native.build_command(Path("TokenMeter.xcodeproj"), Path("derived"))
        self.assertEqual({argument for argument in arguments if argument.startswith("-")}, supported)
        self.assertEqual(arguments[arguments.index("-parallel-testing-enabled") + 1], "NO")
        for architecture in ("arm64", "x86_64"):
            with mock.patch.object(native.platform, "machine", return_value=architecture):
                arguments = native.build_command(Path("TokenMeter.xcodeproj"), Path("derived"))
            self.assertEqual(arguments[arguments.index("-destination") + 1], "platform=macOS,arch=" + architecture)


class EvidenceVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = native.new_run_directory(self.root, "nonce")
        self.bundle = self.output / "case/native.xcresult"
        self.bundle.mkdir(parents=True)
        (self.bundle / "Info.plist").write_text("Synthetic verifier unit test artifact")
        (self.output / "case/app.zip").write_bytes(b"Synthetic artifact, never real E2E")
        (self.output / "case/manifest.json").write_text("{}")
        self.now = time.time()
        self.summary = json.loads((ROOT / "tests/e2e/fixtures/xcresult-16.4-native-summary.json").read_text())
        self.destination = native.native_destination(self.summary, "arm64", "15.7.9")
        self.report = {
            "state": "PASS", "runner_implemented": True, "run_id": "nonce", "phase": "iteration",
            "started_at": datetime.fromtimestamp(self.now, timezone.utc).isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "source_commit": "a" * 40, "working_tree_dirty": False,
            "platform": {"architecture": "arm64", "macos": "15.7.9"},
            "manifest_sha256": {"fixture": "digest"}, "executed_cases": 1, "cleanup_completed": True,
            "suites": [{"case_id": "E2E-TM001-001", "exit_code": 0, "xcresult": "case/native.xcresult",
                        "xcresult_sha256": native.tree_digest(self.bundle), "fixture_manifest": "case/manifest.json",
                        "fixture_sha256": native.sha256(self.output / "case/manifest.json"), "app_artifact": "case/app.zip",
                        "app_sha256": native.sha256(self.output / "case/app.zip"), "destination": self.destination}],
        }
        self.path = self.output / "result.json"
        for function, value in (("git", None), ("snapshot", {"fixture": "digest"}),
                                ("required_cases", {"E2E-TM001-001": "target/suite/testCase"}),
                                ("parse_bundle", ({"native": "tree"}, self.summary)),
                                ("check_native_result", ["target/suite/testCase"])):
            patcher = mock.patch.object(native, function, return_value=value)
            mocked = patcher.start()
            self.addCleanup(patcher.stop)
            if function == "git":
                mocked.side_effect = lambda _root, *args: "a" * 40 if args == ("rev-parse", "HEAD") else ""

    def verify(self):
        self.path.write_text(json.dumps(self.report))
        return native.verify_report(self.root, self.path, run_id="nonce", phase="iteration", not_before=self.now)

    def test_verification_reopens_native_artifact_and_does_not_trust_only_json(self):
        self.verify()
        native.parse_bundle.assert_called_once_with(self.root, self.bundle)
        native.check_native_result.assert_called_once()
        native.parse_bundle.side_effect = native.Blocked("Not a real xcresult")
        with self.assertRaises(native.Blocked):
            self.verify()

    def test_forged_run_stale_commit_dirty_source_and_incomplete_coverage_rejected(self):
        for field, bad in (("run_id", "other"), ("source_commit", "b" * 40), ("working_tree_dirty", True),
                           ("executed_cases", 0), ("cleanup_completed", False), ("manifest_sha256", {}),
                           ("started_at", "2000-01-01T00:00:00+00:00"), ("suites", [])):
            with self.subTest(field=field):
                original = self.report[field]
                self.report[field] = bad
                with self.assertRaises(native.EvidenceError):
                    self.verify()
                self.report[field] = original

    def test_changed_or_missing_native_build_and_fixture_artifacts_fail(self):
        for relative in ("case/app.zip", "case/manifest.json", "case/native.xcresult/Info.plist"):
            path = self.output / relative
            original = path.read_bytes()
            path.write_bytes(b"tampered")
            with self.subTest(relative=relative), self.assertRaises(native.EvidenceError):
                self.verify()
            path.write_bytes(original)

    def test_forged_native_destination_is_rejected(self):
        self.report["suites"][0]["destination"] = dict(self.destination, architecture="x86_64h")
        with self.assertRaises(native.EvidenceError):
            self.verify()

    def test_release_cannot_reuse_iteration_pass(self):
        self.report["phase"] = "release"
        self.path.write_text(json.dumps(self.report))
        with self.assertRaises(native.Blocked):
            native.verify_report(self.root, self.path, run_id="nonce", phase="release", not_before=self.now)


if __name__ == "__main__":
    unittest.main()
