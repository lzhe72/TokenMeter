"""Environment probe diagnostics; mocked setup is never product E2E evidence."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("native_environment", ROOT / "scripts/native_environment.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class EnvironmentProbeTests(unittest.TestCase):
    def root(self, directory):
        root = Path(directory)
        (root / "releases").mkdir()
        (root / "releases/current.json").write_text(json.dumps({"release_id": "v0.1.0-20260929T074814Z"}))
        return root

    def test_ready_does_not_report_product_execution_or_release_qualification(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with mock.patch.object(probe, "execute_probe"), \
                 mock.patch.object(probe.e2e, "git_value", side_effect=["a" * 40, ""]), contextlib.redirect_stdout(output):
                self.assertEqual(probe.main(root=self.root(directory)), 0)
            result = json.loads(output.getvalue().splitlines()[-1])
            report = json.loads(Path(result["report"]).read_text())
            self.assertEqual(Path(result["report"]).name, "environment.json")
            self.assertEqual(report["state"], "READY")
            self.assertEqual(report["scope"], "environment_only")
            self.assertEqual(report["executed_cases"], 0)
            self.assertFalse(report["release_eligible"])
            self.assertEqual(report["sop_id"], "SOP-009")
            self.assertEqual(report["release_id"], "v0.1.0-20260929T074814Z")
            self.assertEqual(report["source_commit"], "a" * 40)
            self.assertFalse(report["working_tree_dirty"])

    def test_original_prepare_error_survives_cleanup_error(self):
        signing = mock.Mock()
        signing.SigningIdentity.return_value.prepare.side_effect = RuntimeError("trust certificate timed out after 60 seconds")
        signing.SigningIdentity.return_value.close.side_effect = RuntimeError("remove certificate trust failed (1)")
        update = mock.Mock()
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(probe.native, "preflight", return_value={"architecture": "arm64"}), \
             mock.patch.object(probe.native, "load_module", side_effect=[signing, update]), \
             contextlib.redirect_stdout(output):
            self.assertEqual(probe.main(root=self.root(directory)), 1)
        result = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(result["blockers"], ["trust certificate timed out after 60 seconds"])
        self.assertFalse(result["cleanup_completed"])
        self.assertTrue(any("remove certificate trust failed" in message for message in result["cleanup_errors"]))
        signing.SigningIdentity.return_value.close.assert_called_once()
        update.UpdateSource.assert_not_called()

    def test_primary_failure_still_records_successful_cleanup(self):
        signing, update = mock.Mock(), mock.Mock()
        update.UpdateSource.return_value.start.side_effect = RuntimeError("loopback port 49177 unavailable")
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(probe.native, "preflight", return_value={"architecture": "x86_64"}), \
             mock.patch.object(probe.native, "load_module", side_effect=[signing, update]), \
             contextlib.redirect_stdout(output):
            self.assertEqual(probe.main(root=self.root(directory)), 2)
        result = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["blockers"], ["loopback port 49177 unavailable"])
        self.assertTrue(result["cleanup_completed"])
        self.assertEqual(result["cleanup_errors"], [])
        signing.SigningIdentity.return_value.close.assert_called_once()
        update.UpdateSource.return_value.close.assert_called_once()

    def test_same_source_start_and_metadata_are_reported_without_product_cases(self):
        signing, update = mock.Mock(), mock.Mock()
        update.UpdateSource.return_value.url = "http://127.0.0.1:49177"
        update.UpdateSource.return_value.source_nonce_sha256 = "b" * 64
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(probe.native, "preflight", return_value={"architecture": "arm64"}), \
             mock.patch.object(probe.native, "load_module", side_effect=[signing, update]), \
             contextlib.redirect_stdout(output):
            self.assertEqual(probe.main(root=self.root(directory)), 0)
        result = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(result["origin_url"], "http://127.0.0.1:49177")
        self.assertEqual(result["transport"], "loopback_http")
        self.assertEqual(result["source_nonce_sha256"], "b" * 64)
        self.assertEqual(result["executed_cases"], 0)
        self.assertFalse(result["release_eligible"])
        update.UpdateSource.assert_called_once()
        update.UpdateSource.return_value.prepare.assert_called_once()
        update.UpdateSource.return_value.start.assert_called_once()
        update.UpdateSource.return_value._run.assert_not_called()

    def test_cleanup_failure_after_successful_probe_blocks_report(self):
        signing, update = mock.Mock(), mock.Mock()
        update.UpdateSource.return_value.close.side_effect = RuntimeError("close failed")
        update.UpdateSource.return_value.url = "http://127.0.0.1:49177"
        update.UpdateSource.return_value.source_nonce_sha256 = "c" * 64
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(probe.native, "preflight", return_value={"architecture": "arm64"}), \
             mock.patch.object(probe.native, "load_module", side_effect=[signing, update]), \
             contextlib.redirect_stdout(output):
            update.UpdateSource.return_value.private = Path(directory)
            self.assertEqual(probe.main(root=self.root(directory)), 1)
        result = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(result["state"], "FAIL")
        self.assertFalse(result["cleanup_completed"])
        self.assertTrue(any("close failed" in message for message in result["cleanup_errors"]))
        signing.SigningIdentity.return_value.close.assert_called_once()
