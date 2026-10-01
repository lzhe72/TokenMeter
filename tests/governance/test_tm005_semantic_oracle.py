"""Negative checks for the fixed TM-005 normalized design oracle."""

import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_tm005_oracle", ROOT / "scripts/check_tm005_oracle.py")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)
ORACLE = json.loads((ROOT / "tests/fixtures/tm005-semantic-expected.json").read_text())


class TM005SemanticOracleTests(unittest.TestCase):
    def test_fixed_design_oracle_is_consistent(self):
        self.assertEqual(CHECKER.validate(ORACLE), [])

    def test_changed_source_total_is_rejected(self):
        altered = copy.deepcopy(ORACLE)
        altered["period_source_totals_design"]["today"]["claude_code"] += 1
        self.assertIn("today: source totals differ", CHECKER.validate(altered))

    def test_unknown_coverage_cannot_become_zero(self):
        altered = copy.deepcopy(ORACLE)
        state = next(item for item in altered["state_algebra_design"]
                     if item["id"] == "one-source-uncovered-empty")
        state["expected_total_tokens"] = 0
        self.assertTrue(any("one-source-uncovered-empty" in error for error in CHECKER.validate(altered)))

    def test_dst_boundary_shift_is_rejected(self):
        altered = copy.deepcopy(ORACLE)
        altered["dst_boundary_design"]["variants"][0]["end_exclusive_utc"] = "2026-03-09T05:00:00Z"
        self.assertTrue(any("#SPRING" in error for error in CHECKER.validate(altered)))

    def test_fork_and_subagent_totals_are_independent(self):
        for section, expected_key in (("codex_fork_cumulative_design", "new_tokens_from_fork"),
                                      ("fork_history_design", "total_tokens"),
                                      ("subagent_usage_design", "total_tokens")):
            with self.subTest(section=section):
                altered = copy.deepcopy(ORACLE)
                output = ("expected_when_source_identity_is_verified" if section.startswith("codex")
                          else "expected_when_lineage_is_verified" if section.startswith("fork")
                          else "expected_when_identity_is_verified")
                altered[section][output][expected_key] += 1
                self.assertTrue(CHECKER.validate(altered))

    def test_cross_source_collision_and_conflicts_are_rejected(self):
        altered = copy.deepcopy(ORACLE)
        altered["cross_source_id_collision_design"]["expected_when_source_identity_is_verified"][
            "unique_calls"] = 1
        self.assertIn("identical native IDs from two sources must remain distinct",
                      CHECKER.validate(altered))
        altered = copy.deepcopy(ORACLE)
        altered["claude_identity_conflict_design"]["variants"][1]["second_model"] = "model-a"
        self.assertIn("Claude usage/model conflict variants must isolate each conflict",
                      CHECKER.validate(altered))

    def test_pagination_and_ambiguous_zero_do_not_become_complete(self):
        altered = copy.deepcopy(ORACLE)
        altered["claude_paged_coverage_design"]["expected_after_between_page_revocation"][
            "coverage"] = "complete"
        self.assertIn("Claude pagination/revocation coverage expectation differs",
                      CHECKER.validate(altered))
        altered = copy.deepcopy(ORACLE)
        altered["claude_zero_ambiguity_design"]["without_additional_proof"] = "confirmed_zero"
        self.assertIn("Claude raw zero without proof must stay unknown", CHECKER.validate(altered))


if __name__ == "__main__":
    unittest.main()
