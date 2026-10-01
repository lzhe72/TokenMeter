"""Focused negative checks for the local product runner; these are not App E2E."""
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler, urlopen

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('local_e2e_test', ROOT / 'scripts/local_e2e.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class WorkbookArchiveTests(unittest.TestCase):
    def test_final_supplemental_requires_distinct_bound_parent_candidate_and_dmg(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();manifest=root/'package-manifest.json';manifest.write_text('{}')
            dmg=root/'candidate.dmg';dmg.write_bytes(b'fixed candidate')
            package={'candidate_tree':'b'*40,'release_id':'v0.1.0-20260929T074814Z',
                     'app':{'tree_sha256':'c'*64}}
            parent={'run_id':'local-'+'a'*32,'scope':'granular_final_package','state':'BLOCKED',
                    'cleanup_completed':True,'source_commit':'d'*40,
                    'candidate_tree':package['candidate_tree'],'release_id':package['release_id'],
                    'package':{'manifest_sha256':runner.digest(manifest),'dmg_sha256':runner.digest(dmg),
                               'app_tree_sha256':'c'*64,'installed_source':'final_dmg'}}
            source=root/'detail.json';source.write_text(json.dumps(parent))
            binding=runner.bind_parent_report(source,run_id='local-'+'e'*32,
                        candidate_sha='d'*40,package=package,manifest=manifest,dmg=dmg)
            self.assertEqual(binding['parent_run_id'],parent['run_id'])
            self.assertEqual(binding['parent_report_sha256'],runner.digest(source))
            for label,edited,aggregate_id in (
                ('same run ID',parent,parent['run_id']),
                ('foreign commit',{**parent,'source_commit':'f'*40},'local-'+'e'*32),
                ('foreign tree',{**parent,'candidate_tree':'f'*40},'local-'+'e'*32),
                ('foreign DMG',{**parent,'package':{**parent['package'],'dmg_sha256':'f'*64}},'local-'+'e'*32),
            ):
                source.write_text(json.dumps(edited))
                with self.subTest(label=label),self.assertRaises(runner.Failed):
                    runner.bind_parent_report(source,run_id=aggregate_id,candidate_sha='d'*40,
                                              package=package,manifest=manifest,dmg=dmg)
            with self.assertRaises(runner.Blocked):
                runner.bind_parent_report(None,run_id='local-'+'e'*32,candidate_sha='d'*40,
                                          package=package,manifest=manifest,dmg=dmg)

    def test_every_product_state_exports_without_changing_original_result(self):
        for state, code in [('PASS', 0), ('FAIL', 1), ('BLOCKED', 2)]:
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temp:
                target = Path(temp) / 'result.json'
                report = {'state': state, 'run_id': 'local-' + 'a' * 32}
                def export(path):
                    self.assertEqual(json.loads(path.read_text()), report)
                    return {'state': 'PASS'}
                with patch.object(runner, 'export_workbook', side_effect=export) as exporter:
                    self.assertEqual(runner.finish_result(target, report), code)
                exporter.assert_called_once_with(target)
                self.assertEqual(json.loads(target.read_text()), report)

    def test_export_failure_prevents_success_without_rewriting_product_pass(self):
        for archive_state, code in [('FAIL', 1), ('BLOCKED', 2)]:
            with self.subTest(archive_state=archive_state), tempfile.TemporaryDirectory() as temp:
                target = Path(temp) / 'result.json'
                with patch.object(runner, 'export_workbook', return_value={'state': archive_state, 'error': 'test fixture'}):
                    self.assertEqual(runner.finish_result(target, {'state': 'PASS'}), code)
                self.assertEqual(json.loads(target.read_text())['state'], 'PASS')

    def args(self, base):
        base = base.resolve()
        return SimpleNamespace(output=base / 'new-run', development=True, run_id='local-' + 'a' * 32,
                               candidate_sha='a' * 40, package_manifest=base / 'manifest.json',
                               dmg=base / 'test.dmg', update_zip=base / 'test.zip')

    def test_blocked_preflight_and_cleanup_exception_still_export(self):
        with tempfile.TemporaryDirectory() as temp:
            args = self.args(Path(temp))
            with patch.object(runner, 'export_workbook', return_value={'state': 'PASS'}) as exporter, \
                 patch.object(runner, 'cleanup_owned_shipit', side_effect=OSError('synthetic cleanup failure')):
                self.assertEqual(runner.execute(args), 2)
            exporter.assert_called_once_with(args.output / 'result.json')
            report = json.loads((args.output / 'result.json').read_text())
            self.assertEqual(report['state'], 'BLOCKED')
            self.assertEqual(report['executed_cases'], 0)
            self.assertFalse(report['cleanup']['shipit'])
            self.assertIn('synthetic cleanup failure', report['cleanup_errors'][0])

    def test_six_group_report_binds_shipit_cleanup_stage_and_preference_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            args = self.args(Path(temp))
            def cleanup(cache, run_id, app, evidence):
                self.assertEqual(run_id, args.run_id)
                runner.write_json(evidence / 'cleanup-stage.json', {'state': 'PASS', 'run_id': run_id})
                (evidence / (runner.SHIPIT_LABEL + '.owned.plist')).write_bytes(plistlib.dumps({}))
                return True
            with patch.object(runner, 'export_workbook', return_value={'state': 'PASS'}), \
                 patch.object(runner, 'cleanup_owned_shipit', side_effect=cleanup):
                self.assertEqual(runner.execute(args), 2)
            report = json.loads((args.output / 'result.json').read_text())
            self.assertEqual(report['state'], 'BLOCKED')  # The package preflight was intentionally absent.
            evidence = report['shipit_cleanup_evidence']
            self.assertEqual(evidence['diagnostic']['path'], 'shipit-cleanup/cleanup-stage.json')
            self.assertEqual(len(evidence['owned_empty_preferences']), 1)
            for item in [evidence['diagnostic'], *evidence['owned_empty_preferences']]:
                source = args.output / item['path']
                self.assertEqual(item['sha256'], hashlib.sha256(source.read_bytes()).hexdigest())

    def test_interrupted_preflight_is_recorded_without_starting_app(self):
        with tempfile.TemporaryDirectory() as temp:
            args = self.args(Path(temp))
            for f in [args.package_manifest, args.dmg, args.update_zip]:
                f.write_text('synthetic fixture')
            with patch.object(runner, 'verify_host_and_manifest', side_effect=KeyboardInterrupt), \
                 patch.object(runner, 'export_workbook', return_value={'state': 'PASS'}) as exporter:
                self.assertEqual(runner.execute(args), 2)
            exporter.assert_called_once()
            report = json.loads((args.output / 'result.json').read_text())
            self.assertIn('interrupted', report['error'])
            self.assertEqual(report['executed_cases'], 0)

    def test_existing_output_is_not_exported_or_modified(self):
        with tempfile.TemporaryDirectory() as temp:
            args = self.args(Path(temp))
            args.output.mkdir()
            marker = args.output / 'result.json'; marker.write_text('previous evidence')
            with patch.object(runner, 'export_workbook') as exporter:
                with self.assertRaises(runner.Blocked):
                    runner.execute(args)
            exporter.assert_not_called()
            self.assertEqual(marker.read_text(), 'previous evidence')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class LocalFixtureTests(unittest.TestCase):
    def setUp(self):
        # Production waits for macOS launchd/CFPreferences quiescence. Keep
        # governance fixtures bounded without changing the production values.
        for name, value in (('SHIPIT_QUIESCENCE_SECONDS', 0.03),
                            ('SHIPIT_TEARDOWN_TIMEOUT_SECONDS', 0.25),
                            ('SHIPIT_POLL_SECONDS', 0.005)):
            patcher = patch.object(runner, name, value, create=True)
            patcher.start(); self.addCleanup(patcher.stop)

    def test_package_versions_are_bound_to_approved_release_config(self):
        releases = (
            ('v0.1.0-20260929T074814Z', '0.1.0', '100', '0.1.1', '101'),
            ('v0.2.0-20261001T034118Z', '0.2.0', '200', '0.2.1', '201'),
        )
        for release_id, app_version, app_build, update_version, update_build in releases:
            with self.subTest(release_id=release_id):
                config = ROOT / 'releases' / release_id / 'local-release.json'
                package = {'release_id': release_id, 'config_sha256': runner.digest(config),
                           'distribution_profile': 'internal',
                           'app': {'version': app_version, 'build': app_build,
                                   'bundle_id': 'org.tokenmeter.TokenMeter'},
                           'update_app': {'version': update_version, 'build': update_build,
                                          'bundle_id': 'org.tokenmeter.TokenMeter'}}
                approved = runner.approved_release_config(package)
                self.assertEqual((approved['version'], approved['build'],
                                  approved['upgrade_version'], approved['upgrade_build']),
                                 (app_version, app_build, update_version, update_build))
                for changed in (
                    {**package, 'config_sha256': '0' * 64},
                    {**package, 'app': {**package['app'], 'build': update_build}},
                    {**package, 'update_app': {**package['update_app'], 'version': app_version}},
                    {**package, 'release_id': release_id.replace('v', 'foreign/', 1)},
                ):
                    with self.assertRaises(runner.Failed):
                        runner.approved_release_config(changed)

    def test_copied_v02_app_requires_its_manifest_version_and_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / 'install' / 'TokenMeter.app'
            package = {'app': {'tree_sha256': 'a' * 64,
                               'designated_requirement': 'identifier "org.tokenmeter.TokenMeter"',
                               'version': '0.2.0', 'build': '200',
                               'bundle_id': 'org.tokenmeter.TokenMeter'}}
            tree = SimpleNamespace(tree_sha256=lambda _: 'a' * 64)
            details = {'CFBundleShortVersionString': '0.2.0', 'CFBundleVersion': '200',
                       'CFBundleIdentifier': 'org.tokenmeter.TokenMeter'}
            def command(argv, **_):
                if argv[0] == 'ditto': app.mkdir(parents=True, exist_ok=True)
                return subprocess.CompletedProcess(argv, 0,
                    details[argv[2]] if argv[0] == 'plutil' else '', '')
            with patch.object(runner, 'command', side_effect=command):
                self.assertEqual(runner.copy_verified_app(root / 'source', app, package,
                    tree, root / 'install.log'), app)
                details['CFBundleVersion'] = '100'
                with self.assertRaises(runner.Failed):
                    runner.copy_verified_app(root / 'source', app, package,
                        tree, root / 'install.log')

    def test_shipit_launchctl_unknown_status_does_not_mean_job_absent(self):
        absent = subprocess.CompletedProcess([], 113, '', 'Could not find service')
        unknown = subprocess.CompletedProcess([], 1, '', 'Permission denied')
        with patch.object(runner.subprocess, 'run', return_value=absent):
            self.assertFalse(runner._shipit_job_present())
        with patch.object(runner.subprocess, 'run', return_value=unknown):
            with self.assertRaises(runner.Blocked): runner._shipit_job_present()

    def test_shipit_cleanup_waits_for_owned_job_after_nonzero_remove(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp); run_id = 'local-' + '5'*32
            (home / 'Library/Caches').mkdir(parents=True)
            app = home / 'install/TokenMeter.app'; app.mkdir(parents=True)
            evidence = home / 'evidence'
            calls = 0
            def job_present():
                nonlocal calls
                calls += 1
                return calls == 2
            with patch.object(runner.Path, 'home', return_value=home), \
                 patch.object(runner, '_shipit_job_present', side_effect=job_present):
                cache = runner.prepare_owned_shipit(run_id)
                (cache / 'ShipItState.plist').write_text(json.dumps({'targetBundleURL': app.as_uri()}))
                response = subprocess.CompletedProcess(['launchctl', 'remove', runner.SHIPIT_LABEL], 1,
                    '', 'Service was already exiting')
                with patch.object(runner.subprocess, 'run', return_value=response) as remove:
                    self.assertTrue(runner.cleanup_owned_shipit(cache, run_id, app, evidence))
                remove.assert_called_once_with(['launchctl', 'remove', runner.SHIPIT_LABEL],
                    capture_output=True, text=True, check=False)
            self.assertFalse(cache.exists())
            self.assertEqual(json.loads((evidence / 'cleanup-stage.json').read_text())['state'], 'PASS')

    def test_shipit_cleanup_waits_for_state_before_touching_owned_job(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp); run_id = 'local-' + '6'*32
            (home / 'Library/Caches').mkdir(parents=True)
            app = home / 'install/TokenMeter.app'; app.mkdir(parents=True)
            evidence = home / 'evidence'; calls = 0
            with patch.object(runner.Path, 'home', return_value=home), \
                 patch.object(runner, '_shipit_job_present', return_value=False):
                cache = runner.prepare_owned_shipit(run_id)
            state = cache / 'ShipItState.plist'
            def job_present():
                nonlocal calls
                calls += 1
                if calls == 2: state.write_text(json.dumps({'targetBundleURL': app.as_uri()}))
                return calls <= 2
            with patch.object(runner.Path, 'home', return_value=home), \
                 patch.object(runner, '_shipit_job_present', side_effect=job_present), \
                 patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as remove:
                self.assertTrue(runner.cleanup_owned_shipit(cache, run_id, app, evidence))
                remove.assert_called_once()
            self.assertFalse(cache.exists())
            self.assertEqual(json.loads((evidence / 'cleanup-stage.json').read_text())['state'], 'PASS')

    def test_shipit_cleanup_waits_for_partial_state_before_touching_owned_job(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp); run_id = 'local-' + '9'*32
            (home / 'Library/Caches').mkdir(parents=True)
            app = home / 'install/TokenMeter.app'; app.mkdir(parents=True)
            evidence = home / 'evidence'
            with patch.object(runner.Path, 'home', return_value=home), \
                 patch.object(runner, '_shipit_job_present', return_value=False):
                cache = runner.prepare_owned_shipit(run_id)
            state = cache / 'ShipItState.plist'; state.write_text('{')
            calls = 0
            def job_present():
                nonlocal calls
                calls += 1
                if calls == 2: state.write_text(json.dumps({'targetBundleURL': app.as_uri()}))
                return calls <= 2
            with patch.object(runner.Path, 'home', return_value=home), \
                 patch.object(runner, '_shipit_job_present', side_effect=job_present), \
                 patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as remove:
                self.assertTrue(runner.cleanup_owned_shipit(cache, run_id, app, evidence))
                remove.assert_called_once()
            self.assertFalse(cache.exists())
            self.assertEqual(json.loads((evidence / 'cleanup-stage.json').read_text())['state'], 'PASS')

    def test_shipit_cleanup_never_removes_unknown_target_job(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp); run_id = 'local-' + '7'*32
            (home / 'Library/Caches').mkdir(parents=True)
            app = home / 'install/TokenMeter.app'; app.mkdir(parents=True)
            other = home / 'other/TokenMeter.app'; other.mkdir(parents=True)
            evidence = home / 'evidence'
            with patch.object(runner.Path, 'home', return_value=home), \
                 patch.object(runner, '_shipit_job_present', return_value=False):
                cache = runner.prepare_owned_shipit(run_id)
            (cache / 'ShipItState.plist').write_text(json.dumps({'targetBundleURL': other.as_uri()}))
            with patch.object(runner, '_shipit_job_present', return_value=True), \
                 patch.object(runner.subprocess, 'run') as remove:
                self.assertFalse(runner.cleanup_owned_shipit(cache, run_id, app, evidence))
                remove.assert_not_called()
            self.assertTrue(cache.exists())
            diagnostic = json.loads((evidence / 'cleanup-stage.json').read_text())
            self.assertEqual(diagnostic['state'], 'FAIL')
            self.assertEqual(diagnostic['stages'][-1]['reason'], 'shipit_state_target_unverified')

    def test_shipit_cleanup_collects_late_owned_empty_preference(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp); run_id = 'local-' + '8'*32
            (home / 'Library/Caches').mkdir(parents=True)
            byhost = home / 'Library/Preferences/ByHost'; byhost.mkdir(parents=True)
            app = home / 'install/TokenMeter.app'; app.mkdir(parents=True)
            evidence = home / 'evidence'
            with patch.object(runner.Path, 'home', return_value=home), \
                 patch.object(runner, '_shipit_job_present', return_value=False):
                cache = runner.prepare_owned_shipit(run_id)
                (cache / 'ShipItState.plist').write_text(json.dumps({'targetBundleURL': app.as_uri()}))
            preference = byhost / (runner.SHIPIT_LABEL + '.owned.plist')
            calls = 0
            def late_preference():
                nonlocal calls
                calls += 1
                if calls == 3: preference.write_bytes(plistlib.dumps({}))
                return [preference] if preference.exists() else []
            with patch.object(runner.Path, 'home', return_value=home), \
                 patch.object(runner, '_shipit_job_present', return_value=False), \
                 patch.object(runner, '_shipit_byhost_preferences', side_effect=late_preference), \
                 patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')):
                self.assertTrue(runner.cleanup_owned_shipit(cache, run_id, app, evidence))
            self.assertFalse(cache.exists())
            self.assertFalse(preference.exists())
            self.assertEqual(plistlib.loads((evidence / preference.name).read_bytes()), {})

    def test_slow_source_releases_exact_archive_only_with_owned_control(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'update.zip'; archive.write_bytes(b'fixed signed archive bytes' * 2048)
            fixture = runner.UpdateFixture(archive, {'signatures': {'update_ed_signature': base64.b64encode(b'a'*64).decode()},
                                                     'update_app': {'version': '0.1.1', 'build': '101'}})
            received = []
            errors = []
            def control(stage, authenticated=True):
                return urlopen(Request(fixture.url + '/control/' + stage, method='POST',
                    headers={'Authorization': 'Bearer ' + fixture.token} if authenticated else {}), timeout=5)
            def download():
                try:
                    with urlopen(fixture.url + '/update.zip', timeout=10) as response: received.append(response.read())
                except Exception as error: errors.append(str(error))
            worker = None
            try:
                with control('release-slow') as response: self.fail('release without wait must be refused')
            except HTTPError as error: self.assertEqual(error.code, 409)
            try:
                with control('slow') as response: self.assertEqual(response.status, 200)
                worker = threading.Thread(target=download); worker.start()
                self.assertTrue(fixture.slow_waiting.wait(5))
                with self.assertRaises(HTTPError) as denied: control('release-slow', False)
                self.assertEqual(denied.exception.code, 403)
                self.assertEqual(received, [])
                with control('release-slow') as response:
                    self.assertEqual(json.load(response), {'stage': 'slow-released', 'nonce': fixture.nonce})
                worker.join(5)
                self.assertFalse(worker.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(received, [archive.read_bytes()])
                self.assertEqual(fixture.stage, 'slow')
            finally:
                self.assertTrue(fixture.close())
                if worker: worker.join(5)

    def test_development_package_never_passes_formal_manifest_check(self):
        for release, version, build, upgrade_version, upgrade_build in (
            ('v0.1.0-20260929T074814Z', '0.1.0', '100', '0.1.1', '101'),
            ('v0.2.0-20261001T034118Z', '0.2.0', '200', '0.2.1', '201'),
        ):
            with self.subTest(release=release), tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                dmg = base / 'candidate.dmg'; dmg.write_bytes(b'private synthetic DMG')
                update = base / 'update.zip'; update.write_bytes(b'private synthetic ZIP')
                manifest = base / 'package-manifest.json'
                def item(path): return {'path':path.name,'sha256':runner.digest(path),'bytes':path.stat().st_size}
                config = ROOT / 'releases' / release / 'local-release.json'
                manifest.write_text(json.dumps({'schema_version':2,'scope':'development','candidate_sha':'a'*40,
                    'working_tree_dirty':True,'release_id':release,'config_sha256':runner.digest(config),
                    'distribution_profile':'internal',
                    'artifacts':{'dmg':item(dmg),'update_zip':item(update)},
                    'app':{'version':version,'build':build,'bundle_id':'org.tokenmeter.TokenMeter'},
                    'update_app':{'version':upgrade_version,'build':upgrade_build,
                                  'bundle_id':'org.tokenmeter.TokenMeter'}}))
                with patch.object(runner.platform,'system',return_value='Darwin'),patch.object(runner.platform,'machine',return_value='x86_64'),\
                     patch.object(runner.platform,'mac_ver',return_value=('15.7.4',('', '', ''),'x86_64')):
                    with self.assertRaises(runner.Failed):
                        runner.verify_host_and_manifest(manifest,dmg.resolve(),update.resolve(),'a'*40)
                    self.assertEqual(runner.verify_host_and_manifest(manifest,dmg.resolve(),update.resolve(),'a'*40,
                        development=True)['scope'],'development')

    def test_service_readiness_failure_closes_owned_listener_and_reader(self):
        class ExitedProcess:
            stdout = io.StringIO('')
            def poll(self): return 1
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / 'accounts.sqlite'; database.write_bytes(b'fixture path only')
            with patch.object(runner.subprocess, 'Popen', return_value=ExitedProcess()):
                with self.assertRaises(runner.Blocked):
                    runner.Service(database, Path(temp))
            # The failed constructor must leave no running reader or service socket.
            self.assertEqual(len(list(Path(temp).glob('service-*.log'))), 1)

    def test_service_spawn_failure_closes_reserved_socket(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / 'accounts.sqlite'; database.write_bytes(b'fixture path only')
            created = []
            original = runner.socket.socket
            def watched(*args, **kwargs):
                sock = original(*args, **kwargs); created.append(sock); return sock
            with patch.object(runner.socket, 'socket', side_effect=watched), patch.object(runner.subprocess,'Popen',side_effect=OSError('no spawn')):
                with self.assertRaises(OSError): runner.Service(database, Path(temp))
            self.assertTrue(created[0].fileno() == -1)

    def test_stage_responses_and_request_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'update.zip'; archive.write_bytes(b'zip payload' * 1024)
            signature = base64.b64encode(b'x' * 64).decode()
            fixture = runner.UpdateFixture(archive, {'signatures': {'update_ed_signature': signature},
                                                     'update_app': {'version': '0.1.1', 'build': '101'}})
            try:
                with urlopen(fixture.url + '/version.json') as response:
                    self.assertEqual(response.status, 204)
                for stage in ('forbidden', 'redirect', 'invalid', 'valid'):
                    control = Request(fixture.url + '/control/' + stage, method='POST',
                                      headers={'Authorization': 'Bearer ' + fixture.token})
                    with urlopen(control) as response: self.assertEqual(response.status, 200)
                    with urlopen(fixture.url + '/version.json') as response: metadata = json.load(response)
                    self.assertEqual(metadata['sha256'], hashlib.sha256(archive.read_bytes()).hexdigest())
                    self.assertEqual(metadata['bytes'], archive.stat().st_size)
                    if stage == 'forbidden':
                        self.assertEqual(metadata['url'], 'http://example.invalid/update.zip')
                    elif stage == 'redirect':
                        opener = build_opener(NoRedirect())
                        with self.assertRaises(HTTPError) as redirected:
                            opener.open(metadata['url'])
                        self.assertEqual(redirected.exception.code, 302)
                        self.assertEqual(redirected.exception.headers['Location'], 'http://example.invalid/update.zip')
                    else:
                        with urlopen(metadata['url']) as response: self.assertEqual(response.read(), archive.read_bytes())
                        self.assertEqual(metadata['ed25519_signature'] == signature, stage == 'valid')
                actual = fixture.requests
                self.assertEqual([r['stage'] for r in actual if r['route'] == '/version.json'],
                                 ['current', 'forbidden', 'redirect', 'invalid', 'valid'])
                for entry in actual:
                    self.assertEqual(len(entry['body_sha256']), 64)
                    self.assertIsInstance(entry['bytes_sent'], int)
                self.assertEqual([r['bytes_sent'] for r in actual if r['route'] == '/update.zip'],
                                 [archive.stat().st_size, archive.stat().st_size])
            finally:
                self.assertTrue(fixture.close())

    def test_control_requires_token_and_existing_shipit_is_never_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'update.zip'; archive.write_bytes(b'zip')
            fixture = runner.UpdateFixture(archive, {'signatures': {'update_ed_signature': base64.b64encode(b'a'*64).decode()},
                                                     'update_app': {'version': '0.1.1', 'build': '101'}})
            try:
                with self.assertRaises(HTTPError) as denied:
                    urlopen(Request(fixture.url + '/control/valid', method='POST'))
                self.assertEqual(denied.exception.code, 403)
                self.assertEqual(fixture.stage, 'current')
            finally: fixture.close()
            cache = Path(temp) / 'Library/Caches' / runner.SHIPIT_LABEL
            cache.mkdir(parents=True)
            (cache / 'unknown-user-file').write_text('preserve')
            with patch.object(runner.Path, 'home', return_value=Path(temp)), patch.object(runner, '_shipit_job_present', return_value=False):
                with self.assertRaises(runner.Blocked): runner.prepare_owned_shipit('local-' + '1'*32)
            self.assertEqual((cache / 'unknown-user-file').read_text(), 'preserve')

    def test_shipit_cleanup_needs_bound_target_before_touching_job(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp); run_id = 'local-' + '1'*32
            (home / 'Library/Caches').mkdir(parents=True)
            with patch.object(runner.Path, 'home', return_value=home), patch.object(runner, '_shipit_job_present', return_value=False):
                cache = runner.prepare_owned_shipit(run_id)
            app = home / 'install/TokenMeter.app'; app.mkdir(parents=True)
            # A job without state could belong to another App, even with our marker.
            with patch.object(runner, '_shipit_job_present', return_value=True), patch.object(runner.subprocess, 'run') as remove:
                self.assertFalse(runner.cleanup_owned_shipit(cache, run_id, app))
                remove.assert_not_called()
            self.assertTrue(cache.exists())
            (cache / 'ShipItState.plist').write_text(json.dumps({'targetBundleURL': app.as_uri()}))
            with patch.object(runner.Path, 'home', return_value=home), patch.object(runner, '_shipit_job_present', return_value=False):
                self.assertTrue(runner.cleanup_owned_shipit(cache, run_id, app))
            self.assertFalse(cache.exists())

    def test_shipit_cleanup_accepts_absent_domain_for_owned_empty_byhost_plist(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp); run_id = 'local-' + '2'*32
            (home / 'Library/Caches').mkdir(parents=True)
            byhost = home / 'Library/Preferences/ByHost'; byhost.mkdir(parents=True)
            app = home / 'install/TokenMeter.app'; app.mkdir(parents=True)
            evidence = home / 'evidence'
            with patch.object(runner.Path, 'home', return_value=home), \
                 patch.object(runner, '_shipit_job_present', return_value=False):
                cache = runner.prepare_owned_shipit(run_id)
                (cache / 'ShipItState.plist').write_text(json.dumps({'targetBundleURL': app.as_uri()}))
                preference = byhost / (runner.SHIPIT_LABEL + '.owned.plist')
                preference.write_bytes(plistlib.dumps({}))
                response = subprocess.CompletedProcess(['defaults', '-currentHost', 'delete', runner.SHIPIT_LABEL], 1,
                    '', 'Domain (' + runner.SHIPIT_LABEL + ') does not exist\nDefaults have not been changed.\n')
                with patch.object(runner.subprocess, 'run', return_value=response) as defaults:
                    self.assertTrue(runner.cleanup_owned_shipit(cache, run_id, app, evidence))
                defaults.assert_called_once_with(['defaults', '-currentHost', 'delete', runner.SHIPIT_LABEL],
                    capture_output=True, text=True, check=False)
            self.assertFalse(cache.exists())
            self.assertFalse(preference.exists())
            self.assertEqual(plistlib.loads((evidence / preference.name).read_bytes()), {})

    def test_shipit_cleanup_rejects_old_nonempty_or_foreign_byhost_state(self):
        for kind in ('old', 'nonempty', 'foreign_marker'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                home = Path(temp); run_id = 'local-' + '3'*32
                (home / 'Library/Caches').mkdir(parents=True)
                byhost = home / 'Library/Preferences/ByHost'; byhost.mkdir(parents=True)
                app = home / 'install/TokenMeter.app'; app.mkdir(parents=True)
                with patch.object(runner.Path, 'home', return_value=home), \
                     patch.object(runner, '_shipit_job_present', return_value=False):
                    cache = runner.prepare_owned_shipit(run_id)
                    (cache / 'ShipItState.plist').write_text(json.dumps({'targetBundleURL': app.as_uri()}))
                    preference = byhost / (runner.SHIPIT_LABEL + '.owned.plist')
                    preference.write_bytes(plistlib.dumps({'other': 'owner'} if kind == 'nonempty' else {}))
                    if kind == 'old':
                        marker_time = (cache / '.tokenmeter-owner.json').stat().st_mtime
                        os.utime(preference, (marker_time - 60, marker_time - 60))
                    if kind == 'foreign_marker':
                        (cache / '.tokenmeter-owner.json').write_text(json.dumps({'owner': 'foreign', 'run_id': run_id}))
                    with patch.object(runner.subprocess, 'run') as defaults:
                        self.assertFalse(runner.cleanup_owned_shipit(cache, run_id, app))
                        defaults.assert_not_called()
                self.assertTrue(cache.exists())
                self.assertTrue(preference.exists())

    def test_shipit_cleanup_rejects_unrelated_defaults_error(self):
        for stderr in ('Unrelated preference not found', 'Domain (other.bundle.ShipIt) does not exist'):
            with self.subTest(stderr=stderr), tempfile.TemporaryDirectory() as temp:
                home = Path(temp); run_id = 'local-' + '4'*32
                (home / 'Library/Caches').mkdir(parents=True)
                byhost = home / 'Library/Preferences/ByHost'; byhost.mkdir(parents=True)
                app = home / 'install/TokenMeter.app'; app.mkdir(parents=True)
                with patch.object(runner.Path, 'home', return_value=home), \
                     patch.object(runner, '_shipit_job_present', return_value=False):
                    cache = runner.prepare_owned_shipit(run_id)
                    (cache / 'ShipItState.plist').write_text(json.dumps({'targetBundleURL': app.as_uri()}))
                    preference = byhost / (runner.SHIPIT_LABEL + '.owned.plist')
                    preference.write_bytes(plistlib.dumps({}))
                    response = subprocess.CompletedProcess(['defaults', '-currentHost', 'delete', runner.SHIPIT_LABEL], 1,
                        '', stderr)
                    with patch.object(runner.subprocess, 'run', return_value=response) as defaults:
                        self.assertFalse(runner.cleanup_owned_shipit(cache, run_id, app))
                    defaults.assert_called_once()
                self.assertTrue(cache.exists())
                self.assertTrue(preference.exists())


if __name__ == '__main__': unittest.main()
