#!/usr/bin/env python3
"""Execute fixed TM-001 auxiliary TC bindings against owned local evidence.

Governance cases exercise real read-only validators on independent fixtures.
UI cases use fixed Playwright assertions against an installed App and an owned
service/database. This program never grants release eligibility.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Callable
import zipfile
import xml.etree.ElementTree as ET
import zlib

try:
    from . import export_test_cases, granular_gate, granular_test_result as results
except ImportError:
    import export_test_cases
    import granular_gate
    import granular_test_result as results


ROOT = Path(__file__).resolve().parents[1]
CASES = ("TC-TM001-UI-01", "TC-TM001-UI-02", "TC-TM001-UI-03",
         "TC-TM001-CATALOG-01", "TC-TM001-CATALOG-02", "TC-TM001-CATALOG-03",
         "TC-TM001-RECORDS-01", "TC-TM001-RECORDS-02",
         "TC-TM001-GATE-01", "TC-TM001-GATE-02", "TC-TM001-GATE-03")
UI_CASES = set(CASES[:3])


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    os.chmod(path, 0o600)


def descriptor(path: Path, root: Path) -> dict:
    raw = results.read_file(path)
    return {"path": str(path.relative_to(root)), "sha256": results.sha(raw), "bytes": len(raw)}


def command(args: list[str], case_dir: Path, label: str) -> dict:
    completed = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=180, check=False)
    record = {"argv": args, "exit_code": completed.returncode,
              "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:]}
    save(case_dir / f"{label}.json", record)
    return record


def workbook_case_ids(path: Path) -> list[str]:
    """Read actual ID cells from the project workbook, without regenerating it."""
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    relation = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    with zipfile.ZipFile(path) as archive:
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = book.find(f"{{{main}}}sheets")
        target = next((item for item in sheets if item.get("name") == "05测试用例"), None)
        if target is None:
            raise ValueError("Project workbook has no 05测试用例 sheet")
        rid = target.get(f"{{{relation}}}id")
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        link = next((item.get("Target") for item in relationships
                     if item.get("Id") == rid and item.tag == f"{{{package_rel}}}Relationship"), None)
        if not link:
            raise ValueError("Project workbook case sheet relationship is missing")
        sheet_path = "xl/" + link.lstrip("/").removeprefix("xl/")
        sheet = ET.fromstring(archive.read(sheet_path))
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in item.iter(f"{{{main}}}t")) for item in strings]
        found = []
        for cell in sheet.iter(f"{{{main}}}c"):
            ref = cell.get("r", "")
            match = re.fullmatch(r"B(\d+)", ref)
            if not match or int(match[1]) < 5:
                continue
            raw = cell.find(f"{{{main}}}v")
            inline = cell.find(f"{{{main}}}is")
            value = "" if raw is None else raw.text or ""
            if cell.get("t") == "s":
                value = shared[int(value)]
            elif inline is not None:
                value = "".join(t.text or "" for t in inline.iter(f"{{{main}}}t"))
            if value:
                found.append(value)
        return found


def catalog_01(case_dir: Path, context: dict) -> dict:
    catalog = context["catalog"]
    errors = export_test_cases.validate_catalog(catalog, ROOT)
    current = results.read_file(ROOT / "TEST_CASES.md").decode("utf-8")
    rendered = export_test_cases.render_markdown(catalog)
    workbook = ROOT / "TokenMeter项目总表.xlsx"
    from_workbook = workbook_case_ids(workbook)
    identifiers = [identity for case in catalog["cases"]
                   for identity in [case["id"], *(variant["id"] for variant in case.get("variants", []))]]
    concrete = [case for case in catalog["cases"] if not case.get("aggregate_planned")]
    actual = {"catalog_errors": errors, "catalog_count": len(identifiers),
              "unique_count": len(set(identifiers)), "all_concrete_have_tasks_and_ac":
              all(case.get("task_ids") and case.get("ac_ids") for case in concrete),
              "markdown_matches_catalog": current == rendered,
              "workbook_ids_match_catalog": from_workbook == identifiers,
              "workbook_count": len(from_workbook),
              "source_sha256": results.sha(results.read_file(ROOT / "tests/test_cases.json")),
              "workbook_sha256": results.sha(results.read_file(workbook))}
    save(case_dir / "catalog-check.json", actual)
    actual["passed"] = (not errors and len(identifiers) == len(set(identifiers))
                        and actual["all_concrete_have_tasks_and_ac"] and current == rendered
                        and from_workbook == identifiers)
    return actual


def catalog_02(case_dir: Path, context: dict) -> dict:
    original = context["catalog"]
    modifications = {
        "duplicate_id": lambda doc: doc["cases"].append(deepcopy(doc["cases"][0])),
        "missing_input": lambda doc: doc["cases"][0].pop("input"),
        "missing_expected": lambda doc: doc["cases"][0]["steps"][0].update(expected="", expected_ui="", expected_api_db=""),
        "wrong_source": lambda doc: doc["cases"][0]["source"].update(path="../outside.md"),
    }
    terms = {"duplicate_id": "duplicate case ID", "missing_input": "missing fields",
             "missing_expected": "independent expected", "wrong_source": "source is not a repository file"}
    observations = {}
    for name, mutate in modifications.items():
        document = deepcopy(original)
        mutate(document)
        save(case_dir / f"{name}.json", document)
        errors = export_test_cases.validate_catalog(document, ROOT)
        observations[name] = {"errors": errors, "rejected": any(terms[name] in error for error in errors)}
    actual = {"checks": observations, "generated_index_exists": (case_dir / "TEST_CASES.md").exists(),
              "passed": all(item["rejected"] for item in observations.values())
              and not (case_dir / "TEST_CASES.md").exists()}
    save(case_dir / "mutation-results.json", actual)
    return actual


def catalog_03(case_dir: Path, context: dict) -> dict:
    baseline = command([sys.executable, "scripts/export_test_cases.py", "--check"], case_dir, "current-index-command")
    original = results.read_file(ROOT / "TEST_CASES.md")
    stale = case_dir / "stale-TEST_CASES.md"
    stale.write_bytes(original.replace(b"| ", b"| CHANGED ", 1))
    os.chmod(stale, 0o600)
    before = results.read_file(stale)
    negative = command([sys.executable, "scripts/export_test_cases.py", "--output", str(stale), "--check"],
                       case_dir, "stale-index-command")
    actual = {"current_exit": baseline["exit_code"], "stale_exit": negative["exit_code"],
              "stale_state": "STALE" in negative["stdout"], "read_only": results.read_file(stale) == before,
              "passed": baseline["exit_code"] == 0 and negative["exit_code"] != 0
              and "STALE" in negative["stdout"] and results.read_file(stale) == before}
    save(case_dir / "index-consistency.json", actual)
    return actual


def _png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))


def _fixture_record(case: dict, identity: str, root: Path, run_id: str, *, fail: bool = False) -> dict:
    folder = root / identity
    folder.mkdir(mode=0o700)
    events, steps = [], []
    governance = identity.startswith(("TC-TM001-CATALOG-", "TC-TM001-RECORDS-", "TC-TM001-GATE-"))
    for step in case["steps"]:
        passed = not (fail and step["step"] == case["steps"][-1]["step"])
        result = {"step": step["step"], "action": step["action"], "expected": step["expected"],
                  "actual": {"fixture_assertion": passed, "case": identity}, "passed": passed,
                  "timestamp": now(), "source": "command" if governance else "ui"}
        steps.append(result)
        events.append({"run_id": run_id, "case_id": identity, **result})
    event_file = folder / "events.jsonl"
    event_file.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in events), encoding="utf-8")
    os.chmod(event_file, 0o600)
    evidence = {"events": descriptor(event_file, root)}
    if governance:
        evidence_file = folder / "command.json"
        save(evidence_file, {"fixture": True, "case_id": identity, "assertions": [item["passed"] for item in steps]})
        evidence["command_log"] = descriptor(evidence_file, root)
    else:
        for role in ("trace", "database_before", "database_after", "service_audit"):
            evidence_file = folder / f"{role}.json"
            save(evidence_file, {"fixture": True, "case_id": identity, "role": role})
            evidence[role] = descriptor(evidence_file, root)
        screen = folder / "screen.png"
        screen.write_bytes(_png())
        os.chmod(screen, 0o600)
        evidence["screenshots"] = [descriptor(screen, root)]
    return {"case_id": identity, "state": "FAIL" if fail else "PASS", "reason": "fixture assertion failed" if fail else "",
            "step_results": steps, "evidence": evidence, "started_at": now(), "finished_at": now()}


def records_fixture(case_dir: Path, context: dict, *, fail: bool = False) -> tuple[Path, Path, Path, Path, dict]:
    root = case_dir / "fixture"
    root.mkdir(mode=0o700)
    catalog = deepcopy(context["catalog"])
    selected = [case for case in catalog["cases"] if case["id"] in ("TC-TM001-RECORDS-01", "TC-TM001-RECORDS-02")]
    for case in selected:
        first = case["steps"][0]
        case["steps"] = [{**first, "action": "Read owned fixture input", "expected": "Owned fixture input is unchanged"},
                         {**first, "step": 2, "action": "Compare independent fixture observation",
                          "expected": "Observed fixture value equals its declared baseline"}]
    run_id = "record-fixture-" + context["run_id"]
    records = [_fixture_record(selected[0], selected[0]["id"], root, run_id, fail=fail)]
    if fail:
        records.append({"case_id": selected[1]["id"], "state": "BLOCKED",
                        "reason": "Owned fixture prerequisite deliberately absent", "step_results": [], "evidence": {},
                        "started_at": None, "finished_at": None})
    else:
        records.append(_fixture_record(selected[1], selected[1]["id"], root, run_id))
    source_release = results.tm001_case_release(catalog)
    report = {"schema_version": 2, "scope": "governance_records_fixture", "run_id": run_id,
              "release_id": source_release, "state": "FAIL" if fail else "BLOCKED",
              "release_eligible": False, "expected_cases": [entry["case_id"] for entry in records],
              "tc_results": records, "suites": []}
    source = root / "result.json"
    catalog_file = root / "catalog.json"
    variant_file = root / "variants.json"
    update_variant_file = root / "update-variants.json"
    save(source, report)
    save(catalog_file, catalog)
    save(variant_file, {"release_id": source_release, "variants": []})
    save(update_variant_file, {"release_id": source_release, "variants": []})
    return source, catalog_file, variant_file, update_variant_file, report


def records_01(case_dir: Path, context: dict) -> dict:
    source, catalog, variants, update_variants, _ = records_fixture(case_dir, context)
    report_before = results.read_file(source)
    output = case_dir / "excel"
    receipt = results.export(source, output, catalog_path=catalog, variants_path=variants,
                             update_variants_path=update_variants)
    workbook = output / receipt["workbook"]["path"]
    saved_before = results.read_file(workbook)
    modified_before = workbook.stat().st_mtime_ns
    repeated = results.export(source, output, catalog_path=catalog, variants_path=variants,
                              update_variants_path=update_variants)
    actual = {"first_export": receipt["state"], "repeat_same_receipt": receipt == repeated,
              "repeat_did_not_overwrite": workbook.stat().st_mtime_ns == modified_before and results.read_file(workbook) == saved_before,
              "fixture_source_unchanged": results.read_file(source) == report_before,
              "fixture_tc_counts": receipt["tc_counts"], "product_state": receipt["product_state"],
              "workbook_sha256": receipt["workbook"]["sha256"],
              "passed": (receipt["state"] == "PASS" and receipt["tc_counts"] == {"PASS": 2, "FAIL": 0, "BLOCKED": 76}
                         and receipt["product_state"] == "BLOCKED" and receipt == repeated
                         and workbook.stat().st_mtime_ns == modified_before and results.read_file(source) == report_before)}
    save(case_dir / "records-success.json", actual)
    return actual


def records_02(case_dir: Path, context: dict) -> dict:
    source, catalog, variants, update_variants, fixture = records_fixture(case_dir, context, fail=True)
    first_events = case_dir / "fixture" / fixture["tc_results"][0]["evidence"]["events"]["path"]
    original_events = results.read_file(first_events)
    output = case_dir / "excel"
    receipt = results.export(source, output, catalog_path=catalog, variants_path=variants,
                             update_variants_path=update_variants)
    failed_before = receipt["tc_counts"] == {"PASS": 0, "FAIL": 1, "BLOCKED": 77}
    previous = os.environ.get("TOKENMETER_WORKBOOK_NODE")
    os.environ["TOKENMETER_WORKBOOK_NODE"] = "/definitely-missing-tokenmeter-node"
    try:
        try:
            results.export(source, case_dir / "missing-runtime", catalog_path=catalog, variants_path=variants,
                           update_variants_path=update_variants)
        except results.Blocked:
            missing_runtime_blocked = True
        else:
            missing_runtime_blocked = False
    finally:
        if previous is None:
            os.environ.pop("TOKENMETER_WORKBOOK_NODE", None)
        else:
            os.environ["TOKENMETER_WORKBOOK_NODE"] = previous
    workbook = output / receipt["workbook"]["path"]
    with workbook.open("ab") as stream:
        stream.write(b"tampered")
    try:
        results.export(source, output, catalog_path=catalog, variants_path=variants,
                       update_variants_path=update_variants)
    except results.Invalid:
        tamper_rejected = True
    else:
        tamper_rejected = False
    actual = {"fixture_tc_counts": receipt["tc_counts"], "missing_runtime_blocked": missing_runtime_blocked,
              "tampered_export_rejected": tamper_rejected, "first_events_preserved": results.read_file(first_events) == original_events,
              "product_state": receipt["product_state"],
              "passed": failed_before and missing_runtime_blocked and tamper_rejected
              and results.read_file(first_events) == original_events and receipt["product_state"] == "FAIL"}
    save(case_dir / "records-failure.json", actual)
    return actual


def gate_fixture(case_dir: Path, context: dict) -> tuple[dict, dict, dict, dict]:
    root = case_dir / "fixture"
    root.mkdir(mode=0o700)
    catalog = deepcopy(context["catalog"])
    current = [case for case in catalog["cases"] if case["feature_id"] == "TM-001"]
    for case in current:
        case["design_status"] = "designed"
        case["binding"] = {"fixed_fixture_code": "scripts/granular_auxiliary.py", "tc_identity": case["id"]}
    variants = context["variants"]
    by_parent = {}
    for variant in variants["variants"]:
        by_parent.setdefault(variant["parent_id"], []).append(variant)
    run_id = "governance-" + context["run_id"]
    records = []
    for case in current:
        children = by_parent.get(case["id"], [])
        if children:
            records.append({"case_id": case["id"], "state": "PASS", "reason": "fixture summary of independent variants",
                            "step_results": [], "evidence": {}})
            for variant in children:
                selected = variant.get("step_numbers", [step["step"] for step in case["steps"]])
                subset = {**case, "steps": [step for step in case["steps"] if step["step"] in selected]}
                records.append(_fixture_record(subset, variant["id"], root, run_id))
        else:
            records.append(_fixture_record(case, case["id"], root, run_id))
    report = {"schema_version": 2, "scope": "governance_fixture", "state": "PASS",
              "release_eligible": False, "run_id": run_id, "release_id": catalog["release_id"],
              "source_commit": "a" * 64, "candidate_tree": "b" * 64, "package": {"dmg_sha256": "c" * 64},
              "started_at": now(), "finished_at": now(), "cleanup_completed": True,
              "expected_cases": [item["case_id"] for item in records], "tc_results": records, "suites": []}
    plan = {"execution_bindings_status": "ready", "test_plan_status": "baselined"}
    save(root / "fixture-report.json", report)
    save(root / "fixture-plan.json", plan)
    return catalog, report, plan, root


def gate_01(case_dir: Path, context: dict) -> dict:
    catalog, report, plan, root = gate_fixture(case_dir, context)
    variants = context["variants"]
    base = granular_gate.verify_candidate(catalog, report, run_root=root, plan=plan, variants=variants, fixture=True)
    changes = {}
    for name in ("missing", "duplicate", "skipped", "foreign_release", "missing_events", "aggregate_only"):
        changed = deepcopy(report)
        if name == "missing":
            changed["expected_cases"].pop()
            changed["tc_results"].pop()
        elif name == "duplicate":
            changed["expected_cases"].append(changed["expected_cases"][0])
            changed["tc_results"].append(deepcopy(changed["tc_results"][0]))
        elif name == "skipped":
            changed["tc_results"][0]["state"] = "BLOCKED"
        elif name == "foreign_release":
            changed["release_id"] = "v9.9.9-20990101T000000Z"
        elif name == "missing_events":
            target = next(item for item in changed["tc_results"] if item.get("evidence", {}).get("events"))
            target["evidence"]["events"] = None
        elif name == "aggregate_only":
            changed["expected_cases"] = ["E2E-TM001-001"]
            changed["tc_results"] = []
            changed["suites"] = [{"case_id": "E2E-TM001-001", "state": "PASS"}]
        outcome = granular_gate.verify_candidate(catalog, changed, run_root=root, plan=plan, variants=variants, fixture=True)
        changes[name] = {"state": outcome["state"], "reasons": outcome["reasons"]}
    actual = {"base_state": base["state"], "rejections": changes, "passport_written": False,
              "passed": base["state"] == "PASS" and all(item["state"] == "FAIL" for item in changes.values())}
    save(case_dir / "gate-negative.json", actual)
    return actual


def gate_02(case_dir: Path, context: dict) -> dict:
    catalog, report, plan, root = gate_fixture(case_dir, context)
    variants = context["variants"]
    outcomes = {}
    draft = granular_gate.verify_candidate(catalog, report, run_root=root,
                                           plan={**plan, "test_plan_status": "draft"}, variants=variants, fixture=True)
    outcomes["draft_plan"] = draft["state"] == "FAIL" and any("计划" in reason for reason in draft["reasons"])
    pending = deepcopy(catalog)
    current = next(case for case in pending["cases"] if case["feature_id"] == "TM-001")
    current["design_status"] = "baseline_pending"
    outcome = granular_gate.verify_candidate(pending, report, run_root=root, plan=plan, variants=variants, fixture=True)
    outcomes["pending_baseline"] = outcome["state"] == "FAIL" and any("基线" in reason for reason in outcome["reasons"])
    unbound = deepcopy(catalog)
    current = next(case for case in unbound["cases"] if case["feature_id"] == "TM-001")
    current["binding"] = None
    outcome = granular_gate.verify_candidate(unbound, report, run_root=root, plan=plan, variants=variants, fixture=True)
    outcomes["missing_binding"] = outcome["state"] == "FAIL" and any("执行绑定" in reason for reason in outcome["reasons"])
    actual = {"checks": outcomes, "passed": all(outcomes.values()), "passport_written": False}
    save(case_dir / "gate-incomplete.json", actual)
    return actual


def gate_03(case_dir: Path, context: dict) -> dict:
    catalog, report, plan, root = gate_fixture(case_dir, context)
    variants = context["variants"]
    valid = granular_gate.verify_candidate(catalog, report, run_root=root, plan=plan, variants=variants, fixture=True)
    changed = deepcopy(report)
    record = next(item for item in changed["tc_results"] if item.get("evidence", {}).get("events"))
    record["evidence"]["events"]["sha256"] = "0" * 64
    invalid = granular_gate.verify_candidate(catalog, changed, run_root=root, plan=plan, variants=variants, fixture=True)
    actual = {"valid_state": valid["state"], "tampered_state": invalid["state"],
              "valid_release_eligible": valid["release_eligible"], "tampered_reasons": invalid["reasons"],
              "passport_written": False,
              "passed": valid["state"] == "PASS" and invalid["state"] == "FAIL"
              and valid["release_eligible"] is False and not list(case_dir.rglob("passport.json"))}
    save(case_dir / "gate-valid-and-tampered.json", actual)
    return actual


HANDLERS: dict[str, Callable[[Path, dict], dict]] = {
    "TC-TM001-CATALOG-01": catalog_01, "TC-TM001-CATALOG-02": catalog_02,
    "TC-TM001-CATALOG-03": catalog_03,
    "TC-TM001-RECORDS-01": records_01, "TC-TM001-RECORDS-02": records_02,
    "TC-TM001-GATE-01": gate_01, "TC-TM001-GATE-02": gate_02, "TC-TM001-GATE-03": gate_03,
}


def run_ui_cases(cases: list[dict], args: argparse.Namespace, parent: dict, output: Path) -> tuple[dict[str, dict], bool]:
    """Execute fixed UI specs only inside one owned installed-DMG session."""
    if str(ROOT / "scripts") not in sys.path:
        sys.path.insert(0, str(ROOT / "scripts"))
    import local_e2e as base
    import granular_e2e as product

    if not args.with_ui:
        return {case["id"]: product.blocked(case, "需要 --with-ui 与同候选安装包；本轮未执行桌面 UI")
                for case in cases}, True
    if not all((args.package_manifest, args.dmg, args.update_zip)):
        raise results.Invalid("UI cases require --package-manifest, --dmg and --update-zip")
    manifest = results.safe_path(args.package_manifest)
    dmg = results.safe_path(args.dmg)
    update_zip = results.safe_path(args.update_zip)
    parent_package = parent.get("package") or {}
    if (results.sha(results.read_file(manifest)) != parent_package.get("manifest_sha256")
            or results.sha(results.read_file(dmg)) != parent_package.get("dmg_sha256")):
        raise results.Invalid("UI package manifest or DMG differs from the parent run")
    development = parent_package.get("installed_source") == "development_dmg"
    package = base.verify_host_and_manifest(manifest, dmg, update_zip, parent["source_commit"],
                                            development=development)
    if package.get("candidate_tree") != parent.get("candidate_tree"):
        raise results.Invalid("UI package candidate tree differs from the parent run")
    session_args = argparse.Namespace(run_id=args.run_id, candidate_sha=parent["source_commit"],
                                      package_manifest=manifest, update_zip=update_zip)
    product.SPEC_BY_GROUP["UI"] = "granular-auxiliary.spec.ts"
    base_dir = ROOT / ".local/local-granular-work"
    base_dir.mkdir(parents=True, exist_ok=True)
    private = Path(tempfile.mkdtemp(prefix=args.run_id + "-aux-", dir=base_dir)).resolve()
    os.chmod(private, 0o700)
    save(private / "owner.json", {"owner": "tokenmeter-granular-auxiliary", "run_id": args.run_id})
    mount = private / "mounted"
    mounted = False
    safe_to_continue = True
    records = {}
    cleanup = False
    try:
        mounted_app = base.mount_dmg(dmg, mount, output / "mount.log")
        mounted = True
        tree_tool = base.module("aux_tree", "scripts/package_release_dmg.py")
        bootstrap = base.module("aux_bootstrap", "scripts/bootstrap_sqlite.py")
        fixtures = base.module("aux_fixtures", "tests/server/fixtures.py")
        for case in cases:
            if safe_to_continue:
                item, safe_to_continue = product.one_case(case, session_args, package, mounted_app,
                                                          private, output, tree_tool, bootstrap, fixtures)
            else:
                item = product.blocked(case, "前一条辅助 UI 用例未完成独占资源清理")
            if (output / "mount.log").is_file():
                item.setdefault("evidence", {})["mount_log"] = descriptor(output / "mount.log", output)
            records[case["id"]] = item
    finally:
        detached = True
        if mounted and mount.exists():
            detached = subprocess.run(["hdiutil", "detach", str(mount)], capture_output=True,
                                      text=True, check=False).returncode == 0
        removed = False
        if detached and safe_to_continue and private.is_dir():
            owner = json.loads((private / "owner.json").read_text(encoding="utf-8"))
            if owner == {"owner": "tokenmeter-granular-auxiliary", "run_id": args.run_id}:
                shutil.rmtree(private)
                removed = not private.exists()
        cleanup = detached and removed and safe_to_continue
    if not cleanup:
        for item in records.values():
            if item["state"] == "PASS":
                item["state"] = "FAIL"
                item["reason"] = "辅助 UI 安装会话未完成全部独占资源清理"
    return records, cleanup


def run_one(case: dict, context: dict, output: Path) -> dict:
    identity = case["id"]
    started = now()
    folder = output / identity
    folder.mkdir(mode=0o700)
    if identity not in HANDLERS:
        return {"case_id": identity, "state": "BLOCKED", "reason": "固定自动化绑定尚未实现",
                "started_at": started, "finished_at": now(), "step_results": [], "evidence": {}}
    try:
        actual = HANDLERS[identity](folder, context)
        passed = actual.get("passed") is True
        state, reason = ("PASS", "固定代码断言与原件均完成") if passed else ("FAIL", "固定代码断言失败；见 command-log.json")
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, subprocess.TimeoutExpired) as error:
        actual = {"error": str(error)}
        passed, state, reason = False, "FAIL", f"固定代码执行失败：{error}"
    command_log = folder / "command-log.json"
    save(command_log, {"run_id": context["run_id"], "case_id": identity,
                       "binding": f"scripts/granular_auxiliary.py::{HANDLERS[identity].__name__}",
                       "actual": actual, "state": state})
    step = case["steps"][0]
    result = {"step": step["step"], "action": step["action"], "expected": step["expected"],
              "actual": actual, "passed": passed, "timestamp": now(), "source": "command"}
    event = {"run_id": context["run_id"], "case_id": identity, **result}
    event_path = folder / "events.jsonl"
    event_path.write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(event_path, 0o600)
    raw_files = [path for path in folder.rglob("*") if path.is_file() and path not in (command_log, event_path)]
    return {"case_id": identity, "state": state, "reason": reason, "started_at": started,
            "finished_at": now(), "step_results": [result],
            "evidence": {"events": descriptor(event_path, output), "command_log": descriptor(command_log, output),
                         "raw_artifacts": [descriptor(path, output) for path in raw_files]}}


def execute(args: argparse.Namespace) -> int:
    if not results.RUN_ID.fullmatch(args.run_id):
        raise results.Invalid("Auxiliary run ID is invalid")
    output = results.safe_path(args.output)
    if output.exists():
        raise results.Invalid("Auxiliary output directory already exists")
    parent_path = results.safe_path(args.parent_report)
    if parent_path.name != "result.json":
        raise results.Invalid("Parent report must be the original result.json")
    parent, parent_bytes = results.read_json(parent_path)
    completed = results.timestamp(parent.get("finished_at"))
    if completed is None or completed > datetime.now(timezone.utc):
        raise results.Invalid("Parent run is not finished")
    catalog, catalog_bytes = results.read_json(ROOT / "tests/test_cases.json")
    login, login_bytes = results.read_json(ROOT / "tests/granular_login_variants.json")
    update_path = ROOT / "tests/granular_update_variants.json"
    update, update_bytes = results.read_json(update_path) if update_path.is_file() else (None, None)
    variants = granular_gate.combine_variants(login, update, results.tm001_case_release(catalog))
    frozen = parent.get("test_inputs_sha256")
    for relative, raw in (("tests/test_cases.json", catalog_bytes),
                          ("tests/granular_login_variants.json", login_bytes),
                          ("tests/granular_update_variants.json", update_bytes)):
        if (not isinstance(frozen, dict) or raw is None
                or frozen.get(relative) != results.sha(raw)):
            raise results.Invalid(f"Auxiliary {relative} differs from parent frozen input")
    source_releases = {case.get("release_id", catalog["release_id"])
                       for case in catalog["cases"] if case.get("feature_id") == "TM-001"}
    if source_releases != {parent.get("release_id")}:
        raise results.Invalid("Parent release differs from TM-001 source cases")
    cases = [case for case in catalog["cases"] if case["id"] in CASES]
    if len(cases) != len(CASES) or {case["id"] for case in cases} != set(CASES):
        raise results.Invalid("Auxiliary 11 TC catalog is incomplete")
    requested = set(args.case_id or CASES)
    if len(requested) != len(args.case_id or CASES) or not requested <= set(CASES):
        raise results.Invalid("Targeted auxiliary TC is unknown or repeated")
    cases = [case for case in cases if case["id"] in requested]
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    source_files = [ROOT / "scripts/granular_auxiliary.py", ROOT / "scripts/granular_gate.py",
                    ROOT / "scripts/granular_test_result.py", ROOT / "scripts/export_test_cases.py",
                    ROOT / "tests/test_cases.json", ROOT / "tests/granular_login_variants.json"]
    if update is not None:
        source_files.append(update_path)
    if any(case["id"] in UI_CASES for case in cases):
        source_files.extend(ROOT / relative for relative in (
            "apps/desktop/e2e/granular-auxiliary.spec.ts", "apps/desktop/e2e/granular-auxiliary-color.ts",
            "apps/desktop/e2e/playwright.config.ts",
            "apps/desktop/resources/TokenMeter.icns", "apps/desktop/resources/TokenMeter.svg",
            "scripts/granular_e2e.py", "scripts/local_e2e.py", "scripts/granular_service_fixture.py",
            "scripts/package_release_dmg.py", "scripts/bootstrap_sqlite.py", "tests/server/fixtures.py"))
        source_files.extend((ROOT / "server").rglob("*.py"))
    source_files = sorted(set(source_files))
    snapshot = []
    for source in source_files:
        target = output / "test-code" / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(source, target)
        os.chmod(target, 0o600)
        if results.read_file(target) != results.read_file(source):
            raise results.Invalid("Auxiliary code snapshot changed during copy")
        snapshot.append(descriptor(target, output))
    report = {"schema_version": 3,
              "scope": "granular_auxiliary_targeted_probe" if args.case_id else "granular_auxiliary_package",
              "state": "BLOCKED", "release_eligible": False, "run_id": args.run_id,
              "parent_run_id": parent["run_id"], "release_id": parent["release_id"],
              "source_commit": parent.get("source_commit"), "candidate_tree": parent.get("candidate_tree"),
              "package": parent.get("package"), "started_at": now(), "finished_at": None,
              "parent_report_sha256": results.sha(parent_bytes),
              "catalog_sha256": results.sha(catalog_bytes), "login_variants_sha256": results.sha(login_bytes),
              "update_variants_sha256": results.sha(update_bytes) if update_bytes else None,
              "test_code_snapshot": snapshot,
              "expected_cases": [case["id"] for case in cases], "tc_results": [], "cleanup_completed": True}
    replay_base = [sys.executable, str(ROOT / "scripts/granular_auxiliary.py"),
                   "--parent-report", str(parent_path), "--run-id", "<new-run-id>",
                   "--output", "<new-output>"]
    if args.with_ui:
        replay_base.append("--with-ui")
        for flag, path in (("--package-manifest", args.package_manifest), ("--dmg", args.dmg),
                           ("--update-zip", args.update_zip)):
            if path is not None:
                replay_base.extend((flag, str(results.safe_path(path))))
    report["replay"] = {"working_directory": str(ROOT),
                        "all_command": shlex.join(replay_base),
                        "cases": {case["id"]: {
                            "code": ("apps/desktop/e2e/granular-auxiliary.spec.ts"
                                     if case["id"] in UI_CASES else "scripts/granular_auxiliary.py"),
                            "test_name": case["id"],
                            "command": shlex.join(replay_base + ["--case-id", case["id"]])}
                            for case in cases}}
    context = {"run_id": args.run_id, "parent": parent, "catalog": catalog, "variants": variants}
    ui_cases = [case for case in cases if case["id"] in UI_CASES]
    ui_results, ui_cleanup = run_ui_cases(ui_cases, args, parent, output) if ui_cases else ({}, True)
    report["cleanup_completed"] = ui_cleanup
    for case in cases:
        report["tc_results"].append(ui_results[case["id"]] if case["id"] in UI_CASES
                                    else run_one(case, context, output))
    states = [entry["state"] for entry in report["tc_results"]]
    report["state"] = "FAIL" if "FAIL" in states else "BLOCKED" if "BLOCKED" in states else "PASS"
    report["finished_at"] = now()
    if (results.read_file(parent_path) != parent_bytes
            or results.read_file(ROOT / "tests/test_cases.json") != catalog_bytes
            or any(results.sha(results.read_file(ROOT / item["path"].removeprefix("test-code/"))) != item["sha256"]
                   for item in snapshot)):
        report["state"] = "FAIL"
        report["error"] = "Parent or fixed test source changed during auxiliary execution"
    save(output / "result.json", report)
    print(json.dumps({"state": report["state"], "run_id": args.run_id,
                      "counts": {state: states.count(state) for state in ("PASS", "FAIL", "BLOCKED")},
                      "report": str(output / "result.json")}, ensure_ascii=False))
    return 0 if report["state"] == "PASS" else 2 if report["state"] == "BLOCKED" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-report", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--with-ui", action="store_true")
    parser.add_argument("--package-manifest", type=Path)
    parser.add_argument("--dmg", type=Path)
    parser.add_argument("--update-zip", type=Path)
    args = parser.parse_args(argv)
    try:
        return execute(args)
    except (OSError, ValueError, TypeError, KeyError, results.Invalid) as error:
        print(json.dumps({"state": "FAIL", "release_eligible": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
