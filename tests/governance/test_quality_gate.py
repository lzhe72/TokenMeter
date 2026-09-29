"""Governance regression checks; these are not TokenMeter product E2E tests."""

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


REPOSITORY = Path(__file__).resolve().parents[2]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, REPOSITORY / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = load_script("quality_gate")
e2e = load_script("e2e")


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "repository"
        self.root.mkdir()
        # Isolate feature/gate tests; the real documentation contract has its own suite.
        # Dedicated cases below remove this stub and exercise the real integration.
        self.baseline_patcher = mock.patch.object(gate, "validate_baseline", return_value=([], {"documents": 0}))
        self.baseline_check = self.baseline_patcher.start()
        self.addCleanup(self.baseline_patcher.stop)
        spec_text = "Synthetic specification for governance tests.\n"
        spec_text += "".join(f"REQ-TM{number:03d}\nAC-TM{number:03d}-001\n" for number in range(1, 13))
        self.write("docs/spec.md", spec_text)
        self.write("sop/SOP-014-e2e.md", "Synthetic SOP for governance tests.\n")
        self.write("scripts/fixtures.py", "# Synthetic fixture generator binding.\n")
        self.write("tests/product_case.py", "# Synthetic test binding; this is not executable product E2E.\n")
        self.datasets = {"schema_version": 1, "datasets": [
            {"id": "planned-data", "description": "Not implemented", "status": "planned", "generator": None},
            {"id": "available-data", "description": "Synthetic available fixtures", "status": "available",
             "generator": "scripts/fixtures.py"},
        ]}
        self.matrix = {"schema_version": 1, "features": [
            {"id": f"TM-{number:03d}", "title": f"Feature {number}", "version": "0.1.0",
             "status": "planned", "spec": "docs/spec.md", "source_requirement": f"REQ-TM{number:03d}", "cases": [
                 {"id": f"E2E-TM{number:03d}-001", "scenario": "Exercise behavior",
                  "acceptance_id": f"AC-TM{number:03d}-001",
                  "expected": "Observed result matches specification", "sop": "sop/SOP-014-e2e.md",
                  "dataset": "planned-data", "data_program": None, "automated_test": None}
             ]} for number in range(1, 13)
        ]}
        self.persist()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def persist(self):
        self.write("tests/datasets.json", json.dumps(self.datasets))
        self.write("tests/feature_matrix.json", json.dumps(self.matrix))

    def errors(self):
        self.persist()
        return gate.validate_manifest(self.root)[0]

    def activate_first(self):
        feature = self.matrix["features"][0]
        feature["status"] = "implemented"
        feature["cases"][0].update(dataset="available-data", data_program="scripts/fixtures.py",
                                     automated_test="tests/product_case.py")
        return feature, feature["cases"][0]

    def test_planned_manifest_passes_traceability_only_with_correct_counts(self):
        errors, counts = gate.validate_manifest(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(counts, {"features": 12, "cases": 12, "implemented": 0, "test_bindings": 0})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(gate.main(["check"], root=self.root), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["scope"], "traceability_only")
        self.assertFalse(result["release_eligible"])

    def test_required_feature_removal_and_empty_case_list_fail(self):
        self.matrix["features"].pop()
        self.matrix["features"][0]["cases"] = []
        errors = self.errors()
        self.assertTrue(any("TM-012" in error and "removed" in error for error in errors))
        self.assertTrue(any("TM-001" in error and "case required" in error for error in errors))

    def test_documentation_failure_blocks_every_phase_before_traceability_or_e2e(self):
        self.baseline_check.return_value = (["required SOP is missing"], {"documents": 1})
        for phase in ("check", "iteration", "release"):
            with self.subTest(phase=phase), mock.patch.object(gate, "validate_manifest") as manifest, \
                    mock.patch.object(gate.subprocess, "run") as execute:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(gate.main([phase], root=self.root), 1)
                self.baseline_check.assert_called_with(self.root)
                manifest.assert_not_called()
                execute.assert_not_called()
                result = json.loads(output.getvalue())
                self.assertEqual(result["scope"], "documentation_baseline_only")
                self.assertEqual(result["state"], "FAIL")
                self.assertFalse(result["release_eligible"])

    def test_importlib_loaded_gate_executes_real_sibling_documentation_checker(self):
        self.baseline_patcher.stop()
        # This temporary repository has valid feature metadata but lacks the docs baseline.
        self.assertEqual(gate.validate_manifest(self.root)[0], [])
        output = io.StringIO()
        with mock.patch.object(gate.subprocess, "run") as execute, contextlib.redirect_stdout(output):
            self.assertEqual(gate.main(["release"], root=self.root), 1)
            execute.assert_not_called()
        result = json.loads(output.getvalue())
        self.assertEqual(result["scope"], "documentation_baseline_only")
        self.assertTrue(any("SOP index" in error for error in result["errors"]))
        self.assertFalse(result["release_eligible"])

    def test_duplicate_feature_case_and_dataset_ids_fail(self):
        self.datasets["datasets"].append(copy.deepcopy(self.datasets["datasets"][0]))
        self.matrix["features"].append(copy.deepcopy(self.matrix["features"][0]))
        errors = self.errors()
        for message in ("duplicate feature: TM-001", "duplicate case: E2E-TM001-001",
                        "duplicate dataset: planned-data"):
            self.assertTrue(any(message in error for error in errors), errors)

    def test_absent_spec_sop_and_generator_fail(self):
        (self.root / "docs/spec.md").unlink()
        (self.root / "sop/SOP-014-e2e.md").unlink()
        (self.root / "scripts/fixtures.py").unlink()
        errors = self.errors()
        for label in ("TM-001.spec", "E2E-TM001-001.sop", "available-data.generator"):
            self.assertTrue(any(label in error for error in errors), errors)

    def test_requirement_and_acceptance_bindings_must_match_feature_and_case_ids(self):
        feature = self.matrix["features"][0]
        case = feature["cases"][0]
        for target, field, invalid_values in (
                (feature, "source_requirement", (None, {}, "REQ-TM002")),
                (case, "acceptance_id", (None, [], "AC-TM001-002", "AC-TM002-001"))):
            original = target[field]
            for invalid in invalid_values:
                with self.subTest(field=field, invalid=invalid):
                    target[field] = invalid
                    self.assertTrue(any(field in error and "must equal" in error for error in self.errors()))
            del target[field]
            self.assertTrue(any(field in error for error in self.errors()))
            target[field] = original

    def test_requirement_and_acceptance_ids_must_exist_as_complete_tokens_in_spec(self):
        path = self.root / "docs/spec.md"
        original = path.read_text()
        for identifier in ("REQ-TM001", "AC-TM001-001"):
            for replacement in ("removed", identifier + "0"):
                with self.subTest(identifier=identifier, replacement=replacement):
                    path.write_text(original.replace(identifier, replacement))
                    self.assertTrue(any(identifier + " not found in spec" in error for error in self.errors()))
        path.write_text(original)
        self.assertEqual(self.errors(), [])

    def test_case_sop_must_reference_existing_independent_root_workflow(self):
        case = self.matrix["features"][0]["cases"][0]
        self.write("docs/testing/execution.md", "A supplementary testing guide.\n")
        for invalid in ("docs/testing/execution.md", "sop/SOP-014-e2e.md#section", "sop/SOP-999-missing.md"):
            with self.subTest(sop=invalid):
                case["sop"] = invalid
                self.assertTrue(any("E2E-TM001-001.sop" in error for error in self.errors()))

    def test_empty_file_cannot_stand_in_for_test_implementation(self):
        self.activate_first()
        self.write("tests/product_case.py", "")
        self.assertTrue(any("automated_test" in error for error in self.errors()))

    def test_active_feature_requires_available_data_program_and_test_binding(self):
        for status in ("in_progress", "implemented"):
            with self.subTest(status=status):
                self.matrix["features"][0]["status"] = status
                errors = self.errors()
                for message in ("active feature needs available dataset", ".data_program", ".automated_test"):
                    self.assertTrue(any(message in error for error in errors), errors)

    def test_valid_active_references_are_counted_but_are_not_execution_evidence(self):
        self.activate_first()
        self.persist()
        errors, counts = gate.validate_manifest(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(counts["implemented"], 1)
        self.assertEqual(counts["test_bindings"], 1)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(gate.main(["check"], root=self.root), 0)
        self.assertFalse(json.loads(output.getvalue())["release_eligible"])

    def test_data_program_must_match_registered_generator(self):
        _, case = self.activate_first()
        self.write("scripts/other_generator.py", "# A different existing program.\n")
        case["data_program"] = "scripts/other_generator.py"
        self.assertTrue(any("differs from registered generator" in error for error in self.errors()))

    def test_case_must_have_explicit_binding_field_even_while_planned(self):
        del self.matrix["features"][0]["cases"][0]["automated_test"]
        self.assertTrue(any("automated_test must be explicit" in error for error in self.errors()))

    def test_file_references_cannot_escape_via_traversal_absolute_path_or_symlink(self):
        outside = self.base / "outside.md"
        outside.write_text("Outside repository", encoding="utf-8")
        (self.root / "docs/link.md").symlink_to(outside)
        for reference in ("../outside.md", str(outside), "docs/link.md"):
            with self.subTest(reference=reference):
                self.matrix["features"][0]["spec"] = reference
                self.assertTrue(any("TM-001.spec" in error for error in self.errors()))

    def test_manifest_documents_cannot_be_symlinks_to_external_files(self):
        for relative in ("tests/feature_matrix.json", "tests/datasets.json"):
            with self.subTest(manifest=relative):
                path = self.root / relative
                original = path.read_text()
                outside = self.base / path.name
                outside.write_text(original, encoding="utf-8")
                path.unlink()
                path.symlink_to(outside)
                self.assertTrue(gate.validate_manifest(self.root)[0])
                path.unlink()
                path.write_text(original, encoding="utf-8")

    def test_wrong_schema_and_container_types_fail_without_exceptions(self):
        originals = copy.deepcopy((self.matrix, self.datasets))
        for document in ("matrix", "datasets"):
            for invalid in (None, [], {"schema_version": True}, {"schema_version": 2},
                            {"schema_version": "1"}, {"schema_version": 1, "features": {}, "datasets": {}}):
                with self.subTest(document=document, invalid=invalid):
                    self.matrix, self.datasets = copy.deepcopy(originals)
                    if document == "matrix":
                        self.matrix = invalid
                    else:
                        self.datasets = invalid
                    self.assertTrue(self.errors())

    def test_malformed_status_types_are_validation_errors(self):
        for location in ("feature", "dataset"):
            for invalid in (None, [], {}, True, 1):
                with self.subTest(location=location, invalid=invalid):
                    target = (self.matrix["features"][0] if location == "feature"
                              else self.datasets["datasets"][0])
                    old = target["status"]
                    target["status"] = invalid
                    self.assertTrue(self.errors())
                    target["status"] = old

    def test_iteration_and_release_ignore_forged_pass_and_zero_exit_runner(self):
        self.write(".local/e2e/forged/result.json", json.dumps({
            "state": "PASS", "release_eligible": True, "executed_cases": 999, "passed_cases": 999}))
        runner = self.write("scripts/e2e.py", "# A zero-exit stub cannot authorize release.\n")
        for phase in ("iteration", "release"):
            with self.subTest(phase=phase):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertNotEqual(gate.main([phase], root=self.root), 0)
                records = [json.loads(line) for line in output.getvalue().splitlines()]
                self.assertEqual(records[-1]["state"], "BLOCKED")
                self.assertTrue(all(record["release_eligible"] is False for record in records))
        self.assertTrue(runner.exists())

    def test_missing_runner_blocks_iteration_and_release(self):
        for phase in ("iteration", "release"):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertNotEqual(gate.main([phase], root=self.root), 0)

    def test_external_runner_symlink_is_not_executed(self):
        sentinel = self.base / "external-runner-executed"
        outside = self.base / "foreign_runner.py"
        outside.write_text(f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\n")
        (self.root / "scripts/e2e.py").symlink_to(outside)
        for phase in ("iteration", "release"):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertNotEqual(gate.main([phase], root=self.root), 0)
        self.assertFalse(sentinel.exists())

    def test_actual_e2e_creates_unique_blocked_reports_with_zero_execution(self):
        release_id = "v0.0.1-20260929T060944Z"
        self.write("releases/current.json", json.dumps({"schema_version": 1, "release_id": release_id}))
        reports = []
        for phase in ("iteration", "release"):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(e2e.main(["--phase", phase], root=self.root), 2)
            summary = json.loads(output.getvalue())
            self.assertFalse(summary["release_eligible"])
            path = Path(summary["report"])
            self.assertTrue(path.is_relative_to(self.root / ".local/e2e"))
            report = json.loads(path.read_text())
            self.assertEqual(report["phase"], phase)
            self.assertEqual(report["release_id"], release_id)
            self.assertEqual(report["manifest_sha256"]["current_release"],
                             hashlib.sha256((self.root / "releases/current.json").read_bytes()).hexdigest())
            self.assertEqual(report["state"], "BLOCKED")
            self.assertEqual(report["executed_cases"], 0)
            self.assertEqual(report["passed_cases"], 0)
            self.assertFalse(report["runner_implemented"])
            self.assertFalse(report["release_eligible"])
            self.assertEqual(report["suites"], [])
            self.assertTrue(report["blockers"])
            self.assertEqual(report["manifest_sha256"]["features"],
                             hashlib.sha256((self.root / "tests/feature_matrix.json").read_bytes()).hexdigest())
            reports.append(path)
        self.assertNotEqual(reports[0], reports[1])
        self.assertTrue(all(path.is_file() for path in reports))

    def test_e2e_corrupt_deep_release_json_still_records_blocked(self):
        self.write("releases/current.json", "[" * 2000 + "]" * 2000)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(e2e.main(["--phase", "release"], root=self.root), 2)
        result = json.loads(output.getvalue())
        report = json.loads(Path(result["report"]).read_text())
        self.assertEqual(report["state"], "BLOCKED")
        self.assertIsNone(report["release_id"])
        self.assertFalse(report["release_eligible"])

    def test_e2e_refuses_local_or_artifact_root_symlinks(self):
        for parent in (".local", ".local/e2e"):
            with self.subTest(parent=parent):
                separate_root = self.base / parent.replace("/", "-").replace(".", "")
                separate_root.mkdir()
                outside = self.base / (separate_root.name + "-outside")
                outside.mkdir()
                link = separate_root / parent
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(outside, target_is_directory=True)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(e2e.main(["--phase", "release"], root=separate_root), 2)
                self.assertEqual(list(outside.iterdir()), [])
                self.assertFalse(json.loads(output.getvalue())["release_eligible"])


if __name__ == "__main__":
    unittest.main()
