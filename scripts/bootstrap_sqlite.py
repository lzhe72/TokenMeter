"""Create the two local SQLite databases and executable, one-time seed SQL.

The generated SQL contains salted password hashes, never plaintext passwords.
Neither database is replaced by initialization or by starting the service.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import sys
import tempfile
import time
from uuid import NAMESPACE_URL, uuid5


SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT))

from server.tokenmeter_server.migrations import migrate  # noqa: E402
from server.tokenmeter_server.security import hash_password, verify_password  # noqa: E402


RUN_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
TEST_DB = Path("database/test/test.db")
PRODUCTION_DB = Path("database/production/production.db")
TEST_MARKER = ".tokenmeter-test-database.json"
OWNER_TABLE = "tokenmeter_seed_owner"
PRODUCTION_INITIAL_PASSWORD = "123456"
PRODUCTION_USER_ID = "00000000-0000-4000-8000-000000000005"


def _fixture_accounts():
    return _fixture_module().accounts(42)


def _fixture_module():
    spec = importlib.util.spec_from_file_location(
        "tokenmeter_account_fixtures", SOURCE_ROOT / "tests/server/fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _path(root: Path, environment: str) -> Path:
    if not root.is_absolute():
        raise ValueError("Repository path must be absolute")
    relative = TEST_DB if environment == "test" else PRODUCTION_DB
    target = root / relative
    for item in (root, *root.parents, root / "database", target.parent, target):
        if item.is_symlink():
            raise ValueError("Refusing a symbolic-link database path")
    if not root.is_dir():
        raise ValueError("Repository path does not exist")
    return target


def _sql_string(value: str) -> str:
    if "\x00" in value:
        raise ValueError("NUL is not valid in seed input")
    return "'" + value.replace("'", "''") + "'"


def _seed_sql(environment: str, run_id: str, accounts: list[dict]) -> str:
    # The guard remains empty if a GUI/CLI keeps executing after an error.
    # Every INSERT reads it, so an unmarked or nonempty DB receives no rows.
    escaped_environment = _sql_string(environment)
    escaped_run = _sql_string(run_id)
    audit_time = _fixture_module().FIXED_CLOCK if environment == "test" else int(time.time())
    lines = [
        "-- Generated TokenMeter SQL. Execute only against its matching empty database.",
        "-- Passwords are salted Argon2 hashes; regenerate this file for a new initialization.",
        "PRAGMA foreign_keys = ON;",
        "BEGIN IMMEDIATE;",
        "CREATE TEMP TABLE _tokenmeter_seed_guard (allowed INTEGER NOT NULL CHECK (allowed = 1));",
        "INSERT INTO _tokenmeter_seed_guard (allowed)",
        "SELECT CASE WHEN (SELECT count(*) FROM users) = 0",
        f"  AND (SELECT count(*) FROM {OWNER_TABLE} WHERE environment = {escaped_environment}",
        f"       AND run_id = {escaped_run}) = 1 THEN 1 ELSE 0 END;",
    ]
    for account in accounts:
        user_id = str(account["id"])
        hash_value = account.get("password_hash") or hash_password(account["password"])
        values = [user_id, account["username"].lower(), hash_value, account["role"]]
        values_sql = ", ".join(_sql_string(value) for value in values)
        active = 1 if account["is_active"] else 0
        lines += [
            "INSERT INTO users (id, username, password_hash, role, is_active, must_change_password, credential_version)",
            f"SELECT {values_sql}, {active}, 1, 1 FROM _tokenmeter_seed_guard WHERE allowed = 1;",
        ]
        audit_id = str(uuid5(NAMESPACE_URL, f"tokenmeter:{environment}:{run_id}:{user_id}:provision"))
        lines += [
            "INSERT INTO audit (id, actor_id, target_id, action, occurred_at)",
            f"SELECT {_sql_string(audit_id)}, NULL, {_sql_string(user_id)}, 'account_provisioned', {audit_time}",
            "FROM _tokenmeter_seed_guard WHERE allowed = 1;",
        ]
    lines += ["DROP TABLE _tokenmeter_seed_guard;", "COMMIT;", ""]
    return "\n".join(lines)


def _write_exclusive(path: Path, content: str) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(content)


def _new_database(path: Path, environment: str, run_id: str) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    os.close(descriptor)
    migrate("sqlite:///" + str(path))
    with sqlite3.connect(path) as connection:
        connection.execute(f"CREATE TABLE {OWNER_TABLE} (environment TEXT NOT NULL, run_id TEXT NOT NULL, PRIMARY KEY (environment, run_id))")
        connection.execute(f"INSERT INTO {OWNER_TABLE} (environment, run_id) VALUES (?, ?)", (environment, run_id))


def _apply_sql(path: Path, sql: str) -> None:
    with sqlite3.connect(path) as connection:
        try:
            connection.executescript(sql)
        except Exception:
            connection.rollback()
            raise


def _assert_database(path: Path, environment: str, run_id: str, accounts: list[dict]) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Database is missing or is a symbolic link")
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        owner = connection.execute(f"SELECT environment, run_id FROM {OWNER_TABLE}").fetchall()
        rows = connection.execute("SELECT id, username, password_hash, role, is_active, must_change_password, credential_version FROM users ORDER BY username").fetchall()
        audit_count = connection.execute("SELECT count(*) FROM audit WHERE action='account_provisioned'").fetchone()[0]
    expected = sorted(accounts, key=lambda item: item["username"])
    if version != ("0001",) or owner != [(environment, run_id)] or len(rows) != len(expected) or audit_count != len(expected):
        raise ValueError("Database schema, ownership or account count is incorrect")
    for row, account in zip(rows, expected):
        if (row[0], row[1], row[3], row[4], row[5], row[6]) != (
            account["id"], account["username"].lower(), account["role"],
            int(account["is_active"]), 1, 1,
        ) or not row[2].startswith("$argon2") or not verify_password(account["password"], row[2]):
            raise ValueError("Database account data does not match the seed")
    return {"environment": environment, "database": str(path), "schema_version": version[0], "accounts": len(rows)}


def _prepare_directory(root: Path, environment: str) -> Path:
    target = _path(root, environment)
    target.parent.mkdir(parents=True, exist_ok=True)
    _path(root, environment)  # Recheck after creation.
    return target


def _publish_new_files(files: list[tuple[Path, Path]], database_target: Path) -> None:
    """Hard-link prepared files without overwriting; install the DB last.

    If publication fails before the DB link, remove only links to our staged
    inodes. A successful DB link means all companion files are already ready.
    """
    published = []
    try:
        for staged, target in files:
            os.link(staged, target)
            published.append((staged, target))
    except Exception:
        if not any(target == database_target for _, target in published):
            for staged, target in reversed(published):
                if target.is_file() and not target.is_symlink() and os.stat(staged).st_ino == os.stat(target).st_ino:
                    target.unlink()
        raise


def initialize_test(root: Path, run_id: str) -> dict:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid isolated test run ID")
    target = _prepare_directory(root, "test")
    marker = target.parent / TEST_MARKER
    seed = target.parent / "seed.sql"
    for item in (target, marker, seed):
        if item.exists() or item.is_symlink():
            raise ValueError("Test database material already exists; use rebuild-test for an owned test database")
    accounts = _fixture_accounts()
    with tempfile.TemporaryDirectory(prefix=".bootstrap-", dir=target.parent) as staging_dir:
        staging = Path(staging_dir)
        staged_db = staging / target.name
        staged_marker = staging / marker.name
        staged_seed = staging / seed.name
        _new_database(staged_db, "test", run_id)
        _write_exclusive(staged_marker, json.dumps({
            "owner": "tokenmeter-test-database", "run_id": run_id, "database": target.name}) + "\n")
        sql = _seed_sql("test", run_id, accounts)
        _write_exclusive(staged_seed, sql)
        _apply_sql(staged_db, sql)
        _assert_database(staged_db, "test", run_id, accounts)
        _path(root, "test")  # Recheck directory links before publication.
        _publish_new_files([(staged_marker, marker), (staged_seed, seed), (staged_db, target)], target)
    return _assert_database(target, "test", run_id, accounts)


def initialize_production(root: Path) -> dict:
    target = _prepare_directory(root, "production")
    seed = target.parent / "seed.sql"
    for item in (target, seed):
        if item.exists() or item.is_symlink():
            raise ValueError("Production database already exists; initialization never overwrites it")
    account = {"id": PRODUCTION_USER_ID, "username": "admin", "password": PRODUCTION_INITIAL_PASSWORD,
               "role": "admin", "is_active": True}
    with tempfile.TemporaryDirectory(prefix=".bootstrap-", dir=target.parent) as staging_dir:
        staging = Path(staging_dir)
        staged_db = staging / target.name
        staged_seed = staging / seed.name
        _new_database(staged_db, "production", "production-init")
        sql = _seed_sql("production", "production-init", [account])
        _write_exclusive(staged_seed, sql)
        _apply_sql(staged_db, sql)
        _assert_database(staged_db, "production", "production-init", [account])
        _path(root, "production")
        _publish_new_files([(staged_seed, seed), (staged_db, target)], target)
    return _assert_database(target, "production", "production-init", [account])


def _validate_owned_test(root: Path, current_run_id: str) -> Path:
    target = _path(root, "test")
    marker = target.parent / TEST_MARKER
    seed = target.parent / "seed.sql"
    if not RUN_ID.fullmatch(current_run_id) or any(item.is_symlink() or not item.is_file() for item in (target, marker, seed)):
        raise ValueError("Test database ownership material is missing or unsafe")
    expected = {"owner": "tokenmeter-test-database", "run_id": current_run_id, "database": target.name}
    if json.loads(marker.read_text()) != expected:
        raise ValueError("Test database ownership marker does not match")
    with sqlite3.connect(f"file:{target}?mode=ro", uri=True) as connection:
        owner = connection.execute(f"SELECT environment, run_id FROM {OWNER_TABLE}").fetchall()
    if owner != [("test", current_run_id)]:
        raise ValueError("Test database internal owner does not match")
    if any((target.parent / (target.name + suffix)).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("Test database has active or stale SQLite sidecar files")
    return target


def _stored_owner(path: Path) -> tuple[str, str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Database is missing or unsafe")
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        owner = connection.execute(f"SELECT environment, run_id FROM {OWNER_TABLE}").fetchall()
    if len(owner) != 1:
        raise ValueError("Database has no unique environment owner")
    return owner[0]


def _replace_text(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + ".tmp-" + secrets.token_hex(6))
    _write_exclusive(temporary, content)
    os.replace(temporary, path)


def repair_test_material(root: Path) -> dict:
    """Recover marker/SQL after an interrupted test DB swap, using DB ownership."""
    target = _path(root, "test")
    environment, run_id = _stored_owner(target)
    if environment != "test" or not RUN_ID.fullmatch(run_id):
        raise ValueError("Database is not owned by a valid test run")
    marker = target.parent / TEST_MARKER
    seed = target.parent / "seed.sql"
    for item in (marker, seed):
        if item.is_symlink() or (item.exists() and not item.is_file()):
            raise ValueError("Cannot repair unsafe test material")
    if any((target.parent / (target.name + suffix)).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("Test database has active or stale SQLite sidecar files")
    # Check that this is the expected isolated fixture before regenerating metadata.
    accounts = _fixture_accounts()
    _assert_database(target, "test", run_id, accounts)
    with sqlite3.connect(f"file:{target}?mode=ro", uri=True) as connection:
        hashes = dict(connection.execute("SELECT username, password_hash FROM users").fetchall())
    for account in accounts:
        account["password_hash"] = hashes[account["username"]]
    expected_marker = json.dumps({
        "owner": "tokenmeter-test-database", "run_id": run_id, "database": target.name}) + "\n"
    _replace_text(marker, expected_marker)
    _replace_text(seed, _seed_sql("test", run_id, accounts))
    return {"database": str(target), "run_id": run_id, "material_repaired": True}


def rebuild_test(root: Path, current_run_id: str, new_run_id: str) -> dict:
    """Back up an owned test run, then atomically swap its database file."""
    if not RUN_ID.fullmatch(new_run_id) or new_run_id == current_run_id:
        raise ValueError("Rebuild requires a different valid run ID")
    target = _validate_owned_test(root, current_run_id)
    seed = target.parent / "seed.sql"
    marker = target.parent / TEST_MARKER
    archive = root / ".local/sqlite-db-backups" / current_run_id
    if archive.exists() or archive.is_symlink():
        raise ValueError("Backup target already exists")
    if (root / ".local").is_symlink():
        raise ValueError("Backup root is a symbolic link")
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.parent.is_symlink():
        raise ValueError("Backup parent is a symbolic link")
    suffix = secrets.token_hex(6)
    replacement = target.parent / f"test.db.tmp-{suffix}"
    accounts = _fixture_accounts()
    _new_database(replacement, "test", new_run_id)
    sql = _seed_sql("test", new_run_id, accounts)
    _apply_sql(replacement, sql)
    _assert_database(replacement, "test", new_run_id, accounts)
    archive.mkdir(mode=0o700)
    with sqlite3.connect(target) as source, sqlite3.connect(archive / target.name) as backup:
        source.backup(backup)
    os.chmod(archive / target.name, 0o600)
    for old in (seed, marker):
        shutil.copy2(old, archive / old.name)
    # Only the DB file is swapped. If interruption occurs before the two small
    # metadata files are replaced, repair-test-material derives their owner
    # from the new DB and regenerates the SQL.
    os.replace(replacement, target)
    _replace_text(marker, json.dumps({
        "owner": "tokenmeter-test-database", "run_id": new_run_id, "database": target.name}) + "\n")
    _replace_text(seed, sql)
    result = _assert_database(target, "test", new_run_id, accounts)
    result["backup"] = str(archive)
    return result


def inspect(root: Path, *, require_both: bool = False) -> list[dict]:
    result = []
    production = _path(root, "production")
    if production.is_file():
        result.append(_daily_status(production, "production", "production-init"))
    test = _path(root, "test")
    if test.is_file():
        marker = test.parent / TEST_MARKER
        if marker.is_symlink() or not marker.is_file():
            raise ValueError("Test database marker is missing or unsafe")
        run_id = json.loads(marker.read_text())["run_id"]
        expected_marker = {"owner": "tokenmeter-test-database", "run_id": run_id, "database": test.name}
        if json.loads(marker.read_text()) != expected_marker:
            raise ValueError("Test database marker does not match")
        result.append(_daily_status(test, "test", run_id))
    if require_both and len(result) != 2:
        raise ValueError("Both test and production SQLite databases are required for verification")
    if not result:
        raise ValueError("No initialized SQLite databases were found")
    return result


def _daily_status(path: Path, environment: str, run_id: str) -> dict:
    if _stored_owner(path) != (environment, run_id):
        raise ValueError("Database environment owner does not match")
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        rows = connection.execute("SELECT username, role, is_active, password_hash FROM users").fetchall()
    if version != ("0001",):
        raise ValueError("Database schema version does not match")
    if not any(role == "admin" and active for _, role, active, _ in rows):
        raise ValueError("Database has no active administrator")
    if any(not hashed.startswith("$argon2") for _, _, _, hashed in rows):
        raise ValueError("Database contains a non-Argon2 password hash")
    if environment == "production" and any(username.startswith("test-") for username, *_ in rows):
        raise ValueError("Production database contains a test account")
    if environment == "test" and any(not username.startswith("test-") for username, *_ in rows):
        raise ValueError("Test database contains a non-fixture account")
    return {"environment": environment, "database": str(path), "schema_version": version[0], "accounts": len(rows)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    test = commands.add_parser("init-test", help="Create test.db and its executable seed.sql")
    test.add_argument("--run-id", required=True)
    commands.add_parser("init-production", help="Create production.db and its executable seed.sql once")
    rebuild = commands.add_parser("rebuild-test", help="Archive and rebuild only an owned test.db")
    rebuild.add_argument("--current-run-id", required=True)
    rebuild.add_argument("--run-id", required=True)
    commands.add_parser("verify", help="Read-only schema/account/ownership verification")
    commands.add_parser("repair-test-material", help="Repair test marker/SQL after interrupted rebuild")
    service = commands.add_parser("serve-production", help="Run API against production.db only")
    service.add_argument("--host", default="127.0.0.1")
    service.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        if args.command == "init-test":
            result = initialize_test(SOURCE_ROOT, args.run_id)
        elif args.command == "init-production":
            result = initialize_production(SOURCE_ROOT)
        elif args.command == "rebuild-test":
            result = rebuild_test(SOURCE_ROOT, args.current_run_id, args.run_id)
        elif args.command == "verify":
            result = inspect(SOURCE_ROOT, require_both=True)
        elif args.command == "repair-test-material":
            result = repair_test_material(SOURCE_ROOT)
        else:
            if args.host not in ("127.0.0.1", "::1"):
                raise ValueError("Production preview service must bind only to a loopback address")
            target = _path(SOURCE_ROOT, "production")
            if not target.is_file() or target.is_symlink():
                raise ValueError("Production database is missing; run init-production first")
            _daily_status(target, "production", "production-init")
            # Existing data is never migrated or seeded by service startup.
            import uvicorn
            os.environ["TOKENMETER_DATABASE_URL"] = "sqlite:///" + str(target)
            uvicorn.run("server.tokenmeter_server.main:app", host=args.host, port=args.port,
                        proxy_headers=False)
            return 0
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as error:
        # Database/SQL exceptions may contain hashes; keep output bounded.
        print(json.dumps({"error": type(error).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
