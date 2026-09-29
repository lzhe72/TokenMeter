#!/usr/bin/env python3
"""Run real native product E2E, retaining failures and missing-environment evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_e2e


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
        print(json.dumps({"state": "BLOCKED", "reason": str(exc), "release_eligible": False}, ensure_ascii=False))
        return 2
    report = json.loads(path.read_text(encoding="utf-8"))
    try:
        native_e2e.execute(root, path.parent, report)
        report["blockers"] = []
        if args.phase == "release":
            raise native_e2e.Blocked("Final signed package, supported platform/MySQL matrix, protected CI and passport issuer are not ready")
    except native_e2e.EvidenceError as exc:
        report["state"], report["errors"] = "FAIL", [str(exc)]
    except (native_e2e.Blocked, OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as exc:
        report["state"], report["blockers"] = "BLOCKED", [str(exc)]
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["release_eligible"] = False
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"state": report["state"], "report": str(path), "release_eligible": False}, ensure_ascii=False))
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[report["state"]]


if __name__ == "__main__":
    raise SystemExit(main())
