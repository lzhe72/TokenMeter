"""Design-index checks use synthetic documents and never launch the product."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("test_case_exporter", ROOT / "scripts/export_test_cases.py")
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)
RELEASE = "v0.1.0-20260929T074814Z"


class TestCaseCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="tokenmeter-case-catalog-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / "tests").mkdir()
        (self.root / "docs").mkdir()
        release = self.root / "releases" / RELEASE
        release.mkdir(parents=True)
        (release / "02-breakdown.md").write_text("TASK-TM001-LOGIN-AUTH\n", encoding="utf-8")
        (self.root / "tests/acceptance.json").write_text(json.dumps({"acceptance_criteria": [
            {"id": "AC-TM001-001", "feature_id": "TM-001"},
            {"id": "AC-TM002-001", "feature_id": "TM-002"}]}), encoding="utf-8")
        (self.root / "docs/cases.md").write_text("# Fixture cases\n\n## TC-TM001-LOGIN-01 · Fixture\n", encoding="utf-8")
        self.data = {"schema_version": 1, "release_id": RELEASE, "cases": [{
            "id": "TC-TM001-LOGIN-01", "title": "Synthetic design check", "feature_id": "TM-001",
            "requirement_id": "REQ-TM001", "task_ids": ["TASK-TM001-LOGIN-AUTH"], "ac_ids": ["AC-TM001-001"],
            "type": "negative", "input": "fixture input", "preconditions": "owned synthetic environment",
            "steps": [{"step": 1, "action": "Read synthetic input", "expected_ui": "fixture label",
                       "expected_api_db": "no product connection", "expected": "fixture value preserved"}],
            "db_operations": {"prepare": "synthetic only", "expected_changes": "none", "verification": "no DB connection"},
            "design_status": "designed", "execution_status": "unexecuted", "binding": None,
            "source": {"path": "docs/cases.md", "line": 3}, "missing": ["No product binding"],
            "aggregate_planned": False, "evidence": None}]}

    def invalid(self, changed, expected):
        data = copy.deepcopy(self.data)
        changed(data)
        errors = exporter.validate_catalog(data, self.root)
        self.assertTrue(any(expected in error for error in errors), errors)

    def invoke(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            code = exporter.main(list(args), root=self.root)
        return code, json.loads(captured.getvalue())

    def save(self):
        path = self.root / "tests/test_cases.json"
        path.write_text(json.dumps(self.data), encoding="utf-8")
        return path

    def test_duplicate_case_id_is_rejected(self):
        self.invalid(lambda data: data["cases"].append(copy.deepcopy(data["cases"][0])), "duplicate case ID")

    def test_missing_input_is_rejected(self):
        self.invalid(lambda data: data["cases"][0].pop("input"), "missing fields")

    def test_step_gap_is_rejected(self):
        self.invalid(lambda data: data["cases"][0]["steps"][0].update(step=2), "step sequence")

    def test_unknown_task_is_rejected(self):
        self.invalid(lambda data: data["cases"][0].update(task_ids=["TASK-TM001-UNREGISTERED"]), "unregistered TASK")

    def test_step_without_independent_expected_result_is_rejected(self):
        self.invalid(lambda data: data["cases"][0]["steps"][0].update(expected="", expected_ui="", expected_api_db=""), "independent expected")

    def test_source_outside_repository_is_rejected(self):
        self.invalid(lambda data: data["cases"][0]["source"].update(path="../outside.md"), "repository file")

    def test_source_heading_line_mismatch_is_rejected(self):
        self.invalid(lambda data: data["cases"][0]["source"].update(line=1), "stale")

    def test_pass_without_execution_evidence_is_rejected(self):
        self.invalid(lambda data: data["cases"][0].update(execution_status="PASS"), "PASS cannot")

    def test_future_aggregate_cannot_be_claimed_as_designed(self):
        self.invalid(lambda data: data["cases"][0].update(aggregate_planned=True), "must remain planned")

    def test_check_stale_index_is_read_only_and_fails(self):
        self.save()
        output = self.root / "TEST_CASES.md"
        output.write_text("Preserve user text\n", encoding="utf-8")
        before = {path.relative_to(self.root): (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in self.root.rglob("*") if path.is_file()}
        code, result = self.invoke("--check")
        after = {path.relative_to(self.root): (path.read_bytes(), path.stat().st_mtime_ns)
                 for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(code, 1)
        self.assertEqual(result["state"], "STALE")
        self.assertEqual(before, after)

    def test_generated_index_check_preserves_unexecuted_status(self):
        self.save()
        code, result = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(result["product_tests_executed"], 0)
        text = (self.root / "TEST_CASES.md").read_text(encoding="utf-8")
        self.assertIn("designed / unexecuted", text)
        self.assertIn("TASK-TM001-LOGIN-AUTH", text)
        self.assertIn("fixture value preserved", text)
        code, result = self.invoke("--check")
        self.assertEqual(code, 0)
        self.assertEqual(result["state"], "CURRENT")
        self.assertEqual(result["cases"], 1)


if __name__ == "__main__":
    unittest.main()
