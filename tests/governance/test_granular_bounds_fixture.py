"""Dependency-free ownership and oracle checks for D42-BOUNDS fixture design."""

import tempfile
import unittest
from pathlib import Path

from scripts import granular_bounds_fixture as bounds


class GranularBoundsContractTests(unittest.TestCase):
    def test_all_three_boundary_inputs_are_distinct_and_exact(self):
        cases = {
            "TC-TM001-LOGIN-19#A": ("a_1", 3),
            "TC-TM001-LOGIN-19#B": ("a" * 64, 64),
            "TC-TM001-LOGIN-19#C": ("test_A-42", 9),
        }
        self.assertEqual(set(bounds.VARIANTS), set(cases))
        for case_id, (username, length) in cases.items():
            with self.subTest(case_id=case_id):
                spec = bounds.variant_spec(case_id)
                self.assertEqual((spec["username"], spec["username_length"]), (username, length))
                self.assertEqual(spec["expected_accounts"], 5)
                self.assertEqual(spec["id"], "00000000-0000-4000-8000-000000000101")
                self.assertEqual(spec["role"], "member")
        self.assertEqual(len({value[0] for value in cases.values()}), 3)

    def test_unknown_variant_and_invalid_run_id_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with self.assertRaises(ValueError):
                bounds.variant_spec("TC-TM001-LOGIN-19#D")
            with self.assertRaises(ValueError):
                bounds.validate_target(root / "private", root / "evidence", "../escape", "TC-TM001-LOGIN-19#A")

    def test_reused_private_or_sql_evidence_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            private, evidence = root / "private", root / "evidence"
            private.mkdir(); evidence.mkdir()
            self.assertEqual(bounds.validate_target(private, evidence, "bounds-a", "TC-TM001-LOGIN-19#A")["username"], "a_1")
            (private / "foreign.txt").write_text("owned by someone else")
            with self.assertRaises(ValueError):
                bounds.validate_target(private, evidence, "bounds-a", "TC-TM001-LOGIN-19#A")
            (private / "foreign.txt").unlink()
            (evidence / "seed-42-bounds.sql").write_text("existing evidence")
            with self.assertRaises(ValueError):
                bounds.validate_target(private, evidence, "bounds-a", "TC-TM001-LOGIN-19#A")

    def test_symlink_and_repository_database_target_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            target = root / "actual"
            target.mkdir()
            (root / "linked").symlink_to(target)
            with self.assertRaises(ValueError):
                bounds.validate_target(root / "linked" / "private", root / "evidence", "bounds-a", "TC-TM001-LOGIN-19#A")
            with self.assertRaises(ValueError):
                bounds.validate_target(bounds.ROOT / "database/production", root / "evidence", "bounds-a", "TC-TM001-LOGIN-19#A")


if __name__ == "__main__":
    unittest.main()
