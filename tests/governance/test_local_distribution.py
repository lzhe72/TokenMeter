"""Isolated local distribution contract tests; not App E2E."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/local_distribution.py'
spec = importlib.util.spec_from_file_location('local_distribution', SCRIPT)
distribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distribution)


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.rid = 'v0.1.0-20260929T074814Z'
        self.candidate = b'synthetic fixture zip; never a product artifact'
        (self.root / 'package').mkdir(exist_ok=True)
        (self.root / 'evidence').mkdir(exist_ok=True)
        (self.root / 'package/candidate.zip').write_bytes(self.candidate)
        self.manifest = {'schema_version':2, 'scope':'final_package', 'release_id': self.rid, 'candidate_sha': 'a'*40,
            'distribution_profile': 'internal', 'app': {'build': '100', 'version': '0.1.0', 'minimum_macos': '15.0'},
            'artifacts': {'candidate_zip': {'path': 'candidate.zip', 'sha256': hashlib.sha256(self.candidate).hexdigest(), 'bytes': len(self.candidate)}},
            'signatures': {'candidate_ed_signature': base64.b64encode(bytes(64)).decode()}}
        self.write()

    def write(self):
        (self.root / 'package/package-manifest.json').write_text(json.dumps(self.manifest))
        self.passport = {'schema_version':2, 'storage':'local_only','github_release':False,'state': 'PASS', 'release_eligible': True, 'release_id': self.rid,
            'distribution_profile': 'internal', 'candidate_sha': 'a'*40,
            'package_manifest_sha256': hashlib.sha256((self.root / 'package/package-manifest.json').read_bytes()).hexdigest()}
        (self.root / ('evidence/'+self.rid+'.passport.json')).write_text(json.dumps(self.passport))
        (self.root/'release-index.json').write_text(json.dumps({'state':'PASS','release_id':self.rid,'candidate_sha':'a'*40,'github_release':False}))

    def test_serves_only_candidate_and_correct_stable_version(self):
        bundle = distribution.load_release(self.root)
        routes = distribution.routes_for(bundle)
        self.assertEqual(set(routes), {'/version.json', '/candidate.zip', '/healthz'})
        self.assertEqual(routes['/candidate.zip'][1], self.candidate)
        metadata=json.loads(routes['/version.json'][1])
        self.assertEqual(metadata['build'],'100')
        self.assertEqual(metadata['version'],'0.1.0')
        self.assertEqual(metadata['url'],'http://127.0.0.1:49177/candidate.zip')
        self.assertEqual(metadata['sha256'],hashlib.sha256(self.candidate).hexdigest())
        self.assertNotIn('/update.zip',routes)

    def test_incomplete_archive_and_symlink_root_refused(self):
        (self.root/'INCOMPLETE.json').write_text('{}')
        with self.assertRaises(ValueError): distribution.load_release(self.root)
        (self.root/'INCOMPLETE.json').unlink()
        link=self.root/'alias';link.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError): distribution.load_release(link)

    def test_changed_zip_or_manifest_is_refused(self):
        (self.root / 'package/candidate.zip').write_bytes(b'changed')
        with self.assertRaises(ValueError): distribution.load_release(self.root)
        (self.root / 'package/candidate.zip').write_bytes(self.candidate)
        (self.root / 'package/package-manifest.json').write_text(json.dumps(self.manifest)+' ')
        with self.assertRaises(ValueError): distribution.load_release(self.root)

    def test_no_passport_no_release(self):
        (self.root / ('evidence/'+self.rid+'.passport.json')).unlink()
        with self.assertRaises((ValueError, OSError)): distribution.load_release(self.root)

    def test_wrong_candidate_blocked_passport_and_escape_are_refused(self):
        path = self.root / ('evidence/'+self.rid+'.passport.json')
        for key, value in [('state', 'BLOCKED'), ('candidate_sha', 'b'*40), ('release_eligible', False), ('distribution_profile','public')]:
            changed = dict(self.passport); changed[key] = value
            path.write_text(json.dumps(changed))
            with self.subTest(key=key), self.assertRaises(ValueError): distribution.load_release(self.root)
        self.manifest['artifacts']['candidate_zip']['path'] = '../candidate.zip'
        self.write()
        with self.assertRaises(ValueError): distribution.load_release(self.root)
