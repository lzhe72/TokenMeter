"""Source-check runner parser and immutable evidence boundary tests."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import tm002_source_check as source_check
from scripts import tm002_source_check_export as source_export


class TM002SourceCheckContractTest(unittest.TestCase):
    def test_fixed_bindings_are_unique_and_cover_25_independent_ids(self) -> None:
        self.assertEqual(len(source_check.BINDINGS), 25)
        self.assertEqual(len(set(source_check.BINDINGS)), 25)
        self.assertEqual(len(source_check.DESKTOP), 14)
        self.assertEqual(len(source_check.GOVERNANCE), 11)
        self.assertIn("TC-TM002-EVIDENCE-01#MISSING_CHOOSER_WITNESS", source_check.BINDINGS)
        self.assertNotIn("TC-TM002-DELIVERY-01", source_check.BINDINGS)

    def test_tap_requires_exact_per_test_lines_and_zero_skips(self) -> None:
        good = ("TAP version 13\n# Subtest: TC-TM002-LIMIT-01 fixed\n"
                "ok 1 - TC-TM002-LIMIT-01 fixed\n1..1\n# tests 1\n# pass 1\n"
                "# fail 0\n# cancelled 0\n# skipped 0\n# todo 0\n")
        self.assertEqual(source_check.parse_tap(good), ({"TC-TM002-LIMIT-01 fixed": "PASS"}, True))
        self.assertFalse(source_check.parse_tap(good.replace("# skipped 0", "# skipped 1"))[1])
        self.assertFalse(source_check.parse_tap(good.replace("# tests 1", "# tests 2"))[1])
        self.assertFalse(source_check.parse_tap(good.replace("1..1", "ok 2 - TC-TM002-LIMIT-01 fixed\n1..2"))[1])

    def test_unittest_requires_exact_method_and_complete_summary(self) -> None:
        good = ("test_TC_TM002_CATALOG_01_VALID (test_tm002_catalog_fixed.FixedCatalogOwnershipTest) ... ok\n"
                "\n----------------------------------------------------------------------\n"
                "Ran 1 test in 0.101s\n\nOK\n")
        self.assertEqual(source_check.parse_unittest(good),
                         ({"test_TC_TM002_CATALOG_01_VALID": "PASS"}, True))
        self.assertFalse(source_check.parse_unittest(good.replace("Ran 1 test", "Ran 2 tests"))[1])
        self.assertFalse(source_check.parse_unittest(good.replace("... ok", "... skipped 'absent'"))[1])

    def test_catalog_does_not_derive_missing_fixed_variant_from_parent(self) -> None:
        value = {"cases": [{"id": "TC-TM002-EVIDENCE-01", "type": "governance_unit",
                 "variants": [{"id": "TC-TM002-EVIDENCE-01#COMPLETE"}]}]}
        entries = source_check.catalog_entries(value)
        self.assertEqual(set(entries), {"TC-TM002-EVIDENCE-01#COMPLETE"})
        self.assertNotIn("TC-TM002-EVIDENCE-01#MISSING_CHOOSER_WITNESS", entries)
        value["cases"][0]["variants"].append({"id": "TC-TM002-EVIDENCE-01#COMPLETE"})
        with self.assertRaisesRegex(ValueError, "Duplicate catalog ID"):
            source_check.catalog_entries(value)

    def test_owner_directory_cannot_be_reused_or_follow_symlink(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tm002-source-check-test-") as temporary:
            root = Path(temporary).resolve()
            first = source_check.safe_new_run(root / "run-a")
            self.assertEqual(first.stat().st_mode & 0o777, 0o700)
            with self.assertRaises(FileExistsError):
                source_check.safe_new_run(first)
            link = root / "alias"
            link.symlink_to(first, target_is_directory=True)
            with self.assertRaises(ValueError):
                source_check.safe_new_run(link / "run-b")

    def test_fixed_c_harness_item_parser_rejects_malformed_output(self) -> None:
        sample = "ITEM QTEuanNvbmw= 25 1700000000 123456789 " + "a" * 64 + " -"
        self.assertEqual(source_check.decoded_item(sample)["name"], "A1.jsonl")
        self.assertIsNone(source_check.decoded_item(sample.replace(" 25 ", " -1 ")))

    def test_limit_marker_uses_unpadded_name_and_actual_cleanup_witness(self) -> None:
        root = source_check.ROOT
        marker = {"case_id": "TC-TM002-LIMIT-01",
                  "input_sha256": source_check.digest((root / "apps/desktop/tests/tm002-limit-harness.c").read_bytes()),
                  "algorithm_sha256": source_check.digest((root / "apps/desktop/native/source-helper.c").read_bytes()),
                  "stdout_lines": ["AUDIT enumerated candidate QTEuanNvbmw 7 101",
                                   "AUDIT metadata candidate QTEuanNvbmw 7 101", "PREVIEW timeout 1 1",
                                   "ITEM QTEuanNvbmw 25 1700000000 123456789 " + "a" * 64 + " -", "END"],
                  "stderr": "HARNESS clock=3 open=2 openat=0 read=0 fstat=4 dup=2 close=4 fdopendir=1 readdir=1 fstatat=1 closedir=1 unexpected=0 names=2",
                  "exit_code": 0, "scratch_removed": True}
        raw = {"stdout_text": "# TM002_LIMIT_ACTUAL " + json.dumps(marker) + "\n",
               "stdout": {"path": "logs/limit.stdout.log"}}
        good, actual, steps, cleanup = source_check.limit_observation(raw)
        self.assertTrue(good)
        self.assertEqual(len(steps), 3)
        self.assertIn("A1.jsonl", actual[0])
        self.assertEqual(cleanup["state"], "PASS")
        marker["scratch_removed"] = False
        raw["stdout_text"] = "# TM002_LIMIT_ACTUAL " + json.dumps(marker) + "\n"
        self.assertFalse(source_check.limit_observation(raw)[0])

    def test_command_writes_separate_exclusive_raw_logs_and_digest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tm002-command-test-") as temporary:
            root = source_check.safe_new_run(Path(temporary).resolve() / "one-run")
            result = source_check.command(root, "smoke", [sys.executable, "-c", "print('owned output')"], root)
            self.assertEqual(result["exit_code"], 0)
            self.assertFalse(result["timeout"])
            self.assertEqual(result["stdout_text"], "owned output\n")
            self.assertEqual(source_check.descriptor(root / result["stdout"]["path"], root), result["stdout"])
            with self.assertRaises(FileExistsError):
                source_check.command(root, "smoke", [sys.executable, "-c", "print('different')"], root)

    def test_source_check_export_blocks_missing_runtime_without_changing_raw_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tm002-export-bridge-") as temporary:
            root = Path(temporary).resolve()
            run = root / "run-001"
            run.mkdir(mode=0o700)
            report = run / "source-check.json"
            original = (json.dumps({"schema_version": 1, "execution_type": "source_check",
                "run_id": "run-001", "state": "BLOCKED", "candidate_sha": "a" * 40,
                "candidate_tree": "b" * 40}) + "\n").encode()
            report.write_bytes(original)
            with patch.dict(os.environ, {"TOKENMETER_WORKBOOK_NODE": str(root / "missing-node")}):
                first = source_export.export(report, root / "xlsx-run-001")
                second = source_export.export(report, root / "xlsx-run-001")
            self.assertEqual(first["state"], "BLOCKED")
            self.assertEqual(second, first)
            self.assertEqual(report.read_bytes(), original)
            receipt = Path(first["receipt_path"])
            self.assertEqual(json.loads(receipt.read_text()), first)
            self.assertFalse((root / "xlsx-run-001").exists())


if __name__ == "__main__":
    unittest.main()
