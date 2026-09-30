#!/usr/bin/env python3
"""Run all native TM-001 cases against the App installed from one final DMG.

This runner is restricted to a fresh GitHub-hosted macOS 15 GUI worker. It
records final-package evidence; only the separate protected parent gate can
issue a release passport. Test inputs stay with XCTest and local services.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import internal_package, native_e2e
from scripts.package_release_dmg import file_sha256, tree_sha256
from tests.e2e.update_source import UpdateSource

Blocked = native_e2e.Blocked
EvidenceError = native_e2e.EvidenceError
BUNDLE_ID = "org.tokenmeter.TokenMeter"
DEFAULT_API = "http://127.0.0.1:49176"
DEFAULT_SOURCE = "http://127.0.0.1:49177"
PREFERENCE_DOMAIN = BUNDLE_ID
TOKEN_FILE = re.compile(r"[0-9a-f]{64}\.token\Z")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def relative_file(path: Path, output: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise EvidenceError("Missing regular final-package evidence file")
    try:
        return path.relative_to(output).as_posix()
    except ValueError as exc:
        raise EvidenceError("Final-package evidence escaped its output directory") from exc


def require_artifact(root: Path, descriptor: dict, supplied: Path) -> Path:
    """Bind a caller path to one regular, hashed builder-manifest artifact."""
    if not isinstance(descriptor, dict) or not isinstance(descriptor.get("path"), str):
        raise EvidenceError("Incomplete package artifact descriptor")
    name = descriptor["path"]
    relative = Path(name)
    if (relative.is_absolute() or not name or name.startswith(".") or ".." in relative.parts
            or any(part in ("", ".") for part in relative.parts)):
        raise EvidenceError("Package artifact path is unsafe")
    root_input, supplied_input = Path(root), Path(supplied)
    if root_input.is_symlink() or supplied_input.is_symlink():
        raise EvidenceError("Package artifact path contains a symbolic link")
    root = root_input.resolve(strict=True)
    expected = root / relative
    supplied = supplied_input.resolve(strict=True)
    if expected != supplied or expected.is_symlink():
        raise EvidenceError("Supplied artifact is not the builder-manifest file")
    if not expected.is_file() or expected.stat().st_nlink != 1:
        raise EvidenceError("Package artifact is missing, linked, or not regular")
    if (type(descriptor.get("bytes")) is not int or descriptor["bytes"] <= 0
            or descriptor["bytes"] != expected.stat().st_size
            or not re.fullmatch(r"[0-9a-f]{64}", str(descriptor.get("sha256", "")))
            or file_sha256(expected) != descriptor["sha256"]):
        raise EvidenceError("Package artifact length or SHA256 differs from builder manifest")
    return expected


def defaults_domain_exists() -> bool:
    result = subprocess.run(["defaults", "read", PREFERENCE_DOMAIN], capture_output=True, text=True,
                            check=False, timeout=15)
    return result.returncode == 0


def delete_defaults_domain() -> bool:
    if defaults_domain_exists():
        result = subprocess.run(["defaults", "delete", PREFERENCE_DOMAIN], capture_output=True, text=True,
                                check=False, timeout=15)
        if result.returncode:
            return False
    return not defaults_domain_exists()


def _production_paths(home: Path) -> tuple[Path, Path]:
    return (home / "Library/Application Support/TokenMeter",
            home / "Library/Preferences" / (PREFERENCE_DOMAIN + ".plist"))


def claim_production_state(home: Path, private: Path, run_id: str) -> dict:
    """Record absence before a production App touches its standard user paths."""
    home, private = Path(home).absolute(), Path(private).absolute()
    if (not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_id) or home.is_symlink()
            or not home.is_dir() or private.is_symlink() or not private.is_dir()
            or private.stat().st_uid != os.getuid()):
        raise Blocked("Final-package user or private run directory is unsafe")
    app_support, preferences = _production_paths(home)
    if app_support.exists() or app_support.is_symlink() or preferences.exists() or preferences.is_symlink():
        raise Blocked("Production App data existed before this hosted test case")
    if defaults_domain_exists():
        raise Blocked("Production defaults domain existed before this hosted test case")
    marker = private / "production-state-owner.json"
    if marker.exists() or marker.is_symlink():
        raise Blocked("Production data ownership marker already exists")
    claim = {"run_id": run_id, "home": str(home), "app_support": str(app_support),
             "preferences": str(preferences), "marker": str(marker), "created_at": utc_now()}
    with marker.open("x") as stream:
        json.dump(claim, stream, sort_keys=True)
        stream.write("\n")
    marker.chmod(0o600)
    return claim


def cleanup_production_state(claim: dict) -> bool:
    """Remove only this run's exact standard credential files and defaults."""
    marker = Path(claim["marker"])
    if (marker.is_symlink() or not marker.is_file() or marker.stat().st_uid != os.getuid()
            or marker.stat().st_mode & 0o7777 != 0o600
            or json.loads(marker.read_text()) != claim):
        raise EvidenceError("Production data ownership marker is invalid")
    home = Path(claim["home"])
    app_support, preferences = _production_paths(home)
    if str(app_support) != claim["app_support"] or str(preferences) != claim["preferences"]:
        raise EvidenceError("Production state paths differ from ownership record")
    credentials = app_support / "credentials"
    if app_support.is_symlink() or credentials.is_symlink() or preferences.is_symlink():
        raise EvidenceError("Production state contains a symbolic-link substitution")
    if app_support.exists():
        if (not app_support.is_dir() or app_support.stat().st_uid != os.getuid()
                or app_support.stat().st_mode & 0o022):
            raise EvidenceError("App data directory changed ownership or permissions")
        if credentials.exists():
            if (not credentials.is_dir() or credentials.stat().st_uid != os.getuid()
                    or credentials.stat().st_mode & 0o7777 != 0o700):
                raise EvidenceError("Credential directory changed ownership or permissions")
            entries = list(credentials.iterdir())
            for entry in entries:
                if (entry.is_symlink() or not entry.is_file() or not TOKEN_FILE.fullmatch(entry.name)
                        or entry.stat().st_uid != os.getuid() or entry.stat().st_mode & 0o7777 != 0o600
                        or entry.stat().st_nlink != 1):
                    raise EvidenceError("Credential directory contains an unexpected entry")
            for entry in entries:
                entry.unlink()
            credentials.rmdir()
        app_support.rmdir()  # Unknown files stop cleanup instead of being deleted.
    if not delete_defaults_domain() or preferences.exists() or preferences.is_symlink():
        raise EvidenceError("Production defaults domain was not deleted and verified")
    marker.unlink()
    return True


def require_hosted_ci(candidate_sha: str, manifest_ci: dict) -> dict:
    ci = internal_package.validate_ci(candidate_sha)
    if ci != manifest_ci:
        raise Blocked("Package builder and test runner are not the same protected CI attempt")
    if any(key.startswith(("TM_INTERNAL_", "TM_E2E_SIGNING_")) for key in os.environ):
        raise Blocked("Final-package test job must not receive release signing secrets")
    if (platform.system() != "Darwin" or platform.mac_ver()[0].split(".")[0] != "15"
            or platform.machine() not in ("arm64", "x86_64")):
        raise Blocked("Final-package runner requires macOS 15 arm64 or Intel")
    console = subprocess.run(["stat", "-f", "%Su", "/dev/console"], capture_output=True,
                             text=True, check=False, timeout=10)
    if console.returncode or console.stdout.strip() != getpass.getuser():
        raise Blocked("The hosted GUI session and test user differ")
    return ci


def inspect_spctl(app: Path) -> dict:
    result = subprocess.run(["spctl", "--assess", "--type", "execute", "-vv", str(app)],
                            capture_output=True, text=True, check=False, timeout=30)
    output = (result.stdout + "\n" + result.stderr).strip()
    if not output:
        raise EvidenceError("Gatekeeper returned no inspectable result")
    return {"exit_code": result.returncode, "output": output[:2000]}


def stop_service(process: subprocess.Popen | None) -> bool:
    if process is None:
        return True
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    return process.poll() is not None


def start_service(root: Path, database: Path, log: Path, *, port: int,
                  listener: socket.socket | None = None) -> tuple[subprocess.Popen, str, socket.socket]:
    listener = listener or native_e2e.reserve_loopback(port)
    stream = log.open("xb")
    try:
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("TM_TEST_", "TM_INTERNAL_", "TM_E2E_SIGNING_"))}
        env["TOKENMETER_DATABASE_URL"] = "sqlite:///" + str(database)
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.tokenmeter_server.main:app",
                                    "--fd", str(listener.fileno()), "--no-proxy-headers"],
                                   cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                   pass_fds=(listener.fileno(),))
    except BaseException:
        listener.close()
        stream.close()
        raise
    stream.close()
    return process, f"http://127.0.0.1:{listener.getsockname()[1]}", listener


def verify_sqlite_restore(database: Path, case_output: Path, private: Path, root: Path) -> dict:
    """Keep only a synthetic no-session backup/restore for independent review."""
    backup = case_output / "initial-backup.db"
    restored = case_output / "initial-restored.db"
    with sqlite3.connect(database) as source, sqlite3.connect(backup) as target:
        source.backup(target)
    with sqlite3.connect(backup) as source, sqlite3.connect(restored) as target:
        source.backup(target)
    with sqlite3.connect(backup) as first, sqlite3.connect(restored) as second:
        original_rows = list(first.iterdump())
        restored_rows = list(second.iterdump())
        integrity = second.execute("PRAGMA integrity_check").fetchone()[0]
        schema = second.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        owner = second.execute("SELECT environment,run_id FROM tokenmeter_seed_owner").fetchall()
        users = second.execute("SELECT username,role,is_active,must_change_password FROM users").fetchall()
    if (original_rows != restored_rows or integrity != "ok" or schema != "0001"
            or owner != [("production", "production-init")]
            or users != [("admin", "admin", 1, 1)]):
        raise EvidenceError("Isolated production SQLite backup/restore differs from initial state")
    # API login uses a third disposable copy so archived backup/restored bytes
    # remain the exact pre-session state for the parent verifier.
    api_copy = private / "restore-api-check.db"
    shutil.copyfile(restored, api_copy)
    process = None
    listener = None
    try:
        process, address, listener = start_service(root, api_copy, case_output / "restore-service.log", port=0)
        native_e2e.wait_for_service(process, address)
        request = Request(address + "/v1/auth/login", method="POST",
                          data=json.dumps({"username": "admin", "password": "123456"}).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=10) as response:
            value = json.loads(response.read())
            api_verified = response.status == 200 and isinstance(value.get("access_token"), str)
    finally:
        if listener is not None:
            listener.close()
        if not stop_service(process):
            raise EvidenceError("Restored SQLite API service did not stop")
        for suffix in ("", "-wal", "-shm"):
            Path(str(api_copy) + suffix).unlink(missing_ok=True)
    if not api_verified:
        raise EvidenceError("Restored SQLite API did not accept its initial administrator")
    state = {"integrity_check": "ok", "schema_version": "0001",
             "table_rows_match": True, "api_login_verified": True}
    state_file = case_output / "restore-state.json"
    save_json(state_file, state)
    return {"fixture_kind": "production_bootstrap", "synthetic_only": True,
            "backup_artifact": backup, "backup_sha256": file_sha256(backup),
            "restored_artifact": restored, "restored_sha256": file_sha256(restored),
            "restored_state_artifact": state_file, "restored_state_sha256": file_sha256(state_file),
            "verified": True}


def verify_builder_manifest(config_path: Path, manifest_path: Path, dmg: Path, update_zip: Path,
                            candidate_sha: str, ci: dict) -> tuple[dict, dict, dict[str, Path]]:
    if Path(config_path).is_symlink() or Path(manifest_path).is_symlink():
        raise EvidenceError("Final-package config or manifest path contains a symbolic link")
    config_path = Path(config_path).resolve(strict=True)
    manifest_path = Path(manifest_path).resolve(strict=True)
    if not config_path.is_file() or not manifest_path.is_file():
        raise EvidenceError("Final-package config or manifest is not a regular file")
    config = internal_package.validate_config(native_e2e.json_file(config_path))
    manifest = native_e2e.json_file(manifest_path)
    if (manifest.get("schema_version") != 1 or manifest.get("distribution_profile") != "internal"
            or manifest.get("release_id") != config["release_id"]
            or manifest.get("candidate_sha") != candidate_sha or manifest.get("ci") != ci
            or manifest.get("config_sha256") != file_sha256(config_path)
            or manifest.get("cleanup_completed") is not True
            or manifest.get("release_eligible") is not False):
        raise EvidenceError("Builder manifest does not bind this protected candidate and config")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {"dmg", "candidate_zip", "update_zip", "server_zip"}:
        raise EvidenceError("Builder manifest lacks a required final artifact")
    root = manifest_path.parent
    files = {name: require_artifact(root, descriptor, root / descriptor["path"])
             for name, descriptor in artifacts.items()}
    if files["dmg"] != Path(dmg).resolve(strict=True) or files["update_zip"] != Path(update_zip).resolve(strict=True):
        raise EvidenceError("Runner was given another DMG or higher-version archive")
    app, higher = manifest.get("app"), manifest.get("update_app")
    if (not isinstance(app, dict) or not isinstance(higher, dict)
            or app.get("bundle_id") != BUNDLE_ID or higher.get("bundle_id") != BUNDLE_ID
            or app.get("build") != "100" or higher.get("build") != "101"
            or app.get("public_key") != config["update_public_key"]
            or higher.get("public_key") != config["update_public_key"]
            or app.get("code_sign_identity") != higher.get("code_sign_identity")
            or app.get("designated_requirement") != higher.get("designated_requirement")
            or app.get("architectures") != config["architectures"]
            or higher.get("architectures") != config["architectures"]):
        raise EvidenceError("Candidate and update are not the same signed production line")
    signatures = manifest.get("signatures")
    if not isinstance(signatures, dict):
        raise EvidenceError("Builder manifest lacks signed archive evidence")
    with tempfile.TemporaryDirectory(prefix="tokenmeter-signature-check-") as work:
        for name, field in (("candidate_zip", "candidate_ed_signature"),
                            ("update_zip", "update_ed_signature")):
            signature = signatures.get(field)
            if not isinstance(signature, str):
                raise EvidenceError("Signed archive has no Ed25519 signature")
            internal_package.verify_ed_signature(files[name], signature, config["update_public_key"], Path(work))
    return config, manifest, files


def mount_dmg(root: Path, dmg: Path, mount: Path, output: Path) -> None:
    mount.mkdir(mode=0o700)
    native_e2e.command(["hdiutil", "verify", str(dmg)], root=root, log=output / "dmg-verify.log", timeout=300)
    native_e2e.command(["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", str(mount), str(dmg)],
                       root=root, log=output / "dmg-attach.log", timeout=120)


def unmount_dmg(root: Path, mount: Path, output: Path) -> None:
    native_e2e.command(["hdiutil", "detach", str(mount)], root=root, log=output / "dmg-detach.log", timeout=120)


def install_from_mounted_dmg(root: Path, mounted_app: Path, private: Path, case_output: Path,
                             config: dict, expected: dict) -> tuple[Path, dict, dict]:
    if mounted_app.is_symlink() or not mounted_app.is_dir():
        raise EvidenceError("Final DMG has no regular production App")
    installed_parent = private / "installed"
    installed_parent.mkdir(mode=0o700)
    app = installed_parent / "TokenMeter.app"
    if app.exists() or app.is_symlink():
        raise EvidenceError("Final App installation path already exists")
    native_e2e.command(["ditto", str(mounted_app), str(app)], root=root,
                       log=case_output / "install.log", timeout=180)
    scratch = private / "verify-installed"
    scratch.mkdir()
    observed = internal_package.verify_app(app, config, config["build"], scratch)
    if observed != expected or tree_sha256(app) != expected["tree_sha256"]:
        raise EvidenceError("Installed production App differs from the final DMG")
    # Reproduce quarantine only on the run-owned App. The system assessment is
    # recorded as-is; an internal self-signed identity is not Apple trusted.
    native_e2e.command(["xattr", "-w", "com.apple.quarantine", "0081;00000000;TokenMeterInternalCI;", str(app)],
                       root=root, log=case_output / "quarantine-set.log", timeout=30)
    before = inspect_spctl(app)
    native_e2e.command(["xattr", "-d", "com.apple.quarantine", str(app)], root=root,
                       log=case_output / "quarantine-remove.log", timeout=30)
    after = inspect_spctl(app)
    save_json(case_output / "gatekeeper.json", {"before": before, "after": after,
                                                "quarantine_removed_on_owned_app_only": True})
    # Clearing this precise internal test copy's quarantine is the documented
    # local permission path. It does not alter system trust or Gatekeeper.
    after_scratch = private / "verify-after-quarantine"
    after_scratch.mkdir()
    verified = internal_package.verify_app(app, config, config["build"], after_scratch)
    if verified != expected:
        raise EvidenceError("Controlled internal permission changed the signed App")
    return app, before, after


def prepare_ui_test_bundle(root: Path, private: Path, output: Path, run_id: str,
                           architecture: str) -> Path:
    derived = private / "derived-tests"
    dummy = private / "unused-uitesting-credentials"
    dummy.mkdir(mode=0o700)
    command = ["xcodebuild", "-project", str(root / "apps/macos/TokenMeter.xcodeproj"),
               "-scheme", "TokenMeter", "-configuration", "UITesting", "-derivedDataPath", str(derived),
               "-destination", "platform=macOS,arch=" + architecture, "-parallel-testing-enabled", "NO",
               "-disableAutomaticPackageResolution", "build-for-testing", "CODE_SIGN_IDENTITY=-",
               "CODE_SIGNING_ALLOWED=YES", "TM_TEST_RUN_ID=" + run_id,
               "TM_TEST_CREDENTIALS_DIR=" + str(dummy), "TM_TEST_API_URL="]
    native_e2e.command(command, root=root, log=output / "build-ui-tests.log", timeout=1800)
    app = derived / "Build/Products/UITesting/TokenMeter.app"
    if not app.is_dir() or plistlib.loads((app / "Contents/Info.plist").read_bytes()).get("CFBundleIdentifier") != BUNDLE_ID + ".UITesting":
        raise EvidenceError("Xcode did not build the separate UI test harness target")
    return derived


def terminate_owned_app(installed: Path) -> None:
    executable = str(installed / "Contents/MacOS/TokenMeter")
    def owned_processes() -> list[int]:
        result = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True,
                                check=False, timeout=10)
        if result.returncode:
            raise EvidenceError("Cannot inspect owned App process after native test")
        found: list[int] = []
        for line in result.stdout.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and (parts[1] == executable or parts[1].startswith(executable + " ")):
                found.append(int(parts[0]))
        return found

    for pid in owned_processes():
        try:
            os.kill(pid, 15)
        except ProcessLookupError:
            pass
    # The XCTest tearDown is the normal termination path. A still-running App
    # would race standard UserDefaults cleanup, so never silently continue.
    deadline = time.monotonic() + 5
    while owned_processes():
        if time.monotonic() >= deadline:
            raise EvidenceError("Installed App remained running after its test case")
        time.sleep(0.1)


def execute(root: Path, output: Path, report: dict, *, config_path: Path, manifest_path: Path,
            dmg: Path, update_zip: Path, candidate_sha: str) -> None:
    """Populate evidence from actual installed App, servers and XCTest runs."""
    report["source_commit"] = native_e2e.git(root, "rev-parse", "HEAD")
    report["working_tree_dirty"] = bool(native_e2e.git(root, "status", "--porcelain"))
    if report["source_commit"] != candidate_sha or report["working_tree_dirty"]:
        raise Blocked("Final-package E2E requires the clean exact candidate checkout")
    report["platform"] = native_e2e.preflight(root)
    ci_preview = internal_package.validate_ci(candidate_sha)
    config, manifest, files = verify_builder_manifest(config_path, manifest_path, dmg, update_zip,
                                                       candidate_sha, ci_preview)
    report["ci"] = require_hosted_ci(candidate_sha, manifest["ci"])
    architecture = report["platform"]["architecture"]
    if (architecture not in config["architectures"] or report["platform"]["macos"].split(".")[0] != "15"
            or report["platform"]["xcode"] != "Xcode 16.4\nBuild version 16F6"):
        raise Blocked("Final-package platform or Xcode differs from approved macOS 15 matrix")
    expected = native_e2e.required_cases(root)
    if set(expected) != {f"E2E-TM001-{number:03d}" for number in range(1, 7)}:
        raise EvidenceError("Internal release requires exactly six native cases")
    report["expected_cases"] = list(expected)
    report["manifest_sha256"] = native_e2e.snapshot(root)
    report["package"] = {"dmg_sha256": manifest["artifacts"]["dmg"]["sha256"],
                         "app_tree_sha256": manifest["app"]["tree_sha256"],
                         "update_zip_sha256": manifest["artifacts"]["update_zip"]["sha256"],
                         "app_bundle_id": manifest["app"]["bundle_id"], "build": manifest["app"]["build"],
                         "architectures": manifest["app"]["architectures"],
                         "code_sign_identity": manifest["app"]["code_sign_identity"],
                         "signature_kind": "internal_self_signed"}
    report["installation"] = {"owned_paths": {},
                              "source_dmg_sha256": manifest["artifacts"]["dmg"]["sha256"]}
    account_data = native_e2e.load_module(root / "tests/server/fixtures.py", "release_account_data")
    bootstrap_data = native_e2e.load_module(root / "scripts/bootstrap_sqlite.py", "release_bootstrap_data")
    failed: list[str] = []
    run_id = report["run_id"]
    with tempfile.TemporaryDirectory(prefix=f"tokenmeter-internal-{run_id}-",
                                     dir=os.environ["RUNNER_TEMP"]) as workspace:
        private = Path(workspace).resolve(strict=True)
        private.chmod(0o700)
        derived = prepare_ui_test_bundle(root, private, output, run_id[:30], architecture)
        mount = private / "mounted-dmg"
        mounted = False
        try:
            mount_dmg(root, files["dmg"], mount, output)
            mounted = True
            internal_package.validate_dmg_layout(mount, root / "docs/releases/02-installation.md")
            mounted_app = mount / "TokenMeter.app"
            mount_scratch = private / "verify-mounted"
            mount_scratch.mkdir()
            if internal_package.verify_app(mounted_app, config, config["build"], mount_scratch) != manifest["app"]:
                raise EvidenceError("Mounted final DMG does not contain the builder's production App")
            for index, (case_id, native_test) in enumerate(expected.items(), 1):
                native_e2e.progress(case_id, "prepare-final-package-case")
                case_output = output / case_id
                case_output.mkdir(mode=0o700)
                case_private = private / case_id
                case_private.mkdir(mode=0o700)
                fixture_run_id = (run_id[:24] + f"-c{index:03d}").lower()
                claim = claim_production_state(Path.home(), case_private, run_id)
                profile = native_e2e.fixture_profile(case_id)
                process = secondary_process = None
                listener = secondary_listener = None
                update = None
                installed = None
                secondary_private = secondary_run_id = None
                suite: dict | None = None
                try:
                    if profile == "production_bootstrap":
                        database, public_manifest = native_e2e.prepare_production_bootstrap(
                            case_private, case_output, bootstrap_data)
                        restored = verify_sqlite_restore(database, case_output, case_private, root)
                        report["sqlite_restore"] = {
                            key: relative_file(value, output) if isinstance(value, Path) else value
                            for key, value in restored.items()}
                    elif profile == "dual_service_routes":
                        (database, secondary_database, secondary_private, secondary_run_id,
                         public_manifest, listener) = native_e2e.prepare_dual_service_databases(
                            root, case_private, case_output, account_data, fixture_run_id)
                    else:
                        database, fixture = native_e2e.prepare_account_database(
                            root, case_private, case_output, account_data, fixture_run_id, 42)
                        public_manifest = case_output / "fixture-manifest.json"
                        save_json(public_manifest, native_e2e.json_file(fixture / "manifest.json"))
                    process, address, listener = start_service(root, database, case_output / "service.log",
                                                               port=49176, listener=listener)
                    try:
                        native_e2e.wait_for_service(process, address)
                    finally:
                        listener.close(); listener = None
                    if address != DEFAULT_API:
                        raise EvidenceError("Installed production App needs the exact built-in service origin")
                    secondary_address = None
                    if profile == "dual_service_routes":
                        secondary_process, secondary_address, secondary_listener = start_service(
                            root, secondary_database, case_output / "service-secondary.log", port=0)
                        try:
                            native_e2e.wait_for_service(secondary_process, secondary_address)
                        finally:
                            secondary_listener.close(); secondary_listener = None
                    if case_id in ("E2E-TM001-004", "E2E-TM001-006"):
                        update = UpdateSource(case_private / "update-source-private", case_output)
                        update.prepare_existing_public_key(config["update_public_key"])
                        update.start()
                        if update.url != DEFAULT_SOURCE:
                            raise Blocked("Installed App's fixed loopback update source is unavailable")
                        if case_id == "E2E-TM001-004":
                            update.publish(files["update_zip"], manifest["signatures"]["update_ed_signature"])
                    installed, before, after = install_from_mounted_dmg(
                        root, mounted_app, case_private, case_output, config, manifest["app"])
                    report["installation"]["owned_paths"][case_id] = str(installed)
                    if "spctl_before" not in report["package"]:
                        report["package"]["spctl_before"] = before
                        report["package"]["spctl_after"] = after
                    test_env = {key: value for key, value in os.environ.items()
                                if not key.startswith(("TM_TEST_", "TM_INTERNAL_", "TM_E2E_SIGNING_"))}
                    test_env.update({"TM_TEST_API_URL": address, "TM_TEST_RUN_ID": fixture_run_id,
                                     "TM_TEST_INSTALLED_APP_PATH": str(installed),
                                     "TM_TEST_EXPECTED_PUBLIC_KEY": config["update_public_key"]})
                    if secondary_address:
                        test_env["TM_TEST_SECOND_API_URL"] = secondary_address
                    if case_id == "E2E-TM001-004":
                        test_env.update({"TM_TEST_UPDATE_CONTROL_URL": update.url + "/control/valid",
                                         "TM_TEST_UPDATE_FORBIDDEN_CONTROL_URL": update.url + "/control/forbidden",
                                         "TM_TEST_UPDATE_REDIRECT_CONTROL_URL": update.url + "/control/redirect",
                                         "TM_TEST_UPDATE_INVALID_CONTROL_URL": update.url + "/control/invalid",
                                         "TM_TEST_UPDATE_CONTROL_TOKEN": update.token,
                                         "TM_TEST_EXPECTED_BUILD": "101"})
                    for key, value in list(test_env.items()):
                        if key.startswith("TM_TEST_"):
                            test_env["TEST_RUNNER_" + key] = value
                    xctestrun = native_e2e.test_configuration(
                        derived, {key: value for key, value in test_env.items() if key.startswith("TM_TEST_")})
                    bundle = case_output / "native.xcresult"
                    command = ["xcodebuild", "test-without-building", "-xctestrun", str(xctestrun),
                               "-destination", "platform=macOS,arch=" + architecture,
                               "-parallel-testing-enabled", "NO", "-only-testing:" + native_test,
                               "-resultBundlePath", str(bundle), "-resultBundleVersion", "3"]
                    native_e2e.progress(case_id, "execute-installed-native-test")
                    result = native_e2e.command(command, root=root, log=case_output / "xcodebuild.log",
                                                env=test_env, timeout=600, required=False)
                    suite = {"case_id": case_id, "native_test": native_test, "exit_code": result.returncode,
                             "xcresult": bundle.relative_to(output).as_posix(), "state": "FAIL",
                             "fixture_manifest": relative_file(public_manifest, output),
                             "fixture_sha256": file_sha256(public_manifest), "native_failures": [],
                             "installed_app_path": str(installed),
                             "installed_app_before_sha256": manifest["app"]["tree_sha256"]}
                    report["suites"].append(suite)
                    if not bundle.is_dir():
                        raise Blocked(f"No native result bundle for {case_id}; xcodebuild exit {result.returncode}")
                    native_e2e.progress(case_id, "parse-installed-native-results")
                    tree, summary = native_e2e.parse_bundle(root, bundle)
                    save_json(case_output / "native-tests.json", tree)
                    save_json(case_output / "native-summary.json", summary)
                    suite["native_failures"] = [failure["failureText"][:1000]
                        for failure in summary.get("testFailures", [])[:3]
                        if isinstance(failure, dict) and isinstance(failure.get("failureText"), str)]
                    if summary.get("totalTestCount", 0) > summary.get("skippedTests", 0):
                        report["executed_cases"] += 1
                    try:
                        suite["destination"] = native_e2e.native_destination(
                            summary, architecture, report["platform"]["macos"])
                        native_e2e.check_native_result(tree, summary, native_test)
                        if result.returncode:
                            raise EvidenceError(f"xcodebuild exited {result.returncode} despite a passing native case")
                    finally:
                        native_e2e.capture_native_artifacts(root, bundle, case_output, suite)
                    if case_id == "E2E-TM001-004":
                        update.verify_exchange()
                        upgrade_scratch = case_private / "verify-upgrade"
                        upgrade_scratch.mkdir()
                        high = internal_package.verify_app(installed, config, config["upgrade_build"], upgrade_scratch)
                        if high != manifest["update_app"]:
                            raise EvidenceError("Sparkle-installed higher App differs from the signed test archive")
                        suite["upgraded_app_sha256"] = high["tree_sha256"]
                        suite["upgraded_build"] = high["build"]
                    else:
                        if tree_sha256(installed) != manifest["app"]["tree_sha256"]:
                            raise EvidenceError("The installed candidate App changed during a non-upgrade case")
                    if profile == "production_bootstrap":
                        native_e2e.assert_production_reinitialization_refused(case_private, bootstrap_data)
                        state = native_e2e.inspect_production_bootstrap(database, after_ui=True)
                        state_file = case_output / "database-state.json"
                        save_json(state_file, {"post_ui_state": state, "reinitialization_refused": True})
                        suite["bootstrap_state_artifact"] = relative_file(state_file, output)
                        suite["bootstrap_state_sha256"] = file_sha256(state_file)
                    suite["state"] = "PASS"
                    report["passed_cases"] += 1
                except EvidenceError as exc:
                    if suite is not None:
                        suite["error"] = str(exc)[:1000]
                        failed.append(f"{case_id}: {exc}")
                    else:
                        raise
                finally:
                    native_e2e.progress(case_id, "cleanup-installed-case")
                    cleanup_errors = []
                    if listener is not None:
                        listener.close()
                    if secondary_listener is not None:
                        secondary_listener.close()
                    for label, child in (("primary", process), ("secondary", secondary_process)):
                        try:
                            if not stop_service(child):
                                cleanup_errors.append(f"{label} service remained running")
                        except (OSError, subprocess.SubprocessError) as exc:
                            cleanup_errors.append(f"{label} service cleanup: {type(exc).__name__}")
                    if update is not None:
                        try:
                            update.close()
                        except (OSError, RuntimeError) as exc:
                            cleanup_errors.append(f"update source cleanup: {type(exc).__name__}")
                        if case_id == "E2E-TM001-004" and suite is not None:
                            for field, name in (("update_fixture_artifact", "update-fixture.json"),
                                                ("update_requests_artifact", "update-requests.json")):
                                path = case_output / name
                                if path.is_file():
                                    suite[field] = relative_file(path, output)
                                    suite[field.replace("_artifact", "_sha256")] = file_sha256(path)
                    try:
                        if installed is not None:
                            terminate_owned_app(installed)
                        cleanup_production_state(claim)
                        report["credential_cleanup"][case_id] = True
                        report["defaults_cleanup"][case_id] = True
                    except (OSError, RuntimeError, ValueError) as exc:
                        cleanup_errors.append(f"production state cleanup: {type(exc).__name__}: {exc}")
                    if profile in ("synthetic_accounts", "dual_service_routes"):
                        try:
                            account_data.reset(fixture_run_id, workspace=case_private)
                            if secondary_private is not None and secondary_run_id is not None:
                                account_data.reset(secondary_run_id, workspace=secondary_private)
                        except (OSError, ValueError) as exc:
                            cleanup_errors.append(f"account fixture cleanup: {type(exc).__name__}")
                    if not cleanup_errors:
                        report["service_cleanup"][case_id] = True
                    else:
                        report.setdefault("cleanup_errors", []).extend(cleanup_errors)
                        raise EvidenceError("; ".join(cleanup_errors))
        finally:
            if mounted:
                unmount_dmg(root, mount, output)
    if failed:
        raise EvidenceError("; ".join(failed))
    if (report["passed_cases"] != 6 or report["executed_cases"] != 6
            or report["credential_cleanup"] != dict.fromkeys(expected, True)
            or report["defaults_cleanup"] != dict.fromkeys(expected, True)
            or report["service_cleanup"] != dict.fromkeys(expected, True)):
        raise EvidenceError("Final DMG native case set or resource cleanup is incomplete")
    if native_e2e.git(root, "status", "--porcelain") or native_e2e.snapshot(root) != report["manifest_sha256"]:
        raise EvidenceError("Final-package source or traceability snapshot changed during execution")
    report["cleanup_completed"] = True
    report["state"] = "PASS"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--dmg", type=Path, required=True)
    parser.add_argument("--update-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--candidate-sha", required=True)
    args = parser.parse_args(argv)
    if (not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", args.run_id)
            or not re.fullmatch(r"[0-9a-f]{40}", args.candidate_sha)):
        print(json.dumps({"state": "BLOCKED", "reason": "Invalid final-package run or candidate identity"}))
        return 2
    output = args.output.absolute()
    if output.is_symlink() or output.exists() or any(parent.is_symlink() for parent in output.parents):
        print(json.dumps({"state": "BLOCKED", "reason": "Final-package evidence output is not a fresh safe directory"}))
        return 2
    output.mkdir(parents=True, mode=0o700)
    release_id = None
    try:
        release_id = native_e2e.json_file(args.config)["release_id"]
    except (OSError, ValueError, KeyError):
        pass
    report = {"schema_version": 1, "run_id": args.run_id, "release_id": release_id,
              "distribution_profile": "internal", "scope": "final_package", "phase": "release",
              "state": "BLOCKED", "release_eligible": False, "started_at": utc_now(),
              "source_commit": None, "working_tree_dirty": None, "platform": {}, "ci": {},
              "expected_cases": [], "executed_cases": 0, "passed_cases": 0, "suites": [],
              "credential_cleanup": {}, "defaults_cleanup": {}, "service_cleanup": {},
              "cleanup_completed": False, "errors": [], "blockers": [], "cleanup_errors": []}
    try:
        execute(ROOT, output, report, config_path=args.config, manifest_path=args.package_manifest,
                dmg=args.dmg, update_zip=args.update_zip, candidate_sha=args.candidate_sha)
    except EvidenceError as exc:
        report["state"] = "FAIL"
        report["errors"].append(str(exc)[:1000])
    except (Blocked, internal_package.PackageError, OSError, RuntimeError, ValueError,
            KeyError, subprocess.SubprocessError) as exc:
        prior_failure = any(suite.get("state") == "FAIL" for suite in report["suites"])
        report["state"] = "FAIL" if prior_failure or report["cleanup_errors"] else "BLOCKED"
        report["blockers"].append(f"{type(exc).__name__}: {str(exc)[:1000]}")
    finally:
        report["finished_at"] = utc_now()
        save_json(output / "result.json", report)
    print(json.dumps({"state": report["state"], "result": str(output / "result.json"),
                      "executed_cases": report["executed_cases"], "passed_cases": report["passed_cases"],
                      "release_eligible": False}, ensure_ascii=False), flush=True)
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[report["state"]]


if __name__ == "__main__":
    raise SystemExit(main())
