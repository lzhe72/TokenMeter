#!/usr/bin/env python3
"""Run individually bound TM-001 test cases against an isolated installed DMG App.

Every catalog case receives its own result. Missing bindings and unresolved
expectations remain BLOCKED; a passing parent E2E scenario is never inherited.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import shlex
import socket
import sqlite3
import subprocess
import sys
import tempfile
import uuid

import local_e2e as base
from granular_service_fixture import ServiceFixture
from granular_update_target import DeniedTarget
import granular_bounds_fixture as bounds
from granular_shipit_probe import probe as shipit_probe


ROOT = Path(__file__).resolve().parents[1]
SPEC_BY_GROUP = {
    "LOGIN": "granular-login.spec.ts", "PASSWORD": "granular-login.spec.ts",
    "SESSION": "granular-account.spec.ts", "ADMIN": "granular-account.spec.ts",
    "BOOTSTRAP": "granular-account.spec.ts", "CONFIG": "granular-config.spec.ts",
    "UPDATE": "granular-update.spec.ts",
}


def case_spec(case_id: str) -> str | None:
    if case_id.startswith("TC-TM001-UPDATE-05#"):
        return "granular-update-validation.spec.ts"
    return SPEC_BY_GROUP.get(case_group(case_id))


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def case_group(case_id: str) -> str:
    parts = case_id.split("-")
    return parts[2] if len(parts) == 4 else ""


def private_case_name(case_id: str) -> str:
    """TC metadata keeps #variant; SQLite URI and App paths use a safe basename."""
    if not re.fullmatch(r"TC-TM001-[A-Z]+-\d{2}(?:#[A-Z0-9_]+)?", case_id):
        raise base.Failed("Invalid private TC identity")
    return case_id.replace("#", "--")


def blocked(case: dict, reason: str) -> dict:
    return {"case_id": case["id"], "state": "BLOCKED", "reason": reason,
            "task_ids": case.get("task_ids", []), "ac_ids": case.get("ac_ids", []),
            "step_results": [], "started_at": None, "finished_at": None, "evidence": {}}


def read_catalog() -> list[dict]:
    catalog = json.loads((ROOT / "tests/test_cases.json").read_text(encoding="utf-8"))
    cases = [item for item in catalog["cases"] if item.get("feature_id") == "TM-001"]
    identifiers = [item["id"] for item in cases]
    if len(cases) != 78 or len(set(identifiers)) != len(cases):
        raise base.Failed("TM-001 catalog count or unique identities changed; review test plan first")
    variants = []
    for variant_file in (ROOT / "tests/granular_login_variants.json", ROOT / "tests/granular_update_variants.json"):
        if variant_file.is_file():
            variants.extend(json.loads(variant_file.read_text(encoding="utf-8")).get("variants", []))
    by_id = {case["id"]: case for case in cases}
    by_parent: dict[str, list[dict]] = {}
    for variant in variants:
        parent = by_id.get(variant.get("parent_id"))
        identity = variant.get("id")
        if (parent is None or not isinstance(identity, str) or not identity.startswith(parent["id"] + "#")
                or identity in by_id or any(identity == item.get("id") for item in variants if item is not variant)):
            raise base.Failed("Granular variant manifest has an unknown or duplicate identity")
        by_parent.setdefault(parent["id"], []).append(variant)
    for parent_id, children in by_parent.items():
        required = {step["step"] for step in by_id[parent_id]["steps"]}
        covered = {number for child in children for number in child.get("step_numbers", sorted(required))}
        if covered != required:
            raise base.Failed("Declared variants do not cover every parent step: " + parent_id)
    expanded = []
    for case in cases:
        expanded.append(case)
        for variant in by_parent.get(case["id"], []):
            steps = case["steps"]
            if "step_numbers" in variant:
                numbers = variant["step_numbers"]
                if (not isinstance(numbers, list) or numbers != sorted(set(numbers))
                        or not set(numbers) <= {step["step"] for step in steps}):
                    raise base.Failed("Variant step subset is invalid")
                steps = [step for step in steps if step["step"] in numbers]
            expanded.append({**case, "id": variant["id"], "parent_id": case["id"],
                             "input": variant["input_ref"], "variant_fixture_kind": variant["fixture_kind"],
                             "variant_expected_ref": variant["expected_ref"], "steps": steps,
                             "variant_blocked_reason": variant.get("blocked_reason")})
    return expanded


def raw_status(path: Path, case_id: str) -> tuple[str, str]:
    if not path.is_file() or path.is_symlink():
        return "BLOCKED", "Playwright did not produce a raw JSON result"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        specs = [spec for group in payload.get("suites", []) for spec in group.get("specs", [])]
        tests = [test for spec in specs for test in spec.get("tests", [])]
        results = [result for test in tests for result in test.get("results", [])]
    except (OSError, ValueError, TypeError):
        return "FAIL", "Playwright raw JSON is unreadable"
    if len(specs) != 1 or len(tests) != 1 or len(results) != 1 or specs[0].get("title") != case_id:
        return "BLOCKED", f"Expected one independent Playwright attempt; observed {len(tests)} tests/{len(results)} attempts"
    status = results[0].get("status")
    if status == "passed":
        return "PASS", ""
    if status == "failed" or status == "timedOut":
        errors = results[0].get("errors") or []
        detail = re.sub(r"\x1b\[[0-9;]*m", "", str(errors[0].get("message", "")))[:1000] if errors else ""
        return "FAIL", detail or f"Playwright status {status}"
    return "BLOCKED", f"Playwright status {status or 'missing'}"


def step_evidence(case: dict, path: Path, run_id: str) -> tuple[list[dict], str | None]:
    if not path.is_file() or path.is_symlink():
        return [], "Independent step event log is missing"
    actual = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("run_id") != run_id or event.get("case_id") != case["id"]:
                return actual, "Step event identity does not match this run and TC"
            if any(field not in event for field in ("step", "action", "expected", "actual", "passed", "timestamp", "source")):
                return actual, "Step event lacks a required action/expected/actual/evidence field"
            if not isinstance(event["step"], int) or isinstance(event["step"], bool):
                return actual, "Step event has no integer catalog step number"
            if not isinstance(event["passed"], bool):
                return actual, "Step comparison is not a Boolean"
            # The synthetic credentials are deliberately available in the private
            # fixture; they must not be exported into a review workbook.
            safe_text = json.dumps(event, ensure_ascii=False)
            if "TEST-ONLY-" in safe_text or re.search(r'"(?:access_token|token|password_hash)"\s*:', safe_text):
                return actual, "Step event contains a credential or token"
            actual.append(event)
    except (OSError, ValueError, TypeError):
        return actual, "Step event log is malformed"
    expected = [step["step"] for step in case["steps"]]
    observed = [step["step"] for step in actual]
    if observed != expected:
        return actual, f"Catalog steps {expected} differ from recorded steps {observed}"
    if not all(step["passed"] for step in actual):
        return actual, "At least one independent step assertion failed"
    return actual, None


def playwright(case_id: str, spec: str, context: Path, output: Path, run_id: str, candidate: str) -> tuple[int, Path]:
    raw = output / "playwright.json"
    env = dict(os.environ, TM_E2E_CONTEXT=str(context), TM_E2E_JSON=str(raw),
               TM_E2E_CASE_OUTPUT=str(output), TM_E2E_RUN_ID=run_id,
               TM_E2E_CANDIDATE_SHA=candidate, TM_E2E_SPEC=spec)
    binary = ROOT / "apps/desktop/node_modules/.bin/playwright"
    with (output / "playwright.log").open("x", encoding="utf-8") as log:
        os.chmod(output / "playwright.log", 0o600)
        try:
            process = subprocess.run([str(binary), "test", f"e2e/{spec}", "--config", "e2e/playwright.config.ts",
                                      "--grep", r"(?:^|\s)" + re.escape(case_id) + "$"], cwd=ROOT / "apps/desktop",
                                     env=env, stdout=log, stderr=subprocess.STDOUT,
                                     timeout=600, check=False)
            return process.returncode, raw
        except subprocess.TimeoutExpired:
            return 124, raw


def prepared_database(case: dict, private: Path, output: Path, bootstrap, fixtures) -> tuple[Path, list[Path], Path | None, dict]:
    case_id = case["id"]
    details: dict = {}
    sql_files: list[Path] = []
    fixture = None
    if case.get("variant_fixture_kind") == "D42-BOUNDS":
        database, fixture, sql = bounds.generate(private / "bounds", output,
                                                 "l" + uuid.uuid4().hex[:18], case_id)
        return database, [sql], fixture, {"fixture_kind": "D42-BOUNDS"}
    if case_group(case_id) == "BOOTSTRAP":
        root = private / "bootstrap"
        root.mkdir(mode=0o700)
        bootstrap_result = bootstrap.initialize_production(root)
        original = root / "database/production/production.db"
        sql = original.with_name("seed.sql")
        evidence_sql = output / "seed-production.sql"
        shutil.copyfile(sql, evidence_sql)
        os.chmod(evidence_sql, 0o600)
        sql_files.append(evidence_sql)
        backup, restored = private / "backup.db", private / "restored.db"
        with sqlite3.connect(original) as source, sqlite3.connect(backup) as target:
            source.backup(target)
        with sqlite3.connect(backup) as source, sqlite3.connect(restored) as target:
            source.backup(target)
        comparison_dir = private / "comparison"
        comparison_dir.mkdir(mode=0o700)
        comparison, fixture, comparison_sql = base.make_account_database(
            comparison_dir, output, "l" + uuid.uuid4().hex[:18], 42, bootstrap, fixtures)
        sql_files.append(comparison_sql)
        base.write_json(output / "bootstrap-result.json", {
            "operation": "initialize_production", "state": "PASS",
            "result": bootstrap_result, "run_id": case_id,
        })
        details = {"fixture_kind": "production_bootstrap_and_restored",
                   "bootstrap_exit_code": 0 if isinstance(bootstrap_result, dict) else None,
                   "bootstrap_seed_sql_path": str(sql),
                   "bootstrap_original_path": str(original), "bootstrap_backup_path": str(backup),
                   "bootstrap_restored_path": str(restored), "comparison_database_path": str(comparison)}
        for source, name in ((original, "bootstrap-original.db"), (backup, "bootstrap-backup.db"),
                             (restored, "bootstrap-restored-before.db")):
            target = output / name
            shutil.copyfile(source, target)
            os.chmod(target, 0o600)
        details.update(bootstrap_root=str(root), python_executable=sys.executable)
        return original if case_id.endswith("-03") else restored, sql_files, fixture, details
    if case_id == "TC-TM001-ADMIN-05#CONCURRENT":
        db_dir = private / "two-admins"
        db_dir.mkdir(mode=0o700)
        database = db_dir / "accounts.sqlite"
        seed_id = "l" + uuid.uuid4().hex[:18]
        accounts = fixtures.accounts(42) + [{"id": "00000000-0000-4000-8000-000000000006",
            "username": "test-admin-two", "password": "TEST-ONLY-admin-two-42!", "role": "admin", "is_active": True}]
        bootstrap._new_database(database, "test", seed_id)
        sql = output / "seed-two-admins.sql"
        sql_text = bootstrap._seed_sql("test", seed_id, accounts)
        bootstrap._write_exclusive(sql, sql_text)
        bootstrap._apply_sql(database, sql_text)
        bootstrap._assert_database(database, "test", seed_id, accounts)
        fixture = db_dir / "oracle"
        fixture.mkdir(mode=0o700)
        base.write_json(fixture / "expected.json", {"users": [{key: value for key, value in account.items()
                          if key != "password"} for account in accounts], "seed": 42})
        return database, [sql], fixture, {"fixture_kind": "two_admin_accounts"}
    db_dir = private / "primary"
    db_dir.mkdir(mode=0o700)
    database, fixture, sql = base.make_account_database(
        db_dir, output, "l" + uuid.uuid4().hex[:18], 42, bootstrap, fixtures)
    sql_files.append(sql)
    return database, sql_files, fixture, {"fixture_kind": "auth_accounts"}


def one_case(case: dict, args, package: dict, mounted: Path, private_root: Path, out: Path,
             tree_tool, bootstrap, fixtures) -> tuple[dict, bool]:
    case_id = case["id"]
    item = blocked(case, "Execution has not started")
    item["started_at"] = now()
    case_out = out / case_id
    case_out.mkdir(mode=0o700)
    private = private_root / private_case_name(case_id)
    private.mkdir(mode=0o700)
    services = []
    proxies = []
    update = None
    denied = None
    shipit = None
    installed = None
    installation = private / "installation"
    peer_installation = private / "peer-installation"
    safe_to_continue = True
    try:
        if case_id == "TC-TM001-UPDATE-08":
            isolation = case_out / "shipit-negative-probes.json"
            base.write_json(isolation, shipit_probe(private, args.run_id))
        installed = base.copy_verified_app(mounted, installation / "TokenMeter.app", package, tree_tool, case_out / "install.log")
        profile = private / "profile"
        profile.mkdir(mode=0o700)
        database, sql_files, fixture, extra = prepared_database(case, private, case_out, bootstrap, fixtures)
        if case_group(case_id) == "ADMIN" or case_id.startswith("TC-TM001-SESSION-05") or case_id == "TC-TM001-PASSWORD-05":
            peer_app = base.copy_verified_app(mounted, peer_installation / "TokenMeter.app", package, tree_tool, case_out / "peer-install.log")
            peer_profile = private / "peer-profile"
            peer_profile.mkdir(mode=0o700)
            extra.update(peer_app_path=str(peer_app), peer_profile_path=str(peer_profile))
        clock_file = None
        if case_id in ("TC-TM001-SESSION-07", "TC-TM001-LOGIN-16"):
            clock_file = private / "clock.txt"
            clock_file.write_text("1700000000\n")
            os.chmod(clock_file, 0o600)
            extra.update(clock_path=str(clock_file), clock_start=1700000000)
        before = case_out / "database-before.json"
        base.write_json(before, base.safe_snapshot_database(database, case_id, args.run_id))
        service = base.Service(database, private, clock_file=clock_file)
        services.append(service)
        proxy = ServiceFixture(service.url, restart=service.restart)
        proxies.append(proxy)
        secondary_url = None
        if case_group(case_id) == "CONFIG":
            secondary_dir = private / "secondary"
            secondary_dir.mkdir(mode=0o700)
            secondary_db, _, secondary_sql = base.make_account_database(
                secondary_dir, case_out, "l" + uuid.uuid4().hex[:18], 43, bootstrap, fixtures)
            sql_files.append(secondary_sql)
            secondary = base.Service(secondary_db, private)
            services.append(secondary)
            secondary_proxy = ServiceFixture(secondary.url)
            proxies.append(secondary_proxy)
            secondary_url = secondary_proxy.url
            extra["secondary_database_path"] = str(secondary_db)
            extra["secondary_service_log_path"] = str(secondary.log)
            extra["secondary_control_url"] = secondary_proxy.control_url
            extra["secondary_control_token"] = secondary_proxy.token
        cdp_port = None
        if case_group(case_id) == "UPDATE" or case_id == "TC-TM001-CONFIG-06":
            if case_id.endswith(("-02", "-03")):
                denied = DeniedTarget()
                extra.update(forbidden_target_url=denied.url + "/update.zip",
                             forbidden_target_observations_url=denied.url + "/observations",
                             forbidden_target_token=denied.token)
            if case_id.startswith("TC-TM001-UPDATE-05#"):
                from granular_update_validation_fixture import ValidationFixture
                update = ValidationFixture(args.update_zip, package, private / "update-validation",
                                            case_id, ROOT / ".local/internal-release-keys")
                extra.update(validation_fixture_url=update.url,
                    validation_fixture_control_url=update.control_url,
                    validation_fixture_control_token=update.token,
                    validation_fixture_manifest_path=str(update.manifest_path),
                    validation_variant=case_id, owned_sentinel_path=str(update.sentinel),
                    package_manifest_path=str(args.package_manifest.absolute()))
                shutil.copyfile(update.manifest_path, case_out / "negative-fixture-manifest.json")
                if update.archive.resolve() != args.update_zip.resolve():
                    shutil.copyfile(update.archive, case_out / "negative-archive.zip")
            else:
                update = base.UpdateFixture(args.update_zip, package,
                                            forbidden_target_url=denied.url + "/update.zip" if denied else None)
            if (case_group(case_id) == "UPDATE" and case_id.endswith(("-06", "-07", "-08"))) or case_id == "TC-TM001-CONFIG-06":
                shipit = base.prepare_owned_shipit(args.run_id)
                extra["shipit_cache_path"] = str(shipit)
            if case_id == "TC-TM001-UPDATE-08":
                extra["shipit_negative_probe_path"] = str(isolation)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", 0))
                cdp_port = probe.getsockname()[1]
        fixture_manifest = base.fixture_evidence(case_out, args.run_id, case_id, fixture, sql_files,
                                                seed=42, kind=extra["fixture_kind"])
        context = private / "context.json"
        base.write_json(context, {"run_id": args.run_id, "candidate_sha": args.candidate_sha,
                                 "case_id": case_id, "app_path": str(installed), "profile_path": str(profile),
                                 "service_url": proxy.url, "service_log_path": str(service.log),
                                 "service_control_url": proxy.control_url,
                                 "service_control_token": proxy.token,
                                 "backend_service_url": service.url,
                                 "database_path": str(database), "secondary_service_url": secondary_url,
                                 "update_url": update.url + "/version.json" if update else None,
                                 "update_control_url": update.url + "/control" if update else None,
                                 "update_control_token": update.token if update else None,
                                 "update_nonce": update.nonce if update else None, "cdp_port": cdp_port,
                                 "expected_upgrade_build": "101",
                                 "expected_app_tree_sha256": package["app"]["tree_sha256"],
                                 "expected_update_tree_sha256": package["update_app"]["tree_sha256"],
                                 **extra})
        spec = case_spec(case_id)
        return_code, raw = playwright(case_id, spec, context, case_out, args.run_id, args.candidate_sha)
        status, reason = raw_status(raw, case_id)
        if return_code and status == "PASS":
            status, reason = "FAIL", f"Playwright exited {return_code} despite reported passed attempt"
        events = case_out / "events.jsonl"
        steps, step_error = step_evidence(case, events, args.run_id)
        traces, screenshots = base.collect_trace_and_screenshots(case_out)
        if status == "PASS" and step_error and case_id != "TC-TM001-UPDATE-08":
            status, reason = "FAIL", step_error
        if status == "PASS" and (not traces or not screenshots):
            status, reason = "FAIL", "Actual UI trace or screenshot is missing"
        coverage = case_out / "coverage-blocked.json"
        if status == "PASS" and coverage.is_file():
            status = "BLOCKED"
            reason = "Incomplete required coverage: " + str(json.loads(coverage.read_text()).get("reason", "missing coverage reason"))
        item.update(state=status, reason=reason or "", step_results=steps,
                    evidence={"playwright": base.descriptor(raw, out) if raw.is_file() else None,
                              "events": base.descriptor(events, out) if events.is_file() else None,
                              "database_before": base.descriptor(before, out),
                              "fixture_manifest": base.descriptor(fixture_manifest, out),
                              "seed_sql": [base.descriptor(path, out) for path in sql_files],
                              "fixture_expected": [base.descriptor(path, out) for path in case_out.glob("account-*expected.json")],
                              "trace": base.descriptor(traces[0], out) if traces else None,
                              "screenshots": [base.descriptor(p, out) for p in screenshots]})
        for evidence_name, filename in (("main_observer", "main-observer.jsonl"),
                                        ("config_phase_observations", "config-phase-observations.jsonl"),
                                        ("config_upgrade_process", "config-upgrade-process.json"),
                                        ("process_open_files", "process-open-files.json")):
            evidence_file = case_out / filename
            if evidence_file.is_file():
                item["evidence"][evidence_name] = base.descriptor(evidence_file, out)
        if coverage.is_file():
            item["evidence"]["coverage_blocked"] = base.descriptor(coverage, out)
        cleanup_observation = case_out / "cleanup-observation.json"
        if cleanup_observation.is_file():
            item["evidence"]["cleanup_observation"] = base.descriptor(cleanup_observation, out)
        if clock_file:
            clock_evidence=case_out/"clock-fixture.json"
            base.write_json(clock_evidence,{"run_id":args.run_id,"case_id":case_id,
                "kind":"test_only_real_service_clock_dependency","initial":extra["clock_start"],
                "final":int(clock_file.read_text()),"database_counters_edited":False})
            item["evidence"]["clock_fixture"]=base.descriptor(clock_evidence,out)
        if update:
            update_log = case_out / "update-requests.json"
            base.write_json(update_log, {"run_id": args.run_id, "case_id": case_id,
                                         "origin": update.url, "nonce": update.nonce,
                                         "requests": update.requests})
            item["evidence"]["update_requests"] = base.descriptor(update_log, out)
            for filename in ("negative-fixture-manifest.json", "negative-archive.zip"):
                artifact = case_out / filename
                if artifact.is_file():
                    item["evidence"][filename.replace(".", "_")] = base.descriptor(artifact, out)
    except base.Blocked as error:
        item.update(state="BLOCKED", reason=str(error))
    except (base.Failed, OSError, ValueError, KeyError, TypeError, sqlite3.Error, subprocess.SubprocessError) as error:
        item.update(state="FAIL", reason=str(error))
    finally:
        cleanup = {"services": True, "transport_proxies": True, "update_source": True, "denied_target": True, "app_processes": True,
                   "shipit": True, "credential_owner_detach": True, "private": False}
        if update:
            try: cleanup["update_source"] = update.close()
            except Exception: cleanup["update_source"] = False
        if denied:
            try: cleanup["denied_target"] = denied.close()
            except Exception: cleanup["denied_target"] = False
            denied_log = case_out / "denied-target.json"
            base.write_json(denied_log, {"run_id": args.run_id, "case_id": case_id,
                                         "url": denied.url, "requests": denied.requests})
            item["evidence"]["denied_target"] = base.descriptor(denied_log, out)
        for proxy in proxies:
            try: cleanup["transport_proxies"] = proxy.close() and cleanup["transport_proxies"]
            except Exception: cleanup["transport_proxies"] = False
        if proxies:
            transport = case_out / "transport-audit.json"
            base.write_json(transport, {"run_id": args.run_id, "case_id": case_id,
                "origins": [{"origin": proxy.url, "requests": proxy.requests,
                             "controls": proxy.controls} for proxy in proxies]})
            item["evidence"]["transport_audit"] = base.descriptor(transport, out)
        for service in services:
            try: cleanup["services"] = service.close() and cleanup["services"]
            except Exception: cleanup["services"] = False
        if services:
            audit = case_out / "service-audit.json"
            base.write_json(audit, {"run_id": args.run_id, "case_id": case_id,
                                    "requests": [request for service in services for request in service.requests]})
            item["evidence"]["service_audit"] = base.descriptor(audit, out)
            for index, service in enumerate(services):
                if service.log.is_file():
                    log = case_out / f"service-{index}.log"
                    shutil.copyfile(service.log, log)
                    os.chmod(log, 0o600)
                    if log.stat().st_size:
                        item["evidence"].setdefault("service_logs", []).append(base.descriptor(log, out))
        database_text = None
        try:
            context = private / "context.json"
            if context.is_file():
                database_text = json.loads(context.read_text(encoding="utf-8")).get("database_path")
            if database_text:
                after = case_out / "database-after.json"
                base.write_json(after, base.safe_snapshot_database(Path(database_text), case_id, args.run_id))
                item["evidence"]["database_after"] = base.descriptor(after, out)
        except Exception as error:
            item["state"], item["reason"] = "FAIL", f"Read-only database verification failed: {error}"
        if installation.exists():
            try: cleanup["app_processes"] = base.stop_owned_apps(installation)
            except Exception: cleanup["app_processes"] = False
        if peer_installation.exists():
            try: cleanup["app_processes"] = base.stop_owned_apps(peer_installation) and cleanup["app_processes"]
            except Exception: cleanup["app_processes"] = False
        owner_record = case_out / "credential-owner-fixture.json"
        if owner_record.is_file():
            try:
                if not cleanup["app_processes"]:
                    raise base.Failed("Owner fixture cannot detach while owned App may still be running")
                completed = subprocess.run([sys.executable, str(ROOT / "scripts/granular_credential_owner_fixture.py"),
                    "detach", "--record", str(owner_record)], capture_output=True, text=True, timeout=90)
                cleanup["credential_owner_detach"] = completed.returncode == 0
                (case_out / "credential-owner-detach.log").write_text(completed.stdout + completed.stderr)
            except Exception:
                cleanup["credential_owner_detach"] = False
            for key, filename in (("credential_owner_fixture", "credential-owner-fixture.json"),
                                  ("credential_owner_image", "credential-owner-fixture.dmg")):
                path = case_out / filename
                if path.is_file():
                    item["evidence"][key] = base.descriptor(path, out)
        if shipit:
            try: cleanup["shipit"] = base.cleanup_owned_shipit(shipit, args.run_id, installed, case_out / "shipit-cleanup")
            except Exception: cleanup["shipit"] = False
            cleanup_stage = case_out / "shipit-cleanup/cleanup-stage.json"
            if cleanup_stage.is_file():
                item["evidence"]["shipit_cleanup_stage"] = base.descriptor(cleanup_stage, out)
            preference_copies = sorted((case_out / "shipit-cleanup").glob("*.plist"))
            if preference_copies:
                item["evidence"]["shipit_preference_copies"] = [base.descriptor(path, out) for path in preference_copies]
        if all(value for key, value in cleanup.items() if key != "private"):
            try:
                shutil.rmtree(private)
                cleanup["private"] = not private.exists()
            except OSError: pass
        item["cleanup"] = cleanup
        if case_id == "TC-TM001-UPDATE-08" and item["state"] == "PASS":
            events = case_out / "events.jsonl"
            checks = [(4, "清理本轮App/服务/更新源/ShipIt及私有目录", all(cleanup.values())),
                      (5, "同run候选原始报告与包证据存在且归档不覆盖", bool(item["evidence"].get("playwright") and item["evidence"].get("update_requests") and item["evidence"].get("trace")))]
            with events.open("a", encoding="utf-8") as stream:
                for number, action, actual in checks:
                    stream.write(json.dumps({"run_id": args.run_id, "case_id": case_id, "step": number,
                        "action": action, "expected": True, "actual": actual, "passed": actual,
                        "source": "runner_cleanup", "timestamp": now()}, ensure_ascii=False) + "\n")
            item["step_results"], final_error = step_evidence(case, events, args.run_id)
            item["evidence"]["events"] = base.descriptor(events, out)
            item["evidence"]["isolation_components"] = base.descriptor(case_out / "shipit-negative-probes.json", out)
            if final_error:
                item["state"], item["reason"] = "FAIL", final_error
        if not all(cleanup.values()):
            if item["state"] == "PASS":
                item["state"], item["reason"] = "FAIL", "Owned test resources were not fully cleaned"
            safe_to_continue = False
        item["finished_at"] = now()
    return item, safe_to_continue


def execute(args) -> int:
    catalog = read_catalog()
    all_catalog = catalog
    if args.case_id:
        requested = set(args.case_id)
        known = {case["id"] for case in catalog}
        if not requested <= known or len(args.case_id) != len(requested):
            raise base.Failed("Targeted TC list contains an unknown or duplicate ID")
        catalog = [case for case in catalog if case["id"] in requested or case.get("parent_id") in requested]
    out = args.output.absolute()
    if out.exists() or any(path.is_symlink() for path in (out, *out.parents)):
        raise base.Blocked("Granular result directory must be new and have no symlink parent")
    out.mkdir(parents=True, mode=0o700)
    os.chmod(out, 0o700)
    scope = "granular_targeted_probe" if args.case_id else ("granular_development_package" if args.development else "granular_final_package")
    report = {"schema_version": 3, "scope": scope,
              "state": "BLOCKED", "release_eligible": False, "run_id": args.run_id,
              "source_commit": args.candidate_sha, "started_at": now(),
              "finished_at": None, "expected_cases": [case["id"] for case in catalog],
              "tc_results": [], "cleanup_completed": False}
    input_paths = [ROOT / "tests/test_cases.json", ROOT / "tests/granular_login_variants.json",
                   ROOT / "tests/granular_update_variants.json",
                   ROOT / "apps/desktop/e2e/playwright.config.ts", ROOT / "scripts/granular_e2e.py",
                   ROOT / "scripts/local_e2e.py", ROOT / "scripts/granular_service_fixture.py",
                   ROOT / "scripts/granular_bounds_fixture.py", ROOT / "scripts/granular_update_target.py"]
    input_paths.extend(ROOT / name for name in ("scripts/run_test_case.py", "scripts/granular_shipit_probe.py", "scripts/granular_clock_server.py", "scripts/granular_credential_owner_fixture.py",
                                                "scripts/granular_update_validation_fixture.py"))
    input_paths.extend(ROOT / name for name in ("scripts/bootstrap_sqlite.py", "tests/server/fixtures.py",
        "apps/desktop/package-lock.json", "server/requirements-dev.txt", "server/requirements.txt"))
    input_paths.extend(ROOT / name for name in ("scripts/local_package.py", "scripts/package_release_dmg.py", "scripts/internal_package.py"))
    input_paths.extend(ROOT / name for name in ("apps/desktop/e2e/main-observer.ts", "apps/desktop/e2e/main-observer.cjs",
                                                "apps/desktop/e2e/lsof.ts"))
    input_paths.extend((ROOT / "server").rglob("*.py"))
    input_paths.extend((ROOT / "releases").glob("*/local-release.json"))
    used_specs = {case_spec(case["id"]) for case in catalog}
    input_paths.extend(ROOT / "apps/desktop/e2e" / name for name in sorted(name for name in used_specs if name))
    inputs = {path.relative_to(ROOT).as_posix(): base.digest(path) for path in input_paths if path.is_file()}
    report["test_inputs_sha256"] = inputs
    replay_base = [sys.executable, str(ROOT / "scripts/run_test_case.py"),
        "--package-manifest", str(args.package_manifest.absolute()), "--source-report", str(out / "result.json")]
    if args.development: replay_base.append("--development")
    report["replay"] = {"working_directory": str(ROOT), "all_command": shlex.join(replay_base + ["--all"]),
        "cases": {case["id"]: {"code": "apps/desktop/e2e/" + spec,
            "test_name": case["id"], "command": shlex.join(replay_base + ["--case-id", case["id"]])}
            for case in catalog if (spec := case_spec(case["id"]))}}
    snapshot_files = []
    for relative in inputs:
        target = out / "test-code" / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(ROOT / relative, target)
        os.chmod(target, 0o600)
        snapshot_files.append(base.descriptor(target, out))
    report["test_code_snapshot"] = snapshot_files
    private = None
    mount = None
    safe_to_continue = True
    try:
        if not base.RUN_ID.fullmatch(args.run_id) or not base.SHA.fullmatch(args.candidate_sha):
            raise base.Failed("Invalid run or candidate SHA")
        manifest = args.package_manifest.resolve(strict=True)
        dmg = args.dmg.resolve(strict=True)
        update_zip = args.update_zip.resolve(strict=True)
        args.update_zip = update_zip
        package = base.verify_host_and_manifest(manifest, dmg, update_zip, args.candidate_sha,
                                                development=args.development)
        report.update(release_id=package["release_id"], working_tree_dirty=package["working_tree_dirty"],
                      candidate_tree=package["candidate_tree"],
                      host={"macos": platform.mac_ver()[0], "architecture": platform.machine()},
                      package={"manifest_sha256": base.digest(manifest), "dmg_sha256": base.digest(dmg),
                               "app_tree_sha256": package["app"]["tree_sha256"],
                               "installed_source": "development_dmg" if args.development else "final_dmg"})
        base_dir = ROOT / ".local/local-granular-work"
        base_dir.mkdir(parents=True, exist_ok=True)
        private = Path(tempfile.mkdtemp(prefix=args.run_id + "-", dir=base_dir)).resolve()
        os.chmod(private, 0o700)
        base.write_json(private / "owner.json", {"owner": "tokenmeter-granular-e2e", "run_id": args.run_id})
        mount = private / "mounted"
        mounted = base.mount_dmg(dmg, mount, out / "mount.log")
        tree_tool = base.module("granular_tree", "scripts/package_release_dmg.py")
        bootstrap = base.module("granular_bootstrap", "scripts/bootstrap_sqlite.py")
        fixtures = base.module("granular_fixtures", "tests/server/fixtures.py")
        variant_parents = {case["parent_id"] for case in all_catalog if case.get("parent_id")}
        for case in catalog:
            case_id = case["id"]
            if case_id in variant_parents:
                item = blocked(case, "Parent TC is concluded only from every independent declared variant")
            elif case["design_status"] != "designed":
                item = blocked(case, f"Design state {case['design_status']}: acceptance expectation is not baselined")
            elif case.get("variant_blocked_reason"):
                item = blocked(case, case["variant_blocked_reason"])
            else:
                spec = case_spec(case_id)
                path = ROOT / "apps/desktop/e2e" / spec if spec else None
                if path is None or not path.is_file():
                    item = blocked(case, "No independently registered Playwright TC and isolated fixture binding")
                elif not safe_to_continue:
                    item = blocked(case, "Previous test left an owned resource unclean; continued execution would be unsafe")
                else:
                    print(json.dumps({"event": "granular_progress", "case_id": case_id, "stage": "started"}), flush=True)
                    item, safe_to_continue = one_case(case, args, package, mounted, private, out,
                                                       tree_tool, bootstrap, fixtures)
                    print(json.dumps({"event": "granular_progress", "case_id": case_id,
                                      "state": item["state"]}), flush=True)
            report["tc_results"].append(item)
        results_by_id = {item["case_id"]: item for item in report["tc_results"]}
        for parent_id in variant_parents:
            if parent_id not in results_by_id:
                continue
            children = [item for item in report["tc_results"] if item["case_id"].startswith(parent_id + "#")]
            parent_result = results_by_id[parent_id]
            declared = {case["id"] for case in all_catalog if case.get("parent_id") == parent_id}
            if {child["case_id"] for child in children} != declared:
                parent_result["reason"] = "Targeted probe did not execute every declared variant"
                continue
            states = {child["state"] for child in children}
            parent_result["state"] = "FAIL" if "FAIL" in states else "BLOCKED" if "BLOCKED" in states else "PASS"
            parent_result["reason"] = "Derived from all independently executed variants" if parent_result["state"] == "PASS" else "One or more independently declared variants failed or were blocked"
            parent_result["derived_variant_ids"] = [child["case_id"] for child in children]
        states = [item["state"] for item in report["tc_results"]]
        report["state"] = "FAIL" if "FAIL" in states else "BLOCKED" if "BLOCKED" in states else "PASS"
    except (base.Blocked, FileNotFoundError, ImportError) as error:
        report["state"], report["error"] = "BLOCKED", str(error)
    except (base.Failed, OSError, ValueError, TypeError, KeyError, sqlite3.Error, subprocess.SubprocessError) as error:
        report["state"], report["error"] = "FAIL", str(error)
    finally:
        for relative, original in inputs.items():
            path = ROOT / relative
            if not path.is_file() or base.digest(path) != original:
                report["state"] = "FAIL"
                report["error"] = f"Test source changed during the run: {relative}"
                break
        if len(report["tc_results"]) < len(catalog):
            seen = {item["case_id"] for item in report["tc_results"]}
            for case in catalog:
                if case["id"] not in seen:
                    report["tc_results"].append(blocked(case, report.get("error", "Run stopped before this TC")))
        mount_closed = True
        if mount and mount.exists():
            detached = subprocess.run(["hdiutil", "detach", str(mount)], capture_output=True, text=True, check=False)
            mount_closed = detached.returncode == 0
        private_closed = False
        if private and private.is_dir() and mount_closed and safe_to_continue:
            try:
                marker = json.loads((private / "owner.json").read_text(encoding="utf-8"))
                if marker == {"owner": "tokenmeter-granular-e2e", "run_id": args.run_id}:
                    shutil.rmtree(private)
                    private_closed = not private.exists()
            except (OSError, ValueError): pass
        report["cleanup"] = {"mount": mount_closed, "private": private_closed,
                             "per_case": safe_to_continue}
        report["cleanup_completed"] = all(report["cleanup"].values())
        if not report["cleanup_completed"] and report["state"] == "PASS":
            report["state"] = "FAIL"
            report["error"] = "Owned resources were not fully cleaned"
        report["finished_at"] = now()
        base.write_json(out / "result.json", report)
    print(json.dumps({"state": report["state"], "run_id": args.run_id,
                      "results": {state: sum(item["state"] == state for item in report["tc_results"])
                                  for state in ("PASS", "FAIL", "BLOCKED")},
                      "report": str(out / "result.json")}), flush=True)
    return 0 if report["state"] == "PASS" else 2 if report["state"] == "BLOCKED" else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-manifest", type=Path, required=True)
    parser.add_argument("--dmg", type=Path, required=True)
    parser.add_argument("--update-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--case-id", action="append", help="Run one or more specific TC IDs for development diagnosis only")
    return execute(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
