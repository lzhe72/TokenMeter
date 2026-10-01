"""Evidence-contract checks for individually executed TM-001 cases."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("granular_e2e_contract", ROOT / "scripts/granular_e2e.py")
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class GranularEvidenceContract(unittest.TestCase):
    def setUp(self):
        self.case = {"id": "TC-TM001-LOGIN-01", "steps": [{"step": 1}, {"step": 2}]}
        self.run_id = "local-" + "a" * 32

    def events(self, path: Path, steps: list[int], *, credential=False):
        rows = [{"run_id": self.run_id, "case_id": self.case["id"], "step": step,
                 "action": "enter a synthetic credential" if not credential else "TEST-ONLY-secret",
                 "expected": True, "actual": True, "passed": True,
                 "timestamp": "2026-09-30T00:00:00Z", "source": "ui"}
                for step in steps]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    def test_catalog_has_independent_variant_identities(self):
        catalog = runner.read_catalog()
        identities = [case["id"] for case in catalog]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertEqual(78, sum("parent_id" not in case for case in catalog))
        declared = []
        for name in ("granular_login_variants.json", "granular_update_variants.json"):
            path = ROOT / "tests" / name
            if path.is_file(): declared.extend(json.loads(path.read_text())["variants"])
        self.assertEqual({row["id"] for row in declared}, {case["id"] for case in catalog if "parent_id" in case})

    def test_missing_or_duplicate_steps_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            self.events(path, [1])
            _, error = runner.step_evidence(self.case, path, self.run_id)
            self.assertIn("Catalog steps", error)
            self.events(path, [1, 1, 2])
            _, error = runner.step_evidence(self.case, path, self.run_id)
            self.assertIn("Catalog steps", error)

    def test_correct_steps_pass_and_credential_leak_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            self.events(path, [1, 2])
            steps, error = runner.step_evidence(self.case, path, self.run_id)
            self.assertIsNone(error)
            self.assertEqual(2, len(steps))
            self.events(path, [1, 2], credential=True)
            _, error = runner.step_evidence(self.case, path, self.run_id)
            self.assertIn("credential", error)

    def test_playwright_title_and_single_attempt_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "playwright.json"
            payload = {"suites": [{"specs": [{"title": self.case["id"],
                        "tests": [{"results": [{"status": "passed"}]}]}]}]}
            path.write_text(json.dumps(payload))
            self.assertEqual("PASS", runner.raw_status(path, self.case["id"])[0])
            self.assertEqual("BLOCKED", runner.raw_status(path, "TC-TM001-LOGIN-02")[0])
            payload["suites"][0]["specs"][0]["tests"][0]["results"].append({"status": "passed"})
            path.write_text(json.dumps(payload))
            self.assertEqual("BLOCKED", runner.raw_status(path, self.case["id"])[0])

    def test_update_signing_preflight_blocks_before_app_mount_and_redacts_report(self):
        from granular_update_validation_fixture import SigningInputsUnavailable
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            manifest=root/'package.json'
            dmg=root/'candidate.dmg'
            update_zip=root/'update.zip'
            for path in (manifest,dmg,update_zip): path.write_bytes(b'fixture')
            key_dir=root/'private-signing-keys'
            key_dir.mkdir()
            parent={'id':'TC-TM001-UPDATE-05','steps':[],'design_status':'designed'}
            child={'id':'TC-TM001-UPDATE-05#BYTES','parent_id':parent['id'],
                   'steps':[],'design_status':'designed'}
            package={'release_id':'v0.1.0-test','working_tree_dirty':False,
                     'candidate_tree':'a'*40,'app':{'tree_sha256':'b'*64}}
            args=SimpleNamespace(case_id=[parent['id']],output=root/'results',
                package_manifest=manifest,dmg=dmg,update_zip=update_zip,
                candidate_sha='a'*40,run_id='local-'+'a'*32,development=False,key_dir=key_dir)
            with (patch.object(runner,'ROOT',root),patch.object(runner,'read_catalog',return_value=[parent,child]),
                  patch.object(runner.base,'verify_host_and_manifest',return_value=package),
                  patch.object(runner.base,'mount_dmg') as mount,
                  patch('granular_update_validation_fixture.validate_signing_inputs',
                        side_effect=SigningInputsUnavailable('unsafe '+str(key_dir))) as preflight,
                  patch('sys.stdout',io.StringIO())):
                self.assertEqual(runner.execute(args),2)
            preflight.assert_called_once_with(key_dir,package,update_zip)
            mount.assert_not_called()
            report=json.loads((args.output/'result.json').read_text())
            self.assertEqual(report['state'],'BLOCKED')
            self.assertEqual(len(report['tc_results']),2)
            self.assertNotIn(str(key_dir),json.dumps(report))
            self.assertIn(runner.KEY_DIR_PLACEHOLDER,report['replay']['all_command'])
            self.assertIn(runner.KEY_DIR_PLACEHOLDER,
                report['replay']['cases'][parent['id']]['command'])
            self.assertIn(runner.KEY_DIR_PLACEHOLDER,
                report['replay']['cases'][child['id']]['command'])

    def test_public_package_mismatch_is_fail_before_app_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            manifest=root/'package.json'
            dmg=root/'candidate.dmg'
            update_zip=root/'update.zip'
            for path in (manifest,dmg,update_zip): path.write_bytes(b'fixture')
            case={'id':'TC-TM001-UPDATE-05#SHA','parent_id':'TC-TM001-UPDATE-05',
                  'steps':[],'design_status':'designed'}
            args=SimpleNamespace(case_id=[case['id']],output=root/'results',
                package_manifest=manifest,dmg=dmg,update_zip=update_zip,
                candidate_sha='a'*40,run_id='local-'+'a'*32,development=False,key_dir=root/'keys')
            with (patch.object(runner,'ROOT',root),patch.object(runner,'read_catalog',return_value=[case]),
                  patch.object(runner.base,'verify_host_and_manifest',return_value={}),
                  patch.object(runner.base,'mount_dmg') as mount,
                  patch('granular_update_validation_fixture.validate_signing_inputs',
                        side_effect=ValueError('Update ZIP differs from current package manifest')),
                  patch('sys.stdout',io.StringIO())):
                self.assertEqual(runner.execute(args),1)
            mount.assert_not_called()
            report=json.loads((args.output/'result.json').read_text())
            self.assertEqual(report['state'],'FAIL')
            self.assertIn('Update ZIP differs',report['error'])

    def test_update_without_absolute_key_dir_is_blocked_before_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            manifest=root/'package.json'
            dmg=root/'candidate.dmg'
            update_zip=root/'update.zip'
            for path in (manifest,dmg,update_zip): path.write_bytes(b'fixture')
            case={'id':'TC-TM001-UPDATE-05#BYTES','parent_id':'TC-TM001-UPDATE-05',
                  'steps':[],'design_status':'designed'}
            for value in (None,Path('relative/keys')):
                args=SimpleNamespace(case_id=[case['id']],output=root/('run-'+str(value)),
                    package_manifest=manifest,dmg=dmg,update_zip=update_zip,
                    candidate_sha='a'*40,run_id='local-'+'a'*32,development=False,key_dir=value)
                with (patch.object(runner,'ROOT',root),patch.object(runner,'read_catalog',return_value=[case]),
                      patch.object(runner.base,'verify_host_and_manifest',return_value={}),
                      patch.object(runner.base,'mount_dmg') as mount,patch('sys.stdout',io.StringIO())):
                    self.assertEqual(runner.execute(args),2)
                mount.assert_not_called()
                self.assertEqual(json.loads((args.output/'result.json').read_text())['state'],'BLOCKED')


if __name__ == "__main__":
    unittest.main()
