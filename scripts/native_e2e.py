"""Execute and independently verify native XCUITest evidence for this checkout.

No external success report is accepted. Every result is parsed again with Apple's
xcresulttool before an iteration can pass. Release qualification is separate.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shlex
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.request import urlopen


class Blocked(RuntimeError):
    """The environment or required implementation cannot execute the test."""


class EvidenceError(RuntimeError):
    """An execution failed or evidence does not match the requested test."""


FIXTURE_PROFILES = {f"E2E-TM001-{number:03d}": "synthetic_accounts" for number in range(1, 5)} | {
    "E2E-TM001-005": "production_bootstrap"
}
PRODUCTION_BOOTSTRAP_USER_ID = "00000000-0000-4000-8000-000000000005"


def fixture_profile(case_id: str) -> str:
    try:
        return FIXTURE_PROFILES[case_id]
    except KeyError as exc:
        raise Blocked(f"No native fixture profile for {case_id}") from exc


def expected_bootstrap_state(*, after_ui: bool) -> dict:
    return {"fixture_kind": "production_bootstrap", "schema_version": "0001",
            "owner": "production-init", "account_count": 1, "username": "admin", "role": "admin",
            "must_change_password": not after_ui, "credential_version": 2 if after_ui else 1,
            "phase": "after_ui" if after_ui else "initial"}


def json_file(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvidenceError(f"Expected JSON object: {path.name}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(path: Path, *, allow_internal_symlinks: bool = False) -> str:
    if path.is_symlink() or not path.is_dir():
        raise EvidenceError(f"Missing regular artifact directory: {path.name}")
    digest = hashlib.sha256()
    count = 0
    for item in sorted(path.rglob("*")):
        relative = item.relative_to(path).as_posix()
        if item.is_symlink():
            if not allow_internal_symlinks or not item.resolve().is_relative_to(path.resolve()):
                raise EvidenceError(f"Unsafe artifact symlink: {relative}")
            digest.update(f"link:{relative}:{os.readlink(item)}\n".encode())
        elif item.is_file():
            digest.update(f"file:{relative}:{sha256(item)}\n".encode())
            count += 1
    if not count:
        raise EvidenceError(f"Empty native artifact: {path.name}")
    return digest.hexdigest()


def new_run_directory(root: Path, run_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_id):
        raise EvidenceError("Invalid run identity")
    for path in (root / ".local", root / ".local/e2e", root / ".local/e2e" / run_id):
        if path.is_symlink():
            raise EvidenceError("Refusing symlink artifact directory")
    result = root / ".local/e2e" / run_id
    result.mkdir(parents=True, exist_ok=False)
    return result


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    if result.returncode:
        raise Blocked("Cannot identify source checkout")
    return result.stdout.strip()


def required_cases(root: Path) -> dict[str, str]:
    try:
        release_id = json_file(root / "releases/current.json")["release_id"]
        if not re.fullmatch(r"v\d+\.\d+\.\d+-\d{8}T\d{6}Z", release_id):
            raise ValueError("Invalid release ID")
        target = json_file(root / f"releases/{release_id}/00-manifest.json")["feature_ids"]
        features = json_file(root / "tests/feature_matrix.json")["features"]
        selected = set(target) | {f["id"] for f in features if f["status"] == "implemented"}
        if not target or not selected or selected - {f["id"] for f in features}:
            raise ValueError("Missing target feature; a target cannot be excluded by status")
        result: dict[str, str] = {}
        for feature in features:
            if feature["id"] not in selected:
                continue
            if not feature["cases"]:
                raise ValueError("Target has no required native cases")
            for case in feature["cases"]:
                identifier = case.get("native_test")
                if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_]+/[A-Za-z0-9_]+/test[A-Za-z0-9_]+", identifier):
                    raise ValueError(f"Native XCTest identity missing for {case['id']}")
                if case["id"] in result or identifier in result.values():
                    raise ValueError("Duplicate case or native test binding")
                result[case["id"]] = identifier
        if not result:
            raise ValueError("Zero native cases")
        return result
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise Blocked(f"Native test contract unavailable: {exc}") from exc


def check_native_result(tree: dict, summary: dict, expected: str) -> list[str]:
    """Use Xcode 16+ native tree and summary, never our own passed boolean."""
    discovered: list[tuple[str, str]] = []

    def walk(node: Any, bundle: str = "", suite: str = "") -> None:
        if not isinstance(node, dict):
            raise EvidenceError("Malformed native test node")
        kind = node.get("nodeType")
        if kind in ("Test Bundle", "UI test bundle"):
            bundle = node.get("name", "").removesuffix(".xctest")
        if kind == "Test Suite":
            suite = node.get("name", "")
        if kind == "Test Case":
            identity = node.get("nodeIdentifier", "").removesuffix("()")
            if not identity:
                identity = f"{suite}/{node.get('name', '').removesuffix('()')}"
            if identity.count("/") == 1:
                identity = f"{bundle}/{identity}"
            discovered.append((identity, node.get("result", "")))
        for child in node.get("children", []):
            walk(child, bundle, suite)

    if not isinstance(tree, dict) or not isinstance(tree.get("testNodes"), list):
        raise EvidenceError("Unknown or absent native test tree")
    for node in tree["testNodes"]:
        walk(node)
    if discovered != [(expected, "Passed")]:
        raise EvidenceError(f"Native case set/result differs: {discovered!r}; expected {expected}")
    for key, value in (("totalTestCount", 1), ("passedTests", 1), ("failedTests", 0), ("skippedTests", 0)):
        if type(summary.get(key)) is not int or summary[key] != value:
            raise EvidenceError(f"Native summary {key} must equal {value}")
    if summary.get("result") != "Passed" or summary.get("testFailures", []) != []:
        raise EvidenceError("Native summary contains unsuccessful results")
    return [expected]


def architecture_family(architecture: str) -> str:
    # xcresult reports arm64e for macOS on Apple Silicon even when the requested
    # Xcode destination is arm64. Preserve the observed value in evidence.
    families = {"arm64": "arm64", "arm64e": "arm64", "x86_64": "x86_64", "x86_64h": "x86_64"}
    if not isinstance(architecture, str) or architecture not in families:
        raise EvidenceError("Unknown native architecture")
    return families[architecture]


def native_destination(summary: dict, architecture: str, macos: str) -> dict:
    configurations = summary.get("devicesAndConfigurations")
    if (not isinstance(configurations, list) or len(configurations) != 1
            or not isinstance(configurations[0], dict)):
        raise EvidenceError("Expected one actual native device/configuration")
    device = configurations[0].get("device")
    if not isinstance(device, dict) or device.get("platform") != "macOS":
        raise EvidenceError("Native destination is not macOS")
    observed = architecture_family(device.get("architecture"))
    if observed != architecture_family(architecture) or device.get("osVersion") != macos:
        raise EvidenceError("Actual native destination differs from requested platform")
    if not isinstance(device.get("deviceId"), str) or not device["deviceId"]:
        raise EvidenceError("Native destination has no device identity")
    return {key: device[key] for key in ("architecture", "deviceId", "osVersion", "platform")} | {"architecture_family": observed}


def command(args: list[str], *, root: Path, log: Path, env: dict | None = None,
            timeout: int = 1200, required: bool = True) -> subprocess.CompletedProcess:
    with log.open("wb") as stream:
        try:
            result = subprocess.run(args, cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                    check=False, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise Blocked(f"Command timed out; evidence: {log.name}") from exc
    if required and result.returncode:
        raise EvidenceError(f"Command exited {result.returncode}; evidence: {log.name}")
    return result


def require_upgrade_environment(root: Path, case_output: Path) -> None:
    result = command([sys.executable, str(root / "scripts/native_environment.py")], root=root,
                     log=case_output / "environment-probe.log", timeout=300, required=False)
    if result.returncode == 2:
        raise Blocked("E2E-TM001-004 environment is unavailable; see environment-probe.log and environment.json")
    if result.returncode:
        raise EvidenceError("E2E-TM001-004 environment probe failed; see environment-probe.log and environment.json")


def parse_bundle(root: Path, bundle: Path) -> tuple[dict, dict]:
    values = []
    for kind in ("tests", "summary"):
        result = subprocess.run(["xcrun", "xcresulttool", "get", "test-results", kind,
                                 "--path", str(bundle)], cwd=root, capture_output=True, text=True,
                                check=False, timeout=60)
        if result.returncode:
            raise Blocked(f"Native xcresulttool cannot parse {bundle.name}: {kind}")
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise EvidenceError("Native result is not an object")
        values.append(value)
    return values[0], values[1]


def export_attachments(root: Path, bundle: Path, output: Path) -> list[dict]:
    help_result = subprocess.run(["xcrun", "xcresulttool", "help", "export", "attachments"],
                                 cwd=root, capture_output=True, text=True, check=False, timeout=30)
    help_text = help_result.stdout + help_result.stderr
    (output / "attachments-help.log").write_text(help_text)
    if help_result.returncode or not all(option in help_text for option in ("--path", "--output-path")):
        raise Blocked("Selected xcresulttool does not advertise required attachment export arguments")
    destination = output / "attachments"
    if destination.exists() or destination.is_symlink():
        raise EvidenceError("Native attachment export must use a new directory")
    command(["xcrun", "xcresulttool", "export", "attachments", "--path", str(bundle), "--output-path", str(destination)],
            root=root, log=output / "attachments-export.log", timeout=60)
    screenshots = []
    for picture in sorted(destination.rglob("*.png")):
        if picture.is_symlink() or not picture.resolve().is_relative_to(destination.resolve()):
            raise EvidenceError("Native screenshot escaped its export directory")
        with picture.open("rb") as stream:
            if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                raise EvidenceError("Native screenshot has an invalid PNG header")
        screenshots.append({"path": picture.relative_to(output).as_posix(), "sha256": sha256(picture)})
    if not screenshots:
        raise EvidenceError("Native result exported no required window screenshots")
    return screenshots


def snapshot(root: Path) -> dict[str, str]:
    return {name: sha256(root / name) for name in (
        "releases/current.json", "tests/feature_matrix.json", "tests/acceptance.json",
        "tests/datasets.json", "docs/catalog.json")}


def verify_report(root: Path, path: Path, *, run_id: str, phase: str,
                  not_before: float) -> dict:
    """Reopen raw bundles after the fixed child process has completed."""
    if path.is_symlink() or path.parent != root / ".local/e2e" / run_id or any(
            parent.is_symlink() for parent in (root / ".local", root / ".local/e2e", path.parent)):
        raise EvidenceError("Report path is not owned by this invocation")
    report = json_file(path)
    if report.get("state") != "PASS" or not report.get("runner_implemented"):
        raise Blocked("Native execution has not passed")
    if report.get("run_id") != run_id or report.get("phase") != phase:
        raise EvidenceError("Evidence belongs to another invocation")
    started = datetime.fromisoformat(report["started_at"]).timestamp()
    finished = datetime.fromisoformat(report["finished_at"]).timestamp()
    if not (not_before - 1 <= started <= finished <= time.time() + 1) or time.time() - started > 7200:
        raise EvidenceError("Native evidence is stale or time range is invalid")
    if report.get("source_commit") != git(root, "rev-parse", "HEAD") or report.get("working_tree_dirty"):
        raise EvidenceError("Native evidence does not match a clean candidate")
    if git(root, "status", "--porcelain"):
        raise EvidenceError("Source changed during native verification")
    if report.get("manifest_sha256") != snapshot(root):
        raise EvidenceError("Native input manifests changed")
    expected = required_cases(root)
    for case_id in expected:
        fixture_profile(case_id)
    if report.get("expected_cases") != list(expected):
        raise EvidenceError("Recorded required native cases differ from the current matrix")
    suites = report.get("suites")
    if not isinstance(suites, list) or len(suites) != len(expected):
        raise EvidenceError("Incomplete native suites")
    observed: set[str] = set()
    for suite in suites:
        case_id = suite.get("case_id")
        if case_id not in expected or case_id in observed or suite.get("exit_code") != 0:
            raise EvidenceError("Wrong, duplicate, or failed native suite")
        relative = suite.get("xcresult", "")
        bundle = path.parent / relative
        if not bundle.resolve().is_relative_to(path.parent.resolve()) or bundle.is_symlink():
            raise EvidenceError("Native artifact escapes current run")
        if tree_digest(bundle) != suite.get("xcresult_sha256"):
            raise EvidenceError("Native bundle was changed after execution")
        if bundle.stat().st_mtime < started - 1:
            raise EvidenceError("Native bundle predates current execution")
        tree, summary = parse_bundle(root, bundle)
        check_native_result(tree, summary, expected[case_id])
        actual = native_destination(summary, report["platform"]["architecture"], report["platform"]["macos"])
        if suite.get("destination") != actual:
            raise EvidenceError("Recorded native destination differs from original xcresult")
        screenshots = suite.get("screenshots")
        if not isinstance(screenshots, list) or not screenshots:
            raise EvidenceError("Required native window screenshots are absent")
        for screenshot in screenshots:
            artifact = path.parent / case_id / screenshot["path"]
            if (artifact.is_symlink() or not artifact.resolve().is_relative_to((path.parent / case_id).resolve())
                    or not artifact.is_file() or sha256(artifact) != screenshot["sha256"]):
                raise EvidenceError("Native window screenshot changed or escaped its case")
        for relative_key, digest_key in (("fixture_manifest", "fixture_sha256"), ("app_artifact", "app_sha256")):
            artifact = path.parent / suite.get(relative_key, "")
            if (not artifact.resolve().is_relative_to(path.parent.resolve()) or artifact.is_symlink()
                    or not artifact.is_file() or not artifact.stat().st_size
                    or sha256(artifact) != suite.get(digest_key)):
                raise EvidenceError("Missing or changed fixture/build artifact")
        if fixture_profile(case_id) == "production_bootstrap":
            manifest = json_file(path.parent / suite["fixture_manifest"])
            if (manifest.get("fixture_kind") != "production_bootstrap"
                    or manifest.get("database") != "database/production/production.db"
                    or manifest.get("initial_state") != expected_bootstrap_state(after_ui=False)
                    or not all(isinstance(manifest.get(key), str) and re.fullmatch(r"[a-f0-9]{64}", manifest[key])
                               for key in ("database_sha256", "seed_sql_sha256"))):
                raise EvidenceError("Production bootstrap manifest does not describe the isolated initial database")
            state_path = path.parent / suite.get("bootstrap_state_artifact", "")
            if (state_path.is_symlink() or not state_path.resolve().is_relative_to((path.parent / case_id).resolve())
                    or not state_path.is_file() or sha256(state_path) != suite.get("bootstrap_state_sha256")
                    or json_file(state_path) != {"post_ui_state": expected_bootstrap_state(after_ui=True),
                                                 "reinitialization_refused": True}):
                raise EvidenceError("Production bootstrap post-UI database state is missing or changed")
        observed.add(case_id)
    if observed != set(expected) or report.get("executed_cases") != len(expected):
        raise EvidenceError("Native execution differs from required coverage")
    if report.get("cleanup_completed") is not True:
        raise EvidenceError("Native resources were not cleaned")
    if phase == "release":
        raise Blocked("Final signed packages, full supported matrix and protected release verification are not connected")
    return report


def preflight(root: Path) -> dict:
    if platform.system() != "Darwin":
        raise Blocked("Native XCUITest requires macOS")
    selected = subprocess.run(["xcode-select", "-p"], text=True, capture_output=True, check=False)
    if selected.returncode or ".app/Contents/Developer" not in selected.stdout:
        raise Blocked("Full Xcode is not selected; no installation was attempted")
    version = subprocess.run(["xcodebuild", "-version"], text=True, capture_output=True, check=False)
    match = re.search(r"Xcode (\d+)", version.stdout)
    if version.returncode or not match or int(match[1]) < 16:
        raise Blocked("Xcode 16+ native result commands are required")
    console_user = subprocess.run(["stat", "-f", "%Su", "/dev/console"], text=True, capture_output=True, check=False)
    if console_user.returncode or console_user.stdout.strip() in ("", "root", "loginwindow"):
        raise Blocked("No logged-in macOS GUI session")
    for relative in ("apps/macos/TokenMeter.xcodeproj/project.pbxproj", "tests/server/fixtures.py",
                     "server/tokenmeter_server/main.py", "apps/macos/build_update_fixture.py",
                     "scripts/bootstrap_sqlite.py"):
        if not (root / relative).is_file():
            raise Blocked(f"Required native input is absent: {relative}")
    return {"xcode": version.stdout.strip(), "macos": platform.mac_ver()[0], "architecture": platform.machine()}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Blocked(f"Cannot load fixture program: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect_production_bootstrap(database: Path, *, after_ui: bool) -> dict:
    """Read only the owned, isolated production fixture; never export its DB or hashes."""
    if database.is_symlink() or not database.is_file() or database.name != "production.db":
        raise EvidenceError("Isolated production fixture database is missing or unsafe")
    try:
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            schema = connection.execute("SELECT version_num FROM alembic_version").fetchall()
            owner = connection.execute("SELECT environment, run_id FROM tokenmeter_seed_owner").fetchall()
            users = connection.execute(
                "SELECT id, username, role, is_active, must_change_password, credential_version "
                "FROM users ORDER BY username"
            ).fetchall()
    except sqlite3.Error as exc:
        raise EvidenceError(f"Cannot inspect isolated production fixture: {type(exc).__name__}") from exc
    expected_user = (PRODUCTION_BOOTSTRAP_USER_ID, "admin", "admin", 1, 0 if after_ui else 1,
                     2 if after_ui else 1)
    if schema != [("0001",)] or owner != [("production", "production-init")] or users != [expected_user]:
        raise EvidenceError("Isolated production fixture ownership or admin state differs from the case contract")
    return expected_bootstrap_state(after_ui=after_ui)


def prepare_production_bootstrap(case_private: Path, case_output: Path, bootstrap_data) -> tuple[Path, Path]:
    """Initialize a fresh production layout strictly beneath this runner's temp root."""
    bootstrap_root = case_private / "production-bootstrap"
    bootstrap_root.mkdir(mode=0o700)
    database = bootstrap_root / "database/production/production.db"
    seed = database.with_name("seed.sql")
    try:
        generated = bootstrap_data.initialize_production(bootstrap_root)
    except Exception as exc:
        raise EvidenceError(f"Isolated production bootstrap failed: {type(exc).__name__}") from exc
    if (not isinstance(generated, dict) or generated.get("database") != str(database)
            or generated.get("environment") != "production" or generated.get("accounts") != 1
            or generated.get("schema_version") != "0001" or seed.is_symlink() or not seed.is_file()):
        raise EvidenceError("Production initializer returned an unexpected isolated layout")
    initial = inspect_production_bootstrap(database, after_ui=False)
    manifest = {"fixture_kind": "production_bootstrap", "database": "database/production/production.db",
                "database_sha256": sha256(database), "seed_sql_sha256": sha256(seed), "initial_state": initial}
    public_manifest = case_output / "fixture-manifest.json"
    public_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    return database, public_manifest


def assert_production_reinitialization_refused(case_private: Path, bootstrap_data) -> None:
    try:
        bootstrap_data.initialize_production(case_private / "production-bootstrap")
    except ValueError:
        return
    except Exception as exc:
        raise EvidenceError(f"Production reinitialization failed unexpectedly: {type(exc).__name__}") from exc
    raise EvidenceError("Production initializer overwrote an existing database")


def wait_for_service(process: subprocess.Popen, address: str) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise Blocked("Isolated account service exited before readiness")
        try:
            with urlopen(address + "/v1/health", timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.2)
    raise Blocked("Isolated account service readiness timed out")


def unused_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def test_configuration(derived: Path, values: dict[str, str]) -> Path:
    files = sorted((derived / "Build/Products").glob("*.xctestrun"))
    files = [path for path in files if path.name != "TokenMeter-isolated.xctestrun"]
    if len(files) != 1:
        raise Blocked("Expected one built native xctestrun configuration")
    document = plistlib.loads(files[0].read_bytes())
    targets = []
    if "TestConfigurations" in document:
        for configuration in document["TestConfigurations"]:
            targets.extend(configuration.get("TestTargets", []))
    else:
        targets = [value for key, value in document.items() if not key.startswith("__") and isinstance(value, dict)]
    matched = 0
    for target in targets:
        if target.get("BlueprintName") == "TokenMeterUITests" or "TokenMeterUITests" in str(target.get("TestBundlePath", "")):
            target.setdefault("EnvironmentVariables", {}).update(values)
            matched += 1
    if matched != 1:
        raise Blocked("Built xctestrun does not identify exactly one real UI test target")
    output = derived / "Build/Products/TokenMeter-isolated.xctestrun"
    output.write_bytes(plistlib.dumps(document))
    return output


def build_command(project: Path, derived: Path) -> list[str]:
    return ["xcodebuild", "-project", str(project), "-scheme", "TokenMeter", "-configuration", "UITesting",
            "-derivedDataPath", str(derived), "-destination", "platform=macOS,arch=" + architecture_family(platform.machine()),
            "-parallel-testing-enabled", "NO"]


def progress(case_id: str, stage: str) -> None:
    # These values are repository-owned case IDs and fixed stage names. Never
    # print environment dictionaries, subprocess arguments or fixture contents.
    print(json.dumps({"event": "e2e_progress", "case_id": case_id, "stage": stage}), flush=True)


def record_cleanup_errors(report: dict, errors: list[str], primary_error: BaseException | None) -> None:
    if errors:
        report.setdefault("cleanup_errors", []).extend(errors)
        # Preserve the pending exception, including its safe operation name.
        # The entry point reports cleanup errors separately and still fails.
        if primary_error is None:
            raise EvidenceError("; ".join(errors))


def execute(root: Path, output: Path, report: dict) -> None:
    """Populate a report from actual commands; the caller writes it even on failure."""
    report["platform"] = preflight(root)
    report["runner_implemented"] = True
    report["source_commit"] = git(root, "rev-parse", "HEAD")
    report["working_tree_dirty"] = bool(git(root, "status", "--porcelain"))
    if report["working_tree_dirty"]:
        raise Blocked("Native candidate must be committed and clean before execution")
    expected = required_cases(root)
    for case_id in expected:
        fixture_profile(case_id)
    report["expected_cases"] = list(expected)
    report["manifest_sha256"] = snapshot(root)
    report["fixture_program_sha256"] = {
        name: sha256(root / name) for name in ("tests/server/fixtures.py", "tests/e2e/update_source.py",
                                              "tests/e2e/code_signing.py", "apps/macos/build_update_fixture.py",
                                              "scripts/bootstrap_sqlite.py")
    }
    account_data = load_module(root / "tests/server/fixtures.py", "native_account_fixture")
    bootstrap_data = load_module(root / "scripts/bootstrap_sqlite.py", "native_production_bootstrap")
    update_data = load_module(root / "tests/e2e/update_source.py", "native_update_fixture")
    signing_data = load_module(root / "tests/e2e/code_signing.py", "native_signing_fixture")
    project = root / "apps/macos/TokenMeter.xcodeproj"
    failed: list[str] = []
    # TemporaryDirectory is owned by this process and is never uploaded. It holds
    # account passwords/database contents, test private keys and build workspaces.
    with tempfile.TemporaryDirectory(prefix="tokenmeter-native-") as temporary:
        private = Path(temporary).resolve()
        derived = private / "derived"
        for index, (case_id, identifier) in enumerate(expected.items(), 1):
            progress(case_id, "prepare-fixtures")
            case_output = output / case_id
            case_output.mkdir()
            case_private = private / case_id
            case_private.mkdir(mode=0o700)
            isolation_id = (report["run_id"][:40] + f"-c{index:03d}").lower()
            profile = fixture_profile(case_id)
            if profile == "production_bootstrap":
                database, public_manifest = prepare_production_bootstrap(case_private, case_output, bootstrap_data)
            else:
                fixture = account_data.generate(isolation_id, 42, workspace=case_private)
                fixture_manifest = json_file(fixture / "manifest.json")
                public_manifest = case_output / "fixture-manifest.json"
                public_manifest.write_text(json.dumps(fixture_manifest, indent=2) + "\n")
                database = case_private / "accounts.sqlite"
                (case_private / ".tokenmeter-test-database.json").write_text(json.dumps({
                    "owner": "tokenmeter-test-database", "run_id": isolation_id, "database": database.name}) + "\n")
            database_url = "sqlite:///" + str(database)
            if profile == "synthetic_accounts":
                command([sys.executable, "-m", "server.tokenmeter_server.cli", "migrate", "--database-url", database_url],
                        root=root, log=case_output / "migrate.log", timeout=60)
                command([sys.executable, "-m", "server.tokenmeter_server.cli", "provision", "--database-url", database_url,
                         "--accounts", str(fixture / "users.json"), "--test-run-id", isolation_id],
                        root=root, log=case_output / "provision.log", timeout=60)
            port = unused_port()
            address = f"http://127.0.0.1:{port}"
            environment = dict(os.environ, TOKENMETER_DATABASE_URL=database_url)
            update = None
            signing = None
            with (case_output / "service.log").open("wb") as service_log:
                process = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.tokenmeter_server.main:app",
                                            "--host", "127.0.0.1", "--port", str(port), "--no-proxy-headers"], cwd=root, env=environment,
                                           stdout=service_log, stderr=subprocess.STDOUT)
                try:
                    progress(case_id, "start-service")
                    wait_for_service(process, address)
                    update_env: dict[str, str] = {}
                    build_settings = ["CURRENT_PROJECT_VERSION=100", "CODE_SIGN_IDENTITY=-", "CODE_SIGNING_ALLOWED=YES",
                                      "TM_TEST_API_URL=" + address, "TM_TEST_RUN_ID=" + isolation_id]
                    if case_id == "E2E-TM001-004":
                        progress(case_id, "verify-upgrade-environment")
                        require_upgrade_environment(root, case_output)
                        progress(case_id, "prepare-signing")
                        signing = signing_data.SigningIdentity(case_private / "code-signing")
                        identity = signing.prepare()
                        build_settings = [setting for setting in build_settings if not setting.startswith("CODE_SIGN_IDENTITY=")]
                        build_settings += ["CODE_SIGN_IDENTITY=" + identity,
                                           "OTHER_CODE_SIGN_FLAGS=--keychain " + shlex.quote(str(signing.keychain))]
                        update = update_data.UpdateSource(case_private / "update-secrets", case_output)
                        progress(case_id, "prepare-https-update")
                        public_key = update.prepare()
                        update.start_tunnel()
                        feed = update.url + "/appcast.xml"
                        build_settings += ["TM_UPDATE_FEED_URL=" + feed, "TM_UPDATE_PUBLIC_KEY=" + public_key]
                        package_output = case_private / "update-package"
                        progress(case_id, "build-update-package")
                        try:
                            command([sys.executable, str(root / "apps/macos/build_update_fixture.py"),
                                     "--derived-data", str(case_private / "derived-update"), "--output", str(package_output),
                                     "--feed-url", feed, "--public-key", public_key,
                                     "--private-key-file", str(update.private / "sparkle-seed.txt"),
                                     "--code-sign-identity", identity, "--signing-keychain", str(signing.keychain),
                                     "--api-url", address, "--run-id", isolation_id, "--build-version", "101"],
                                    root=root, log=case_output / "update-build.log")
                        finally:
                            if (package_output / "build.log").is_file():
                                (case_output / "update-package-build.log").write_bytes((package_output / "build.log").read_bytes())
                        update_metadata = json_file(package_output / "signature.json")
                        signature = update_metadata["signature"]
                        (case_output / "update-signature.json").write_text(json.dumps(update_metadata, indent=2) + "\n")
                        update.publish(package_output / "update.zip", signature)
                        report["development_signing"] = {"kind": "ephemeral-self-signed-isolated-keychain",
                                                         "certificate_sha1": identity, "developer_id": False,
                                                         "notarized": False, "system_trust_modified": False}
                        update_env = {"TM_TEST_UPDATE_CONTROL_URL": update.url + "/control/valid",
                                      "TM_TEST_UPDATE_CONTROL_TOKEN": update.token,
                                      "TM_TEST_UPDATE_VALID_FEED": update.url + "/valid.xml",
                                      "TM_TEST_UPDATE_INVALID_FEED": update.url + "/invalid.xml",
                                      "TM_TEST_EXPECTED_BUILD": "101"}
                    base = build_command(project, derived)
                    progress(case_id, "build-native-tests")
                    command(base + ["build-for-testing"] + build_settings, root=root, log=case_output / "build.log")
                    app = derived / "Build/Products/UITesting/TokenMeter.app"
                    if not app.is_dir():
                        raise Blocked("Native build did not produce TokenMeter.app")
                    if signing is not None:
                        displayed = subprocess.run(["codesign", "-d", "-r-", str(app)], capture_output=True, text=True, check=False)
                        requirements = [line for line in (displayed.stdout + displayed.stderr).splitlines() if line.startswith("designated =>")]
                        if (displayed.returncode or len(requirements) != 1 or "cdhash" in requirements[0]
                                or requirements[0] != update_metadata.get("designated_requirement")
                                or update_metadata.get("code_sign_identity") != identity):
                            raise EvidenceError("Candidate and update do not share the same stable signing requirement")
                        (case_output / "candidate-signing.json").write_text(json.dumps({
                            "code_sign_identity": identity, "designated_requirement": requirements[0],
                            "matches_update": True, "developer_id": False, "notarized": False}, indent=2) + "\n")
                    archived_app = case_output / "candidate-app.zip"
                    command(["ditto", "-c", "-k", "--keepParent", str(app), str(archived_app)],
                            root=root, log=case_output / "archive.log", timeout=120)
                    test_env = dict(os.environ, TM_TEST_API_URL=address, TM_TEST_RUN_ID=isolation_id, **update_env)
                    # xcodebuild forwards explicitly prefixed environment variables
                    # to the test process. The App only receives the safe subset
                    # selected by the XCTest launchEnvironment implementation.
                    for key, value in list(test_env.items()):
                        if key.startswith("TM_TEST_"):
                            test_env["TEST_RUNNER_" + key] = value
                    config = test_configuration(derived, {key: value for key, value in test_env.items() if key.startswith("TM_TEST_")})
                    bundle = case_output / "native.xcresult"
                    args = ["xcodebuild", "test-without-building", "-xctestrun", str(config),
                            "-destination", "platform=macOS,arch=" + architecture_family(report["platform"]["architecture"]),
                            "-parallel-testing-enabled", "NO", "-only-testing:" + identifier,
                            "-resultBundlePath", str(bundle), "-resultBundleVersion", "3"]
                    progress(case_id, "execute-native-test")
                    result = command(args, root=root, log=case_output / "xcodebuild.log", env=test_env,
                                     timeout=600, required=False)
                    suite = {"case_id": case_id, "native_test": identifier, "exit_code": result.returncode,
                             "xcresult": bundle.relative_to(output).as_posix(),
                             "fixture_manifest": public_manifest.relative_to(output).as_posix(),
                             "fixture_sha256": sha256(public_manifest),
                             "app_artifact": archived_app.relative_to(output).as_posix(),
                             "app_sha256": sha256(archived_app), "state": "FAIL"}
                    report["suites"].append(suite)
                    if bundle.is_dir():
                        progress(case_id, "parse-native-results")
                        suite["xcresult_sha256"] = tree_digest(bundle)
                        tree, summary = parse_bundle(root, bundle)
                        (case_output / "native-tests.json").write_text(json.dumps(tree, indent=2) + "\n")
                        (case_output / "native-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
                        suite["native_failures"] = [failure["failureText"][:1000]
                            for failure in summary.get("testFailures", [])[:3]
                            if isinstance(failure, dict) and isinstance(failure.get("failureText"), str)]
                        if summary.get("totalTestCount", 0) > summary.get("skippedTests", 0):
                            report["executed_cases"] += 1
                        try:
                            suite["destination"] = native_destination(summary, report["platform"]["architecture"], report["platform"]["macos"])
                            try:
                                check_native_result(tree, summary, identifier)
                                if result.returncode:
                                    raise EvidenceError(f"xcodebuild exited {result.returncode} despite passing case")
                            finally:
                                primary_error = sys.exc_info()[1]
                                progress(case_id, "export-native-attachments")
                                try:
                                    suite["screenshots"] = export_attachments(root, bundle, case_output)
                                except (EvidenceError, Blocked, OSError, subprocess.SubprocessError) as exc:
                                    suite["attachment_error"] = str(exc)
                                    if primary_error is None:
                                        raise
                            if update is not None:
                                try:
                                    update.verify_exchange()
                                except RuntimeError as exc:
                                    raise EvidenceError(str(exc)) from exc
                            if profile == "production_bootstrap":
                                assert_production_reinitialization_refused(case_private, bootstrap_data)
                                state = inspect_production_bootstrap(database, after_ui=True)
                                state_file = case_output / "database-state.json"
                                state_file.write_text(json.dumps({"post_ui_state": state,
                                                                  "reinitialization_refused": True}, indent=2) + "\n")
                                suite["bootstrap_state_artifact"] = state_file.relative_to(output).as_posix()
                                suite["bootstrap_state_sha256"] = sha256(state_file)
                            suite["state"] = "PASS"
                            report["passed_cases"] += 1
                        except EvidenceError as exc:
                            suite["error"] = str(exc)
                            failed.append(f"{case_id}: {exc}")
                    else:
                        raise Blocked(f"No native result bundle for {case_id}; xcodebuild exit {result.returncode}")
                finally:
                    primary_error = sys.exc_info()[1]
                    progress(case_id, "cleanup")
                    cleanup_errors = []
                    try:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=10)
                    except (OSError, subprocess.SubprocessError) as exc:
                        cleanup_errors.append(f"service cleanup: {exc}")
                    if update is not None:
                        try:
                            update.close()
                        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                            cleanup_errors.append(f"update source cleanup: {exc}")
                    if signing is not None:
                        try:
                            signing.close()
                        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                            cleanup_errors.append(f"code-signing cleanup: {exc}")
                    service = "org.tokenmeter.session." + isolation_id + "." + hashlib.sha256(address.rstrip("/").encode()).hexdigest()
                    try:
                        keychain = subprocess.run(["security", "delete-generic-password", "-s", service,
                                                   "-a", "access-token"], capture_output=True, text=True, check=False, timeout=15)
                        if keychain.returncode not in (0, 44):
                            cleanup_errors.append(f"Scoped test Keychain cleanup failed: {keychain.returncode}")
                    except (OSError, subprocess.SubprocessError) as exc:
                        cleanup_errors.append(f"test Keychain cleanup: {exc}")
                    if profile == "synthetic_accounts":
                        try:
                            account_data.reset(isolation_id, workspace=case_private)
                        except (OSError, ValueError) as exc:
                            cleanup_errors.append(f"account fixture cleanup: {exc}")
                    record_cleanup_errors(report, cleanup_errors, primary_error)
            # XCTest logs out/removes only its own run's session; database and
            # credentials are removed with the owned temporary directory.
        report["cleanup_completed"] = True
    if failed:
        raise EvidenceError("; ".join(failed))
    if report["passed_cases"] != len(expected):
        raise EvidenceError("Required native case set did not pass in full")
    if git(root, "status", "--porcelain") or snapshot(root) != report["manifest_sha256"]:
        raise EvidenceError("Candidate changed while tests were executing")
    report["state"] = "PASS"
