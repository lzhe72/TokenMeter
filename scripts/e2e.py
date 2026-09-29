#!/usr/bin/env python3
"""Product E2E adapter bootstrap: record BLOCKED, never fabricate execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def git_value(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    except OSError:
        return None


def record_blocked(root: Path, phase: str) -> Path:
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex
    output_root = root / ".local" / "e2e"
    # Never follow an externally supplied artifact-directory symlink.
    for directory in (root / ".local", output_root):
        if directory.is_symlink():
            raise ValueError(f"Refusing symlink artifact directory: {directory}")
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
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
            "datasets": digest(root / "tests/datasets.json"),
        },
        "runner_implemented": False,
        "executed_cases": 0,
        "passed_cases": 0,
        "suites": [],
        "artifacts": [],
        "blockers": [
            "真实 SwiftUI App、FastAPI 服务端及原生产品 E2E 测试目标尚未建立。",
            "自动构建、隔离账号初始化、GUI 驱动和原生结果校验尚未接通。",
            "当前运行只记录阻塞；没有执行任何产品用例，不能获得发布资格。",
        ],
    }
    destination = output / "result.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("iteration", "release"), required=True)
    args = parser.parse_args(argv)
    try:
        path = record_blocked(root, args.phase)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"state": "BLOCKED", "reason": str(exc), "release_eligible": False}, ensure_ascii=False))
        return 2
    print(json.dumps({"state": "BLOCKED", "report": str(path), "release_eligible": False}, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
