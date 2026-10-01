"""Independent TC workbook source classification; no suite PASS inheritance."""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
import zlib

from scripts import granular_test_result as granular


CATALOG = json.loads((granular.ROOT / "tests/test_cases.json").read_text())
VARIANTS = json.loads((granular.ROOT / "tests/granular_login_variants.json").read_text())
CURRENT = [case for case in CATALOG["cases"] if case["feature_id"] == "TM-001"]
FUTURE_IDS = {case["id"] for case in CATALOG["cases"] if case["feature_id"] != "TM-001"}


def descriptor(root: Path, path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.relative_to(root)), "sha256": granular.sha(data), "bytes": len(data)}


def tiny_png() -> bytes:
    def chunk(kind: bytes, value: bytes) -> bytes:
        return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))


def recorded_case(root: Path, run_id: str, case: dict, state: str, count: int | None = None,
                  identity: str | None = None):
    identity = identity or case["id"]
    case_dir = root / identity
    case_dir.mkdir()
    chosen = case["steps"][:count] if count is not None else case["steps"]
    results = []
    events = []
    for step in chosen:
        passed = not (state == "FAIL" and step == chosen[-1])
        item = {"step": step["step"], "action": step["action"], "expected": step["expected"],
                "actual": f"observed-{step['step']}", "passed": passed,
                "timestamp": "2026-09-30T12:00:00Z", "source": "ui" if step == chosen[0] else "db"}
        results.append(item)
        events.append({"run_id": run_id, "case_id": identity, **item})
    event_file = case_dir / "events.jsonl"
    event_file.write_text("\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n")
    evidence = {"events": descriptor(root, event_file)}
    for name in ("trace", "database_before", "database_after", "service_audit"):
        path = case_dir / f"{name}.json"
        path.write_text('{"synthetic":true}')
        evidence[name] = descriptor(root, path)
    screenshot = case_dir / "screen.png"
    screenshot.write_bytes(tiny_png())
    evidence["screenshots"] = [descriptor(root, screenshot)]
    return {"case_id": identity, "state": state, "reason": "observed failure" if state == "FAIL" else "",
            "step_results": results, "evidence": evidence}


class GranularResultTests(unittest.TestCase):
    def test_targeted_probe_lists_only_its_parent_and_keeps_rest_out_of_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            case = next(item for item in CURRENT if item["id"] == "TC-TM001-LOGIN-01")
            item = recorded_case(root, "targeted01", case, "PASS")
            report = {"run_id": "targeted01", "release_id": CATALOG["release_id"],
                      "scope": "granular_targeted_probe", "state": "PASS",
                      "expected_cases": [case["id"]], "tc_results": [item]}
            model = granular.build_model(CATALOG, report, run_root=root, variants=VARIANTS)
            self.assertEqual([row["id"] for row in model["cases"]], [case["id"]])
            self.assertEqual(model["tc_counts"], {"PASS": 1, "FAIL": 0, "BLOCKED": 0})
            self.assertEqual(len(model["out_of_scope"]), 77)
            self.assertEqual({row["id"] for row in model["future"]}, FUTURE_IDS)

    def test_standalone_auxiliary_single_tc_has_only_one_result(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            case = next(item for item in CURRENT if item["id"] == "TC-TM001-UI-01")
            item = recorded_case(root, "aux-targeted", case, "PASS")
            code = root / "test-code/apps/desktop/e2e/granular-auxiliary.spec.ts"
            code.parent.mkdir(parents=True)
            code.write_text("fixed UI test")
            report = {"schema_version": 3, "run_id": "aux-targeted", "release_id": CATALOG["release_id"],
                      "scope": "granular_auxiliary_targeted_probe", "state": "PASS",
                      "expected_cases": [case["id"]], "tc_results": [item],
                      "test_code_snapshot": [descriptor(root, code)],
                      "replay": {"cases": {case["id"]: {"code": "apps/desktop/e2e/granular-auxiliary.spec.ts",
                                                        "command": "fixed UI replay"}}}}
            model = granular.build_model(CATALOG, report, run_root=root, variants=VARIANTS)
            self.assertEqual([row["id"] for row in model["cases"]], [case["id"]])
            self.assertEqual(model["tc_counts"], {"PASS": 1, "FAIL": 0, "BLOCKED": 0})
            self.assertEqual(model["auxiliary_tc_counts"], {"PASS": 1, "FAIL": 0, "BLOCKED": 0})
            self.assertEqual(len(model["out_of_scope"]), 77)

    def test_service_observed_login_requires_single_playwright_ui_trace(self):
        identity = "TC-TM001-LOGIN-13"
        raw = json.dumps({"suites": [{"specs": [{"title": identity, "file": "granular-login.spec.ts", "ok": True,
                                              "tests": [{"results": [{"status": "passed", "retry": 0}]}]}]}]}).encode()
        steps = [("fill", "auth.username"), ("fill", "auth.password"), ("click", "auth.login"),
                 ("expect", "auth.error"), ("fill", "auth.username"), ("fill", "auth.password"),
                 ("click", "auth.login"), ("expect", "session.username")]
        def trace(actions):
            stream = BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr("trace.trace", "\n".join(json.dumps(event) for index, (method, selector) in enumerate(actions)
                    for event in ({"type": "before", "callId": str(index), "class": "Frame", "method": method,
                                   "params": {"selector": f'internal:testid=[data-testid="{selector}"s]'}},
                                  {"type": "after", "callId": str(index)})))
            return stream.getvalue()
        self.assertIsNone(granular.playwright_ui_proof(identity, raw, trace(steps)))
        self.assertIn("UI trace", granular.playwright_ui_proof(identity, raw, trace(steps[:-1])))
        retry = raw.replace(b'"retry": 0', b'"retry": 1')
        self.assertIn("单次", granular.playwright_ui_proof(identity, retry, trace(steps)))
        generic = raw.replace(identity.encode(), b"TC-TM001-LOGIN-19#A")
        self.assertIsNone(granular.playwright_ui_proof("TC-TM001-LOGIN-19#A", generic, trace(steps)))
        self.assertIn("UI trace", granular.playwright_ui_proof("TC-TM001-LOGIN-19#A", generic,
                                                         trace([("fill", "auth.username")])))

    def test_frozen_catalog_rejects_moving_override(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            source = root / "test-code/tests/test_cases.json"
            source.parent.mkdir(parents=True)
            source.write_text('{"release_id":"frozen"}')
            report = {"schema_version": 3, "test_inputs_sha256": {"tests/test_cases.json": granular.sha(source.read_bytes())},
                      "test_code_snapshot": [descriptor(root, source)]}
            self.assertEqual(granular.frozen_input(report, root, "tests/test_cases.json", None), source)
            override = root / "moving.json"
            override.write_text('{"release_id":"changed"}')
            with self.assertRaises(granular.Invalid):
                granular.frozen_input(report, root, "tests/test_cases.json", override)
            source.write_text('{"release_id":"tampered"}')
            with self.assertRaises(granular.Invalid):
                granular.frozen_input(report, root, "tests/test_cases.json", None)

    def test_supplemental_audit_can_only_lower_original_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            case = next(item for item in CURRENT if item["id"] == "TC-TM001-LOGIN-01")
            item = recorded_case(root, "auditmain", case, "PASS")
            code = root / "test-code/apps/desktop/e2e/granular-login.spec.ts"
            code.parent.mkdir(parents=True)
            code.write_text("fixed test source")
            source = {"run_id": "auditmain", "release_id": CATALOG["release_id"], "state": "BLOCKED",
                      "source_commit": "a" * 40, "expected_cases": [case["id"]], "tc_results": [item],
                      "test_code_snapshot": [descriptor(root, code)],
                      "replay": {"cases": {case["id"]: {"code": "apps/desktop/e2e/granular-login.spec.ts",
                                                        "command": "fixed replay"}}}}
            audit_root = root / "audit"
            auditor = audit_root / "audit-code/audit_granular_evidence.py"
            auditor.parent.mkdir(parents=True)
            auditor.write_text("fixed auditor")
            finding = {"case_id": case["id"], "original_state": "PASS", "state": "BLOCKED",
                       "reason": "Independent UI assertion is insufficient",
                       "test_code_sha256": granular.sha(code.read_bytes()),
                       "evidence": {"events": item["evidence"]["events"]}}
            audit = {"schema_version": 2, "run_id": "auditmain", "source_commit": "a" * 40,
                     "audited_cases": [case["id"]], "findings": [finding],
                     "auditor_code": descriptor(audit_root, auditor),
                     "auditor_code_sha256": granular.sha(auditor.read_bytes()), "state": "BLOCKED"}
            model = granular.build_model(CATALOG, source, run_root=root, audit_report=audit,
                                         audit_root=audit_root)
            row = next(row for row in model["cases"] if row["id"] == case["id"])
            self.assertEqual((row["reported_state"], row["state"], row["audit_state"]),
                             ("PASS", "BLOCKED", "BLOCKED"))
            self.assertIn("独立复核", row["reason"])
            finding["state"] = "PASS"
            source["tc_results"][0]["evidence"]["screenshots"][0]["sha256"] = "0" * 64
            still_blocked = granular.build_model(CATALOG, source, run_root=root, audit_report=audit,
                                                 audit_root=audit_root)
            self.assertEqual(next(row for row in still_blocked["cases"] if row["id"] == case["id"])["state"],
                             "BLOCKED")
            audit["audited_cases"] = []
            with self.assertRaises(granular.Invalid):
                granular.build_model(CATALOG, source, run_root=root, audit_report=audit, audit_root=audit_root)

    def test_legacy_aggregate_pass_does_not_mark_any_tc_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            event_file = root / "events.jsonl"
            event_file.write_text(json.dumps({"run_id": "legacy01", "case_id": "E2E-TM001-001",
                                              "step": "default_routes", "passed": True}) + "\n")
            report = {"run_id": "legacy01", "release_id": CATALOG["release_id"], "state": "PASS",
                      "expected_cases": ["E2E-TM001-001"],
                      "suites": [{"case_id": "E2E-TM001-001", "state": "PASS", "events": descriptor(root, event_file)}]}
            model = granular.build_model(CATALOG, report, run_root=root)
            self.assertEqual(len(model["cases"]), 78)
            self.assertEqual({row["id"] for row in model["future"]}, FUTURE_IDS)
            self.assertEqual(model["tc_counts"], {"PASS": 0, "FAIL": 0, "BLOCKED": 78})
            self.assertEqual(model["suites"][0]["state"], "PASS")
            self.assertTrue(all(case["state"] == "BLOCKED" for case in model["cases"]))

    def test_fresh_tc_records_need_exact_steps_and_source_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            run_id = "granular01"
            passing = recorded_case(root, run_id, CURRENT[0], "PASS")
            failing = recorded_case(root, run_id, CURRENT[1], "FAIL", 1)
            report = {"run_id": run_id, "release_id": CATALOG["release_id"], "state": "FAIL",
                      "expected_cases": [CURRENT[0]["id"], CURRENT[1]["id"]],
                      "tc_results": [passing, failing], "suites": []}
            model = granular.build_model(CATALOG, report, run_root=root)
            rows = {case["id"]: case for case in model["cases"]}
            self.assertEqual(rows[CURRENT[0]["id"]]["state"], "PASS")
            self.assertEqual(rows[CURRENT[1]["id"]]["state"], "FAIL")
            self.assertEqual(model["tc_counts"], {"PASS": 1, "FAIL": 1, "BLOCKED": 76})
            self.assertTrue(all(step["state"] == "PASS" for step in model["steps"] if step["tc_id"] == CURRENT[0]["id"]))
            passing["evidence"]["events"]["sha256"] = "0" * 64
            changed = granular.build_model(CATALOG, report, run_root=root)
            row = next(case for case in changed["cases"] if case["id"] == CURRENT[0]["id"])
            self.assertEqual(row["state"], "BLOCKED")
            self.assertIn("证据缺口", row["reason"])

    def test_pending_baseline_and_foreign_checks_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            pending = {**CURRENT[0], "design_status": "baseline_pending", "missing": ["synthetic baseline gap"]}
            record = recorded_case(root, "granular02", pending, "PASS")
            report = {"run_id": "granular02", "release_id": CATALOG["release_id"], "state": "PASS",
                      "expected_cases": [pending["id"]], "tc_results": [record], "suites": []}
            modified = {**CATALOG, "cases": [pending if case["id"] == pending["id"] else case for case in CATALOG["cases"]]}
            model = granular.build_model(modified, report, run_root=root)
            row = next(case for case in model["cases"] if case["id"] == pending["id"])
            self.assertEqual(row["state"], "BLOCKED")
            self.assertIn("基线", row["reason"])
            with self.assertRaises(granular.Invalid):
                granular.build_model(modified, report, run_root=root, checks={"run_id": "another", "checks": []})

    def test_aggregate_and_tc_runs_keep_separate_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            granular_run = {"run_id": "detail01", "release_id": CATALOG["release_id"], "state": "BLOCKED",
                            "source_commit": "detail-sha", "expected_cases": [CURRENT[0]["id"]], "tc_results": [], "suites": []}
            aggregate = {"run_id": "aggregate01", "release_id": CATALOG["release_id"], "state": "FAIL",
                         "source_commit": "aggregate-sha", "expected_cases": ["E2E-TM001-001"], "suites": []}
            model = granular.build_model(CATALOG, granular_run, run_root=root,
                                         aggregate_report=aggregate, aggregate_root=root)
            self.assertEqual(model["run_id"], "detail01")
            self.assertEqual(model["aggregate_run_id"], "aggregate01")
            self.assertEqual(model["aggregate_candidate_sha"], "aggregate-sha")
            self.assertEqual(model["tc_counts"]["BLOCKED"], 78)

    def test_basic_checks_keep_each_real_state_and_count(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            report = {"run_id": "checks01", "release_id": CATALOG["release_id"], "state": "BLOCKED",
                      "expected_cases": [CURRENT[0]["id"]], "tc_results": [], "suites": []}
            checks = {"run_id": "checks01", "checks": [
                {"id": "docs-structure", "command": "python3 scripts/check_docs.py --mode structure",
                 "scope": "governance", "state": "PASS", "passed": 1, "total": 1,
                 "exit_code": 0, "evidence": ".local/ci/structure.json", "note": ""},
                {"id": "docs-baseline", "command": "python3 scripts/check_docs.py --mode baseline",
                 "scope": "governance", "state": "FAIL", "passed": 0, "total": 1,
                 "exit_code": 1, "evidence": ".local/ci/baseline.json", "note": "six drafts"}]}
            model = granular.build_model(CATALOG, report, run_root=root, checks=checks)
            self.assertEqual([row["state"] for row in model["checks"]], ["PASS", "FAIL"])
            self.assertEqual(model["checks"][1]["note"], "six drafts")
            self.assertEqual(model["tc_counts"]["BLOCKED"], 78)
            checks["checks"].append(dict(checks["checks"][0]))
            with self.assertRaises(granular.Invalid):
                granular.build_model(CATALOG, report, run_root=root, checks=checks)

    def test_parent_pass_requires_every_declared_variant(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            parent = next(case for case in CURRENT if case["id"] == "TC-TM001-LOGIN-17")
            declared = [variant for variant in VARIANTS["variants"] if variant["parent_id"] == parent["id"]]
            first = recorded_case(root, "variants01", parent, "PASS", identity=declared[0]["id"])
            parent_summary = {"case_id": parent["id"], "state": "PASS", "step_results": [], "evidence": {}}
            report = {"run_id": "variants01", "release_id": CATALOG["release_id"], "state": "BLOCKED",
                      "expected_cases": [parent["id"], *(variant["id"] for variant in declared)],
                      "tc_results": [parent_summary, first], "suites": []}
            model = granular.build_model(CATALOG, report, run_root=root, variants=VARIANTS)
            row = next(case for case in model["cases"] if case["id"] == parent["id"])
            self.assertEqual(row["state"], "BLOCKED")
            self.assertEqual([variant["state"] for variant in model["variants"] if variant["parent_id"] == parent["id"]],
                             ["PASS", "BLOCKED"])
            second = recorded_case(root, "variants01", parent, "PASS", identity=declared[1]["id"])
            report["tc_results"].append(second)
            model = granular.build_model(CATALOG, report, run_root=root, variants=VARIANTS)
            row = next(case for case in model["cases"] if case["id"] == parent["id"])
            self.assertEqual(row["state"], "PASS")
            second["state"] = "FAIL"
            report["tc_results"][-1] = second
            model = granular.build_model(CATALOG, report, run_root=root, variants=VARIANTS)
            row = next(case for case in model["cases"] if case["id"] == parent["id"])
            self.assertEqual(row["state"], "FAIL")

    def test_auxiliary_pass_needs_same_candidate_time_and_independent_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            auxiliary = [case for case in CURRENT if case["id"].startswith(granular.AUX_PREFIXES)]
            ui = next(case for case in auxiliary if case["id"] == "TC-TM001-UI-01")
            aux_run_id = "aux01"
            passing = recorded_case(root, aux_run_id, ui, "PASS")
            primary = {"run_id": "main01", "release_id": CATALOG["release_id"], "state": "BLOCKED",
                       "source_commit": "a" * 40, "candidate_tree": "b" * 64,
                       "package": {"dmg_sha256": "c" * 64},
                       "started_at": "2026-09-30T11:00:00Z", "finished_at": "2026-09-30T12:00:00Z",
                       "expected_cases": [case["id"] for case in CURRENT], "tc_results": [], "suites": []}
            supplement = {"run_id": aux_run_id, "parent_run_id": primary["run_id"],
                          "release_id": primary["release_id"], "state": "BLOCKED",
                          "cleanup_completed": True,
                          "source_commit": primary["source_commit"], "candidate_tree": primary["candidate_tree"],
                          "package": primary["package"],
                          "started_at": "2026-09-30T12:01:00Z", "finished_at": "2026-09-30T12:02:00Z",
                          "expected_cases": [case["id"] for case in auxiliary],
                          "tc_results": [passing] + [{"case_id": case["id"], "state": "BLOCKED",
                                                       "reason": "not executed", "step_results": [], "evidence": {}}
                                                      for case in auxiliary if case["id"] != ui["id"]]}
            model = granular.build_model(CATALOG, primary, run_root=root,
                                         auxiliary_report=supplement, auxiliary_root=root)
            self.assertTrue(model["auxiliary_bound"])
            self.assertEqual(next(row for row in model["cases"] if row["id"] == ui["id"])["state"], "PASS")
            self.assertEqual(model["tc_counts"], {"PASS": 1, "FAIL": 0, "BLOCKED": 77})
            self.assertEqual(len(model["auxiliary"]), 11)
            supplement["package"] = {"dmg_sha256": "d" * 64}
            mismatch = granular.build_model(CATALOG, primary, run_root=root,
                                            auxiliary_report=supplement, auxiliary_root=root)
            self.assertFalse(mismatch["auxiliary_bound"])
            self.assertEqual(next(row for row in mismatch["cases"] if row["id"] == ui["id"])["state"], "BLOCKED")
            supplement["package"] = primary["package"]
            passing["state"] = "FAIL"
            passing["step_results"][0]["passed"] = False
            event_path = root / ui["id"] / "events.jsonl"
            event = json.loads(event_path.read_text())
            event["passed"] = False
            event_path.write_text(json.dumps(event) + "\n")
            passing["evidence"]["events"] = descriptor(root, event_path)
            failed = granular.build_model(CATALOG, primary, run_root=root,
                                          auxiliary_report=supplement, auxiliary_root=root)
            failed_row = next(row for row in failed["cases"] if row["id"] == ui["id"])
            self.assertEqual(failed_row["state"], "FAIL")
            self.assertEqual(failed_row["result_run_id"], aux_run_id)
            passing["state"] = "PASS"
            passing["step_results"][0]["passed"] = True
            event["passed"] = True
            event_path.write_text(json.dumps(event) + "\n")
            passing["evidence"]["events"] = descriptor(root, event_path)
            (root / ui["id"] / "screen.png").write_bytes(b"not an image")
            screenshot_gap = granular.build_model(CATALOG, primary, run_root=root,
                                                  auxiliary_report=supplement, auxiliary_root=root)
            self.assertEqual(next(row for row in screenshot_gap["cases"] if row["id"] == ui["id"])["state"], "BLOCKED")

    def test_evidence_copy_is_relative_and_hash_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            original = root / "events.jsonl"
            original.write_text('{"step":1}\n')
            model = {"source_files": [{"role": "run", "path": "result.json", "sha256": granular.sha(original.read_bytes()),
                                        "absolute_path": str(original)}],
                     "evidence": [{"role": "TC events", "path": "events.jsonl", "state": "已核对",
                                   "sha256": granular.sha(original.read_bytes()), "absolute_path": str(original)}]}
            destination = root / "report"
            destination.mkdir()
            copied = granular.copy_verified_evidence(model, destination)
            self.assertNotIn("absolute_path", json.dumps(copied))
            self.assertEqual(copied["copied_evidence_count"], 1)
            stored = destination / copied["evidence"][0]["link"]
            self.assertEqual(stored.read_bytes(), original.read_bytes())
            original.write_text("changed")
            self.assertNotEqual(stored.read_bytes(), original.read_bytes())


if __name__ == "__main__":
    unittest.main()
