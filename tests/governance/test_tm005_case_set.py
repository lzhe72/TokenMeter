"""Fixed case-set checks independent of unfinished desktop bindings."""

import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_tm005_case_set", ROOT / "scripts/check_tm005_case_set.py")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)
MANIFEST = json.loads((ROOT / CHECKER.RELEASE_DIR / "00-manifest.json").read_text())
DETAIL = (ROOT / CHECKER.RELEASE_DIR / "04a-test-cases.md").read_text()


class TM005CaseSetTests(unittest.TestCase):
    def test_manifest_and_detailed_document_have_fixed_set(self):
        errors, parents, variants, core = CHECKER.expected_case_set(MANIFEST, DETAIL)
        self.assertEqual(errors, [])
        self.assertEqual((len(parents), len(variants)), (32, 6))
        self.assertEqual(core, CHECKER.CORE_IDS)

    def test_dropped_variant_cannot_disappear_from_plan(self):
        altered = copy.deepcopy(MANIFEST)
        altered["traceability"] = [row for row in altered["traceability"]
                                   if row["test"] != "TC-TM005-RANGE-11#SPRING"]
        errors, _, _, _ = CHECKER.expected_case_set(altered, DETAIL)
        self.assertIn("release manifest and product case set differ", errors)

    def test_catalog_rejects_wrong_set_and_unbacked_pass(self):
        _, parents, variants, core = CHECKER.expected_case_set(MANIFEST, DETAIL)
        catalog = {"cases": [{"id": "TC-TM005-CONTRACT-01", "release_id": CHECKER.RELEASE,
                              "execution_status": "PASS", "evidence": None,
                              "binding": None, "variants": []}]}
        errors, product_gaps, core_gaps = CHECKER.validate_catalog(catalog, parents, variants, core)
        self.assertIn("machine catalog TM-005 product parent set differs", errors)
        self.assertIn("machine catalog TM-005 product variant set differs", errors)
        self.assertIn("unbacked PASS: TC-TM005-CONTRACT-01", errors)
        self.assertEqual(product_gaps, ["TC-TM005-CONTRACT-01"])
        self.assertEqual(core_gaps, [])

    def test_core_three_are_separate_from_product_32(self):
        augmented = copy.deepcopy(MANIFEST)
        errors, parents, variants, core = CHECKER.expected_case_set(augmented, DETAIL)
        self.assertEqual(errors, [])
        self.assertEqual((len(parents), len(variants), len(core)), (32, 6, 3))
        incomplete = copy.deepcopy(augmented)
        incomplete["traceability"] = [row for row in incomplete["traceability"]
                                      if row["test"] != "TC-TM005-CORE-03"]
        errors, _, _, _ = CHECKER.expected_case_set(incomplete, DETAIL)
        self.assertIn("CORE auxiliary set must contain exactly three manifest and detailed cases", errors)
        errors, _, _, _ = CHECKER.expected_case_set(
            augmented, DETAIL + "\n### TC-TM005-CORE-04 · 意外用例")
        self.assertIn("CORE auxiliary set must contain exactly three manifest and detailed cases", errors)
        missing = copy.deepcopy(MANIFEST)
        missing["traceability"] = [row for row in missing["traceability"]
                                   if not row["test"].startswith("TC-TM005-CORE-")]
        errors, _, _, _ = CHECKER.expected_case_set(missing, DETAIL)
        self.assertIn("CORE auxiliary set must contain exactly three manifest and detailed cases", errors)

    def test_registered_case_documents_must_match_files(self):
        errors, _ = CHECKER.case_document_registration(MANIFEST)
        self.assertEqual(errors, [])
        altered = copy.deepcopy(MANIFEST)
        altered["test_case_documents"].append(
            str(CHECKER.RELEASE_DIR / "04b-test-cases.md"))
        errors, _ = CHECKER.case_document_registration(altered)
        self.assertIn("release case documents are not fully registered", errors)

    def test_core_unbacked_pass_and_missing_catalog_row_fail(self):
        core = set(CHECKER.CORE_IDS)
        catalog = {"cases": [{"id": "TC-TM005-CORE-01", "release_id": CHECKER.RELEASE,
                              "execution_status": "PASS", "evidence": None,
                              "binding": None, "variants": []}]}
        errors, product_gaps, core_gaps = CHECKER.validate_catalog(catalog, set(), set(), core)
        self.assertIn("machine catalog TM-005 CORE auxiliary set differs", errors)
        self.assertIn("unbacked PASS: TC-TM005-CORE-01", errors)
        self.assertEqual(product_gaps, [])
        self.assertEqual(core_gaps, ["TC-TM005-CORE-01"])


if __name__ == "__main__":
    unittest.main()
