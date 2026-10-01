#!/usr/bin/env python3
"""Export one immutable product result to a separate workbook and receipt.

This bridge does not run the product or change its conclusion. A caller must
check the returned export state before declaring its reporting workflow done.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
DEFAULT_NODE = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
EXPORT_TIMEOUT_SECONDS = 180
RECEIPT_NAME = "excel-export.json"


class Blocked(RuntimeError):
    """A required export runtime or readable input is unavailable."""


class Invalid(RuntimeError):
    """Export inputs or returned evidence contradict the contract."""


def _safe_path(path: Path) -> Path:
    absolute = Path(path).absolute()
    if ".." in absolute.parts or any(p.is_symlink() for p in (absolute, *absolute.parents)):
        raise Invalid("Report or export path contains a symlink or parent traversal")
    return absolute


def _read_file(path: Path) -> bytes:
    _safe_path(path)
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise Invalid("Expected a regular report or export evidence file")
        content = stream.read()
        after = os.fstat(stream.fileno())
    current = path.lstat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns):
        raise Invalid("Report or export evidence changed while being read")
    return content


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _json(content: bytes, description: str) -> dict:
    value = json.loads(content)
    if not isinstance(value, dict):
        raise Invalid(f"{description} must be a JSON object")
    return value


def _descriptor(path: Path, content: bytes) -> dict:
    return {"path": str(path), "sha256": _sha(content), "bytes": len(content)}


def _verify_export(output: Path, report_path: Path, source_sha: str, run_id: str) -> dict:
    try:
        return _verify_export_files(output, report_path, source_sha, run_id)
    except OSError as error:
        raise Invalid(f"Exporter claimed success but required evidence is unavailable: {error}") from error


def _verify_export_files(output: Path, report_path: Path, source_sha: str, run_id: str) -> dict:
    verification_path = _safe_path(output / "verification.json")
    raw = _read_file(verification_path)
    verification = _json(raw, "Export verification")
    if verification.get("state") != "PASS" or verification.get("run_id") != run_id:
        raise Invalid("Export verification did not pass for this run")
    source = verification.get("source_report")
    if not isinstance(source, dict) or source.get("sha256") != source_sha or source.get("path") != str(report_path):
        raise Invalid("Export verification refers to a different source report")
    entry = verification.get("workbook")
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        raise Invalid("Export verification has no workbook descriptor")
    relative = Path(entry["path"])
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".xlsx":
        raise Invalid("Workbook path escapes its export directory or is not XLSX")
    workbook = _safe_path(output / relative)
    data = _read_file(workbook)
    if not data or entry.get("bytes") != len(data) or not isinstance(entry.get("sha256"), str) or not SHA256.fullmatch(entry["sha256"]) or entry["sha256"] != _sha(data):
        raise Invalid("Workbook bytes or SHA256 differ from export verification")
    return {"verification": _descriptor(verification_path, raw), "workbook": _descriptor(workbook, data)}


def _runtime() -> Path:
    node = Path(os.environ.get("TOKENMETER_WORKBOOK_NODE", str(DEFAULT_NODE))).expanduser()
    if not node.is_absolute() or not node.is_file() or not os.access(node, os.X_OK):
        raise Blocked("Node runtime is unavailable; configure TOKENMETER_WORKBOOK_NODE with an absolute executable path")
    return node


def _persist_receipt(path: Path, receipt: dict) -> dict:
    try:
        _safe_path(path)
        # Exclusive creation preserves every previous receipt, including failures.
        with path.open("x", encoding="utf-8") as stream:
            os.chmod(path, 0o600)
            json.dump(receipt, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
    except (OSError, Invalid) as error:
        return {**receipt, "state": "FAIL", "error": f"Export receipt could not be saved without overwrite: {error}"}
    return receipt


def export_result(report_path: Path, output: Path | None = None) -> dict:
    """Return a verified export receipt; FAIL/BLOCKED must remain visible to callers.

    The default workbook directory is .local/test-results/<run_id>. Successful
    repeated calls recheck the original bytes and assets and return the original
    receipt. Existing receipts are never overwritten, even after failure. To
    recover after fixing an export environment, pass an explicit new output:
    its receipt is named excel-export-<output-path-hash>.json and preserves the
    failed default receipt without repeating any product test.
    """
    receipt = {"schema_version": 1, "scope": "test_result_excel_export", "state": "FAIL",
               "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    source_bytes = None
    source_path = None
    receipt_path = None
    safe_to_save = False
    try:
        source_path = _safe_path(Path(report_path))
        source_bytes = _read_file(source_path)
        receipt_path = source_path.parent / RECEIPT_NAME
        safe_to_save = True
        source_sha = _sha(source_bytes)
        receipt.update(report_path=str(source_path), report_sha256=source_sha,
                       receipt_path=str(receipt_path))
        report = _json(source_bytes, "Product result")
        run_id = report.get("run_id")
        receipt["product_state"] = report.get("state")
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            raise Invalid("Report run_id must be a safe nonempty directory identifier")
        if report.get("state") not in ("PASS", "FAIL", "BLOCKED"):
            raise Invalid("Product result must retain its PASS, FAIL or BLOCKED state")
        output_path = _safe_path(Path(output) if output is not None else ROOT / ".local/test-results" / run_id)
        if output is not None:
            receipt_path = source_path.parent / f"excel-export-{_sha(str(output_path).encode('utf-8'))[:16]}.json"
            receipt["receipt_path"] = str(receipt_path)
        receipt.update(run_id=run_id, output=str(output_path))
        if output_path == source_path.parent or output_path in source_path.parents:
            raise Invalid("Workbook output must be separate from the source report directory")
        if receipt_path.exists() or receipt_path.is_symlink():
            safe_to_save = False
            existing = _json(_read_file(receipt_path), "Existing export receipt")
            for key in ("scope", "report_path", "report_sha256", "product_state", "run_id", "output", "receipt_path"):
                if existing.get(key) != receipt.get(key):
                    raise Invalid(f"Existing export receipt differs from this request: {key}")
            if existing.get("state") == "PASS":
                descriptors = _verify_export(output_path, source_path, source_sha, run_id)
                if any(existing.get(key) != value for key, value in descriptors.items()):
                    raise Invalid("Existing export evidence changed since its receipt")
                if _read_file(source_path) != source_bytes:
                    raise Invalid("Original report changed during export verification")
            elif existing.get("state") not in ("FAIL", "BLOCKED") or not existing.get("error"):
                raise Invalid("Existing export receipt has no valid conclusion")
            receipt = existing
        else:
            node = _runtime()
            exporter = ROOT / "scripts/export_test_result.mjs"
            if not exporter.is_file():
                raise Blocked("Test-result workbook exporter is unavailable")
            command = [str(node), str(exporter), "--report", str(source_path), "--output", str(output_path)]
            process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                     check=False, timeout=EXPORT_TIMEOUT_SECONDS)
            if process.returncode:
                diagnostic = (process.stderr or process.stdout or "No exporter diagnostic").strip()[-1800:]
                if any(marker in diagnostic for marker in ("MODULE_NOT_FOUND", "ERR_MODULE_NOT_FOUND", "Cannot find package '@oai/artifact-tool'", "Cannot find module '@oai/artifact-tool'")):
                    raise Blocked("Workbook artifact runtime is unavailable: " + diagnostic)
                raise Invalid(f"Workbook exporter exited {process.returncode}: {diagnostic}")
            receipt.update(_verify_export(output_path, source_path, source_sha, run_id))
            receipt["state"] = "PASS"
    except (Blocked, FileNotFoundError, PermissionError, subprocess.TimeoutExpired) as error:
        receipt.update(state="BLOCKED", error=str(error))
    except (Invalid, OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        receipt.update(state="FAIL", error=str(error))
    finally:
        if source_bytes is not None and source_path is not None:
            try:
                if _read_file(source_path) != source_bytes:
                    raise Invalid("Original report changed during export; source was not restored or overwritten")
            except (OSError, Invalid) as error:
                receipt.update(state="FAIL", error=str(error))
    if receipt["state"] != "PASS":
        receipt.pop("workbook", None)
        receipt.pop("verification", None)
    if safe_to_save and receipt_path is not None:
        return _persist_receipt(receipt_path, receipt)
    return receipt
