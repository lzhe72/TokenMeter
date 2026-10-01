"""Result-export bridge checks use synthetic reports and a mocked Node process."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("test_result_export_bridge", ROOT / "scripts/test_result_export.py")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class ResultExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="tokenmeter-result-export-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.report = self.root / "run/result.json"
        self.report.parent.mkdir()
        self.run_id = "local-" + "a" * 32
        self.write_report()
        self.output = self.root / ".local/test-results" / self.run_id
        (self.root / "scripts").mkdir()
        (self.root / "scripts/export_test_result.mjs").write_text("// mocked exporter\n")
        self.node = self.root / "runtime/node"
        self.node.parent.mkdir()
        self.node.write_text("#!/bin/sh\nexit 99\n")
        self.node.chmod(0o700)
        self.addCleanup(patch.stopall)
        patch.object(bridge, "ROOT", self.root).start()
        patch.dict(os.environ, {"TOKENMETER_WORKBOOK_NODE": str(self.node)}).start()

    def write_report(self, state="FAIL", **values):
        self.report.write_text(json.dumps({"schema_version": 2, "run_id": self.run_id,
            "state": state, "expected_cases": ["E2E-TM001-001"], "suites": [],
            "executed_cases": 0, "passed_cases": 0, **values}), encoding="utf-8")

    def fake_export(self, command, **kwargs):
        self.assertEqual(command[:2], [str(self.node), str(self.root / "scripts/export_test_result.mjs")])
        self.assertEqual(command[command.index("--report") + 1], str(self.report))
        self.assertFalse(kwargs.get("shell", False))
        output = Path(command[command.index("--output") + 1])
        output.mkdir(parents=True, exist_ok=True)
        workbook = output / "test-result.xlsx"
        workbook.write_bytes(b"synthetic workbook bytes: no artifact rendering")
        verification = {"schema_version": 1, "state": "PASS", "run_id": self.run_id,
            "source_report": {"path": str(self.report), "sha256": hashlib.sha256(self.report.read_bytes()).hexdigest()},
            "workbook": {"path": workbook.name, "sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
                         "bytes": workbook.stat().st_size}}
        (output / "verification.json").write_text(json.dumps(verification))
        return subprocess.CompletedProcess(command, 0, json.dumps(verification), "")

    def invoke(self, side_effect=None, output=None):
        with patch.object(bridge.subprocess, "run", side_effect=side_effect or self.fake_export) as process:
            receipt = bridge.export_result(self.report, output=output)
        return receipt, process

    def test_success_verifies_assets_preserves_failed_product_report(self):
        original = self.report.read_bytes()
        receipt, process = self.invoke()
        self.assertEqual(receipt["state"], "PASS")
        self.assertEqual(receipt["product_state"], "FAIL")
        self.assertEqual(receipt["report_sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(self.report.read_bytes(), original)
        self.assertEqual(json.loads((self.report.parent / "excel-export.json").read_text()), receipt)
        process.assert_called_once()

    def test_pass_and_blocked_product_states_are_preserved(self):
        for state in ("PASS", "BLOCKED"):
            with self.subTest(state=state):
                self.write_report(state=state)
                original = self.report.read_bytes()
                receipt, _ = self.invoke(output=self.root / state)
                self.assertEqual(receipt["state"], "PASS")
                self.assertEqual(receipt["product_state"], state)
                self.assertEqual(self.report.read_bytes(), original)
                Path(receipt["receipt_path"]).unlink()

    def test_missing_runtime_is_explicit_blocked(self):
        self.node.unlink()
        receipt, process = self.invoke()
        self.assertEqual(receipt["state"], "BLOCKED")
        self.assertIn("Node", receipt["error"])
        self.assertNotIn("workbook", receipt)
        process.assert_not_called()

    def test_relative_runtime_override_is_rejected(self):
        with patch.dict(os.environ, {"TOKENMETER_WORKBOOK_NODE": "node"}):
            receipt, process = self.invoke()
        self.assertEqual(receipt["state"], "BLOCKED")
        process.assert_not_called()

    def test_missing_artifact_dependency_is_blocked(self):
        receipt, _ = self.invoke(lambda command, **_: subprocess.CompletedProcess(command, 1, "", "Error: Cannot find module '@oai/artifact-tool'\ncode: MODULE_NOT_FOUND"))
        self.assertEqual(receipt["state"], "BLOCKED")
        self.assertNotIn("workbook", receipt)

    def test_process_failure_timeout_and_spawn_error_are_visible(self):
        outcomes = [
            (lambda command, **_: subprocess.CompletedProcess(command, 1, "", "render verification failed"), "FAIL"),
            (lambda command, **_: (_ for _ in ()).throw(subprocess.TimeoutExpired(command, 120)), "BLOCKED"),
            (lambda command, **_: (_ for _ in ()).throw(FileNotFoundError("Node disappeared")), "BLOCKED"),
        ]
        for outcome, expected in outcomes:
            with self.subTest(expected=expected):
                receipt, _ = self.invoke(outcome)
                self.assertEqual(receipt["state"], expected)
                self.assertTrue(receipt["error"])
                self.assertEqual(json.loads(self.report.read_text())["state"], "FAIL")
                (self.report.parent / "excel-export.json").unlink()

    def test_unsafe_run_ids_never_start_export(self):
        for value in ("../outside", "/tmp/outside", "", "..", "run/name", "run\\name"):
            with self.subTest(value=value):
                self.write_report(run_id=value)
                receipt, process = self.invoke()
                self.assertEqual(receipt["state"], "FAIL")
                process.assert_not_called()
                (self.report.parent / "excel-export.json").unlink()
        self.assertFalse(self.output.exists())

    def test_success_exit_without_verification_is_not_success(self):
        receipt, _ = self.invoke(lambda command, **_: subprocess.CompletedProcess(command, 0, "PASS", ""))
        self.assertEqual(receipt["state"], "FAIL")
        self.assertNotIn("workbook", receipt)

    def test_missing_workbook_and_wrong_hash_are_rejected(self):
        def changed(command, **kwargs):
            completed = self.fake_export(command, **kwargs)
            (self.output / "test-result.xlsx").write_bytes(b"changed after verification")
            return completed
        receipt, _ = self.invoke(changed)
        self.assertEqual(receipt["state"], "FAIL")
        self.assertNotIn("workbook", receipt)

    def test_missing_workbook_is_a_verification_failure(self):
        def missing(command, **kwargs):
            completed = self.fake_export(command, **kwargs)
            (self.output / "test-result.xlsx").unlink()
            return completed
        receipt, _ = self.invoke(missing)
        self.assertEqual(receipt["state"], "FAIL")
        self.assertNotIn("workbook", receipt)

    def test_wrong_run_or_source_in_verification_is_rejected(self):
        for field in ("run_id", "source_report"):
            with self.subTest(field=field):
                target = self.root / field
                def changed(command, **kwargs):
                    completed = self.fake_export(command, **kwargs)
                    proof = target / "verification.json"
                    value = json.loads(proof.read_text())
                    if field == "run_id":
                        value["run_id"] = "another-run"
                    else:
                        value["source_report"]["sha256"] = "f" * 64
                    proof.write_text(json.dumps(value))
                    return completed
                receipt, _ = self.invoke(changed, output=target)
                self.assertEqual(receipt["state"], "FAIL")

    def test_source_mutation_during_export_cannot_pass(self):
        def changed(command, **kwargs):
            completed = self.fake_export(command, **kwargs)
            self.write_report(state="PASS")
            return completed
        receipt, _ = self.invoke(changed)
        self.assertEqual(receipt["state"], "FAIL")
        self.assertIn("changed", receipt["error"])

    def test_idempotence_reverifies_assets_without_overwriting_receipt(self):
        first, _ = self.invoke()
        before = (self.report.parent / "excel-export.json").read_bytes()
        second, process = self.invoke()
        self.assertEqual(first, second)
        self.assertEqual((self.report.parent / "excel-export.json").read_bytes(), before)
        process.assert_not_called()
        (self.output / "test-result.xlsx").write_bytes(b"tamper")
        invalid, process = self.invoke()
        self.assertEqual(invalid["state"], "FAIL")
        self.assertEqual((self.report.parent / "excel-export.json").read_bytes(), before)
        process.assert_not_called()

    def test_stale_receipt_cannot_apply_to_another_report_or_output(self):
        self.invoke()
        self.write_report(state="PASS")
        receipt, process = self.invoke()
        self.assertEqual(receipt["state"], "FAIL")
        process.assert_not_called()

    def test_failed_export_can_recover_into_new_directory_without_repeating_test(self):
        original_report = self.report.read_bytes()
        with patch.dict(os.environ, {"TOKENMETER_WORKBOOK_NODE": str(self.root / "missing-node")}):
            failed, process = self.invoke()
        self.assertEqual(failed["state"], "BLOCKED")
        process.assert_not_called()
        original_receipt = (self.report.parent / "excel-export.json").read_bytes()
        recovered, process = self.invoke(output=self.root / "recovered-export")
        self.assertEqual(recovered["state"], "PASS")
        process.assert_called_once()
        self.assertNotEqual(failed["receipt_path"], recovered["receipt_path"])
        self.assertEqual((self.report.parent / "excel-export.json").read_bytes(), original_receipt)
        self.assertEqual(self.report.read_bytes(), original_report)
        repeated, process = self.invoke(output=self.root / "recovered-export")
        self.assertEqual(repeated, recovered)
        process.assert_not_called()

    def test_workbook_cannot_escape_or_use_symlink(self):
        def changed(command, **kwargs):
            completed = self.fake_export(command, **kwargs)
            verification_path = self.output / "verification.json"
            verification = json.loads(verification_path.read_text())
            verification["workbook"]["path"] = "../outside.xlsx"
            verification_path.write_text(json.dumps(verification))
            return completed
        receipt, _ = self.invoke(changed)
        self.assertEqual(receipt["state"], "FAIL")

    def test_symlink_output_parent_and_report_are_not_followed(self):
        alias = self.root / "alias"
        alias.symlink_to(self.report.parent, target_is_directory=True)
        with patch.object(bridge.subprocess, "run") as process:
            receipt = bridge.export_result(alias / "result.json")
        self.assertEqual(receipt["state"], "FAIL")
        process.assert_not_called()
        self.assertFalse((self.report.parent / "excel-export.json").exists())

    def test_symlink_output_and_workbook_are_rejected(self):
        destination = self.root / "destination"
        destination.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(destination, target_is_directory=True)
        receipt, process = self.invoke(output=alias / "export")
        self.assertEqual(receipt["state"], "FAIL")
        process.assert_not_called()
        Path(receipt["receipt_path"]).unlink()
        def changed(command, **kwargs):
            completed = self.fake_export(command, **kwargs)
            workbook = self.output / "test-result.xlsx"
            outside = self.root / "outside.xlsx"
            workbook.rename(outside)
            workbook.symlink_to(outside)
            return completed
        receipt, _ = self.invoke(changed)
        self.assertEqual(receipt["state"], "FAIL")


if __name__ == "__main__":
    unittest.main()
