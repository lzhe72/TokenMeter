"""Negative checks for the final-DMG runner; these never claim product E2E."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts import internal_package_e2e as release_e2e


class InternalPackageE2ETests(unittest.TestCase):
    def test_manifest_artifact_must_be_exact_non_symlink_file_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "TokenMeter.dmg"
            package.write_bytes(b"synthetic DMG bytes")
            expected = hashlib.sha256(package.read_bytes()).hexdigest()
            descriptor = {"path": package.name, "sha256": expected, "bytes": package.stat().st_size}
            self.assertEqual(release_e2e.require_artifact(root, descriptor, package), package.resolve())
            with self.assertRaises(release_e2e.EvidenceError):
                release_e2e.require_artifact(root, dict(descriptor, sha256="0" * 64), package)
            with self.assertRaises(release_e2e.EvidenceError):
                release_e2e.require_artifact(root, dict(descriptor, path="../TokenMeter.dmg"), package)
            linked = root / "alias.dmg"
            linked.symlink_to(package)
            with self.assertRaises(release_e2e.EvidenceError):
                release_e2e.require_artifact(root, dict(descriptor, path="alias.dmg"), linked)

    def test_ownership_claim_refuses_existing_production_state_and_preserves_it(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            home.mkdir()
            private = Path(directory) / "private"
            private.mkdir()
            with mock.patch.object(release_e2e, "defaults_domain_exists", return_value=False):
                claim = release_e2e.claim_production_state(home, private, "one")
                self.assertEqual(claim["run_id"], "one")
                with self.assertRaises(release_e2e.Blocked):
                    release_e2e.claim_production_state(home, private, "two")
            tokenmeter = home / "Library/Application Support/TokenMeter"
            tokenmeter.mkdir(parents=True)
            marker = tokenmeter / "do-not-remove"
            marker.write_text("user data")
            with mock.patch.object(release_e2e, "defaults_domain_exists", return_value=False):
                with self.assertRaises(release_e2e.Blocked):
                    release_e2e.claim_production_state(home, Path(directory), "three")
            self.assertEqual(marker.read_text(), "user data")

    def test_cleanup_refuses_unknown_credential_files_and_does_not_follow_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir()
            private = root / "private"
            private.mkdir()
            with mock.patch.object(release_e2e, "defaults_domain_exists", return_value=False):
                claim = release_e2e.claim_production_state(home, private, "one")
            credentials = home / "Library/Application Support/TokenMeter/credentials"
            credentials.mkdir(parents=True, mode=0o700)
            outside = root / "outside"
            outside.write_text("keep")
            (credentials / "unknown").symlink_to(outside)
            with mock.patch.object(release_e2e, "delete_defaults_domain", return_value=True):
                with self.assertRaises(release_e2e.EvidenceError):
                    release_e2e.cleanup_production_state(claim)
            self.assertEqual(outside.read_text(), "keep")
            self.assertTrue((credentials / "unknown").is_symlink())

    def test_termination_waits_for_owned_app_to_exit_and_ignores_other_processes(self):
        installed = Path("/private/tmp/owned/TokenMeter.app")
        executable = str(installed / "Contents/MacOS/TokenMeter")
        running = f"42 {executable}\n43 /Applications/TokenMeter.app/Contents/MacOS/TokenMeter\n"
        unrelated = "43 /Applications/TokenMeter.app/Contents/MacOS/TokenMeter\n"
        responses = [subprocess.CompletedProcess([], 0, running),
                     subprocess.CompletedProcess([], 0, running),
                     subprocess.CompletedProcess([], 0, unrelated)]
        with mock.patch.object(release_e2e.subprocess, "run", side_effect=responses) as run, \
                mock.patch.object(release_e2e.os, "kill") as kill, \
                mock.patch.object(release_e2e.time, "sleep") as sleep:
            release_e2e.terminate_owned_app(installed)
        self.assertEqual(run.call_count, 3)
        kill.assert_called_once_with(42, 15)
        sleep.assert_called_once_with(0.1)

    def test_termination_blocks_when_owned_app_remains_running(self):
        installed = Path("/private/tmp/owned/TokenMeter.app")
        executable = str(installed / "Contents/MacOS/TokenMeter")
        still_running = subprocess.CompletedProcess([], 0, f"42 {executable}\n")
        with mock.patch.object(release_e2e.subprocess, "run", return_value=still_running), \
                mock.patch.object(release_e2e.os, "kill"), \
                mock.patch.object(release_e2e.time, "monotonic", side_effect=[0, 5]), \
                self.assertRaisesRegex(release_e2e.EvidenceError, "remained running"):
            release_e2e.terminate_owned_app(installed)


if __name__ == "__main__":
    unittest.main()
