#!/usr/bin/env python3
"""Run the frozen TM-002 source checks and retain their individual raw results.

This is deliberately separate from product E2E.  A passing TAP/unittest line
proves the named module test ran; it does not invent the step observations that
older module tests did not emit.  Such rows remain BLOCKED for report completeness.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RELEASE = "v0.2.0-20261001T034118Z"
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
NODE = Path(os.environ.get("TOKENMETER_WORKBOOK_NODE",
    str(Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node")))
SOURCE_TYPES = frozenset({"unit", "security_unit", "governance_unit", "source_check"})


def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_git(*arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def descriptor(path: Path, run: Path) -> dict:
    data = path.read_bytes()
    return {"path": path.relative_to(run).as_posix(), "sha256": digest(data), "bytes": len(data)}


def write_new(path: Path, data: bytes) -> None:
    with path.open("xb") as output:
        os.chmod(path, 0o600)
        output.write(data)


def safe_new_run(path: Path) -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Run directory must be an absolute path without parent traversal")
    for ancestor in (path.parent, *path.parent.parents):
        if ancestor.is_symlink():
            raise ValueError("Run directory has a symlink ancestor")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists() or path.is_symlink():
        raise FileExistsError("Run directory already exists; prior evidence cannot be overwritten")
    path.mkdir(mode=0o700)
    os.chmod(path, 0o700)
    return path


# Every binding names an exact test title/function.  No prefix or name-only
# heuristics are used to allocate PASS.  The fixed IDs also expose missing
# catalog variants rather than silently shrinking the declared suite.
DESKTOP: dict[str, tuple[str, str]] = {
    "TC-TM002-LIMIT-01": ("tm002-limit-source-check.test.mjs",
        "TC-TM002-LIMIT-01 source_check records the 2001 ms production C boundary once"),
    "TC-TM002-STORE-01#KEY_UNAVAILABLE": ("source-access.test.ts",
        "TC-TM002-STORE-01#KEY_UNAVAILABLE persists a stop-reading latch"),
    "TC-TM002-STORE-01#DECRYPT_FAIL": ("source-access.test.ts",
        "TC-TM002-STORE-01#DECRYPT_FAIL rejects a formerly healthy locator without fallback"),
    "TC-TM002-STORE-01#WRITE_FAIL_KEEP_OLD": ("source-access.test.ts",
        "TC-TM002-STORE-01#WRITE_FAIL_KEEP_OLD keeps A while B is pending or atomic replacement fails"),
    "TC-TM002-ACCESS-06#PAGE_COMPLETION": ("source-helper.test.ts",
        "TC-TM002-ACCESS-06#PAGE_COMPLETION: 1201 native candidates span five ordered pages"),
    "TC-TM002-ACCESS-06#REVOKE_CURSOR": ("tm002-aux-fixed.test.ts",
        "TC-TM002-ACCESS-06#REVOKE_CURSOR rejects the old page after a real 1201-file source is revoked"),
    "TC-TM002-ACCESS-06#TREE_CHANGED": ("source-helper.test.ts",
        "TC-TM002-ACCESS-06#TREE_CHANGED: an insertion invalidates the old page before any result"),
    "TC-TM002-SECURITY-01#ABSOLUTE": ("tm002-security-ipc-fixed.test.ts",
        "TC-TM002-SECURITY-01#ABSOLUTE rejects a renderer path at the production source IPC dispatcher"),
    "TC-TM002-SECURITY-01#FILE_URL": ("tm002-security-ipc-fixed.test.ts",
        "TC-TM002-SECURITY-01#FILE_URL rejects a renderer path at the production source IPC dispatcher"),
    "TC-TM002-SECURITY-01#DOTDOT": ("tm002-security-ipc-fixed.test.ts",
        "TC-TM002-SECURITY-01#DOTDOT rejects a renderer path at the production source IPC dispatcher"),
    "TC-TM002-SECURITY-01#TOKEN": ("source-access.test.ts",
        "TC-TM002-SECURITY-01#TOKEN rejects a fabricated selection handle"),
    "TC-TM002-SECURITY-01#STALE_SELECTION": ("source-access.test.ts",
        "TC-TM002-SECURITY-01#STALE_SELECTION rejects old native picker result after identity epoch changes"),
    "TC-TM002-SECURITY-01#REVOKE_DURING_REFRESH": ("source-access.test.ts",
        "TC-TM002-SECURITY-01#REVOKE_DURING_REFRESH discards result and closes old helper"),
    "TC-TM002-SECURITY-01#SWITCH_DURING_REFRESH": ("source-access.test.ts",
        "TC-TM002-SECURITY-01#SWITCH_DURING_REFRESH discards Alice result after switching to Bob"),
}

GOVERNANCE: dict[str, tuple[str, str]] = {
    "TC-TM002-DATA-01": ("test_tm002_data_fixed.py",
        "test_tc_tm002_data_01_owned_generation_mutation_and_reset"),
    **{f"TC-TM002-CATALOG-01#{suffix}": ("test_tm002_catalog_fixed.py",
        f"test_TC_TM002_CATALOG_01_{suffix}") for suffix in
        ("VALID", "MISSING_TASK", "WRONG_RELEASE")},
    **{f"TC-TM002-EVIDENCE-01#{suffix}": ("test_tm002_evidence_fixed.py",
        f"test_TC_TM002_EVIDENCE_01_{suffix}") for suffix in
        ("COMPLETE", "MISSING_STEP", "MISSING_PICKER", "MISSING_CHOOSER_WITNESS",
         "MISSING_FS", "WRONG_PACKAGE", "FAILED_CLEANUP")},
}
BINDINGS = {**DESKTOP, **GOVERNANCE}


def catalog_entries(catalog: dict) -> dict[str, dict]:
    entries = {}
    for parent in catalog.get("cases", []):
        if not parent.get("id", "").startswith("TC-TM002-") or parent.get("type") not in SOURCE_TYPES:
            continue
        children = parent.get("variants") or [parent]
        for child in children:
            identity = child["id"]
            if identity in entries:
                raise ValueError(f"Duplicate catalog ID: {identity}")
            entries[identity] = {"parent": parent, "child": child}
    return entries


def parse_tap(stdout: str) -> tuple[dict[str, str], bool]:
    results: dict[str, str] = {}
    for line in stdout.splitlines():
        match = re.fullmatch(r"(ok|not ok)\s+\d+\s+-\s+(.+)", line)
        if match:
            if match[2] in results:
                return results, False
            results[match[2]] = "PASS" if match[1] == "ok" else "FAIL"
    summary = {key: int(value) for key, value in re.findall(
        r"^# (tests|pass|fail|cancelled|skipped|todo) (\d+)$", stdout, re.M)}
    complete = summary.get("tests") == len(results) and summary.get("pass", 0) + summary.get("fail", 0) == len(results)
    complete &= all(summary.get(key, -1) == 0 for key in ("cancelled", "skipped", "todo"))
    return results, complete


def parse_unittest(stderr: str) -> tuple[dict[str, str], bool]:
    results: dict[str, str] = {}
    for line in stderr.splitlines():
        match = re.fullmatch(r"(test_[A-Za-z0-9_]+)\s+\([^)]+\)\s+\.\.\.\s+(ok|FAIL|ERROR|skipped .+)", line)
        if match:
            if match[1] in results:
                return results, False
            results[match[1]] = "PASS" if match[2] == "ok" else "FAIL"
    count = re.search(r"^Ran (\d+) tests? in ", stderr, re.M)
    complete = bool(count and int(count[1]) == len(results) and "\nOK" in stderr and
                    "skipped=" not in stderr and all(value == "PASS" for value in results.values()))
    return results, complete


def command(run: Path, name: str, argv: list[str], cwd: Path, env: dict[str, str] | None = None) -> dict:
    relative = Path("logs") / name
    base = run / relative
    base.parent.mkdir(mode=0o700, exist_ok=True)
    stdout_file, stderr_file = base.with_suffix(".stdout.log"), base.with_suffix(".stderr.log")
    if any(path.exists() or path.is_symlink() for path in (stdout_file, stderr_file)):
        raise FileExistsError("A raw command log already exists; refusing to rerun this fixed command")
    started = utc()
    spawn_error = False
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True)
    except OSError as error:
        stdout, stderr, code, timeout, spawn_error = b"", str(error).encode(), None, False, True
    else:
        try:
            stdout, stderr = process.communicate(timeout=180)
            code = process.returncode
            timeout = False
        except subprocess.TimeoutExpired:
            # The process group was created by this command, so only this run's
            # test process and its native helper children can be terminated.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
            code = None
            timeout = True
    write_new(stdout_file, stdout)
    write_new(stderr_file, stderr)
    return {"command": argv, "cwd": str(cwd), "started_at": started, "finished_at": utc(),
            "exit_code": code, "timeout": timeout, "spawn_error": spawn_error,
            "stdout": descriptor(stdout_file, run), "stderr": descriptor(stderr_file, run),
            "stdout_text": stdout.decode("utf-8", errors="replace"),
            "stderr_text": stderr.decode("utf-8", errors="replace")}


def decode_name(token: str) -> str:
    return base64.b64decode(token + "=" * (-len(token) % 4), validate=True).decode("utf-8")


def decoded_item(line: str) -> dict | None:
    item = re.fullmatch(r"ITEM ([A-Za-z0-9+/=]+) (\d+) (\d+) (\d+) ([a-f0-9]{64}) (-)", line)
    if not item:
        return None
    try:
        name = decode_name(item[1])
    except (ValueError, UnicodeDecodeError):
        return None
    return {"name": name, "bytes": int(item[2]), "mtime_s": int(item[3]), "mtime_ns": int(item[4])}


def limit_observation(raw: dict) -> tuple[bool, list[str], list[str], dict]:
    markers = [line.removeprefix("# TM002_LIMIT_ACTUAL ") for line in raw["stdout_text"].splitlines()
               if line.startswith("# TM002_LIMIT_ACTUAL ")]
    default_cleanup = {"mode": "memory_only", "state": "BLOCKED", "evidence": raw["stdout"]["path"]}
    if len(markers) != 1:
        return False, [], ["Missing or duplicate fixed C actual marker"], default_cleanup
    try:
        marker = json.loads(markers[0])
    except json.JSONDecodeError:
        return False, [], ["Malformed fixed C actual marker"], default_cleanup
    if not isinstance(marker, dict):
        return False, [], ["Fixed C actual marker is not an object"], default_cleanup
    lines = marker.get("stdout_lines", [])
    if not isinstance(lines, list) or any(not isinstance(line, str) for line in lines):
        return False, [], ["Fixed C stdout lines have an invalid shape"], default_cleanup
    item = decoded_item(lines[3]) if len(lines) == 5 else None
    audit_name = None
    metadata_name = None
    if len(lines) == 5:
        for operation, value in (("enumerated", lines[0]), ("metadata", lines[1])):
            match = re.fullmatch(r"AUDIT " + operation + r" candidate ([A-Za-z0-9+/=]+) \d+ 101", value)
            if match:
                try:
                    decoded = decode_name(match[1])
                    if operation == "enumerated": audit_name = decoded
                    else: metadata_name = decoded
                except (ValueError, UnicodeDecodeError): pass
    expected_counts = "HARNESS clock=3 open=2 openat=0 read=0 fstat=4 dup=2 close=4 fdopendir=1 readdir=1 fstatat=1 closedir=1 unexpected=0 names=2"
    harness = ROOT / "apps/desktop/tests/tm002-limit-harness.c"
    production = ROOT / "apps/desktop/native/source-helper.c"
    correct = (marker.get("case_id") == "TC-TM002-LIMIT-01" and
        marker.get("input_sha256") == digest(harness.read_bytes()) and
        marker.get("algorithm_sha256") == digest(production.read_bytes()) and
        marker.get("exit_code") == 0 and marker.get("scratch_removed") is True and
        audit_name == "A1.jsonl" and metadata_name == "A1.jsonl" and
        item is not None and item["name"] == "A1.jsonl" and item["bytes"] == 25 and
        item["mtime_s"] == 1700000000 and item["mtime_ns"] == 123456789 and
        lines[2] == "PREVIEW timeout 1 1" and lines[4] == "END" and
        marker.get("stderr") == expected_counts)
    actual = ([f"Decoded candidate: {item['name']}; bytes={item['bytes']}; mtime={item['mtime_s']}.{item['mtime_ns']}" ]
              if item else []) + [f"C stdout: {line}" for line in lines] + [f"C stderr: {marker.get('stderr')}"]
    steps = [
        "A1.jsonl enumerated with safe metadata; read/openat=0 and unexpected=0",
        "At 2001 ms preview returned timeout, incomplete=1, one A1.jsonl item of 25 bytes",
        "Harness process exited 0; fixed adapter counters, process and scratch cleanup were recorded in TAP",
    ] if correct else ["C harness output or counters differed from frozen assertions"]
    cleanup = {"mode": "memory_only", "state": "PASS" if correct else "BLOCKED",
               "evidence": raw["stdout"]["path"] + "; marker scratch_removed=true and exit_code=0"}
    return correct, actual, steps, cleanup


def run_suite(run_id: str, output: Path, catalog_path: Path) -> dict:
    if not RUN_ID.fullmatch(run_id) or output.name != run_id:
        raise ValueError("Invalid run ID or output directory name")
    if NODE.is_symlink() or not NODE.is_absolute() or not NODE.is_file() or not os.access(NODE, os.X_OK):
        raise ValueError("A real absolute executable Node runtime is required")
    if catalog_path != ROOT / "tests/test_cases.json":
        raise ValueError("Only the candidate's committed tests/test_cases.json is accepted")
    if read_git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Candidate worktree is not clean; commit and freeze the source_check runner before testing")
    candidate = read_git("rev-parse", "HEAD")
    tree = read_git("rev-parse", "HEAD^{tree}")
    if not re.fullmatch(r"[0-9a-f]{40}", candidate + "") or not re.fullmatch(r"[0-9a-f]{40}", tree + ""):
        raise ValueError("Invalid Git candidate identity")
    catalog_bytes = catalog_path.read_bytes()
    catalog = json.loads(catalog_bytes)
    if catalog.get("release_id") != RELEASE:
        raise ValueError("Wrong release catalog")
    entries = catalog_entries(catalog)
    unexpected = set(entries) - set(BINDINGS)
    if unexpected:
        raise ValueError("A fixed source_check ID has no runner binding: " + ", ".join(sorted(unexpected)))
    run = safe_new_run(output)
    write_new(run / "owner.json", (json.dumps({"run_id": run_id, "execution_type": "source_check",
        "candidate_sha": candidate, "candidate_tree": tree}, sort_keys=True) + "\n").encode())
    started = utc()
    commands: list[dict] = []
    case_tests: dict[str, tuple[str, bool, dict]] = {}
    for filename in sorted({file for file, _ in DESKTOP.values()}):
        argv = [str(NODE), "--experimental-strip-types", "--test", "--test-reporter=tap", f"tests/{filename}"]
        result = command(run, "node-" + filename.removesuffix(".test.ts"), argv, ROOT / "apps/desktop")
        commands.append(result)
        tests, complete = parse_tap(result["stdout_text"])
        full = complete and result["exit_code"] == 0 and not result["timeout"]
        for identity, (file, title) in DESKTOP.items():
            if file == filename:
                case_tests[identity] = (tests.get(title, "BLOCKED"), full, result)
    for filename in sorted({file for file, _ in GOVERNANCE.values()}):
        argv = [sys.executable, "-m", "unittest", "discover", "-s", "tests/governance", "-p", filename, "-v"]
        env = os.environ.copy(); env["PYTHONPATH"] = str(ROOT)
        env.pop("TM002_AUX_EVIDENCE_DIR", None)
        result = command(run, "python-" + filename.removesuffix(".py"), argv, ROOT, env)
        commands.append(result)
        tests, complete = parse_unittest(result["stderr_text"])
        full = complete and result["exit_code"] == 0 and not result["timeout"]
        for identity, (file, method) in GOVERNANCE.items():
            if file == filename:
                case_tests[identity] = (tests.get(method, "BLOCKED"), full, result)

    results = []
    for identity, (filename, test_name) in BINDINGS.items():
        suite = case_tests.get(identity)
        test_state, complete, raw = suite if suite else ("BLOCKED", False, None)
        entry = entries.get(identity)
        parent = entry["parent"] if entry else None
        child = entry["child"] if entry else None
        source = (ROOT / "apps/desktop/tests" / filename) if identity in DESKTOP else (ROOT / "tests/governance" / filename)
        path = source.relative_to(ROOT).as_posix()
        code_sha = digest(source.read_bytes())
        extra_sources = []
        if identity == "TC-TM002-LIMIT-01":
            for relative in ("apps/desktop/tests/tm002-limit-harness.c",
                             "apps/desktop/native/source-helper.c"):
                extra_sources.append({"file": relative, "sha256": digest((ROOT / relative).read_bytes())})
        logs = [raw["stdout"], raw["stderr"]] if raw else []
        actual: list[str] = []
        steps = []
        cleanup = {"mode": "memory_only" if identity == "TC-TM002-LIMIT-01" else "owned_root",
                   "state": "BLOCKED", "evidence": "No independent post-cleanup ownership witness in raw test output"}
        reason = "Fixed module test has no independently recorded step actuals and cleanup witness"
        state = "BLOCKED"
        if raw:
            actual.append(f"Exact test {test_name}: {test_state}; command exit={raw['exit_code']}; per-test raw line in {raw['stdout']['path'] if identity in DESKTOP else raw['stderr']['path']}")
        if test_state == "FAIL" or (raw and raw["exit_code"] not in (0, None)):
            state, reason = "FAIL", "Fixed module test or its command failed; see immutable raw output"
        elif not complete or test_state != "PASS":
            state, reason = "BLOCKED", "Exact per-test result, zero-skip summary, or command completion is missing"
        elif not entry:
            state, reason = "BLOCKED", "Frozen TC/variant is absent from this candidate's catalog"
        elif identity == "TC-TM002-LIMIT-01":
            good, facts, step_actuals, cleanup = limit_observation(raw)
            actual.extend(facts)
            if good:
                state, reason = "PASS", "Direct production C algorithm harness matched frozen stdout, counters and process cleanup"
                for design, observation in zip(parent["steps"], step_actuals, strict=True):
                    steps.append({"number": design["step"], "action": design["action"],
                        "expected": design["expected"], "actual": observation, "state": "PASS",
                        "evidence": raw["stdout"]["path"]})
            else:
                state, reason = "BLOCKED", "Single-run C marker or exact output is missing or inconsistent"
        elif identity in {f"TC-TM002-SECURITY-01#{item}" for item in ("ABSOLUTE", "FILE_URL", "DOTDOT")}:
            marker = re.search(r"^# TM002_IPC_EVIDENCE case=" + re.escape(identity) +
                r" code=invalid_selection picker=0 helper=0 source_audit=0 records=0 a_sha256=([0-9a-f]{64}) b_sha256=([0-9a-f]{64})$",
                raw["stdout_text"], re.M)
            if marker:
                actual.append(f"IPC marker: invalid_selection; picker/helper/source_audit/records=0; A sha256={marker[1]}; B sha256={marker[2]}")
                reason = "Raw IPC assertions passed, but no independent owned-root cleanup witness or per-step event output was emitted"
            else:
                state, reason = "BLOCKED", "Exact IPC actual marker is absent or malformed"
        if entry:
            design_steps = (child.get("steps") or parent.get("steps") or [])
            if not steps:
                steps = [{"number": step["step"], "action": step["action"], "expected": step["expected"],
                    "actual": "No step-specific runtime event in fixed test output", "state": "BLOCKED",
                    "evidence": logs[0]["path"] if logs else ""} for step in design_steps]
        designed_expected = (child.get("expected") or "；".join(step.get("expected", "") for step in
            (child.get("steps") or parent.get("steps") or []))) if entry else "Missing catalog expected"
        result = {"id": identity, "parent_id": identity.split("#")[0], "test_state": test_state,
            "state": state, "reason": reason, "input": child.get("input", "") if child else "Missing catalog input",
            "expected": designed_expected,
            "actual_assertions": actual, "steps": steps,
            "binding": {"file": path, "test_name": test_name, "code_sha256": code_sha,
                "command": raw["command"] if raw else [], "sources": extra_sources}, "logs": logs,
            "data_reset": (child.get("reset") or parent.get("reset") or parent.get("db_operations", {}).get("reset", "")) if entry else "Catalog missing",
            "cleanup": cleanup}
        results.append(result)
    if read_git("rev-parse", "HEAD") != candidate or read_git("rev-parse", "HEAD^{tree}") != tree or \
            catalog_path.read_bytes() != catalog_bytes or read_git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("Candidate, catalog, or worktree changed during source_check; raw logs retained")
    counts = {value: sum(row["state"] == value for row in results) for value in ("PASS", "FAIL", "BLOCKED")}
    test_counts = {value: sum(row["test_state"] == value for row in results) for value in ("PASS", "FAIL", "BLOCKED")}
    state = "FAIL" if counts["FAIL"] else "BLOCKED" if counts["BLOCKED"] else "PASS"
    report = {"schema_version": 1, "execution_type": "source_check", "run_id": run_id,
        "release_id": RELEASE, "candidate_sha": candidate, "candidate_tree": tree,
        "catalog": {"path": "tests/test_cases.json", "sha256": digest(catalog_bytes)},
        "runner": {"path": "scripts/tm002_source_check.py", "sha256": digest(Path(__file__).read_bytes())},
        "environment": {"os": platform.platform(), "architecture": platform.machine(),
            "node": str(NODE), "python": sys.executable, "started_at": started, "finished_at": utc()},
        "expected_ids": list(BINDINGS), "results": results, "counts": counts,
        "test_counts": test_counts, "state": state,
        "product_e2e_state": "NOT_RUN", "release_eligible": False,
        "commands": [{key: value for key, value in item.items() if key not in ("stdout_text", "stderr_text")}
            for item in commands]}
    write_new(run / "source-check.json", (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path)
    values = parser.parse_args(argv)
    output = values.output or ROOT / ".local/source-check" / values.run_id
    try:
        report = run_suite(values.run_id, output, ROOT / "tests/test_cases.json")
        from tm002_source_check_export import export
        receipt = export(output / "source-check.json")
        print(json.dumps({"run_id": report["run_id"], "state": report["state"],
            "counts": report["counts"], "test_counts": report["test_counts"],
            "report": str(output / "source-check.json"),
            "excel_export_state": receipt["state"], "excel_receipt": receipt.get("receipt_path")}, sort_keys=True))
        return 0 if report["state"] == "PASS" and receipt["state"] == "PASS" else 1
    except Exception as error:
        print(json.dumps({"state": "FAIL", "error": str(error), "run_id": values.run_id}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
