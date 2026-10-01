"""A replay must reject changed assertions or a different package before launch."""
import hashlib
import json
from pathlib import Path
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

if __name__=='__main__':unittest.main()
