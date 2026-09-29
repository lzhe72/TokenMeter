"""Independent account fixture specification, isolated generation and reset."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

RUN_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
MARKER = ".tokenmeter-accounts.json"
OWNED = {MARKER, "users.json", "expected.json", "manifest.json"}
FIXED_CLOCK = 1_790_654_400  # 2026-09-29 04:00:00Z, not the production clock.
IDS = {
    "admin": "00000000-0000-4000-8000-000000000001",
    "alice": "00000000-0000-4000-8000-000000000002",
    "bob": "00000000-0000-4000-8000-000000000003",
    "disabled": "00000000-0000-4000-8000-000000000004",
}
CHANGED_PASSWORD = "TEST-ONLY-Changed-42!"
RESET_PASSWORD = "TEST-ONLY-Reset-42!"


def accounts(seed=42):
    return [{"id": IDS[name], "username": f"test-{name}",
             "password": f"TEST-ONLY-{name}-{seed}!",
             "role": "admin" if name == "admin" else "member",
             "is_active": name != "disabled"} for name in IDS]


def expected():
    # Approved oracle values are independent of API/ORM/production functions.
    return {"account_count": 4, "users": [
        {"id": IDS["admin"], "username": "test-admin", "role": "admin", "is_active": True, "must_change_password": True},
        {"id": IDS["alice"], "username": "test-alice", "role": "member", "is_active": True, "must_change_password": True},
        {"id": IDS["bob"], "username": "test-bob", "role": "member", "is_active": True, "must_change_password": True},
        {"id": IDS["disabled"], "username": "test-disabled", "role": "member", "is_active": False, "must_change_password": True}],
        "changed_password": CHANGED_PASSWORD, "reset_password": RESET_PASSWORD,
        "initial_schema_version": "0001", "session_seconds": 86400,
        "login_failure_limit": 5, "login_window_seconds": 300}


def _target(run_id, workspace=None):
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid isolated run ID")
    target = Path(os.path.abspath(workspace or Path.cwd())) / ".local/account-fixtures" / run_id
    for part in (target, *target.parents):
        if part.is_symlink() or (part.exists() and not part.is_dir()):
            raise ValueError("Refusing symlink or non-directory fixture path")
    return target


def _encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def generate(run_id, seed=42, *, workspace=None):
    target = _target(run_id, workspace)
    if target.exists():
        raise ValueError("Fixture directory already exists")
    payloads = {
        MARKER: _encode({"owner": "tokenmeter-account-fixtures", "run_id": run_id, "files": sorted(OWNED)}),
        "users.json": _encode({"schema_version": 1, "test_only": True, "users": accounts(seed)}),
        "expected.json": _encode(expected()),
    }
    payloads["manifest.json"] = _encode({"schema_version": 1, "run_id": run_id, "seed": seed,
        "fixture_kind": "account-auth-spec", "files": {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}})
    target.mkdir(parents=True, mode=0o700)
    for name, data in payloads.items():
        with (target / name).open("xb") as output:
            os.chmod(output.name, 0o600)
            output.write(data)
    return target


def reset(run_id, *, workspace=None):
    target = _target(run_id, workspace)
    if not target.is_dir() or {p.name for p in target.iterdir()} != OWNED:
        raise ValueError("Fixture ownership/file set does not match")
    for child in target.iterdir():
        if child.is_symlink() or not child.is_file():
            raise ValueError("Refusing foreign fixture entry")
    marker = json.loads((target / MARKER).read_text())
    if marker != {"owner": "tokenmeter-account-fixtures", "run_id": run_id, "files": sorted(OWNED)}:
        raise ValueError("Invalid fixture ownership marker")
    for name in OWNED:
        (target / name).unlink()
    target.rmdir()
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("generate", "reset"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    path = generate(args.run_id, args.seed) if args.operation == "generate" else reset(args.run_id)
    print(json.dumps({"operation": args.operation, "path": str(path)}))
