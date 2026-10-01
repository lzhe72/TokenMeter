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
NEW_RELEASE = "v0.2.0-20261001T034118Z"


class TestCaseCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="tokenmeter-case-catalog-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / "tests").mkdir()
        (self.root / "docs/testing/cases").mkdir(parents=True)
        self.case_document = self.root / "docs/testing/cases/fixture.md"
        release = self.root / "releases" / RELEASE
        release.mkdir(parents=True)
        (release / "00-manifest.json").write_text(json.dumps({
            "schema_version": 1, "release_id": RELEASE, "feature_ids": ["TM-001"]}), encoding="utf-8")
        (release / "02-breakdown.md").write_text("TASK-TM001-LOGIN-AUTH\n", encoding="utf-8")
        new_release = self.root / "releases" / NEW_RELEASE
        new_release.mkdir(parents=True)
        (new_release / "00-manifest.json").write_text(json.dumps({
            "schema_version": 1, "release_id": NEW_RELEASE, "feature_ids": ["TM-002"]}), encoding="utf-8")
        (new_release / "02-breakdown.md").write_text("TASK-TM002-PICKER\n", encoding="utf-8")
        (self.root / "tests/acceptance.json").write_text(json.dumps({"acceptance_criteria": [
            {"id": "AC-TM001-001", "feature_id": "TM-001"},
            {"id": "AC-TM002-001", "feature_id": "TM-002"}]}), encoding="utf-8")
        self.case_document.write_text("# Fixture cases\n\n## TC-TM001-LOGIN-01 · Fixture\n", encoding="utf-8")
        self.data = {"schema_version": 1, "release_id": RELEASE, "cases": [{
            "id": "TC-TM001-LOGIN-01", "title": "Fixture", "feature_id": "TM-001",
            "requirement_id": "REQ-TM001", "task_ids": ["TASK-TM001-LOGIN-AUTH"], "ac_ids": ["AC-TM001-001"],
            "type": "negative", "input": "fixture input", "preconditions": "owned synthetic environment",
            "steps": [{"step": 1, "action": "Read synthetic input", "expected_ui": "fixture label",
                       "expected_api_db": "no product connection", "expected": "fixture value preserved"}],
            "db_operations": {"prepare": "synthetic only", "expected_changes": "none", "verification": "no DB connection"},
            "design_status": "designed", "execution_status": "unexecuted", "binding": None,
            "source": {"path": "docs/testing/cases/fixture.md", "heading": "TC-TM001-LOGIN-01 · Fixture", "line": 3},
            "missing": ["No product binding"],
            "aggregate_planned": False, "evidence": None}]}

    def second_case(self):
        self.case_document.write_text(self.case_document.read_text(encoding="utf-8") +
                                      "\n## TC-TM002-SELECT-01 · Fixture\n", encoding="utf-8")
        case = copy.deepcopy(self.data["cases"][0])
        case.update(id="TC-TM002-SELECT-01", feature_id="TM-002", requirement_id="REQ-TM002",
                    release_id=NEW_RELEASE, task_ids=["TASK-TM002-PICKER"], ac_ids=["AC-TM002-001"],
                    type="product_e2e", source={"path": "docs/testing/cases/fixture.md",
                                                "heading": "TC-TM002-SELECT-01 · Fixture", "line": 5})
        case["steps"][0]["expected_file"] = "no filesystem read"
        return case

    def add_variant(self, case, suffix="A", *, document=True):
        variant_id = case["id"] + "#" + suffix
        variant = {"id": variant_id, "input": "synthetic variant input",
                   "expected": "synthetic variant result", "execution_status": "unexecuted"}
        if "release_id" in case:
            variant["steps"] = copy.deepcopy(case["steps"])
        case.setdefault("variants", []).append(variant)
        if document:
            self.case_document.write_text(self.case_document.read_text(encoding="utf-8") +
                                          "\n- " + variant_id + ": synthetic input and result\n", encoding="utf-8")
        return variant_id

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

    def test_two_releases_keep_legacy_rows_and_validate_new_rows(self):
        self.data["cases"].append(self.second_case())
        self.assertEqual(exporter.validate_catalog(self.data, self.root), [])

    def test_stable_ids_allow_named_subgroups_and_numeric_e2e_group(self):
        for case_id in ("TC-TM003-COVERAGE-OVERFLOW-01", "TC-TM003-E2E-01", "TC-TM003-E2E-02"):
            self.assertIsNotNone(exporter.CASE_ID.fullmatch(case_id))
        for case_id in ("TC-TM002-COVERAGE-OVERFLOW-01", "TC-TM002-E2E-01"):
            with self.subTest(case_id=case_id):
                self.case_document.write_text("# Fixture cases\n\n## TC-TM001-LOGIN-01 · Fixture\n",
                                              encoding="utf-8")
                data = copy.deepcopy(self.data)
                case = self.second_case()
                self.case_document.write_text(
                    self.case_document.read_text(encoding="utf-8").replace("TC-TM002-SELECT-01", case_id),
                    encoding="utf-8")
                case["id"] = case_id
                case["source"]["heading"] = case_id + " · Fixture"
                self.add_variant(case)
                data["cases"].append(case)
                self.assertEqual(exporter.validate_catalog(data, self.root), [])

    def test_stable_ids_reject_empty_lowercase_or_missing_number(self):
        for case_id in ("TC-TM002-COVERAGE--01", "TC-TM002-coverage-01", "TC-TM002-E2E"):
            with self.subTest(case_id=case_id):
                self.case_document.write_text("# Fixture cases\n\n## TC-TM001-LOGIN-01 · Fixture\n",
                                              encoding="utf-8")
                data = copy.deepcopy(self.data)
                case = self.second_case()
                case["id"] = case_id
                data["cases"].append(case)
                self.assertTrue(any("invalid stable case ID" in error
                                    for error in exporter.validate_catalog(data, self.root)))

    def test_legacy_future_aggregate_without_release_id_is_preserved(self):
        future = self.second_case()
        future.pop("release_id")
        future.update(task_ids=[], design_status="planned", aggregate_planned=True)
        self.data["cases"].append(future)
        self.assertEqual(exporter.validate_catalog(self.data, self.root), [])

    def test_new_case_task_from_old_release_is_rejected(self):
        case = self.second_case()
        case["task_ids"] = ["TASK-TM001-LOGIN-AUTH"]
        self.data["cases"].append(case)
        self.assertTrue(any("unregistered TASK" in error for error in exporter.validate_catalog(self.data, self.root)))

    def test_new_detailed_case_without_task_is_rejected(self):
        case = self.second_case()
        case["task_ids"] = []
        self.data["cases"].append(case)
        self.assertTrue(any("requires a concrete TASK" in error for error in exporter.validate_catalog(self.data, self.root)))

    def test_case_feature_must_belong_to_its_release_manifest(self):
        case = self.second_case()
        case["release_id"] = RELEASE
        self.data["cases"].append(case)
        self.assertTrue(any("does not belong to release" in error for error in exporter.validate_catalog(self.data, self.root)))

    def test_case_release_manifest_must_exist(self):
        (self.root / "releases" / NEW_RELEASE / "00-manifest.json").unlink()
        self.data["cases"].append(self.second_case())
        self.assertTrue(any("Release manifest does not exist" in error for error in exporter.validate_catalog(self.data, self.root)))

    def test_case_release_manifest_id_must_match(self):
        (self.root / "releases" / NEW_RELEASE / "00-manifest.json").write_text(json.dumps({
            "schema_version": 1, "release_id": RELEASE, "feature_ids": ["TM-002"]}), encoding="utf-8")
        self.data["cases"].append(self.second_case())
        self.assertTrue(any("Release manifest ID does not match" in error for error in exporter.validate_catalog(self.data, self.root)))

    def test_source_heading_text_must_match_document_title(self):
        self.invalid(lambda data: data["cases"][0]["source"].update(
            heading="TC-TM001-LOGIN-01 · Stale title"), "source heading text differs")

    def test_catalog_title_must_match_document_title(self):
        self.invalid(lambda data: data["cases"][0].update(title="Stale title"),
                     "catalog title differs from document")

    def test_new_case_with_id_only_heading_keeps_its_separate_title(self):
        case = self.second_case()
        self.case_document.write_text(
            self.case_document.read_text(encoding="utf-8").replace(
                "## TC-TM002-SELECT-01 · Fixture", "## TC-TM002-SELECT-01"),
            encoding="utf-8")
        case["source"]["heading"] = case["id"]
        self.data["cases"].append(case)
        self.assertEqual(exporter.validate_catalog(self.data, self.root), [])

    def test_product_case_requires_all_three_observation_surfaces(self):
        for field in ("expected_ui", "expected_api_db", "expected_file"):
            with self.subTest(field=field):
                case = self.second_case()
                case["steps"][0].pop(field)
                data = copy.deepcopy(self.data)
                data["cases"].append(case)
                self.assertTrue(any("product step 1 requires " + field in error
                                    for error in exporter.validate_catalog(data, self.root)))
                self.case_document.write_text("# Fixture cases\n\n## TC-TM001-LOGIN-01 · Fixture\n",
                                              encoding="utf-8")

    def test_document_case_cannot_disappear_from_catalog(self):
        self.second_case()
        self.assertTrue(any("document case missing from catalog: TC-TM002-SELECT-01" in error
                            for error in exporter.validate_catalog(self.data, self.root)))

    def test_document_variant_cannot_disappear_from_catalog(self):
        case = self.second_case()
        self.case_document.write_text(self.case_document.read_text(encoding="utf-8") +
                                      "\n- TC-TM002-SELECT-01#A: synthetic input and result\n", encoding="utf-8")
        self.data["cases"].append(case)
        self.assertTrue(any("document variant missing from catalog: TC-TM002-SELECT-01#A" in error
                            for error in exporter.validate_catalog(self.data, self.root)))

    def test_catalog_variant_must_appear_in_document(self):
        case = self.second_case()
        self.add_variant(case, document=False)
        self.data["cases"].append(case)
        self.assertTrue(any("catalog variant missing from document: TC-TM002-SELECT-01#A" in error
                            for error in exporter.validate_catalog(self.data, self.root)))

    def test_summary_mention_does_not_replace_variant_details(self):
        case = self.second_case()
        variant_id = self.add_variant(case, document=False)
        self.case_document.write_text(self.case_document.read_text(encoding="utf-8") +
                                      "\n## Summary\n\n- " + variant_id + " is mentioned here only\n", encoding="utf-8")
        self.data["cases"].append(case)
        self.assertTrue(any("catalog variant missing from document: " + variant_id in error
                            for error in exporter.validate_catalog(self.data, self.root)))

    def test_variant_requires_stable_unique_id_input_and_expected(self):
        for field, value, expected in (("id", "TC-TM002-PREVIEW-01#A", "invalid stable variant ID"),
                                       ("input", "", "variant input must be nonempty"),
                                       ("expected", "", "variant expected must be nonempty")):
            with self.subTest(field=field):
                case = self.second_case()
                self.add_variant(case)
                case["variants"][0][field] = value
                data = copy.deepcopy(self.data)
                data["cases"].append(case)
                self.assertTrue(any(expected in error for error in exporter.validate_catalog(data, self.root)))
                self.case_document.write_text("# Fixture cases\n\n## TC-TM001-LOGIN-01 · Fixture\n",
                                              encoding="utf-8")
        case = self.second_case()
        self.add_variant(case)
        self.add_variant(case)
        self.data["cases"].append(case)
        self.assertTrue(any("duplicate variant ID" in error for error in exporter.validate_catalog(self.data, self.root)))

    def test_valid_variants_are_visible_in_generated_index(self):
        case = self.second_case()
        first = self.add_variant(case, "A")
        second = self.add_variant(case, "B")
        self.data["cases"].append(case)
        self.assertEqual(exporter.validate_catalog(self.data, self.root), [])
        rendered = exporter.render_markdown(self.data)
        self.assertIn(first, rendered)
        self.assertIn(second, rendered)

    def test_variant_uses_its_own_actions_and_stepwise_expected(self):
        case = self.second_case()
        case["id"] = "TC-TM002-SELECT-02"
        case["source"]["heading"] = "TC-TM002-SELECT-02 · Fixture"
        self.case_document.write_text(self.case_document.read_text(encoding="utf-8").replace(
            "TC-TM002-SELECT-01", "TC-TM002-SELECT-02"), encoding="utf-8")
        case["steps"][0]["action"] = "Click the native Cancel button"
        variant_id = self.add_variant(case, "REPLACE_CONFIRMED")
        case["variants"][0]["steps"][0].update(
            action="Select B in the real native panel and confirm replacement",
            expected="Only the newly confirmed B root remains readable",
            expected_ui="B is confirmed",
            expected_file="A is invalidated; B metadata is readable")
        self.data["cases"].append(case)
        self.assertEqual(exporter.validate_catalog(self.data, self.root), [])
        row = next(line for line in exporter.render_markdown(self.data).splitlines() if variant_id in line)
        self.assertIn("Select B in the real native panel", row)
        self.assertIn("Only the newly confirmed B root", row)
        self.assertNotIn("Click the native Cancel button", row)

    def test_new_release_variant_requires_ordered_complete_steps(self):
        case = self.second_case()
        self.add_variant(case)
        self.data["cases"].append(case)
        variant = case["variants"][0]
        variant.pop("steps")
        self.assertTrue(any("requires ordered steps" in error
                            for error in exporter.validate_catalog(self.data, self.root)))
        variant["steps"] = [{"step": 2, "action": "Confirm A", "expected": "confirmed"}]
        errors = exporter.validate_catalog(self.data, self.root)
        self.assertTrue(any("step sequence is invalid" in error for error in errors), errors)
        variant["steps"][0]["step"] = 1
        errors = exporter.validate_catalog(self.data, self.root)
        self.assertTrue(any("requires expected_file" in error for error in errors), errors)

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
