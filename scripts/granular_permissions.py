#!/usr/bin/env python3
"""Fixed TM-002 installed-App product E2E runner.

Only a verified final or marked development DMG and independently owned
synthetic inputs are used. Development results never grant release eligibility.
Missing native picker or Keychain proof yields raw BLOCKED records before an
App is launched. This runner never changes product state to manufacture PASS.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import grp
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import secrets
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shutil
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import threading
import uuid
from urllib.parse import urlsplit

import local_e2e as base
from granular_service_fixture import ServiceFixture
import tm002_fixture as sources
import verify_tm002_evidence as evidence_audit


ROOT = Path(__file__).resolve().parents[1]
RELEASE = "v0.2.0-20261001T034118Z"
SPEC = "granular-permissions.spec.ts"
NO_KEYCHAIN_ITEM_EXPECTED = {
    "TC-TM002-SELECT-01", "TC-TM002-SELECT-02#FIRST_CANCEL",
    "TC-TM002-PREVIEW-01", "TC-TM002-CONSENT-01",
    "TC-TM002-PREVIEW-04#CANDIDATES_1001",
    "TC-TM002-PREVIEW-04#ENTRIES_5001", "TC-TM002-PREVIEW-04#DEPTH_9"
}


class IdentityBarrier:
    """Hold an actual upstream /v1/me reply after FastAPI has produced it."""
    def __init__(self, upstream: str):
        target = urlsplit(upstream)
        if target.scheme != "http" or target.hostname != "127.0.0.1" or not target.port:
            raise ValueError("Identity barrier requires this run's loopback proxy")
        self.token = secrets.token_urlsafe(32)
        self.armed = threading.Event()
        self.captured = threading.Event()
        self.released = threading.Event()
        self.stopping = threading.Event()
        self.observation: dict = {}
        barrier = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args): return

            def reply_json(self, status: int, value: dict):
                body = json.dumps(value, sort_keys=True).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def control(self) -> bool:
                if not self.path.startswith("/__tm002_barrier/"):
                    return False
                if self.headers.get("Authorization") != "Bearer " + barrier.token:
                    self.reply_json(403, {"error": "forbidden"})
                    return True
                if self.path == "/__tm002_barrier/status" and self.command == "GET":
                    self.reply_json(200, {"armed": barrier.armed.is_set(),
                                          "captured": barrier.captured.is_set(),
                                          "released": barrier.released.is_set(),
                                          "observation": barrier.observation})
                elif self.path == "/__tm002_barrier/arm" and self.command == "POST":
                    barrier.captured.clear(); barrier.released.clear(); barrier.observation = {}
                    barrier.armed.set()
                    self.reply_json(200, {"armed": True})
                elif self.path == "/__tm002_barrier/release" and self.command == "POST":
                    if not barrier.captured.is_set():
                        self.reply_json(409, {"error": "real_response_not_captured"})
                    else:
                        barrier.released.set()
                        self.reply_json(200, {"released": True, "observation": barrier.observation})
                else:
                    self.reply_json(404, {"error": "unknown_control"})
                return True

            def do_GET(self): self.forward()
            def do_POST(self): self.forward()
            def do_PUT(self): self.forward()
            def do_PATCH(self): self.forward()
            def do_DELETE(self): self.forward()

            def forward(self):
                if self.control(): return
                size = int(self.headers.get("Content-Length", "0"))
                if size < 0 or size > 1_048_576:
                    self.send_error(413); return
                body = self.rfile.read(size) if size else None
                headers = {name: value for name, value in self.headers.items()
                           if name.lower() not in ("host", "connection", "content-length")}
                connection = http.client.HTTPConnection(target.hostname, target.port, timeout=30)
                try:
                    connection.request(self.command, self.path, body=body, headers=headers)
                    actual = connection.getresponse()
                    response_body = actual.read()
                    hold = self.command == "GET" and self.path == "/v1/me" and barrier.armed.is_set()
                    if hold:
                        parsed = json.loads(response_body) if actual.status == 200 else {}
                        barrier.observation = {"status": actual.status,
                                               "body_sha256": hashlib.sha256(response_body).hexdigest(),
                                               "account_id": parsed.get("id"),
                                               "captured_at": now()}
                        barrier.captured.set()
                        if not barrier.released.wait(timeout=45) or barrier.stopping.is_set():
                            return
                        barrier.armed.clear()
                    self.send_response(actual.status)
                    for name, value in actual.getheaders():
                        if name.lower() not in ("connection", "transfer-encoding", "content-length"):
                            self.send_header(name, value)
                    self.send_header("Content-Length", str(len(response_body)))
                    self.end_headers()
                    self.wfile.write(response_body)
                except (OSError, http.client.HTTPException, ValueError):
                    try: self.send_error(502)
                    except OSError: pass
                finally:
                    connection.close()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> bool:
        self.stopping.set(); self.released.set()
        self.server.shutdown(); self.server.server_close()
        self.thread.join(timeout=5)
        return not self.thread.is_alive()


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_case_name(case_id: str) -> str:
    if not sources.CASE_ID.fullmatch(case_id):
        raise base.Failed("Invalid TM-002 case ID")
    return case_id.replace("#", "--")


def read_catalog() -> tuple[list[dict], dict[str, list[str]]]:
    payload = json.loads((ROOT / "tests/test_cases.json").read_text(encoding="utf-8"))
    if payload.get("release_id") != RELEASE:
        raise base.Blocked("TM-002 catalog is not the selected release baseline")
    parents = [case for case in payload["cases"] if case.get("feature_id") == "TM-002"
               and case.get("type") == "product_e2e"]
    if len(parents) != 20 or len({case["id"] for case in parents}) != 20:
        raise base.Failed("TM-002 product parent catalog differs from the baselined 20")
    expanded: list[dict] = []
    variants_by_parent: dict[str, list[str]] = {}
    for parent in parents:
        if parent.get("design_status") != "baselined" or parent.get("release_id") != RELEASE:
            raise base.Blocked("Product TC is not baselined for TM-002")
        expanded.append(parent)
        children = parent.get("variants") or []
        if children:
            variants_by_parent[parent["id"]] = []
        for child in children:
            identity = child.get("id")
            if (not isinstance(identity, str) or not identity.startswith(parent["id"] + "#")
                    or not child.get("steps") or child.get("execution_status") != "unexecuted"):
                raise base.Failed("Invalid fixed TM-002 variant identity or steps")
            variants_by_parent[parent["id"]].append(identity)
            expanded.append({**parent, "id": identity, "parent_id": parent["id"],
                             "steps": child["steps"], "input": child["input"],
                             "overall_expected": child["expected"], "variants": []})
    all_ids = [case["id"] for case in expanded]
    if len(all_ids) != 33 or len(set(all_ids)) != 33 or sum(map(len, variants_by_parent.values())) != 13:
        raise base.Failed("TM-002 product variants differ from the baselined 13")
    return expanded, variants_by_parent


def select_cases(cases: list[dict], case_ids: list[str]) -> list[dict]:
    if not case_ids:
        return cases
    requested = set(case_ids)
    known = {case["id"] for case in cases}
    if len(requested) != len(case_ids) or not requested <= known:
        raise base.Failed("Unknown or duplicate TM-002 case ID")
    return [case for case in cases if case["id"] in requested or case.get("parent_id") in requested]


def blocked(case: dict, reason: str) -> dict:
    return {"case_id": case["id"], "parent_id": case.get("parent_id"), "state": "BLOCKED",
            "reason": reason, "task_ids": case.get("task_ids", []), "ac_ids": case.get("ac_ids", []),
            "step_results": [], "started_at": None, "finished_at": None, "evidence": {},
            "cleanup": {"completed": False}}


def require_new_directory(path: Path) -> Path:
    target = path.absolute()
    if target.exists() or target.is_symlink() or any(item.is_symlink() for item in target.parents):
        raise base.Blocked("Evidence output must be new and have no linked parent")
    target.mkdir(parents=True, mode=0o700)
    os.chmod(target, 0o700)
    return target


def require_private_base(path: Path) -> Path:
    if path.is_symlink() or any(parent.is_symlink() for parent in path.absolute().parents):
        raise base.Blocked("Private work base is linked")
    target = path.resolve(strict=False)
    if any(parent.is_symlink() for parent in target.parents):
        raise base.Blocked("Private work base has a linked parent")
    if not target.exists():
        if not target.parent.is_dir() or target.parent.stat().st_uid != os.getuid():
            raise base.Blocked("Private work base parent is not owned by this account")
        target.mkdir(mode=0o700)
    details = target.stat(follow_symlinks=False)
    if not target.is_dir() or details.st_uid != os.getuid() or details.st_mode & 0o777 != 0o700:
        raise base.Blocked("Private work base is not an owned 0700 directory")
    return target


def verify_package(manifest: Path, dmg: Path, candidate_sha: str, *, development: bool = False) -> dict:
    if platform.system() != "Darwin" or platform.machine() != "x86_64" or not platform.mac_ver()[0].startswith("15."):
        raise base.Blocked("TM-002 final product profile requires macOS 15 Intel")
    for command in ("hdiutil", "ditto", "codesign", "plutil", "swift"):
        if shutil.which(command) is None:
            raise base.Blocked("Missing local product tool: " + command)
    if not re.fullmatch(r"[a-f0-9]{40}", candidate_sha):
        raise base.Failed("Candidate SHA is malformed")
    package = json.loads(manifest.read_text(encoding="utf-8"))
    scope = "development" if development else "final_package"
    if (package.get("schema_version") != 2 or package.get("scope") != scope
            or package.get("release_id") != RELEASE or package.get("candidate_sha") != candidate_sha
            or not isinstance(package.get("working_tree_dirty"), bool)
            or (not development and package["working_tree_dirty"] is not False)):
        raise base.Failed("Input does not match the selected TM-002 package scope")
    original_dmg = base.checked_file(manifest.parent, package["artifacts"]["dmg"])
    if dmg.is_symlink() or not dmg.is_file() or any(parent.is_symlink() for parent in dmg.parents):
        raise base.Failed("DMG path is missing or linked")
    if development:
        marker = re.fullmatch(
            rf"TokenMeter-{re.escape(RELEASE)}(?:-[a-f0-9]{{12}}-[a-f0-9]{{12}})?-DEVELOPMENT-NOT-RELEASED\.dmg",
            dmg.name)
        if (not marker or base.digest(dmg) != package["artifacts"]["dmg"]["sha256"]
                or dmg.stat().st_size != package["artifacts"]["dmg"]["bytes"]):
            raise base.Failed("Development DMG lacks its NOT-RELEASED marker or differs from the package")
    elif original_dmg.resolve() != dmg.resolve():
        raise base.Failed("Final DMG does not match the final manifest")
    base.checked_file(manifest.parent, package["artifacts"]["update_zip"])
    if package.get("app", {}).get("version") != "0.2.0" or str(package["app"].get("build")) != "200":
        raise base.Failed("Installed App is not TM-002 version 0.2.0/build 200")
    tree = subprocess.run(["git", "rev-parse", f"{candidate_sha}^{{tree}}"], cwd=ROOT,
                          capture_output=True, text=True, timeout=10, check=False)
    if tree.returncode or tree.stdout.strip() != package.get("candidate_tree"):
        raise base.Failed("Candidate commit tree differs from package manifest")
    return package


def ax_preflight() -> dict:
    driver = ROOT / "apps/desktop/e2e/native_picker_driver.swift"
    if not driver.is_file():
        raise base.Blocked("Fixed real NSOpenPanel AX driver is missing")
    result = subprocess.run(["swift", str(driver), "probe"], cwd=ROOT, capture_output=True,
                            text=True, timeout=60, check=False)
    if result.returncode:
        raise base.Blocked("Fixed native AX probe failed")
    value = json.loads(result.stdout)
    if value != {"operation": "probe", "platform": "macos_ax", "prompted": False, "trusted": True}:
        raise base.Blocked("Accessibility is not trusted for the real native chooser")
    return value


def verify_test_account(args) -> None:
    """Bind the excluded owner and this process to two distinct local accounts."""
    if not args.keychain_test_user or not args.keychain_excluded_user or args.keychain_excluded_uid is None:
        raise base.Blocked("Explicit independent test and excluded owner accounts are required")
    for name in (args.keychain_test_user, args.keychain_excluded_user):
        if not re.fullmatch(r"[a-z_][a-z0-9_-]{2,63}", name):
            raise base.Failed("Keychain account name is malformed")
    try:
        account = pwd.getpwnam(args.keychain_test_user)
        excluded = pwd.getpwnam(args.keychain_excluded_user)
        admin = grp.getgrnam("admin")
    except KeyError:
        raise base.Blocked("An explicitly named local account or admin group is absent") from None
    if excluded.pw_uid <= 0 or excluded.pw_uid != args.keychain_excluded_uid:
        raise base.Blocked("Excluded UID does not match the named primary account")
    if (os.getuid() == 0 or os.getuid() == excluded.pw_uid or account.pw_uid != os.getuid()
            or account.pw_uid == excluded.pw_uid or os.getgid() == admin.gr_gid
            or admin.gr_gid in os.getgroups() or account.pw_name in admin.gr_mem):
        raise base.Blocked("Runner is not executing in a separate standard test account")


def keychain_probe_stage(mode: str, *, args, installed: Path, profile: Path,
                         private: Path, case_out: Path, owner_id: str,
                         expect_created: bool, dmg_digest: str) -> dict:
    """Bind Security.framework metadata proof to this owned profile and DMG."""
    if mode not in ("preflight", "postflight", "cleanup"):
        raise base.Failed("Unknown fixed Keychain proof stage")
    probe = ROOT / "scripts/tm002_keychain_probe.swift"
    if not probe.is_file() or probe.is_symlink():
        raise base.Blocked("Fixed native Keychain probe is missing")
    output = case_out / f"keychain-{mode}.json"
    log_path = case_out / f"keychain-{mode}.log"
    command = ["swift", str(probe), "--mode", mode, "--profile", str(profile),
               "--state", str(private / "keychain-owner.json"), "--output", str(output),
               "--app", str(installed), "--dmg", str(args.dmg), "--run-id", owner_id,
               "--test-user", args.keychain_test_user,
               "--excluded-uid", str(args.keychain_excluded_uid),
               "--expect-created", str(expect_created).lower()]
    with log_path.open("x", encoding="utf-8") as stream:
        os.chmod(log_path, 0o600)
        try:
            process = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                     timeout=120, check=False)
        except (OSError, subprocess.SubprocessError):
            raise base.Blocked("Native Keychain metadata probe could not run") from None
    if output.is_symlink() or not output.is_file():
        raise base.Blocked("Native Keychain probe produced no private structured evidence")
    try: value = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, ValueError): raise base.Blocked("Native Keychain proof is malformed") from None
    app_name = "TokenMeter-Test-" + hashlib.sha256(str(profile).encode()).hexdigest()[:24]
    expected = {"service_digest": hashlib.sha256((app_name + " Safe Storage").encode()).hexdigest(),
                "account_digest": hashlib.sha256(app_name.encode()).hexdigest(),
                "dmg_digest": dmg_digest}
    if (value.get("schema_version") != 1 or value.get("mode") != mode
            or value.get("uid") != os.getuid() or value.get("expected_item_created") is not expect_created
            or any(value.get(key) != digest for key, digest in expected.items())
            or not re.fullmatch(r"[a-f0-9]{64}", str(value.get("app_signature_digest", "")))
            or value.get("first_call_absent") is not True):
        raise base.Blocked("Native Keychain proof identity or first-call absence differs")
    if process.returncode != 0 or value.get("state") != "PASS":
        reason = value.get("reason")
        raise base.Blocked("Native Keychain proof blocked: " +
                           (reason if isinstance(reason, str) and re.fullmatch(r"[a-z_]{2,60}", reason)
                            else "unknown_reason"))
    if mode == "preflight":
        valid = value.get("item_created") is False and value.get("item_ref_digest") is None
    elif mode == "postflight":
        valid = (value.get("item_created") is expect_created and
                 value.get("acl_bound_to_app") is expect_created and
                 value.get("exact_cleanup_ready") is expect_created and
                 (bool(re.fullmatch(r"[a-f0-9]{64}", str(value.get("item_ref_digest", ""))))
                  is expect_created))
    else:
        valid = (value.get("item_created") is expect_created and
                 value.get("acl_bound_to_app") is expect_created)
    if not valid:
        raise base.Blocked("Native Keychain proof stage fields differ")
    return value


def copy_installed_app(source: Path, destination: Path, package: dict, tree_tool, log: Path) -> Path:
    destination.parent.mkdir(mode=0o700, exist_ok=True)
    base.command(["ditto", str(source), str(destination)], timeout=180, log=log)
    if tree_tool.tree_sha256(destination) != package["app"]["tree_sha256"]:
        raise base.Failed("Installed App tree differs from signed DMG")
    requirement = package["app"].get("designated_requirement")
    if not isinstance(requirement, str) or not requirement:
        raise base.Failed("Final App has no designated signing requirement")
    base.command(["codesign", "--verify", "--deep", "--strict", "-R", "=" + requirement,
                  str(destination)], log=log)
    plist = destination / "Contents/Info.plist"
    actual_build = base.command(["plutil", "-extract", "CFBundleVersion", "raw", str(plist)]).stdout.strip()
    if actual_build != str(package["app"].get("build")):
        raise base.Failed("Installed App build differs from manifest")
    return destination


def playwright(case_id: str, context: Path, output: Path, run_id: str, candidate_sha: str) -> tuple[int, Path]:
    raw = output / "playwright.json"
    binary = ROOT / "apps/desktop/node_modules/.bin/playwright"
    if not binary.is_file():
        raise base.Blocked("Pinned Playwright executable is absent")
    env = dict(os.environ, TM_E2E_CONTEXT=str(context), TM_E2E_JSON=str(raw),
               TM_E2E_CASE_OUTPUT=str(output), TM_E2E_RUN_ID=run_id,
               TM_E2E_CANDIDATE_SHA=candidate_sha, TM_E2E_SPEC=SPEC)
    with (output / "playwright.log").open("x", encoding="utf-8") as log:
        os.chmod(output / "playwright.log", 0o600)
        try:
            process = subprocess.run([str(binary), "test", f"e2e/{SPEC}", "--config", "e2e/playwright.config.ts",
                                      "--grep", r"(?:^|\s)" + re.escape(case_id) + "$"],
                                     cwd=ROOT / "apps/desktop", env=env, stdout=log, stderr=subprocess.STDOUT,
                                     timeout=600, check=False)
            return process.returncode, raw
        except subprocess.TimeoutExpired:
            return 124, raw


def result_status(raw: Path, case_id: str) -> tuple[str, str]:
    if raw.is_symlink() or not raw.is_file():
        return "BLOCKED", "Playwright produced no original JSON"
    try:
        value = json.loads(raw.read_text(encoding="utf-8"))
        specs = [spec for suite in value.get("suites", []) for spec in suite.get("specs", [])]
        tests = [test for spec in specs for test in spec.get("tests", [])]
        attempts = [result for test in tests for result in test.get("results", [])]
    except (OSError, ValueError, TypeError):
        return "FAIL", "Playwright original JSON is malformed"
    if len(specs) != 1 or len(tests) != 1 or len(attempts) != 1 or specs[0].get("title") != case_id:
        return "BLOCKED", "Expected exactly one fixed TC and one attempt"
    status = attempts[0].get("status")
    if status == "passed":
        return "PASS", ""
    if status in ("failed", "timedOut"):
        return "FAIL", "Playwright assertion failed; inspect the owned original JSON"
    return "BLOCKED", "Playwright status is not a completed assertion"


def step_evidence(case: dict, events: Path, run_id: str) -> tuple[list[dict], str | None]:
    if events.is_symlink() or not events.is_file():
        return [], "Fixed step event log is missing"
    try:
        observed = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
    except (OSError, ValueError, TypeError):
        return [], "Fixed step event log is malformed"
    expected_numbers = [step["step"] for step in case["steps"]]
    if [item.get("step") for item in observed] != expected_numbers:
        return observed, "Recorded steps differ from the baselined TC"
    for item in observed:
        if (item.get("run_id") != run_id or item.get("case_id") != case["id"]
                or item.get("passed") is not True or not all(key in item for key in
                ("action", "expected", "actual", "source", "timestamp", "evidence"))):
            return observed, "Step identity, comparison or evidence is incomplete"
        serialized = json.dumps(item, ensure_ascii=False)
        if "TEST-ONLY-" in serialized or "PRIVATE_" in serialized or re.search(r"\"(?:access_token|password_hash)\"", serialized):
            return observed, "Step evidence contains private fixture bytes or credentials"
    return observed, None


def one_case(case: dict, args, package: dict, mounted: Path, private_root: Path,
             output: Path, tree_tool, bootstrap, fixtures) -> dict:
    case_id = case["id"]
    item = blocked(case, "Execution not started")
    item["started_at"] = now()
    case_out = output / safe_case_name(case_id)
    case_out.mkdir(mode=0o700)
    private = private_root / safe_case_name(case_id)
    private.mkdir(mode=0o700)
    owner_id = "owner-" + uuid.uuid4().hex
    source_fixture = None
    services = []
    proxies = []
    barriers = []
    installed = None
    database: Path | None = None
    keychain_started = False
    keychain_expected = case_id not in NO_KEYCHAIN_ITEM_EXPECTED
    item["keychain_expected_item_created"] = keychain_expected
    keychain_signature: str | None = None
    profile: Path | None = None
    try:
        source_fixture = sources.prepare(case_id, private / "source-fixture", owner_id)
        audit_nonce = secrets.token_bytes(32)
        source_expected = case_out / "source-expected.json"
        base.write_json(source_expected, sources.redacted_expected(source_fixture, audit_nonce))
        item["evidence"]["source_expected"] = base.descriptor(source_expected, output)
        if case_id.startswith("TC-TM002-PREVIEW-04#"):
            preprobe = sources.volume_preprobe(source_fixture)
            base.write_json(case_out / "volume-preprobe.json", preprobe)
            item["evidence"]["volume_preprobe"] = base.descriptor(case_out / "volume-preprobe.json", output)
            if not preprobe["under_2_seconds"]:
                raise base.Blocked("Owned volume fixture exceeded the independent 2-second preprobe")
        installed = copy_installed_app(mounted, private / "installation/TokenMeter.app", package, tree_tool,
                                       case_out / "install.log")
        profile = private / "profile"
        profile.mkdir(mode=0o700)
        db_dir = private / "database"
        database, account_fixture, seed_sql = base.make_account_database(
            db_dir, case_out, "l" + uuid.uuid4().hex[:18], 42, bootstrap, fixtures)
        oracle = sources.verify_accounts(database)
        before = base.safe_snapshot_database(database, case_id, args.run_id)
        base.write_json(case_out / "database-before.json", {"account_oracle": oracle, "snapshot": before})
        item["evidence"]["seed_sql"] = base.descriptor(seed_sql, output)
        item["evidence"]["database_before"] = base.descriptor(case_out / "database-before.json", output)
        preflight = keychain_probe_stage(
            "preflight", args=args, installed=installed, profile=profile, private=private,
            case_out=case_out, owner_id=owner_id, expect_created=keychain_expected,
            dmg_digest=package["artifacts"]["dmg"]["sha256"])
        keychain_started = True
        keychain_signature = preflight["app_signature_digest"]
        item["evidence"]["keychain_preflight"] = base.descriptor(case_out / "keychain-preflight.json", output)
        service = base.Service(database, private)
        services.append(service)
        proxy = ServiceFixture(service.url, restart=service.restart)
        proxies.append(proxy)
        identity_barrier = None
        app_service_url = proxy.url
        if case_id.startswith("TC-TM002-STATE-01#"):
            identity_barrier = IdentityBarrier(proxy.url)
            barriers.append(identity_barrier)
            app_service_url = identity_barrier.url
        second_url = None
        second_database_path = None
        if case_id == "TC-TM002-STATE-03":
            second_dir = private / "database-s2"
            second_db, _, second_sql = base.make_account_database(
                second_dir, case_out, "l" + uuid.uuid4().hex[:18], 43, bootstrap, fixtures)
            sources.verify_accounts(second_db)
            second_service = base.Service(second_db, private)
            services.append(second_service)
            second_proxy = ServiceFixture(second_service.url)
            proxies.append(second_proxy)
            second_url = second_proxy.url
            second_database_path = str(second_db)
            item["evidence"]["s2_seed_sql"] = base.descriptor(second_sql, output)
        context = private / "context.json"
        base.write_json(context, {"run_id": args.run_id, "candidate_sha": args.candidate_sha,
                                 "case_id": case_id, "app_path": str(installed), "profile_path": str(profile),
                                 "service_url": app_service_url, "service_control_url": proxy.control_url,
                                 "service_control_token": proxy.token, "database_path": str(database),
                                 "identity_control_url": identity_barrier.url + "/__tm002_barrier" if identity_barrier else None,
                                 "identity_control_token": identity_barrier.token if identity_barrier else None,
                                 "secondary_service_url": second_url, "source_a": str(source_fixture.a),
                                 "secondary_database_path": second_database_path,
                                 "source_b": str(source_fixture.b), "source_expected_path": str(source_fixture.manifest_path),
                                 "source_audit_nonce_hex": audit_nonce.hex(),
                                 "source_audit_path": str(profile / "source-access-audit.jsonl"),
                                 "picker_driver_path": str(ROOT / "apps/desktop/e2e/native_picker_driver.swift"),
                                 "python_executable": sys.executable, "source_owner_id": owner_id,
                                 "source_fixture_script": str(ROOT / "scripts/tm002_fixture.py")})
        return_code, raw = playwright(case_id, context, case_out, args.run_id, args.candidate_sha)
        state, reason = result_status(raw, case_id)
        blocked_marker = case_out / "coverage-blocked.json"
        if blocked_marker.is_file() and not blocked_marker.is_symlink():
            try:
                state, reason = "BLOCKED", json.loads(blocked_marker.read_text(encoding="utf-8"))["reason"]
            except (ValueError, KeyError, TypeError):
                state, reason = "BLOCKED", "Case declared an unreadable prerequisite block"
        if return_code and state == "PASS":
            state, reason = "FAIL", "Playwright process failed despite a passing JSON attempt"
        steps, step_error = step_evidence(case, case_out / "events.jsonl", args.run_id)
        private_audit = profile / "source-access-audit.jsonl"
        if private_audit.is_file() and not private_audit.is_symlink():
            shutil.copyfile(private_audit, case_out / "source-access-audit.jsonl")
            os.chmod(case_out / "source-access-audit.jsonl", 0o600)
        if state == "PASS" and step_error:
            state, reason = "FAIL", step_error
        traces, screenshots = base.collect_trace_and_screenshots(case_out)
        if state == "PASS" and (not traces or not screenshots):
            state, reason = "FAIL", "Native App trace or screenshot is absent"
        picker_events = sorted(case_out.glob("picker-*.json"))
        if state == "PASS" and not picker_events:
            state, reason = "BLOCKED", "No real NSOpenPanel AX event was preserved"
        if not (case_out / "source-access-audit.jsonl").is_file():
            state, reason = "BLOCKED", "No actual main/helper file access audit was preserved"
        item.update(state=state, reason=reason, step_results=steps)
        for key, path in (("playwright", raw), ("events", case_out / "events.jsonl"),
                          ("trace", traces[0] if traces else None),
                          ("source_access_audit", case_out / "source-access-audit.jsonl"),
                          ("coverage_blocked", blocked_marker)):
            if path and path.is_file():
                item["evidence"][key] = base.descriptor(path, output)
        item["evidence"]["screenshots"] = [base.descriptor(path, output) for path in screenshots]
        item["evidence"]["picker_events"] = [base.descriptor(path, output) for path in picker_events]
    except base.Blocked as error:
        item.update(state="BLOCKED", reason=str(error))
    except (OSError, subprocess.SubprocessError) as error:
        item.update(state="FAIL", reason=f"Owned resource operation failed ({type(error).__name__})")
    except (base.Failed, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        item.update(state="FAIL", reason=str(error))
    finally:
        cleanup = {"app_processes": True, "services": True, "transport_proxies": True,
                   "identity_barriers": True,
                   "source_fixture": True, "private": False, "keychain_item": not keychain_started}
        for barrier in barriers:
            try: cleanup["identity_barriers"] = barrier.close() and cleanup["identity_barriers"]
            except Exception: cleanup["identity_barriers"] = False
        if barriers:
            base.write_json(case_out / "identity-barrier.json", {"observations": [barrier.observation for barrier in barriers]})
            item["evidence"]["identity_barrier"] = base.descriptor(case_out / "identity-barrier.json", output)
        for proxy in proxies:
            try: cleanup["transport_proxies"] = proxy.close() and cleanup["transport_proxies"]
            except Exception: cleanup["transport_proxies"] = False
        if proxies:
            base.write_json(case_out / "transport-audit.json", {"requests": [row for proxy in proxies for row in proxy.requests]})
            item["evidence"]["transport_audit"] = base.descriptor(case_out / "transport-audit.json", output)
        for service in services:
            try: cleanup["services"] = service.close() and cleanup["services"]
            except Exception: cleanup["services"] = False
        if services:
            base.write_json(case_out / "service-audit.json", {"requests": [row for service in services for row in service.requests]})
            item["evidence"]["service_audit"] = base.descriptor(case_out / "service-audit.json", output)
        if database and database.is_file():
            try:
                oracle_after = sources.verify_accounts(database)
                after = base.safe_snapshot_database(database, case_id, args.run_id)
                base.write_json(case_out / "database-after.json", {"account_oracle": oracle_after, "snapshot": after})
                item["evidence"]["database_after"] = base.descriptor(case_out / "database-after.json", output)
            except Exception as error:
                item["state"], item["reason"] = "FAIL", "Read-only DB aftermath check failed: " + str(error)
        if installed:
            try: cleanup["app_processes"] = base.stop_owned_apps(private / "installation")
            except Exception: cleanup["app_processes"] = False
        if keychain_started and installed and profile and cleanup["app_processes"]:
            try:
                postflight = keychain_probe_stage(
                    "postflight", args=args, installed=installed, profile=profile, private=private,
                    case_out=case_out, owner_id=owner_id, expect_created=keychain_expected,
                    dmg_digest=package["artifacts"]["dmg"]["sha256"])
                if postflight["app_signature_digest"] != keychain_signature:
                    raise base.Blocked("Native Keychain App signature changed after first call")
                item["evidence"]["keychain_postflight"] = base.descriptor(
                    case_out / "keychain-postflight.json", output)
                cleaned = keychain_probe_stage(
                    "cleanup", args=args, installed=installed, profile=profile, private=private,
                    case_out=case_out, owner_id=owner_id, expect_created=keychain_expected,
                    dmg_digest=package["artifacts"]["dmg"]["sha256"])
                if cleaned["app_signature_digest"] != keychain_signature:
                    raise base.Blocked("Native Keychain App signature changed during cleanup")
                item["evidence"]["keychain_cleanup"] = base.descriptor(
                    case_out / "keychain-cleanup.json", output)
                cleanup["keychain_item"] = True
            except (base.Blocked, base.Failed, OSError, ValueError, KeyError) as error:
                cleanup["keychain_item"] = False
                if item["state"] == "PASS":
                    item["state"] = "BLOCKED"
                    item["reason"] = str(error)
                else:
                    item["cleanup_reason"] = str(error)
            finally:
                for mode in ("preflight", "postflight", "cleanup"):
                    evidence = case_out / f"keychain-{mode}.json"
                    if evidence.is_file() and not evidence.is_symlink():
                        item["evidence"][f"keychain_{mode}"] = base.descriptor(evidence, output)
        if source_fixture and cleanup["app_processes"]:
            try: source_fixture.cleanup()
            except Exception: cleanup["source_fixture"] = False
        if all(value for key, value in cleanup.items() if key != "private"):
            try:
                shutil.rmtree(private)
                cleanup["private"] = not private.exists()
            except OSError: pass
        item["cleanup"] = {**cleanup, "completed": all(cleanup.values())}
        if item["state"] == "PASS" and not all(cleanup.values()):
            item["state"], item["reason"] = "FAIL", "Owned resource cleanup was incomplete"
        item["finished_at"] = now()
    if item["state"] == "PASS":
        audit = evidence_audit.verify_case(case, item, output, args.package_manifest, run_id=args.run_id)
        audit_path = case_out / "evidence-audit.json"
        base.write_json(audit_path, audit)
        item["evidence"]["structure_audit"] = base.descriptor(audit_path, output)
        if audit["state"] != "PASS":
            item["state"], item["reason"] = "FAIL", "Fixed TM-002 evidence audit failed: " + "; ".join(audit["errors"])
    return item


def execute(args) -> int:
    catalog, variants_by_parent = read_catalog()
    cases = select_cases(catalog, args.case_id or [])
    output = require_new_directory(args.output)
    scope = ("tm002_granular_targeted_development_probe" if args.case_id else
             "tm002_granular_development_package") if args.development else (
             "tm002_granular_targeted_final_probe" if args.case_id else "tm002_granular_final_package")
    report = {"schema_version": 1, "scope": scope,
              "release_id": RELEASE, "source_commit": args.candidate_sha,
              "run_id": args.run_id, "started_at": now(), "finished_at": None,
              "expected_cases": [case["id"] for case in cases], "tc_results": [],
              "keychain_expectations": {case["id"]: case["id"] not in NO_KEYCHAIN_ITEM_EXPECTED
                                        for case in cases if case["id"] not in variants_by_parent},
              "state": "BLOCKED", "release_eligible": False, "cleanup_completed": False}
    code_paths = [ROOT / path for path in ("scripts/granular_permissions.py", "scripts/verify_tm002_evidence.py",
                 "scripts/tm002_fixture.py",
                 "scripts/tm002_keychain_probe.swift",
                 "scripts/local_e2e.py", "scripts/granular_service_fixture.py",
                 "scripts/bootstrap_sqlite.py", "tests/server/fixtures.py",
                 "apps/desktop/package-lock.json", "server/requirements-dev.txt",
                 "apps/desktop/e2e/granular-permissions.spec.ts",
                 "apps/desktop/e2e/native_picker_driver.swift",
                 "apps/desktop/e2e/playwright.config.ts", "tests/test_cases.json",
                 "apps/desktop/native/source-helper.c", "apps/desktop/src/main/source-audit.ts",
                 "apps/desktop/src/main/source-access.ts", "apps/desktop/src/main/source-ipc.ts",
                 "apps/desktop/src/main/source-helper.ts",
                 "apps/desktop/src/main/source-store.ts")]
    code_paths.extend((ROOT / "server").rglob("*.py"))
    report["test_inputs_sha256"] = {path.relative_to(ROOT).as_posix(): base.digest(path)
                                    for path in code_paths if path.is_file()}
    report["test_code_snapshot"] = []
    for path in code_paths:
        if path.is_file():
            destination = output / "test-code" / path.relative_to(ROOT)
            destination.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            shutil.copyfile(path, destination)
            os.chmod(destination, 0o600)
            report["test_code_snapshot"].append(base.descriptor(destination, output))
    private = None
    mount = None
    cleanup = True
    try:
        if not base.RUN_ID.fullmatch(args.run_id) or not re.fullmatch(r"[a-f0-9]{40}", args.candidate_sha):
            raise base.Failed("Run ID or candidate SHA is malformed")
        if args.package_manifest.is_symlink() or args.dmg.is_symlink():
            raise base.Failed("Package input is linked")
        manifest = args.package_manifest.resolve(strict=True)
        dmg = args.dmg.absolute()
        if any(parent.is_symlink() for parent in dmg.parents):
            raise base.Failed("DMG path has a linked parent")
        if not dmg.is_file():
            raise base.Blocked("Selected package DMG is missing")
        args.dmg = dmg
        package = verify_package(manifest, dmg, args.candidate_sha, development=args.development)
        report["package"] = {"manifest_sha256": base.digest(manifest), "dmg_sha256": base.digest(dmg),
                             "app_tree_sha256": package["app"]["tree_sha256"],
                             "installed_source": "development_dmg" if args.development else "final_dmg"}
        report["working_tree_dirty"] = package["working_tree_dirty"]
        report["candidate_tree"] = package["candidate_tree"]
        report["host"] = {"macos": platform.mac_ver()[0], "architecture": platform.machine()}
        verify_test_account(args)
        report["ax_preflight"] = ax_preflight()
        if not (ROOT / "apps/desktop/node_modules/.bin/playwright").is_file():
            raise base.Blocked("Pinned Playwright executable is absent")
        private_base = require_private_base(args.private_base or ROOT / ".local/tm002-permissions-work")
        private = Path(tempfile.mkdtemp(prefix=args.run_id + "-", dir=private_base)).resolve()
        os.chmod(private, 0o700)
        base.write_json(private / "owner.json", {"owner": "tokenmeter-tm002-e2e", "run_id": args.run_id})
        mount = private / "mounted"
        mounted = base.mount_dmg(dmg, mount, output / "mount.log")
        tree_tool = base.module("tm002_tree", "scripts/package_release_dmg.py")
        bootstrap = base.module("tm002_bootstrap", "scripts/bootstrap_sqlite.py")
        fixtures = base.module("tm002_accounts", "tests/server/fixtures.py")
        results: dict[str, dict] = {}
        for case in cases:
            if case["id"] in variants_by_parent:
                continue
            result = one_case(case, args, package, mounted, private, output, tree_tool, bootstrap, fixtures)
            report["tc_results"].append(result)
            results[case["id"]] = result
            if not result["cleanup"]["completed"]:
                cleanup = False
                break
        for case in cases:
            if case["id"] not in variants_by_parent:
                continue
            child_ids = variants_by_parent[case["id"]]
            child_results = [results.get(identity) for identity in child_ids]
            if not all(child_results):
                result = blocked(case, "A required fixed variant has no independent attempt")
            elif all(child["state"] == "PASS" for child in child_results):
                result = {**blocked(case, ""), "state": "PASS", "reason": "Derived from all fixed variant originals",
                          "cleanup": {"completed": all(child["cleanup"]["completed"] for child in child_results)}}
            else:
                state = "FAIL" if any(child["state"] == "FAIL" for child in child_results) else "BLOCKED"
                result = {**blocked(case, "A fixed variant failed or is blocked"), "state": state}
            report["tc_results"].append(result)
    except (base.Blocked, base.Failed, OSError, ValueError, KeyError, TypeError,
            subprocess.SubprocessError) as error:
        state = "BLOCKED" if isinstance(error, (base.Blocked, FileNotFoundError)) else "FAIL"
        reason = (f"Required local input is unavailable ({type(error).__name__})"
                  if isinstance(error, OSError) else str(error))
        report["preflight"] = {"state": state, "reason": reason}
        seen = {result["case_id"] for result in report["tc_results"]}
        report["tc_results"].extend(blocked(case, reason) for case in cases if case["id"] not in seen)
    finally:
        if mount and mount.exists():
            try:
                base.command(["hdiutil", "detach", str(mount)], timeout=120, log=output / "unmount.log")
            except (base.Blocked, base.Failed):
                cleanup = False
        if private and private.exists():
            if cleanup:
                marker = private / "owner.json"
                try:
                    if json.loads(marker.read_text(encoding="utf-8")) != {"owner": "tokenmeter-tm002-e2e", "run_id": args.run_id}:
                        raise base.Failed("TM-002 private owner changed")
                    shutil.rmtree(private)
                except (OSError, ValueError, base.Failed):
                    cleanup = False
            else:
                report["private_recovery_required"] = True
        report["cleanup_completed"] = cleanup and (private is None or not private.exists())
        report["finished_at"] = now()
        ordered = {item["case_id"]: item for item in report["tc_results"]}
        report["tc_results"] = [ordered.get(case["id"], blocked(case, "No independent attempt")) for case in cases]
        if report["tc_results"] and all(item["state"] == "PASS" for item in report["tc_results"]) and report["cleanup_completed"]:
            report["state"] = "PASS"
        elif any(item["state"] == "FAIL" for item in report["tc_results"]) or report.get("preflight", {}).get("state") == "FAIL":
            report["state"] = "FAIL"
        else:
            report["state"] = "BLOCKED"
        base.write_json(output / "result.json", report)
        if report["state"] == "PASS":
            audit = evidence_audit.verify_report(output / "result.json", package_manifest=args.package_manifest)
            base.write_json(output / "evidence-audit.json", audit)
            report["evidence_audit"] = base.descriptor(output / "evidence-audit.json", output)
            if audit["state"] != "PASS":
                report["state"] = "FAIL"
                report["evidence_audit_reason"] = "Fixed TM-002 report evidence audit failed: " + "; ".join(audit["errors"])
            base.write_json(output / "result.json", report)
    return 0 if report["state"] == "PASS" else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-manifest", type=Path, required=True)
    parser.add_argument("--dmg", type=Path, required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--run-id", default="local-" + uuid.uuid4().hex)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--development", action="store_true",
                        help="Run only this requirement's fixed TC against the marked development DMG")
    parser.add_argument("--keychain-test-user",
                        help="Explicit separate non-admin macOS test account; required for product execution")
    parser.add_argument("--keychain-excluded-user",
                        help="Explicit primary macOS account whose Keychain must remain untouched")
    parser.add_argument("--keychain-excluded-uid", type=int,
                        help="Primary account UID, checked against --keychain-excluded-user")
    parser.add_argument("--private-base", type=Path,
                        help="Existing or creatable owned 0700 work base for the separate test account")
    parser.add_argument("--case-id", action="append")
    args = parser.parse_args(argv)
    return execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
