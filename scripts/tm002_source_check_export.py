#!/usr/bin/env python3
"""Bridge an immutable TM-002 module report to its separate result workbook."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
DEFAULT_NODE = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"


class Invalid(ValueError):
    """Input or returned evidence contradicts the frozen report."""


class Blocked(RuntimeError):
    """A required local export dependency is unavailable."""


def secure_file(path: Path) -> bytes:
    path = path.absolute()
    if ".." in path.parts or any(part.is_symlink() for part in (path, *path.parents)):
        raise Invalid("Evidence path traverses a symlink or parent component")
    with path.open("rb") as input_file:
        before = os.fstat(input_file.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise Invalid("Expected a regular evidence file")
        content = input_file.read()
        after = os.fstat(input_file.fileno())
    current = path.lstat()
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
    if identity(before) != identity(after) or identity(after) != identity(current):
        raise Invalid("Evidence changed while being read")
    return content


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_path(path: Path) -> Path:
    path = path.absolute()
    if ".." in path.parts or any(part.is_symlink() for part in (path, *path.parents)):
        raise Invalid("Export path traverses a symlink or parent component")
    return path


def write_receipt(path: Path, value: dict) -> dict:
    try:
        safe_path(path)
        with path.open("x", encoding="utf-8") as output:
            os.chmod(path, 0o600)
            json.dump(value, output, ensure_ascii=False, indent=2, sort_keys=True)
            output.write("\n")
    except (OSError, Invalid) as error:
        return {**value, "state": "FAIL", "error": f"Could not retain immutable receipt: {error}"}
    return value


def verify_returned(report_path: Path, report_sha: str, report: dict, output: Path) -> dict:
    verification_file = safe_path(output / "verification.json")
    raw = secure_file(verification_file)
    verification = json.loads(raw)
    if not isinstance(verification, dict) or verification.get("state") != "PASS" or \
            verification.get("execution_type") != "source_check" or \
            verification.get("run_id") != report["run_id"] or \
            verification.get("candidate_sha") != report["candidate_sha"] or \
            verification.get("candidate_tree") != report["candidate_tree"]:
        raise Invalid("Independent export verification has a different run, type or candidate")
    source = verification.get("source_report")
    if not isinstance(source, dict) or source.get("path") != str(report_path) or source.get("sha256") != report_sha:
        raise Invalid("Independent export verification refers to a different source report")
    workbook = verification.get("workbook")
    if not isinstance(workbook, dict) or workbook.get("path") != f"TokenMeter测试结果-{report['run_id']}.xlsx":
        raise Invalid("Workbook identity is incorrect")
    book_path = safe_path(output / workbook["path"])
    book = secure_file(book_path)
    if not book.startswith(b"PK\x03\x04") or workbook.get("bytes") != len(book) or \
            not isinstance(workbook.get("sha256"), str) or not HEX.fullmatch(workbook["sha256"]) or \
            workbook["sha256"] != digest(book):
        raise Invalid("Workbook bytes differ from independent verification")
    if verification.get("counts") != report["counts"] or verification.get("expected_ids") != report["expected_ids"]:
        raise Invalid("Workbook verification omits or changes source-check IDs/counts")
    return {"verification": {"path": str(verification_file), "sha256": digest(raw), "bytes": len(raw)},
            "workbook": {"path": str(book_path), "sha256": digest(book), "bytes": len(book)}}


def run_exporter(source: Path, target: Path) -> None:
    """The JS verifier rechecks every raw log and committed binding on re-entry."""
    node = Path(os.environ.get("TOKENMETER_WORKBOOK_NODE", str(DEFAULT_NODE))).expanduser()
    if not node.is_absolute() or not node.is_file() or not os.access(node, os.X_OK):
        raise Blocked("Bundled Node runtime is unavailable")
    exporter = ROOT / "scripts/export_tm002_source_check.mjs"
    if not exporter.is_file():
        raise Blocked("TM-002 source_check workbook exporter is unavailable")
    process = subprocess.run([str(node), str(exporter), "--report", str(source), "--output", str(target)],
                             cwd=ROOT, capture_output=True, text=True, timeout=180, check=False)
    if process.returncode:
        diagnostic = (process.stderr or process.stdout or "No exporter diagnostic").strip()[-1600:]
        if "MODULE_NOT_FOUND" in diagnostic or "Cannot find package '@oai/artifact-tool'" in diagnostic:
            raise Blocked("Bundled artifact-tool is unavailable: " + diagnostic)
        raise Invalid(f"Source-check workbook exporter exited {process.returncode}: {diagnostic}")


def export(report_path: Path, output: Path | None = None) -> dict:
    receipt = {"schema_version": 1, "scope": "tm002_source_check_excel_export", "state": "FAIL",
               "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
    receipt_path = None
    report_bytes = None
    source = None
    save = False
    try:
        source = safe_path(report_path)
        if source.name != "source-check.json":
            raise Invalid("Only the original source-check.json can be exported")
        report_bytes = secure_file(source)
        report_sha = digest(report_bytes)
        report = json.loads(report_bytes)
        if not isinstance(report, dict) or report.get("schema_version") != 1 or report.get("execution_type") != "source_check":
            raise Invalid("Report is not a TM-002 source_check original")
        run_id = report.get("run_id")
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id) or source.parent.name != run_id:
            raise Invalid("Report run ID and owned directory do not match")
        if report.get("state") not in ("PASS", "FAIL", "BLOCKED"):
            raise Invalid("Report lacks a real run state")
        target = safe_path(output or ROOT / ".local/test-results" / run_id)
        if target == source.parent or target in source.parents or source.parent in target.parents:
            raise Invalid("Workbook output must be separate from raw report evidence")
        receipt_path = source.parent / ("excel-export.json" if output is None else
            f"excel-export-{digest(str(target).encode())[:16]}.json")
        receipt.update(report_path=str(source), report_sha256=report_sha,
                       run_id=run_id, candidate_sha=report.get("candidate_sha"),
                       candidate_tree=report.get("candidate_tree"), report_state=report["state"],
                       output=str(target), receipt_path=str(receipt_path))
        save = True
        if receipt_path.exists() or receipt_path.is_symlink():
            save = False
            old = json.loads(secure_file(receipt_path))
            for field in ("scope", "report_path", "report_sha256", "run_id", "candidate_sha", "candidate_tree",
                          "report_state", "output", "receipt_path"):
                if old.get(field) != receipt.get(field):
                    raise Invalid(f"Existing receipt belongs to a different source: {field}")
            if old.get("state") == "PASS":
                details = verify_returned(source, report_sha, report, target)
                if any(old.get(key) != value for key, value in details.items()):
                    raise Invalid("Existing workbook or verification changed after export")
                run_exporter(source, target)
                details = verify_returned(source, report_sha, report, target)
                if any(old.get(key) != value for key, value in details.items()):
                    raise Invalid("Existing workbook or verification changed during source re-verification")
            elif old.get("state") not in ("FAIL", "BLOCKED") or not old.get("error"):
                raise Invalid("Existing receipt has no valid failure conclusion")
            receipt = old
        else:
            run_exporter(source, target)
            receipt.update(verify_returned(source, report_sha, report, target))
            receipt["state"] = "PASS"
    except (Blocked, FileNotFoundError, PermissionError, subprocess.TimeoutExpired) as error:
        receipt.update(state="BLOCKED", error=str(error))
    except (Invalid, OSError, ValueError, TypeError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        receipt.update(state="FAIL", error=str(error))
    finally:
        if report_bytes is not None and source is not None:
            try:
                if secure_file(source) != report_bytes:
                    raise Invalid("Raw module report changed during export")
            except (OSError, Invalid) as error:
                receipt.update(state="FAIL", error=str(error))
    if receipt.get("state") != "PASS":
        receipt.pop("workbook", None); receipt.pop("verification", None)
    return write_receipt(receipt_path, receipt) if save and receipt_path else receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = export(args.report, args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["state"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
