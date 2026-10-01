"""The detailed release rule rejects missing originals and unexecuted TC rows.

The compact model is synthetic. It tests gate decisions, not product behavior.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import audit_granular_evidence, granular_gate


ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT / "tests/test_cases.json").read_text())
MANIFEST = json.loads((ROOT / "releases" / CATALOG["release_id"] / "00-manifest.json").read_text())
DOCS = json.loads((ROOT / "docs/catalog.json").read_text())
LOGIN = json.loads((ROOT / "tests/granular_login_variants.json").read_text())
UPDATE = json.loads((ROOT / "tests/granular_update_variants.json").read_text())
VARIANTS = granular_gate.combine_variants(LOGIN, UPDATE, CATALOG["release_id"])
CURRENT = [case for case in CATALOG["cases"] if case.get("feature_id") == "TM-001"]
AUX = {case["id"] for case in CURRENT if case["id"].startswith(granular_gate.results.AUX_PREFIXES)}


class GranularGateTests(unittest.TestCase):
    def test_historical_variant_source_is_distinct_from_candidate_release(self):
        target = "v0.2.0-20261001T034118Z"
        catalog = deepcopy(CATALOG)
        catalog["release_id"] = target
        for case in catalog["cases"]:
            if case.get("feature_id") == "TM-001":
                case["release_id"] = LOGIN["release_id"]
        self.assertEqual({case["release_id"] for case in catalog["cases"]
                          if case.get("feature_id") == "TM-001"}, {LOGIN["release_id"]})
        combined = granular_gate.combine_variants(LOGIN, UPDATE, target)
        self.assertEqual(combined["release_id"], LOGIN["release_id"])
        self.assertEqual(len(combined["variants"]), 38)
        wrong_update = deepcopy(UPDATE)
        wrong_update["release_id"] = target
        with self.assertRaises(granular_gate.results.Invalid):
            granular_gate.combine_variants(LOGIN, wrong_update, target)
        future_login = deepcopy(LOGIN)
        future_login["release_id"] = "v0.3.0-20261002T000000Z"
        with self.assertRaises(granular_gate.results.Invalid):
            granular_gate.combine_variants(future_login, None, target)
        with tempfile.TemporaryDirectory() as temp:
            wrong_source = {**combined, "release_id": target}
            outcome = granular_gate.verify_candidate(
                catalog, {"release_id": target}, run_root=Path(temp), plan={},
                variants=wrong_source, fixture=True)
            self.assertEqual(outcome["state"], "FAIL")
            self.assertIn("TM-001 变体来源版本与父用例不一致", outcome["reasons"])

    def fixture(self, root: Path):
        now = datetime.now(timezone.utc) - timedelta(minutes=2)
        later = now + timedelta(minutes=1)
        raw = []
        for identity in [case["id"] for case in CURRENT] + [variant["id"] for variant in VARIANTS["variants"]]:
            if identity in AUX:
                raw.append({"case_id": identity, "state": "BLOCKED", "reason":
                            "No independently registered Playwright TC and isolated fixture binding",
                            "step_results": [], "evidence": {}, "started_at": None, "finished_at": None})
            else:
                raw.append({"case_id": identity, "state": "PASS"})
        primary = {"run_id": "primary", "release_id": CATALOG["release_id"],
                   "scope": "granular_final_package", "state": "BLOCKED", "source_commit": "a" * 40,
                   "candidate_tree": "b" * 40, "package": {"dmg_sha256": "c" * 64},
                   "started_at": now.isoformat(), "finished_at": later.isoformat(),
                   "cleanup_completed": True, "expected_cases": [row["case_id"] for row in raw],
                   "tc_results": raw}
        source = root / "result.json"
        source.write_text(json.dumps(primary))
        auxiliary = {"run_id": "auxiliary", "parent_run_id": "primary", "release_id": CATALOG["release_id"],
                     "source_commit": "a" * 40, "candidate_tree": "b" * 40,
                     "package": {"dmg_sha256": "c" * 64}, "cleanup_completed": True, "state": "PASS",
                     "started_at": (later + timedelta(seconds=1)).isoformat(),
                     "finished_at": (later + timedelta(seconds=3)).isoformat(),
                     "expected_cases": sorted(AUX), "tc_results": [{"case_id": identity, "state": "PASS"}
                                                               for identity in sorted(AUX)]}
        audit = {"state": "PASS", "audited_cases": list(audit_granular_evidence.AUDITED_CASES),
                 "source_report_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        plan = {**MANIFEST, "execution_bindings_status": "ready"}
        model = {"cases": [{"id": case["id"], "state": "PASS"} for case in CURRENT],
                 "variants": [{"id": item["id"], "state": "PASS"} for item in VARIANTS["variants"]],
                 "auxiliary": [{"id": identity, "state": "PASS"} for identity in sorted(AUX)],
                 "audit": [{"id": identity, "state": "PASS"} for identity in audit_granular_evidence.AUDITED_CASES]}
        return source, primary, auxiliary, audit, plan, model

    def decide(self, root, primary, auxiliary, audit, plan, model, catalog=CATALOG, docs=DOCS):
        (root / "result.json").write_text(json.dumps(primary))
        if audit is not None:
            audit = {**audit, "source_report_sha256": hashlib.sha256((root / "result.json").read_bytes()).hexdigest()}
        with patch.object(granular_gate.results, "build_model", return_value=model):
            return granular_gate.verify_candidate(catalog, primary, run_root=root, plan=plan,
                variants=VARIANTS, auxiliary=auxiliary, auxiliary_root=root,
                audit=audit, audit_root=root, document_catalog=docs)

    def test_real_plan_baseline_comes_from_catalog_and_missing_evidence_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, primary, auxiliary, audit, plan, model = self.fixture(root)
            self.assertNotIn("test_plan_status", plan)
            self.assertEqual(self.decide(root, primary, auxiliary, audit, plan, model)["state"], "PASS")
            for label, changed in (
                ("planned binding", {**plan, "execution_bindings_status": "planned"}),
                ("wrong test plan", {**plan, "documents": {**plan["documents"], "test_plan": "other.md"}}),
            ):
                with self.subTest(label=label):
                    result = self.decide(root, primary, auxiliary, audit, changed, model)
                    self.assertEqual(result["state"], "FAIL")
            pending = deepcopy(DOCS)
            next(entry for entry in pending["documents"] if entry.get("path") ==
                 plan["documents"]["test_plan"])["status"] = "draft"
            self.assertEqual(self.decide(root, primary, auxiliary, audit, plan, model, docs=pending)["state"], "FAIL")
            self.assertEqual(self.decide(root, primary, None, audit, plan, model)["state"], "FAIL")
            self.assertEqual(self.decide(root, primary, auxiliary, None, plan, model)["state"], "FAIL")

    def test_missing_duplicate_failed_and_placeholder_tc_cannot_be_covered_by_auxiliary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, primary, auxiliary, audit, plan, model = self.fixture(root)
            self.assertEqual(self.decide(root, primary, auxiliary, audit, plan, model)["state"], "PASS")
            variants = []
            missing = deepcopy(primary); missing["tc_results"].pop(); variants.append(missing)
            repeated = deepcopy(primary); repeated["tc_results"].append(deepcopy(repeated["tc_results"][0])); variants.append(repeated)
            failed = deepcopy(primary); failed["tc_results"][0]["state"] = "FAIL"; variants.append(failed)
            skipped = deepcopy(primary); skipped["tc_results"][0]["state"] = "BLOCKED"; variants.append(skipped)
            occupied = deepcopy(primary)
            next(item for item in occupied["tc_results"] if item["case_id"] in AUX)["started_at"] = primary["started_at"]
            variants.append(occupied)
            for changed in variants:
                with self.subTest(change=changed["tc_results"][-1]["case_id"]):
                    self.assertEqual(self.decide(root, changed, auxiliary, audit, plan, model)["state"], "FAIL")

    def test_auxiliary_audit_package_and_binding_mismatches_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, primary, auxiliary, audit, plan, model = self.fixture(root)
            wrong_aux = deepcopy(auxiliary); wrong_aux["package"]["dmg_sha256"] = "d" * 64
            self.assertEqual(self.decide(root, primary, wrong_aux, audit, plan, model)["state"], "FAIL")
            blocked_audit = {**audit, "state": "BLOCKED"}
            self.assertEqual(self.decide(root, primary, auxiliary, blocked_audit, plan, model)["state"], "FAIL")
            incomplete = {**audit, "audited_cases": audit["audited_cases"][:-1]}
            self.assertEqual(self.decide(root, primary, auxiliary, incomplete, plan, model)["state"], "FAIL")
            bad_catalog = deepcopy(CATALOG)
            next(case for case in bad_catalog["cases"] if case.get("feature_id") == "TM-001")["binding"] = None
            self.assertEqual(self.decide(root, primary, auxiliary, audit, plan, model, catalog=bad_catalog)["state"], "FAIL")
            missing_variant = {"release_id": VARIANTS["release_id"], "variants": VARIANTS["variants"][:-1]}
            with patch.object(granular_gate.results, "build_model", return_value=model):
                self.assertEqual(granular_gate.verify_candidate(CATALOG, primary, run_root=root, plan=plan,
                    variants=missing_variant, auxiliary=auxiliary, auxiliary_root=root,
                    audit=audit, audit_root=root, document_catalog=DOCS)["state"], "FAIL")


if __name__ == "__main__":
    unittest.main()
