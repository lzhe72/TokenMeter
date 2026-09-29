import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text

from server.tokenmeter_server.database import make_engine, transaction
from server.tokenmeter_server.main import create_app
from server.tokenmeter_server.migrations import assert_schema, migrate
from server.tokenmeter_server.models import User
from server.tokenmeter_server.provision import provision
from server.tokenmeter_server.cli import validate_test_database
from fixtures import accounts, generate, reset


def test_migration_repeat_and_sqlite_backup_restore_keep_accounts(tmp_path):
    original = tmp_path / "original.sqlite"
    url = f"sqlite:///{original}"
    migrate(url)
    assert provision(url, accounts()) == 4
    migrate(url)
    backup = tmp_path / "backup.sqlite"
    with sqlite3.connect(original) as source, sqlite3.connect(backup) as target:
        source.backup(target)
    restored = make_engine(f"sqlite:///{backup}")
    try:
        assert_schema(restored)
        assert {"users", "sessions", "audit", "login_buckets", "alembic_version"} == set(inspect(restored).get_table_names())
        with transaction(restored) as session:
            assert list(session.scalars(select(User.username).order_by(User.username))) == ["test-admin", "test-alice", "test-bob", "test-disabled"]
    finally:
        restored.dispose()


def test_schema_mismatch_and_uninitialized_database_refuse_start(tmp_path):
    url = f"sqlite:///{tmp_path / 'empty.sqlite'}"
    with pytest.raises(Exception):
        with TestClient(create_app(url)):
            pass
    migrate(url)
    engine = make_engine(url)
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num='future'"))
    engine.dispose()
    with pytest.raises(RuntimeError, match="schema"):
        with TestClient(create_app(url)):
            pass


def test_provision_needs_explicit_accounts_and_never_overwrites(environment):
    _, app, _, url = environment
    with pytest.raises(ValueError, match="already exists"):
        provision(url, accounts())
    with pytest.raises(ValueError):
        provision(url, [])
    with transaction(app.state.engine) as session:
        assert len(list(session.scalars(select(User)))) == 4


def test_provision_requires_active_admin_and_is_atomic(tmp_path):
    url = f"sqlite:///{tmp_path / 'accounts.sqlite'}"
    migrate(url)
    with pytest.raises(ValueError, match="administrator"):
        provision(url, accounts()[1:])
    engine = make_engine(url)
    try:
        with transaction(engine) as session:
            assert list(session.scalars(select(User))) == []
        values = accounts()
        values[-1]["id"] = values[0]["id"]
        with pytest.raises(ValueError):
            provision(url, values)
        with transaction(engine) as session:
            assert list(session.scalars(select(User))) == []
    finally:
        engine.dispose()


def test_sqlite_foreign_keys_and_transactional_ddl_are_enabled(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'tx.sqlite'}")
    try:
        with pytest.raises(RuntimeError):
            with engine.begin() as connection:
                assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
                connection.execute(text("CREATE TABLE interrupted (id INTEGER)"))
                raise RuntimeError("interrupt migration")
        assert "interrupted" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_fixture_is_reproducible_isolated_and_refuses_foreign_files(tmp_path):
    first = generate("one", workspace=tmp_path)
    second = generate("two", workspace=tmp_path)
    assert (first / "users.json").read_bytes() == (second / "users.json").read_bytes()
    assert (first / "expected.json").read_bytes() == (second / "expected.json").read_bytes()
    with pytest.raises(ValueError):
        generate("one", workspace=tmp_path)
    (first / "foreign.txt").write_text("keep")
    with pytest.raises(ValueError):
        reset("one", workspace=tmp_path)
    assert (first / "foreign.txt").read_text() == "keep"
    reset("two", workspace=tmp_path)
    assert not second.exists()
    with pytest.raises(ValueError):
        generate("../outside", workspace=tmp_path)


def test_fixture_symlinks_cannot_escape_owned_directory(tmp_path):
    local = tmp_path / ".local"
    local.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (local / "account-fixtures").symlink_to(outside)
    with pytest.raises(ValueError):
        generate("symlink", workspace=tmp_path)
    assert list(outside.iterdir()) == []


def test_cli_does_not_echo_invalid_password_fields(tmp_path):
    source = tmp_path / "accounts.json"
    secret = "NEVER-PRINT-SECRET"
    source.write_text(json.dumps({"users": [{"password": secret}]}))
    result = subprocess.run([sys.executable, "-m", "server.tokenmeter_server.cli", "provision",
                             "--database-url", f"sqlite:///{tmp_path / 'unused.sqlite'}", "--accounts", str(source)],
                            text=True, capture_output=True)
    assert result.returncode == 1
    assert secret not in result.stdout + result.stderr
    assert json.loads(result.stdout)["error"]["code"] == "operation_failed"


def test_cli_refuses_synthetic_accounts_in_unmarked_database(tmp_path):
    fixture = generate("unsafe", workspace=tmp_path)
    url = f"sqlite:///{tmp_path / 'unmarked.sqlite'}"
    migrate(url)
    result = subprocess.run([sys.executable, "-m", "server.tokenmeter_server.cli", "provision",
                            "--database-url", url, "--accounts", str(fixture / "users.json")], text=True, capture_output=True)
    assert result.returncode != 0
    engine = make_engine(url)
    try:
        with transaction(engine) as session:
            assert list(session.scalars(select(User))) == []
    finally:
        engine.dispose()


def test_test_import_marker_must_bind_exact_run_and_database(tmp_path):
    marker = tmp_path / ".tokenmeter-test-database.json"
    marker.write_text(json.dumps({"owner": "tokenmeter-test-database", "run_id": "isolated", "database": "test.sqlite"}))
    validate_test_database(f"sqlite:///{tmp_path / 'test.sqlite'}", "isolated")
    for url, run in [(f"sqlite:///{tmp_path / 'other.sqlite'}", "isolated"),
                     (f"sqlite:///{tmp_path / 'test.sqlite'}", "wrong"),
                     ("mysql://localhost/test", "isolated"), ("sqlite:///relative.sqlite", "isolated")]:
        with pytest.raises(ValueError):
            validate_test_database(url, run)
    (tmp_path / "test.sqlite").symlink_to(tmp_path / "real.sqlite")
    with pytest.raises(ValueError):
        validate_test_database(f"sqlite:///{tmp_path / 'test.sqlite'}", "isolated")
