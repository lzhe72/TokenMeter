"""A replay must reject changed assertions or a different package before launch."""
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import run_test_case as replay

class ReplayContract(unittest.TestCase):
    def test_changed_code_or_package_cannot_reuse_the_previous_run_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'fixed-test.py';source.write_text('assert actual == expected\n')
            manifest=root/'package.json';manifest.write_text('{"candidate":"one"}')
            report=root/'result.json'
            report.write_text(json.dumps({'test_inputs_sha256':{'fixed-test.py':hashlib.sha256(source.read_bytes()).hexdigest()},
                'package':{'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()}}))
            with patch.object(replay,'ROOT',root):
                replay.verify_replay(report,manifest)
                source.write_text('assert True\n')
                with self.assertRaisesRegex(ValueError,'Test source differs'):replay.verify_replay(report,manifest)
                source.write_text('assert actual == expected\n');manifest.write_text('{"candidate":"two"}')
                with self.assertRaisesRegex(ValueError,'Package manifest differs'):replay.verify_replay(report,manifest)

    def test_tc_selector_is_preserved_and_output_is_a_new_run(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest=Path(directory)/'package.json'
            manifest.write_text(json.dumps({'candidate_sha':'a'*40,'artifacts':{'dmg':{'path':'candidate.dmg'},'update_zip':{'path':'update.zip'}}}))
            one=replay.command(manifest,case_id='TC-TM001-LOGIN-01',all_cases=False,development=True,run_id='local-first')
            two=replay.command(manifest,case_id='TC-TM001-LOGIN-01',all_cases=False,development=True,run_id='local-second')
            self.assertEqual(one[-2:],['--case-id','TC-TM001-LOGIN-01'])
            self.assertNotEqual(one[one.index('--output')+1],two[two.index('--output')+1])
            with self.assertRaises(ValueError):replay.command(manifest,case_id='TC-TM001-LOGIN-01',all_cases=True,development=True,run_id='invalid')

    def test_signing_input_required_for_full_parent_and_variant_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest=Path(directory)/'package.json'
            manifest.write_text(json.dumps({'candidate_sha':'a'*40,'artifacts':{
                'dmg':{'path':'candidate.dmg'},'update_zip':{'path':'update.zip'}}}))
            for case_id,all_cases in ((None,True),('TC-TM001-UPDATE-05',False),
                                      ('TC-TM001-UPDATE-05#BYTES',False)):
                with self.subTest(case_id=case_id):
                    with self.assertRaises(replay.ReplayBlocked):
                        replay.command(manifest,case_id=case_id,all_cases=all_cases,
                                       development=False,run_id='local-missing')
                    with self.assertRaises(replay.ReplayBlocked):
                        replay.command(manifest,case_id=case_id,all_cases=all_cases,
                                       development=False,run_id='local-relative',key_dir=Path('keys'))
                    actual=replay.command(manifest,case_id=case_id,all_cases=all_cases,
                                          development=False,run_id='local-present',key_dir=Path(directory))
                    self.assertEqual(actual[actual.index('--key-dir')+1],directory)
            self.assertNotIn('--key-dir',replay.command(manifest,case_id='TC-TM001-LOGIN-01',
                all_cases=False,development=False,run_id='local-login'))

    def test_missing_signing_input_records_blocked_without_starting_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            manifest=root/'package.json'
            manifest.write_text('{}')
            stdout=io.StringIO()
            with (patch.object(replay,'ROOT',root), patch('sys.stdout',stdout),
                  patch.object(replay.subprocess,'Popen') as launch):
                code=replay.main(['--all','--package-manifest',str(manifest)])
            self.assertEqual(code,2)
            launch.assert_not_called()
            reports=list((root/'.local/ci').glob('local-*/result.json'))
            self.assertEqual(len(reports),1)
            self.assertEqual(json.loads(reports[0].read_text())['state'],'BLOCKED')
            self.assertEqual(reports[0].stat().st_mode & 0o777,0o600)
            self.assertEqual(reports[0].parent.stat().st_mode & 0o777,0o700)

    def test_private_signing_path_is_redacted_from_invocation_and_console(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            actual_key_dir=root/'real "key\''
            actual_key_dir.mkdir()
            key_dir=root/'private "key\''
            key_dir.symlink_to(actual_key_dir,target_is_directory=True)
            manifest=root/'package.json'
            manifest.write_text(json.dumps({'candidate_sha':'a'*40,'artifacts':{
                'dmg':{'path':'candidate.dmg'},'update_zip':{'path':'update.zip'}}}))
            encoded=json.dumps(str(key_dir),ensure_ascii=True)[1:-1]
            escaped=repr(str(key_dir))[1:-1]
            variants=[str(key_dir),str(key_dir.resolve()),encoded,escaped,shlex.quote(str(key_dir)),
                      json.dumps(str(key_dir.resolve()),ensure_ascii=True)[1:-1]]
            for form in variants:
                self.assertNotIn(form,replay.redact_signing_text('source='+form,key_dir))
            structured=replay.redact_signing_data({'error':variants},key_dir)
            self.assertNotIn(str(key_dir),json.dumps(structured))
            self.assertNotIn(str(key_dir.resolve()),json.dumps(structured))
            output=io.StringIO()
            captured=[]
            class Process:
                stdout=io.StringIO('failure '+str(key_dir)+' '+str(key_dir.resolve())+' '+encoded+' '+escaped+'\n')
                def wait(self): return 2
            def fake_launch(argv,**kwargs):
                captured.extend(argv)
                return Process()
            with (patch.object(replay,'ROOT',root),patch('sys.stdout',output),
                  patch.object(replay.subprocess,'Popen',side_effect=fake_launch)):
                self.assertEqual(replay.main(['--case-id','TC-TM001-UPDATE-05#BYTES',
                    '--package-manifest',str(manifest),'--key-dir',str(key_dir)]),2)
            self.assertIn(str(key_dir),captured)
            self.assertNotIn(str(key_dir),output.getvalue())
            self.assertNotIn(str(key_dir.resolve()),output.getvalue())
            log=next((root/'.local/ci').glob('*.console.log'))
            self.assertEqual(log.stat().st_mode & 0o777,0o600)
            self.assertNotIn(str(key_dir),log.read_text())
            self.assertNotIn(str(key_dir.resolve()),log.read_text())
            self.assertIn(replay.KEY_DIR_PLACEHOLDER,log.read_text())

    def test_launch_error_cannot_print_signing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            manifest=root/'package.json'
            manifest.write_text(json.dumps({'candidate_sha':'a'*40,'artifacts':{
                'dmg':{'path':'candidate.dmg'},'update_zip':{'path':'update.zip'}}}))
            key_dir=root/'private-keys'
            output=io.StringIO()
            with (patch.object(replay,'ROOT',root),patch('sys.stdout',output),
                  patch.object(replay.subprocess,'Popen',side_effect=OSError('launch '+str(key_dir)))):
                self.assertEqual(replay.main(['--case-id','TC-TM001-UPDATE-05#BYTES',
                    '--package-manifest',str(manifest),'--key-dir',str(key_dir)]),2)
            self.assertNotIn(str(key_dir),output.getvalue())
            log=next((root/'.local/ci').glob('*.console.log'))
            self.assertNotIn(str(key_dir),log.read_text())
            self.assertEqual(log.stat().st_mode & 0o777,0o600)

if __name__=='__main__':unittest.main()
