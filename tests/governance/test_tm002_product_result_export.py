"""Fixed export contract tests; these synthetic JSON fixtures are not product E2E."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "tm002_product_result_export", ROOT / "scripts/tm002_product_result_export.py")
export = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TM002ProductResultExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tm002-product-export-", dir=ROOT / ".local")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / "source"
        self.run.mkdir()
        self.output = self.root / "result-workbook"
        self.run_id = "local-" + uuid.uuid4().hex
        self.code = {}
        self.snapshots = []
        for relative in ("scripts/granular_permissions.py",
                         "apps/desktop/e2e/granular-permissions.spec.ts", "tests/test_cases.json"):
            target = self.run / "test-code" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            raw = relative.encode()
            target.write_bytes(raw)
            self.code[relative] = sha(raw)
            self.snapshots.append({"path": "test-code/" + relative, "sha256": sha(raw), "bytes": len(raw)})
        identity = "TC-TM002-SELECT-01"
        self.report = {
            "schema_version": 1, "scope": "tm002_granular_targeted_development_probe",
            "release_id": "v0.2.0-20261001T034118Z", "run_id": self.run_id,
            "source_commit": "a" * 40, "candidate_tree": "b" * 40,
            "state": "BLOCKED", "release_eligible": False, "cleanup_completed": True,
            "started_at": "2026-10-01T00:00:00Z", "finished_at": "2026-10-01T00:00:01Z",
            "expected_cases": [identity], "test_inputs_sha256": self.code,
            "test_code_snapshot": self.snapshots,
            "preflight": {"state": "BLOCKED", "reason": "Independent test account is absent"},
            "tc_results": [{"case_id": identity, "parent_id": None, "state": "BLOCKED",
                            "reason": "Independent test account is absent", "task_ids": ["TASK-TM002-PICKER"],
                            "ac_ids": ["AC-TM002-001"], "step_results": [],
                            "started_at": None, "finished_at": None, "evidence": {},
                            "cleanup": {"completed": False}}],
        }

    def save(self):
        target = self.run / "result.json"
        target.write_text(json.dumps(self.report, ensure_ascii=False) + "\n", encoding="utf-8")
        return target

    def test_real_blocked_semantics_export_and_repeat_are_immutable(self):
        source = self.save()
        before = source.read_bytes()
        receipt = export.export_result(source, self.output)
        self.assertEqual(receipt["state"], "PASS")
        self.assertEqual(receipt["product_state"], "BLOCKED")
        verification = json.loads((self.output / export.VERIFICATION).read_text())
        self.assertEqual(verification["product_state"], "BLOCKED")
        self.assertEqual(verification["rows"]["tc"], 1)
        self.assertEqual(verification["rows"]["steps"], 0)
        self.assertEqual(source.read_bytes(), before)
        saved = (self.output / export.RECEIPT).read_bytes()
        workbook = (self.output / f"TokenMeter测试结果-{self.run_id}.xlsx").read_bytes()
        self.assertEqual(export.export_result(source, self.output), receipt)
        self.assertEqual((self.output / export.RECEIPT).read_bytes(), saved)
        self.assertEqual((self.output / f"TokenMeter测试结果-{self.run_id}.xlsx").read_bytes(), workbook)

    def test_fail_state_remains_fail_without_invented_steps(self):
        self.report.pop("preflight")
        item = self.report["tc_results"][0]
        item.update(state="FAIL", reason="Playwright assertion failed", started_at="2026-10-01T00:00:00Z",
                    finished_at="2026-10-01T00:00:01Z")
        self.report["state"] = "FAIL"
        source = self.save()
        receipt = export.export_result(source, self.output)
        self.assertEqual(receipt["state"], "PASS")
        self.assertEqual(receipt["product_state"], "FAIL")
        self.assertEqual(json.loads((self.output / export.VERIFICATION).read_text())["rows"]["steps"], 0)

    def test_targeted_variant_can_be_exported_without_parent_attempt(self):
        variant = "TC-TM002-SELECT-02#FIRST_CANCEL"
        self.report["expected_cases"] = [variant]
        self.report["tc_results"][0].update(case_id=variant, parent_id="TC-TM002-SELECT-02")
        receipt = export.export_result(self.save(), self.output)
        self.assertEqual(receipt["state"], "PASS")
        self.assertEqual(receipt["product_state"], "BLOCKED")

    def test_actual_failed_step_requires_and_retains_its_event_original(self):
        self.report.pop("preflight")
        identity = self.report["expected_cases"][0]
        event = {"run_id": self.run_id, "case_id": identity, "step": 1,
                 "timestamp": "2026-10-01T00:00:00Z", "action": "Select owned source",
                 "source": "ui", "expected": {"access": "granted"},
                 "actual": {"access": "denied"}, "passed": False,
                 "evidence": {"screenshot": None}}
        event_path = self.run / identity / "events.jsonl"
        event_path.parent.mkdir()
        original = (json.dumps(event) + "\n").encode()
        event_path.write_bytes(original)
        self.report["tc_results"][0].update(
            state="FAIL", reason="Actual assertion failed", step_results=[event],
            started_at="2026-10-01T00:00:00Z", finished_at="2026-10-01T00:00:01Z",
            evidence={"events": {"path": f"{identity}/events.jsonl", "sha256": sha(original),
                                 "bytes": len(original)}})
        self.report["state"] = "FAIL"
        source = self.save()
        receipt = export.export_result(source, self.output)
        self.assertEqual(receipt["state"], "PASS")
        self.assertEqual(receipt["product_state"], "FAIL")
        self.assertEqual(json.loads((self.output / export.VERIFICATION).read_text())["rows"]["steps"], 1)
        event_path.write_bytes(b"changed")
        self.assertEqual(export.export_result(source, self.output)["state"], "FAIL")

    def test_wrong_type_and_duplicate_tc_are_rejected(self):
        self.report["scope"] = "source_check"
        source = self.save()
        receipt = export.export_result(source, self.output)
        self.assertEqual(receipt["state"], "FAIL")
        self.assertFalse(list(self.output.glob("*.xlsx")))
        saved = (self.output / export.RECEIPT).read_bytes()
        self.assertEqual(export.export_result(source, self.output), receipt)
        self.assertEqual((self.output / export.RECEIPT).read_bytes(), saved)
        second = self.root / "duplicate"
        second.mkdir()
        self.report["scope"] = "tm002_granular_targeted_development_probe"
        self.report["expected_cases"] *= 2
        self.report["tc_results"] *= 2
        source.write_text(json.dumps(self.report), encoding="utf-8")
        self.assertEqual(export.export_result(source, second)["state"], "FAIL")

    def test_preflight_cannot_have_product_steps(self):
        self.report["tc_results"][0]["step_results"] = [{"step": 1, "passed": True}]
        receipt = export.export_result(self.save(), self.output)
        self.assertEqual(receipt["state"], "FAIL")
        self.assertFalse(list(self.output.glob("*.xlsx")))

    def test_changed_evidence_is_rejected(self):
        source = self.save()
        (self.run / "test-code/scripts/granular_permissions.py").write_bytes(b"changed")
        receipt = export.export_result(source, self.output)
        self.assertEqual(receipt["state"], "FAIL")
        self.assertFalse(list(self.output.glob("*.xlsx")))

    def test_existing_workbook_tamper_does_not_rewrite_receipt(self):
        source = self.save()
        first = export.export_result(source, self.output)
        self.assertEqual(first["state"], "PASS")
        receipt_bytes = (self.output / export.RECEIPT).read_bytes()
        target = self.output / f"TokenMeter测试结果-{self.run_id}.xlsx"
        with target.open("ab") as stream:
            stream.write(b"tamper")
        second = export.export_result(source, self.output)
        self.assertEqual(second["state"], "FAIL")
        self.assertEqual((self.output / export.RECEIPT).read_bytes(), receipt_bytes)


if __name__ == "__main__":
    unittest.main()
