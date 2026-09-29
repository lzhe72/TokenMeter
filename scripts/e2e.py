#!/usr/bin/env python3
"""Run real native product E2E, retaining failures and missing-environment evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_e2e


def safe_diagnostic(message: object) -> str:
    value = str(message)
    value = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9_.~+/-]+=*", "Bearer <redacted>", value)
    return re.sub(r"(?i)(\b(?:password|passwd|secret|private_key|access_token|authorization|TM_TEST_UPDATE_CONTROL_TOKEN)\b\s*['\"]?\s*[:=]\s*['\"]?)[^\s,'\"}\]]+",
                  r"\1<redacted>", value)


def exception_message(error: Exception) -> str:
    # subprocess exception strings include command arguments, which may contain
    # the isolated keychain password. Only expose the operation's exit/timeout.
    if isinstance(error, subprocess.TimeoutExpired):
        return f"Subprocess timed out after {error.timeout} seconds"
    if isinstance(error, subprocess.CalledProcessError):
        return f"Subprocess failed with exit code {error.returncode}"
    return safe_diagnostic(error)


def print_result(report: dict, path: Path) -> None:
    cases = [{key: safe_diagnostic(suite[key]) if key == "error" else suite[key]
              for key in ("case_id", "state", "exit_code", "error") if key in suite}
             for suite in report.get("suites", [])]
    for case, suite in zip(cases, report.get("suites", [])):
        case["native_failures"] = [safe_diagnostic(message) for message in suite.get("native_failures", [])[:3]]
    print(json.dumps({"event": "e2e_result", "state": report["state"], "report": str(path),
                      "executed_cases": report["executed_cases"], "passed_cases": report["passed_cases"],
                      "cases": cases, "errors": report.get("errors", []), "blockers": report.get("blockers", []),
                      "cleanup_errors": report.get("cleanup_errors", []), "release_eligible": False},
                     ensure_ascii=False), flush=True)


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def git_value(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    except OSError:
        return None


def record_blocked(root: Path, phase: str, run_id: str | None = None) -> Path:
    now = datetime.now(timezone.utc)
    run_id = run_id or now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex
    output = native_e2e.new_run_directory(root, run_id)
    release_id = None
    try:
        current = json.loads((root / "releases/current.json").read_text(encoding="utf-8"))
        if isinstance(current, dict) and isinstance(current.get("release_id"), str):
            release_id = current["release_id"]
    except (OSError, ValueError, RuntimeError):
        pass  # The diagnostic remains BLOCKED when the release index is absent.
    report = {
        "schema_version": 1,
        "run_id": run_id,
        "release_id": release_id,
        "phase": phase,
        "state": "BLOCKED",
        "release_eligible": False,
        "started_at": now.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": git_value(root, "rev-parse", "HEAD"),
        "working_tree_dirty": git_value(root, "status", "--porcelain") != "",
        "platform": {"system": platform.system(), "release": platform.release(), "architecture": platform.machine()},
        "manifest_sha256": {
            "documents": digest(root / "docs/catalog.json"),
            "current_release": digest(root / "releases/current.json"),
            "features": digest(root / "tests/feature_matrix.json"),
            "acceptance": digest(root / "tests/acceptance.json"),
            "datasets": digest(root / "tests/datasets.json"),
        },
        "runner_implemented": False,
        "executed_cases": 0,
        "passed_cases": 0,
        "suites": [],
        "artifacts": [],
        "cleanup_completed": False,
        "blockers": ["Native execution has not started."],
    }
    destination = output / "result.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("iteration", "release"), required=True)
    parser.add_argument("--run-id", help="Invocation nonce allocated by the parent gate")
    args = parser.parse_args(argv)
    try:
        path = record_blocked(root, args.phase, args.run_id)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"state": "BLOCKED", "reason": exception_message(exc), "release_eligible": False}, ensure_ascii=False))
        return 2
    report = json.loads(path.read_text(encoding="utf-8"))
    try:
        native_e2e.execute(root, path.parent, report)
        report["blockers"] = []
        if args.phase == "release":
            raise native_e2e.Blocked("Final signed package, supported platform/MySQL matrix, protected CI and passport issuer are not ready")
    except native_e2e.EvidenceError as exc:
        report["state"], report["errors"] = "FAIL", [exception_message(exc)]
        report["blockers"] = []
    except (native_e2e.Blocked, OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as exc:
        # A later missing environment must not erase already observed failures.
        failures = [f"{suite['case_id']}: {suite['error']}" for suite in report.get("suites", [])
                    if suite.get("state") == "FAIL" and suite.get("error")]
        report["state"] = "FAIL" if failures else "BLOCKED"
        report["blockers"] = [exception_message(exc)]
        if failures:
            report["errors"] = failures
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["release_eligible"] = False
        for field in ("errors", "blockers", "cleanup_errors"):
            if field in report:
                report[field] = [safe_diagnostic(message) for message in report[field]]
        for suite in report.get("suites", []):
            if "error" in suite:
                suite["error"] = safe_diagnostic(suite["error"])
            if "native_failures" in suite:
                suite["native_failures"] = [safe_diagnostic(message)[:1000] for message in suite["native_failures"][:3]]
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print_result(report, path)
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[report["state"]]


if __name__ == "__main__":
    raise SystemExit(main())
