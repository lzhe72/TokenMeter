#!/usr/bin/env python3
"""Revalidate final package bytes and raw native evidence before internal release.

This entry point only issues a release passport in the protected master
workflow. JSON success flags alone never satisfy the native or package checks.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


native = load_module("internal_gate_native", ROOT / "scripts/native_e2e.py")
package_tool = load_module("internal_gate_package", ROOT / "scripts/internal_package.py")
update_tool = load_module("internal_gate_update", ROOT / "tests/e2e/update_source.py")
publish_tool = load_module("internal_gate_publish", ROOT / "scripts/internal_publish.py")
account_tool = load_module("internal_gate_accounts", ROOT / "tests/server/fixtures.py")


class GateError(ValueError):
    """Evidence contradicts the required release contract."""


class GateBlocked(GateError):
    """A required input or execution tool is unavailable."""


def require(condition, message):
    if not condition:
        raise GateError(message)


def digest_value(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GateBlocked(f"Required evidence is missing: {path.name}") from exc
    except (OSError, ValueError) as exc:
        raise GateError(f"Invalid JSON evidence: {path.name}") from exc


def ci_context(environment, candidate_sha):
    expected = {"GITHUB_ACTIONS": "true", "RUNNER_OS": "macOS", "RUNNER_ENVIRONMENT": "github-hosted",
                "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/master",
                "GITHUB_REF_PROTECTED": "true", "GITHUB_REPOSITORY": "lzhe72/TokenMeter",
                "GITHUB_WORKFLOW_REF": "lzhe72/TokenMeter/.github/workflows/internal-release.yml@refs/heads/master"}
    require(isinstance(candidate_sha, str) and re.fullmatch(r"[0-9a-f]{40}", candidate_sha), "Invalid candidate SHA")
    require(all(environment.get(k) == v for k, v in expected.items()), "Release requires the protected master workflow on a GitHub Mac")
    require(environment.get("GITHUB_SHA") == candidate_sha == environment.get("GITHUB_WORKFLOW_SHA"),
            "Dispatch, workflow, and candidate SHAs differ")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(isinstance(environment.get(key), str) and re.fullmatch(r"[1-9][0-9]*", environment[key]), "Invalid CI run or attempt")
    return {"repository": environment["GITHUB_REPOSITORY"], "workflow": environment["GITHUB_WORKFLOW_REF"],
            "run_id": environment["GITHUB_RUN_ID"], "run_attempt": environment["GITHUB_RUN_ATTEMPT"],
            "sha": candidate_sha, "event_name": environment["GITHUB_EVENT_NAME"], "ref": environment["GITHUB_REF"]}


def safe_artifact(base, relative, *, directory=False, allow_empty=False):
    require(isinstance(relative, str) and relative and "\\" not in relative, "Invalid artifact path")
    path = PurePosixPath(relative)
    require(not path.is_absolute() and all(p not in ("", ".", "..") for p in relative.split("/")), "Artifact path escapes its owner")
    require(base.is_dir() and not base.is_symlink() and not any(p.is_symlink() for p in base.parents),
            "Artifact root is not a regular directory")
    result = base
    for part in path.parts:
        result = result / part
        require(not result.is_symlink(), "Artifact path contains a symlink")
    if not result.exists():
        raise GateBlocked(f"Required artifact missing: {relative}")
    require(result.resolve().is_relative_to(base.resolve()), "Artifact escaped its root")
    if directory:
        require(result.is_dir(), "Expected an artifact directory")
    else:
        require(result.is_file() and (allow_empty or result.stat().st_size > 0), "Expected a nonempty regular artifact")
    return result


def checked_artifact(base, relative, digest):
    path = safe_artifact(base, relative)
    require(digest_value(digest) and native.sha256(path) == digest, "Artifact bytes differ from their recorded SHA256")
    return path


def time_range(record, now):
    try:
        dates = [datetime.fromisoformat(record[key]) for key in ("started_at", "finished_at")]
        require(all(d.tzinfo is not None and d.utcoffset() is not None for d in dates), "Evidence timestamps must include UTC offset")
        start, end = [d.timestamp() for d in dates]
    except (KeyError, TypeError, ValueError) as exc:
        raise GateError("Invalid evidence timestamps") from exc
    require(now - 14400 <= start <= end <= now + 5, "Evidence is stale, from the future, or has an invalid interval")
    return start, end


def expected_update_fixture(package):
    origin = "http://127.0.0.1:49177"
    signature = package["signatures"]["update_ed_signature"]
    size = package["artifacts"]["update_zip"]["bytes"]
    feeds = {"valid": (origin + "/update.zip", signature),
             "invalid": (origin + "/update.zip", base64.b64encode(bytes(64)).decode()),
             "forbidden": ("http://example.invalid/update.zip", signature),
             "redirect": (origin + "/redirect.zip", signature)}
    return {"kind": "controlled-signed-update", "build": "101",
            "package_sha256": package["artifacts"]["update_zip"]["sha256"],
            "transport": "loopback_http", "origin_url": origin, "private_key_archived": False} | {
                mode + "_feed_sha256": hashlib.sha256(update_tool.appcast(url, sig, size)).hexdigest()
                for mode, (url, sig) in feeds.items()}


def verify_update(base, suite, package, start, end):
    fixture_path = checked_artifact(base, suite.get("update_fixture_artifact"), suite.get("update_fixture_sha256"))
    fixture = read_json(fixture_path)
    expected = expected_update_fixture(package)
    require(isinstance(fixture, dict) and all(fixture.get(k) == v for k, v in expected.items())
            and digest_value(fixture.get("source_nonce_sha256")), "Update fixture does not bind the signed same-Mac archive")
    require(suite.get("upgraded_build") == "101" and suite.get("upgraded_app_sha256") == package["update_app"]["tree_sha256"],
            "Installed higher version does not match the signed upgrade artifact")
    events = read_json(checked_artifact(base, suite.get("update_requests_artifact"), suite.get("update_requests_sha256")))
    require(isinstance(events, list) and events, "Update request log is missing")
    for event in events:
        require(isinstance(event, dict) and isinstance(event.get("path"), str) and type(event.get("status")) is int,
                "Malformed update exchange event")
        try:
            when = datetime.fromisoformat(event["at"])
            require(when.tzinfo is not None and start - 2 <= when.timestamp() <= end + 2, "Update event is outside this run")
        except (KeyError, TypeError, ValueError) as exc:
            raise GateError("Invalid update event timestamp") from exc
    controls = [(i, e["path"].removeprefix("/control/")) for i, e in enumerate(events)
                if e["path"].startswith("/control/") and e["status"] == 200]
    require([mode for _, mode in controls] == ["forbidden", "redirect", "invalid", "valid"],
            "Update controls do not show exactly the four required stages")
    for position, (index, mode) in enumerate(controls):
        phase = events[index + 1:controls[position + 1][0] if position + 1 < len(controls) else len(events)]
        feed = [i for i, e in enumerate(phase) if e["path"] == "/appcast.xml" and e["status"] == 200
                and e.get("mode") == mode and type(e.get("served_bytes")) is int and e["served_bytes"] > 0]
        require(feed, "Update stage has no actual feed exchange")
        downloads = [i for i, e in enumerate(phase) if e["path"] == "/update.zip" and e["status"] == 200
                     and e.get("mode") == mode and e.get("served_bytes") == package["artifacts"]["update_zip"]["bytes"]]
        if mode in ("forbidden", "redirect"):
            require(not any(e["path"] == "/update.zip" for e in phase), "Forbidden update stage downloaded a package")
        else:
            require(downloads and min(downloads) > min(feed), "Missing complete signed update exchange after feed")
        if mode == "redirect":
            require(any(e["path"] == "/redirect.zip" and e["status"] == 302 and e.get("mode") == mode for e in phase),
                    "Missing actual redirect response")


def sqlite_contents(path):
    try:
        with sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True) as database:
            require(database.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "SQLite integrity check failed")
            # Fixed revision 0001 contract, independent of a report's schema label.
            columns = {
                "alembic_version": {"version_num"}, "tokenmeter_seed_owner": {"environment", "run_id"},
                "users": {"id", "username", "password_hash", "role", "is_active", "must_change_password", "credential_version"},
                "sessions": {"token_hash", "user_id", "credential_version", "expires_at"},
                "audit": {"id", "actor_id", "target_id", "action", "occurred_at"},
                "login_buckets": {"key", "failures", "window_start"},
            }
            tables = {row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            require(tables == set(columns), "Restored SQLite is not the complete revision 0001 schema")
            for table, expected in columns.items():
                require({row[1] for row in database.execute('PRAGMA table_info("' + table + '")')} == expected,
                        "Restored SQLite table columns differ from revision 0001")
            require(database.execute("PRAGMA foreign_key_check").fetchall() == [], "Restored SQLite has broken references")
            require(database.execute("SELECT version_num FROM alembic_version").fetchall() == [("0001",)], "Unexpected restored schema")
            require(database.execute("SELECT environment,run_id FROM tokenmeter_seed_owner").fetchall()
                    == [("production", "production-init")], "Restore is not the isolated production initializer")
            require(database.execute("SELECT id,username,role,is_active,must_change_password,credential_version FROM users").fetchall()
                    == [(native.PRODUCTION_BOOTSTRAP_USER_ID, "admin", "admin", 1, 1, 1)],
                    "Restored production database does not contain the initial forced-change administrator")
            password = database.execute("SELECT password_hash FROM users").fetchone()[0]
            require(isinstance(password, str) and password.startswith("$argon2id$"), "Restored account has no Argon2 password hash")
            require(database.execute("SELECT count(*) FROM sessions").fetchone() == (0,),
                    "Only session-free synthetic database snapshots may be archived")
            require(database.execute("SELECT count(*) FROM login_buckets").fetchone() == (0,),
                    "Restore backup contains login attempts from another phase")
            require(database.execute("SELECT actor_id,target_id,action FROM audit").fetchall()
                    == [(None, native.PRODUCTION_BOOTSTRAP_USER_ID, "account_provisioned")],
                    "Restore backup lacks the initial provisioning audit")
            return list(database.iterdump())
    except sqlite3.Error as exc:
        raise GateError("Cannot independently read the SQLite restore evidence") from exc


def verify_restore(base, report):
    restore = report.get("sqlite_restore")
    require(isinstance(restore, dict) and restore.get("verified") is True
            and restore.get("fixture_kind") == "production_bootstrap" and restore.get("synthetic_only") is True,
            "SQLite restore evidence is absent or is not explicitly isolated synthetic data")
    before = checked_artifact(base, restore.get("backup_artifact"), restore.get("backup_sha256"))
    after = checked_artifact(base, restore.get("restored_artifact"), restore.get("restored_sha256"))
    require(before != after, "Backup and restored database must be distinct artifacts")
    require(sqlite_contents(before) == sqlite_contents(after), "Restored SQLite rows differ from the actual backup")
    state = read_json(checked_artifact(base, restore.get("restored_state_artifact"), restore.get("restored_state_sha256")))
    require(state == {"integrity_check": "ok", "schema_version": "0001", "table_rows_match": True,
                      "api_login_verified": True}, "Restore API and state verification is incomplete")


def expected_account_manifest(run_id, seed):
    require(isinstance(run_id, str) and account_tool.RUN_ID.fullmatch(run_id), "Invalid account data invocation identity")
    payloads = {
        account_tool.MARKER: account_tool._encode({"owner": "tokenmeter-account-fixtures", "run_id": run_id,
                                                 "files": sorted(account_tool.OWNED)}),
        "users.json": account_tool._encode({"schema_version": 1, "test_only": True, "users": account_tool.accounts(seed)}),
        "expected.json": account_tool._encode(account_tool.expected()),
    }
    return {"schema_version": 1, "run_id": run_id, "seed": seed, "fixture_kind": "account-auth-spec",
            "files": {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}}


def verify_fixture(base, suite):
    manifest = read_json(checked_artifact(base, suite.get("fixture_manifest"), suite.get("fixture_sha256")))
    require(isinstance(manifest, dict), "Fixture manifest must be an object")
    profile = native.fixture_profile(suite["case_id"])
    if profile == "production_bootstrap":
        require(manifest.get("fixture_kind") == profile and manifest.get("database") == "database/production/production.db"
                and manifest.get("initial_state") == native.expected_bootstrap_state(after_ui=False)
                and digest_value(manifest.get("database_sha256")) and digest_value(manifest.get("seed_sql_sha256")),
                "Invalid production bootstrap fixture")
        state = read_json(checked_artifact(base, suite.get("bootstrap_state_artifact"), suite.get("bootstrap_state_sha256")))
        require(state == {"post_ui_state": native.expected_bootstrap_state(after_ui=True), "reinitialization_refused": True},
                "Production bootstrap UI result differs from the required account state")
    elif profile == "dual_service_routes":
        first, second = manifest.get("primary", {}), manifest.get("secondary", {})
        require(isinstance(first, dict) and isinstance(second, dict)
                and manifest.get("fixture_kind") == profile and manifest.get("default_port") == 49176
                and first.get("seed") == 42 and second.get("seed") == 43
                and isinstance(first.get("run_id"), str) and first["run_id"]
                and isinstance(second.get("run_id"), str) and second["run_id"] != first["run_id"]
                and all(digest_value(m.get("account_manifest_sha256")) for m in (first, second)),
                "Dual-service fixture does not identify two independent databases")
        for item in (first, second):
            expected = expected_account_manifest(item["run_id"], item["seed"])
            require(item["account_manifest_sha256"] == hashlib.sha256(account_tool._encode(expected)).hexdigest(),
                    "Dual-service account data differs from the fixed data generator")
    else:
        require(manifest.get("schema_version") == 1 and isinstance(manifest.get("run_id"), str)
                and manifest["run_id"] and manifest.get("seed") == 42,
                "Synthetic account fixture identity is invalid")
        require(manifest == expected_account_manifest(manifest["run_id"], 42),
                "Account fixture file hashes differ from independent test data and expected values")


def verify_platforms(root, evidence, package, config, *, candidate_sha, run_id, ci, now):
    expected = native.required_cases(root)
    require(set(expected) == {f"E2E-TM001-{i:03}" for i in range(1, 7)}, "Internal v0.1.0 requires exactly all six cases")
    require(evidence.is_dir() and not evidence.is_symlink(), "Missing owned platform evidence root")
    require({p.name for p in evidence.iterdir()} == {"arm64", "x86_64"}, "Expected exactly the two platform artifact directories")
    results, bundles, file_hashes = {}, [], []
    for item in sorted(evidence.rglob("*")):
        require(not item.is_symlink(), "Platform evidence contains a symlink")
        if item.is_file():
            file_hashes.append((item, native.sha256(item)))
        else:
            require(item.is_dir(), "Unsupported evidence file type")
    try:
        for arch in ("arm64", "x86_64"):
            base = safe_artifact(evidence, arch, directory=True)
            path = safe_artifact(base, "result.json")
            report = read_json(path)
            require(isinstance(report, dict), "Platform report must be an object")
            start, end = time_range(report, now)
            contract = {"schema_version": 1, "run_id": run_id, "release_id": config["release_id"],
                        "distribution_profile": "internal", "scope": "final_package", "phase": "release",
                        "state": "PASS", "release_eligible": False, "source_commit": candidate_sha,
                        "working_tree_dirty": False, "ci": ci, "cleanup_completed": True,
                        "manifest_sha256": native.snapshot(root)}
            require(all(report.get(k) == v and type(report.get(k)) is type(v) for k, v in contract.items()),
                    "Platform report belongs to a different candidate, run, or execution contract")
            require(report.get("cleanup_errors", []) == [] and report.get("errors", []) == []
                    and report.get("blockers", []) == [], "Platform report contains a failure or cleanup error")
            require(all(type(report.get(k)) is int and report[k] == 6 for k in ("executed_cases", "passed_cases")),
                    "Platform did not execute and pass all six cases")
            require(report.get("expected_cases") == list(expected), "Required case list changed")
            for key in ("credential_cleanup", "defaults_cleanup", "service_cleanup"):
                require(report.get(key) == dict.fromkeys(expected, True)
                        and all(v is True for v in report[key].values()), "Per-case production resource cleanup is incomplete")
            platform = report.get("platform", {})
            require(isinstance(platform, dict) and platform.get("architecture") == arch and isinstance(platform.get("macos"), str)
                    and re.fullmatch(r"15(?:\.\d+){1,2}", platform["macos"]), "Platform is outside the approved macOS 15 matrix")
            require(platform.get("xcode") == "Xcode 16.4\nBuild version 16F6", "Native toolchain differs from the pinned release toolchain")
            recorded = report.get("package", {})
            require(isinstance(recorded, dict), "Missing installed package identity")
            same = {"dmg_sha256": package["artifacts"]["dmg"]["sha256"],
                    "app_tree_sha256": package["app"]["tree_sha256"], "update_zip_sha256": package["artifacts"]["update_zip"]["sha256"],
                    "app_bundle_id": package["app"]["bundle_id"], "build": package["app"]["build"],
                    "architectures": package["app"]["architectures"], "code_sign_identity": package["app"]["code_sign_identity"],
                    "signature_kind": "internal_self_signed"}
            require(all(recorded.get(k) == v for k, v in same.items()), "Platform did not test the same final DMG and signed production App")
            for key in ("spctl_before", "spctl_after"):
                assessment = recorded.get(key)
                require(isinstance(assessment, dict) and type(assessment.get("exit_code")) is int
                        and isinstance(assessment.get("output"), str) and assessment["output"], "Gatekeeper assessment was not recorded")
            installation = report.get("installation", {})
            require(isinstance(installation, dict) and installation.get("source_dmg_sha256") == same["dmg_sha256"],
                    "Installation did not originate from this DMG")
            owned = installation.get("owned_paths")
            require(isinstance(owned, dict) and set(owned) == set(expected), "Missing per-case installation ownership identities")
            suites = report.get("suites")
            require(isinstance(suites, list) and len(suites) == 6, "Incomplete native suites")
            observed, installed_paths = set(), set()
            for suite in suites:
                require(isinstance(suite, dict), "Invalid native suite")
                case = suite.get("case_id")
                require(case in expected and case not in observed and suite.get("native_test") == expected[case]
                        and suite.get("state") == "PASS" and type(suite.get("exit_code")) is int and suite["exit_code"] == 0
                        and suite.get("native_failures") == [], "Wrong, duplicate, skipped, or failed native case")
                installed = suite.get("installed_app_path")
                require(isinstance(installed, str) and Path(installed).is_absolute() and run_id in installed
                        and Path(installed).name == "TokenMeter.app" and installed not in installed_paths
                        and owned.get(case) == installed
                        and suite.get("installed_app_before_sha256") == same["app_tree_sha256"], "Native case did not use the owned final App")
                installed_paths.add(installed)
                require(suite.get("xcresult") == case + "/native.xcresult", "Native bundle path does not match its case")
                bundle = safe_artifact(base, suite["xcresult"], directory=True)
                before = native.tree_digest(bundle)
                require(before == suite.get("xcresult_sha256"), "Native bundle changed after execution")
                bundles.append((bundle, before))
                tree, summary = native.parse_bundle(root, bundle)
                native.check_native_result(tree, summary, expected[case])
                require(type(summary.get("expectedFailures")) is int and summary["expectedFailures"] == 0,
                        "Native expected failures are not allowed")
                require(all(type(summary.get(k)) in (int, float) for k in ("startTime", "finishTime"))
                        and start - 2 <= summary["startTime"] <= summary["finishTime"] <= end + 2,
                        "Raw native evidence is outside this execution interval")
                actual = native.native_destination(summary, arch, platform["macos"])
                require(suite.get("destination") == actual, "Recorded platform does not match raw xcresult")
                pictures = suite.get("screenshots")
                require(isinstance(pictures, list) and pictures, "Native case has no required screenshots")
                for picture in pictures:
                    require(isinstance(picture, dict), "Invalid screenshot descriptor")
                    image = checked_artifact(base / case, picture.get("path"), picture.get("sha256"))
                    require(image.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "Screenshot is not a PNG")
                verify_fixture(base, suite)
                if case == "E2E-TM001-004":
                    verify_update(base, suite, package, start, end)
                observed.add(case)
            require(observed == set(expected), "Native case coverage is incomplete")
            verify_restore(base, report)
            results[arch] = {"report_sha256": native.sha256(path), "platform": platform,
                             "executed_cases": 6, "passed_cases": 6, "cases": list(expected),
                             "xcresult_sha256": {s["case_id"]: s["xcresult_sha256"] for s in suites},
                             "sqlite_restore": report["sqlite_restore"], "cleanup_completed": True}
        for bundle, before in bundles:
            require(native.tree_digest(bundle) == before, "Native bundle changed during parent verification")
        for path, before in file_hashes:
            require(native.sha256(path) == before, "Evidence changed during parent verification")
        require({p for p in evidence.rglob("*") if p.is_file()} == {p for p, _ in file_hashes},
                "Evidence file inventory changed during parent verification")
    except native.Blocked as exc:
        raise GateBlocked(str(exc)) from exc
    except native.EvidenceError as exc:
        raise GateError(str(exc)) from exc
    return results


def validate_zip(archive, *, app_only=False):
    with zipfile.ZipFile(archive) as zipped:
        names = set()
        for entry in zipped.infolist():
            name = entry.filename.rstrip("/")
            require(name and name not in names and "\\" not in name and not name.startswith("/")
                    and all(p not in (".", "..", "") for p in name.split("/")), "Unsafe or duplicate archive member")
            names.add(name)
            if app_only:
                require(name.split("/")[0] in {"TokenMeter.app", "__MACOSX"}, "Archive contains content outside the App")
            if stat.S_ISLNK(entry.external_attr >> 16):
                target = zipped.read(entry).decode("utf-8")
                destination = (Path("/archive") / Path(name).parent / target).resolve()
                require(not target.startswith("/") and destination.is_relative_to(Path("/archive/TokenMeter.app")),
                        "Archive symlink escapes the application")
        require(names, "Empty release archive")
        return names


def verify_package(root, manifest_path, config, candidate_sha, ci, now):
    safe_artifact(manifest_path.parent, manifest_path.name)
    manifest = read_json(manifest_path)
    require(isinstance(manifest, dict), "Package manifest must be an object")
    time_range(manifest, now)
    config_path = root / "releases" / config["release_id"] / "internal-release.json"
    require(all(manifest.get(k) == v and type(manifest.get(k)) is type(v) for k, v in {
        "schema_version": 1, "release_id": config["release_id"], "distribution_profile": "internal",
        "candidate_sha": candidate_sha, "config_sha256": native.sha256(config_path), "ci": ci,
        "cleanup_completed": True, "release_eligible": False}.items()), "Package manifest identity or cleanup differs")
    descriptors = manifest.get("artifacts", {})
    require(set(descriptors) == {"dmg", "candidate_zip", "update_zip", "server_zip"}, "Release package asset set differs")
    assets = {}
    for kind, descriptor in descriptors.items():
        require(isinstance(descriptor, dict), "Invalid package asset descriptor")
        path = checked_artifact(manifest_path.parent, descriptor.get("path"), descriptor.get("sha256"))
        require(type(descriptor.get("bytes")) is int and descriptor["bytes"] == path.stat().st_size, "Package asset size differs")
        assets[kind] = path
    require(len(set(assets.values())) == 4, "Package assets alias each other")
    expected_sources = {p.relative_to(root).as_posix() for p in (root / "server").rglob("*.py") if "__pycache__" not in p.parts}
    expected_sources |= {p.relative_to(root).as_posix() for p in (root / "server").glob("requirements*.txt")}
    expected_sources |= {"scripts/bootstrap_sqlite.py", "scripts/local_distribution.py", "docs/releases/02-installation.md",
                         config_path.relative_to(root).as_posix()}
    require(manifest.get("server_source_files") == sorted(expected_sources), "Server archive source list differs")
    require(validate_zip(assets["server_zip"]) == expected_sources, "Server archive file set differs")
    with zipfile.ZipFile(assets["server_zip"]) as zipped:
        for name in expected_sources:
            source = safe_artifact(root, name, allow_empty=True)
            require(zipped.read(name) == source.read_bytes(), "Server archive does not match the candidate source")
    require(sys.platform == "darwin", "Raw final package verification requires macOS")
    with tempfile.TemporaryDirectory(prefix="tokenmeter-parent-package-") as temporary:
        work = Path(temporary).resolve()
        for kind, metadata_key, build, signature_key in (
            ("candidate_zip", "app", "100", "candidate_ed_signature"),
            ("update_zip", "update_app", "101", "update_ed_signature")):
            validate_zip(assets[kind], app_only=True)
            extracted = work / kind
            extracted.mkdir()
            package_tool.run(["ditto", "-x", "-k", str(assets[kind]), str(extracted)], "Extract independently verified App archive")
            scratch = work / (kind + "-signature")
            scratch.mkdir()
            actual = package_tool.verify_app(extracted / "TokenMeter.app", config, build, scratch)
            require(actual == manifest.get(metadata_key), "App signature, architecture, or content differs from package manifest")
            package_tool.verify_ed_signature(assets[kind], manifest.get("signatures", {}).get(signature_key),
                                             config["update_public_key"], scratch)
        require(manifest["app"]["designated_requirement"] == manifest["update_app"]["designated_requirement"],
                "Candidate and upgrade signing requirements differ")
        mount = work / "mounted"
        mount.mkdir()
        package_tool.run(["hdiutil", "verify", str(assets["dmg"])], "Verify original final DMG", timeout=300)
        package_tool.run(["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", str(mount), str(assets["dmg"])],
                         "Mount original final DMG")
        try:
            scratch = work / "dmg-signature"
            scratch.mkdir()
            package_tool.validate_dmg_layout(mount, root / "docs/releases/02-installation.md")
            require(package_tool.verify_app(mount / "TokenMeter.app", config, "100", scratch) == manifest["app"],
                    "Final DMG does not contain the validated production App")
        finally:
            package_tool.run(["hdiutil", "detach", str(mount)], "Detach independently verified DMG")
    for kind, path in assets.items():
        require(native.sha256(path) == descriptors[kind]["sha256"], "Package changed during verification")
    return manifest


def verify_checkout(root, candidate_sha, release_id):
    require(native.git(root, "rev-parse", "HEAD") == candidate_sha, "Candidate checkout SHA differs")
    require(not native.git(root, "status", "--porcelain", "--untracked-files=all"), "Release checkout is dirty")
    require(not native.git(root, "tag", "--list", release_id), "Official release tag already exists")


def source_snapshot(root):
    names = native.git(root, "ls-files", "-z").split("\0")
    return {name: native.sha256(safe_artifact(root, name, allow_empty=True)) for name in names if name}


def verify_protection(path, release_id, candidate_sha, run_id, ci, now):
    safe_artifact(path.parent, path.name)
    value = read_json(path)
    require(isinstance(value, dict) and all(value.get(k) == v and type(value.get(k)) is type(v) for k, v in {
        "state": "PASS", "scope": "release_context_only", "release_eligible": False,
        "release_id": release_id, "candidate_sha": candidate_sha, "run_id": run_id, "ci": ci}.items()),
        "Remote protection evidence does not bind this release invocation")
    stamp = value.get("verified_at")
    time_range({"started_at": stamp, "finished_at": stamp}, now)
    remote = value.get("remote", {})
    require(isinstance(remote, dict), "Invalid remote protection snapshot")
    try:
        publish_tool.validate_remote_checks(remote["branch"], remote["checks"], candidate_sha)
    except (KeyError, TypeError, ValueError) as exc:
        raise GateError("Required remote branch protection or checks were not verified") from exc
    require(remote.get("environment", {}).get("deployment_branch_policy")
            == {"protected_branches": False, "custom_branch_policies": True}
            and [(p.get("name"), p.get("type")) for p in remote.get("policies", {}).get("branch_policies", [])]
            == [("master", "branch")], "Release environment permits a ref other than master")
    return {"path": path.name, "sha256": native.sha256(path), "verified_at": stamp}


def verify_release(root, manifest_path, evidence, protection_path, candidate_sha, run_id, *, environment=None, now=None):
    now = time.time() if now is None else now
    environment = os.environ if environment is None else environment
    require(isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_id), "Invalid release invocation identity")
    ci = ci_context(environment, candidate_sha)
    current = read_json(root / "releases/current.json")
    release_id = current.get("release_id") if isinstance(current, dict) else None
    require(isinstance(release_id, str) and re.fullmatch(r"v\d+\.\d+\.\d+-\d{8}T\d{6}Z", release_id), "Invalid release ID")
    config = package_tool.validate_config(read_json(root / "releases" / release_id / "internal-release.json"))
    verify_checkout(root, candidate_sha, release_id)
    sources = source_snapshot(root)
    protection = verify_protection(protection_path, release_id, candidate_sha, run_id, ci, now)
    manifest_digest = native.sha256(manifest_path)
    package = verify_package(root, manifest_path, config, candidate_sha, ci, now)
    require(datetime.fromisoformat(package["started_at"]).timestamp() >= datetime.fromisoformat(protection["verified_at"]).timestamp() - 2,
            "Package build predates this protected invocation")
    platforms = verify_platforms(root, evidence, package, config, candidate_sha=candidate_sha, run_id=run_id, ci=ci, now=now)
    verify_checkout(root, candidate_sha, release_id)
    require(source_snapshot(root) == sources and native.sha256(manifest_path) == manifest_digest
            and native.sha256(protection_path) == protection["sha256"], "Release inputs changed during verification")
    for artifact in package["artifacts"].values():
        checked_artifact(manifest_path.parent, artifact["path"], artifact["sha256"])
    return {"schema_version": 1, "state": "PASS", "release_eligible": True, "release_id": release_id,
            "distribution_profile": "internal", "candidate_sha": candidate_sha, "run_id": run_id, "ci": ci,
            "verified_at": datetime.now(timezone.utc).isoformat(), "package_manifest_sha256": manifest_digest,
            "artifacts": package["artifacts"], "app": package["app"], "update_app": package["update_app"],
            "config_sha256": package["config_sha256"], "source_files_sha256": sources,
            "protection": protection, "platforms": platforms, "cleanup_completed": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--package-manifest", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--protection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    output = args.output.absolute()
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        print(json.dumps({"state": "FAIL", "release_eligible": False, "errors": ["Output must be a new owned directory"]}))
        return 1
    output.mkdir(parents=True, mode=0o700)
    try:
        passport = verify_release(args.root.resolve(), args.package_manifest.absolute(), args.evidence.absolute(), args.protection.absolute(),
                                  args.candidate_sha, args.run_id)
        passport_path = output / (passport["release_id"] + ".passport.json")
        with passport_path.open("x") as stream:
            json.dump(passport, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        report = {"state": "PASS", "scope": "internal_final_package_release", "release_eligible": True,
                  "candidate_sha": args.candidate_sha, "run_id": args.run_id,
                  "passport": passport_path.name, "passport_sha256": native.sha256(passport_path)}
        code = 0
    except (GateBlocked, native.Blocked, FileNotFoundError) as exc:
        report = {"state": "BLOCKED", "release_eligible": False, "errors": [str(exc)]}
        code = 2
    except (GateError, native.EvidenceError, package_tool.PackageError, OSError, ValueError, KeyError, TypeError,
            zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        report = {"state": "FAIL", "release_eligible": False, "errors": [str(exc)]}
        code = 1
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
