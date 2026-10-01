#!/usr/bin/env python3
"""Run all TM-001 Playwright cases against an App copied from one final DMG.

This runner collects evidence. Only scripts/local_gate.py may decide release
eligibility. It never opens the user's production database or installed App.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import urlopen
from urllib.parse import unquote, urlparse
import uuid


ROOT = Path(__file__).resolve().parents[1]
CASES = [f"E2E-TM001-{number:03d}" for number in (1, 2, 3, 5, 6, 4)]
RUN_ID = re.compile(r"local-[0-9a-f]{32}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
ACCESS = re.compile(r'"(GET|POST|PUT|PATCH|DELETE) (\/[^ ?"]*) HTTP/[0-9.]+" ([0-9]{3})')


class Blocked(RuntimeError):
    """A required real execution input or host capability is absent."""


class Failed(RuntimeError):
    """A present input or product result contradicts the contract."""


def iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def descriptor(path: Path, base: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(base.resolve()):
        raise Failed("Evidence is absent or outside the owned output")
    return {"path": path.relative_to(base).as_posix(), "sha256": digest(path), "bytes": path.stat().st_size}


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    if spec is None or spec.loader is None:
        raise Blocked(f"Missing source module {relative}")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def checked_file(base: Path, description: dict) -> Path:
    if not isinstance(description, dict) or not isinstance(description.get("path"), str):
        raise Blocked("Package asset descriptor is missing")
    relative = Path(description["path"])
    if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
        raise Failed("Package asset path escapes its directory")
    target = base / relative
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(base.resolve()):
        raise Blocked("Package asset is missing or linked")
    if digest(target) != description.get("sha256") or target.stat().st_size != description.get("bytes"):
        raise Failed("Package asset digest or size changed")
    return target


def command(argv: list[str], *, timeout=120, cwd=ROOT, log: Path | None = None) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Blocked(f"Required command could not complete: {Path(argv[0]).name}") from exc
    if log is not None:
        log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise Failed(f"{Path(argv[0]).name} exited {result.returncode}; see case evidence")
    return result


def approved_release_config(package: dict) -> dict:
    """Bind package versions to the source-controlled config for this release."""
    release_id = package.get("release_id")
    if not isinstance(release_id, str) or not re.fullmatch(r"v\d+\.\d+\.\d+-\d{8}T\d{6}Z", release_id):
        raise Failed("Package release ID is invalid")
    config_path = ROOT / "releases" / release_id / "local-release.json"
    if config_path.is_symlink() or not config_path.is_file():
        raise Blocked("Approved local release config is absent")
    if digest(config_path) != package.get("config_sha256"):
        raise Failed("Package release config digest differs from source")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Failed("Approved local release config is unreadable") from exc
    builder = module("local_e2e_package", "scripts/local_package.py")
    try:
        builder.validate_config(config)
    except builder.PackageError as exc:
        raise Failed("Approved local release config is invalid") from exc
    if config["release_id"] != release_id or package.get("distribution_profile") != config["distribution_profile"]:
        raise Failed("Package release identity differs from approved config")
    for asset, version_key, build_key in (("app", "version", "build"),
                                          ("update_app", "upgrade_version", "upgrade_build")):
        details = package.get(asset)
        if (not isinstance(details, dict) or details.get("version") != config[version_key]
                or str(details.get("build")) != config[build_key]
                or details.get("bundle_id") != config["bundle_id"]):
            raise Failed(f"Package {asset} version or build differs from approved config")
    return config


def verify_host_and_manifest(manifest_path: Path, dmg: Path, update_zip: Path, candidate_sha: str,
                             *, development: bool = False) -> dict:
    if platform.system() != "Darwin" or platform.machine() != "x86_64" or not platform.mac_ver()[0].startswith("15."):
        raise Blocked("This local release profile requires macOS 15 Intel")
    for executable in ("hdiutil", "ditto", "codesign", "plutil", "node"):
        if shutil.which(executable) is None:
            raise Blocked(f"Missing local E2E tool: {executable}")
    if not (ROOT / "apps/desktop/node_modules/.bin/playwright").is_file():
        raise Blocked("Pinned Playwright dependencies are not installed")
    package = json.loads(manifest_path.read_text())
    required_scope = "development" if development else "final_package"
    if package.get("schema_version") != 2 or package.get("scope") != required_scope:
        raise Failed("The input is not a final Electron package manifest")
    if package.get("candidate_sha") != candidate_sha or (not development and package.get("working_tree_dirty") is not False):
        raise Failed("Package source differs from requested clean candidate")
    if checked_file(manifest_path.parent, package["artifacts"]["dmg"]).resolve() != dmg.resolve():
        raise Failed("DMG differs from manifest")
    if checked_file(manifest_path.parent, package["artifacts"]["update_zip"]).resolve() != update_zip.resolve():
        raise Failed("Upgrade ZIP differs from manifest")
    approved_release_config(package)
    return package


def bind_parent_report(parent_path: Path | None, *, run_id: str, candidate_sha: str,
                       package: dict, manifest: Path, dmg: Path) -> dict:
    """Bind the supplemental run to the finished detailed original before opening the App."""
    if parent_path is None:
        raise Blocked("Final supplemental E2E requires the detailed parent report")
    parent_path = Path(parent_path).absolute()
    if parent_path.is_symlink() or not parent_path.is_file():
        raise Blocked("Detailed parent report is absent or linked")
    original = parent_path.read_bytes()
    parent = json.loads(original)
    if not isinstance(parent, dict) or not RUN_ID.fullmatch(str(parent.get("run_id", ""))):
        raise Failed("Detailed parent has no valid run identity")
    expected_package = {"manifest_sha256": digest(manifest), "dmg_sha256": digest(dmg),
                        "app_tree_sha256": package["app"]["tree_sha256"],
                        "installed_source": "final_dmg"}
    if (parent["run_id"] == run_id or parent.get("scope") != "granular_final_package"
            or parent.get("state") != "BLOCKED" or parent.get("cleanup_completed") is not True
            or parent.get("source_commit") != candidate_sha
            or parent.get("candidate_tree") != package["candidate_tree"]
            or parent.get("release_id") != package["release_id"]
            or parent.get("package") != expected_package):
        raise Failed("Supplemental E2E parent differs from this clean candidate and DMG")
    if parent_path.read_bytes() != original:
        raise Failed("Detailed parent changed during supplemental preflight")
    return {"parent_run_id": parent["run_id"],
            "parent_report_sha256": hashlib.sha256(original).hexdigest()}


def mount_dmg(dmg: Path, mount: Path, log: Path) -> Path:
    mount.mkdir(mode=0o700)
    command(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", str(mount), str(dmg)], timeout=180, log=log)
    app = mount / "TokenMeter.app"
    if app.is_symlink() or not app.is_dir() or app.name != "TokenMeter.app":
        raise Failed("Final DMG does not contain one regular TokenMeter.app")
    return app


def copy_verified_app(source: Path, destination: Path, package: dict, tree_tool, log: Path) -> Path:
    destination.parent.mkdir(mode=0o700, exist_ok=True)
    command(["ditto", str(source), str(destination)], timeout=180, log=log)
    if tree_tool.tree_sha256(destination) != package["app"]["tree_sha256"]:
        raise Failed("App copied from final DMG differs from signed candidate")
    requirement = package["app"].get("designated_requirement")
    if not isinstance(requirement, str) or not requirement:
        raise Failed("Missing signed App designated requirement")
    command(["codesign", "--verify", "--deep", "--strict", "-R", "=" + requirement, str(destination)], log=log)
    plist = destination / "Contents/Info.plist"
    for key, expected in (("CFBundleShortVersionString", package["app"]["version"]),
                          ("CFBundleVersion", str(package["app"]["build"])),
                          ("CFBundleIdentifier", package["app"]["bundle_id"])):
        if command(["plutil", "-extract", key, "raw", str(plist)]).stdout.strip() != expected:
            raise Failed(f"Installed App {key} differs from package")
    return destination


def make_account_database(private: Path, case_out: Path, short_id: str, seed: int, bootstrap, fixtures) -> tuple[Path, Path, Path]:
    """Create a real migrated DB, execute synthetic SQL, and keep its oracle separate."""
    private.mkdir(mode=0o700, exist_ok=True)
    fixture = fixtures.generate(short_id, seed, workspace=private)
    database = private / "accounts.sqlite"
    bootstrap._new_database(database, "test", short_id)
    sql_text = bootstrap._seed_sql("test", short_id, fixtures.accounts(seed))
    sql = case_out / f"seed-{seed}.sql"
    sql.write_text(sql_text)
    os.chmod(sql, 0o600)
    bootstrap._apply_sql(database, sql_text)
    bootstrap._assert_database(database, "test", short_id, fixtures.accounts(seed))
    return database, fixture, sql


def safe_snapshot_database(database: Path, case_id: str, run_id: str) -> dict:
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        version = db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        owner = db.execute("SELECT environment,run_id FROM tokenmeter_seed_owner").fetchone()
        users = [dict(zip(("id", "username", "role", "is_active", "must_change_password"), row)) for row in
                 db.execute("SELECT id,username,role,is_active,must_change_password FROM users ORDER BY username")]
        audit = [dict(zip(("action", "actor_id", "target_id"), row)) for row in
                 db.execute("SELECT action,actor_id,target_id FROM audit ORDER BY occurred_at,id")]
        sessions = db.execute("SELECT count(*) FROM sessions").fetchone()[0]
        buckets = db.execute("SELECT count(*) FROM login_buckets").fetchone()[0]
        session_rows = [dict(zip(("user_id", "credential_version", "expires_at"), row)) for row in
                        db.execute("SELECT user_id,credential_version,expires_at FROM sessions ORDER BY user_id,expires_at")]
        bucket_rows = [dict(zip(("key_digest", "failures", "window_start"), row)) for row in
                       db.execute("SELECT key,failures,window_start FROM login_buckets ORDER BY key")]
    return {"case_id": case_id, "run_id": run_id, "integrity_check": integrity, "schema_version": version,
            "owner": {"environment": owner[0], "run_id": owner[1]}, "users": users,
            "audit_actions": audit, "session_count": sessions, "login_bucket_count": buckets,
            "sessions_without_tokens": session_rows, "login_buckets_without_credentials": bucket_rows,
            "actual_database_path": str(database)}


class Service:
    def __init__(self, database: Path, owner: Path, *, clock_file: Path | None = None):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0)); listener.listen(128)
        self.listener = listener
        self.url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        self.requests: list[dict] = []
        self.log = owner / f"service-{listener.getsockname()[1]}.log"
        self.env = dict(os.environ, TOKENMETER_DATABASE_URL="sqlite:///" + str(database))
        self.argv = [sys.executable, "-m", "uvicorn", "server.tokenmeter_server.main:app", "--fd", str(listener.fileno()), "--no-proxy-headers"]
        if clock_file:
            self.argv = [sys.executable, "scripts/granular_clock_server.py", "--fd", str(listener.fileno()),
                         "--database", str(database), "--clock-file", str(clock_file)]
        try:
            self.process = subprocess.Popen(
                self.argv, cwd=ROOT, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                pass_fds=(listener.fileno(),), bufsize=1)
        except BaseException:
            listener.close()
            raise
        self.thread = threading.Thread(target=self._collect, daemon=True)
        self.thread.start()
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise Blocked("Owned FastAPI service exited before readiness")
                try:
                    with urlopen(self.url + "/v1/health", timeout=1) as response:
                        if response.status == 200:
                            return
                except OSError:
                    pass
                time.sleep(0.2)
            raise Blocked("Owned FastAPI service readiness timed out")
        except BaseException:
            self.close()
            raise

    def _collect(self) -> None:
        assert self.process.stdout is not None
        # Independent TC cases inspect this owned request log while the service
        # is alive, so each request line must become observable immediately.
        with self.log.open("a", buffering=1) as log:
            os.chmod(self.log, 0o600)
            for line in self.process.stdout:
                match = ACCESS.search(line)
                if match:
                    self.requests.append({"method": match.group(1), "route": match.group(2),
                                          "status": int(match.group(3)), "time": iso(), "origin": self.url})
                log.write(line)

    def restart(self) -> dict:
        old_pid = self.process.pid
        self.process.terminate()
        self.process.wait(timeout=10)
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise Failed("Old owned service log reader did not stop")
        self.process = subprocess.Popen(self.argv, cwd=ROOT, env=self.env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            pass_fds=(self.listener.fileno(),), bufsize=1)
        self.thread = threading.Thread(target=self._collect, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.process.poll() is not None: raise Failed("Restarted owned service exited")
            try:
                with urlopen(self.url + "/v1/health", timeout=1) as response:
                    if response.status == 200:
                        return {"old_pid": old_pid, "new_pid": self.process.pid, "same_origin": True, "health": 200}
            except OSError: pass
            time.sleep(.1)
        raise Failed("Restarted owned service did not become healthy")

    def close(self) -> bool:
        if self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait(timeout=5)
        self.listener.close()
        self.thread.join(timeout=5)
        try:
            with socket.create_connection(("127.0.0.1", int(self.url.rsplit(":", 1)[1])), timeout=1):
                return False
        except OSError:
            return self.process.poll() is not None and not self.thread.is_alive()


class UpdateFixture:
    """One owned, nonce-checked source for all four updater stages."""
    def __init__(self, update_zip: Path, package: dict, *, forbidden_target_url: str | None = None):
        self.stage = "current"
        self.nonce = uuid.uuid4().hex
        self.token = uuid.uuid4().hex + uuid.uuid4().hex
        self.requests: list[dict] = []
        self.update_zip = update_zip
        self.signature = package["signatures"]["update_ed_signature"]
        self.version = package["update_app"]["version"]
        self.build = str(package["update_app"]["build"])
        self.forbidden_target_url = forbidden_target_url or "http://example.invalid/update.zip"
        self.stop = threading.Event()
        self.slow_release = threading.Event()
        self.slow_waiting = threading.Event()
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return

            def _answer(self, code: int, body: bytes = b"", **headers):
                self.send_response(code)
                self.send_header("Cache-Control", "no-store")
                for name, value in headers.items(): self.send_header(name.replace("_", "-"), str(value))
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    try: self.wfile.write(body)
                    except (BrokenPipeError, ConnectionResetError): pass
                fixture.requests.append({"stage": fixture.stage, "method": self.command, "route": self.path,
                                         "status": code, "bytes_sent": len(body),
                                         "body_sha256": hashlib.sha256(body).hexdigest(), "time": iso()})

            def do_POST(self):
                stage = self.path.removeprefix("/control/") if self.path.startswith("/control/") else ""
                if self.headers.get("Authorization") != "Bearer " + fixture.token or stage not in {"forbidden", "redirect", "redirect-multi", "redirect-allowed", "slow", "release-slow", "invalid", "valid"}:
                    self._answer(403); return
                if stage == "release-slow":
                    if fixture.stage != "slow" or not fixture.slow_waiting.is_set():
                        self._answer(409); return
                    fixture.slow_release.set()
                    self._answer(200, json.dumps({"stage": "slow-released", "nonce": fixture.nonce}).encode(), Content_Type="application/json")
                    return
                if stage == "slow":
                    fixture.slow_release.clear()
                    fixture.slow_waiting.clear()
                fixture.stage = stage
                self._answer(200, json.dumps({"stage": stage, "nonce": fixture.nonce}).encode(), Content_Type="application/json")

            def do_GET(self):
                if self.path == "/observations":
                    if self.headers.get("Authorization") != "Bearer " + fixture.token:
                        self._answer(403); return
                    self._answer(200, json.dumps({"nonce": fixture.nonce, "requests": fixture.requests}).encode(), Content_Type="application/json"); return
                if self.path == "/health":
                    self._answer(200, fixture.nonce.encode()); return
                if self.path == "/version.json":
                    if fixture.stage == "current": self._answer(204); return
                    route = {"redirect": "/redirect.zip", "redirect-multi": "/redirect-first.zip",
                             "redirect-allowed": "/redirect-allowed.zip"}.get(fixture.stage, "/update.zip")
                    address = fixture.forbidden_target_url if fixture.stage == "forbidden" else fixture.url + route
                    signature = fixture.signature
                    if fixture.stage in {"invalid", "redirect-allowed"}:
                        raw = bytearray(base64.b64decode(signature)); raw[0] ^= 1
                        signature = base64.b64encode(raw).decode()
                    body = json.dumps({"schema_version": 1, "version": fixture.version, "build": fixture.build,
                                       "url": address, "sha256": digest(fixture.update_zip),
                                       "bytes": fixture.update_zip.stat().st_size, "ed25519_signature": signature}).encode()
                    self._answer(200, body, Content_Type="application/json"); return
                if self.path == "/redirect.zip":
                    self._answer(302, Location=fixture.forbidden_target_url); return
                if self.path == "/redirect-first.zip":
                    self._answer(302, Location=fixture.url + "/redirect.zip"); return
                if self.path == "/redirect-allowed.zip":
                    self._answer(302, Location=fixture.url + "/update.zip"); return
                if self.path == "/update.zip":
                    if fixture.stage == "slow":
                        fixture.requests.append({"stage": "slow", "method": "GET", "route": self.path,
                                                 "status": 0, "time": iso(), "waiting": True})
                        fixture.slow_waiting.set()
                        released = fixture.slow_release.wait(180)
                        if fixture.stop.is_set(): return
                        if not released:
                            self._answer(504); return
                    self._answer(200, fixture.update_zip.read_bytes(), Content_Type="application/zip"); return
                self._answer(404)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        with urlopen(self.url + "/health", timeout=3) as response:
            if response.read().decode() != self.nonce:
                raise Blocked("Owned update source nonce mismatch")

    def close(self) -> bool:
        self.stop.set()
        self.slow_release.set()
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=5)
        return not self.thread.is_alive()


def stop_owned_apps(installation: Path) -> bool:
    """Only target the unique executable under this invocation's private install."""
    executable = str(installation / "TokenMeter.app/Contents/MacOS/TokenMeter")
    result = subprocess.run(["ps", "-axo", "pid=,command="], text=True, capture_output=True, check=False)
    if result.returncode:
        return False
    owned = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[1].startswith(executable) and parts[0].isdigit():
            owned.append(int(parts[0]))
    for pid in owned:
        try: os.kill(pid, signal.SIGTERM)
        except ProcessLookupError: pass
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        alive = []
        for pid in owned:
            try: os.kill(pid, 0); alive.append(pid)
            except ProcessLookupError: pass
        if not alive: return True
        time.sleep(0.2)
    for pid in owned:
        try: os.kill(pid, signal.SIGKILL)
        except ProcessLookupError: pass
    return all(not _pid_exists(pid) for pid in owned)


def _pid_exists(pid: int) -> bool:
    try: os.kill(pid, 0); return True
    except ProcessLookupError: return False


SHIPIT_LABEL = "org.tokenmeter.TokenMeter.ShipIt"
SHIPIT_QUIESCENCE_SECONDS = 6.0
SHIPIT_TEARDOWN_TIMEOUT_SECONDS = 15.0
SHIPIT_POLL_SECONDS = 0.2


def _shipit_job_present() -> bool:
    result = subprocess.run(["launchctl", "list", SHIPIT_LABEL], text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return True
    # macOS launchctl uses EX_NOHOST (113) for an absent service. Any other
    # failure means we cannot safely conclude that the fixed ShipIt job is gone.
    if result.returncode == 113:
        return False
    raise Blocked("Cannot determine whether the ShipIt launchd job is present")


def _shipit_byhost_preferences() -> list[Path]:
    root = Path.home() / "Library/Preferences/ByHost"
    return sorted(root.glob(SHIPIT_LABEL + ".*.plist")) if root.is_dir() else []


def prepare_owned_shipit(run_id: str) -> Path:
    """Fail closed if this user's fixed Squirrel location has existing state."""
    cache = Path.home() / "Library/Caches" / SHIPIT_LABEL
    if cache.exists() or cache.is_symlink() or _shipit_job_present() or _shipit_byhost_preferences():
        raise Blocked("Existing Squirrel cache, launchd job or ByHost preference belongs to an unknown App")
    if not cache.parent.is_dir():
        raise Blocked("The user cache parent is unavailable; cannot claim Squirrel state")
    cache.mkdir(mode=0o700)
    write_json(cache / ".tokenmeter-owner.json", {"owner": "tokenmeter-local-e2e", "run_id": run_id})
    return cache


def cleanup_owned_shipit(cache: Path | None, run_id: str, installed_app: Path | None,
                         evidence_directory: Path | None = None) -> bool:
    """Remove only this run's Squirrel state after launchd and preferences settle.

    ShipIt may exit between ``launchctl list`` and ``remove`` and CFPreferences
    may write its empty ByHost plist shortly after the process exits. Both are
    normal asynchronous transitions, so confirm the final state for a bounded
    interval instead of treating one immediate observation as definitive.
    """
    diagnostic = {"run_id": run_id, "state": "FAIL", "owner_verified": False,
                  "verified_target": None, "stages": [], "started_at": iso()}
    current_stage = "start"

    def stage(name: str, reason: str) -> None:
        nonlocal current_stage
        if name != current_stage or not diagnostic["stages"]:
            diagnostic["stages"].append({"at": iso(), "stage": name, "reason": reason})
        current_stage = name

    def finish(success: bool, reason: str) -> bool:
        stage("complete" if success else "rejected", reason)
        diagnostic["state"] = "PASS" if success else "FAIL"
        diagnostic["finished_at"] = iso()
        if evidence_directory is not None:
            try:
                if evidence_directory.is_symlink():
                    return False
                evidence_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                write_json(evidence_directory / "cleanup-stage.json", diagnostic)
            except (OSError, ValueError, TypeError):
                return False
        return success

    if cache is None:
        return finish(True, "no_owned_cache")
    marker = cache / ".tokenmeter-owner.json"
    state = cache / "ShipItState.plist"  # Squirrel writes JSON despite this extension.
    deadline = time.monotonic() + SHIPIT_TEARDOWN_TIMEOUT_SECONDS

    def owned() -> bool:
        if cache.is_symlink() or not cache.is_dir() or marker.is_symlink() or not marker.is_file():
            return False
        cache_stat = cache.stat()
        marker_stat = marker.stat()
        if (cache_stat.st_uid != os.getuid() or cache_stat.st_mode & 0o777 != 0o700
                or marker_stat.st_uid != os.getuid()):
            return False
        return json.loads(marker.read_text()) == {"owner": "tokenmeter-local-e2e", "run_id": run_id}

    def bound_state() -> tuple[str, tuple[int, int] | None]:
        if not state.exists() and not state.is_symlink():
            return "missing", None
        if state.is_symlink() or not state.is_file() or installed_app is None:
            return "invalid", None
        try:
            payload = json.loads(state.read_text())
        except json.JSONDecodeError:
            # Squirrel can expose the file between create and its final write.
            # Wait for a complete target; never remove a job while it is partial.
            return "pending", None
        target = payload.get("targetBundleURL") if isinstance(payload, dict) else None
        parsed = urlparse(target) if isinstance(target, str) else None
        if parsed is None or parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
            return "invalid", None
        if Path(unquote(parsed.path)).resolve() != installed_app.resolve():
            return "invalid", None
        diagnostic["verified_target"] = str(installed_app.resolve())
        info = state.stat()
        return "bound", (info.st_mtime_ns, info.st_size)

    def owned_preferences() -> tuple[list[Path], tuple[tuple[str, int, int], ...]] | None:
        preferences = _shipit_byhost_preferences()
        signature = []
        for preference in preferences:
            info = preference.lstat()
            if (preference.is_symlink() or not preference.is_file() or info.st_uid != os.getuid()
                    or info.st_mtime < marker.stat().st_mtime
                    or plistlib.loads(preference.read_bytes()) != {}):
                return None
            signature.append((preference.name, info.st_mtime_ns, info.st_size))
        return preferences, tuple(signature)

    try:
        if not owned():
            return finish(False, "owner_marker_or_cache_invalid")
        diagnostic["owner_verified"] = True
        stage("owner_verified", "current_run_marker_and_cache_mode")
        removed_job = False
        quiet_since = None
        last_signature = None
        while True:
            if not owned():
                return finish(False, "owner_changed_during_teardown")
            job_present = _shipit_job_present()
            state_status, state_signature = bound_state()
            if state_status == "invalid":
                return finish(False, "shipit_state_target_unverified")
            preference_state = owned_preferences()
            if preference_state is None:
                return finish(False, "byhost_preference_unowned_or_nonempty")
            preferences, preference_signature = preference_state
            now = time.monotonic()
            if state_status == "pending":
                stage("waiting_for_state_write", "shipit_state_is_partial")
                if now >= deadline:
                    return finish(False, "shipit_teardown_timeout_at_" + current_stage)
                time.sleep(SHIPIT_POLL_SECONDS)
                continue
            if job_present:
                quiet_since = None
                if state_status != "bound":
                    stage("waiting_for_bound_state", "job_present_without_verified_target")
                elif not removed_job:
                    stage("removing_owned_job", "bound_target_verified")
                    result = subprocess.run(["launchctl", "remove", SHIPIT_LABEL],
                                            capture_output=True, text=True, check=False)
                    removed_job = True
                    stage("waiting_for_job_exit", "remove_returned_zero" if result.returncode == 0
                          else "remove_nonzero_requires_confirmed_job_absence")
                else:
                    stage("waiting_for_job_exit", "job_still_present")
            else:
                signature = (state_signature, preference_signature)
                if signature != last_signature or quiet_since is None:
                    quiet_since = now
                    last_signature = signature
                    stage("waiting_for_quiescence", "owned_state_or_preference_changed")
                if now - quiet_since >= SHIPIT_QUIESCENCE_SECONDS:
                    stage("quiescent", "job_absent_and_owned_state_stable")
                    break
            if now >= deadline:
                return finish(False, "shipit_teardown_timeout_at_" + current_stage)
            time.sleep(SHIPIT_POLL_SECONDS)

        # The same owner and content checks have held through the settling
        # window. Copy evidence before asking CFPreferences to delete its domain.
        for preference in preferences:
            if evidence_directory:
                if evidence_directory.is_symlink():
                    return finish(False, "evidence_directory_is_link")
                evidence_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                destination = evidence_directory / preference.name
                if destination.exists() or destination.is_symlink():
                    return finish(False, "preference_evidence_already_exists")
                shutil.copy2(preference, destination)
        stage("clearing_owned_preferences", "verified_empty_byhost_files")
        if preferences:
            # Use CFPreferences as well as checking the file, so its daemon
            # cannot immediately rewrite the removed empty domain.
            removed = subprocess.run(["defaults", "-currentHost", "delete", SHIPIT_LABEL],
                                     capture_output=True, text=True, check=False)
            absent_domain = isinstance(removed.stderr, str) and re.search(
                rf"\bDomain\s+\(?{re.escape(SHIPIT_LABEL)}\)?\s+(?:does not exist|not found)\b",
                removed.stderr, flags=re.IGNORECASE)
            if removed.returncode and not absent_domain:
                return finish(False, "defaults_delete_unrelated_error")
            for preference in preferences:
                if preference.exists():
                    if preference.is_symlink() or plistlib.loads(preference.read_bytes()) != {}:
                        return finish(False, "preference_changed_before_unlink")
                    preference.unlink()
        if not owned() or _shipit_job_present() or _shipit_byhost_preferences():
            return finish(False, "ownership_or_shipit_state_changed_before_cache_remove")
        stage("removing_owned_cache", "owner_and_job_reverified")
        shutil.rmtree(cache)
        if cache.exists() or _shipit_job_present() or _shipit_byhost_preferences():
            return finish(False, "shipit_state_remains_after_cache_remove")
        return finish(True, "owned_shipit_resources_removed")
    except (OSError, ValueError, TypeError, Blocked) as error:
        return finish(False, "exception_at_" + current_stage + "_" + type(error).__name__)


def playwright_case(case_id: str, context: Path, case_out: Path) -> tuple[int, Path]:
    raw = case_out / "playwright.json"
    identity = json.loads(context.read_text())
    env = dict(os.environ, TM_E2E_CONTEXT=str(context), TM_E2E_JSON=str(raw), TM_E2E_CASE_OUTPUT=str(case_out),
               TM_E2E_RUN_ID=identity["run_id"], TM_E2E_CANDIDATE_SHA=identity["candidate_sha"])
    binary = ROOT / "apps/desktop/node_modules/.bin/playwright"
    with (case_out / "playwright.log").open("x") as log:
        os.chmod(case_out / "playwright.log", 0o600)
        try:
            result = subprocess.run([str(binary), "test", "e2e/tm001.spec.ts", "--config", "e2e/playwright.config.ts",
                                     "--grep", case_id], cwd=ROOT / "apps/desktop", env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=600, check=False)
        except subprocess.TimeoutExpired:
            return 124, raw
    return result.returncode, raw


def fixture_evidence(case_out: Path, run_id: str, case_id: str, fixture: Path | None,
                     sql_files: list[Path], *, seed: int | list[int], kind: str) -> Path:
    files = []
    if fixture is not None:
        for source in sorted(fixture.iterdir()):
            if source.is_file() and not source.is_symlink():
                destination = case_out / ("account-" + source.name)
                shutil.copyfile(source, destination); os.chmod(destination, 0o600)
                files.append(descriptor(destination, case_out.parents[0]))
    for sql in sql_files: files.append(descriptor(sql, case_out.parents[0]))
    path = case_out / "fixture-manifest.json"
    write_json(path, {"generator": "scripts/bootstrap_sqlite.py + tests/server/fixtures.py", "fixture_kind": kind,
                      "seed": seed, "run_id": run_id, "case_id": case_id, "files": files})
    return path


def collect_trace_and_screenshots(case_out: Path) -> tuple[list[Path], list[Path]]:
    traces = sorted(p for p in case_out.rglob("trace-*.zip") if p.is_file() and not p.is_symlink())
    shots = sorted(p for p in case_out.rglob("*.png") if p.is_file() and not p.is_symlink())
    return traces, shots


def export_workbook(report_path: Path) -> dict:
    """Keep spreadsheet delivery separate from the immutable product result."""
    exporter = module("local_test_result_export", "scripts/test_result_export.py")
    return exporter.export_result(report_path)


def finish_result(report_path: Path, report: dict) -> int:
    write_json(report_path, report)
    receipt = export_workbook(report_path)
    product_code = 0 if report["state"] == "PASS" else 2 if report["state"] == "BLOCKED" else 1
    if receipt["state"] != "PASS":
        print(json.dumps({"product_state": report["state"], "excel_export_state": receipt["state"],
                          "error": receipt.get("error", "Workbook archive is incomplete")}, ensure_ascii=False), file=sys.stderr)
        return product_code or (2 if receipt["state"] == "BLOCKED" else 1)
    return product_code


def execute(args) -> int:
    out = args.output.absolute()
    if out.exists() or any(part.is_symlink() for part in (out, *out.parents)):
        raise Blocked("E2E output must be a new non-symlink directory")
    out.mkdir(parents=True, mode=0o700)
    os.chmod(out, 0o700)
    started = iso()
    report = {"schema_version": 2, "scope": "development_package" if args.development else "final_package", "distribution_profile": "internal",
              "release_eligible": False, "state": "BLOCKED", "run_id": args.run_id,
              "source_commit": args.candidate_sha, "working_tree_dirty": bool(args.development),
              "started_at": started, "finished_at": started, "expected_cases": CASES,
              "executed_cases": 0, "passed_cases": 0, "suites": [], "cleanup_completed": False,
              "cleanup": {key: False for key in ("mount", "services", "app_processes", "profiles", "installs", "ports")}}
    private = None; mount = None; services: list[Service] = []; source = None; installs: list[Path] = []
    shipit_cache = None; shipit_app = None; completed_service_cleanup = True
    try:
        if not RUN_ID.fullmatch(args.run_id) or not SHA.fullmatch(args.candidate_sha):
            raise Failed("Invalid gate-issued run or candidate identity")
        manifest = args.package_manifest.resolve(strict=True)
        dmg, update_zip = args.dmg.resolve(strict=True), args.update_zip.resolve(strict=True)
        package = verify_host_and_manifest(manifest, dmg, update_zip, args.candidate_sha, development=args.development)
        report["working_tree_dirty"] = package.get("working_tree_dirty") is True
        report.update(release_id=package["release_id"], candidate_tree=package["candidate_tree"],
                      host={"macos": platform.mac_ver()[0], "architecture": platform.machine()},
                      package={"manifest_sha256": digest(manifest), "dmg_sha256": digest(dmg),
                               "app_tree_sha256": package["app"]["tree_sha256"], "build": package["app"]["build"],
                               "installed_source": "final_dmg"})
        if not args.development or getattr(args, "parent_report", None) is not None:
            report.update(bind_parent_report(getattr(args, "parent_report", None), run_id=args.run_id,
                                             candidate_sha=args.candidate_sha, package=package,
                                             manifest=manifest, dmg=dmg))
        private_base = ROOT / ".local/local-e2e-work"
        private_base.mkdir(parents=True, exist_ok=True)
        private = Path(tempfile.mkdtemp(prefix=args.run_id + "-", dir=private_base)).resolve()
        os.chmod(private, 0o700)
        write_json(private / "owner.json", {"owner": "tokenmeter-local-e2e", "run_id": args.run_id})
        mount = private / "mounted"
        mounted_app = mount_dmg(dmg, mount, out / "mount.log")
        tree_tool = module("local_e2e_tree", "scripts/package_release_dmg.py")
        bootstrap = module("local_e2e_bootstrap", "scripts/bootstrap_sqlite.py")
        fixtures = module("local_e2e_fixtures", "tests/server/fixtures.py")
        for case_id in CASES:
            case_out = out / case_id; case_out.mkdir(mode=0o700)
            case_private = private / case_id; case_private.mkdir(mode=0o700)
            install_parent = case_private / "installation"; install_parent.mkdir(mode=0o700)
            installed = copy_verified_app(mounted_app, install_parent / "TokenMeter.app", package, tree_tool, case_out / "install.log")
            installs.append(install_parent)
            profile = case_private / "profile"; profile.mkdir(mode=0o700)
            short_id = "l" + uuid.uuid4().hex[:18]
            seed = 42; kind = "account-auth-spec"
            sql_files = []; fixture = None; secondary = None; database = None
            if case_id.endswith("005"):
                kind = "production_bootstrap"
                bootstrap_root = case_private / "bootstrap"; bootstrap_root.mkdir(mode=0o700)
                bootstrap.initialize_production(bootstrap_root)
                database = bootstrap_root / "database/production/production.db"
                seed_source = database.with_name("seed.sql")
                sql = case_out / "seed-production.sql"; shutil.copyfile(seed_source, sql); os.chmod(sql, 0o600); sql_files.append(sql)
                # A real SQLite backup and restore before any HTTP/UI login.
                backup = case_private / "initial-backup.db"; restored = case_private / "restored.db"
                with sqlite3.connect(database) as original, sqlite3.connect(backup) as target: original.backup(target)
                with sqlite3.connect(backup) as original, sqlite3.connect(restored) as target: original.backup(target)
                with sqlite3.connect(backup) as first, sqlite3.connect(restored) as second:
                    if list(first.iterdump()) != list(second.iterdump()):
                        raise Failed("Production bootstrap backup/restore differs")
                backup_evidence = case_out / "bootstrap-backup.db"
                restored_evidence = case_out / "bootstrap-restored.db"
                for source_db, evidence_db in ((backup, backup_evidence), (restored, restored_evidence)):
                    shutil.copyfile(source_db, evidence_db); os.chmod(evidence_db, 0o600)
                database = restored  # The actual App/API now authenticate against the restored copy.
                write_json(case_out / "restore-state.json", {"integrity_check": "ok", "schema_version": "0001",
                           "table_rows_match": True, "backup_sha256": digest(backup_evidence), "restored_sha256": digest(restored_evidence),
                           "backup": descriptor(backup_evidence, out), "restored": descriptor(restored_evidence, out),
                           "synthetic_only": True, "run_id": args.run_id, "case_id": case_id,
                           "actual_service_database": str(restored)})
            else:
                db_private = case_private / "primary"; db_private.mkdir(mode=0o700)
                database, fixture, sql = make_account_database(db_private, case_out, short_id, 42, bootstrap, fixtures)
                sql_files.append(sql)
            service = Service(database, case_private); services.append(service)
            secondary_url = None
            if case_id.endswith("006"):
                secondary_private = case_private / "secondary"; secondary_private.mkdir(mode=0o700)
                second_id = "l" + uuid.uuid4().hex[:18]
                second_db, secondary, second_sql = make_account_database(secondary_private, case_out, second_id, 43, bootstrap, fixtures)
                sql_files.append(second_sql)
                secondary_service = Service(second_db, case_private); services.append(secondary_service)
                secondary_url = secondary_service.url
                seed = [42, 43]; kind = "dual_service_routes"
            if case_id.endswith("004"):
                shipit_cache = prepare_owned_shipit(args.run_id)
                shipit_app = installed
                source = UpdateFixture(update_zip, package)
            fixture_path = fixture_evidence(case_out, args.run_id, case_id, fixture, sql_files, seed=seed, kind=kind)
            if secondary is not None:
                for source_file in sorted(secondary.iterdir()):
                    if source_file.is_file() and not source_file.is_symlink():
                        target = case_out / ("secondary-" + source_file.name)
                        shutil.copyfile(source_file, target); os.chmod(target, 0o600)
                item = json.loads(fixture_path.read_text())
                item["files"] += [descriptor(path, out) for path in sorted(case_out.glob("secondary-*"))]
                fixture_path.unlink(); write_json(fixture_path, item)
            cdp_port = None
            if case_id.endswith("004"):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    probe.bind(("127.0.0.1", 0)); cdp_port = probe.getsockname()[1]
                    if cdp_port < 1024: raise Blocked("No unprivileged diagnostic loopback port")
            context = case_private / "context.json"
            write_json(context, {"run_id": args.run_id, "candidate_sha": args.candidate_sha,
                                 "case_id": case_id, "app_path": str(installed), "profile_path": str(profile),
                                 "service_url": service.url, "secondary_service_url": secondary_url,
                                 "update_url": source.url + "/version.json" if source else None,
                                 "update_control_url": source.url + "/control" if source else None,
                                 "update_control_token": source.token if source else None,
                                 "update_nonce": source.nonce if source else None, "cdp_port": cdp_port,
                                 "expected_app_version": package["app"]["version"],
                                 "expected_app_build": str(package["app"]["build"]),
                                 "expected_upgrade_version": package["update_app"]["version"],
                                 "expected_upgrade_build": str(package["update_app"]["build"]),
                                 "expected_app_tree_sha256": package["app"]["tree_sha256"],
                                 "expected_update_tree_sha256": package["update_app"]["tree_sha256"]})
            started_case = iso()
            rc, raw = playwright_case(case_id, context, case_out)
            ended_case = iso()
            report["executed_cases"] += 1  # A real Playwright attempt ran, even if it failed before opening a window.
            if source:
                write_json(case_out / "update-requests.json", {"run_id": args.run_id, "case_id": case_id,
                           "origin": source.url, "nonce": source.nonce, "requests": source.requests})
                source_closed = source.close(); source = None
            else: source_closed = True
            for active in services:
                completed_service_cleanup = active.close() and completed_service_cleanup
            audit = {"case_id": case_id, "run_id": args.run_id, "requests": [item for active in services for item in active.requests]}
            write_json(case_out / "service-audit.json", audit)
            services.clear()
            if not completed_service_cleanup:
                raise Failed("A case service or its loopback port remained active")
            write_json(case_out / "database-summary.json", safe_snapshot_database(database, case_id, args.run_id))
            events = case_out / "events.jsonl"
            traces, screenshots = collect_trace_and_screenshots(case_out)
            if not (raw.is_file() and events.is_file() and traces and screenshots):
                report["suites"].append({"case_id": case_id, "state": "FAIL", "cleanup_completed": False,
                    "failures": ["Playwright attempt lacked required raw UI trace, assertions or screenshots"],
                    "playwright_json": descriptor(raw, out) if raw.is_file() else None,
                    "started_at": started_case, "finished_at": ended_case})
                raise Failed(f"{case_id} lacks Playwright raw output, UI events, trace or screenshots")
            suite = {"case_id": case_id, "state": "PASS" if rc == 0 else "FAIL", "failures": [] if rc == 0 else [f"Playwright exited {rc}"],
                     "started_at": started_case, "finished_at": ended_case,
                     "playwright_json": descriptor(raw, out), "events": descriptor(events, out),
                     "fixture_manifest": descriptor(fixture_path, out), "sql": descriptor(sql_files[0], out),
                     "service_audit": descriptor(case_out / "service-audit.json", out),
                     "database_summary": descriptor(case_out / "database-summary.json", out),
                     "trace": descriptor(traces[0], out), "traces": [descriptor(trace, out) for trace in traces],
                     "screenshots": [descriptor(shot, out) for shot in screenshots],
                     "installation": {"path": str(installed), "app_tree_sha256": package["app"]["tree_sha256"],
                                      "signature": package["app"]["designated_requirement"]},
                     "cleanup_completed": source_closed and stop_owned_apps(install_parent)}
            if case_id.endswith("005"):
                suite["restore"] = descriptor(case_out / "restore-state.json", out)
            if case_id.endswith("004"):
                upgrade = json.loads((case_out / "upgrade-result.json").read_text()) if (case_out / "upgrade-result.json").is_file() else {}
                upgrade["old_app_tree_sha256"] = package["app"]["tree_sha256"]
                upgrade["new_app_tree_sha256"] = tree_tool.tree_sha256(installed)
                suite["update"] = {"requests": descriptor(case_out / "update-requests.json", out),
                                   "result": descriptor(case_out / "upgrade-result.json", out) if upgrade else None,
                                   "process": descriptor(case_out / "upgrade-process.json", out) if (case_out / "upgrade-process.json").is_file() else None,
                                   **upgrade}
            report["suites"].append(suite)
            if rc != 0 or not suite["cleanup_completed"]:
                raise Failed(f"{case_id} failed real App UI or owned cleanup; inspect case evidence")
            report["passed_cases"] += 1
        report["state"] = "PASS"
    except KeyboardInterrupt:
        report["state"] = "BLOCKED"
        report["error"] = "Execution interrupted; remaining cases were not executed"
    except (Blocked, Failed, ImportError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        report["state"] = "BLOCKED" if isinstance(error, (Blocked, ImportError, FileNotFoundError)) else "FAIL"
        report["error"] = str(error)
    finally:
        all_services = completed_service_cleanup
        for active in services:
            try: all_services = active.close() and all_services
            except Exception: all_services = False
        source_closed = True
        if source:
            try: source_closed = source.close()
            except Exception: source_closed = False
        cleanup_errors = []
        app_results = []
        for parent in installs:
            try:
                app_results.append(stop_owned_apps(parent))
            except Exception as error:
                app_results.append(False)
                cleanup_errors.append(f"Owned App cleanup: {error}")
        apps_closed = all(app_results)
        mount_closed = True
        if mount and mount.exists():
            try:
                result = subprocess.run(["hdiutil", "detach", str(mount)], capture_output=True, text=True, check=False)
                mount_closed = result.returncode == 0
            except Exception as error:
                mount_closed = False
                cleanup_errors.append(f"Owned mount cleanup: {error}")
        try:
            shipit_closed = cleanup_owned_shipit(shipit_cache, args.run_id, shipit_app,
                                                 out / "shipit-cleanup") if apps_closed else False
        except Exception as error:
            shipit_closed = False
            cleanup_errors.append(f"Owned updater cleanup: {error}")
        shipit_evidence = out / "shipit-cleanup"
        diagnostic = shipit_evidence / "cleanup-stage.json"
        if diagnostic.exists() or diagnostic.is_symlink():
            try:
                report["shipit_cleanup_evidence"] = {
                    "diagnostic": descriptor(diagnostic, out),
                    "owned_empty_preferences": [descriptor(path, out) for path in sorted(shipit_evidence.glob(SHIPIT_LABEL + ".*.plist"))],
                }
            except (Failed, OSError, ValueError):
                shipit_closed = False
                cleanup_errors.append("Owned updater cleanup evidence is invalid")
        elif apps_closed:
            shipit_closed = False
            cleanup_errors.append("Owned updater cleanup stage evidence is missing")
        profiles_closed = installs_closed = False
        if private and private.is_dir() and (private / "owner.json").is_file():
            try:
                marker = json.loads((private / "owner.json").read_text())
                if marker == {"owner": "tokenmeter-local-e2e", "run_id": args.run_id} and mount_closed and apps_closed and all_services and source_closed and shipit_closed:
                    shutil.rmtree(private)
                    profiles_closed = installs_closed = True
            except (OSError, ValueError): pass
        report["cleanup"] = {"mount": mount_closed, "services": all_services,
                             "app_processes": apps_closed, "profiles": profiles_closed,
                             "installs": installs_closed, "ports": all_services and source_closed,
                             "shipit": shipit_closed}
        report["cleanup_completed"] = all(report["cleanup"].values())
        if cleanup_errors:
            report["cleanup_errors"] = cleanup_errors
        if not report["cleanup_completed"] and report["state"] == "PASS":
            report["state"] = "FAIL"; report["error"] = "Owned resources were not fully cleaned"
        report["finished_at"] = iso()
    return finish_result(out / "result.json", report)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-manifest", type=Path, required=True)
    parser.add_argument("--dmg", type=Path, required=True)
    parser.add_argument("--update-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--parent-report", type=Path,
                        help="Finished detailed report for a distinct final supplemental run")
    parser.add_argument("--development", action="store_true", help="Run a dirty development package for red/green diagnostics only")
    args = parser.parse_args(argv)
    return execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
