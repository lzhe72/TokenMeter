"""A real TCP smoke test in addition to in-process API integration tests."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx

from fixtures import generate


def test_real_uvicorn_cli_migration_provision_and_authentication(tmp_path):
    fixture = generate("network", workspace=tmp_path)
    url = f"sqlite:///{tmp_path / 'server.sqlite'}"
    (tmp_path / ".tokenmeter-test-database.json").write_text(json.dumps({
        "owner": "tokenmeter-test-database", "run_id": "network", "database": "server.sqlite"}))
    base = [sys.executable, "-m", "server.tokenmeter_server.cli"]
    for args in (["migrate", "--database-url", url],
                 ["provision", "--database-url", url, "--accounts", str(fixture / "users.json"), "--test-run-id", "network"]):
        result = subprocess.run(base + args, text=True, capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    env = dict(os.environ, TOKENMETER_DATABASE_URL=url)
    log = (tmp_path / "uvicorn.log").open("w+")
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "server.tokenmeter_server.main:app",
                                "--fd", str(listener.fileno()), "--no-proxy-headers", "--no-access-log"],
                               env=env, pass_fds=(listener.fileno(),), stdout=log, stderr=log)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=2) as client:
            deadline = time.monotonic() + 15
            while True:
                assert process.poll() is None, "Server exited during startup"
                try:
                    ready = client.get("/v1/health")
                    if ready.status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                assert time.monotonic() < deadline, "Server did not become healthy"
                time.sleep(0.05)
            assert ready.json() == {"status": "ok", "schema_version": "0001"}
            account = json.loads((fixture / "users.json").read_text())["users"][1]
            response = client.post("/v1/auth/login", json={"username": account["username"], "password": account["password"]})
            assert response.status_code == 200
            token = response.json()["access_token"]
            assert client.get("/v1/me", headers={"Authorization": f"Bearer {token}"}).json()["id"] == account["id"]
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        listener.close()
        log.close()
