#!/usr/bin/env python3
"""Export a TM-002 product run without changing its original result.

The Node exporter verifies the report and every referenced evidence file, then
round-trips its XLSX. This bridge writes an immutable, separate receipt. A
failed export never upgrades a product FAIL or BLOCKED result.
"""
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


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NODE = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
RUN_ID = re.compile(r"local-[0-9a-f]{32}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
RECEIPT = "tm002-product-excel-export.json"
VERIFICATION = "tm002-product-verification.json"
SOURCE_MANIFEST = "tm002-product-source-digests.json"


class Blocked(RuntimeError):
    """An export runtime or source is unavailable."""


class Invalid(RuntimeError):
    """An original or generated artifact contradicts the export contract."""


def safe_path(path: Path) -> Path:
    absolute = path.absolute()
    if ".." in absolute.parts or any(part.is_symlink() for part in (absolute, *absolute.parents)):
        raise Invalid("Export path contains a symlink or parent traversal")
    return absolute


def read_file(path: Path) -> bytes:
    safe_path(path)
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise Invalid("Expected a regular export input or output")
        data = stream.read()
        after = os.fstat(stream.fileno())
    current = path.lstat()
    identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
    if identity(before) != identity(after) or identity(after) != identity(current):
        raise Invalid("Export input or output changed while reading")
    return data


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def runtime() -> Path:
    node = Path(os.environ.get("TOKENMETER_WORKBOOK_NODE", str(DEFAULT_NODE))).expanduser()
    if not node.is_absolute() or not node.is_file() or not os.access(node, os.X_OK):
        raise Blocked("Bundled Node runtime is unavailable")
    if not (ROOT / ".local/workbook/node_modules/@oai/artifact-tool").exists():
        raise Blocked("Bundled workbook dependency link is unavailable")
    return node


def verified_artifacts(output: Path, report: Path, original_sha: str, run_id: str) -> dict:
    raw = read_file(output / VERIFICATION)
    verification = json.loads(raw)
    if not isinstance(verification, dict):
        raise Invalid("TM-002 workbook verification is not an object")
    if (verification.get("schema_version") != 1 or verification.get("state") != "PASS"
            or verification.get("run_id") != run_id
            or verification.get("source_report") != {"path": str(report), "sha256": original_sha}):
        raise Invalid("TM-002 workbook verification has a different source identity")
    entry = verification.get("workbook")
    expected_name = f"TokenMeter测试结果-{run_id}.xlsx"
    if not isinstance(entry, dict) or entry.get("path") != expected_name:
        raise Invalid("TM-002 workbook verification has a different workbook name")
    book = read_file(output / expected_name)
    if (not book or entry.get("sha256") != sha(book) or entry.get("bytes") != len(book)
            or not SHA256.fullmatch(str(entry.get("sha256", "")))):
        raise Invalid("TM-002 workbook differs from its readback verification")
    source_bytes = read_file(output / SOURCE_MANIFEST)
    source_entry = verification.get("source_manifest")
    source_manifest = json.loads(source_bytes)
    if not isinstance(source_manifest, dict):
        raise Invalid("TM-002 source manifest is not an object")
    if (source_entry != {"path": SOURCE_MANIFEST, "sha256": sha(source_bytes)}
            or source_manifest.get("report_sha256") != original_sha
            or source_manifest.get("fingerprint") != verification.get("source_fingerprint")):
        raise Invalid("TM-002 source manifest differs from export verification")
    return {"workbook": {"path": str(output / expected_name), "sha256": sha(book), "bytes": len(book)},
            "verification": {"path": str(output / VERIFICATION), "sha256": sha(raw), "bytes": len(raw)},
            "source_manifest": {"path": str(output / SOURCE_MANIFEST), "sha256": sha(source_bytes),
                                "bytes": len(source_bytes)}}


def export_result(report_path: Path, output: Path | None = None) -> dict:
    """Return an immutable receipt or an in-memory failure for an existing receipt."""
    receipt = {"schema_version": 1, "scope": "tm002_product_e2e_excel_export",
               "state": "FAIL", "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    receipt_path = None
    original = None
    report = None
    try:
        report = safe_path(Path(report_path))
        original = read_file(report)
        source_sha = sha(original)
        value = json.loads(original)
        if not isinstance(value, dict):
            raise Invalid("TM-002 original result is not an object")
        run_id = value.get("run_id")
        receipt["product_state"] = value.get("state")
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            raise Invalid("TM-002 result has an invalid run_id")
        if value.get("state") not in ("PASS", "FAIL", "BLOCKED"):
            raise Invalid("TM-002 result has no actual PASS, FAIL or BLOCKED state")
        target = safe_path(Path(output) if output is not None else report.parent)
        receipt.update(run_id=run_id, report_path=str(report), report_sha256=source_sha,
                       output=str(target))
        if target == report or target in report.parents:
            raise Invalid("Workbook output cannot be an ancestor of the original report")
        target.mkdir(parents=True, mode=0o700, exist_ok=True)
        receipt_path = target / RECEIPT
        if receipt_path.exists() or receipt_path.is_symlink():
            previous = json.loads(read_file(receipt_path))
            if not isinstance(previous, dict):
                raise Invalid("Existing TM-002 export receipt is not an object")
            for key in ("schema_version", "scope", "run_id", "report_path", "report_sha256",
                        "product_state", "output"):
                if previous.get(key) != receipt.get(key):
                    raise Invalid("Existing TM-002 export receipt belongs to different input: " + key)
            if previous.get("state") in ("FAIL", "BLOCKED") and previous.get("error"):
                return previous
            if previous.get("state") != "PASS":
                raise Invalid("Existing TM-002 export receipt has no valid result")
        node = runtime()
        script = ROOT / "scripts/export_tm002_product_result.mjs"
        if not script.is_file() or script.is_symlink():
            raise Blocked("Fixed TM-002 product workbook exporter is unavailable")
        process = subprocess.run([str(node), str(script), "--report", str(report), "--output", str(target)],
                                 cwd=ROOT, capture_output=True, text=True, check=False, timeout=180)
        if process.returncode:
            diagnostic = (process.stderr or process.stdout or "No exporter diagnostic").strip()[-1600:]
            if "MODULE_NOT_FOUND" in diagnostic or "ERR_MODULE_NOT_FOUND" in diagnostic:
                raise Blocked("Workbook artifact runtime is unavailable: " + diagnostic)
            raise Invalid(f"TM-002 workbook exporter exited {process.returncode}: {diagnostic}")
        details = verified_artifacts(target, report, source_sha, run_id)
        if read_file(report) != original:
            raise Invalid("Original TM-002 product result changed during export")
        receipt.update(state="PASS", **details)
        if receipt_path.exists():
            previous = json.loads(read_file(receipt_path))
            if not isinstance(previous, dict):
                raise Invalid("Existing TM-002 export receipt is not an object")
            if any(previous.get(key) != receipt.get(key) for key in
                   ("scope", "run_id", "report_path", "report_sha256", "product_state",
                    "output", "workbook", "verification", "source_manifest", "state")):
                raise Invalid("Existing TM-002 export receipt or workbook changed")
            return previous
    except (Blocked, FileNotFoundError, PermissionError, subprocess.TimeoutExpired) as error:
        receipt.update(state="BLOCKED", error=str(error))
    except (Invalid, OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        receipt.update(state="FAIL", error=str(error))
    finally:
        if original is not None and report is not None:
            try:
                if read_file(report) != original:
                    receipt.update(state="FAIL", error="Original TM-002 product result changed during export")
            except (OSError, Invalid) as error:
                receipt.update(state="FAIL", error=str(error))
    if receipt.get("state") != "PASS":
        receipt.pop("workbook", None)
        receipt.pop("verification", None)
        receipt.pop("source_manifest", None)
    if receipt_path is not None and not receipt_path.exists() and not receipt_path.is_symlink():
        try:
            with receipt_path.open("x", encoding="utf-8") as stream:
                os.chmod(receipt_path, 0o600)
                json.dump(receipt, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
        except OSError as error:
            receipt.update(state="FAIL", error="TM-002 export receipt could not be saved: " + str(error))
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    receipt = export_result(args.report, args.output)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["state"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
