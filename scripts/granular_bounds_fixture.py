"""Create one owned D42-BOUNDS SQLite fixture for LOGIN-19 parameter E2E.

The caller gives a fresh private directory and a separate owned evidence
directory. This module never selects a repository production/test database.
The generated SQL has salted Argon2 hashes, never clear-text passwords.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys


ROOT = Path(__file__).resolve().parents[1]
OWNER_FILE = ".tokenmeter-bounds-owner.json"
BOUNDARY_ID = "00000000-0000-4000-8000-000000000101"
BOUNDARY_PASSWORD = "TEST-ONLY-Boundary-42!"
VARIANTS = {
    "TC-TM001-LOGIN-19#A": "a_1",
    "TC-TM001-LOGIN-19#B": "a" * 64,
    "TC-TM001-LOGIN-19#C": "test_A-42",
}
RUN_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")


def variant_spec(variant_id: str) -> dict:
    """Return a deterministic, password-free oracle for one boundary row."""
    try:
        username = VARIANTS[variant_id]
    except KeyError as exc:
        raise ValueError("Unknown LOGIN-19 boundary variant") from exc
    return {"variant_id": variant_id, "username": username,
            "stored_username": username.lower(),
            "username_length": len(username), "id": BOUNDARY_ID,
            "role": "member", "is_active": True, "must_change_password": True,
            "base_accounts": 4, "expected_accounts": 5}


def _parts_safe(path: Path) -> None:
    if not path.is_absolute():
        raise ValueError("Fixture paths must be absolute")
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError("Fixture path contains a symbolic link")
        if item.exists() and not item.is_dir() and item == path:
            raise ValueError("Fixture target is not a directory")
    if path == ROOT / "database" or path.is_relative_to(ROOT / "database"):
        raise ValueError("Repository database directories are never fixture targets")


def validate_target(private: Path, evidence: Path, run_id: str, variant_id: str) -> dict:
    """Reject unsafe/reused targets before creating or resetting any file."""
    spec = variant_spec(variant_id)
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid owned fixture run ID")
    private = Path(private)
    evidence = Path(evidence)
    _parts_safe(private)
    _parts_safe(evidence)
    if private == evidence or private.is_relative_to(evidence) or evidence.is_relative_to(private):
        raise ValueError("Private database and evidence directories must be separate")
    for path in (private, evidence):
        if path.exists() and path.stat().st_uid != os.getuid():
            raise ValueError("Fixture directory belongs to another user")
    if private.exists() and any(private.iterdir()):
        raise ValueError("Boundary fixture private directory must be empty")
    if evidence.exists() and (evidence / "seed-42-bounds.sql").exists():
        raise ValueError("Boundary SQL evidence already exists")
    return spec


def _dependencies():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts import bootstrap_sqlite as bootstrap
    return bootstrap, bootstrap._fixture_module()


def _accounts(spec: dict, fixtures) -> list[dict]:
    return fixtures.accounts(42) + [{"id": BOUNDARY_ID, "username": spec["username"],
                                     "password": BOUNDARY_PASSWORD, "role": "member",
                                     "is_active": True}]


def _write(path: Path, value: object, bootstrap) -> None:
    bootstrap._write_exclusive(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(private: Path, evidence: Path, run_id: str, variant_id: str) -> tuple[Path, Path, Path]:
    """Build one fresh DB; return (database, fixture_dir, seed_sql).

    The caller owns both directories and must stop its service before reset.
    `private` must be empty; `evidence/seed-42-bounds.sql` must not exist.
    """
    private, evidence = Path(private), Path(evidence)
    spec = validate_target(private, evidence, run_id, variant_id)
    bootstrap, fixtures = _dependencies()
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
    fixture = private / "bounds-fixture"
    fixture.mkdir(mode=0o700)
    database = private / "accounts.sqlite"
    sql_path = evidence / "seed-42-bounds.sql"
    accounts = _accounts(spec, fixtures)
    bootstrap._new_database(database, "test", run_id)
    sql = bootstrap._seed_sql("test", run_id, accounts)
    if any(account["password"] in sql for account in accounts):
        raise ValueError("Seed SQL unexpectedly contains a clear-text password")
    bootstrap._write_exclusive(sql_path, sql)
    bootstrap._apply_sql(database, sql)
    bootstrap._assert_database(database, "test", run_id, accounts)
    oracle = {"schema_version": 1, "fixture_kind": "D42-BOUNDS", "run_id": run_id,
              "seed": 42, "boundary": spec,
              "users": [{"id": account["id"], "username": account["username"].lower(),
                         "role": account["role"], "is_active": account["is_active"],
                         "must_change_password": True} for account in accounts]}
    _write(fixture / "expected.json", oracle, bootstrap)
    _write(fixture / "manifest.json", {"schema_version": 1, "fixture_kind": "D42-BOUNDS",
        "run_id": run_id, "variant_id": variant_id, "sql_sha256": _file_hash(sql_path),
        "initial_database_sha256": _file_hash(database),
        "expected_sha256": _file_hash(fixture / "expected.json")}, bootstrap)
    _write(private / OWNER_FILE, {"owner": "tokenmeter-granular-bounds",
        "run_id": run_id, "variant_id": variant_id,
        "database": database.name, "fixture": fixture.name}, bootstrap)
    verify(database, run_id, variant_id)
    return database, fixture, sql_path


def verify(database: Path, run_id: str, variant_id: str) -> dict:
    """Check a generated, still-pristine fixture against the independent oracle."""
    database = Path(database)
    spec = variant_spec(variant_id)
    if not RUN_ID.fullmatch(run_id) or database.name != "accounts.sqlite":
        raise ValueError("Invalid boundary fixture identity")
    private = database.parent
    _parts_safe(private)
    marker = private / OWNER_FILE
    if any(path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid()
           for path in (database, marker, private / "bounds-fixture/expected.json",
                        private / "bounds-fixture/manifest.json")):
        raise ValueError("Boundary fixture ownership files are missing or unsafe")
    owner = json.loads(marker.read_text())
    if owner != {"owner": "tokenmeter-granular-bounds", "run_id": run_id,
                  "variant_id": variant_id, "database": "accounts.sqlite", "fixture": "bounds-fixture"}:
        raise ValueError("Boundary fixture owner marker differs")
    bootstrap, fixtures = _dependencies()
    accounts = _accounts(spec, fixtures)
    bootstrap._assert_database(database, "test", run_id, accounts)
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        owners = db.execute("SELECT environment, run_id FROM tokenmeter_seed_owner").fetchall()
        users = db.execute("SELECT id,username,role,is_active,must_change_password FROM users ORDER BY username").fetchall()
        sessions = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        audit = db.execute("SELECT COUNT(*) FROM audit WHERE action='account_provisioned'").fetchone()[0]
    expected_users = sorted((a["id"], a["username"].lower(), a["role"],
                             int(a["is_active"]), 1) for a in accounts)
    if owners != [("test", run_id)] or sorted(users) != expected_users or sessions != 0 or audit != 5:
        raise ValueError("Boundary fixture differs from its independent five-account oracle")
    return {"fixture_kind": "D42-BOUNDS", "run_id": run_id,
            "variant_id": variant_id, "account_count": 5, "boundary": spec}


def reset(private: Path, run_id: str, variant_id: str) -> None:
    """Remove only this generator's verified files after its service is stopped.

    SQL in the separate evidence directory is retained for run provenance.
    """
    private = Path(private)
    variant_spec(variant_id)
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid owned fixture run ID")
    _parts_safe(private)
    database = private / "accounts.sqlite"
    fixture = private / "bounds-fixture"
    marker = private / OWNER_FILE
    if set(path.name for path in private.iterdir()) != {database.name, fixture.name, marker.name}:
        raise ValueError("Boundary fixture directory contains foreign or missing entries")
    if fixture.is_symlink() or not fixture.is_dir() or set(path.name for path in fixture.iterdir()) != {"expected.json", "manifest.json"}:
        raise ValueError("Boundary fixture metadata is incomplete or foreign")
    if any(path.is_symlink() or not path.is_file() for path in
           (database, marker, fixture / "expected.json", fixture / "manifest.json")):
        raise ValueError("Boundary fixture files are linked or missing")
    if any((private / (database.name + suffix)).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("Boundary database has active or stale SQLite sidecars")
    owner = json.loads(marker.read_text())
    if owner != {"owner": "tokenmeter-granular-bounds", "run_id": run_id,
                  "variant_id": variant_id, "database": "accounts.sqlite", "fixture": "bounds-fixture"}:
        raise ValueError("Boundary fixture marker does not match")
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        owners = db.execute("SELECT environment,run_id FROM tokenmeter_seed_owner").fetchall()
    if owners != [("test", run_id)]:
        raise ValueError("Boundary database owner does not match")
    database.unlink()
    marker.unlink()
    (fixture / "expected.json").unlink()
    (fixture / "manifest.json").unlink()
    fixture.rmdir()
