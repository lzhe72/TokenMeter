from conftest import headers, login
from fixtures import CHANGED_PASSWORD, IDS, RESET_PASSWORD, expected
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from server.tokenmeter_server.database import transaction
from server.tokenmeter_server.main import create_app
from server.tokenmeter_server.models import AuthSession, LoginBucket, User
from server.tokenmeter_server.provision import provision
from concurrent.futures import ThreadPoolExecutor


def changed(client, name="alice"):
    first = login(client, name).json()["access_token"]
    response = client.post("/v1/auth/change-password", headers=headers(first), json={
        "current_password": f"TEST-ONLY-{name}-42!", "new_password": CHANGED_PASSWORD})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_health_uses_migrated_database(environment):
    client, _, _, _ = environment
    assert client.get("/v1/health").json() == {"status": "ok", "schema_version": "0001"}


def test_initial_login_change_logout_and_old_token_rejection(environment):
    client, _, _, _ = environment
    result = login(client)
    assert result.status_code == 200
    assert result.json()["user"] == expected()["users"][1]
    original = result.json()["access_token"]
    assert client.get("/v1/me", headers=headers(original)).json() == expected()["users"][1]
    assert client.get("/v1/admin/users", headers=headers(original)).status_code == 403
    token = changed(client)
    assert client.get("/v1/me", headers=headers(original)).status_code == 401
    assert client.get("/v1/me", headers=headers(token)).json()["must_change_password"] is False
    assert login(client).status_code == 401
    assert login(client, password=CHANGED_PASSWORD).status_code == 200
    assert client.post("/v1/auth/logout", headers=headers(token)).status_code == 204
    assert client.get("/v1/me", headers=headers(token)).status_code == 401


def test_admin_reset_disable_and_enable_revoke_sessions_and_are_audited(environment):
    client, _, _, _ = environment
    admin, bob = changed(client, "admin"), changed(client, "bob")
    endpoint = f"/v1/admin/users/{IDS['bob']}"
    assert client.post(endpoint + "/disable", headers=headers(admin)).json()["is_active"] is False
    assert client.get("/v1/me", headers=headers(bob)).status_code == 401
    assert login(client, "bob", CHANGED_PASSWORD).json()["error"]["code"] == "account_disabled"
    assert client.post(endpoint + "/enable", headers=headers(admin)).status_code == 200
    assert client.get("/v1/me", headers=headers(bob)).status_code == 401
    live = login(client, "bob", CHANGED_PASSWORD).json()["access_token"]
    reset = client.post(endpoint + "/reset-password", headers=headers(admin), json={"temporary_password": RESET_PASSWORD})
    assert reset.json()["must_change_password"] is True
    assert client.get("/v1/me", headers=headers(live)).status_code == 401
    assert login(client, "bob", CHANGED_PASSWORD).status_code == 401
    assert login(client, "bob", RESET_PASSWORD).json()["user"]["must_change_password"] is True
    events = client.get("/v1/admin/audit", headers=headers(admin)).json()["events"]
    actions = {event["action"] for event in events if event["target_id"] == IDS["bob"]}
    assert {"account_disabled", "account_enabled", "password_reset"} <= actions
    assert RESET_PASSWORD not in str(events) and admin not in str(events)


def test_bad_credentials_and_disabled_login_have_stable_errors(environment):
    client, _, _, _ = environment
    wrong = login(client, password="incorrect-password")
    unknown = login(client, "unknown", "incorrect-password")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["error"]["code"] == "invalid_credentials"
    disabled = login(client, "disabled")
    assert disabled.status_code == 403
    assert disabled.json()["error"]["code"] == "account_disabled"


def test_first_password_scope_is_enforced_server_side(environment):
    client, _, _, _ = environment
    token = login(client, "admin").json()["access_token"]
    result = client.get("/v1/admin/users", headers=headers(token))
    assert result.status_code == 403
    assert result.json()["error"]["code"] == "password_change_required"
    assert client.post("/v1/auth/logout", headers=headers(token)).status_code == 204


@pytest.mark.parametrize("method,path,payload", [
    ("get", "/v1/admin/users", None),
    ("get", "/v1/admin/audit", None),
    ("post", f"/v1/admin/users/{IDS['bob']}/disable", None),
    ("post", f"/v1/admin/users/{IDS['bob']}/enable", None),
    ("post", f"/v1/admin/users/{IDS['bob']}/reset-password", {"temporary_password": RESET_PASSWORD}),
])
def test_members_cannot_call_any_administrative_endpoint(environment, method, path, payload):
    client, _, _, _ = environment
    token = changed(client)
    result = client.request(method, path, headers=headers(token), **({"json": payload} if payload else {}))
    assert result.status_code == 403
    assert result.json()["error"]["code"] == "forbidden"


def test_password_change_revokes_every_old_session_but_logout_only_current(environment):
    client, _, _, _ = environment
    old_a = login(client).json()["access_token"]
    old_b = login(client).json()["access_token"]
    current = changed(client)
    for token in (old_a, old_b):
        assert client.get("/v1/me", headers=headers(token)).status_code == 401
    other = login(client, password=CHANGED_PASSWORD).json()["access_token"]
    assert client.post("/v1/auth/logout", headers=headers(current)).status_code == 204
    assert client.get("/v1/me", headers=headers(other)).status_code == 200


def test_session_survives_server_restart_and_expires_exactly_at_boundary(environment):
    client, _, now, url = environment
    token = changed(client)
    with TestClient(create_app(url, clock=lambda: now[0])) as restarted:
        assert restarted.get("/v1/me", headers=headers(token)).status_code == 200
        now[0] += 86399
        assert restarted.get("/v1/me", headers=headers(token)).status_code == 200
        now[0] += 1
        result = restarted.get("/v1/me", headers=headers(token))
        assert result.status_code == 401
        assert result.json()["error"]["code"] == "invalid_session"


def test_throttle_is_persistent_and_cannot_trust_forwarded_header(environment):
    client, _, now, url = environment
    for _ in range(5):
        assert login(client, password="incorrect-password").status_code == 401
    with TestClient(create_app(url, clock=lambda: now[0])) as restarted:
        limited = restarted.post("/v1/auth/login", headers={"X-Forwarded-For": "198.51.100.99"},
                                 json={"username": "test-alice", "password": "TEST-ONLY-alice-42!"})
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "rate_limited"
        now[0] += 300
        assert login(restarted).status_code == 200


def test_throttle_limits_distributed_usernames_from_one_source(environment):
    client, _, _, _ = environment
    for index in range(5):
        assert login(client, f"unknown{index}", "incorrect-password").status_code == 401
    assert login(client, "admin").status_code == 429


def test_secrets_are_hashed_and_validation_does_not_reflect_inputs(environment):
    client, app, _, _ = environment
    token = login(client).json()["access_token"]
    with transaction(app.state.engine) as session:
        user = session.get(User, IDS["alice"])
        stored = session.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
        assert user.password_hash.startswith("$argon2id$")
        assert user.password_hash != "TEST-ONLY-alice-42!"
        assert stored.token_hash != token and len(stored.token_hash) == 64
    secret = "SECRET-MUST-NOT-BE-ECHOED"
    result = client.post("/v1/auth/login", json={"username": {}, "password": secret, "role": "admin"})
    assert result.status_code == 422
    assert secret not in result.text
    assert set(result.json()) == {"error"}


def test_self_disable_and_last_administrator_are_protected(environment):
    client, app, _, _ = environment
    token = changed(client, "admin")
    result = client.post(f"/v1/admin/users/{IDS['admin']}/disable", headers=headers(token))
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "admin_protected"
    with transaction(app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True))) == 1


def test_unchanged_password_is_rejected_without_revoking_session(environment):
    client, _, _, _ = environment
    token = changed(client)
    result = client.post("/v1/auth/change-password", headers=headers(token), json={
        "current_password": CHANGED_PASSWORD, "new_password": CHANGED_PASSWORD})
    assert result.status_code == 409
    assert client.get("/v1/me", headers=headers(token)).status_code == 200


def test_role_injection_and_open_registration_are_rejected(environment):
    client, _, _, _ = environment
    assert client.post("/v1/auth/login", json={"username": "test-alice", "password": "TEST-ONLY-alice-42!", "role": "admin"}).status_code == 422
    assert client.post("/v1/auth/register", json={}).status_code == 404


def test_missing_bearer_and_nonbearer_credentials_rejected(environment):
    client, _, _, _ = environment
    for auth in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer junk"}):
        response = client.get("/v1/me", headers=auth)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_session"


def test_credential_version_rejects_a_concurrently_created_old_session(environment):
    client, app, _, _ = environment
    token = changed(client)
    with transaction(app.state.engine, write=True) as session:
        # Simulate a reset committing while a previously issued session survives.
        user = session.get(User, IDS["alice"])
        user.credential_version += 1
    assert client.get("/v1/me", headers=headers(token)).status_code == 401


def test_two_administrators_cannot_concurrently_disable_each_other(environment):
    client, app, _, url = environment
    second_id = "00000000-0000-4000-8000-000000000005"
    provision(url, [{"id": second_id, "username": "test-admin2", "password": "TEST-ONLY-admin2-42!",
                     "role": "admin", "is_active": True}])
    first, second = changed(client, "admin"), changed(client, "admin2")
    with ThreadPoolExecutor(max_workers=2) as pool:
        first_action = pool.submit(client.post, f"/v1/admin/users/{second_id}/disable", headers=headers(first))
        second_action = pool.submit(client.post, f"/v1/admin/users/{IDS['admin']}/disable", headers=headers(second))
        assert sorted([first_action.result().status_code, second_action.result().status_code]) == [200, 401]
    with transaction(app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True))) == 1


def test_member_identity_is_not_selected_by_client_query(environment):
    client, _, _, _ = environment
    token = changed(client)
    result = client.get("/v1/me", params={"id": IDS["admin"], "role": "admin"}, headers=headers(token))
    assert result.json()["id"] == IDS["alice"]
    assert result.json()["role"] == "member"


def test_wrong_current_password_preserves_existing_session(environment):
    client, _, _, _ = environment
    token = changed(client)
    result = client.post("/v1/auth/change-password", headers=headers(token), json={
        "current_password": "WRONG-CURRENT-PASSWORD", "new_password": RESET_PASSWORD})
    assert result.status_code == 401
    assert client.get("/v1/me", headers=headers(token)).status_code == 200
