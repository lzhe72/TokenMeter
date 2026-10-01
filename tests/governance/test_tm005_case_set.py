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
        errors, parents, variants = CHECKER.expected_case_set(MANIFEST, DETAIL)
        self.assertEqual(errors, [])
        self.assertEqual((len(parents), len(variants)), (32, 6))

    def test_dropped_variant_cannot_disappear_from_plan(self):
        altered = copy.deepcopy(MANIFEST)
        altered["traceability"] = [row for row in altered["traceability"]
                                   if row["test"] != "TC-TM005-RANGE-11#SPRING"]
        errors, _, _ = CHECKER.expected_case_set(altered, DETAIL)
        self.assertIn("release manifest and detailed case set differ", errors)

    def test_catalog_rejects_wrong_set_and_unbacked_pass(self):
        _, parents, variants = CHECKER.expected_case_set(MANIFEST, DETAIL)
        catalog = {"cases": [{"id": "TC-TM005-CONTRACT-01", "release_id": CHECKER.RELEASE,
                              "execution_status": "PASS", "evidence": None,
                              "binding": None, "variants": []}]}
        errors, gaps = CHECKER.validate_catalog(catalog, parents, variants)
        self.assertIn("machine catalog TM-005 parent set differs", errors)
        self.assertIn("machine catalog TM-005 variant set differs", errors)
        self.assertIn("unbacked PASS: TC-TM005-CONTRACT-01", errors)
        self.assertEqual(gaps, ["TC-TM005-CONTRACT-01"])


if __name__ == "__main__":
    unittest.main()
