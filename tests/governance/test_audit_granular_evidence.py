"""A delayed old /me must never stand in for a new UI refresh."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/audit_granular_evidence.py"
CASE = "TC-TM001-SESSION-04"


def load_auditor():
    spec = importlib.util.spec_from_file_location("granular_evidence_auditor", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def fixture(directory: Path, *, add_new: bool, probe: bool = False,
            new_status: int = 200, tamper: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    case_dir = directory / CASE
    case_dir.mkdir()
    events = case_dir / "events.jsonl"
    events.write_text("".join(json.dumps({"run_id": "run-1", "case_id": CASE,
        "step": step, "action": "owned UI operation", "expected": True,
        "actual": True, "passed": True, "source": "ui", "timestamp": timestamp}) + "\n"
        for step, timestamp in [(3, "2026-09-30T10:00:00Z"), (4, "2026-09-30T10:00:30Z")]))
    requests = [{"method": "GET", "route": "/v1/me", "mode": "delay", "probe": False,
        "forwarded": True, "status": 200, "received_at": "2026-09-30T10:00:05Z",
        "finished_at": "2026-09-30T10:00:21Z"}]
    if add_new:
        requests.append({"method": "GET", "route": "/v1/me", "mode": "normal", "probe": probe,
            "forwarded": True, "status": new_status, "received_at": "2026-09-30T10:00:22Z",
            "finished_at": "2026-09-30T10:00:23Z"})
    transport = case_dir / "transport-audit.json"
    transport.write_text(json.dumps({"run_id": "run-1", "case_id": CASE,
        "origins": [{"origin": "http://127.0.0.1:12345", "requests": requests, "controls": []}]}))
    def descriptor(path: Path) -> dict:
        return {"path": path.relative_to(directory).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    report = directory / "result.json"
    report.write_text(json.dumps({"run_id": "run-1", "tc_results": [{"case_id": CASE,
        "state": "PASS", "evidence": {"events": descriptor(events),
        "transport_audit": descriptor(transport)}}]}))
    if tamper:
        transport.write_text(transport.read_text() + " ")
    return report


class GranularEvidenceAuditTests(unittest.TestCase):
    def test_delayed_old_response_alone_blocks_new_refresh_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            verdict = load_auditor().audit(fixture(Path(temp), add_new=False), CASE)
            self.assertEqual(verdict["state"], "BLOCKED")
            self.assertEqual(verdict["normal_me_200_count"], 0)

    def test_independent_normal_me_200_closes_gap(self):
        with tempfile.TemporaryDirectory() as temp:
            verdict = load_auditor().audit(fixture(Path(temp), add_new=True), CASE)
            self.assertEqual(verdict["state"], "PASS")
            self.assertEqual(verdict["normal_me_200_count"], 1)
            self.assertEqual(verdict["delayed_me_count"], 1)

    def test_probe_or_failure_cannot_substitute_for_app_refresh(self):
        with tempfile.TemporaryDirectory() as temp:
            verdict = load_auditor().audit(fixture(Path(temp), add_new=True, probe=True), CASE)
            self.assertEqual(verdict["state"], "BLOCKED")
        with tempfile.TemporaryDirectory() as temp:
            verdict = load_auditor().audit(fixture(Path(temp), add_new=True, new_status=0), CASE)
            self.assertEqual(verdict["state"], "BLOCKED")

    def test_tampered_claimed_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            verdict = load_auditor().audit(fixture(Path(temp), add_new=True, tamper=True), CASE)
            self.assertEqual(verdict["state"], "FAIL")

    def test_batch_audit_requires_new_b_me_after_step_three(self):
        with tempfile.TemporaryDirectory() as temp:
            report = batch_fixture(Path(temp), new_b_me=False)
            result = load_auditor().audit_run(report)
            finding = next(item for item in result["findings"] if item["case_id"] == "TC-TM001-CONFIG-03")
            self.assertEqual(finding["state"], "BLOCKED")
        with tempfile.TemporaryDirectory() as temp:
            report = batch_fixture(Path(temp), new_b_me=True)
            result = load_auditor().audit_run(report)
            finding = next(item for item in result["findings"] if item["case_id"] == "TC-TM001-CONFIG-03")
            self.assertEqual(finding["state"], "PASS")
            self.assertEqual(finding["evidence"]["transport_audit"]["sha256"],
                             hashlib.sha256((report.parent / "TC-TM001-CONFIG-03/transport-audit.json").read_bytes()).hexdigest())

    def test_batch_audit_blocks_tautological_lsof_and_preserves_failed_case(self):
        with tempfile.TemporaryDirectory() as temp:
            report = batch_fixture(Path(temp), new_b_me=True, update07_pass=True)
            result = load_auditor().audit_run(report)
            findings = {item["case_id"]: item for item in result["findings"]}
            self.assertEqual(findings["TC-TM001-UPDATE-07"]["state"], "BLOCKED")
            self.assertEqual(findings["TC-TM001-PASSWORD-05"]["state"], "NOT_APPLICABLE")
            self.assertIn("test_setup", findings["TC-TM001-PASSWORD-05"]["reason"])
            self.assertEqual(result["audited_cases"], [item["case_id"] for item in result["findings"]])

    def test_batch_audit_rejects_tampered_frozen_test_source(self):
        with tempfile.TemporaryDirectory() as temp:
            report = batch_fixture(Path(temp), new_b_me=True)
            source = report.parent / "test-code/apps/desktop/e2e/granular-config.spec.ts"
            source.write_text(source.read_text() + "changed")
            result = load_auditor().audit_run(report)
            finding = next(item for item in result["findings"] if item["case_id"] == "TC-TM001-CONFIG-03")
            self.assertEqual(finding["state"], "FAIL")

    def test_batch_audit_rejects_wrong_b_credential_after_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            report = batch_fixture(Path(temp), new_b_me=True)
            transport = report.parent / "TC-TM001-CONFIG-03/transport-audit.json"
            data = json.loads(transport.read_text())
            data["origins"][1]["requests"][-1]["authorization_sha256"] = "c" * 64
            transport.write_text(json.dumps(data))
            manifest = json.loads(report.read_text())
            target = next(row for row in manifest["tc_results"] if row["case_id"] == "TC-TM001-CONFIG-03")
            target["evidence"]["transport_audit"] = descriptor(report.parent, transport)
            report.write_text(json.dumps(manifest))
            result = load_auditor().audit_run(report)
            finding = next(item for item in result["findings"] if item["case_id"] == "TC-TM001-CONFIG-03")
            self.assertEqual(finding["state"], "BLOCKED")

    def test_config02_per_origin_readback_is_required(self):
        for variant, expected in (("complete", "PASS"), ("missing_ui", "BLOCKED"),
                                  ("missing_invalid", "BLOCKED"), ("tampered", "FAIL")):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                report = config_readback_fixture(Path(temp), "TC-TM001-CONFIG-02", variant)
                finding = load_auditor().audit_run(report)["findings"][0]
                self.assertEqual(finding["state"], expected)

    def test_config04_each_feed_requires_ui_file_and_restart_readback(self):
        for variant, expected in (("complete", "PASS"), ("missing_restart", "BLOCKED"),
                                  ("wrong_error", "BLOCKED"), ("tampered", "FAIL")):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                report = config_readback_fixture(Path(temp), "TC-TM001-CONFIG-04", variant)
                finding = load_auditor().audit_run(report)["findings"][0]
                self.assertEqual(finding["state"], expected)

    def test_default_boundary_audit_requires_pre_entry_observation(self):
        for case, broken in (("TC-TM001-CONFIG-01", "default_request"),
                             ("TC-TM001-CONFIG-05", "missing_launch")):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                good = observed_boundary_fixture(Path(temp) / "good", case)
                self.assertEqual(load_auditor().audit_run(good)["findings"][0]["state"], "PASS")
            with self.subTest(case=case, variant=broken), tempfile.TemporaryDirectory() as temp:
                bad = observed_boundary_fixture(Path(temp) / "bad", case, broken)
                self.assertEqual(load_auditor().audit_run(bad)["findings"][0]["state"], "BLOCKED")

    def test_config06_requires_every_phase_and_autonomous_process(self):
        for variant, expected in (("complete", "PASS"), ("missing_ready", "BLOCKED"),
                                  ("missing_process", "BLOCKED")):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                report = observed_boundary_fixture(Path(temp), "TC-TM001-CONFIG-06", variant)
                self.assertEqual(load_auditor().audit_run(report)["findings"][0]["state"], expected)

    def test_update04_rejects_native_handoff_on_bad_signature(self):
        for variant, expected in (("complete", "PASS"), ("native_handoff", "BLOCKED"),
                                  ("missing_zip", "BLOCKED")):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                report = observed_boundary_fixture(Path(temp), "TC-TM001-UPDATE-04", variant)
                self.assertEqual(load_auditor().audit_run(report)["findings"][0]["state"], expected)

    def test_update01_discovery_only_has_no_archive_or_native_handoff(self):
        for variant, expected in (("complete", "PASS"), ("archive_egress", "BLOCKED"),
                                  ("native_handoff", "BLOCKED")):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                report = observed_boundary_fixture(Path(temp), "TC-TM001-UPDATE-01", variant)
                self.assertEqual(load_auditor().audit_run(report)["findings"][0]["state"], expected)

    def test_update07_requires_unfiltered_lsof_evidence(self):
        for variant, expected in (("complete", "PASS"), ("filtered", "BLOCKED"),
                                  ("default_open", "BLOCKED")):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                report = update07_full_lsof_fixture(Path(temp), variant)
                self.assertEqual(load_auditor().audit_run(report)["findings"][0]["state"], expected)

    def test_cli_saves_auditor_code_snapshot_beside_immutable_report(self):
        with tempfile.TemporaryDirectory() as temp:
            report = batch_fixture(Path(temp) / "raw", new_b_me=True)
            before = hashlib.sha256(report.read_bytes()).hexdigest()
            output = Path(temp) / "audit" / "audit.json"
            completed = subprocess.run([sys.executable, str(SCRIPT), "--report", str(report),
                                        "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 2)
            verdict = json.loads(output.read_text())
            snapshot = output.parent / verdict["auditor_code"]["path"]
            self.assertEqual(hashlib.sha256(snapshot.read_bytes()).hexdigest(), verdict["auditor_code"]["sha256"])
            self.assertEqual(verdict["source_report_sha256"], before)
            self.assertEqual(hashlib.sha256(report.read_bytes()).hexdigest(), before)

    def test_targeted_run_omits_cases_outside_declared_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            report = batch_fixture(Path(temp), new_b_me=True)
            data = json.loads(report.read_text())
            data["expected_cases"] = ["TC-TM001-PASSWORD-05"]
            data["tc_results"] = [item for item in data["tc_results"]
                                  if item["case_id"] == "TC-TM001-PASSWORD-05"]
            report.write_text(json.dumps(data))
            result = load_auditor().audit_run(report)
            self.assertEqual(result["audited_cases"], ["TC-TM001-PASSWORD-05"])
            self.assertEqual(result["findings"][0]["state"], "NOT_APPLICABLE")

    def test_password05_peer_binding_requires_separate_app_profile_and_restart_request(self):
        for variant, expected in (("valid", "PASS"), ("shared_app", "BLOCKED"),
                                  ("shared_profile", "BLOCKED"), ("missing_restart_me", "BLOCKED")):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                report, trusted = password_peer_fixture(Path(temp), variant)
                auditor = load_auditor()
                with patch.dict(auditor.PASSWORD05_PEER_SOURCES, trusted):
                    result = auditor.audit_run(report)
                self.assertEqual(result["audited_cases"], ["TC-TM001-PASSWORD-05"])
                finding = result["findings"][0]
                self.assertEqual(finding["state"], expected)
                if expected == "PASS":
                    self.assertEqual(finding["distinct_old_sessions"], 2)
                    self.assertIn("peer_trace_after", finding["evidence"])
                    self.assertIn("peer_runner_code", finding["evidence"])

    def test_password05_changed_frozen_peer_runner_cannot_inherit_review(self):
        with tempfile.TemporaryDirectory() as temp:
            report, trusted = password_peer_fixture(Path(temp), "valid")
            trusted["scripts/granular_e2e.py"] = "0" * 64
            auditor = load_auditor()
            with patch.dict(auditor.PASSWORD05_PEER_SOURCES, trusted):
                result = auditor.audit_run(report)
            self.assertEqual(result["findings"][0]["state"], "BLOCKED")
            self.assertIn("changed since its reviewed binding", result["findings"][0]["reason"])

    def test_password05_20261001_frozen_sources_need_whole_peer_review(self):
        reviewed = {
            "scripts/granular_e2e.py": "83872c29f7be845de0bac933e8a981615def0d4e4e1bd49948efcd0d738af21e",
            "scripts/local_e2e.py": "d43036d0cee91b06df325f0fd8c9a60067b198fb2702ee56cedc80fcd028dae1",
            "apps/desktop/e2e/granular-login.spec.ts": "0bd303133c7d3bd0452eac4359af45ff8a8d94295664af0aed500faacafbe5a2",
        }
        with tempfile.TemporaryDirectory() as temp:
            report, _ = password_peer_fixture(Path(temp), "valid")
            data = json.loads(report.read_text())
            frozen_bytes = {}
            for name, expected_sha in reviewed.items():
                original = (ROOT / name).read_bytes()
                self.assertEqual(hashlib.sha256(original).hexdigest(), expected_sha,
                                 "Source changed; review its peer fixture behavior before accepting a new triple")
                frozen_bytes[name] = original
                target = report.parent / "test-code" / name
                target.write_bytes(original)
                source_descriptor = descriptor(report.parent, target)
                index = next(index for index, row in enumerate(data["test_code_snapshot"])
                             if row["path"] == "test-code/" + name)
                data["test_code_snapshot"][index] = source_descriptor
                data["test_inputs_sha256"][name] = source_descriptor["sha256"]
            report.write_text(json.dumps(data))
            auditor = load_auditor()
            finding = auditor.audit_run(report)["findings"][0]
            self.assertEqual(finding["state"], "PASS", finding["reason"])
            self.assertEqual(finding["distinct_old_sessions"], 2)

            for name, original in frozen_bytes.items():
                with self.subTest(changed_source=name):
                    target = report.parent / "test-code" / name
                    target.write_bytes(original + b"\nreview pending\n")
                    changed = json.loads(json.dumps(data))
                    source_descriptor = descriptor(report.parent, target)
                    index = next(index for index, row in enumerate(changed["test_code_snapshot"])
                                 if row["path"] == "test-code/" + name)
                    changed["test_code_snapshot"][index] = source_descriptor
                    changed["test_inputs_sha256"][name] = source_descriptor["sha256"]
                    report.write_text(json.dumps(changed))
                    finding = auditor.audit_run(report)["findings"][0]
                    self.assertEqual(finding["state"], "BLOCKED")
                    self.assertIn("changed since its reviewed binding", finding["reason"])
                    target.write_bytes(original)
                    report.write_text(json.dumps(data))

    def test_password05_runner_allowlist_rejects_mixed_reviewed_combinations(self):
        with tempfile.TemporaryDirectory() as temp:
            report, old = password_peer_fixture(Path(temp), "valid")
            source = report.parent / "test-code/scripts/granular_e2e.py"
            source.write_text("second reviewed runner peer behavior unchanged")
            new_runner = descriptor(report.parent, source)["sha256"]
            source_local = report.parent / "test-code/scripts/local_e2e.py"
            new_local_text = "second reviewed installer peer behavior unchanged"
            new_local = hashlib.sha256(new_local_text.encode()).hexdigest()
            whole_new = {**old, "scripts/granular_e2e.py": new_runner,
                         "scripts/local_e2e.py": new_local}
            data = json.loads(report.read_text())
            for name, digest in (("scripts/granular_e2e.py", new_runner),):
                data["test_inputs_sha256"][name] = digest
                index = next(index for index, row in enumerate(data["test_code_snapshot"])
                             if row["path"] == "test-code/" + name)
                data["test_code_snapshot"][index] = descriptor(report.parent, report.parent / "test-code" / name)
            report.write_text(json.dumps(data))
            auditor = load_auditor()
            with patch.object(auditor, "PASSWORD05_PEER_SOURCE_SETS", (old, whole_new)):
                self.assertEqual(auditor.audit_run(report)["findings"][0]["state"], "BLOCKED")
                name = "scripts/local_e2e.py"
                source_local.write_text(new_local_text)
                data["test_inputs_sha256"][name] = new_local
                index = next(index for index, row in enumerate(data["test_code_snapshot"])
                             if row["path"] == "test-code/" + name)
                data["test_code_snapshot"][index] = descriptor(report.parent, source_local)
                report.write_text(json.dumps(data))
                self.assertEqual(auditor.audit_run(report)["findings"][0]["state"], "PASS")
                source.write_text("reviewed fixed source: scripts/granular_e2e.py")
                name = "scripts/granular_e2e.py"
                data["test_inputs_sha256"][name] = old[name]
                index = next(index for index, row in enumerate(data["test_code_snapshot"])
                             if row["path"] == "test-code/" + name)
                data["test_code_snapshot"][index] = descriptor(report.parent, source)
                report.write_text(json.dumps(data))
                self.assertEqual(auditor.audit_run(report)["findings"][0]["state"], "BLOCKED")


def password_peer_fixture(directory: Path, variant: str) -> tuple[Path, dict[str, str]]:
    """Synthetic immutable run with three separate launch-context traces."""
    case = "TC-TM001-PASSWORD-05"
    case_dir = directory / case
    case_dir.mkdir(parents=True)
    sources = ("scripts/granular_e2e.py", "scripts/local_e2e.py",
               "apps/desktop/e2e/granular-login.spec.ts")
    trusted = {}
    snapshots = []
    for source in sources:
        target = directory / "test-code" / source
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("reviewed fixed source: " + source)
        snapshots.append(descriptor(directory, target))
        trusted[source] = snapshots[-1]["sha256"]
    expected = (
        {"identity": True, "mustChange": False, "role": "成员", "sessions": 1},
        {"old1": 401, "old2": 401, "newSession": 200, "identity": True},
        {"old": 401, "new": 200, "changedAudit": 1, "role": "member"},
        {"loginVisible": True, "savedCredential": False, "oldSession": 401},
    )
    timestamps = ("2026-09-30T10:00:01Z", "2026-09-30T10:00:05Z",
                  "2026-09-30T10:00:10Z", "2026-09-30T10:00:20Z")
    events = case_dir / "events.jsonl"
    events.write_text("".join(json.dumps({"run_id": "run-1", "case_id": case, "step": index,
        "action": "fixed product operation", "source": "ui", "expected": values,
        "actual": values, "passed": True, "timestamp": timestamps[index-1]}) + "\n"
        for index, values in enumerate(expected, 1)))
    root = directory / ".local" / "local-granular-work" / "run-1-abcdef" / case
    main_exe = root / "installation/TokenMeter.app/Contents/MacOS/TokenMeter"
    peer_exe = root / "peer-installation/TokenMeter.app/Contents/MacOS/TokenMeter"
    main_profile = root / "profile"
    peer_profile = root / "peer-profile"
    for name, binary, profile in (
        ("trace-01.zip", main_exe, main_profile),
        ("trace-second-before-restart.zip", main_exe if variant == "shared_app" else peer_exe,
         main_profile if variant == "shared_profile" else peer_profile),
        ("trace-second-after-restart.zip", peer_exe, peer_profile),
    ):
        options = {"executablePath": str(binary), "args": ["--user-data-dir=" + str(profile)],
                   "chromiumSandbox": True}
        record = {"type": "context-options", "options": options}
        with ZipFile(case_dir / name, "w") as archive:
            archive.writestr("trace.trace", json.dumps(record, separators=(",", ":")) + "\n")
    def req(method: str, route: str, status: int, at: str, *, fingerprint=None,
            probe=False) -> dict:
        return {"method": method, "route": route, "status": status, "mode": "normal",
                "forwarded": True, "probe": probe, "authorization_sha256": fingerprint,
                "received_at": at, "finished_at": at}
    requests = [
        req("POST", "/v1/auth/login", 200, "2026-09-30T09:59:00Z"),
        req("POST", "/v1/auth/login", 200, "2026-09-30T09:59:10Z"),
        req("POST", "/v1/auth/change-password", 200, "2026-09-30T10:00:00Z"),
        req("GET", "/v1/me", 401, "2026-09-30T10:00:02Z", fingerprint="a" * 64, probe=True),
        req("GET", "/v1/me", 401, "2026-09-30T10:00:03Z", fingerprint="b" * 64, probe=True),
        req("GET", "/v1/me", 200, "2026-09-30T10:00:04Z", fingerprint="c" * 64, probe=True),
    ]
    if variant != "missing_restart_me":
        requests.append(req("GET", "/v1/me", 401, "2026-09-30T10:00:15Z", fingerprint="b" * 64))
    transport = case_dir / "transport-audit.json"
    transport.write_text(json.dumps({"run_id": "run-1", "case_id": case,
        "origins": [{"origin": "http://127.0.0.1:31234", "requests": requests}]}))
    report = directory / "result.json"
    report.write_text(json.dumps({"run_id": "run-1", "source_commit": "d" * 40,
        "expected_cases": [case], "test_inputs_sha256": trusted,
        "test_code_snapshot": snapshots, "tc_results": [{"case_id": case, "state": "PASS",
        "evidence": {"events": descriptor(directory, events),
                     "trace": descriptor(directory, case_dir / "trace-01.zip"),
                     "transport_audit": descriptor(directory, transport)}}]}))
    return report, trusted


def config_readback_fixture(directory: Path, case: str, variant: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "test-code/apps/desktop/e2e/granular-config.spec.ts"
    source.parent.mkdir(parents=True)
    source.write_text("frozen granular CONFIG test source")
    launcher = directory / "test-code/apps/desktop/e2e/main-observer.ts"
    collector = directory / "test-code/apps/desktop/e2e/main-observer.cjs"
    launcher.write_text("frozen pre-entry inspector launcher")
    collector.write_text("frozen delegated request collector")
    case_dir = directory / case
    case_dir.mkdir()
    if case.endswith("02"):
        valid = ["http://127.0.0.1:49176", "http://localhost:49176",
                 "http://[::1]:49176", "https://example.invalid"]
        step1 = [{"input": value, "canonical": value, "ui": value,
                  "fileOverride": None if index == 0 else value, "requestDelta": 0}
                 for index, value in enumerate(valid)]
        if variant == "missing_ui":
            step1[2].pop("ui")
        invalid = ["http://example.invalid", "http://127.1:49176",
                   "http://2130706433:49176", "http://", "http://127.0.0.1:65536",
                   "http://user:pass@127.0.0.1:49176", "http://127.0.0.1:49176/path",
                   "http://127.0.0.1:49176?x=1", "http://127.0.0.1:49176/#f"]
        step2 = [{"input": value, "error": "请输入 HTTPS 服务地址或本机回环 HTTP 地址（invalid_server_url）",
                  "fileSha": "a" * 64, "server": valid[-1], "ownedAuthCount": 0,
                  "mainRequestCount": 0}
                 for value in invalid]
        if variant == "missing_invalid":
            step2.pop()
        step3 = {"first": valid[-1], "second": valid[-1], "uiA": valid[-1],
                 "uiB": valid[-1], "sameCredentialPath": True}
        step4 = {"origin": "http://127.0.0.1:34567", "ui": "http://127.0.0.1:34567",
                 "differentCredentialPath": True, "newCredentialPresent": False}
    else:
        local = "http://127.0.0.1:34567/version.json"
        remote = "https://updates.example.invalid/version.json"
        step1 = [{"input": value, "ui": value, "file": value,
                  "afterRestartUi": value, "afterRestartFile": value, "requestDelta": 0}
                 for value in (local, remote)]
        if variant == "missing_restart":
            step1[1].pop("afterRestartUi")
        invalid = ["http://example.invalid/version.json", "http://",
                   "http://user:pass@127.0.0.1/version.json",
                   "http://127.0.0.1/version.json?", "http://127.0.0.1/version.json#",
                   "http://127.0.0.1:65536/version.json", "http://127.1/version.json",
                   "http://2130706433/version.json"]
        step2 = [{"input": value, "error": "更新地址无效，仅支持 HTTPS 或本机回环 HTTP（update_source_rejected）",
                  "fileSha": "b" * 64, "feed": remote, "ownedAuthCount": 0,
                  "mainRequestCount": 0}
                 for value in invalid]
        if variant == "wrong_error":
            step2[0]["error"] = "other error"
        step3 = {"publicKeyPinned": True, "noKeyEditor": True}
        step4 = remote
    events = case_dir / "events.jsonl"
    records = []
    for step, values in enumerate((step1, step2, step3, step4), 1):
        records.append({"run_id": "run-1", "case_id": case, "step": step,
                        "action": "fixed App/UI operation", "expected": values,
                        "actual": values, "passed": True, "source": "filesystem",
                        "timestamp": f"2026-09-30T10:00:0{step}Z"})
    events.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records))
    observer = case_dir / "main-observer.jsonl"
    launches = 1 if case.endswith("02") else 4
    observer_rows = []
    for number in range(launches):
        observer_rows.append({"run_id": "run-1", "case_id": case,
            "launch_id": f"launch-{number}", "pid": 2000 + number, "sequence": 1,
            "time": f"2026-09-30T09:59:{number:02d}Z", "kind": "installed-before-entry",
            "source_sha256": descriptor(directory, collector)["sha256"]})
    observer.write_text("".join(json.dumps(row) + "\n" for row in observer_rows))
    report = directory / "result.json"
    report.write_text(json.dumps({"run_id": "run-1", "source_commit": "c" * 40,
        "expected_cases": [case], "test_inputs_sha256": {
            "apps/desktop/e2e/granular-config.spec.ts": descriptor(directory, source)["sha256"],
            "apps/desktop/e2e/main-observer.ts": descriptor(directory, launcher)["sha256"],
            "apps/desktop/e2e/main-observer.cjs": descriptor(directory, collector)["sha256"]},
        "test_code_snapshot": [descriptor(directory, source), descriptor(directory, launcher),
                               descriptor(directory, collector)],
        "tc_results": [{"case_id": case, "state": "PASS",
                        "evidence": {"events": descriptor(directory, events),
                                     "main_observer": descriptor(directory, observer)}}]}))
    if variant == "tampered":
        events.write_text(events.read_text() + " ")
    return report


def observed_boundary_fixture(directory: Path, case: str, variant: str = "complete") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    spec_name = "granular-update.spec.ts" if "UPDATE" in case else "granular-config.spec.ts"
    paths = [f"apps/desktop/e2e/{spec_name}", "apps/desktop/e2e/main-observer.ts",
             "apps/desktop/e2e/main-observer.cjs"]
    sources = []
    for name in paths:
        file = directory / "test-code" / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("frozen fixed source " + name)
        sources.append(file)
    case_dir = directory / case
    case_dir.mkdir()
    default = {"api": "http://127.0.0.1:49176",
               "feed": "http://127.0.0.1:49177/version.json"}
    owned = "http://127.0.0.1:34567"
    if case.endswith("CONFIG-01"):
        values = [
            {"ui": default, "signed": default},
            {"unauthenticated": True, "ownedAuthenticationRequests": 0,
             "observerArmed": True, "defaultRequests": 0},
            {"origin": owned, "ownedLogin": True, "observedLogin": True},
            {"api": owned, "observerLaunches": 2, "defaultRequests": 0},
        ]
    elif case.endswith("CONFIG-05"):
        values = [
            {"server": owned, "feed": owned + "/a.json"},
            {"server": owned, "feed": owned + "/a.json"},
            True,
            {"ui": default, "observerLaunches": 4, "defaultRequests": 0},
            True,
        ]
    elif case.endswith("CONFIG-06"):
        values = [
            {"api": True, "feed": False, "reset": True},
            {"api": True, "feed": False, "reset": True},
            {"api": False, "feed": False, "reset": False},
            {"firstDownloadLocked": True, "allPhases": True, "stateLocked": True,
             "uiStayedLocked": True, "autonomousNewPid": True, "feedUnchanged": True},
            {"preHandoffCancelRestored": True, "handoffNoCancel": True},
        ]
    elif case.endswith("UPDATE-01"):
        values = [
            {"defaultApi": True, "defaultFeed": True,
             "unauthenticated": True, "noPrematureCheck": True},
            {"autoCurrent": True, "idleRequest": True,
             "noArchive": True, "verified": True},
            {"versionOffered": True, "build100": True,
             "validMetadataRead": True, "noArchive": True},
            {"noArchive": True, "noNativeCache": True,
             "oldProcessOnly": True, "oldAppTree": True,
             "installStillRequiresClick": True, "observerBeforeEntry": True,
             "observedEgressOnlyOwned": True, "observedMetadataOnly": True,
             "nativeHandoffCount": 0},
        ]
    else:
        values = [
            {"sourceReady": True, "productMetadata": True, "archiveCount": 1,
             "completeBytes": True, "matchingSha": True},
            {"signatureRejected": True, "keyUnchanged": True, "build100": True},
            {"samePid": True, "sameTree": True, "oldBuild": True,
             "verifiedSession": True, "observerBeforeEntry": True, "nativeHandoffCount": 0},
            {"temporaryDownloads": 0, "noHigherApp": True,
             "sourceEvidence": True, "noPrivateKeyInEvents": True},
        ]
    events = case_dir / "events.jsonl"
    events.write_text("".join(json.dumps({"run_id": "run-1", "case_id": case, "step": index,
        "action": "fixed App operation", "expected": value, "actual": value, "passed": True,
        "source": "ui", "timestamp": f"2026-09-30T10:00:0{index}Z"}, ensure_ascii=False) + "\n"
        for index, value in enumerate(values, 1)))

    collector_sha = descriptor(directory, sources[-1])["sha256"]
    launches = 2 if case.endswith("CONFIG-01") else 4 if case.endswith("CONFIG-05") else 1
    if variant == "missing_launch":
        launches -= 1
    rows = []
    for index in range(launches):
        rows.append({"run_id": "run-1", "case_id": case, "launch_id": f"launch-{index}",
                     "pid": 3000 + index, "sequence": 1,
                     "time": f"2026-09-30T09:59:{index:02d}Z",
                     "kind": "installed-before-entry", "source_sha256": collector_sha})
        if case.endswith("CONFIG-01") and index == 0:
            rows.append({"run_id": "run-1", "case_id": case, "launch_id": "launch-0",
                         "pid": 3000, "sequence": 2, "time": "2026-09-30T10:00:02Z",
                         "kind": "request", "origin": owned, "path": "/v1/auth/login", "method": "POST"})
        if case.endswith("UPDATE-01"):
            rows.extend([
                {"run_id": "run-1", "case_id": case, "launch_id": "launch-0",
                 "pid": 3000, "sequence": 2, "time": "2026-09-30T10:00:02Z",
                 "kind": "request", "origin": owned, "path": "/v1/auth/login", "method": "POST"},
                {"run_id": "run-1", "case_id": case, "launch_id": "launch-0",
                 "pid": 3000, "sequence": 3, "time": "2026-09-30T10:00:03Z",
                 "kind": "request", "origin": "http://127.0.0.1:34568",
                 "path": "/version.json", "method": "GET"},
            ])
    if variant == "default_request":
        rows.append({"run_id": "run-1", "case_id": case, "launch_id": "launch-0",
                     "pid": 3000, "sequence": 3, "time": "2026-09-30T10:00:03Z",
                     "kind": "request", "origin": default["api"], "path": "/v1/auth/login", "method": "POST"})
    if case.endswith("CONFIG-06"):
        for index, method in enumerate(("setFeedURL", "checkForUpdates", "quitAndInstall"), 2):
            rows.append({"run_id": "run-1", "case_id": case, "launch_id": "launch-0",
                         "pid": 3000, "sequence": index,
                         "time": f"2026-09-30T10:00:1{index}Z",
                         "kind": "native-updater", "method": method})
    if case.endswith("UPDATE-04") and variant != "missing_zip":
        rows.append({"run_id": "run-1", "case_id": case, "launch_id": "launch-0",
                     "pid": 3000, "sequence": 2, "time": "2026-09-30T10:00:02Z",
                     "kind": "request", "origin": owned, "path": "/update.zip", "method": "GET"})
    if variant == "native_handoff":
        rows.append({"run_id": "run-1", "case_id": case, "launch_id": "launch-0",
                     "pid": 3000, "sequence": 4 if case.endswith("UPDATE-01") else 3,
                     "time": "2026-09-30T10:00:04Z",
                     "kind": "native-updater", "method": "setFeedURL"})
    if variant == "archive_egress":
        rows.append({"run_id": "run-1", "case_id": case, "launch_id": "launch-0",
                     "pid": 3000, "sequence": 4, "time": "2026-09-30T10:00:04Z",
                     "kind": "request", "origin": "http://127.0.0.1:34568",
                     "path": "/update.zip", "method": "GET"})
    observer = case_dir / "main-observer.jsonl"
    observer.write_text("".join(json.dumps(row) + "\n" for row in rows))
    evidence = {"events": descriptor(directory, events),
                "main_observer": descriptor(directory, observer)}
    if case.endswith("CONFIG-06"):
        phases = ["downloading", "verifying", "ready", "installing"]
        if variant == "missing_ready":
            phases.remove("ready")
        raw = []
        for index, phase in enumerate(phases, 1):
            raw.append({"run_id": "run-1", "case_id": case, "segment": "upgrade",
                        "sequence": index, "kind": "snapshot", "phase": phase,
                        "canConfigure": False, "feedDisabled": True, "resetDisabled": True,
                        "cancelVisible": phase in ("downloading", "verifying")})
        raw.append({"run_id": "run-1", "case_id": case, "segment": "upgrade",
                    "sequence": len(raw) + 1, "kind": "dom", "phase": "installing",
                    "canConfigure": False, "feedDisabled": True, "resetDisabled": True,
                    "cancelVisible": False})
        phase_file = case_dir / "config-phase-observations.jsonl"
        phase_file.write_text("".join(json.dumps(row) + "\n" for row in raw))
        evidence["config_phase_observations"] = descriptor(directory, phase_file)
        process_file = case_dir / "config-upgrade-process.json"
        process_file.write_text(json.dumps({"run_id": "run-1", "case_id": case,
            "old_pid": 3000, "new_pid": 3001, "runner_launches_before": 1,
            "runner_launches_after": 1,
            "observed_phases": ["downloading", "verifying", "ready", "installing"]}))
        if variant != "missing_process":
            evidence["config_upgrade_process"] = descriptor(directory, process_file)
    report = directory / "result.json"
    report.write_text(json.dumps({"run_id": "run-1", "source_commit": "c" * 40,
        "expected_cases": [case],
        "test_inputs_sha256": {name: descriptor(directory, source)["sha256"]
                               for name, source in zip(paths, sources)},
        "test_code_snapshot": [descriptor(directory, source) for source in sources],
        "tc_results": [{"case_id": case, "state": "PASS", "evidence": evidence}]}))
    return report


def update07_full_lsof_fixture(directory: Path, variant: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    case = "TC-TM001-UPDATE-07"
    source = directory / "test-code/apps/desktop/e2e/granular-update.spec.ts"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("fixed unfiltered lsof source")
    case_dir = directory / case
    case_dir.mkdir()
    event = case_dir / "events.jsonl"
    expected = {"newPidOwnsProfile": True, "originCredentialOwned": True,
                "noUserProfile": True}
    event.write_text(json.dumps({"run_id": "run-1", "case_id": case, "step": 5,
        "action": "read complete lsof list", "source": "process", "expected": expected,
        "actual": expected, "passed": True, "timestamp": "2026-09-30T10:00:05Z"}) + "\n")
    root = "/private/tmp/tokenmeter-run/profile"
    default = "/Users/example/Library/Application Support/TokenMeter"
    owned = [root + "/chromium/Cache/index", root + "/logs/main.log"]
    paths = owned + ["/usr/lib/libSystem.B.dylib", "/System/Library/CoreServices/CoreTypes.bundle"]
    if variant == "filtered":
        paths = owned
    if variant == "default_open":
        paths.append(default + "/settings.json")
    process = case_dir / "process-open-files.json"
    process.write_text(json.dumps({"run_id": "run-1", "case_id": case, "pid": 3001,
        "observed_at": "2026-09-30T10:00:05Z", "all_open_paths": paths,
        "owned_profile_paths": owned, "default_profile": default,
        "default_profile_paths": [] if variant != "default_open" else [default + "/settings.json"]}))
    report = directory / "result.json"
    report.write_text(json.dumps({"run_id": "run-1", "source_commit": "c" * 40,
        "expected_cases": [case],
        "test_inputs_sha256": {"apps/desktop/e2e/granular-update.spec.ts": descriptor(directory, source)["sha256"]},
        "test_code_snapshot": [descriptor(directory, source)],
        "tc_results": [{"case_id": case, "state": "PASS",
            "evidence": {"events": descriptor(directory, event),
                         "process_open_files": descriptor(directory, process)}}]}))
    return report


def batch_fixture(directory: Path, *, new_b_me: bool, update07_pass: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    cases = ["TC-TM001-SESSION-04", "TC-TM001-CONFIG-02", "TC-TM001-CONFIG-03",
             "TC-TM001-CONFIG-04", "TC-TM001-UPDATE-01", "TC-TM001-UPDATE-07",
             "TC-TM001-PASSWORD-05", "TC-TM001-ADMIN-03"]
    mapping = {"SESSION": "granular-account.spec.ts", "CONFIG": "granular-config.spec.ts",
               "UPDATE": "granular-update.spec.ts", "PASSWORD": "granular-login.spec.ts",
               "ADMIN": "granular-account.spec.ts"}
    snapshots = []
    inputs = {}
    for name in mapping.values():
        source = directory / "test-code/apps/desktop/e2e" / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("fixed test source " + name)
        snapshots.append(descriptor(directory, source))
        inputs["apps/desktop/e2e/" + name] = snapshots[-1]["sha256"]
    results = []
    for case in cases:
        group = case.split("-")[2]
        state = "PASS" if case == "TC-TM001-CONFIG-03" or (update07_pass and case == "TC-TM001-UPDATE-07") else "FAIL"
        evidence = {}
        if state == "PASS":
            case_dir = directory / case
            case_dir.mkdir()
            events = case_dir / "events.jsonl"
            steps = [3, 4] if group == "CONFIG" else [5]
            events.write_text("".join(json.dumps({"run_id": "run-1", "case_id": case,
                "step": step, "action": "fixed action", "expected": True, "actual": True,
                "passed": True, "source": "ui", "timestamp": timestamp}) + "\n"
                for step, timestamp in zip(steps, ["2026-09-30T10:00:00Z", "2026-09-30T10:00:30Z"])))
            evidence["events"] = descriptor(directory, events)
            if group == "CONFIG":
                reference = "a" * 64
                b_requests = [{"method": "GET", "route": "/v1/me", "mode": "normal",
                               "probe": True, "forwarded": True, "status": 200,
                               "authorization_sha256": reference,
                               "received_at": "2026-09-30T09:59:55Z", "finished_at": "2026-09-30T09:59:56Z"}]
                if new_b_me:
                    b_requests.append({"method": "GET", "route": "/v1/me", "mode": "normal",
                                       "probe": False, "forwarded": True, "status": 200,
                                       "authorization_sha256": reference,
                                       "received_at": "2026-09-30T10:00:20Z", "finished_at": "2026-09-30T10:00:21Z"})
                transport = case_dir / "transport-audit.json"
                transport.write_text(json.dumps({"run_id": "run-1", "case_id": case,
                    "origins": [{"origin": "http://127.0.0.1:11111", "requests": []},
                                {"origin": "http://127.0.0.1:22222", "requests": b_requests}]}))
                evidence["transport_audit"] = descriptor(directory, transport)
        elif case in ("TC-TM001-PASSWORD-05", "TC-TM001-ADMIN-03"):
            case_dir = directory / case
            case_dir.mkdir()
            raw = case_dir / "playwright.json"
            raw.write_text("TokenMeter unsafe_storage secondary-profile electron.launch" if group == "PASSWORD"
                           else "Cannot read properties of undefined bobApp.process().pid")
            evidence["playwright"] = descriptor(directory, raw)
            if group == "ADMIN":
                events = case_dir / "events.jsonl"
                events.write_text("".join(json.dumps({"run_id": "run-1", "case_id": case,
                    "step": step, "action": "fixed action", "expected": True, "actual": True,
                    "passed": True, "source": "ui", "timestamp": f"2026-09-30T10:00:0{step}Z"}) + "\n"
                    for step in (1, 2, 3, 4)))
                evidence["events"] = descriptor(directory, events)
        results.append({"case_id": case, "state": state, "evidence": evidence})
    report = directory / "result.json"
    report.write_text(json.dumps({"run_id": "run-1", "source_commit": "b" * 64,
        "expected_cases": cases, "test_inputs_sha256": inputs,
        "test_code_snapshot": snapshots, "tc_results": results}))
    return report


def descriptor(root: Path, file: Path) -> dict:
    return {"path": file.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "bytes": file.stat().st_size}


if __name__ == "__main__":
    unittest.main()
