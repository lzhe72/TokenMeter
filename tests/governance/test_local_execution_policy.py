"""Local policy cannot silently run or publish through the retired CI route."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('local_policy_gate', ROOT/'scripts/quality_gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class PolicyTests(unittest.TestCase):
    def test_all_workflows_are_manual_nonpublishing_blocked_placeholders(self):
        for path in (ROOT/'.github/workflows').glob('*.yml'):
            with self.subTest(path=path.name):
                body = path.read_text()
                self.assertIn('workflow_dispatch:', body)
                self.assertIn('exit 2', body)
                for forbidden in ['pull_request:', 'push:', 'schedule:', 'workflow_run:', 'contents: write', 'upload-artifact', 'internal_publish.py', 'continue-on-error:']:
                    self.assertNotIn(forbidden, body)

    def test_electron_phase_never_falls_back_to_legacy_runner(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'releases/r').mkdir(parents=True)
            (root/'releases/current.json').write_text(json.dumps({'release_id':'r'}))
            (root/'releases/r/00-manifest.json').write_text(json.dumps({'execution_profile':'local_electron','execution_bindings_status':'planned'}))
            (root/'scripts').mkdir()
            (root/'scripts/e2e.py').write_text('raise RuntimeError("must not run legacy")')
            with patch.object(gate, 'validate_baseline', return_value=([],{})), patch.object(gate, 'validate_manifest', return_value=([],{})), patch.object(gate.subprocess,'run') as run, contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(gate.main(['iteration'],root=root),2)
                run.assert_not_called()
                self.assertIn('BLOCKED',out.getvalue())

if __name__=='__main__': unittest.main()
