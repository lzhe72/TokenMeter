"""Negative verification of local evidence; synthetic data is not product E2E."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import contextlib
import io
import copy
import hashlib
import base64
import zipfile
import sqlite3
import shutil
import re
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('local_gate_test', ROOT/'scripts/local_gate.py')
gate=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class EvidenceTests(unittest.TestCase):
    def test_parent_gate_dispatches_distinct_bound_supplemental_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();out=root/'gate'
            manifest=root/'package-manifest.json';manifest.write_text('{}')
            dmg=root/'candidate.dmg';dmg.write_bytes(b'candidate')
            update=root/'update.zip';update.write_bytes(b'update')
            package={'artifacts':{'dmg':gate.descriptor(dmg,root),
                                  'update_zip':gate.descriptor(update,root)}}
            calls=[]
            def fake_runner(argv,log_path):
                calls.append(argv)
                output=Path(argv[argv.index('--output')+1])
                if Path(argv[1]).name=='granular_test_result.py':
                    log_path.write_text('synthetic export stop')
                    return 1
                if Path(argv[1]).name=='audit_granular_evidence.py':
                    output.parent.mkdir(exist_ok=True);output.write_text(json.dumps({'state':'PASS'}))
                else:
                    output.mkdir()
                    state='BLOCKED' if Path(argv[1]).name=='granular_e2e.py' else 'PASS'
                    (output/'result.json').write_text(json.dumps({'state':state,'cleanup_completed':True}))
                log_path.write_text('synthetic runner')
                return 2 if Path(argv[1]).name=='granular_e2e.py' else 0
            def fake_git(*args):
                if args==('rev-parse','HEAD'):return 'a'*40
                if args==('rev-parse','HEAD^{tree}'):return 'b'*40
                if args==('status','--porcelain'):return ''
                raise AssertionError(args)
            with patch.object(gate,'ROOT',root),patch.object(gate.platform,'system',return_value='Darwin'),\
                 patch.object(gate.platform,'machine',return_value='x86_64'),\
                 patch.object(gate,'git',side_effect=fake_git),\
                 patch.object(gate,'current_cases',return_value=('release',
                     {'execution_profile':'local_electron','execution_bindings_status':'ready'},gate.CASES)),\
                 patch.object(gate.subprocess,'run',return_value=SimpleNamespace(returncode=0)),\
                 patch.object(gate,'verify_package',return_value=package),\
                 patch.object(gate,'run_logged',side_effect=fake_runner),\
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gate.main(['--package-manifest',str(manifest),'--output',str(out)]),1)
            detailed=next(item for item in calls if Path(item[1]).name=='granular_e2e.py')
            supplemental=next((item for item in calls if Path(item[1]).name=='local_e2e.py'),None)
            self.assertIsNotNone(supplemental,repr((calls,json.loads((out/'gate.json').read_text()))))
            detail_id=detailed[detailed.index('--run-id')+1]
            supplement_id=supplemental[supplemental.index('--run-id')+1]
            self.assertNotEqual(detail_id,supplement_id)
            self.assertRegex(supplement_id,r'^local-[0-9a-f]{32}$')
            self.assertEqual(supplemental[supplemental.index('--parent-report')+1],
                             str(out/'granular/result.json'))
            self.assertEqual(json.loads((out/'gate.json').read_text())['supplemental_run_id'],supplement_id)

    def test_primary_runner_exit_one_cannot_pass_with_plausible_blocked_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();out=root/'gate'
            manifest=root/'package-manifest.json';manifest.write_text('{}')
            dmg=root/'candidate.dmg';dmg.write_bytes(b'candidate')
            update=root/'update.zip';update.write_bytes(b'update')
            package={'artifacts':{'dmg':gate.descriptor(dmg,root),
                                  'update_zip':gate.descriptor(update,root)}}
            release_id=json.loads((ROOT/'releases/current.json').read_text())['release_id']
            def fake_runner(argv,log_path):
                destination=Path(argv[argv.index('--output')+1]);destination.mkdir()
                (destination/'result.json').write_text(json.dumps({
                    'state':'BLOCKED','cleanup_completed':True,
                    'tc_results':[{'case_id':'TC-TM001-UI-01','state':'BLOCKED'}]}))
                log_path.write_text('synthetic abnormal exit')
                return 1
            def fake_git(*args):
                if args==('rev-parse','HEAD'):return 'a'*40
                if args==('rev-parse','HEAD^{tree}'):return 'b'*40
                if args==('status','--porcelain'):return ''
                raise AssertionError(args)
            with patch.object(gate.platform,'system',return_value='Darwin'),\
                 patch.object(gate.platform,'machine',return_value='x86_64'),\
                 patch.object(gate,'git',side_effect=fake_git),\
                 patch.object(gate,'current_cases',return_value=(release_id,
                     {'execution_profile':'local_electron','execution_bindings_status':'ready'},gate.CASES)),\
                 patch.object(gate.subprocess,'run',return_value=SimpleNamespace(returncode=0)),\
                 patch.object(gate,'verify_package',return_value=package),\
                 patch.object(gate,'run_logged',side_effect=fake_runner),\
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gate.main(['--package-manifest',str(manifest),'--output',str(out)]),1)
            recorded=json.loads((out/'gate.json').read_text())
            self.assertEqual(recorded['state'],'FAIL')
            self.assertEqual(recorded['granular_exit_code'],1)
            self.assertEqual(json.loads((out/'granular/result.json').read_text())['state'],'BLOCKED')
            self.assertFalse(list(out.glob('*.passport.json')))

    def final_product_fixture(self, root):
        from scripts import audit_granular_evidence, granular_gate
        catalog=json.loads((ROOT/'tests/test_cases.json').read_text())
        login=json.loads((ROOT/'tests/granular_login_variants.json').read_text())
        update=json.loads((ROOT/'tests/granular_update_variants.json').read_text())
        variants=granular_gate.combine_variants(login,update,catalog['release_id'])['variants']
        parents=[case['id'] for case in catalog['cases'] if case.get('feature_id')=='TM-001']
        auxiliary_ids={identity for identity in parents if identity.startswith(granular_gate.results.AUX_PREFIXES)}
        audited=list(audit_granular_evidence.AUDITED_CASES)
        package={'manifest_sha256':'d'*64,'dmg_sha256':'e'*64,'app_tree_sha256':'f'*64,
                 'installed_source':'final_dmg'}
        raw=[]
        for identity in parents+[item['id'] for item in variants]:
            if identity in auxiliary_ids:
                raw.append({'case_id':identity,'state':'BLOCKED','step_results':[],'evidence':{},
                            'started_at':None,'finished_at':None,
                            'reason':'No independently registered Playwright TC and isolated fixture binding'})
            else:raw.append({'case_id':identity,'state':'PASS'})
        primary={'scope':'granular_final_package','state':'BLOCKED','run_id':'run',
                 'release_id':catalog['release_id'],'source_commit':'a'*40,'candidate_tree':'b'*40,
                 'release_eligible':False,'cleanup_completed':True,'package':package,
                 'expected_cases':[item['case_id'] for item in raw],'tc_results':raw}
        primary_path=root/'granular/result.json';primary_path.parent.mkdir();primary_path.write_text(json.dumps(primary))
        auxiliary={'scope':'granular_auxiliary_package','state':'PASS','run_id':'aux-run',
                   'parent_run_id':'run','parent_report_sha256':gate.sha256(primary_path),
                   'source_commit':'a'*40,'candidate_tree':'b'*40,'release_id':catalog['release_id'],
                   'package':package,'release_eligible':False,'cleanup_completed':True,
                   'expected_cases':sorted(auxiliary_ids),
                   'tc_results':[{'case_id':identity,'state':'PASS'} for identity in sorted(auxiliary_ids)]}
        audit={'state':'PASS','run_id':'run','source_commit':'a'*40,
               'source_report_sha256':gate.sha256(primary_path),'audited_cases':audited,
               'findings':[{'case_id':identity,'original_state':'PASS','state':'PASS'} for identity in audited]}
        supplemental={'scope':'final_package','state':'PASS','run_id':'local-'+'c'*32,
                      'parent_run_id':'run','parent_report_sha256':gate.sha256(primary_path),
                      'release_id':catalog['release_id'],'source_commit':'a'*40,'candidate_tree':'b'*40,
                      'release_eligible':False,'cleanup_completed':True,'package':package,
                      'expected_cases':gate.CASES,
                      'suites':[{'case_id':identity,'state':'PASS','cleanup_completed':True} for identity in gate.CASES]}
        for folder,name,value in (('auxiliary','result.json',auxiliary),('audit','audit.json',audit),
                                  ('e2e','result.json',supplemental)):
            path=root/folder/name;path.parent.mkdir();path.write_text(json.dumps(value))
        model={'auxiliary_bound':True,'tc_counts':{'PASS':78,'FAIL':0,'BLOCKED':0},
               'auxiliary_tc_counts':{'PASS':11,'FAIL':0,'BLOCKED':0},
               'variant_counts':{'PASS':38,'FAIL':0,'BLOCKED':0},
               'cases':[{'id':identity,'state':'PASS','reported_state':'BLOCKED' if identity in auxiliary_ids else 'PASS',
                         'result_run_id':'aux-run' if identity in auxiliary_ids else 'run',
                         'auxiliary_state':'PASS' if identity in auxiliary_ids else '',
                         'audit_state':'PASS' if identity in audited else ''} for identity in parents],
               'variants':[{'id':item['id'],'parent_id':item['parent_id'],
                            'state':'PASS','reported_state':'PASS'} for item in variants],
               'auxiliary':[{'id':identity,'state':'PASS','reported_state':'PASS','run_id':'aux-run'}
                            for identity in sorted(auxiliary_ids)],
               'audit':[{'id':identity,'state':'PASS'} for identity in audited]}
        return model,primary,auxiliary,audit,supplemental

    def test_final_product_original_recalculates_all_cases_without_upgrading_raw_blocked(self):
        from scripts import granular_test_result
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            model,primary,auxiliary,audit,supplemental=self.final_product_fixture(root)
            with patch.dict(sys.modules,{'granular_test_result':granular_test_result}),\
                 patch.object(granular_test_result,'build_model',return_value=model):
                normalized=gate.derive_final_product_result(root,run_id='run',
                    candidate_sha='a'*40,candidate_tree='b'*40)
                self.assertEqual(normalized['state'],'PASS')
                self.assertEqual(normalized['primary_original_state'],'BLOCKED')
                self.assertEqual(normalized['supplemental_run_id'],'local-'+'c'*32)
                self.assertEqual(len(normalized['parent_cases']),78)
                self.assertEqual(len(normalized['variants']),38)
                self.assertEqual(sum(row['source']=='auxiliary' for row in normalized['parent_cases']),11)
                self.assertEqual(json.loads((root/'granular/result.json').read_text())['state'],'BLOCKED')
                result=root/'final-product-result.json';gate.write_new(result,normalized)
                self.assertEqual(gate.verify_final_product_result(root,run_id='run',
                    candidate_sha='a'*40,candidate_tree='b'*40),gate.descriptor(result,root))
                changed=copy.deepcopy(normalized);changed['parent_cases'][0]['final_state']='BLOCKED'
                result.write_text(json.dumps(changed))
                with self.assertRaises(gate.Invalid):gate.verify_final_product_result(root,run_id='run',
                    candidate_sha='a'*40,candidate_tree='b'*40)

    def test_final_product_rejects_unmapped_blocked_auxiliary_audit_and_package_mismatch(self):
        from scripts import granular_test_result
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            model,primary,auxiliary,audit,supplemental=self.final_product_fixture(root)
            original={name:(root/name/'audit.json' if name=='audit' else root/name/'result.json').read_bytes()
                      for name in ('granular','auxiliary','audit','e2e')}
            with patch.dict(sys.modules,{'granular_test_result':granular_test_result}),\
                 patch.object(granular_test_result,'build_model',return_value=model):
                for label,folder,edit in (
                    ('unmapped main blocked','granular',lambda value: next(item for item in value['tc_results']
                        if item['state']=='PASS').update(state='BLOCKED')),
                    ('unexecuted auxiliary','auxiliary',lambda value: value['tc_results'][0].update(state='BLOCKED')),
                    ('blocked audit','audit',lambda value: value.update(state='BLOCKED')),
                    ('wrong package','e2e',lambda value: value['package'].update(dmg_sha256='0'*64)),
                    ('reused primary run ID','e2e',lambda value: value.update(run_id='run')),
                    ('wrong parent report SHA','e2e',lambda value: value.update(parent_report_sha256='0'*64)),
                    ('wrong parent run ID','e2e',lambda value: value.update(parent_run_id='other')),
                ):
                    path=root/folder/('audit.json' if folder=='audit' else 'result.json')
                    value=json.loads(original[folder]);edit(value);path.write_text(json.dumps(value))
                    with self.subTest(label=label),self.assertRaises(gate.Invalid):
                        gate.derive_final_product_result(root,run_id='run',
                            candidate_sha='a'*40,candidate_tree='b'*40)
                    path.write_bytes(original[folder])

    def test_combined_excel_copy_keeps_sop_entry_and_verified_gate_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();source=root/'test-results/run/granular-reviewed'
            source.mkdir(parents=True)
            run_id='unit-review'
            gate_root=root/'gate';gate_root.mkdir()
            originals={}
            for folder,payload in (('granular',{'run_id':run_id,'source_commit':'a'*40,
                                               'package':{'dmg_sha256':'b'*64}}),
                                   ('auxiliary',{'run_id':'aux-unit'}),('audit',{}),
                                   ('e2e',{'run_id':'local-'+'c'*32,'parent_run_id':run_id,
                                           'source_commit':'a'*40,'package':{'dmg_sha256':'b'*64}})):
                target=gate_root/folder/'result.json' if folder!='audit' else gate_root/folder/'audit.json'
                target.parent.mkdir();target.write_text(json.dumps(payload));originals[folder]=target
            aggregate=json.loads(originals['e2e'].read_text())
            aggregate['parent_report_sha256']=gate.sha256(originals['granular'])
            originals['e2e'].write_text(json.dumps(aggregate))
            expected={'逐 TC 主原件':originals['granular'],'辅助 11 TC 原件':originals['auxiliary'],
                      '独立复核原件':originals['audit'],'六组聚合原件':originals['e2e'],
                      '用例目录':ROOT/'tests/test_cases.json',
                      '参数变体目录':ROOT/'tests/granular_login_variants.json',
                      '更新参数变体目录':ROOT/'tests/granular_update_variants.json'}
            source_files=[]
            for role,original in expected.items():
                digest=gate.sha256(original);target=source/'evidence'/digest[:2]/(digest+'.json')
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(original.read_bytes())
                source_files.append({'role':role,'sha256':digest,'link':str(target.relative_to(source))})
            model=source/'granular-source.json'
            model.write_text(json.dumps({'run_id':run_id,'aggregate_run_id':'local-'+'c'*32,'audit_run_id':run_id,
                'auxiliary_run_id':'aux-unit','candidate_sha':'a'*40,'package_dmg_sha256':'b'*64,
                'aggregate_candidate_sha':'a'*40,'aggregate_dmg_sha256':'b'*64,
                'tc_counts':{'PASS':78,'FAIL':0,'BLOCKED':0},
                'variant_counts':{'PASS':38,'FAIL':0,'BLOCKED':0},
                'auxiliary_product_state':'PASS','audit_state':'PASS','aggregate_product_state':'PASS',
                'source_files':source_files}))
            book=source/f'TokenMeter测试结果-{run_id}.xlsx'
            with zipfile.ZipFile(book,'w') as archive:
                archive.writestr('xl/workbook.xml','01逐例结果 02参数变体 04聚合场景 08辅助用例 11独立复核')
            receipt={'schema_version':1,'scope':'granular_test_result_excel','state':'PASS',
                     'run_id':run_id,'aggregate_run_id':'local-'+'c'*32,'product_state':'BLOCKED',
                     'tc_counts':{'PASS':78,'FAIL':0,'BLOCKED':0},
                     'variant_counts':{'PASS':38,'FAIL':0,'BLOCKED':0},
                     'suite_count':6,'audit_count':12,'source_model_sha256':gate.sha256(model),
                     'workbook':gate.descriptor(book,source)}
            (source/'verification.json').write_text(json.dumps(receipt))
            destination=gate_root/'granular-reviewed'
            gate.copy_reviewed_export(source,destination)
            verified=gate.verify_granular_workbook(gate_root,run_id=run_id)
            self.assertEqual(verified['state'],'PASS')
            self.assertEqual(verified['workbook']['sha256'],gate.sha256(book))
            aggregate_original=originals['e2e'].read_bytes()
            for mutation in ({'run_id':run_id},{'parent_report_sha256':'0'*64}):
                changed=json.loads(aggregate_original);changed.update(mutation)
                originals['e2e'].write_text(json.dumps(changed))
                with self.assertRaises(gate.Invalid):gate.verify_granular_workbook(gate_root,run_id=run_id)
            originals['e2e'].write_bytes(aggregate_original)
            with self.assertRaises(gate.Invalid):gate.copy_reviewed_export(source,destination)
            (destination/book.name).write_bytes(b'changed')
            with self.assertRaises(gate.Invalid):gate.verify_granular_workbook(gate_root,run_id=run_id)

    def test_detailed_fixed_code_snapshot_must_match_current_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            original=ROOT/'scripts/local_gate.py'
            snapshot=root/'test-code/scripts/local_gate.py'
            snapshot.parent.mkdir(parents=True)
            snapshot.write_bytes(original.read_bytes())
            digest=gate.sha256(original)
            report={'test_code_snapshot':[gate.descriptor(snapshot,root)],
                    'test_inputs_sha256':{'scripts/local_gate.py':digest}}
            self.assertEqual(gate._frozen_code(report,root,{'scripts/local_gate.py'})['scripts/local_gate.py'],digest)
            changed=copy.deepcopy(report);changed['test_inputs_sha256']['scripts/local_gate.py']='0'*64
            with self.assertRaises(gate.Invalid):gate._frozen_code(changed,root,{'scripts/local_gate.py'})
            snapshot.write_text('changed after run')
            with self.assertRaises(gate.Invalid):gate._frozen_code(report,root,{'scripts/local_gate.py'})
            report['test_code_snapshot'][0]['path']='test-code/../scripts/local_gate.py'
            with self.assertRaises(gate.Invalid):gate._frozen_code(report,root,{'scripts/local_gate.py'})

    def test_detailed_raw_playwright_rejects_skip_retry_and_foreign_candidate(self):
        from scripts import granular_test_result as results
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();identity='TC-TM001-LOGIN-01';run_id='unit-detailed'
            case=root/identity;case.mkdir()
            trace=case/'trace.zip'
            with zipfile.ZipFile(trace,'w') as archive:
                archive.writestr('trace.trace','\n'.join(json.dumps(event) for event in (
                    {'type':'context-options'},
                    {'type':'before','callId':'unit','class':'Frame','method':'click','params':{'selector':'data-testid="auth.login"'}},
                    {'type':'after','callId':'unit'})))
            png=case/'screen.png'
            png.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII='))
            raw={'errors':[],'config':{'metadata':{'run_id':run_id,'candidate_sha':'a'*40}},
                 'suites':[{'specs':[{'title':identity,'file':'granular-login.spec.ts','ok':True,
                                     'tests':[{'expectedStatus':'passed','status':'expected','results':[
                                         {'status':'passed','retry':0,'errors':[],
                                          'startTime':'1970-01-01T00:01:40Z','duration':100}]}]}]}]}
            path=case/'playwright.json';path.write_text(json.dumps(raw))
            def evidence():return {'evidence':{'playwright':gate.descriptor(path,root),
                    'trace':gate.descriptor(trace,root),'screenshots':[gate.descriptor(png,root)]}}
            gate._granular_playwright(root,evidence(),identity,run_id,'a'*40,99,102,results)
            for name,mutate in (
                ('retry',lambda item:item['suites'][0]['specs'][0]['tests'][0]['results'][0].update(retry=1)),
                ('skip',lambda item:item['suites'][0]['specs'][0]['tests'][0].update(status='skipped')),
                ('foreign',lambda item:item['config']['metadata'].update(candidate_sha='b'*40)),
            ):
                with self.subTest(name=name):
                    altered=copy.deepcopy(raw);mutate(altered);path.write_text(json.dumps(altered))
                    with self.assertRaises(gate.Invalid):
                        gate._granular_playwright(root,evidence(),identity,run_id,'a'*40,99,102,results)

    def test_detailed_parent_rejects_wrong_package_and_blocked_audit(self):
        now=gate.time.time()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();evidence=root/'evidence';evidence.mkdir()
            for name in ('granular','auxiliary','audit'):(evidence/name).mkdir()
            manifest=root/'package-manifest.json';manifest.write_text('{}')
            dmg=root/'original.dmg';dmg.write_bytes(b'dmg')
            # This verifier and its variant manifests are the frozen TM-001 release,
            # even when a later feature is the repository's current release.
            release=json.loads((ROOT/'tests/test_cases.json').read_text())['release_id']
            package={'release_id':release,'artifacts':{'dmg':gate.descriptor(dmg,root)},
                     'app':{'tree_sha256':'d'*64}}
            bound_package={'manifest_sha256':gate.sha256(manifest),'dmg_sha256':gate.sha256(dmg),
                           'app_tree_sha256':'d'*64,'installed_source':'final_dmg'}
            primary={'schema_version':3,'scope':'granular_final_package','run_id':'current',
                     'release_id':release,'release_eligible':False,'source_commit':'a'*40,
                     'candidate_tree':'b'*40,'working_tree_dirty':False,
                     'started_at':now-60,'finished_at':now-50,'host':{'architecture':'x86_64','macos':'15.7.4'},
                     'package':bound_package,'cleanup':{'mount':True,'private':True,'per_case':True},
                     'cleanup_completed':True,'state':'BLOCKED','tc_results':[]}
            first=evidence/'granular/result.json';first.write_text(json.dumps(primary))
            auxiliary={'schema_version':3,'scope':'granular_auxiliary_package','release_eligible':False,
                       'package':bound_package,'started_at':now-49,'finished_at':now-40,
                       'state':'PASS','parent_report_sha256':gate.sha256(first),'tc_results':[]}
            (evidence/'auxiliary/result.json').write_text(json.dumps(auxiliary))
            audit={'state':'BLOCKED','source_report_sha256':gate.sha256(first)}
            (evidence/'audit/audit.json').write_text(json.dumps(audit))
            frozen={name:gate.sha256(ROOT/name) for name in
                    ('tests/test_cases.json','tests/granular_login_variants.json','tests/granular_update_variants.json')}
            with patch.object(gate,'verify_package',return_value=package),\
                 patch.object(gate,'current_cases',return_value=(release,{},gate.CASES)),\
                 patch.object(gate,'_frozen_code',return_value=frozen):
                with self.assertRaises(gate.Blocked):
                    gate.verify_granular_run(evidence,manifest,run_id='current',candidate_sha='a'*40,
                                             candidate_tree='b'*40,not_before=now-90)
                changed=copy.deepcopy(primary);changed['package']['dmg_sha256']='e'*64
                first.write_text(json.dumps(changed))
                with self.assertRaises(gate.Invalid):
                    gate.verify_granular_run(evidence,manifest,run_id='current',candidate_sha='a'*40,
                                             candidate_tree='b'*40,not_before=now-90)
                changed=copy.deepcopy(primary);changed['source_commit']='f'*40
                first.write_text(json.dumps(changed))
                with self.assertRaises(gate.Invalid):
                    gate.verify_granular_run(evidence,manifest,run_id='current',candidate_sha='a'*40,
                                             candidate_tree='b'*40,not_before=now-90)

    def test_required_steps_match_the_checked_in_supplemental_spec(self):
        source=(ROOT/'apps/desktop/e2e/tm001.spec.ts').read_text()
        self.assertIn("async function defaults(step='default_routes')",source)
        for case,required in gate.REQUIRED_STEPS.items():
            start=re.search(r"test\('"+re.escape(case)+r"[^']*',\s*async\s*\(\)\s*=>\s*\{",source)
            self.assertIsNotNone(start,case)
            end=source.find('\n});',start.end())
            self.assertNotEqual(end,-1,case)
            body=source[start.end():end]
            recorded=set(re.findall(r"\b(?:event|identity|uiEquals|status)\('([^']+)'",body))
            if re.search(r'\bdefaults\(\)',body): recorded.add('default_routes')
            recorded.update(re.findall(r"\bdefaults\('([^']+)'\)",body))
            self.assertFalse(required-recorded,f'{case} gate requires events absent from the real spec: {required-recorded}')

    def update_requests(self):
        rows=[]
        def row(stage,route,status,body=b'',method='GET'):
            rows.append(dict(stage=stage,route=route,status=status,method=method,time=100+len(rows)/10,
                             bytes_sent=len(body),body_sha256=hashlib.sha256(body).hexdigest()))
        row('current','/version.json',204)
        for stage in ('forbidden','redirect','invalid','valid'):
            row(stage,'/control/'+stage,200,b'control','POST')
            row(stage,'/version.json',200,b'metadata')
            if stage=='redirect':row(stage,'/redirect.zip',302)
            if stage in ('invalid','valid'):row(stage,'/update.zip',200,b'zip')
        return dict(run_id='fresh',case_id='E2E-TM001-004',origin='http://127.0.0.1:54321',requests=rows)

    def test_update_requires_ordered_real_transfers_and_current_source(self):
        artifact=dict(bytes=3,sha256=hashlib.sha256(b'zip').hexdigest())
        good=self.update_requests()
        gate.verify_update_requests(good,run_id='fresh',start=99,end=105,artifact=artifact)
        bad=[]
        for field,value in [('run_id','old'),('origin','http://example.invalid'),('requests',[])]:
            item=copy.deepcopy(good);item[field]=value;bad.append(item)
        for key,value in [('bytes_sent',2),('body_sha256','0'*64),('status',206),('time',98)]:
            item=copy.deepcopy(good);item['requests'][-1][key]=value;bad.append(item)
        item=copy.deepcopy(good);item['requests']=[r for r in item['requests'] if r['stage']!='invalid'];bad.append(item)
        item=copy.deepcopy(good);item['requests'][0]['stage']='valid';bad.append(item)
        item=copy.deepcopy(good);item['requests'][2].update(route='/update.zip');bad.append(item)
        item=copy.deepcopy(good);item['requests'][-1]['route']='http://example.invalid/update.zip';bad.append(item)
        for value in bad:
            with self.subTest(value=value),self.assertRaises(gate.Invalid):
                gate.verify_update_requests(value,run_id='fresh',start=99,end=105,artifact=artifact)

    def raw(self, **result):
        return {'errors':[], 'suites':[{'specs':[{'title':'E2E-TM001-001 login', 'ok':True, 'tests':[{'expectedStatus':'passed','status':'expected','results':[{'status':'passed','retry':0,'errors':[], **result}]}]}]}]}

    def test_report_rejects_stale_identity_missing_cases_and_cleanup(self):
        # Deliberately synthetic evidence tests the verifier; no passport is issued.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();manifest=root/'package.json';manifest.write_text('{}')
            report=root/'result.json'
            package={'release_id':'release','artifacts':{'dmg':{'sha256':'dmg'},'update_zip':{'bytes':3,'sha256':hashlib.sha256(b'zip').hexdigest()}},'app':{'tree_sha256':'app'},'update_app':{'tree_sha256':'update'}}
            common=dict(schema_version=2,scope='final_package',run_id='fresh',release_id='release',
                        distribution_profile='internal',release_eligible=False,source_commit='sha',
                        candidate_tree='tree',working_tree_dirty=False,started_at=100,finished_at=105,
                        state='PASS',host={'architecture':'x86_64','macos':'15.7.4'},
                        package={'manifest_sha256':gate.sha256(manifest),'dmg_sha256':'dmg','app_tree_sha256':'app','build':'100'},
                        expected_cases=gate.CASES,executed_cases=6,passed_cases=6,suites=[],cleanup_completed=True,
                        cleanup={k:True for k in ('mount','services','app_processes','profiles','installs','ports','shipit')})
            def evidence(case,name,value):
                path=root/case/name;path.parent.mkdir(exist_ok=True)
                if isinstance(value,bytes):path.write_bytes(value)
                else:path.write_text(value if isinstance(value,str) else json.dumps(value))
                return gate.descriptor(path,root)
            buffer=io.BytesIO()
            with zipfile.ZipFile(buffer,'w') as trace:
                trace.writestr('trace.trace','{"type":"context-options"}\n{"type":"before","callId":"unit"}\n{"type":"after","callId":"unit"}\n')
            trace_bytes=buffer.getvalue()
            png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII=')
            for case in gate.CASES:
                raw=self.raw();raw['suites'][0]['specs'][0]['title']=case
                raw['config']={'metadata':{'run_id':'fresh','candidate_sha':'sha'}}
                raw['suites'][0]['specs'][0]['tests'][0]['results'][0].update(startTime='1970-01-01T00:01:40Z',duration=100)
                events=''.join(json.dumps(dict(run_id='fresh',case_id=case,timestamp=101,step=step,
                            source='ui',expected=True,actual=True,passed=True))+'\n' for step in gate.REQUIRED_STEPS[case])
                sql=evidence(case,'seed.sql','SELECT 1;')
                names=['admin'] if case.endswith('005') else ['test-admin','test-alice','test-bob','test-disabled']
                users=[dict(username=name,role='admin' if name.endswith('admin') else 'member',must_change_password=False) for name in names]
                suite=dict(case_id=case,state='PASS',cleanup_completed=True,failures=[],
                    playwright_json=evidence(case,'playwright.json',raw),events=evidence(case,'events.jsonl',events),
                    fixture_manifest=evidence(case,'fixture.json',dict(run_id='fresh',case_id=case,generator='synthetic-unit-test',files=[sql])),
                    sql=sql,service_audit=evidence(case,'audit.json',dict(run_id='fresh',case_id=case,requests=[{'route':route,'status':200} for route in ('/v1/auth/login','/v1/me')])),
                    database_summary=evidence(case,'db.json',dict(run_id='fresh',case_id=case,integrity_check='ok',schema_version='0001',users=users)),
                    trace=evidence(case,'trace.zip',trace_bytes),screenshots=[evidence(case,'image.png',png)],
                    installation={'app_tree_sha256':'app','path':'/owned/TokenMeter.app'})
                suite['traces']=[suite['trace']]
                if case.endswith('005'):
                    db_path=root/suite['database_summary']['path'];db=json.loads(db_path.read_text());db['actual_database_path']='/owned/restored.db'
                    suite['database_summary']=evidence(case,'db.json',db)
                    backup=root/case/'backup.db'
                    with sqlite3.connect(backup) as database:
                        database.executescript("CREATE TABLE alembic_version(version_num TEXT);INSERT INTO alembic_version VALUES('0001');CREATE TABLE users(username TEXT,role TEXT,is_active INTEGER,must_change_password INTEGER);INSERT INTO users VALUES('admin','admin',1,1);CREATE TABLE sessions(id TEXT);")
                    restored=root/case/'restored.db';shutil.copyfile(backup,restored)
                    suite['restore']=evidence(case,'restore.json',dict(run_id='fresh',case_id=case,synthetic_only=True,table_rows_match=True,integrity_check='ok',actual_service_database='/owned/restored.db',backup_sha256=gate.sha256(backup),restored_sha256=gate.sha256(restored),backup=gate.descriptor(backup,root),restored=gate.descriptor(restored,root)))
                if case.endswith('004'):
                    suite['update']=dict(requests=evidence(case,'requests.json',self.update_requests()),old_pid=1,new_pid=2,
                        old_build='100',new_build='101',old_app_tree_sha256='app',new_app_tree_sha256='update',
                        profile_before_after={'before':'/owned/profile','after':'/owned/profile'},me_status=200,
                        runtime_sha256_before='a'*64,runtime_sha256_after='a'*64,profile_observed_in_lsof=True,
                        default_profile_observed_in_lsof=False,runner_launch_count_after_install=0,reconnected_at=103)
                    suite['update']['result']=evidence(case,'upgrade-result.json',{k:v for k,v in suite['update'].items() if k not in ('requests','old_app_tree_sha256','new_app_tree_sha256')})
                    default_profile=str(Path.home()/'Library/Application Support/TokenMeter')
                    evidence(case,'process-open-files.json',dict(run_id='fresh',case_id=case,pid=2,observed_at=102,
                        all_open_paths=['/owned/profile/cache','/usr/lib/libSystem.B.dylib'],
                        owned_profile_paths=['/owned/profile/cache'],default_profile=default_profile,default_profile_paths=[]))
                    suite['update']['process']=evidence(case,'process.json',dict(run_id='fresh',case_id=case,old_pid=1,new_pid=2,
                        profile_path='/owned/profile',observed_open_paths=['/owned/profile/cache','/usr/lib/libSystem.B.dylib'],
                        observed_owned_open_paths=['/owned/profile/cache'],observed_default_open_paths=[],
                        process_open_files='process-open-files.json',
                        installed_executable='/owned/TokenMeter.app/Contents/MacOS/TokenMeter',observed_at=102))
                common['suites'].append(suite)
            variants=[]
            for field,value in [('scope','development_package'),('source_commit','other'),('candidate_tree','other'),
                                ('run_id','old'),('working_tree_dirty',True),('state','FAIL'),('passed_cases',0),
                                ('expected_cases',gate.CASES[:-1]),('cleanup_completed',False),('started_at',98)]:
                value_set=copy.deepcopy(common);value_set[field]=value;variants.append(value_set)
            for name in ('dmg_sha256','manifest_sha256','app_tree_sha256'):
                value_set=copy.deepcopy(common);value_set['package'][name]='altered';variants.append(value_set)
            value_set=copy.deepcopy(common);value_set['host']['architecture']='arm64';variants.append(value_set)
            value_set=copy.deepcopy(common);value_set['suites']=[];variants.append(value_set)
            value_set=copy.deepcopy(common);value_set['cleanup']['services']=False;variants.append(value_set)
            value_set=copy.deepcopy(common);value_set['suites'][0]['trace']['sha256']='0'*64;variants.append(value_set)
            for field,value in [('runner_launch_count_after_install',1),('runtime_sha256_after','c'*64),('new_pid',1)]:
                value_set=copy.deepcopy(common);value_set['suites'][-1]['update'][field]=value;variants.append(value_set)
            value_set=copy.deepcopy(common);value_set['suites'][0]['traces']=[];variants.append(value_set)
            value_set=copy.deepcopy(common)
            admin_suite=next(s for s in value_set['suites'] if s['case_id']=='E2E-TM001-003')
            admin_suite['service_audit']=evidence('E2E-TM001-003','audit-without-valid-me.json',
                dict(run_id='fresh',case_id='E2E-TM001-003',requests=[
                    {'route':'/v1/auth/login','status':200},
                    {'route':'/v1/me','status':401}]))
            variants.append(value_set)
            case='E2E-TM001-004'
            raw_open=json.loads((root/case/'process-open-files.json').read_text())
            raw_process=json.loads((root/case/'process.json').read_text())
            for name,altered_open,altered_process in (
                ('default-profile-open',
                 {**raw_open,'all_open_paths':raw_open['all_open_paths']+[default_profile+'/settings.json'],
                  'default_profile_paths':[default_profile+'/settings.json']},
                 {**raw_process,'observed_open_paths':raw_process['observed_open_paths']+[default_profile+'/settings.json'],
                  'observed_default_open_paths':[default_profile+'/settings.json']}),
                ('owned-profile-absent',
                 {**raw_open,'all_open_paths':['/usr/lib/libSystem.B.dylib'],'owned_profile_paths':[]},
                 {**raw_process,'observed_open_paths':['/usr/lib/libSystem.B.dylib'],
                  'observed_owned_open_paths':[]}),
                ('filtered-open-file-list',
                 {**raw_open,'owned_profile_paths':['/owned/profile/different']},raw_process),
            ):
                (root/case/name).mkdir()
                evidence(case,name+'/process-open-files.json',altered_open)
                altered=evidence(case,name+'/process.json',altered_process)
                value_set=copy.deepcopy(common)
                value_set['suites'][-1]['update']['process']=altered
                variants.append(value_set)
            with patch.object(gate,'verify_package',return_value=package),patch.object(gate,'current_cases',return_value=('release',{},gate.CASES)):
                report.write_text(json.dumps(common))
                self.assertEqual(gate.verify_report(report,manifest,run_id='fresh',candidate_sha='sha',candidate_tree='tree',not_before=99)[0]['run_id'],'fresh')
                for value_set in variants:
                    report.write_text(json.dumps(value_set))
                    with self.subTest(value_set=value_set),self.assertRaises(gate.Invalid):
                        gate.verify_report(report,manifest,run_id='fresh',candidate_sha='sha',candidate_tree='tree',not_before=99)

    def test_nonempty_text_cannot_impersonate_trace_or_screenshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();file=root/'artifact';file.write_text('a nonempty fake screenshot or trace')
            for verify in (gate.verify_trace,gate.verify_png):
                with self.subTest(verify=verify.__name__),self.assertRaises(gate.Invalid):
                    verify(root,gate.descriptor(file,root))
            with zipfile.ZipFile(file,'w') as archive:archive.writestr('readme.txt','Not a trace')
            with self.assertRaises(gate.Invalid):gate.verify_trace(root,gate.descriptor(file,root))

    def test_raw_case_requires_single_genuine_attempt(self):
        self.assertEqual(gate.verify_playwright(self.raw(), 'E2E-TM001-001'),1)
        for status in ['failed','skipped','timedOut','interrupted']:
            with self.subTest(status=status), self.assertRaises(gate.Invalid):
                gate.verify_playwright(self.raw(status=status),'E2E-TM001-001')
        with self.assertRaises(gate.Invalid):gate.verify_playwright(self.raw(retry=1),'E2E-TM001-001')
        x=self.raw();x['suites'][0]['specs'][0]['tests'][0]['results'].insert(0,{'status':'failed','retry':0})
        with self.assertRaises(gate.Invalid):gate.verify_playwright(x,'E2E-TM001-001')

    def test_zero_wrong_duplicate_global_error_and_expected_failure_rejected(self):
        variants=[{'errors':[],'suites':[]},self.raw()]
        variants[1]['errors']=[{'message':'worker failed'}]
        dupe=self.raw();dupe['suites']*=2;variants.append(dupe)
        expected=self.raw();expected['suites'][0]['specs'][0]['tests'][0]['expectedStatus']='failed';variants.append(expected)
        for value in variants:
            with self.assertRaises(gate.Invalid):gate.verify_playwright(value,'E2E-TM001-001')
        with self.assertRaises(gate.Invalid):gate.verify_playwright(self.raw(),'E2E-TM001-006')

    def test_artifact_escaping_mutation_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t).resolve();(base/'raw.json').write_text('{}')
            descriptor={'path':'raw.json','sha256':gate.sha256(base/'raw.json')}
            self.assertEqual(gate.checked_file(base,descriptor),base/'raw.json')
            for rel in ['../raw.json','/tmp/raw.json','a/../raw.json','./raw.json']:
                with self.assertRaises(gate.Invalid):gate.checked_file(base,{**descriptor,'path':rel})
            (base/'link.json').symlink_to(base/'raw.json')
            with self.assertRaises(gate.Invalid):gate.checked_file(base,{**descriptor,'path':'link.json'})
            (base/'raw.json').write_text('{"altered":true}')
            with self.assertRaises(gate.Invalid):gate.checked_file(base,descriptor)

    def test_gate_never_writes_into_an_existing_output_on_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp).resolve()
            with patch.object(gate.platform,'system',return_value='Darwin'), patch.object(gate.platform,'machine',return_value='x86_64'), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gate.main(['--output',str(out),'--package-manifest',str(out/'absent.json')]),1)
            self.assertEqual(list(out.iterdir()),[])

    def test_time_range_rejects_stale_future_or_reversed(self):
        self.assertEqual(gate.time_range({'started_at':100,'finished_at':101},not_before=99,now=102),(100,101))
        for a,b in [(98,101),(102,101),(101,108)]:
            with self.assertRaises(gate.Invalid):gate.time_range({'started_at':a,'finished_at':b},not_before=99,now=102)

if __name__=='__main__':unittest.main()
