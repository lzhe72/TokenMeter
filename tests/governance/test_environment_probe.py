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
    def test_ready_does_not_report_product_execution_or_release_qualification(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with mock.patch.object(probe, "execute_probe"), contextlib.redirect_stdout(output):
                self.assertEqual(probe.main(root=Path(directory)), 0)
            result = json.loads(output.getvalue().splitlines()[-1])
            report = json.loads(Path(result["report"]).read_text())
            self.assertEqual(Path(result["report"]).name, "environment.json")
            self.assertEqual(report["state"], "READY")
            self.assertEqual(report["scope"], "environment_only")
            self.assertEqual(report["executed_cases"], 0)
            self.assertFalse(report["release_eligible"])

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
            self.assertEqual(probe.main(root=Path(directory)), 1)
        result = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(result["blockers"], ["trust certificate timed out after 60 seconds"])
        self.assertTrue(any("remove certificate trust failed" in message for message in result["cleanup_errors"]))
        signing.SigningIdentity.return_value.close.assert_called_once()
        update.UpdateSource.assert_not_called()
