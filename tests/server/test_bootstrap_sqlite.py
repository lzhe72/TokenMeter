"""The visible SQLite files must remain isolated and usable by the real API."""

import json
import sqlite3

from fastapi.testclient import TestClient
import pytest

from scripts import bootstrap_sqlite
from scripts.bootstrap_sqlite import (
    _apply_sql,
    initialize_production,
    initialize_test,
    inspect,
    repair_test_material,
    rebuild_test,
)
from server.tokenmeter_server.main import create_app


def _users(path):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT username, role, is_active, must_change_password FROM users ORDER BY username"
        ).fetchall()


def test_bootstrap_generates_sql_isolates_accounts_and_real_api_login(tmp_path):
    test = initialize_test(tmp_path, "regression-001")
    production = initialize_production(tmp_path)
    assert test["accounts"] == 4
    assert production["accounts"] == 1
    assert _users(tmp_path / "database/test/test.db") == [
        ("test-admin", "admin", 1, 1),
        ("test-alice", "member", 1, 1),
        ("test-bob", "member", 1, 1),
        ("test-disabled", "member", 0, 1),
    ]
    assert _users(tmp_path / "database/production/production.db") == [("admin", "admin", 1, 1)]
    assert len(inspect(tmp_path)) == 2
    with sqlite3.connect(tmp_path / "database/test/test.db") as connection:
        assert connection.execute("SELECT DISTINCT occurred_at FROM audit").fetchall() == [(1790654400,)]
    for environment, password in (("test", "TEST-ONLY-admin-42!"), ("production", "123456")):
        sql = (tmp_path / f"database/{environment}/seed.sql").read_text()
        assert "$argon2" in sql
        assert password not in sql
        assert "_tokenmeter_seed_guard" in sql

    # API actions write sessions/audit, so authenticate against an SQLite backup
    # instead of contaminating the user's production file.
    original = tmp_path / "database/production/production.db"
    copy = tmp_path / "production-api-check.db"
    with sqlite3.connect(original) as source, sqlite3.connect(copy) as target:
        source.backup(target)
    with TestClient(create_app("sqlite:///" + str(copy))) as client:
        login = client.post("/v1/auth/login", json={"username": "admin", "password": "123456"})
        assert login.status_code == 200
        data = login.json()
        assert data["user"]["must_change_password"] is True
        header = {"Authorization": "Bearer " + data["access_token"]}
        assert client.get("/v1/admin/users", headers=header).status_code == 403
        changed = client.post("/v1/auth/change-password", headers=header,
                              json={"current_password": "123456", "new_password": "NewProductionPassword-2026!"})
        assert changed.status_code == 200
        assert changed.json()["user"]["must_change_password"] is False
    with sqlite3.connect(original) as connection:
        assert connection.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM audit").fetchone()[0] == 1


def test_seed_sql_refuses_other_environment_and_nonempty_database(tmp_path):
    initialize_test(tmp_path, "regression-002")
    initialize_production(tmp_path)
    test = tmp_path / "database/test/test.db"
    production = tmp_path / "database/production/production.db"
    test_sql = (tmp_path / "database/test/seed.sql").read_text()
    production_sql = (tmp_path / "database/production/seed.sql").read_text()
    for target, sql in ((test, production_sql), (production, test_sql),
                        (test, test_sql), (production, production_sql)):
        with pytest.raises(sqlite3.IntegrityError):
            _apply_sql(target, sql)
    assert len(_users(test)) == 4
    assert _users(production) == [("admin", "admin", 1, 1)]
    # Remove the initial admin only in this isolated test DB. A cross-environment
    # SQL file must still fail even when the target users table is empty.
    with sqlite3.connect(production) as connection:
        connection.execute("DELETE FROM audit")
        connection.execute("DELETE FROM users")
    with pytest.raises(sqlite3.IntegrityError):
        _apply_sql(production, test_sql)
    assert _users(production) == []
    with pytest.raises(ValueError, match="never overwrites"):
        initialize_production(tmp_path)


def test_rebuild_only_owned_test_database_and_preserves_previous_run(tmp_path):
    initialize_test(tmp_path, "old-run")
    initialize_production(tmp_path)
    with pytest.raises(ValueError, match="ownership"):
        rebuild_test(tmp_path, "wrong-run", "next-run")
    production = tmp_path / "database/production/production.db"
    with sqlite3.connect(production) as connection:
        old_hash = connection.execute("SELECT password_hash FROM users").fetchone()[0]
    result = rebuild_test(tmp_path, "old-run", "next-run")
    assert result["accounts"] == 4
    archive = tmp_path / ".local/sqlite-db-backups/old-run"
    assert result["backup"] == str(archive)
    assert {item.name for item in archive.iterdir()} == {
        "test.db", "seed.sql", ".tokenmeter-test-database.json"
    }
    marker = json.loads((tmp_path / "database/test/.tokenmeter-test-database.json").read_text())
    assert marker["run_id"] == "next-run"
    assert _users(tmp_path / "database/test/test.db") == _users(archive / "test.db")
    with sqlite3.connect(production) as connection:
        assert connection.execute("SELECT password_hash FROM users").fetchone()[0] == old_hash
    (tmp_path / ".local/sqlite-db-backups/next-run").mkdir()
    with pytest.raises(ValueError, match="already exists"):
        rebuild_test(tmp_path, "next-run", "old-run")


def test_read_only_health_allows_production_password_change_and_new_member(tmp_path):
    initialize_production(tmp_path)
    path = tmp_path / "database/production/production.db"
    with TestClient(create_app("sqlite:///" + str(path))) as client:
        login = client.post("/v1/auth/login", json={"username": "admin", "password": "123456"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        changed = client.post("/v1/auth/change-password",
                              headers={"Authorization": "Bearer " + token},
                              json={"current_password": "123456", "new_password": "ChangedAdminPassword-2026!"})
        assert changed.status_code == 200
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO users (id, username, password_hash, role, is_active, must_change_password, credential_version) "
                           "SELECT '00000000-0000-4000-8000-000000000006', 'member-one', password_hash, 'member', 1, 0, 1 "
                           "FROM users WHERE username='admin'")
    assert inspect(tmp_path)[0]["accounts"] == 2
    # A newly started service app must retain the changed password and member.
    with TestClient(create_app("sqlite:///" + str(path))) as restarted:
        assert restarted.post("/v1/auth/login", json={
            "username": "admin", "password": "123456"
        }).status_code == 401
        login = restarted.post("/v1/auth/login", json={
            "username": "admin", "password": "ChangedAdminPassword-2026!"
        })
        assert login.status_code == 200
        assert login.json()["user"]["must_change_password"] is False
        accounts = restarted.get("/v1/admin/users", headers={
            "Authorization": "Bearer " + login.json()["access_token"]
        })
        assert accounts.status_code == 200
        assert {user["username"] for user in accounts.json()["users"]} == {"admin", "member-one"}
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE users SET username='test-leak' WHERE username='member-one'")
    with pytest.raises(ValueError, match="test account"):
        inspect(tmp_path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE users SET username='member-one' WHERE username='test-leak'")
        connection.execute("UPDATE users SET is_active=0 WHERE username='admin'")
    with pytest.raises(ValueError, match="no active administrator"):
        inspect(tmp_path)


def test_interrupted_rebuild_can_recover_marker_and_sql(tmp_path, monkeypatch):
    initialize_test(tmp_path, "before-crash")
    original_replace_text = bootstrap_sqlite._replace_text

    def interrupt_after_db_swap(path, content):
        if path.name == ".tokenmeter-test-database.json":
            raise OSError("simulated interruption after database replacement")
        return original_replace_text(path, content)

    monkeypatch.setattr(bootstrap_sqlite, "_replace_text", interrupt_after_db_swap)
    with pytest.raises(OSError, match="simulated interruption"):
        rebuild_test(tmp_path, "before-crash", "after-crash")
    monkeypatch.setattr(bootstrap_sqlite, "_replace_text", original_replace_text)
    with pytest.raises(ValueError, match="owner does not match"):
        inspect(tmp_path)
    repaired = repair_test_material(tmp_path)
    assert repaired["run_id"] == "after-crash"
    assert inspect(tmp_path)[0]["accounts"] == 4


def test_failed_initialization_leaves_no_partial_database_or_seed(tmp_path, monkeypatch):
    original_apply = bootstrap_sqlite._apply_sql

    def fail_seed(_path, _sql):
        raise RuntimeError("simulated seed failure")

    monkeypatch.setattr(bootstrap_sqlite, "_apply_sql", fail_seed)
    with pytest.raises(RuntimeError, match="simulated seed failure"):
        initialize_production(tmp_path)
    assert list((tmp_path / "database/production").iterdir()) == []
    monkeypatch.setattr(bootstrap_sqlite, "_apply_sql", original_apply)
    assert initialize_production(tmp_path)["accounts"] == 1

    original_link = bootstrap_sqlite.os.link

    def fail_database_link(source, target):
        if str(target).endswith("/database/test/test.db"):
            raise OSError("simulated publication failure")
        return original_link(source, target)

    monkeypatch.setattr(bootstrap_sqlite.os, "link", fail_database_link)
    with pytest.raises(OSError, match="simulated publication failure"):
        initialize_test(tmp_path, "failed-publication")
    assert list((tmp_path / "database/test").iterdir()) == []
    monkeypatch.setattr(bootstrap_sqlite.os, "link", original_link)
    assert initialize_test(tmp_path, "successful-publication")["accounts"] == 4


def test_symlink_directory_is_rejected_before_creating_database(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "database").mkdir()
    (tmp_path / "database/test").symlink_to(outside)
    with pytest.raises(ValueError, match="symbolic-link"):
        initialize_test(tmp_path, "isolated")
    assert list(outside.iterdir()) == []


def test_verify_requires_both_database_files(tmp_path, monkeypatch):
    initialize_test(tmp_path, "regression-only")
    with pytest.raises(ValueError, match="Both test and production"):
        inspect(tmp_path, require_both=True)
    monkeypatch.setattr(bootstrap_sqlite, "SOURCE_ROOT", tmp_path)
    assert bootstrap_sqlite.main(["verify"]) == 1
    initialize_production(tmp_path)
    assert len(inspect(tmp_path, require_both=True)) == 2


def test_production_preview_rejects_non_loopback_host(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap_sqlite, "SOURCE_ROOT", tmp_path)
    assert bootstrap_sqlite.main(["serve-production", "--host", "0.0.0.0"]) == 1
    assert list(tmp_path.iterdir()) == []
