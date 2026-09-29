import pytest
from fastapi.testclient import TestClient

from server.tokenmeter_server.main import create_app
from server.tokenmeter_server.migrations import migrate
from server.tokenmeter_server.provision import provision
from fixtures import accounts, FIXED_CLOCK


@pytest.fixture
def environment(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'accounts.sqlite'}"
    migrate(database_url)
    provision(database_url, accounts())
    now = [FIXED_CLOCK]
    app = create_app(database_url, clock=lambda: now[0])
    with TestClient(app) as client:
        yield client, app, now, database_url


def login(client, name="alice", password=None):
    return client.post("/v1/auth/login", json={"username": f"test-{name}", "password": password or f"TEST-ONLY-{name}-42!"})


def headers(token):
    return {"Authorization": f"Bearer {token}"}
