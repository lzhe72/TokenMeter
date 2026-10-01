"""Auxiliary TC runner is repeatable and never infers an unrun UI PASS."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from scripts import granular_auxiliary as auxiliary
from scripts import granular_test_result as results


class AuxiliaryTests(unittest.TestCase):
    def parent(self, root: Path) -> Path:
        files = ("tests/test_cases.json", "tests/granular_login_variants.json",
                 "tests/granular_update_variants.json")
        catalog = json.loads((results.ROOT / files[0]).read_text())
        source_releases = {case["release_id"] for case in catalog["cases"]
                           if case.get("feature_id") == "TM-001"}
        self.assertEqual(len(source_releases), 1)
        payload = {"schema_version": 3, "run_id": "parent-test-01", "release_id": source_releases.pop(),
                   "source_commit": "a" * 40, "candidate_tree": "b" * 40,
                   "package": {"manifest_sha256": "c" * 64, "dmg_sha256": "d" * 64,
                               "installed_source": "development_dmg"},
                   "finished_at": (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(),
                   "test_inputs_sha256": {name: results.sha((results.ROOT / name).read_bytes()) for name in files}}
        path = root / "result.json"
        path.write_text(json.dumps(payload))
        return path

    def test_single_ui_without_package_is_explicitly_blocked_and_replayable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            parent = self.parent(root)
            output = root / "auxiliary"
            args = argparse.Namespace(parent_report=parent, output=output, run_id="aux-test-01",
                                      case_id=["TC-TM001-UI-01"], with_ui=False,
                                      package_manifest=None, dmg=None, update_zip=None)
            self.assertEqual(auxiliary.execute(args), 2)
            report = json.loads((output / "result.json").read_text())
            self.assertEqual(report["scope"], "granular_auxiliary_targeted_probe")
            self.assertEqual(report["expected_cases"], ["TC-TM001-UI-01"])
            self.assertEqual(report["tc_results"][0]["state"], "BLOCKED")
            self.assertEqual(report["replay"]["cases"]["TC-TM001-UI-01"]["code"],
                             "apps/desktop/e2e/granular-auxiliary.spec.ts")
            self.assertTrue(any(item["path"].endswith("granular-auxiliary.spec.ts")
                                for item in report["test_code_snapshot"]))

    def test_single_governance_case_runs_fixed_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            parent = self.parent(root)
            output = root / "auxiliary"
            args = argparse.Namespace(parent_report=parent, output=output, run_id="aux-test-02",
                                      case_id=["TC-TM001-CATALOG-02"], with_ui=False,
                                      package_manifest=None, dmg=None, update_zip=None)
            self.assertEqual(auxiliary.execute(args), 0)
            report = json.loads((output / "result.json").read_text())
            item = report["tc_results"][0]
            self.assertEqual(item["state"], "PASS")
            self.assertEqual(item["step_results"][0]["source"], "command")
            for role in ("events", "command_log"):
                raw, status, _ = results.evidence_file(output, item["evidence"][role])
                self.assertEqual(status, "已核对")
                self.assertTrue(raw)

    def test_tm001_parent_accepts_newer_combined_catalog(self):
        catalog = json.loads((results.ROOT / "tests/test_cases.json").read_text())
        source_releases = {case["release_id"] for case in catalog["cases"]
                           if case.get("feature_id") == "TM-001"}
        self.assertEqual(len(source_releases), 1)
        source_release = source_releases.pop()
        self.assertNotEqual(source_release, catalog["release_id"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            parent = self.parent(root)
            payload = json.loads(parent.read_text())
            payload["release_id"] = source_release
            parent.write_text(json.dumps(payload))
            output = root / "auxiliary"
            args = argparse.Namespace(parent_report=parent, output=output, run_id="aux-test-newer-catalog",
                                      case_id=["TC-TM001-CATALOG-02"], with_ui=False,
                                      package_manifest=None, dmg=None, update_zip=None)
            self.assertEqual(auxiliary.execute(args), 0)
            report = json.loads((output / "result.json").read_text())
            self.assertEqual(report["release_id"], source_release)
            self.assertEqual(report["tc_results"][0]["state"], "PASS")

    def test_catalog_index_includes_registered_inline_variants(self):
        catalog = json.loads((results.ROOT / "tests/test_cases.json").read_text())
        self.assertTrue(any(case.get("variants") for case in catalog["cases"]))
        with tempfile.TemporaryDirectory() as temp:
            actual = auxiliary.catalog_01(Path(temp), {"catalog": catalog})
            self.assertTrue(actual["passed"])
            self.assertEqual(actual["workbook_count"], sum(1 + len(case.get("variants", []))
                                                          for case in catalog["cases"]))

    def test_records_fixtures_export_with_owned_variant_inputs(self):
        catalog = json.loads((results.ROOT / "tests/test_cases.json").read_text())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            context = {"catalog": catalog, "run_id": "aux-records-fixture-01"}
            (root / "positive").mkdir()
            (root / "negative").mkdir()
            self.assertTrue(auxiliary.records_01(root / "positive", context)["passed"])
            self.assertTrue(auxiliary.records_02(root / "negative", context)["passed"])

    def test_auxiliary_rejects_wrong_source_release_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            parent = self.parent(root)
            payload = json.loads(parent.read_text())
            payload["release_id"] = json.loads((results.ROOT / "tests/test_cases.json").read_text())["release_id"]
            parent.write_text(json.dumps(payload))
            output = root / "auxiliary"
            args = argparse.Namespace(parent_report=parent, output=output, run_id="aux-wrong-release",
                                      case_id=["TC-TM001-CATALOG-02"], with_ui=False,
                                      package_manifest=None, dmg=None, update_zip=None)
            with self.assertRaisesRegex(results.Invalid, "TM-001 source cases"):
                auxiliary.execute(args)
            self.assertFalse(output.exists())

    def test_auxiliary_rejects_changed_frozen_catalog_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            parent = self.parent(root)
            payload = json.loads(parent.read_text())
            payload["test_inputs_sha256"]["tests/test_cases.json"] = "0" * 64
            parent.write_text(json.dumps(payload))
            output = root / "auxiliary"
            args = argparse.Namespace(parent_report=parent, output=output, run_id="aux-changed-catalog",
                                      case_id=["TC-TM001-CATALOG-02"], with_ui=False,
                                      package_manifest=None, dmg=None, update_zip=None)
            with self.assertRaisesRegex(results.Invalid, "frozen input"):
                auxiliary.execute(args)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
