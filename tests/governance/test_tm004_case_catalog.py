import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
RELEASE = "v0.4.0-20261001T040433Z"
DETAIL = ROOT / "docs/testing/cases/04-TM-004-claude-collection.md"
PRODUCT_EXPECTED = {
    "TC-TM004-SOURCE-01", "TC-TM004-SOURCE-02", "TC-TM004-SOURCE-03", "TC-TM004-SOURCE-04",
    "TC-TM004-PARSER-01", "TC-TM004-PARSER-02", "TC-TM004-PARSER-03",
    "TC-TM004-LINEAGE-01", "TC-TM004-LINEAGE-02", "TC-TM004-LINEAGE-03",
    "TC-TM004-LINEAGE-04", "TC-TM004-LINEAGE-05",
    "TC-TM004-INCREMENTAL-01", "TC-TM004-INCREMENTAL-02", "TC-TM004-INCREMENTAL-03",
    "TC-TM004-DIAG-01", "TC-TM004-DIAG-02", "TC-TM004-DATA-01",
    "TC-TM004-E2E-01", "TC-TM004-RELEASE-01",
}
CORE_EXPECTED = {f"TC-TM004-CORE-0{number}" for number in range(1, 6)}
EXPECTED = PRODUCT_EXPECTED | CORE_EXPECTED


class TM004CatalogTests(unittest.TestCase):
    def test_stable_design_ids_are_bidirectional_and_not_product_pass(self):
        catalog = json.loads((ROOT / "tests/test_cases.json").read_text())
        rows = {row["id"]: row for row in catalog["cases"] if row["id"].startswith("TC-TM004-")}
        document_ids = set(re.findall(r"^### (TC-TM004-[A-Z0-9-]+)\b", DETAIL.read_text(), re.M))
        manifest = json.loads((ROOT / "releases" / RELEASE / "00-manifest.json").read_text())
        tracked = {row["test"] for row in manifest["traceability"] if row["test"].startswith("TC-TM004-")}
        suites = json.loads((ROOT / "tests/source_check_suites.json").read_text())["suites"]
        self.assertEqual(set(rows), EXPECTED)
        self.assertEqual(document_ids, EXPECTED)
        self.assertEqual(tracked, EXPECTED)
        root_index = (ROOT / "TEST_CASES.md").read_text()
        for case_id, row in rows.items():
            self.assertIn(f"[{case_id}]", root_index)
            self.assertEqual(row["release_id"], RELEASE)
            if case_id in CORE_EXPECTED:
                self.assertEqual(row["type"], "source_check")
                self.assertEqual(row["design_status"], "draft")
                binding = row["binding"]
                self.assertIsInstance(binding, dict)
                self.assertEqual(binding["tc_identity"], case_id)
                self.assertEqual(binding["execution_type"], "source_check")
                self.assertEqual(binding["runner"], "scripts/run_source_check.mjs")
                self.assertEqual(binding["suite_registry"], "tests/source_check_suites.json")
                suite = suites[binding["suite"]]
                self.assertEqual(suite["release_id"], RELEASE)
                self.assertIn(case_id, suite["cases"])
                self.assertEqual(binding["program"], suite["file"])
                self.assertEqual(row["data_program"], suite["file"])
                self.assertEqual(binding["reset_kind"], suite["reset_kind"])
                self.assertEqual(binding["status"], "implemented_pending_integrated_run")
                program = (ROOT / suite["file"]).read_text()
                if binding["test_name"] not in program:
                    self.assertIn(f"const CASE = '{case_id}'", program)
                    self.assertIn(binding["test_name"].removeprefix(case_id), program)
            else:
                self.assertEqual(row["design_status"], "baseline_pending")
                self.assertIsNone(row["binding"])
            self.assertEqual(row["execution_status"], "unexecuted")
            self.assertIsNone(row["evidence"])
            self.assertGreaterEqual(len(row["steps"]), 3)
            if row["type"] == "product_e2e":
                for step in row["steps"]:
                    for field in ("expected_ui", "expected_api_db", "expected_file"):
                        self.assertTrue(step[field].strip())


if __name__ == "__main__":
    unittest.main()
