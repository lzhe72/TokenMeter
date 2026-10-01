"""Release-control regressions use synthetic GitHub responses, not a release."""
import importlib.util
from pathlib import Path
import unittest
import hashlib
import json
import tempfile

spec = importlib.util.spec_from_file_location('internal_publish', Path(__file__).resolve().parents[2] / 'scripts/internal_publish.py')
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)

class PublishTests(unittest.TestCase):
    def setUp(self):
        self.branch = {'protected': True, 'commit': {'sha': 'a'*40}, 'protection': {'enabled':True,
            'required_status_checks': {'enforcement_level': 'everyone', 'contexts': sorted(publish.CHECKS)}}}
        self.checks = [{'name': name, 'head_sha':'a'*40, 'conclusion':'success', 'status':'completed',
            'app': {'slug':'github-actions'}} for name in publish.CHECKS]

    def test_exact_successful_candidate_checks(self):
        publish.validate_remote_checks(self.branch, self.checks, 'a'*40)

    def test_missing_failed_or_wrong_commit_cannot_publish(self):
        for field,value in [('conclusion','failure'),('status','in_progress'),('head_sha','b'*40)]:
            records=[dict(x) for x in self.checks]; records[0][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):
                publish.validate_remote_checks(self.branch, records, 'a'*40)
        with self.assertRaises(ValueError): publish.validate_remote_checks(self.branch, self.checks[:-1], 'a'*40)

    def test_admin_bypass_or_old_master_refused(self):
        self.branch['protection']['required_status_checks']['enforcement_level']='non_admins'
        with self.assertRaises(ValueError): publish.validate_remote_checks(self.branch,self.checks,'a'*40)
        self.branch['protection']['required_status_checks']['enforcement_level']='everyone'
        self.branch['commit']['sha']='b'*40
        with self.assertRaises(ValueError): publish.validate_remote_checks(self.branch,self.checks,'a'*40)

    def test_publish_requires_all_actual_dependency_jobs(self):
        jobs=[{'name': n,'status':'completed','conclusion':'success','head_sha':'a'*40,'run_attempt':1}
              for n in publish.RELEASE_JOBS]
        publish.validate_jobs(jobs,'a'*40,'1')
        jobs[-1]['conclusion']='skipped'
        with self.assertRaises(ValueError): publish.validate_jobs(jobs,'a'*40,'1')
        jobs[-1]['conclusion']='success'; jobs[-1]['run_attempt']=2
        with self.assertRaises(ValueError): publish.validate_jobs(jobs,'a'*40,'1')


class AssetBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.ci = {'run_id': '123', 'run_attempt': '1'}
        self.manifest = {'release_id':'v0.1.0-20260929T074814Z', 'candidate_sha':'a'*40,
            'distribution_profile':'internal', 'artifacts':{}}
        for key in ('dmg','candidate_zip','server_zip'):
            path=self.root/(key+'.fixture'); path.write_bytes(key.encode())
            self.manifest['artifacts'][key]={'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
        self.mp=self.root/'package-manifest.json'; self.mp.write_text(json.dumps(self.manifest))
        self.passport={'state':'PASS','release_eligible':True,'distribution_profile':'internal',
            'release_id':self.manifest['release_id'],'candidate_sha':'a'*40,'ci':self.ci,'run_id':'nonce',
            'package_manifest_sha256':hashlib.sha256(self.mp.read_bytes()).hexdigest()}
        self.pp=self.root/'passport.json'; self.pp.write_text(json.dumps(self.passport))

    def verify(self):
        return publish.verified_assets(self.mp,self.pp,'a'*40,self.ci,'nonce')

    def test_original_assets_only(self):
        rid, assets=self.verify()
        self.assertEqual(rid,self.manifest['release_id'])
        self.assertEqual(len(assets),3)
        self.assertFalse(any('update' in p.name for p in assets))

    def test_wrong_run_or_attempt_or_manifest_refused(self):
        for key,value in [('run_id','other'),('ci',{'run_id':'123','run_attempt':'2'}),('package_manifest_sha256','0'*64)]:
            data=dict(self.passport); data[key]=value; self.pp.write_text(json.dumps(data))
            with self.subTest(key=key), self.assertRaises(ValueError): self.verify()

    def test_changed_original_package_refused(self):
        (self.root/'dmg.fixture').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.verify()

class EvidenceArchiveTests(unittest.TestCase):
    def test_archives_bind_native_bytes_and_reject_changed_bundle(self):
        import tarfile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); raw=root/'raw'; raw.mkdir()
            passport={'platforms':{}}
            for arch in ('arm64','x86_64'):
                bundle=raw/arch/'case/native.xcresult'; bundle.mkdir(parents=True)
                (bundle/'Data.sqlite').write_bytes(b'isolated fake raw bundle for governance')
                report={'suites':[{'case_id':'case','xcresult':'case/native.xcresult'}]}
                rp=raw/arch/'result.json'; rp.write_text(json.dumps(report))
                passport['platforms'][arch]={'report_sha256':publish.digest(rp),'xcresult_sha256':{'case':publish.native_e2e.tree_digest(bundle)}}
                with tarfile.open(root/('evidence-'+arch+'.tar.gz'),'w:gz') as tar: tar.add(raw/arch,arcname=arch)
            pp=root/'passport.json'; pp.write_text(json.dumps(passport))
            self.assertEqual(len(publish.verified_evidence(root,pp)),2)
            (raw/'arm64/case/native.xcresult/Data.sqlite').write_bytes(b'changed')
            with tarfile.open(root/'evidence-arm64.tar.gz','w:gz') as tar: tar.add(raw/'arm64',arcname='arm64')
            with self.assertRaises(ValueError): publish.verified_evidence(root,pp)

    def test_archive_refuses_links_and_traversal(self):
        import tarfile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve(); pp=root/'passport.json'; pp.write_text('{}')
            for name,kind in [('../escape',tarfile.REGTYPE),('arm64/link',tarfile.SYMTYPE)]:
                with tarfile.open(root/'evidence-arm64.tar.gz','w:gz') as tar:
                    member=tarfile.TarInfo(name); member.type=kind; member.linkname='/tmp/escape'; tar.addfile(member)
                with self.subTest(name=name),self.assertRaises(ValueError): publish.verified_evidence(root,pp)
