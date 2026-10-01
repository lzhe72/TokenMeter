"""Local archive copy integrity and no-clobber policy."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import json
import zipfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('release_local_test',ROOT/'scripts/local_release.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)

class ArchiveTests(unittest.TestCase):
    def synthetic_release_inputs(self, root):
        manifest=root/'package.json';manifest.write_text('{}')
        raw=root/'e2e'/'result.json';raw.parent.mkdir();raw.write_text('{}')
        rid='v0.1.0-20260929T074814Z'
        originals={}
        for folder,name,key in [('granular','result.json','granular_report'),
                                ('auxiliary','result.json','auxiliary_report'),
                                ('audit','audit.json','audit_report')]:
            path=root/folder/name;path.parent.mkdir()
            content={'source':folder}
            if folder=='granular':content.update(source_commit='sha',package={'dmg_sha256':'0'*64})
            if folder=='auxiliary':content['run_id']='aux-run'
            path.write_text(json.dumps(content))
            originals[key]=release.gate.descriptor(path,root)
        granular=dict(state='PASS',run_id='run',candidate_sha='sha',candidate_tree='tree',dmg_sha256='0'*64,
                      **originals,parent_cases=78,variants=38,auxiliary_cases=11,audited_cases=12)
        aggregate_id='local-'+'c'*32
        raw.write_text(json.dumps({'run_id':aggregate_id,'parent_run_id':'run',
            'parent_report_sha256':release.gate.sha256(root/'granular/result.json'),
            'source_commit':'sha','package':{'dmg_sha256':'0'*64}}))
        reviewed=root/'granular-reviewed';reviewed.mkdir()
        source_paths={
            '逐 TC 主原件':root/'granular'/'result.json',
            '辅助 11 TC 原件':root/'auxiliary'/'result.json',
            '独立复核原件':root/'audit'/'audit.json',
            '六组聚合原件':raw,
            '用例目录':ROOT/'tests/test_cases.json',
            '参数变体目录':ROOT/'tests/granular_login_variants.json',
            '更新参数变体目录':ROOT/'tests/granular_update_variants.json',
        }
        links=reviewed/'source-links';links.mkdir()
        source_files=[]
        for index,(role,source) in enumerate(source_paths.items()):
            link=links/f'{index}.json';link.write_bytes(source.read_bytes())
            source_files.append({'role':role,'sha256':release.gate.sha256(source),'link':str(link.relative_to(reviewed))})
        model=reviewed/'granular-source.json'
        model.write_text(json.dumps(dict(run_id='run',aggregate_run_id=aggregate_id,audit_run_id='run',
            auxiliary_run_id='aux-run',candidate_sha='sha',package_dmg_sha256='0'*64,
            aggregate_candidate_sha='sha',aggregate_dmg_sha256='0'*64,
            tc_counts={'PASS':78,'FAIL':0,'BLOCKED':0},variant_counts={'PASS':38,'FAIL':0,'BLOCKED':0},
            auxiliary_product_state='PASS',audit_state='PASS',aggregate_product_state='PASS',
            source_files=source_files)))
        book=reviewed/'TokenMeter测试结果-run.xlsx'
        with zipfile.ZipFile(book,'w') as archive:
            archive.writestr('xl/workbook.xml',' '.join(('01逐例结果','02参数变体','04聚合场景','08辅助用例','11独立复核')))
        receipt=reviewed/'verification.json'
        receipt.write_text(json.dumps(dict(schema_version=1,scope='granular_test_result_excel',state='PASS',
            run_id='run',aggregate_run_id=aggregate_id,product_state='BLOCKED',
            tc_counts={'PASS':78,'FAIL':0,'BLOCKED':0},variant_counts={'PASS':38,'FAIL':0,'BLOCKED':0},
            suite_count=6,audit_count=12,source_model_sha256=release.gate.sha256(model),
            workbook=release.gate.descriptor(book,reviewed))))
        workbook=release.gate.verify_granular_workbook(root,run_id='run')
        final_path=root/'final-product-result.json'
        final_path.write_text(json.dumps({'state':'PASS','run_id':'run',
            'parent_cases':[{'case_id':'TM-001-TC-001','final_state':'PASS'}]}))
        final_descriptor=release.gate.descriptor(final_path,root)
        result=dict(state='PASS',release_id=rid,release_eligible=True,phase='release',scope='local_final_package',
                    candidate_sha='sha',candidate_tree='tree',package_manifest_sha256=release.gate.sha256(manifest),
                    report=release.gate.descriptor(raw,root),run_id='run',supplemental_run_id=aggregate_id,
                    started_at=1,finished_at=2,
                    granular_evidence=granular,granular_workbook=workbook,final_product_result=final_descriptor)
        passport=dict(result,schema_version=2,distribution_profile='internal',storage='local_only',github_release=False,
                      source_inputs={p:release.gate.sha256(ROOT/p) for p in (
                          'tests/feature_matrix.json','tests/acceptance.json','tests/datasets.json',
                          'tests/test_cases.json','tests/granular_login_variants.json','tests/granular_update_variants.json',
                          'docs/catalog.json','scripts/granular_gate.py','sop/SOP-014-e2e.md',
                          'sop/SOP-018-release-gate.md','apps/desktop/package-lock.json')},artifacts={})
        (root/'gate.json').write_text(json.dumps(result))
        (root/(rid+'.passport.json')).write_text(json.dumps(passport))
        return manifest,result,passport,granular

    def test_passport_itself_must_authorize_release(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();manifest,result,passport,granular=self.synthetic_release_inputs(root)
            path=root/(result['release_id']+'.passport.json')
            with patch.object(release.gate,'git',side_effect=lambda *args:'' if args[0]=='status' else 'tree'),\
                 patch.object(release.gate,'verify_report',return_value=({}, {'artifacts':{}})),\
                 patch.object(release.gate,'verify_granular_run',return_value=granular),\
                 patch.object(release.gate,'verify_final_product_result',return_value=result['final_product_result'],create=True):
                self.assertEqual(release.verify_inputs(root,manifest)[1]['release_eligible'],True)
                for field,value in [('release_eligible',False),('phase','iteration'),('source_inputs',{}),
                                    ('source_inputs',{k:v for k,v in passport['source_inputs'].items()
                                                      if k!='tests/test_cases.json'})]:
                    path.write_text(json.dumps({**passport,field:value}))
                    with self.subTest(field=field),self.assertRaises(release.gate.Invalid):release.verify_inputs(root,manifest)

    def test_missing_or_changed_detailed_descriptor_cannot_authorize_release(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();manifest,result,passport,granular=self.synthetic_release_inputs(root)
            gate_path=root/'gate.json';passport_path=root/(result['release_id']+'.passport.json')
            with patch.object(release.gate,'git',side_effect=lambda *args:'' if args[0]=='status' else 'tree'),\
                 patch.object(release.gate,'verify_report',return_value=({}, {'artifacts':{}})),\
                 patch.object(release.gate,'verify_granular_run',return_value=granular) as verify,\
                 patch.object(release.gate,'verify_final_product_result',return_value=result['final_product_result'],create=True):
                self.assertEqual(release.verify_inputs(root,manifest)[0]['granular_evidence'],granular)
                verify.assert_called_with(root,manifest,run_id='run',candidate_sha='sha',candidate_tree='tree',not_before=1)
                for changed_gate,changed_passport in [
                    ({k:v for k,v in result.items() if k!='granular_evidence'},
                     {k:v for k,v in passport.items() if k!='granular_evidence'}),
                    (result,{**passport,'granular_evidence':{**granular,'parent_cases':77}}),
                    ({**result,'granular_evidence':{**granular,'granular_report':
                        {**granular['granular_report'],'sha256':'f'*64}}},
                     {**passport,'granular_evidence':{**granular,'granular_report':
                        {**granular['granular_report'],'sha256':'f'*64}}}),
                ]:
                    gate_path.write_text(json.dumps(changed_gate));passport_path.write_text(json.dumps(changed_passport))
                    with self.subTest(changed_gate=changed_gate.get('granular_evidence'),
                                      changed_passport=changed_passport.get('granular_evidence')):
                        self.assertRaises(release.gate.Invalid,release.verify_inputs,root,manifest)

    def test_archived_detailed_originals_are_rechecked(self):
        with tempfile.TemporaryDirectory() as t:
            archive=Path(t).resolve()/'release-archive'
            evidence=archive/'evidence';evidence.mkdir(parents=True)
            package=archive/'package';package.mkdir()
            manifest,result,passport,granular=self.synthetic_release_inputs(evidence)
            archived_manifest=package/'package-manifest.json'
            archived_manifest.write_bytes(manifest.read_bytes())
            result['package_manifest_sha256']=release.gate.sha256(archived_manifest)
            passport['package_manifest_sha256']=result['package_manifest_sha256']
            (evidence/'gate.json').write_text(json.dumps(result))
            (evidence/(result['release_id']+'.passport.json')).write_text(json.dumps(passport))
            def recheck(directory,manifest_path,**identity):
                self.assertEqual(directory,evidence)
                self.assertEqual(manifest_path,archived_manifest)
                self.assertEqual(identity,dict(run_id='run',candidate_sha='sha',candidate_tree='tree',not_before=1))
                for key in ('granular_report','auxiliary_report','audit_report'):
                    release.gate.checked_file(directory,granular[key])
                return granular
            def recheck_final(directory,**identity):
                self.assertEqual(directory,evidence)
                self.assertEqual(identity,dict(run_id='run',candidate_sha='sha',candidate_tree='tree'))
                return release.gate.descriptor(directory/'final-product-result.json',directory)
            with patch.object(release.gate,'git',side_effect=lambda *args:'' if args[0]=='status' else 'tree'),\
                 patch.object(release.gate,'verify_report',return_value=({}, {'artifacts':{}})),\
                 patch.object(release.gate,'verify_granular_run',side_effect=recheck),\
                 patch.object(release.gate,'verify_final_product_result',side_effect=recheck_final,create=True):
                self.assertEqual(release.verify_inputs(evidence,archived_manifest)[0]['granular_evidence'],granular)
                granular_original=evidence/'granular'/'result.json'
                original_bytes=granular_original.read_bytes()
                granular_original.write_text('{"source":"tampered"}')
                with self.assertRaises(release.gate.Invalid):
                    release.verify_inputs(evidence,archived_manifest)
                granular_original.write_bytes(original_bytes)
                archived_book=evidence/'granular-reviewed'/'TokenMeter测试结果-run.xlsx'
                book_bytes=archived_book.read_bytes()
                archived_book.write_bytes(b'tampered workbook')
                with self.assertRaises(release.gate.Invalid):
                    release.verify_inputs(evidence,archived_manifest)
                archived_book.unlink()
                with self.assertRaises(release.gate.Blocked):
                    release.verify_inputs(evidence,archived_manifest)
                archived_book.write_bytes(book_bytes)
                (evidence/'final-product-result.json').write_text('{"state":"BLOCKED"}')
                with self.assertRaises(release.gate.Invalid):
                    release.verify_inputs(evidence,archived_manifest)

    def test_missing_or_changed_workbook_descriptor_cannot_authorize_release(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();manifest,result,passport,granular=self.synthetic_release_inputs(root)
            gate_path=root/'gate.json';passport_path=root/(result['release_id']+'.passport.json')
            workbook=result['granular_workbook']
            with patch.object(release.gate,'git',side_effect=lambda *args:'' if args[0]=='status' else 'tree'),\
                 patch.object(release.gate,'verify_report',return_value=({}, {'artifacts':{}})),\
                 patch.object(release.gate,'verify_granular_run',return_value=granular),\
                 patch.object(release.gate,'verify_final_product_result',return_value=result['final_product_result'],create=True):
                self.assertEqual(release.verify_inputs(root,manifest)[0]['granular_workbook'],workbook)
                for changed_gate,changed_passport in [
                    ({k:v for k,v in result.items() if k!='granular_workbook'},
                     {k:v for k,v in passport.items() if k!='granular_workbook'}),
                    (result,{**passport,'granular_workbook':{**workbook,'run_id':'other'}}),
                    ({**result,'granular_workbook':{**workbook,'workbook':
                        {**workbook['workbook'],'sha256':'f'*64}}},
                     {**passport,'granular_workbook':{**workbook,'workbook':
                        {**workbook['workbook'],'sha256':'f'*64}}}),
                ]:
                    gate_path.write_text(json.dumps(changed_gate));passport_path.write_text(json.dumps(changed_passport))
                    with self.subTest(changed_gate=changed_gate.get('granular_workbook'),
                                      changed_passport=changed_passport.get('granular_workbook')):
                        self.assertRaises(release.gate.Invalid,release.verify_inputs,root,manifest)

    def test_missing_or_changed_final_product_result_cannot_authorize_release(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();manifest,result,passport,granular=self.synthetic_release_inputs(root)
            gate_path=root/'gate.json';passport_path=root/(result['release_id']+'.passport.json')
            original=result['final_product_result']
            with patch.object(release.gate,'git',side_effect=lambda *args:'' if args[0]=='status' else 'tree'),\
                 patch.object(release.gate,'verify_report',return_value=({}, {'artifacts':{}})),\
                 patch.object(release.gate,'verify_granular_run',return_value=granular),\
                 patch.object(release.gate,'verify_final_product_result',return_value=original,create=True) as verify:
                self.assertEqual(release.verify_inputs(root,manifest)[0]['final_product_result'],original)
                verify.assert_called_with(root,run_id='run',candidate_sha='sha',candidate_tree='tree')
                for changed_gate,changed_passport in [
                    ({k:v for k,v in result.items() if k!='final_product_result'},
                     {k:v for k,v in passport.items() if k!='final_product_result'}),
                    (result,{**passport,'final_product_result':{**original,'bytes':original['bytes']+1}}),
                    ({**result,'final_product_result':{**original,'sha256':'f'*64}},
                     {**passport,'final_product_result':{**original,'sha256':'f'*64}}),
                ]:
                    gate_path.write_text(json.dumps(changed_gate));passport_path.write_text(json.dumps(changed_passport))
                    with self.subTest(changed_gate=changed_gate.get('final_product_result'),
                                      changed_passport=changed_passport.get('final_product_result')):
                        self.assertRaises(release.gate.Invalid,release.verify_inputs,root,manifest)
                gate_path.write_text(json.dumps(result));passport_path.write_text(json.dumps(passport))
                final_path=root/'final-product-result.json'
                final_path.write_text('{"state":"BLOCKED","run_id":"run"}')
                with self.assertRaises(release.gate.Invalid):
                    release.verify_inputs(root,manifest)
                final_path.unlink()
                with self.assertRaises(release.gate.Blocked):
                    release.verify_inputs(root,manifest)

    def test_forged_blocked_final_mapping_is_recomputed_from_originals(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();manifest,result,passport,granular=self.synthetic_release_inputs(root)
            final_path=root/'final-product-result.json'
            expected=json.loads(final_path.read_text())
            forged=json.loads(final_path.read_text())
            forged['parent_cases'][0]['final_state']='BLOCKED'
            final_path.write_text(json.dumps(forged))
            forged_descriptor=release.gate.descriptor(final_path,root)
            result['final_product_result']=forged_descriptor
            passport['final_product_result']=forged_descriptor
            (root/'gate.json').write_text(json.dumps(result))
            (root/(result['release_id']+'.passport.json')).write_text(json.dumps(passport))
            with patch.object(release.gate,'git',side_effect=lambda *args:'' if args[0]=='status' else 'tree'),\
                 patch.object(release.gate,'verify_report',return_value=({}, {'artifacts':{}})),\
                 patch.object(release.gate,'verify_granular_run',return_value=granular),\
                 patch.object(release.gate,'derive_final_product_result',return_value=expected):
                with self.assertRaisesRegex(release.gate.Invalid,
                                            'Final product result differs from its four original sources'):
                    release.verify_inputs(root,manifest)

    def test_missing_archived_auxiliary_original_is_blocked_by_real_verifier(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();manifest,result,passport,_=self.synthetic_release_inputs(root)
            (root/'auxiliary'/'result.json').unlink()
            with patch.object(release.gate,'git',side_effect=lambda *args:'' if args[0]=='status' else 'tree'),\
                 patch.object(release.gate,'verify_report',return_value=({}, {'artifacts':{}})),\
                 patch.object(release.gate,'verify_package',return_value={}):
                with self.assertRaisesRegex(release.gate.Blocked,'Missing artifact auxiliary/result.json'):
                    release.verify_inputs(root,manifest)

    def test_copy_is_exact_and_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();source=root/'source';source.mkdir();(source/'report.json').write_text('{"test":"synthetic"}')
            target=root/'target'
            index=release.copy_evidence(source,target)
            self.assertEqual((target/'report.json').read_bytes(),(source/'report.json').read_bytes())
            self.assertEqual(index['report.json'],release.gate.sha256(source/'report.json'))
            with self.assertRaises(release.gate.Invalid):release.copy_evidence(source,target)
    def test_evidence_symlink_refused(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();source=root/'source';source.mkdir();(root/'secret').write_text('synthetic');(source/'escape').symlink_to(root/'secret')
            with self.assertRaises(release.gate.Invalid):release.copy_evidence(source,root/'target')
    def test_existing_output_not_modified(self):
        with tempfile.TemporaryDirectory() as t:
            target=Path(t).resolve()/'v';target.mkdir();(target/'keep').write_text('keep')
            with self.assertRaises(release.gate.Invalid):release.new_directory(target)
            self.assertEqual((target/'keep').read_text(),'keep')

    def test_publish_final_dmg_is_hash_checked_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();rid='v0.1.0-20260929T074814Z'
            archive=root/'archive';package=archive/'package';package.mkdir(parents=True)
            filename=f'TokenMeter-{rid}-internal.dmg';source=package/filename
            source.write_bytes(b'synthetic final dmg')
            descriptor={'path':filename,'sha256':release.gate.sha256(source),'bytes':source.stat().st_size}
            (archive/'release-index.json').write_text(json.dumps({'state':'PASS','release_id':rid,
                'dmg':'package/'+filename,'files':{'package/'+filename:descriptor['sha256']}}))
            version=root/'dmg'/rid;version.mkdir(parents=True)
            (version/'README.md').write_text('Synthetic preview and final locations')
            (version/f'TokenMeter-{rid}-DEVELOPMENT-NOT-RELEASED.dmg').write_bytes(b'preview')
            target=release.publish_final_dmg(archive,rid,descriptor,dmg_root=root/'dmg')
            self.assertEqual(target,version/filename)
            self.assertEqual(target.read_bytes(),source.read_bytes())
            self.assertEqual(release.gate.sha256(target),descriptor['sha256'])
            self.assertEqual(list(version.glob('*.part')),[])
            with self.assertRaises(release.gate.Invalid):
                release.publish_final_dmg(archive,rid,descriptor,dmg_root=root/'dmg')
            self.assertEqual(target.read_bytes(),source.read_bytes())

    def test_publish_refuses_symlink_directories_and_destination(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();rid='v0.1.0-20260929T074814Z'
            package=root/'archive'/'package';package.mkdir(parents=True)
            filename=f'TokenMeter-{rid}-internal.dmg';source=package/filename;source.write_bytes(b'final')
            descriptor={'path':filename,'sha256':release.gate.sha256(source),'bytes':source.stat().st_size}
            (root/'archive'/'release-index.json').write_text(json.dumps({'state':'PASS','release_id':rid,
                'dmg':'package/'+filename,'files':{'package/'+filename:descriptor['sha256']}}))
            (root/'outside').mkdir();(root/'linked-dmg').symlink_to(root/'outside',target_is_directory=True)
            with self.assertRaises(release.gate.Invalid):
                release.publish_final_dmg(root/'archive',rid,descriptor,dmg_root=root/'linked-dmg')
            dmg=root/'dmg';dmg.mkdir();(dmg/rid).symlink_to(root/'outside',target_is_directory=True)
            with self.assertRaises(release.gate.Invalid):
                release.publish_final_dmg(root/'archive',rid,descriptor,dmg_root=dmg)
            (dmg/rid).unlink();(dmg/rid).mkdir();(dmg/rid/filename).symlink_to(source)
            with self.assertRaises(release.gate.Invalid):
                release.publish_final_dmg(root/'archive',rid,descriptor,dmg_root=dmg)
            self.assertEqual(source.read_bytes(),b'final')

    def test_publish_does_not_expose_failed_copy(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();rid='v0.1.0-20260929T074814Z'
            package=root/'archive'/'package';package.mkdir(parents=True)
            filename=f'TokenMeter-{rid}-internal.dmg';source=package/filename;source.write_bytes(b'final')
            descriptor={'path':filename,'sha256':release.gate.sha256(source),'bytes':source.stat().st_size}
            (root/'archive'/'release-index.json').write_text(json.dumps({'state':'PASS','release_id':rid,
                'dmg':'package/'+filename,'files':{'package/'+filename:descriptor['sha256']}}))
            def corrupt(_read,write):write.write(b'changed')
            with patch.object(release.shutil,'copyfileobj',side_effect=corrupt):
                with self.assertRaises(release.gate.Invalid):
                    release.publish_final_dmg(root/'archive',rid,descriptor,dmg_root=root/'dmg')
            self.assertFalse((root/'dmg'/rid/filename).exists())
            self.assertEqual(list((root/'dmg'/rid).glob('*.part')),[])

    def test_publish_requires_completed_pass_archive(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();rid='v0.1.0-20260929T074814Z'
            archive=root/'archive';package=archive/'package';package.mkdir(parents=True)
            filename=f'TokenMeter-{rid}-internal.dmg';source=package/filename;source.write_bytes(b'final')
            descriptor={'path':filename,'sha256':release.gate.sha256(source),'bytes':source.stat().st_size}
            (archive/'INCOMPLETE.json').write_text('{}')
            (archive/'release-index.json').write_text(json.dumps({'state':'PASS','release_id':rid,
                'dmg':'package/'+filename,'files':{'package/'+filename:descriptor['sha256']}}))
            with self.assertRaises(release.gate.Invalid):
                release.publish_final_dmg(archive,rid,descriptor,dmg_root=root/'dmg')
            (archive/'INCOMPLETE.json').unlink()
            (archive/'release-index.json').write_text(json.dumps({'state':'FAIL','release_id':rid,
                'dmg':'package/'+filename,'files':{'package/'+filename:descriptor['sha256']}}))
            with self.assertRaises(release.gate.Invalid):
                release.publish_final_dmg(archive,rid,descriptor,dmg_root=root/'dmg')
            self.assertFalse((root/'dmg').exists())

    def test_archive_does_not_publish_when_gate_rejects(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve()
            with patch.object(release,'verify_inputs',side_effect=release.gate.Invalid('No release qualification')):
                with patch.object(release,'publish_final_dmg') as publish:
                    with self.assertRaises(release.gate.Invalid):release.archive(root,root/'manifest.json',root/'dmg'/'release-archive')
                    publish.assert_not_called()
            self.assertFalse((root/'dmg').exists())

    def test_archive_default_is_under_root_dmg(self):
        rid='v0.1.0-20260929T074814Z'
        with patch.object(release,'verify_inputs',return_value=({'release_id':rid},None,None,None)):
            with patch.object(release,'archive',return_value={'state':'PASS'}) as archive:
                self.assertEqual(release.main(['archive','--gate-dir','/tmp/gate','--package-manifest','/tmp/manifest']),0)
        self.assertEqual(archive.call_args.args[2],ROOT/'dmg'/rid/'release-archive')

if __name__=='__main__':unittest.main()
