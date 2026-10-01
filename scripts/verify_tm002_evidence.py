#!/usr/bin/env python3
"""Read-only structural audit of TM-002's original per-case product evidence.

This consumer checks independently saved files and cross-file identities. It
never launches an App and never grants product or release eligibility. A PASS
means only that the supplied report has the required evidence structure; real
product assertions and package provenance remain separate gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RELEASE = "v0.2.0-20261001T034118Z"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
OPERATIONS = {"picker_open", "picker_result", "root_open", "enumerate", "metadata",
              "open_read", "reject", "cancel", "preview_complete"}
ACCESS = {"root_open", "enumerate", "metadata", "open_read"}
CHOOSER_CONFIRM_BUTTONS = {"Choose", "Open", "Select", "选择", "打开"}
CHOOSER_CANCEL_BUTTONS = {"Cancel", "取消"}


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def checked_file(output_root: Path, item: object, label: str, errors: list[str]) -> Path | None:
    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
        errors.append(label + " descriptor is missing")
        return None
    relative = Path(item["path"])
    if (relative.is_absolute() or not relative.parts or
            any(part in (".", "..") for part in relative.parts)):
        errors.append(label + " descriptor path is unsafe")
        return None
    root = output_root.resolve()
    target = root / relative
    if (any(part.is_symlink() for part in (target, *target.parents) if part != root and root in part.parents)
            or not target.is_file() or not target.resolve().is_relative_to(root)):
        errors.append(label + " file is missing, linked or outside the owned report")
        return None
    if (not isinstance(item.get("sha256"), str) or not HEX64.fullmatch(item["sha256"])
            or not isinstance(item.get("bytes"), int) or item["bytes"] < 0
            or sha256(target) != item["sha256"] or target.stat().st_size != item["bytes"]):
        errors.append(label + " digest or byte count differs from the original")
        return None
    return target


def read_jsonl(path: Path, label: str, errors: list[str]) -> list[dict]:
    try:
        data = path.read_text(encoding="utf-8")
        if not data or not data.endswith("\n"):
            raise ValueError("empty or incomplete")
        rows = [json.loads(line) for line in data.splitlines()]
        if any(not isinstance(row, dict) for row in rows):
            raise ValueError("nonobject event")
        return rows
    except (OSError, UnicodeError, ValueError, TypeError):
        errors.append(label + " JSONL is malformed")
        return []


def verify_case(case: dict, case_result: dict, output_root: Path,
                package_manifest: Path, *, run_id: str | None = None) -> dict:
    """Check one attempted leaf TC. Call after one_case has completed cleanup.

    The caller may invoke this immediately before returning from one_case, or
    after execute has written result.json. Its report-level package hash check
    is performed by verify_report; this function validates the manifest identity
    and every per-case original descriptor without mutating the report.
    """
    errors: list[str] = []
    identity = case.get("id")
    if (not isinstance(identity, str) or not isinstance(case_result, dict)
            or case_result.get("case_id") != identity):
        return {"case_id": identity, "state": "FAIL", "release_eligible": False,
                "errors": ["case identity differs from the baselined TC"]}
    if case_result.get("state") != "PASS":
        errors.append("case did not finish with a product assertion PASS")
    cleanup = case_result.get("cleanup")
    if not isinstance(cleanup, dict) or cleanup.get("completed") is not True:
        errors.append("cleanup.completed is not true")
    if case_result.get("task_ids") != case.get("task_ids") or case_result.get("ac_ids") != case.get("ac_ids"):
        errors.append("case TASK/AC ownership differs from the catalog")
    try:
        package = json.loads(package_manifest.read_text(encoding="utf-8"))
        if (not isinstance(package, dict) or package.get("release_id") != RELEASE
                or not HEX40.fullmatch(str(package.get("candidate_sha", "")))
                or not HEX40.fullmatch(str(package.get("candidate_tree", "")))):
            errors.append("package manifest release or candidate identity is malformed")
    except (OSError, ValueError, UnicodeError):
        errors.append("package manifest is unreadable")
    evidence = case_result.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}
        errors.append("case evidence map is missing")

    expected_numbers = [row.get("step") for row in case.get("steps", [])]
    observed = case_result.get("step_results")
    if not isinstance(observed, list) or [row.get("step") for row in observed if isinstance(row, dict)] != expected_numbers:
        errors.append("step results do not match the baselined step sequence")
        observed = []
    events_path = checked_file(output_root, evidence.get("events"), "step events", errors)
    events = read_jsonl(events_path, "step events", errors) if events_path else []
    if [row.get("step") for row in events] != expected_numbers:
        errors.append("step events do not match the baselined step sequence")
    if observed != events:
        errors.append("step results differ from the original step events")
    for row in events:
        if (row.get("case_id") != identity or (run_id is not None and row.get("run_id") != run_id)
                or row.get("passed") is not True or row.get("expected") != row.get("actual")
                or not all(key in row for key in ("action", "source", "timestamp", "evidence"))):
            errors.append("step identity, comparison or observation is incomplete")
            break

    screenshot_items = evidence.get("screenshots")
    screenshots: set[str] = set()
    if not isinstance(screenshot_items, list) or not screenshot_items:
        errors.append("screenshot descriptors are missing")
    else:
        for item in screenshot_items:
            if checked_file(output_root, item, "screenshot", errors) is not None:
                screenshots.add(item["path"])
    case_folder = identity.replace("#", "--")
    for row in events:
        screenshot = row.get("evidence", {}).get("screenshot") if isinstance(row.get("evidence"), dict) else None
        if screenshot is not None and (not isinstance(screenshot, str)
                                      or (Path(case_folder) / screenshot).as_posix() not in screenshots):
            errors.append("step screenshot is not bound to an original descriptor")
            break
    if not any(isinstance(row.get("evidence"), dict) and row["evidence"].get("screenshot") for row in events):
        errors.append("no step screenshot observation was preserved")

    playwright_path = checked_file(output_root, evidence.get("playwright"), "Playwright", errors)
    if playwright_path:
        try:
            playwright = json.loads(playwright_path.read_text(encoding="utf-8"))
            specs = [spec for suite in playwright.get("suites", []) for spec in suite.get("specs", [])]
            tests = [test for spec in specs for test in spec.get("tests", [])]
            attempts = [attempt for test in tests for attempt in test.get("results", [])]
            if (len(specs) != 1 or specs[0].get("title") != identity or len(tests) != 1
                    or len(attempts) != 1 or attempts[0].get("status") != "passed"
                    or attempts[0].get("retry", 0) != 0):
                errors.append("Playwright original is not one successful fixed TC attempt")
        except (OSError, ValueError, TypeError, KeyError):
            errors.append("Playwright original is malformed")
    trace_path = checked_file(output_root, evidence.get("trace"), "trace", errors)
    if trace_path:
        try:
            with zipfile.ZipFile(trace_path) as trace:
                if not trace.namelist() or trace.testzip() is not None:
                    errors.append("trace ZIP has no intact original entries")
        except (OSError, zipfile.BadZipFile):
            errors.append("trace ZIP is malformed")

    expected_path = checked_file(output_root, evidence.get("source_expected"), "source oracle", errors)
    tool = None
    if expected_path:
        try:
            source_expected = json.loads(expected_path.read_text(encoding="utf-8"))
            tool = source_expected.get("tool")
            if (source_expected.get("case_id") != identity or tool not in ("codex", "claude_code")
                    or not HEX64.fullmatch(str(source_expected.get("private_oracle_sha256", "")))):
                errors.append("source oracle identity or digest is malformed")
        except (OSError, ValueError, TypeError):
            errors.append("source oracle is malformed")
    picker_items = evidence.get("picker_events")
    if not isinstance(picker_items, list) or not picker_items:
        errors.append("native picker event is missing")
    else:
        for index, item in enumerate(picker_items, 1):
            path = checked_file(output_root, item, f"native picker {index}", errors)
            if not path:
                continue
            try:
                event = json.loads(path.read_text(encoding="utf-8"))
                operation = event.get("operation")
                valid = (event.get("real_ax_action") is True and operation in ("select", "cancel")
                         and isinstance(event.get("owner_pid"), int) and event["owner_pid"] > 0
                         and event.get("panel_role") in ("AXSheet", "AXDialog")
                         and event.get("chooser_confirm_button") in CHOOSER_CONFIRM_BUTTONS
                         and isinstance(event.get("native_button"), str) and event["native_button"]
                         and isinstance(event.get("completed_at"), str) and event["completed_at"])
                if operation == "select":
                    valid = valid and event["native_button"] in CHOOSER_CONFIRM_BUTTONS
                    valid = valid and event.get("selection_label") in ("A", "B") and bool(
                        HEX64.fullmatch(str(event.get("selection_path_sha256", ""))))
                else:
                    valid = valid and event["native_button"] in CHOOSER_CANCEL_BUTTONS
                if identity == "TC-TM002-SELECT-01":
                    valid = valid and operation == "select" and event.get("selection_label") == "A"
                if not valid:
                    errors.append("native picker event lacks a real owned AX action")
            except (OSError, ValueError, TypeError):
                errors.append("native picker event is malformed")

    audit_path = checked_file(output_root, evidence.get("source_access_audit"), "source audit", errors)
    audit = read_jsonl(audit_path, "source audit", errors) if audit_path else []
    if not audit:
        errors.append("source audit has no independent filesystem observation")
    for number, event in enumerate(audit, 1):
        if (event.get("schema_version") != 1 or event.get("sequence") != number
                or event.get("operation") not in OPERATIONS
                or event.get("decision") not in ("allowed", "denied")
                or event.get("tool") != tool or not isinstance(event.get("generation"), int)
                or event["generation"] < 0):
            errors.append("source audit order, ownership or event schema differs")
            break
        root_digest = event.get("root_digest")
        if (event["operation"] in ACCESS and event["decision"] == "allowed"
                and not HEX64.fullmatch(str(root_digest))):
            errors.append("source audit allowed access has no bound root digest")
            break
        if event["operation"] == "open_read" and event["decision"] == "allowed":
            errors.append("source audit observed a body read during metadata-only permission testing")
            break
    if audit and not any(event.get("operation") == "picker_open" for event in audit):
        errors.append("source audit has no picker open operation")
    if audit and not any(event.get("operation") == "picker_result" for event in audit):
        errors.append("source audit has no picker result operation")
    return {"case_id": identity, "state": "PASS" if not errors else "FAIL",
            "release_eligible": False, "scope": "tm002_evidence_structure_only", "errors": errors}


def _catalog_cases() -> tuple[dict[str, dict], dict[str, list[str]]]:
    catalog = json.loads((ROOT / "tests/test_cases.json").read_text(encoding="utf-8"))
    cases: dict[str, dict] = {}
    parents: dict[str, list[str]] = {}
    for row in catalog["cases"]:
        if row.get("feature_id") != "TM-002" or row.get("type") != "product_e2e":
            continue
        cases[row["id"]] = row
        children = row.get("variants", [])
        if children:
            parents[row["id"]] = [item["id"] for item in children]
        for child in children:
            cases[child["id"]] = {**row, "id": child["id"], "steps": child["steps"]}
    return cases, parents


def verify_report(report_path: Path, *, package_manifest: Path) -> dict:
    """Validate report/package identity and each expected leaf's stored originals."""
    errors: list[str] = []
    case_reports: list[dict] = []
    try:
        if report_path.is_symlink() or package_manifest.is_symlink():
            raise ValueError("linked input")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        package = json.loads(package_manifest.read_text(encoding="utf-8"))
        if not isinstance(report, dict) or not isinstance(package, dict):
            raise ValueError("nonobject input")
    except (OSError, ValueError, UnicodeError, TypeError) as error:
        return {"state": "FAIL", "scope": "tm002_evidence_structure_only", "release_eligible": False,
                "errors": ["report or package manifest is unreadable: " + type(error).__name__], "cases": []}
    if (report.get("schema_version") != 1 or not str(report.get("scope", "")).startswith("tm002_granular_")
            or report.get("release_id") != RELEASE or package.get("release_id") != RELEASE
            or report.get("release_eligible") is not False):
        errors.append("report/package scope or release identity differs")
    report_package = report.get("package")
    if not isinstance(report_package, dict) or report_package.get("manifest_sha256") != sha256(package_manifest):
        errors.append("package manifest SHA256 differs from its actual original")
    if (report.get("source_commit") != package.get("candidate_sha")
            or report.get("candidate_tree") != package.get("candidate_tree")
            or report.get("working_tree_dirty") != package.get("working_tree_dirty")):
        errors.append("package manifest candidate SHA/tree differs from the report")
    if report.get("state") != "PASS" or report.get("cleanup_completed") is not True:
        errors.append("report state or overall cleanup is incomplete")
    expected = report.get("expected_cases")
    results = report.get("tc_results")
    if (not isinstance(expected, list) or not expected or any(not isinstance(item, str) for item in expected)
            or len(expected) != len(set(expected))
            or not isinstance(results, list) or len(results) != len(expected)
            or [row.get("case_id") for row in results if isinstance(row, dict)] != expected):
        errors.append("expected cases and original result rows differ")
        results = []
    catalog, derived_parents = _catalog_cases()
    by_id = {row["case_id"]: row for row in results if isinstance(row, dict) and isinstance(row.get("case_id"), str)}
    for identity in expected if isinstance(expected, list) else []:
        case = catalog.get(identity)
        row = by_id.get(identity)
        if case is None or row is None:
            errors.append("unknown or missing fixed TM-002 case: " + str(identity))
            continue
        if identity in derived_parents:
            children = derived_parents[identity]
            cleanup = row.get("cleanup")
            if (row.get("state") != "PASS" or not isinstance(cleanup, dict)
                    or cleanup.get("completed") is not True
                    or any(by_id.get(child, {}).get("state") != "PASS" for child in children)):
                errors.append("derived parent lacks every fixed child original: " + identity)
            continue
        result = verify_case(case, row, report_path.parent, package_manifest, run_id=report.get("run_id"))
        case_reports.append(result)
        errors.extend(identity + ": " + item for item in result["errors"])
    return {"state": "PASS" if not errors else "FAIL", "scope": "tm002_evidence_structure_only",
            "release_eligible": False, "product_e2e_verified": False,
            "errors": errors, "cases": case_reports}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--package-manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    result = verify_report(args.report, package_manifest=args.package_manifest)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["state"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
