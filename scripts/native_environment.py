#!/usr/bin/env python3
"""Probe isolated CI signing/TLS preparation; this is not a product test gate."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2e
import native_e2e as native


def execute_probe(root: Path, output: Path, report: dict) -> None:
    report["platform"] = native.preflight(root)
    signing_data = native.load_module(root / "tests/e2e/code_signing.py", "probe_signing_fixture")
    update_data = native.load_module(root / "tests/e2e/update_source.py", "probe_update_fixture")
    with tempfile.TemporaryDirectory(prefix="tokenmeter-environment-") as temporary:
        private = Path(temporary).resolve()
        signing = signing_data.SigningIdentity(private / "signing")
        update = None
        try:
            native.progress("environment", "prepare-signing")
            signing.prepare()
            native.progress("environment", "prepare-https")
            update = update_data.UpdateSource(private / "update", output)
            update.prepare()
            update.trust_on_ephemeral_ci()
            # The leaf must chain through the installed CA using normal system
            # trust. No custom anchor (-r), allowed error, or TLS bypass is used.
            update._run(["/usr/bin/security", "verify-cert", "-c", str(update.private / "server.pem"),
                         "-p", "ssl", "-n", "localhost", "-L"], "verify temporary TLS trust")
        finally:
            primary_error = sys.exc_info()[1]
            native.progress("environment", "cleanup")
            errors = []
            for label, resource in (("update source", update), ("code-signing", signing)):
                if resource is not None:
                    try:
                        resource.close()
                    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                        errors.append(f"{label} cleanup: {e2e.exception_message(exc)}")
            native.record_cleanup_errors(report, errors, primary_error)
        report["cleanup_completed"] = True


def main(root: Path = ROOT) -> int:
    output = native.new_run_directory(root, "environment-" + uuid.uuid4().hex)
    path = output / "environment.json"
    report = {"scope": "environment_only", "state": "BLOCKED", "release_eligible": False,
              "executed_cases": 0, "cleanup_completed": False, "errors": [], "blockers": [], "cleanup_errors": [],
              "started_at": datetime.now(timezone.utc).isoformat()}
    try:
        execute_probe(root, output, report)
        report["state"] = "READY"
    except native.EvidenceError as exc:
        report["state"], report["errors"] = "FAIL", [e2e.exception_message(exc)]
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        report["blockers"] = [e2e.exception_message(exc)]
        if report["cleanup_errors"]:
            report["state"], report["errors"] = "FAIL", list(report["cleanup_errors"])
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        for field in ("errors", "blockers", "cleanup_errors"):
            report[field] = [e2e.safe_diagnostic(message) for message in report[field]]
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(report, report=str(path)), ensure_ascii=False), flush=True)
    return {"READY": 0, "FAIL": 1, "BLOCKED": 2}[report["state"]]


if __name__ == "__main__":
    raise SystemExit(main())
