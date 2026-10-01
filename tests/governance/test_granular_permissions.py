"""TM-002 fixed catalog binding and real-response barrier infrastructure."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import granular_permissions as subject  # noqa: E402


class PermissionsBindingTest(unittest.TestCase):
    def test_development_dmg_requires_scope_digest_and_not_released_marker(self):
        candidate = "a" * 40
        tree = "b" * 40
        with tempfile.TemporaryDirectory(prefix="tm002-package-contract-") as temporary:
            root = Path(temporary).resolve()
            original = root / f"TokenMeter-{subject.RELEASE}-internal.dmg"
            original.write_bytes(b"fixed synthetic DMG descriptor only")
            marked = root / f"TokenMeter-{subject.RELEASE}-DEVELOPMENT-NOT-RELEASED.dmg"
            marked.write_bytes(original.read_bytes())
            update = root / "update.zip"
            update.write_bytes(b"fixed synthetic ZIP descriptor only")
            descriptor = lambda path: {"path": path.name,
                                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                       "bytes": path.stat().st_size}
            payload = {"schema_version": 2, "scope": "development", "release_id": subject.RELEASE,
                       "candidate_sha": candidate, "candidate_tree": tree, "working_tree_dirty": True,
                       "artifacts": {"dmg": descriptor(original), "update_zip": descriptor(update)},
                       "app": {"version": "0.2.0", "build": "200"}}
            manifest = root / "package-manifest.json"
            def save(): manifest.write_text(json.dumps(payload), encoding="utf-8")
            save()
            with (patch.object(subject.platform, "system", return_value="Darwin"),
                  patch.object(subject.platform, "machine", return_value="x86_64"),
                  patch.object(subject.platform, "mac_ver", return_value=("15.7", (), "")),
                  patch.object(subject.shutil, "which", return_value="/usr/bin/synthetic"),
                  patch.object(subject.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, tree + "\n"))):
                self.assertEqual(subject.verify_package(manifest, marked, candidate, development=True), payload)
                with self.assertRaises(subject.base.Failed):
                    subject.verify_package(manifest, original, candidate, development=True)
                marked.write_bytes(b"changed")
                with self.assertRaises(subject.base.Failed):
                    subject.verify_package(manifest, marked, candidate, development=True)
                marked.write_bytes(original.read_bytes())
                payload["scope"] = "final_package"
                payload["working_tree_dirty"] = False
                save()
                self.assertEqual(subject.verify_package(manifest, original, candidate), payload)
                with self.assertRaises(subject.base.Failed):
                    subject.verify_package(manifest, marked, candidate)
                payload["working_tree_dirty"] = True
                save()
                with self.assertRaises(subject.base.Failed):
                    subject.verify_package(manifest, original, candidate)

    def test_all_28_executable_product_cases_have_literal_playwright_titles(self):
        cases, variants = subject.read_catalog()
        executable = {case["id"] for case in cases if case["id"] not in variants}
        code = (ROOT / "apps/desktop/e2e/granular-permissions.spec.ts").read_text(encoding="utf-8")
        titles = re.findall(r"^test\('(TC-TM002-[A-Z]+-\d{2}(?:#[A-Z0-9_]+)?)'", code, flags=re.M)
        self.assertEqual(len(titles), 28)
        self.assertEqual(set(titles), executable)
        self.assertEqual(len(cases), 33)
        self.assertEqual(sum(map(len, variants.values())), 13)

    def test_only_unconfirmed_cases_expect_no_native_keychain_item(self):
        cases, variants = subject.read_catalog()
        executable = {case["id"] for case in cases if case["id"] not in variants}
        self.assertEqual(subject.NO_KEYCHAIN_ITEM_EXPECTED, {
            "TC-TM002-SELECT-01", "TC-TM002-SELECT-02#FIRST_CANCEL",
            "TC-TM002-PREVIEW-01", "TC-TM002-CONSENT-01",
            "TC-TM002-PREVIEW-04#CANDIDATES_1001",
            "TC-TM002-PREVIEW-04#ENTRIES_5001", "TC-TM002-PREVIEW-04#DEPTH_9"
        })
        self.assertEqual(len(executable - subject.NO_KEYCHAIN_ITEM_EXPECTED), 21)
        self.assertTrue(subject.NO_KEYCHAIN_ITEM_EXPECTED <= executable)

    def test_identity_barrier_holds_only_after_real_upstream_response(self):
        body = json.dumps({"id": "00000000-0000-4000-8000-000000000002", "username": "test-alice"}).encode()
        upstream_requests: list[str] = []

        class RealFixture(BaseHTTPRequestHandler):
            def log_message(self, *_args): return
            def do_GET(self):
                upstream_requests.append(self.path)
                if self.path != "/v1/me":
                    self.send_error(404); return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), RealFixture)
        upstream.daemon_threads = True
        thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        thread.start()
        barrier = subject.IdentityBarrier(f"http://127.0.0.1:{upstream.server_port}")
        control_headers = {"Authorization": "Bearer " + barrier.token}
        try:
            with urlopen(Request(barrier.url + "/__tm002_barrier/arm", data=b"", headers=control_headers),
                         timeout=5) as response:
                self.assertEqual(response.status, 200)
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(lambda: urlopen(barrier.url + "/v1/me", timeout=10).read())
                deadline = time.monotonic() + 5
                observation = None
                while time.monotonic() < deadline:
                    with urlopen(Request(barrier.url + "/__tm002_barrier/status", headers=control_headers),
                                 timeout=5) as response:
                        status = json.load(response)
                    if status["captured"]:
                        observation = status["observation"]
                        break
                    time.sleep(0.03)
                self.assertIsNotNone(observation)
                self.assertEqual(upstream_requests, ["/v1/me"])
                self.assertEqual(observation["status"], 200)
                self.assertEqual(observation["account_id"], "00000000-0000-4000-8000-000000000002")
                self.assertFalse(future.done(), "The client must wait after FastAPI produced the real response")
                with urlopen(Request(barrier.url + "/__tm002_barrier/release", data=b"",
                                     headers=control_headers), timeout=5) as response:
                    self.assertEqual(response.status, 200)
                self.assertEqual(future.result(timeout=5), body)
        finally:
            self.assertTrue(barrier.close())
            upstream.shutdown(); upstream.server_close(); thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
