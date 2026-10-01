"""Fixed negative checks for the source_check report type and case identity."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUN_BASE = ROOT / ".local/source-check-runs"
OUTPUT_BASE = ROOT / ".local/test-results"
EXPORTER = ROOT / "scripts/export_source_check_result.mjs"


class SourceCheckExportContract(unittest.TestCase):
    def setUp(self):
        RUN_BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.temp = tempfile.TemporaryDirectory(prefix="source-check-negative-", dir=RUN_BASE)
        self.addCleanup(self.temp.cleanup)
        self.run_dir = Path(self.temp.name)
        self.run_id = self.run_dir.name
        self.commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        self.tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip()

    def invoke(self, report):
        (self.run_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
        return subprocess.run([
            "node", str(EXPORTER), "--report", str(self.run_dir / "report.json"),
            "--output", str(OUTPUT_BASE / self.run_id),
        ], cwd=ROOT, capture_output=True, text=True, check=False)

    def base_report(self):
        return {
            "schema_version": 1, "execution_type": "source_check", "run_id": self.run_id,
            "state": "PASS", "product_e2e": "NOT_RUN", "release_gate": "NOT_RUN",
            "candidate_commit": self.commit, "candidate_tree": self.tree,
            "expected_cases": ["TC-TM003-CORE-01"],
            "cases": [{"case_id": "TC-TM003-CORE-01"}],
        }

    def test_rejects_product_report_as_module_evidence(self):
        report = self.base_report()
        report["execution_type"] = "product_e2e"
        result = self.invoke(report)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid source_check report identity", result.stderr)
        self.assertFalse((OUTPUT_BASE / self.run_id).exists())

    def test_rejects_duplicate_case_ids_before_export(self):
        report = self.base_report()
        report["expected_cases"] *= 2
        report["cases"] *= 2
        result = self.invoke(report)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Duplicate or mismatched module case ID", result.stderr)
        self.assertFalse((OUTPUT_BASE / self.run_id).exists())


if __name__ == "__main__":
    unittest.main()
