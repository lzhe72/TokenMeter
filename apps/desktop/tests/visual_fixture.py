#!/usr/bin/env python3
"""Run auxiliary visual checks against real development App and isolated SQLite.

From repository root after npm run build:
  .local/venv-tm001/bin/python apps/desktop/tests/visual_fixture.py
This does not validate the final DMG or issue product/release qualification.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import uuid


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    output = root / ".local/ci" / ("hig-visual-" + uuid.uuid4().hex)
    output.mkdir(mode=0o700)
    spec = importlib.util.spec_from_file_location("visual_runner", root / "scripts/local_e2e.py")
    assert spec and spec.loader
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    private = output / "private"
    private.mkdir(mode=0o700)
    project = private / "apps/desktop"
    project.mkdir(parents=True, mode=0o700)
    shutil.copytree(root / "apps/desktop/out", project / "out")
    shutil.copyfile(root / "apps/desktop/package.json", project / "package.json")
    release_id = "v0.1.0-20260929T074814Z"
    release = private / "releases" / release_id
    release.mkdir(parents=True, mode=0o700)
    shutil.copyfile(root / "releases" / release_id / "local-release.json", release / "local-release.json")
    bootstrap = runner.module("visual_bootstrap", "scripts/bootstrap_sqlite.py")
    fixtures = runner.module("visual_fixtures", "tests/server/fixtures.py")
    database, _, _ = runner.make_account_database(private / "data", output, "hig" + uuid.uuid4().hex[:10], 42, bootstrap, fixtures)
    service = runner.Service(database, private)
    result_code = 1
    closed = False
    try:
        context = {
            "owner": "tokenmeter-hig-probe", "output": str(output), "project": str(project),
            "profile": str(private / "profile"), "service_url": service.url,
            "executable": str(root / "apps/desktop/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron"),
        }
        context_path = private / "context.json"
        context_path.write_text(json.dumps(context), encoding="utf-8")
        context_path.chmod(0o600)
        log_path = output / "run.log"
        with log_path.open("w", encoding="utf-8") as log:
            log_path.chmod(0o600)
            result_code = subprocess.run(["node", str(root / "apps/desktop/tests/hig.visual.cjs"), str(context_path)],
                                         cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=180).returncode
    finally:
        closed = service.close()
        cleanup = output / "cleanup.json"
        cleanup.write_text(json.dumps({"service_closed": closed, "scope": "auxiliary_visual", "product_e2e": False}), encoding="utf-8")
        cleanup.chmod(0o600)
        print(json.dumps({"output": str(output), "exit_code": result_code, "service_closed": closed}))
    return result_code if closed else 1


if __name__ == "__main__":
    raise SystemExit(main())
