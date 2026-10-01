"""Evidence-contract checks for individually executed TM-001 cases."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("granular_e2e_contract", ROOT / "scripts/granular_e2e.py")
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class GranularEvidenceContract(unittest.TestCase):
    def setUp(self):
        self.case = {"id": "TC-TM001-LOGIN-01", "steps": [{"step": 1}, {"step": 2}]}
        self.run_id = "local-" + "a" * 32

    def events(self, path: Path, steps: list[int], *, credential=False):
        rows = [{"run_id": self.run_id, "case_id": self.case["id"], "step": step,
                 "action": "enter a synthetic credential" if not credential else "TEST-ONLY-secret",
                 "expected": True, "actual": True, "passed": True,
                 "timestamp": "2026-09-30T00:00:00Z", "source": "ui"}
                for step in steps]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    def test_catalog_has_independent_variant_identities(self):
        catalog = runner.read_catalog()
        identities = [case["id"] for case in catalog]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertEqual(78, sum("parent_id" not in case for case in catalog))
        declared = []
        for name in ("granular_login_variants.json", "granular_update_variants.json"):
            path = ROOT / "tests" / name
            if path.is_file(): declared.extend(json.loads(path.read_text())["variants"])
        self.assertEqual({row["id"] for row in declared}, {case["id"] for case in catalog if "parent_id" in case})

    def test_missing_or_duplicate_steps_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            self.events(path, [1])
            _, error = runner.step_evidence(self.case, path, self.run_id)
            self.assertIn("Catalog steps", error)
            self.events(path, [1, 1, 2])
            _, error = runner.step_evidence(self.case, path, self.run_id)
            self.assertIn("Catalog steps", error)

    def test_correct_steps_pass_and_credential_leak_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            self.events(path, [1, 2])
            steps, error = runner.step_evidence(self.case, path, self.run_id)
            self.assertIsNone(error)
            self.assertEqual(2, len(steps))
            self.events(path, [1, 2], credential=True)
            _, error = runner.step_evidence(self.case, path, self.run_id)
            self.assertIn("credential", error)

    def test_playwright_title_and_single_attempt_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "playwright.json"
            payload = {"suites": [{"specs": [{"title": self.case["id"],
                        "tests": [{"results": [{"status": "passed"}]}]}]}]}
            path.write_text(json.dumps(payload))
            self.assertEqual("PASS", runner.raw_status(path, self.case["id"])[0])
            self.assertEqual("BLOCKED", runner.raw_status(path, "TC-TM001-LOGIN-02")[0])
            payload["suites"][0]["specs"][0]["tests"][0]["results"].append({"status": "passed"})
            path.write_text(json.dumps(payload))
            self.assertEqual("BLOCKED", runner.raw_status(path, self.case["id"])[0])


if __name__ == "__main__":
    unittest.main()
