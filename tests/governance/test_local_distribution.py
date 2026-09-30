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
        self.root = Path(self.temp.name)
        self.rid = 'v0.1.0-20260929T074814Z'
        self.candidate = b'synthetic fixture zip; never a product artifact'
        (self.root / 'candidate.zip').write_bytes(self.candidate)
        self.manifest = {'release_id': self.rid, 'candidate_sha': 'a'*40,
            'distribution_profile': 'internal', 'app': {'build': '100', 'version': '0.1.0', 'minimum_macos': '15.0'},
            'artifacts': {'candidate_zip': {'path': 'candidate.zip', 'sha256': hashlib.sha256(self.candidate).hexdigest(), 'bytes': len(self.candidate)}},
            'signatures': {'candidate_ed_signature': base64.b64encode(bytes(64)).decode()}}
        self.write()

    def write(self):
        (self.root / 'package-manifest.json').write_text(json.dumps(self.manifest))
        self.passport = {'state': 'PASS', 'release_eligible': True, 'release_id': self.rid,
            'distribution_profile': 'internal', 'candidate_sha': 'a'*40,
            'package_manifest_sha256': hashlib.sha256((self.root / 'package-manifest.json').read_bytes()).hexdigest()}
        (self.root / (self.rid+'.passport.json')).write_text(json.dumps(self.passport))

    def test_serves_only_candidate_and_correct_stable_version(self):
        bundle = distribution.load_release(self.root)
        routes = distribution.routes_for(bundle)
        self.assertEqual(set(routes), {'/appcast.xml', '/candidate.zip', '/healthz'})
        self.assertEqual(routes['/candidate.zip'][1], self.candidate)
        self.assertIn(b'<sparkle:version>100</sparkle:version>', routes['/appcast.xml'][1])
        self.assertNotIn(b'101', routes['/appcast.xml'][1])
        self.assertIn(b'http://127.0.0.1:49177/candidate.zip', routes['/appcast.xml'][1])

    def test_changed_zip_or_manifest_is_refused(self):
        (self.root / 'candidate.zip').write_bytes(b'changed')
        with self.assertRaises(ValueError): distribution.load_release(self.root)
        (self.root / 'candidate.zip').write_bytes(self.candidate)
        (self.root / 'package-manifest.json').write_text(json.dumps(self.manifest)+' ')
        with self.assertRaises(ValueError): distribution.load_release(self.root)

    def test_no_passport_no_release(self):
        (self.root / (self.rid+'.passport.json')).unlink()
        with self.assertRaises((ValueError, OSError)): distribution.load_release(self.root)

    def test_wrong_candidate_blocked_passport_and_escape_are_refused(self):
        path = self.root / (self.rid+'.passport.json')
        for key, value in [('state', 'BLOCKED'), ('candidate_sha', 'b'*40), ('release_eligible', False), ('distribution_profile','public')]:
            changed = dict(self.passport); changed[key] = value
            path.write_text(json.dumps(changed))
            with self.subTest(key=key), self.assertRaises(ValueError): distribution.load_release(self.root)
        self.manifest['artifacts']['candidate_zip']['path'] = '../candidate.zip'
        self.write()
        with self.assertRaises(ValueError): distribution.load_release(self.root)
