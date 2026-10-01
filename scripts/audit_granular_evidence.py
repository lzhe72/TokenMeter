#!/usr/bin/env python3
"""Independently verify frozen granular App, network, phase and fixture evidence.

The supplemental verifier never changes the original report, TC result, App,
service, or SQLite database. It can only preserve or lower original PASS.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from zipfile import BadZipFile, ZipFile


CASE = "TC-TM001-SESSION-04"
SHA = re.compile(r"[a-f0-9]{64}\Z")


class EvidenceMissing(Exception):
    pass


class EvidenceInvalid(Exception):
    pass


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def _read_claimed(base: Path, description: object) -> tuple[Path, bytes, str]:
    if not isinstance(description, dict):
        raise EvidenceMissing("Original report has no descriptor for required evidence")
    relative = description.get("path")
    digest = description.get("sha256")
    length = description.get("bytes")
    if not isinstance(relative, str) or not relative or relative.startswith("/") or ".." in Path(relative).parts:
        raise EvidenceInvalid("Evidence descriptor path is unsafe")
    if not isinstance(digest, str) or not SHA.fullmatch(digest) or not isinstance(length, int) or length < 0:
        raise EvidenceInvalid("Evidence descriptor digest or length is invalid")
    path = base / relative
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(base.resolve()):
        raise EvidenceMissing("Claimed evidence file is absent or outside the run")
    raw = path.read_bytes()
    observed = hashlib.sha256(raw).hexdigest()
    if len(raw) != length or observed != digest:
        raise EvidenceInvalid("Evidence bytes do not match the original report SHA-256")
    return path, raw, observed


def _instant(value: object) -> datetime:
    if not isinstance(value, str):
        raise EvidenceInvalid("Evidence timestamp is missing")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceInvalid("Evidence timestamp is invalid") from error
    if instant.tzinfo is None:
        raise EvidenceInvalid("Evidence timestamp has no timezone")
    return instant


def _result(state: str, reason: str, report: Path, run_id: str | None,
            *, events_sha: str | None = None, transport_sha: str | None = None,
            delayed: int = 0, normal: int = 0) -> dict:
    return {"schema_version": 1, "verifier": "session04-refresh-transport-v1", "case_id": CASE,
            "run_id": run_id, "source_report_sha256": _digest(report),
            "events_sha256": events_sha, "transport_sha256": transport_sha,
            "delayed_me_count": delayed, "normal_me_200_count": normal,
            "state": state, "reason": reason}


def audit(report_path: Path, case_id: str = CASE) -> dict:
    """Return PASS only for a distinct post-recovery, non-probe normal /me 200."""
    report_path = Path(report_path).resolve(strict=True)
    if case_id != CASE:
        raise ValueError("This fixed verifier only supports TC-TM001-SESSION-04")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        run_id = report.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise EvidenceInvalid("Original report run identity is missing")
        items = [item for item in report.get("tc_results", []) if item.get("case_id") == case_id]
        if len(items) != 1:
            raise EvidenceMissing("Original report has no unique SESSION-04 result")
        item = items[0]
        if item.get("state") != "PASS":
            return _result("NOT_APPLICABLE", "Original SESSION-04 is not PASS", report_path, run_id)
        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            raise EvidenceMissing("Original PASS has no evidence map")
        _, event_bytes, event_sha = _read_claimed(report_path.parent, evidence.get("events"))
        _, transport_bytes, transport_sha = _read_claimed(report_path.parent, evidence.get("transport_audit"))
        steps = []
        for line in event_bytes.decode("utf-8").splitlines():
            entry = json.loads(line)
            if entry.get("run_id") != run_id or entry.get("case_id") != case_id:
                raise EvidenceInvalid("Step event identity differs from original report")
            if entry.get("step") in (3, 4):
                steps.append(entry)
        if [entry.get("step") for entry in steps] != [3, 4] or not all(entry.get("passed") is True for entry in steps):
            raise EvidenceMissing("Passed step 3 and step 4 events are not both available")
        started, finished = (_instant(entry.get("timestamp")) for entry in steps)
        if finished <= started:
            raise EvidenceInvalid("Step timing order is invalid")
        transport = json.loads(transport_bytes)
        if transport.get("run_id") != run_id or transport.get("case_id") != case_id:
            raise EvidenceInvalid("Transport audit identity differs from original report")
        origins = transport.get("origins")
        if not isinstance(origins, list) or len(origins) != 1 or not isinstance(origins[0].get("requests"), list):
            raise EvidenceMissing("One owned transport request stream is required")
        requests = origins[0]["requests"]
        relevant = [row for row in requests if row.get("method") == "GET" and row.get("route") == "/v1/me"
                    and row.get("probe") is False and started < _instant(row.get("received_at")) < finished]
        delayed = [row for row in relevant if row.get("mode") == "delay"]
        normal = [row for row in relevant if row.get("mode") == "normal" and row.get("forwarded") is True
                  and row.get("status") == 200 and _instant(row.get("finished_at")) <= finished]
        if not delayed:
            return _result("BLOCKED", "No separately audited delayed /v1/me request in step-4 interval",
                           report_path, run_id, events_sha=event_sha, transport_sha=transport_sha,
                           delayed=0, normal=len(normal))
        if not normal:
            return _result("BLOCKED", "Old delayed response cannot prove a new UI refresh; no distinct normal /v1/me 200",
                           report_path, run_id, events_sha=event_sha, transport_sha=transport_sha,
                           delayed=len(delayed), normal=0)
        return _result("PASS", "Distinct new normal /v1/me 200 is present after recovery",
                       report_path, run_id, events_sha=event_sha, transport_sha=transport_sha,
                       delayed=len(delayed), normal=len(normal))
    except EvidenceMissing as error:
        return _result("BLOCKED", str(error), report_path, locals().get("run_id"))
    except (EvidenceInvalid, UnicodeError, json.JSONDecodeError, TypeError, AttributeError) as error:
        return _result("FAIL", str(error), report_path, locals().get("run_id"))


AUDITED_CASES = (
    "TC-TM001-SESSION-04", "TC-TM001-CONFIG-01", "TC-TM001-CONFIG-02",
    "TC-TM001-CONFIG-03", "TC-TM001-CONFIG-04", "TC-TM001-CONFIG-05",
    "TC-TM001-CONFIG-06", "TC-TM001-UPDATE-01", "TC-TM001-UPDATE-04",
    "TC-TM001-UPDATE-07",
    "TC-TM001-PASSWORD-05", "TC-TM001-ADMIN-03",
)
SPEC = {"SESSION": "granular-account.spec.ts", "CONFIG": "granular-config.spec.ts",
        "UPDATE": "granular-update.spec.ts", "PASSWORD": "granular-login.spec.ts",
        "ADMIN": "granular-account.spec.ts"}

# These three frozen sources were reviewed together for the independently
# installed peer App and profile. A changed runner or spec needs a new review;
# matching words in otherwise arbitrary source are not sufficient evidence.
PASSWORD05_PEER_SOURCES = {
    "scripts/granular_e2e.py": "a1aba3d1f41b096bb8f3c236d2d92d03179f9060da829cf9368dfcea21f2a3ea",
    "scripts/local_e2e.py": "f5fa187deb8bc406854683d7b1a8baab419781ccf6d5f2608fdbf83187691cd7",
    "apps/desktop/e2e/granular-login.spec.ts": "0bd303133c7d3bd0452eac4359af45ff8a8d94295664af0aed500faacafbe5a2",
}
# The subsequent runner added unrelated CONFIG observer evidence and owned fixture
# cleanup without changing PASSWORD-05's peer App/profile creation or launch.
# Keep whole reviewed triples so a mixed runner/installer combination is blocked.
PASSWORD05_PEER_SOURCE_SETS = (PASSWORD05_PEER_SOURCES, {
    "scripts/granular_e2e.py": "c7c081af5ef98d7d911f4cc78d8f8b276d99dc1bb60e6f8f937d22355593e654",
    "scripts/local_e2e.py": "2ce5abbf7be1481c4f9a09ae875f3a0e3e40ce28c1255d498f2decf71b1fee83",
    "apps/desktop/e2e/granular-login.spec.ts": "0bd303133c7d3bd0452eac4359af45ff8a8d94295664af0aed500faacafbe5a2",
}, {
    # Reviewed against the previous frozen pair: only ShipIt cleanup and its
    # evidence changed. PASSWORD-05 never prepares or cleans ShipIt; its peer
    # installation, profile, context, and Playwright launch are unchanged.
    "scripts/granular_e2e.py": "83872c29f7be845de0bac933e8a981615def0d4e4e1bd49948efcd0d738af21e",
    "scripts/local_e2e.py": "b418c83bd8935c3a985d06d5d0dae6ab73c63a26b91840d1c99da83b1e07491c",
    "apps/desktop/e2e/granular-login.spec.ts": "0bd303133c7d3bd0452eac4359af45ff8a8d94295664af0aed500faacafbe5a2",
}, {
    # The final supplemental runner now binds a distinct run ID to the already
    # finished detailed report before mounting the DMG. Its peer App/profile
    # installation, context creation and Playwright launch paths are unchanged.
    "scripts/granular_e2e.py": "83872c29f7be845de0bac933e8a981615def0d4e4e1bd49948efcd0d738af21e",
    "scripts/local_e2e.py": "d43036d0cee91b06df325f0fd8c9a60067b198fb2702ee56cedc80fcd028dae1",
    "apps/desktop/e2e/granular-login.spec.ts": "0bd303133c7d3bd0452eac4359af45ff8a8d94295664af0aed500faacafbe5a2",
}, {
    # The detailed runner now snapshots the shared lsof parser imported only by
    # update specs. Its peer App installation, profile and launch paths are unchanged.
    "scripts/granular_e2e.py": "22e85ed37e850d38b7fd05ccc79346e96f5a7dbd6a1744f1b84b51dad07a6f5b",
    "scripts/local_e2e.py": "d43036d0cee91b06df325f0fd8c9a60067b198fb2702ee56cedc80fcd028dae1",
    "apps/desktop/e2e/granular-login.spec.ts": "0bd303133c7d3bd0452eac4359af45ff8a8d94295664af0aed500faacafbe5a2",
})


def _code_snapshot(report_path: Path, report: dict, case_id: str) -> tuple[dict, str]:
    group = case_id.split("-")[2]
    relative = "apps/desktop/e2e/" + SPEC[group]
    expected = report.get("test_inputs_sha256")
    snapshots = report.get("test_code_snapshot")
    if not isinstance(expected, dict) or not isinstance(snapshots, list):
        raise EvidenceMissing("Frozen test input hashes and source snapshots are absent")
    descriptors = [entry for entry in snapshots if isinstance(entry, dict)
                   and entry.get("path") == "test-code/" + relative]
    if len(descriptors) != 1:
        raise EvidenceMissing("Unique frozen test code snapshot is absent")
    _, _, digest = _read_claimed(report_path.parent, descriptors[0])
    if expected.get(relative) != digest:
        raise EvidenceInvalid("Frozen test source differs from its report input hash")
    return descriptors[0], digest


def _events(report_path: Path, report: dict, item: dict, case_id: str,
            required_steps: tuple[int, ...]) -> tuple[list[dict], dict]:
    evidence = item.get("evidence")
    if not isinstance(evidence, dict):
        raise EvidenceMissing("Original PASS has no evidence map")
    descriptor = evidence.get("events")
    _, raw, _ = _read_claimed(report_path.parent, descriptor)
    records = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    if any(row.get("run_id") != report["run_id"] or row.get("case_id") != case_id for row in records):
        raise EvidenceInvalid("Step event identity differs from original run")
    observed = [row for row in records if row.get("step") in required_steps]
    if [row.get("step") for row in observed] != list(required_steps) or not all(row.get("passed") is True for row in observed):
        raise EvidenceMissing("Required passing step events are not complete")
    return observed, descriptor


def _transport(report_path: Path, report: dict, item: dict, case_id: str) -> tuple[dict, dict]:
    evidence = item.get("evidence")
    if not isinstance(evidence, dict):
        raise EvidenceMissing("Original PASS has no evidence map")
    descriptor = evidence.get("transport_audit")
    _, raw, _ = _read_claimed(report_path.parent, descriptor)
    data = json.loads(raw)
    if data.get("run_id") != report["run_id"] or data.get("case_id") != case_id:
        raise EvidenceInvalid("Transport audit identity differs from original run")
    return data, descriptor


def _main_observer(report_path: Path, report: dict, item: dict,
                   finding: dict) -> list[dict]:
    """Bind App requests to the frozen pre-entry collector and each owned PID."""
    evidence = item.get("evidence")
    if not isinstance(evidence, dict):
        raise EvidenceMissing("Original PASS has no evidence map")
    descriptor = evidence.get("main_observer")
    _, raw, _ = _read_claimed(report_path.parent, descriptor)
    finding["evidence"]["main_observer"] = descriptor
    snapshots = report.get("test_code_snapshot")
    inputs = report.get("test_inputs_sha256")
    if not isinstance(snapshots, list) or not isinstance(inputs, dict):
        raise EvidenceMissing("Frozen main-observer test source is absent")
    helper_hash = None
    for name in ("apps/desktop/e2e/main-observer.ts", "apps/desktop/e2e/main-observer.cjs"):
        matches = [entry for entry in snapshots if isinstance(entry, dict)
                   and entry.get("path") == "test-code/" + name]
        if len(matches) != 1:
            raise EvidenceMissing("Unique frozen main-observer source is absent: " + name)
        _, _, digest = _read_claimed(report_path.parent, matches[0])
        if inputs.get(name) != digest:
            raise EvidenceInvalid("Main-observer source differs from report input hash: " + name)
        if name.endswith(".cjs"):
            helper_hash = digest
            finding["evidence"]["main_observer_code"] = matches[0]
        else:
            finding["evidence"]["main_observer_launcher"] = matches[0]
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    if not rows:
        raise EvidenceMissing("Main observer recorded no launch marker")
    launches: dict[str, list[dict]] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("run_id") != report["run_id"] or \
                row.get("case_id") != finding["case_id"]:
            raise EvidenceInvalid("Main-observer row identity differs from original run")
        launch = row.get("launch_id")
        if not isinstance(launch, str) or not launch:
            raise EvidenceInvalid("Main-observer launch identity is missing")
        if type(row.get("pid")) is not int or row["pid"] <= 0 or \
                type(row.get("sequence")) is not int:
            raise EvidenceInvalid("Main-observer PID or sequence is invalid")
        _instant(row.get("time"))
        launches.setdefault(launch, []).append(row)
    for group in launches.values():
        if group[0].get("kind") != "installed-before-entry" or \
                group[0].get("source_sha256") != helper_hash or \
                [row["sequence"] for row in group] != list(range(1, len(group) + 1)) or \
                len({row["pid"] for row in group}) != 1:
            raise EvidenceMissing("A main-process launch lacks an intact pre-entry observer sequence")
    finding["observer_launches"] = len(launches)
    return rows


def _failure_classification(report_path: Path, report: dict, item: dict,
                            case_id: str, finding: dict) -> str:
    evidence = item.get("evidence")
    if not isinstance(evidence, dict):
        return "Original TC was not PASS; no audit upgrade"
    descriptor = evidence.get("playwright")
    _, raw, _ = _read_claimed(report_path.parent, descriptor)
    finding["evidence"]["playwright"] = descriptor
    if case_id == "TC-TM001-PASSWORD-05" and b"TokenMeter unsafe_storage" in raw and \
            b"secondary-profile" in raw and b"electron.launch" in raw:
        return ("test_setup: the second App launch used an unprepared secondary profile and the "
                "first App binary's bound runtime sidecar; password behavior was not reached")
    if case_id == "TC-TM001-ADMIN-03" and b"bobApp.process().pid" in raw and \
            b"Cannot read properties of undefined" in raw:
        _events(report_path, report, item, case_id, (1, 2, 3, 4))
        return "test_cleanup: all four steps passed before the test finally read a closed bobApp process"
    return "Original TC was not PASS; no audit upgrade"


def _config03_new_b_me(report_path: Path, report: dict, item: dict, finding: dict) -> tuple[str, str]:
    case_id = finding["case_id"]
    steps, events_descriptor = _events(report_path, report, item, case_id, (3, 4))
    finding["evidence"]["events"] = events_descriptor
    started, finished = (_instant(row.get("timestamp")) for row in steps)
    if finished <= started:
        raise EvidenceInvalid("CONFIG-03 step timing order is invalid")
    transport, transport_descriptor = _transport(report_path, report, item, case_id)
    finding["evidence"]["transport_audit"] = transport_descriptor
    origins = transport.get("origins")
    if not isinstance(origins, list) or len(origins) != 2 or not isinstance(origins[1], dict):
        raise EvidenceMissing("CONFIG-03 requires primary and secondary owned transport streams")
    rows = origins[1].get("requests")
    if not isinstance(rows, list):
        raise EvidenceMissing("Secondary transport request stream is absent")
    references = {row.get("authorization_sha256") for row in rows
                  if row.get("method") == "GET" and row.get("route") == "/v1/me"
                  and row.get("probe") is True and row.get("status") == 200
                  and row.get("forwarded") is True and _instant(row.get("finished_at")) <= started
                  and isinstance(row.get("authorization_sha256"), str)
                  and SHA.fullmatch(row["authorization_sha256"])}
    if len(references) != 1:
        return "BLOCKED", "No unique pre-restart B token fingerprint from a real /v1/me 200 probe"
    renewed = [row for row in rows if row.get("method") == "GET" and row.get("route") == "/v1/me"
               and row.get("probe") is False and row.get("mode") == "normal"
               and row.get("forwarded") is True and row.get("status") == 200
               and row.get("authorization_sha256") in references
               and started < _instant(row.get("received_at"))
               and _instant(row.get("finished_at")) <= finished]
    finding["new_b_me_200_count"] = len(renewed)
    if not renewed:
        return "BLOCKED", "Historical B requests cannot prove a new post-restart App /v1/me 200"
    return "PASS", "New post-restart non-probe B /v1/me 200 uses the previously verified B credential"


def _config_origin_readback(report_path: Path, report: dict, item: dict,
                            finding: dict) -> tuple[str, str]:
    """Verify every fixed API-origin input was read back from both UI and settings."""
    case_id = finding["case_id"]
    observer = _main_observer(report_path, report, item, finding)
    if finding["observer_launches"] != 1 or any(row.get("kind") == "request" for row in observer):
        raise EvidenceMissing("Configuration-only API-origin saves unexpectedly sent a network request")
    steps, descriptor = _events(report_path, report, item, case_id, (1, 2, 3, 4))
    finding["evidence"]["events"] = descriptor
    valid = ("http://127.0.0.1:49176", "http://localhost:49176",
             "http://[::1]:49176", "https://example.invalid")
    saved = steps[0].get("actual")
    if not isinstance(saved, list) or len(saved) != len(valid):
        raise EvidenceMissing("Every legal API origin needs separate UI and settings-file readback")
    for observed, origin in zip(saved, valid):
        if not isinstance(observed, dict) or observed != {
            "input": origin, "canonical": origin, "ui": origin,
            "fileOverride": None if origin == valid[0] else origin, "requestDelta": 0,
        }:
            raise EvidenceMissing("A legal API origin lacks its exact canonical UI/file value")
    if steps[0].get("expected") != saved:
        raise EvidenceInvalid("Legal API-origin expected and actual evidence differ")

    invalid = ("http://example.invalid", "http://127.1:49176",
               "http://2130706433:49176", "http://", "http://127.0.0.1:65536",
               "http://user:pass@127.0.0.1:49176", "http://127.0.0.1:49176/path",
               "http://127.0.0.1:49176?x=1", "http://127.0.0.1:49176/#f")
    rejected = steps[1].get("actual")
    if not isinstance(rejected, list) or len(rejected) != len(invalid):
        raise EvidenceMissing("Every illegal API origin needs a separate rejection and unchanged file")
    file_shas = {row.get("fileSha") for row in rejected if isinstance(row, dict)}
    auth_counts = {row.get("ownedAuthCount") for row in rejected if isinstance(row, dict)}
    if len(file_shas) != 1 or not all(isinstance(value, str) and SHA.fullmatch(value) for value in file_shas):
        raise EvidenceMissing("Illegal API origins do not have one stable settings-file digest")
    if len(auth_counts) != 1 or not all(type(value) is int and value >= 0 for value in auth_counts):
        raise EvidenceMissing("Illegal API-origin saves lack a stable owned authentication count")
    if next(iter(auth_counts)) != 0:
        raise EvidenceMissing("An illegal API-origin save coincided with an owned authentication request")
    for observed, origin in zip(rejected, invalid):
        if observed != {"input": origin, "error": "请输入 HTTPS 服务地址或本机回环 HTTP 地址（invalid_server_url）",
                       "fileSha": next(iter(file_shas)), "server": valid[-1],
                       "ownedAuthCount": next(iter(auth_counts)), "mainRequestCount": 0}:
            raise EvidenceMissing("Illegal API origin was not visibly rejected with settings unchanged")
    if steps[1].get("expected") != rejected:
        raise EvidenceInvalid("Illegal API-origin expected and actual evidence differ")
    normalized = {"first": valid[-1], "second": valid[-1], "uiA": valid[-1],
                  "uiB": valid[-1], "sameCredentialPath": True}
    if steps[2].get("expected") != normalized or steps[2].get("actual") != normalized:
        raise EvidenceMissing("Equivalent HTTPS inputs lack identical UI, origin and credential path")
    separate = steps[3].get("actual")
    if not isinstance(separate, dict) or steps[3].get("expected") != separate or \
            not re.fullmatch(r"http://127\.0\.0\.1:[1-9][0-9]{0,4}", str(separate.get("origin"))) or \
            separate.get("ui") != separate.get("origin") or \
            separate.get("differentCredentialPath") is not True or \
            separate.get("newCredentialPresent") is not False:
        raise EvidenceMissing("Distinct owned API origin has no separate credential and UI readback")
    return "PASS", "All legal/illegal API origins have individual UI and settings evidence"


def _config_feed_readback(report_path: Path, report: dict, item: dict,
                          finding: dict) -> tuple[str, str]:
    """Verify each legal feed persists before and after a real App restart."""
    case_id = finding["case_id"]
    observer = _main_observer(report_path, report, item, finding)
    if finding["observer_launches"] != 4 or any(row.get("kind") == "request" for row in observer):
        raise EvidenceMissing("Configuration-only update-feed saves unexpectedly sent a network request")
    steps, descriptor = _events(report_path, report, item, case_id, (1, 2, 3, 4))
    finding["evidence"]["events"] = descriptor
    saved = steps[0].get("actual")
    if not isinstance(saved, list) or len(saved) != 2:
        raise EvidenceMissing("Both legal update feeds need separate UI/file and restart readback")
    loopback = saved[0].get("input") if isinstance(saved[0], dict) else None
    if not isinstance(loopback, str) or not re.fullmatch(
            r"http://127\.0\.0\.1:[1-9][0-9]{0,4}/version\.json", loopback):
        raise EvidenceMissing("Owned loopback version feed is not present")
    remote = "https://updates.example.invalid/version.json"
    for row, feed in zip(saved, (loopback, remote)):
        required = {"input": feed, "ui": feed, "file": feed,
                    "afterRestartUi": feed, "afterRestartFile": feed,
                    "requestDelta": 0}
        if row != required:
            raise EvidenceMissing("A legal update feed lacks save and restart UI/file readback")
    if steps[0].get("expected") != saved:
        raise EvidenceInvalid("Legal update-feed expected and actual evidence differ")

    invalid = ("http://example.invalid/version.json", "http://",
               "http://user:pass@127.0.0.1/version.json",
               "http://127.0.0.1/version.json?", "http://127.0.0.1/version.json#",
               "http://127.0.0.1:65536/version.json", "http://127.1/version.json",
               "http://2130706433/version.json")
    rejected = steps[1].get("actual")
    if not isinstance(rejected, list) or len(rejected) != len(invalid):
        raise EvidenceMissing("Every illegal update feed needs separate visible rejection")
    file_shas = {row.get("fileSha") for row in rejected if isinstance(row, dict)}
    auth_counts = {row.get("ownedAuthCount") for row in rejected if isinstance(row, dict)}
    if len(file_shas) != 1 or not all(isinstance(value, str) and SHA.fullmatch(value) for value in file_shas):
        raise EvidenceMissing("Illegal update feeds do not have one stable settings-file digest")
    if len(auth_counts) != 1 or not all(type(value) is int and value >= 0 for value in auth_counts):
        raise EvidenceMissing("Illegal update-feed saves lack a stable owned authentication count")
    if next(iter(auth_counts)) != 0:
        raise EvidenceMissing("An illegal update-feed save coincided with an owned authentication request")
    for row, feed in zip(rejected, invalid):
        if row != {"input": feed, "error": "更新地址无效，仅支持 HTTPS 或本机回环 HTTP（update_source_rejected）",
                   "fileSha": next(iter(file_shas)), "feed": remote,
                   "ownedAuthCount": next(iter(auth_counts)), "mainRequestCount": 0}:
            raise EvidenceMissing("Illegal update feed changed settings or lacked visible rejection")
    if steps[1].get("expected") != rejected:
        raise EvidenceInvalid("Illegal update-feed expected and actual evidence differ")
    pinned = {"publicKeyPinned": True, "noKeyEditor": True}
    if steps[2].get("expected") != pinned or steps[2].get("actual") != pinned:
        raise EvidenceMissing("Pinned signing key or no-editor evidence is absent")
    if steps[3].get("expected") != remote or steps[3].get("actual") != remote:
        raise EvidenceMissing("Final restart did not retain the legal update feed")
    return "PASS", "Both legal feeds and all rejected feeds have per-value UI/file evidence"


def _config01_default_boundary(report_path: Path, report: dict, item: dict,
                               finding: dict) -> tuple[str, str]:
    case_id = finding["case_id"]
    steps, descriptor = _events(report_path, report, item, case_id, (1, 2, 3, 4))
    finding["evidence"]["events"] = descriptor
    rows = _main_observer(report_path, report, item, finding)
    defaults = {"api": "http://127.0.0.1:49176",
                "feed": "http://127.0.0.1:49177/version.json"}
    if steps[0].get("expected") != {"ui": defaults, "signed": defaults} or \
            steps[0].get("actual") != steps[0].get("expected"):
        raise EvidenceMissing("First-launch UI and frozen package defaults do not match")
    first = steps[1].get("actual")
    if first != {"unauthenticated": True, "ownedAuthenticationRequests": 0,
                 "observerArmed": True, "defaultRequests": 0} or \
            steps[1].get("expected") != first:
        raise EvidenceMissing("Startup lacks no-session and pre-entry zero-request evidence")
    configured = steps[2].get("actual")
    if not isinstance(configured, dict) or steps[2].get("expected") != configured or \
            not re.fullmatch(r"http://127\.0\.0\.1:[1-9][0-9]{0,4}", str(configured.get("origin"))) or \
            configured["origin"] == defaults["api"] or configured.get("ownedLogin") is not True or \
            configured.get("observedLogin") is not True:
        raise EvidenceMissing("Owned dynamic service login positive control is absent")
    after = steps[3].get("actual")
    if after != {"api": configured["origin"], "observerLaunches": 2,
                 "defaultRequests": 0} or steps[3].get("expected") != after or \
            finding["observer_launches"] != 2:
        raise EvidenceMissing("Restart lacks persisted owned API address or a second observed launch")
    requests = [row for row in rows if row.get("kind") == "request"]
    if any(row.get("origin") in (defaults["api"], "http://127.0.0.1:49177")
           for row in requests):
        raise EvidenceMissing("App actually sent a request to a user-default local port")
    if not any(row.get("origin") == configured["origin"] and row.get("path") == "/v1/auth/login"
               and row.get("method") == "POST" for row in requests):
        raise EvidenceMissing("Pre-entry observer did not see the real owned login request")
    return "PASS", "Both launches were observed before App entry, with zero default-port requests and a real owned login"


def _config05_default_reset(report_path: Path, report: dict, item: dict,
                            finding: dict) -> tuple[str, str]:
    case_id = finding["case_id"]
    steps, descriptor = _events(report_path, report, item, case_id, (1, 2, 3, 4, 5))
    finding["evidence"]["events"] = descriptor
    rows = _main_observer(report_path, report, item, finding)
    if any(row.get("expected") != row.get("actual") for row in steps) or \
            steps[2].get("actual") is not True or steps[4].get("actual") is not True:
        raise EvidenceMissing("Pair validation, reset deletion or signed defaults failed")
    defaults = {"api": "http://127.0.0.1:49176",
                "feed": "http://127.0.0.1:49177/version.json"}
    reset = {"ui": defaults, "observerLaunches": 4, "defaultRequests": 0}
    if steps[3].get("expected") != reset or steps[3].get("actual") != reset or \
            finding["observer_launches"] != 4:
        raise EvidenceMissing("Reset/default readback lacks four observed App launches")
    if any(row.get("kind") == "request" and row.get("origin") in
           (defaults["api"], "http://127.0.0.1:49177") for row in rows):
        raise EvidenceMissing("Default reset caused a request to a user-default local port")
    return "PASS", "Reset removed both overrides; four observed App launches sent no default-port request"


def _config06_phase_locks(report_path: Path, report: dict, item: dict,
                          finding: dict) -> tuple[str, str]:
    case_id = finding["case_id"]
    steps, descriptor = _events(report_path, report, item, case_id, (1, 2, 3, 4, 5))
    finding["evidence"]["events"] = descriptor
    main = _main_observer(report_path, report, item, finding)
    if finding["observer_launches"] != 1:
        raise EvidenceMissing("Upgrade attempt needs one independently observed initial App process")
    for row in steps:
        if row.get("expected") != row.get("actual"):
            raise EvidenceMissing("CONFIG-06 has an unequal step result despite original PASS")
    expected_locks = {"api": True, "feed": False, "reset": True}
    if steps[0].get("actual") != expected_locks or steps[1].get("actual") != expected_locks or \
            steps[2].get("actual") != {"api": False, "feed": False, "reset": False}:
        raise EvidenceMissing("Account/pending-logout locks are incomplete")
    expected_busy = {"firstDownloadLocked": True, "allPhases": True,
                     "stateLocked": True, "uiStayedLocked": True,
                     "autonomousNewPid": True, "feedUnchanged": True}
    if steps[3].get("actual") != expected_busy or \
            steps[4].get("actual") != {"preHandoffCancelRestored": True, "handoffNoCancel": True}:
        raise EvidenceMissing("Cancellation, busy-phase locks or native handoff did not pass")
    evidence = item.get("evidence")
    if not isinstance(evidence, dict):
        raise EvidenceMissing("CONFIG-06 original evidence map is absent")
    _, phase_raw, _ = _read_claimed(report_path.parent, evidence.get("config_phase_observations"))
    finding["evidence"]["config_phase_observations"] = evidence["config_phase_observations"]
    phase_rows = [json.loads(line) for line in phase_raw.decode("utf-8").splitlines()]
    if not phase_rows or any(not isinstance(row, dict) or row.get("run_id") != report["run_id"]
                             or row.get("case_id") != case_id or row.get("segment") != "upgrade"
                             for row in phase_rows):
        raise EvidenceInvalid("Upgrade phase rows have missing or mismatched identity")
    sequences = [row.get("sequence") for row in phase_rows]
    if sequences != list(range(1, len(sequences) + 1)):
        raise EvidenceMissing("Upgrade phase observation sequence is incomplete")
    snapshots = [row for row in phase_rows if row.get("kind") == "snapshot"]
    phases = ("downloading", "verifying", "ready", "installing")
    if not all(any(row.get("phase") == phase and row.get("canConfigure") is False
                   for row in snapshots) for phase in phases):
        raise EvidenceMissing("A real updater busy-phase snapshot or lock is absent")
    visible = [row for row in phase_rows if row.get("feedDisabled") is not None]
    if not visible or any(row.get("feedDisabled") is not True or row.get("resetDisabled") is not True
                          for row in visible):
        raise EvidenceMissing("Configuration UI unlocked during an observed updater busy phase")
    if not any(row.get("kind") == "dom" and row.get("phase") == "installing"
               and row.get("cancelVisible") is False for row in phase_rows):
        raise EvidenceMissing("No visible post-handoff state without cancel control")
    methods = {row.get("method") for row in main if row.get("kind") == "native-updater"}
    if not {"setFeedURL", "checkForUpdates", "quitAndInstall"}.issubset(methods):
        raise EvidenceMissing("Native Squirrel updater method chain is not observed")
    _, process_raw, _ = _read_claimed(report_path.parent, evidence.get("config_upgrade_process"))
    finding["evidence"]["config_upgrade_process"] = evidence["config_upgrade_process"]
    process = json.loads(process_raw)
    old_pid = next(row["pid"] for row in main if row.get("kind") == "installed-before-entry")
    if process.get("run_id") != report["run_id"] or process.get("case_id") != case_id or \
            process.get("old_pid") != old_pid or \
            type(process.get("new_pid")) is not int or process["new_pid"] == old_pid or \
            process.get("runner_launches_before") != process.get("runner_launches_after") or \
            set(process.get("observed_phases", [])) != set(phases):
        raise EvidenceMissing("Autonomous upgrade process evidence does not bind the observed old App")
    return "PASS", "Every updater phase remained locked; native methods and autonomous new PID are bound to the run"


def _update04_no_native_handoff(report_path: Path, report: dict, item: dict,
                                finding: dict) -> tuple[str, str]:
    case_id = finding["case_id"]
    steps, descriptor = _events(report_path, report, item, case_id, (1, 2, 3, 4))
    finding["evidence"]["events"] = descriptor
    rows = _main_observer(report_path, report, item, finding)
    if finding["observer_launches"] != 1:
        raise EvidenceMissing("Bad-signature rejection requires one observed old App launch")
    fixed = (
        {"sourceReady": True, "productMetadata": True, "archiveCount": 1,
         "completeBytes": True, "matchingSha": True},
        {"signatureRejected": True, "keyUnchanged": True, "build100": True},
        {"samePid": True, "sameTree": True, "oldBuild": True,
         "verifiedSession": True, "observerBeforeEntry": True,
         "nativeHandoffCount": 0},
        {"temporaryDownloads": 0, "noHigherApp": True,
         "sourceEvidence": True, "noPrivateKeyInEvents": True},
    )
    if any(row.get("expected") != expected or row.get("actual") != expected
           for row, expected in zip(steps, fixed)):
        raise EvidenceMissing("Bad-signature UI, archive or cleanup step lacks fixed expected evidence")
    if any(row.get("kind") == "native-updater" for row in rows):
        raise EvidenceMissing("A native updater method was called despite signature rejection")
    if not any(row.get("kind") == "request" and row.get("path") == "/update.zip"
               for row in rows):
        raise EvidenceMissing("Main-process observer did not see the real ZIP request")
    return "PASS", "Real ZIP was fetched, signature was rejected, and no native updater method ran"


def _update01_discovery_only(report_path: Path, report: dict, item: dict,
                             finding: dict) -> tuple[str, str]:
    case_id = finding["case_id"]
    steps, descriptor = _events(report_path, report, item, case_id, (1, 2, 3, 4))
    finding["evidence"]["events"] = descriptor
    rows = _main_observer(report_path, report, item, finding)
    if finding["observer_launches"] != 1:
        raise EvidenceMissing("Discovery-only run needs one pre-entry observed App")
    for row in steps:
        if row.get("expected") != row.get("actual"):
            raise EvidenceMissing("Discovery-only UI or process step is not fully proved")
    fixed = {"noArchive": True, "noNativeCache": True, "oldProcessOnly": True,
             "oldAppTree": True, "installStillRequiresClick": True,
             "observerBeforeEntry": True, "observedEgressOnlyOwned": True,
             "observedMetadataOnly": True, "nativeHandoffCount": 0}
    if steps[3].get("actual") != fixed:
        raise EvidenceMissing("Pre-confirmation fixed source/network/process assertions are incomplete")
    requests = [row for row in rows if row.get("kind") == "request"]
    service = {row.get("origin") for row in requests if row.get("path") == "/v1/auth/login"
               and row.get("method") == "POST"}
    update = {row.get("origin") for row in requests if row.get("path") == "/version.json"
              and row.get("method") == "GET"}
    if len(service) != 1 or len(update) != 1 or service == update or \
            not all(isinstance(origin, str) and re.fullmatch(r"http://127\.0\.0\.1:[1-9][0-9]{0,4}", origin)
                    for origin in service | update):
        raise EvidenceMissing("Owned service and update source are not separately observed")
    if any(row.get("origin") not in service | update or
           (row.get("origin") in update and row.get("path") != "/version.json")
           for row in requests):
        raise EvidenceMissing("Pre-confirmation App request escaped owned origins or fetched the archive")
    if any(row.get("kind") == "native-updater" for row in rows):
        raise EvidenceMissing("Native updater was invoked before install confirmation")
    return "PASS", "Only owned metadata was requested before confirmation; archive and native handoff were absent"


def _update07_full_open_files(report_path: Path, report: dict, item: dict,
                              finding: dict) -> tuple[str, str]:
    case_id = finding["case_id"]
    steps, descriptor = _events(report_path, report, item, case_id, (5,))
    finding["evidence"]["events"] = descriptor
    required = {"newPidOwnsProfile": True, "originCredentialOwned": True,
                "noUserProfile": True}
    if steps[0].get("expected") != required or steps[0].get("actual") != required:
        raise EvidenceMissing("New PID profile ownership step lacks fixed expected evidence")
    evidence = item.get("evidence")
    if not isinstance(evidence, dict):
        raise EvidenceMissing("Original PASS has no evidence map")
    descriptor = evidence.get("process_open_files")
    _, raw, _ = _read_claimed(report_path.parent, descriptor)
    finding["evidence"]["process_open_files"] = descriptor
    record = json.loads(raw)
    if record.get("run_id") != report["run_id"] or record.get("case_id") != case_id or \
            type(record.get("pid")) is not int or record["pid"] <= 0:
        raise EvidenceInvalid("Complete lsof evidence identity or PID is invalid")
    paths = record.get("all_open_paths")
    owned = record.get("owned_profile_paths")
    default = record.get("default_profile")
    default_paths = record.get("default_profile_paths")
    if not isinstance(paths, list) or not all(isinstance(path, str) and path for path in paths) or \
            not isinstance(owned, list) or not isinstance(default, str) or \
            not default.endswith("/Library/Application Support/TokenMeter") or \
            not isinstance(default_paths, list):
        raise EvidenceMissing("Complete named lsof path list or profile comparison is absent")
    candidate_roots = {path.split("/profile/", 1)[0] + "/profile" for path in owned
                       if isinstance(path, str) and "/profile/" in path}
    if len(candidate_roots) != 1:
        raise EvidenceMissing("One owned profile root cannot be inferred from opened files")
    owned_root = next(iter(candidate_roots))
    if owned_root == default or \
            owned != [path for path in paths if path.startswith(owned_root + "/")] or \
            default_paths != [path for path in paths if path == default or path.startswith(default + "/")] or \
            default_paths or not owned or len(paths) <= len(owned):
        raise EvidenceMissing("Full lsof list does not prove owned profile use and zero default-profile file")
    finding["all_open_file_count"] = len(paths)
    return "PASS", "Unfiltered new-PID lsof list contains owned files and no default-profile file"


def _peer_trace(report_path: Path, case_id: str, name: str,
                claimed: dict | None = None) -> tuple[dict, dict]:
    if claimed is None:
        path = report_path.parent / case_id / name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(report_path.parent):
            raise EvidenceMissing("Independent peer App trace is absent or outside the run")
        if path.stat().st_size > 20 * 1024 * 1024:
            raise EvidenceInvalid("Independent peer App trace is unexpectedly large")
        raw = path.read_bytes()
        descriptor = {"path": f"{case_id}/{name}", "sha256": hashlib.sha256(raw).hexdigest(),
                      "bytes": len(raw)}
    else:
        descriptor = claimed
        _, raw, _ = _read_claimed(report_path.parent, claimed)
    try:
        with ZipFile(report_path.parent / descriptor["path"]) as archive:
            entries = archive.infolist()
            if sum(entry.file_size for entry in entries) > 20 * 1024 * 1024:
                raise EvidenceInvalid("Peer App trace expands beyond its evidence limit")
            if archive.testzip() is not None:
                raise EvidenceInvalid("Peer App trace ZIP has a failed member checksum")
            options = [json.loads(line) for line in archive.read("trace.trace").splitlines()
                       if b'"type":"context-options"' in line]
    except (BadZipFile, KeyError, OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceInvalid("Peer App trace is not a valid Playwright context record") from error
    if len(options) != 1 or not isinstance(options[0].get("options"), dict):
        raise EvidenceMissing("Peer App trace has no unique launch context")
    return options[0]["options"], descriptor


def _password05_peer_binding(report_path: Path, report: dict, item: dict,
                             finding: dict) -> tuple[str, str]:
    case_id = finding["case_id"]
    snapshots = report.get("test_code_snapshot")
    inputs = report.get("test_inputs_sha256")
    if not isinstance(snapshots, list) or not isinstance(inputs, dict):
        raise EvidenceMissing("Frozen peer fixture source snapshots are absent")
    observed_sources = {}
    for source in PASSWORD05_PEER_SOURCES:
        relative = "test-code/" + source
        matches = [entry for entry in snapshots if isinstance(entry, dict) and entry.get("path") == relative]
        if len(matches) != 1:
            raise EvidenceMissing("Unique frozen peer fixture source is absent: " + source)
        _, _, observed_sha = _read_claimed(report_path.parent, matches[0])
        if inputs.get(source) != observed_sha:
            raise EvidenceInvalid("Frozen peer fixture source differs from report input SHA: " + source)
        observed_sources[source] = observed_sha
        if source == "scripts/granular_e2e.py":
            finding["evidence"]["peer_runner_code"] = matches[0]
        elif source == "scripts/local_e2e.py":
            finding["evidence"]["peer_install_code"] = matches[0]
    if not any(observed_sources == trusted for trusted in PASSWORD05_PEER_SOURCE_SETS):
        raise EvidenceMissing("Peer fixture source changed since its reviewed binding")

    steps, descriptor = _events(report_path, report, item, case_id, (1, 2, 3, 4))
    finding["evidence"]["events"] = descriptor
    required = (
        {"identity": True, "mustChange": False, "role": "成员", "sessions": 1},
        {"old1": 401, "old2": 401, "newSession": 200, "identity": True},
        {"old": 401, "new": 200, "changedAudit": 1, "role": "member"},
        {"loginVisible": True, "savedCredential": False, "oldSession": 401},
    )
    if any(row.get("expected") != want or row.get("actual") != want
           for row, want in zip(steps, required)):
        raise EvidenceMissing("Second-profile password-change steps lack the fixed expected values")

    evidence = item.get("evidence")
    if not isinstance(evidence, dict):
        raise EvidenceMissing("Original PASS has no evidence map")
    main_options, main_descriptor = _peer_trace(report_path, case_id, "trace-01.zip", evidence.get("trace"))
    before_options, before_descriptor = _peer_trace(report_path, case_id, "trace-second-before-restart.zip")
    after_options, after_descriptor = _peer_trace(report_path, case_id, "trace-second-after-restart.zip")
    finding["evidence"].update(trace=main_descriptor, peer_trace_before=before_descriptor,
                               peer_trace_after=after_descriptor)
    try:
        main_exe = Path(main_options["executablePath"])
        case_root = main_exe.parents[4]
        if (case_root.name != case_id or not case_root.parent.name.startswith(report["run_id"] + "-")
                or case_root.parent.parent.name != "local-granular-work"
                or case_root.parent.parent.parent.name != ".local"):
            raise EvidenceMissing("Main App trace is outside this run's owned case root")
        expected = (
            (main_options, case_root / "installation/TokenMeter.app/Contents/MacOS/TokenMeter",
             case_root / "profile"),
            (before_options, case_root / "peer-installation/TokenMeter.app/Contents/MacOS/TokenMeter",
             case_root / "peer-profile"),
            (after_options, case_root / "peer-installation/TokenMeter.app/Contents/MacOS/TokenMeter",
             case_root / "peer-profile"),
        )
        if any(options.get("executablePath") != str(binary)
               or options.get("args") != ["--user-data-dir=" + str(profile)]
               or options.get("chromiumSandbox") is not True
               for options, binary, profile in expected):
            raise EvidenceMissing("Peer App launch path/profile is not independent and stable across restart")
    except (KeyError, TypeError, IndexError, ValueError) as error:
        raise EvidenceInvalid("App trace launch context is malformed") from error

    transport, transport_descriptor = _transport(report_path, report, item, case_id)
    finding["evidence"]["transport_audit"] = transport_descriptor
    origins = transport.get("origins")
    if not isinstance(origins, list) or len(origins) != 1 or not isinstance(origins[0].get("requests"), list):
        raise EvidenceMissing("Password-change case has no unique owned service transport")
    requests = origins[0]["requests"]
    changes = [row for row in requests if row.get("method") == "POST"
               and row.get("route") == "/v1/auth/change-password" and row.get("status") == 200
               and row.get("forwarded") is True and row.get("probe") is False]
    if len(changes) != 1:
        raise EvidenceMissing("No unique successful real password-change request")
    change_at = _instant(changes[0].get("finished_at"))
    if len([row for row in requests if row.get("method") == "POST"
            and row.get("route") == "/v1/auth/login" and row.get("status") == 200
            and row.get("probe") is False and _instant(row.get("finished_at")) < change_at]) != 2:
        raise EvidenceMissing("Two distinct pre-change real App logins are not present")
    first_step, second_step, third_step, fourth_step = (_instant(row.get("timestamp")) for row in steps)
    if not change_at < first_step < second_step < third_step < fourth_step:
        raise EvidenceInvalid("Password-change event order is invalid")
    probes = [row for row in requests if row.get("method") == "GET" and row.get("route") == "/v1/me"
              and row.get("probe") is True and row.get("forwarded") is True
              and change_at < _instant(row.get("received_at"))
              and _instant(row.get("finished_at")) <= second_step]
    probes.sort(key=lambda row: _instant(row["received_at"]))
    if len(probes) != 3 or [row.get("status") for row in probes] != [401, 401, 200]:
        raise EvidenceMissing("Both old sessions and the new session lack independent API status evidence")
    fingerprints = [row.get("authorization_sha256") for row in probes]
    if len(set(fingerprints)) != 3 or not all(isinstance(value, str) and SHA.fullmatch(value)
                                            for value in fingerprints):
        raise EvidenceMissing("Two old sessions and new session have no distinct credential fingerprints")
    restarted = [row for row in requests if row.get("method") == "GET"
                 and row.get("route") == "/v1/me" and row.get("probe") is False
                 and row.get("forwarded") is True and row.get("status") == 401
                 and row.get("authorization_sha256") == fingerprints[1]
                 and third_step < _instant(row.get("received_at"))
                 and _instant(row.get("finished_at")) <= fourth_step]
    if not restarted:
        raise EvidenceMissing("Restarted peer App did not present the second revoked session to the real service")
    finding["distinct_old_sessions"] = 2
    finding["peer_restart_rejected_requests"] = len(restarted)
    return "PASS", "Separate installed peer App/profile and restart traces match two revoked real sessions"


def audit_run(report_path: Path) -> dict:
    """Check frozen per-TC evidence without changing original product results."""
    report_path = Path(report_path).resolve(strict=True)
    raw = report_path.read_bytes()
    report = json.loads(raw)
    if not isinstance(report, dict) or not isinstance(report.get("run_id"), str):
        raise EvidenceInvalid("Original run report identity is invalid")
    run_id = report["run_id"]
    results = report.get("tc_results")
    if not isinstance(results, list):
        raise EvidenceInvalid("Original run has no per-TC results")
    declared = report.get("expected_cases")
    if declared is None:
        declared = [item.get("case_id") for item in results if isinstance(item, dict)]
    if not isinstance(declared, list) or any(not isinstance(item, str) for item in declared):
        raise EvidenceInvalid("Original run expected TC identities are invalid")
    audited_cases = [case_id for case_id in AUDITED_CASES if case_id in declared]
    findings = []
    for case_id in audited_cases:
        matching = [item for item in results if isinstance(item, dict) and item.get("case_id") == case_id]
        original = matching[0].get("state") if len(matching) == 1 else None
        finding = {"case_id": case_id, "original_state": original,
                   "state": "BLOCKED", "reason": "", "test_code_sha256": None,
                   "evidence": {}}
        try:
            if len(matching) != 1:
                raise EvidenceMissing("Original run has no unique result for this audited TC")
            code_descriptor, code_digest = _code_snapshot(report_path, report, case_id)
            finding["test_code_sha256"] = code_digest
            finding["evidence"]["test_code"] = code_descriptor
            if original != "PASS":
                finding["state"] = "NOT_APPLICABLE"
                finding["reason"] = (_failure_classification(report_path, report, matching[0], case_id, finding)
                                     if original == "FAIL" and case_id in
                                     ("TC-TM001-PASSWORD-05", "TC-TM001-ADMIN-03") else
                                     "Original TC was not PASS; no audit upgrade")
            elif case_id == CASE:
                verdict = audit(report_path, case_id)
                finding["state"], finding["reason"] = verdict["state"], verdict["reason"]
                finding["delayed_me_count"] = verdict["delayed_me_count"]
                finding["normal_me_200_count"] = verdict["normal_me_200_count"]
                evidence = matching[0].get("evidence", {})
                for role in ("events", "transport_audit"):
                    if isinstance(evidence, dict) and isinstance(evidence.get(role), dict):
                        finding["evidence"][role] = evidence[role]
            elif case_id == "TC-TM001-CONFIG-03":
                finding["state"], finding["reason"] = _config03_new_b_me(report_path, report, matching[0], finding)
            elif case_id == "TC-TM001-CONFIG-01":
                finding["state"], finding["reason"] = _config01_default_boundary(
                    report_path, report, matching[0], finding)
            elif case_id == "TC-TM001-CONFIG-02":
                finding["state"], finding["reason"] = _config_origin_readback(report_path, report, matching[0], finding)
            elif case_id == "TC-TM001-CONFIG-04":
                finding["state"], finding["reason"] = _config_feed_readback(report_path, report, matching[0], finding)
            elif case_id == "TC-TM001-CONFIG-05":
                finding["state"], finding["reason"] = _config05_default_reset(
                    report_path, report, matching[0], finding)
            elif case_id == "TC-TM001-CONFIG-06":
                finding["state"], finding["reason"] = _config06_phase_locks(
                    report_path, report, matching[0], finding)
            elif case_id == "TC-TM001-UPDATE-04":
                finding["state"], finding["reason"] = _update04_no_native_handoff(
                    report_path, report, matching[0], finding)
            elif case_id == "TC-TM001-UPDATE-01":
                finding["state"], finding["reason"] = _update01_discovery_only(
                    report_path, report, matching[0], finding)
            elif case_id == "TC-TM001-UPDATE-07":
                finding["state"], finding["reason"] = _update07_full_open_files(
                    report_path, report, matching[0], finding)
            elif case_id == "TC-TM001-ADMIN-03":
                _, descriptor = _events(report_path, report, matching[0], case_id, (1, 2, 3, 4))
                finding["evidence"]["events"] = descriptor
                finding["state"], finding["reason"] = "PASS", "All four original steps are bound; no additional coverage gap is claimed"
            elif case_id == "TC-TM001-PASSWORD-05":
                finding["state"], finding["reason"] = _password05_peer_binding(
                    report_path, report, matching[0], finding)
        except EvidenceMissing as error:
            finding["state"], finding["reason"] = "BLOCKED", str(error)
        except (EvidenceInvalid, UnicodeError, json.JSONDecodeError, TypeError, AttributeError, KeyError) as error:
            finding["state"], finding["reason"] = "FAIL", str(error)
        findings.append(finding)
    if _digest(report_path) != hashlib.sha256(raw).hexdigest():
        raise EvidenceInvalid("Original report changed during independent audit")
    states = {item["state"] for item in findings}
    return {"schema_version": 2, "verifier": "granular-evidence-audit-v2",
            "run_id": run_id, "source_commit": report.get("source_commit"),
            "source_report_sha256": hashlib.sha256(raw).hexdigest(),
            "auditor_code_sha256": _digest(Path(__file__)),
            "audited_cases": audited_cases, "findings": findings,
            "state": "FAIL" if "FAIL" in states else "BLOCKED" if "BLOCKED" in states else "PASS"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--case-id")
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    verdict = audit(options.report, options.case_id) if options.case_id else audit_run(options.report)
    options.output.parent.mkdir(parents=True, exist_ok=True)
    if not options.case_id:
        source = Path(__file__).resolve(strict=True)
        snapshot = options.output.parent / "audit-code" / source.name
        snapshot.parent.mkdir(mode=0o700, exist_ok=True)
        with source.open("rb") as reader, snapshot.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
        os.chmod(snapshot, 0o600)
        content = snapshot.read_bytes()
        verifier_digest = hashlib.sha256(content).hexdigest()
        if verifier_digest != verdict["auditor_code_sha256"]:
            raise EvidenceInvalid("Auditor source changed while taking its run snapshot")
        verdict["auditor_code"] = {"path": "audit-code/" + source.name,
                                  "sha256": verifier_digest, "bytes": len(content)}
    descriptor = os.open(options.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as target:
        json.dump(verdict, target, ensure_ascii=False, sort_keys=True, indent=2)
        target.write("\n")
    print(json.dumps({"state": verdict["state"], "audited_cases": verdict.get("audited_cases", [verdict.get("case_id")]),
                      "output": str(options.output)}, ensure_ascii=False))
    return 0 if verdict["state"] in ("PASS", "NOT_APPLICABLE") else 2 if verdict["state"] == "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
