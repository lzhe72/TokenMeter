"""Negative checks for native evidence; these synthetic objects are not App E2E."""
import copy
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import plistlib
import socket
import sqlite3
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("native_e2e", ROOT / "scripts/native_e2e.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "releases/v0.1.0-20260929T074814Z").mkdir(parents=True)
        (self.root / "tests").mkdir()
        self.write("releases/current.json", {"release_id": "v0.1.0-20260929T074814Z"})
        self.write("releases/v0.1.0-20260929T074814Z/00-manifest.json", {"feature_ids": ["TM-001"]})
        self.features = [
            {"id": "TM-001", "status": "planned", "cases": [{"id": "E2E-TM001-001", "native_test": "TokenMeterUITests/TM001AccountUITests/testE2E_TM001_001"}]},
            {"id": "TM-002", "status": "implemented", "cases": [{"id": "E2E-TM002-001", "native_test": "TokenMeterUITests/TM002UITests/testE2E_TM002_001"}]},
            {"id": "TM-003", "status": "planned", "cases": [{"id": "E2E-TM003-001"}]},
        ]
        self.write("tests/feature_matrix.json", {"features": self.features})
        self.tree = {"testNodes": [{"nodeType": "Test Bundle", "name": "TokenMeterUITests", "children": [
            {"nodeType": "Test Suite", "name": "TM001AccountUITests", "children": [
                {"nodeType": "Test Case", "name": "testE2E_TM001_001()", "nodeIdentifier": "TM001AccountUITests/testE2E_TM001_001()", "result": "Passed"}
            ]}
        ]}]}
        self.summary = {"totalTestCount": 1, "passedTests": 1, "failedTests": 0, "skippedTests": 0, "testFailures": [], "result": "Passed"}
        self.identity = "TokenMeterUITests/TM001AccountUITests/testE2E_TM001_001"

    def write(self, path, value):
        (self.root / path).write_text(json.dumps(value))

    def test_target_planned_is_not_excluded_and_delivered_is_regressed(self):
        self.assertEqual(set(native.required_cases(self.root)), {"E2E-TM001-001", "E2E-TM002-001"})

    def test_fixture_profiles_keep_upgrade_case_and_add_production_bootstrap(self):
        for index in range(1, 5):
            self.assertEqual(native.fixture_profile(f"E2E-TM001-{index:03d}"), "synthetic_accounts")
        self.assertEqual(native.fixture_profile("E2E-TM001-005"), "production_bootstrap")
        self.assertEqual(native.fixture_profile("E2E-TM001-006"), "dual_service_routes")
        with self.assertRaises(native.Blocked):
            native.fixture_profile("E2E-TM001-007")

    def test_dual_service_data_has_two_owned_databases_and_distinct_credentials(self):
        account_data = native.load_module(ROOT / "tests/server/fixtures.py", "native_account_fixture_test")
        case_output = self.root / "case-output"
        case_output.mkdir()
        primary = self.root.resolve() / "case-private"
        secondary = primary / "secondary"
        secondary.mkdir(parents=True)
        calls = []
        def cli(arguments, **kwargs):
            calls.append(arguments)
            return mock.Mock(returncode=0)
        with mock.patch.object(native, "command", side_effect=cli):
            first_database, first_fixture = native.prepare_account_database(
                ROOT, primary, case_output, account_data, "route-primary", 42)
            second_database, second_fixture = native.prepare_account_database(
                ROOT, secondary, case_output, account_data, "route-secondary", 43, suffix="-secondary")
        self.assertNotEqual(first_database, second_database)
        self.assertEqual(len(calls), 4)
        self.assertEqual(json.loads((primary / ".tokenmeter-test-database.json").read_text())["run_id"], "route-primary")
        self.assertEqual(json.loads((secondary / ".tokenmeter-test-database.json").read_text())["run_id"], "route-secondary")
        primary_users = json.loads((first_fixture / "users.json").read_text())["users"]
        secondary_users = json.loads((second_fixture / "users.json").read_text())["users"]
        self.assertEqual(primary_users[1]["password"], "TEST-ONLY-alice-42!")
        self.assertEqual(secondary_users[1]["password"], "TEST-ONLY-alice-43!")
        manifest = native.write_dual_service_manifest(case_output, first_fixture, second_fixture,
                                                      "route-primary", "route-secondary")
        self.assertEqual(json.loads(manifest.read_text())["default_port"], 49176)
        self.assertNotIn("TEST-ONLY-", manifest.read_text())
        account_data.reset("route-primary", workspace=primary)
        account_data.reset("route-secondary", workspace=secondary)

    def test_reserved_port_never_connects_to_an_existing_service(self):
        private = self.root / "case-private"
        private.mkdir()
        database = private / "accounts.sqlite"
        database.write_bytes(b"isolated-test-file")
        log = self.root / "service.log"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as existing:
            existing.bind(("127.0.0.1", 0))
            existing.listen(1)
            with log.open("wb") as stream, mock.patch.object(native.subprocess, "Popen") as launch:
                with self.assertRaises(native.Blocked):
                    native.start_isolated_service(ROOT, private, database, stream,
                                                  port=existing.getsockname()[1])
                launch.assert_not_called()
        with log.open("wb") as stream, mock.patch.object(native.subprocess, "Popen") as launch:
            _, address, listener = native.start_isolated_service(ROOT, private, database, stream)
            try:
                self.assertTrue(address.startswith("http://127.0.0.1:"))
                arguments = launch.call_args.args[0]
                self.assertIn("--fd", arguments)
                self.assertNotIn("--host", arguments)
                self.assertEqual(launch.call_args.kwargs["env"]["TOKENMETER_DATABASE_URL"],
                                 "sqlite:///" + str(database))
                self.assertEqual(len(launch.call_args.kwargs["pass_fds"]), 1)
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as intruder:
                    with self.assertRaises(OSError):
                        intruder.bind(("127.0.0.1", int(address.rsplit(":", 1)[1])))
                with mock.patch.object(native, "urlopen") as probe:
                    with self.assertRaises(native.Blocked):
                        native.wait_for_service(mock.Mock(poll=mock.Mock(return_value=1)), address)
                    probe.assert_not_called()
            finally:
                listener.close()
        outside = self.root / "production.db"
        outside.write_bytes(b"not-an-owned-db")
        with log.open("wb") as stream, mock.patch.object(native.subprocess, "Popen") as launch:
            with self.assertRaises(native.EvidenceError):
                native.start_isolated_service(ROOT, private, outside, stream)
            launch.assert_not_called()

    def test_default_route_port_conflict_blocks_before_database_or_account_mutation(self):
        case_private = self.root.resolve() / "case-private"
        case_output = self.root.resolve() / "case-output"
        case_private.mkdir()
        case_output.mkdir()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as existing:
            existing.bind(("127.0.0.1", 0))
            existing.listen(1)
            with mock.patch.object(native, "prepare_account_database") as provision:
                with self.assertRaises(native.Blocked):
                    native.prepare_dual_service_databases(
                        ROOT, case_private, case_output, mock.Mock(), "route-primary",
                        port=existing.getsockname()[1])
                provision.assert_not_called()
        self.assertEqual(list(case_private.iterdir()), [])

    def test_default_route_bundle_rejects_stale_injected_api_url(self):
        app = self.root / "TokenMeter.app"
        (app / "Contents").mkdir(parents=True)
        info = app / "Contents/Info.plist"
        info.write_bytes(plistlib.dumps({"TMTestAPIURL": "", "TMTestRunID": "route-case"}))
        native.verify_default_route_bundle(app, "route-case")
        info.write_bytes(plistlib.dumps({"TMTestAPIURL": "http://127.0.0.1:12345", "TMTestRunID": "route-case"}))
        with self.assertRaises(native.EvidenceError):
            native.verify_default_route_bundle(app, "route-case")
        info.write_bytes(plistlib.dumps({"TMTestAPIURL": "", "TMTestRunID": "other-case"}))
        with self.assertRaises(native.EvidenceError):
            native.verify_default_route_bundle(app, "route-case")

    def test_each_case_uses_owned_private_credential_directory_and_exact_cleanup(self):
        case = self.root.resolve() / "case-private"
        case.mkdir(mode=0o700)
        credentials = native.prepare_test_credentials(case)
        self.assertEqual(credentials, case / "credentials")
        self.assertEqual(credentials.stat().st_mode & 0o777, 0o700)
        token = credentials / "one-origin.token"
        token.write_text("synthetic test-only token")
        token.chmod(0o600)
        native.clean_test_credentials(case, credentials)
        self.assertFalse(credentials.exists())
        self.assertFalse(token.exists())
        with self.assertRaises(native.EvidenceError):
            native.clean_test_credentials(case, credentials)
        case.chmod(0o1700)
        with self.assertRaises(native.EvidenceError):
            native.prepare_test_credentials(case)

    def test_credential_directory_rejects_alias_and_never_follows_file_symlink(self):
        case = self.root.resolve() / "case-private"
        case.mkdir(mode=0o700)
        alias = self.root.resolve() / "case-alias"
        alias.symlink_to(case, target_is_directory=True)
        with self.assertRaises(native.EvidenceError):
            native.prepare_test_credentials(alias)
        credentials = native.prepare_test_credentials(case)
        outside = self.root.resolve() / "outside-token"
        outside.write_text("must survive")
        (credentials / "link").symlink_to(outside)
        with self.assertRaises(native.EvidenceError):
            native.clean_test_credentials(case, credentials)
        self.assertEqual(outside.read_text(), "must survive")
        self.assertFalse(credentials.exists())

    def test_built_app_must_embed_exact_run_credential_directory(self):
        case = self.root.resolve() / "case-private"
        case.mkdir(mode=0o700)
        credentials = native.prepare_test_credentials(case)
        app = self.root / "TokenMeter.app"
        (app / "Contents").mkdir(parents=True)
        info = app / "Contents/Info.plist"
        info.write_bytes(plistlib.dumps({"TMTestRunID": "this-case",
                                        "TMTestCredentialsDirectory": str(credentials)}))
        native.verify_test_credentials_bundle(app, credentials, "this-case")
        info.write_bytes(plistlib.dumps({"TMTestRunID": "this-case",
                                        "TMTestCredentialsDirectory": str(case / "other")}))
        with self.assertRaises(native.EvidenceError):
            native.verify_test_credentials_bundle(app, credentials, "this-case")
        native.clean_test_credentials(case, credentials)

    def test_production_bootstrap_runner_confines_and_checks_database_evidence(self):
        # This stdlib fixture tests the runner contract. The real initializer is
        # exercised separately by server tests with its locked dependencies.
        def initialize(root):
            database = root / "database/production/production.db"
            database.parent.mkdir(parents=True, exist_ok=True)
            if database.exists():
                raise ValueError("Existing production database")
            with sqlite3.connect(database) as connection:
                connection.executescript("""
                    CREATE TABLE alembic_version (version_num TEXT);
                    INSERT INTO alembic_version VALUES ('0001');
                    CREATE TABLE tokenmeter_seed_owner (environment TEXT, run_id TEXT);
                    INSERT INTO tokenmeter_seed_owner VALUES ('production', 'production-init');
                    CREATE TABLE users (id TEXT, username TEXT, password_hash TEXT, role TEXT, is_active INTEGER,
                                        must_change_password INTEGER, credential_version INTEGER);
                    INSERT INTO users VALUES ('00000000-0000-4000-8000-000000000005', 'admin', 'synthetic', 'admin', 1, 1, 1);
                """)
            database.with_name("seed.sql").write_text("-- Synthetic governance fixture only\n")
            return {"environment": "production", "database": str(database), "schema_version": "0001", "accounts": 1}

        bootstrap = mock.Mock(initialize_production=initialize)
        case_private = self.root.resolve() / "case-private"
        case_output = self.root / "case-output"
        case_private.mkdir()
        case_output.mkdir()
        database, manifest_path = native.prepare_production_bootstrap(case_private, case_output, bootstrap)
        self.assertEqual(database, case_private / "production-bootstrap/database/production/production.db")
        self.assertEqual(native.inspect_production_bootstrap(database, after_ui=False),
                         native.expected_bootstrap_state(after_ui=False))
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["fixture_kind"], "production_bootstrap")
        self.assertEqual(manifest["initial_state"]["account_count"], 1)
        self.assertNotIn("123456", manifest_path.read_text())
        self.assertNotIn("$argon2", manifest_path.read_text())
        self.assertNotIn(str(case_private), manifest_path.read_text())
        native.assert_production_reinitialization_refused(case_private, bootstrap)
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE users SET must_change_password=0, credential_version=2")
        self.assertEqual(native.inspect_production_bootstrap(database, after_ui=True),
                         native.expected_bootstrap_state(after_ui=True))
        with sqlite3.connect(database) as connection:
            connection.execute("INSERT INTO users (id, username, password_hash, role, is_active, must_change_password, credential_version) "
                               "SELECT '00000000-0000-4000-8000-000000000099', 'test-leak', password_hash, 'member', 1, 1, 1 "
                               "FROM users WHERE username='admin'")
        with self.assertRaises(native.EvidenceError):
            native.inspect_production_bootstrap(database, after_ui=True)

    def test_unknown_target_empty_or_duplicate_native_binding_fails(self):
        for mutation in ("unknown", "empty", "duplicate"):
            with self.subTest(mutation=mutation):
                features = copy.deepcopy(self.features)
                if mutation == "unknown":
                    features.pop(0)
                elif mutation == "empty":
                    features[0]["cases"] = []
                else:
                    features[1]["cases"][0]["native_test"] = self.identity
                self.write("tests/feature_matrix.json", {"features": features})
                with self.assertRaises(native.Blocked):
                    native.required_cases(self.root)

    def test_native_tree_and_summary_require_exact_one_pass(self):
        self.assertEqual(native.check_native_result(self.tree, self.summary, self.identity), [self.identity])

    def test_cleanup_error_cannot_replace_primary_failure(self):
        report = {}
        original = native.Blocked("trust ephemeral code-signing certificate timed out")
        with self.assertRaises(native.Blocked) as caught:
            try:
                raise original
            finally:
                native.record_cleanup_errors(report, ["remove signing trust failed"], original)
        self.assertIs(caught.exception, original)
        self.assertEqual(report["cleanup_errors"], ["remove signing trust failed"])
        with self.assertRaises(native.EvidenceError):
            native.record_cleanup_errors({}, ["cleanup failed without prior error"], None)

    def test_upgrade_environment_checks_the_same_live_resources_used_by_product(self):
        output = self.root / "evidence"
        output.mkdir()
        private = self.root / "update"
        private.mkdir()
        signing = mock.Mock()
        signing.prepare.return_value = "A" * 40
        update = mock.Mock()
        update.private = private
        update.url = "http://127.0.0.1:49177"
        update.source_nonce_sha256 = "c" * 64
        update.prepare.return_value = "synthetic public key"
        order = mock.Mock()
        order.attach_mock(signing.prepare, "signing")
        order.attach_mock(update.prepare, "prepare")
        order.attach_mock(update.start, "start")
        with mock.patch.object(native, "git", side_effect=lambda _root, *args: "A" * 40 if args == ("rev-parse", "HEAD") else ""):
            identity, public_key = native.require_upgrade_environment(self.root, output, signing, update)
        self.assertEqual((identity, public_key), ("A" * 40, "synthetic public key"))
        self.assertEqual([call[0] for call in order.mock_calls], ["signing", "prepare", "start"])
        update._run.assert_not_called()
        report = native.json_file(output / "environment.json")
        self.assertEqual(report["state"], "READY")
        self.assertEqual(report["scope"], "environment_only")
        self.assertEqual(report["snapshot_stage"], "preparation")
        self.assertEqual(report["cleanup_owner"], "parent_run_result")
        self.assertEqual(report["executed_cases"], 0)
        self.assertFalse(report["release_eligible"])
        self.assertFalse(report["cleanup_completed"])
        self.assertEqual(report["origin_url"], "http://127.0.0.1:49177")
        self.assertEqual(report["transport"], "loopback_http")
        self.assertEqual(report["source_nonce_sha256"], "c" * 64)
        self.assertNotIn("tunnel_url", report)

    def test_upgrade_environment_health_failure_never_marks_ready_or_restarts_source(self):
        output = self.root / "evidence"
        output.mkdir()
        private = self.root / "update"
        private.mkdir()
        signing = mock.Mock()
        signing.prepare.return_value = "A" * 40
        update = mock.Mock()
        update.private = private
        update.url = "http://127.0.0.1:49177"
        update.source_nonce_sha256 = "c" * 64
        update.prepare.return_value = "synthetic public key"
        update.start.side_effect = RuntimeError("Loopback update fixture source nonce mismatch")
        with mock.patch.object(native, "git", return_value="A" * 40), \
             self.assertRaisesRegex(RuntimeError, "source nonce mismatch"):
            native.require_upgrade_environment(self.root, output, signing, update)
        self.assertEqual(update.start.call_count, 1)
        update._run.assert_not_called()
        report = native.json_file(output / "environment.json")
        self.assertEqual(report["state"], "BLOCKED")
        self.assertIn("source nonce mismatch", report["blockers"][0])

    def test_upgrade_environment_failure_closes_the_same_resources_in_case_finally(self):
        output = self.root / "evidence"
        output.mkdir()
        account_data = mock.Mock()
        signing = mock.Mock()
        signing.prepare.return_value = "A" * 40
        signing.keychain = self.root / "synthetic-signing.keychain"
        update = mock.Mock()
        update.url = None
        update.prepare.return_value = "synthetic public key"
        update.start.side_effect = RuntimeError("Loopback update fixture source nonce mismatch")
        created = {"signing": 0, "update": 0}
        def make_signing(private):
            created["signing"] += 1
            signing.private = private
            return signing
        def make_update(private, evidence):
            created["update"] += 1
            update.private = private
            private.mkdir()
            return update
        modules = {
            "fixtures.py": account_data,
            "bootstrap_sqlite.py": mock.Mock(),
            "update_source.py": SimpleNamespace(UpdateSource=make_update),
            "code_signing.py": SimpleNamespace(SigningIdentity=make_signing),
        }
        def provision(_root, case_private, _case_output, _data, _isolation_id, _seed):
            fixture = case_private / "fixture"
            fixture.mkdir()
            (fixture / "manifest.json").write_text("{}")
            database = case_private / "database.sqlite"
            database.write_bytes(b"synthetic, never product data")
            return database, fixture
        process = mock.Mock()
        report = {"run_id": "governance", "suites": [], "executed_cases": 0, "passed_cases": 0,
                  "cleanup_completed": False}
        with mock.patch.object(native, "preflight", return_value={"architecture": "arm64", "macos": "15.7.9"}), \
             mock.patch.object(native, "git", side_effect=lambda _root, *args: "A" * 40 if args == ("rev-parse", "HEAD") else ""), \
             mock.patch.object(native, "required_cases", return_value={"E2E-TM001-004": self.identity}), \
             mock.patch.object(native, "snapshot", return_value={}), \
             mock.patch.object(native, "load_module", side_effect=lambda path, _name: modules[path.name]), \
             mock.patch.object(native, "prepare_account_database", side_effect=provision), \
             mock.patch.object(native, "start_isolated_service", return_value=(process, "http://127.0.0.1:12345", mock.Mock())), \
             mock.patch.object(native, "wait_for_service"), \
             mock.patch.object(native, "command") as command, \
             self.assertRaisesRegex(RuntimeError, "source nonce mismatch"):
            native.execute(ROOT, output, report)
        self.assertEqual(created, {"signing": 1, "update": 1})
        signing.close.assert_called_once_with()
        update.close.assert_called_once_with()
        update.start.assert_called_once_with()
        update._run.assert_not_called()
        command.assert_not_called()  # No build, package, or App launch after blocked readiness.
        self.assertEqual(native.json_file(output / "E2E-TM001-004/environment.json")["state"], "BLOCKED")
        self.assertEqual(report["credential_cleanup"]["E2E-TM001-004"], "SUCCEEDED")

    def test_attachment_export_requires_native_help_and_real_png_files(self):
        bundle = self.root / "native.xcresult"
        bundle.mkdir()
        output = self.root / "evidence"
        output.mkdir()
        help_result = mock.Mock(returncode=0, stdout="USAGE: export attachments --path <path> --output-path <output-path>", stderr="")
        def export(arguments, **kwargs):
            destination = Path(arguments[arguments.index("--output-path") + 1])
            destination.mkdir()
            (destination / "screen.png").write_bytes(b"\x89PNG\r\n\x1a\nSynthetic unit fixture")
            (destination / "manifest.json").write_text("[]")
        with mock.patch.object(native.subprocess, "run", return_value=help_result), \
             mock.patch.object(native, "command", side_effect=export):
            result = native.export_attachments(self.root, bundle, output)
        self.assertEqual(result[0]["path"], "attachments/screen.png")
        self.assertEqual(result[0]["sha256"], native.sha256(output / result[0]["path"]))
        self.assertTrue((output / "attachments-help.log").is_file())
        with mock.patch.object(native.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="unknown help", stderr="")), \
             self.assertRaises(native.Blocked):
            native.export_attachments(self.root, bundle, output)

    def test_default_update_bundle_rejects_injected_feed_and_wrong_public_key(self):
        app = self.root / "TokenMeter.app"
        contents = app / "Contents"
        contents.mkdir(parents=True)
        info = contents / "Info.plist"
        original = {"SUFeedURL": "", "SUPublicEDKey": "fixed-test-public-key",
                    "SUVerifyUpdateBeforeExtraction": True}
        info.write_bytes(plistlib.dumps(original))
        native.verify_default_update_bundle(app, "fixed-test-public-key")
        for field, value in (("SUFeedURL", "http://127.0.0.1:49177/appcast.xml"),
                             ("SUFeedURL", "https://example.invalid/appcast.xml"),
                             ("SUPublicEDKey", "other-key"), ("SUVerifyUpdateBeforeExtraction", False)):
            with self.subTest(field=field, value=value):
                info.write_bytes(plistlib.dumps(dict(original, **{field: value})))
                with self.assertRaises(native.EvidenceError):
                    native.verify_default_update_bundle(app, "fixed-test-public-key")

    def test_native_bundle_digest_is_captured_after_export_finishes(self):
        bundle = self.root / "native.xcresult"
        bundle.mkdir()
        database = bundle / "database.sqlite3"
        database.write_bytes(b"initial completed test output")
        before = native.tree_digest(bundle)
        suite = {}
        def export(*_args):
            database.write_bytes(b"final database after parsing and export")
            return [{"path": "screen.png", "sha256": "a" * 64}]
        with mock.patch.object(native, "export_attachments", side_effect=export):
            native.capture_native_artifacts(self.root, bundle, self.root, suite)
        self.assertNotEqual(suite["xcresult_sha256"], before)
        self.assertEqual(suite["xcresult_sha256"], native.tree_digest(bundle))
        database.write_bytes(b"later tampering must not change the recorded digest")
        self.assertNotEqual(suite["xcresult_sha256"], native.tree_digest(bundle))

    def test_failed_export_keeps_final_bundle_digest_without_hiding_failure(self):
        bundle = self.root / "native.xcresult"
        bundle.mkdir()
        database = bundle / "database.sqlite3"
        database.write_bytes(b"initial")
        suite = {}
        def export(*_args):
            database.write_bytes(b"final failure evidence")
            raise native.EvidenceError("actual export failed")
        with mock.patch.object(native, "export_attachments", side_effect=export), \
             self.assertRaisesRegex(native.EvidenceError, "actual export failed"):
            native.capture_native_artifacts(self.root, bundle, self.root, suite)
        self.assertEqual(suite["xcresult_sha256"], native.tree_digest(bundle))
        self.assertNotIn("screenshots", suite)

    def test_exported_attachment_missing_png_cannot_be_accepted(self):
        output = self.root / "evidence"
        output.mkdir()
        with mock.patch.object(native.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="--path --output-path", stderr="")), \
             mock.patch.object(native, "command"), self.assertRaises(native.EvidenceError):
            native.export_attachments(self.root, self.root / "native.xcresult", output)

    def test_xcode_16_4_ui_bundle_name_is_preserved_and_original_failure_stays_failed(self):
        tree = json.loads((ROOT / "tests/e2e/fixtures/xcresult-16.4-native-tests.json").read_text())
        summary = json.loads((ROOT / "tests/e2e/fixtures/xcresult-16.4-native-summary.json").read_text())
        with self.assertRaises(native.EvidenceError) as caught:
            native.check_native_result(tree, summary, self.identity)
        self.assertIn(self.identity, str(caught.exception))
        self.assertNotIn("('/TM001", str(caught.exception))
        # Synthetic passing format variant tests parsing only, not product behavior.
        def mark_nodes(node):
            node["result"] = "Passed"
            for child in node.get("children", []):
                mark_nodes(child)
        for node in tree["testNodes"]:
            mark_nodes(node)
        summary.update(result="Passed", failedTests=0, passedTests=1, testFailures=[])
        self.assertEqual(native.check_native_result(tree, summary, self.identity), [self.identity])
        tree["testNodes"][0]["children"][0]["name"] = "WrongUITestBundle"
        with self.assertRaises(native.EvidenceError):
            native.check_native_result(tree, summary, self.identity)

    def test_native_destination_architecture_family_must_match_requested_architecture(self):
        summary = json.loads((ROOT / "tests/e2e/fixtures/xcresult-16.4-native-summary.json").read_text())
        observed = native.native_destination(summary, "arm64", "15.7.9")
        self.assertEqual(observed["architecture"], "arm64e")
        self.assertEqual(observed["architecture_family"], "arm64")
        intel = copy.deepcopy(summary)
        intel["devicesAndConfigurations"][0]["device"]["architecture"] = "x86_64h"
        self.assertEqual(native.native_destination(intel, "x86_64", "15.7.9")["architecture_family"], "x86_64")
        with self.assertRaises(native.EvidenceError):
            native.native_destination(summary, "x86_64", "15.7.9")
        for field, bad in (("platform", "iOS"), ("architecture", "unknown"), ("osVersion", "14.0")):
            mutated = copy.deepcopy(summary)
            mutated["devicesAndConfigurations"][0]["device"][field] = bad
            with self.subTest(field=field), self.assertRaises(native.EvidenceError):
                native.native_destination(mutated, "arm64", "15.7.9")

    def test_failed_skipped_unknown_and_duplicate_native_cases_rejected(self):
        for status in ("Failed", "Skipped", "Expected Failure", "Unknown", "Passed"):
            tree = copy.deepcopy(self.tree)
            leaf = tree["testNodes"][0]["children"][0]["children"][0]
            leaf["result"] = status
            if status == "Passed":
                tree["testNodes"][0]["children"][0]["children"].append(copy.deepcopy(leaf))
            with self.subTest(status=status), self.assertRaises(native.EvidenceError):
                native.check_native_result(tree, self.summary, self.identity)

    def test_missing_and_wrong_native_case_rejected(self):
        for tree in ({"testNodes": []}, {"passed": True}, self.tree):
            with self.assertRaises(native.EvidenceError):
                native.check_native_result(tree, self.summary, self.identity + "Wrong")

    def test_summary_must_not_hide_failure_skip_zero_or_unrecognized_counts(self):
        for field, value in (("totalTestCount", 0), ("passedTests", 0), ("failedTests", 1), ("skippedTests", 1), ("result", "Failed"), ("testFailures", [{"message": "failed"}])):
            summary = dict(self.summary, **{field: value})
            with self.subTest(field=field), self.assertRaises(native.EvidenceError):
                native.check_native_result(self.tree, summary, self.identity)

    def test_bundle_hash_changes_with_contents_and_rejects_symlinks(self):
        bundle = self.root / "result.xcresult"
        bundle.mkdir()
        (bundle / "Info.plist").write_text("first")
        first = native.tree_digest(bundle)
        (bundle / "Info.plist").write_text("second")
        self.assertNotEqual(first, native.tree_digest(bundle))
        (bundle / "external").symlink_to(self.root / "tests")
        with self.assertRaises(native.EvidenceError):
            native.tree_digest(bundle)

    def test_run_directory_must_be_new_and_confined(self):
        self.assertTrue(native.new_run_directory(self.root, "test-123").is_dir())
        with self.assertRaises((native.EvidenceError, FileExistsError)):
            native.new_run_directory(self.root, "test-123")
        for bad in ("../escape", "/tmp/escape", "has space"):
            with self.assertRaises(native.EvidenceError):
                native.new_run_directory(self.root, bad)

    def test_xctestrun_environment_is_only_bound_to_real_ui_target(self):
        products = self.root / "derived/Build/Products"
        products.mkdir(parents=True)
        document = {"TestConfigurations": [{"TestTargets": [{"BlueprintName": "TokenMeterUITests", "EnvironmentVariables": {"existing": "yes"}}]}]}
        (products / "TokenMeter.xctestrun").write_bytes(plistlib.dumps(document))
        output = native.test_configuration(self.root / "derived", {"TM_TEST_RUN_ID": "isolated"})
        environment = plistlib.loads(output.read_bytes())["TestConfigurations"][0]["TestTargets"][0]["EnvironmentVariables"]
        self.assertEqual(environment, {"existing": "yes", "TM_TEST_RUN_ID": "isolated"})
        document["TestConfigurations"][0]["TestTargets"][0]["BlueprintName"] = "OtherTarget"
        (products / "TokenMeter.xctestrun").write_bytes(plistlib.dumps(document))
        with self.assertRaises(native.Blocked):
            native.test_configuration(self.root / "derived", {})

    def test_build_options_are_supported_by_actual_xcode_16_4_help(self):
        # Independent option set from both failed platform jobs in CI run
        # 36541990316. That native usage output has no macOS concurrency option.
        supported = {"-project", "-scheme", "-configuration", "-derivedDataPath",
                     "-destination", "-parallel-testing-enabled"}
        arguments = native.build_command(Path("TokenMeter.xcodeproj"), Path("derived"))
        self.assertEqual({argument for argument in arguments if argument.startswith("-")}, supported)
        self.assertEqual(arguments[arguments.index("-parallel-testing-enabled") + 1], "NO")
        for architecture in ("arm64", "x86_64"):
            with mock.patch.object(native.platform, "machine", return_value=architecture):
                arguments = native.build_command(Path("TokenMeter.xcodeproj"), Path("derived"))
            self.assertEqual(arguments[arguments.index("-destination") + 1], "platform=macOS,arch=" + architecture)


class EvidenceVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = native.new_run_directory(self.root, "nonce")
        self.bundle = self.output / "case/native.xcresult"
        self.bundle.mkdir(parents=True)
        (self.bundle / "Info.plist").write_text("Synthetic verifier unit test artifact")
        (self.output / "case/app.zip").write_bytes(b"Synthetic artifact, never real E2E")
        (self.output / "case/manifest.json").write_text("{}")
        (self.output / "E2E-TM001-001").mkdir()
        (self.output / "E2E-TM001-001/screen.png").write_bytes(b"\x89PNG\r\n\x1a\nSynthetic evidence test fixture")
        self.now = time.time()
        self.summary = json.loads((ROOT / "tests/e2e/fixtures/xcresult-16.4-native-summary.json").read_text())
        self.destination = native.native_destination(self.summary, "arm64", "15.7.9")
        self.report = {
            "state": "PASS", "runner_implemented": True, "run_id": "nonce", "phase": "iteration",
            "release_id": "v0.1.0-20260929T074814Z",
            "started_at": datetime.fromtimestamp(self.now, timezone.utc).isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "source_commit": "a" * 40, "working_tree_dirty": False,
            "platform": {"architecture": "arm64", "macos": "15.7.9"},
            "manifest_sha256": {"fixture": "digest"}, "expected_cases": ["E2E-TM001-001"],
            "executed_cases": 1, "cleanup_completed": True,
            "suites": [{"case_id": "E2E-TM001-001", "exit_code": 0, "xcresult": "case/native.xcresult",
                        "xcresult_sha256": native.tree_digest(self.bundle), "fixture_manifest": "case/manifest.json",
                        "fixture_sha256": native.sha256(self.output / "case/manifest.json"), "app_artifact": "case/app.zip",
                        "app_sha256": native.sha256(self.output / "case/app.zip"), "destination": self.destination,
                        "screenshots": [{"path": "screen.png", "sha256": native.sha256(self.output / "E2E-TM001-001/screen.png")}]}],
        }
        self.path = self.output / "result.json"
        for function, value in (("git", None), ("snapshot", {"fixture": "digest"}),
                                ("required_cases", {"E2E-TM001-001": "target/suite/testCase"}),
                                ("parse_bundle", ({"native": "tree"}, self.summary)),
                                ("check_native_result", ["target/suite/testCase"])):
            patcher = mock.patch.object(native, function, return_value=value)
            mocked = patcher.start()
            self.addCleanup(patcher.stop)
            if function == "git":
                mocked.side_effect = lambda _root, *args: "a" * 40 if args == ("rev-parse", "HEAD") else ""

    def verify(self):
        self.path.write_text(json.dumps(self.report))
        return native.verify_report(self.root, self.path, run_id="nonce", phase="iteration", not_before=self.now)

    def configure_upgrade_snapshot(self):
        case = "E2E-TM001-004"
        case_output = self.output / case
        case_output.mkdir()
        (case_output / "screen.png").write_bytes((self.output / "E2E-TM001-001/screen.png").read_bytes())
        self.report["expected_cases"] = [case]
        self.report["suites"][0]["case_id"] = case
        native.required_cases.return_value = {case: "target/suite/testCase"}
        environment = {
            "scope": "environment_only", "case_id": case, "run_id": "nonce", "state": "READY",
            "snapshot_stage": "preparation", "cleanup_owner": "parent_run_result",
            "source_commit": self.report["source_commit"], "working_tree_dirty": False,
            "release_id": self.report["release_id"], "executed_cases": 0,
            "release_eligible": False, "cleanup_completed": False,
            "origin_url": "http://127.0.0.1:49177", "transport": "loopback_http",
            "source_nonce_sha256": "a" * 64,
        }
        environment_path = case_output / "environment.json"
        environment_path.write_text(json.dumps(environment))
        self.report["upgrade_environment"] = {
            "path": f"{case}/environment.json", "sha256": native.sha256(environment_path), "state": "READY"}
        return environment_path, environment

    def test_upgrade_environment_evidence_is_reopened_and_bound_to_this_run(self):
        environment_path, environment = self.configure_upgrade_snapshot()
        self.verify()
        original = environment_path.read_bytes()
        environment_path.write_bytes(original + b"\n")
        with self.assertRaises(native.EvidenceError):
            self.verify()
        environment_path.write_bytes(original)
        environment_path.unlink()
        with self.assertRaises(native.EvidenceError):
            self.verify()
        environment_path.write_bytes(original)
        self.report.pop("upgrade_environment")
        with self.assertRaises(native.EvidenceError):
            self.verify()
        self.report["upgrade_environment"] = {"path": "../outside.json", "sha256": native.sha256(environment_path),
                                              "state": "READY"}
        with self.assertRaises(native.EvidenceError):
            self.verify()
        self.report["upgrade_environment"]["path"] = "E2E-TM001-004/environment.json"
        environment_path.unlink()
        outside = self.output / "outside.json"
        outside.write_text(json.dumps(environment))
        environment_path.symlink_to(outside)
        with self.assertRaises(native.EvidenceError):
            self.verify()

    def test_upgrade_environment_rejects_rehashed_wrong_candidate_or_snapshot_claims(self):
        environment_path, original = self.configure_upgrade_snapshot()
        self.verify()
        changes = {
            "scope": "product_pass", "case_id": "E2E-TM001-003", "run_id": "old-run",
            "state": "BLOCKED", "snapshot_stage": "cleanup", "cleanup_owner": "environment_probe",
            "source_commit": "b" * 40, "working_tree_dirty": True, "release_id": "old-release",
            "executed_cases": 1, "release_eligible": True, "cleanup_completed": True,
            "origin_url": "http://127.0.0.1:12345", "transport": "public_tunnel", "source_nonce_sha256": "invalid",
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                changed = dict(original, **{field: value})
                environment_path.write_text(json.dumps(changed))
                self.report["upgrade_environment"]["sha256"] = native.sha256(environment_path)
                with self.assertRaises(native.EvidenceError):
                    self.verify()
        environment_path.write_text(json.dumps(original))
        self.report["upgrade_environment"]["sha256"] = native.sha256(environment_path)
        self.report["upgrade_environment"]["state"] = "PASS"
        with self.assertRaises(native.EvidenceError):
            self.verify()

    def test_verification_reopens_native_artifact_and_does_not_trust_only_json(self):
        self.verify()
        native.parse_bundle.assert_called_once_with(self.root, self.bundle)
        native.check_native_result.assert_called_once()
        native.parse_bundle.side_effect = native.Blocked("Not a real xcresult")
        with self.assertRaises(native.Blocked):
            self.verify()

    def test_parent_rejects_bundle_changed_during_original_result_parsing(self):
        def parse_and_modify(_root, bundle):
            (bundle / "database.sqlite3").write_bytes(b"late parser write")
            return {"native": "tree"}, self.summary
        native.parse_bundle.side_effect = parse_and_modify
        with self.assertRaisesRegex(native.EvidenceError, "changed during verification"):
            self.verify()

    def test_forged_run_stale_commit_dirty_source_and_incomplete_coverage_rejected(self):
        for field, bad in (("run_id", "other"), ("source_commit", "b" * 40), ("working_tree_dirty", True),
                           ("executed_cases", 0), ("cleanup_completed", False), ("manifest_sha256", {}),
                           ("started_at", "2000-01-01T00:00:00+00:00"), ("expected_cases", []),
                           ("suites", [])):
            with self.subTest(field=field):
                original = self.report[field]
                self.report[field] = bad
                with self.assertRaises(native.EvidenceError):
                    self.verify()
                self.report[field] = original

    def test_changed_or_missing_native_build_and_fixture_artifacts_fail(self):
        for relative in ("case/app.zip", "case/manifest.json", "case/native.xcresult/Info.plist", "E2E-TM001-001/screen.png"):
            path = self.output / relative
            original = path.read_bytes()
            path.write_bytes(b"tampered")
            with self.subTest(relative=relative), self.assertRaises(native.EvidenceError):
                self.verify()
            path.write_bytes(original)

    def test_forged_native_destination_is_rejected(self):
        self.report["suites"][0]["destination"] = dict(self.destination, architecture="x86_64h")
        with self.assertRaises(native.EvidenceError):
            self.verify()

    def test_release_cannot_reuse_iteration_pass(self):
        self.report["phase"] = "release"
        self.path.write_text(json.dumps(self.report))
        with self.assertRaises(native.Blocked):
            native.verify_report(self.root, self.path, run_id="nonce", phase="release", not_before=self.now)

    def test_production_case_requires_initial_and_post_ui_database_evidence(self):
        case = "E2E-TM001-005"
        case_output = self.output / case
        case_output.mkdir()
        manifest = {
            "fixture_kind": "production_bootstrap", "database": "database/production/production.db",
            "database_sha256": "a" * 64, "seed_sql_sha256": "b" * 64,
            "initial_state": native.expected_bootstrap_state(after_ui=False),
        }
        manifest_path = case_output / "fixture-manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        state_path = case_output / "database-state.json"
        state_path.write_text(json.dumps({"post_ui_state": native.expected_bootstrap_state(after_ui=True),
                                          "reinitialization_refused": True}))
        old_suite = self.report["suites"][0]
        self.report["expected_cases"] = [case]
        self.report["suites"] = [dict(old_suite, case_id=case,
                                      fixture_manifest=f"{case}/fixture-manifest.json",
                                      fixture_sha256=native.sha256(manifest_path),
                                      bootstrap_state_artifact=f"{case}/database-state.json",
                                      bootstrap_state_sha256=native.sha256(state_path),
                                      screenshots=[{"path": "screen.png", "sha256": native.sha256(self.output / "E2E-TM001-001/screen.png")}])]
        (case_output / "screen.png").write_bytes((self.output / "E2E-TM001-001/screen.png").read_bytes())
        self.report["suites"][0]["screenshots"][0]["sha256"] = native.sha256(case_output / "screen.png")
        native.required_cases.return_value = {case: "target/suite/testCase"}
        self.verify()
        for field, bad in (("initial_state", native.expected_bootstrap_state(after_ui=True)),
                           ("fixture_kind", "synthetic_accounts")):
            with self.subTest(field=field):
                original = manifest[field]
                manifest[field] = bad
                manifest_path.write_text(json.dumps(manifest))
                self.report["suites"][0]["fixture_sha256"] = native.sha256(manifest_path)
                with self.assertRaises(native.EvidenceError):
                    self.verify()
                manifest[field] = original
        manifest_path.write_text(json.dumps(manifest))
        self.report["suites"][0]["fixture_sha256"] = native.sha256(manifest_path)
        state_path.write_text(json.dumps({"post_ui_state": native.expected_bootstrap_state(after_ui=False),
                                          "reinitialization_refused": True}))
        self.report["suites"][0]["bootstrap_state_sha256"] = native.sha256(state_path)
        with self.assertRaises(native.EvidenceError):
            self.verify()

    def test_dual_service_case_requires_two_distinct_data_sources(self):
        case = "E2E-TM001-006"
        case_output = self.output / case
        case_output.mkdir()
        manifest = {
            "fixture_kind": "dual_service_routes", "default_port": 49176,
            "primary": {"run_id": "route-primary", "seed": 42, "account_manifest_sha256": "a" * 64},
            "secondary": {"run_id": "route-secondary", "seed": 43, "account_manifest_sha256": "b" * 64},
        }
        manifest_path = case_output / "fixture-manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        (case_output / "screen.png").write_bytes((self.output / "E2E-TM001-001/screen.png").read_bytes())
        self.report["expected_cases"] = [case]
        self.report["suites"] = [dict(self.report["suites"][0], case_id=case,
                                      fixture_manifest=f"{case}/fixture-manifest.json",
                                      fixture_sha256=native.sha256(manifest_path),
                                      screenshots=[{"path": "screen.png", "sha256": native.sha256(case_output / "screen.png")}])]
        native.required_cases.return_value = {case: "target/suite/testCase"}
        self.verify()
        for key, bad in (("default_port", 49177), ("fixture_kind", "synthetic_accounts")):
            with self.subTest(key=key):
                original = manifest[key]
                manifest[key] = bad
                manifest_path.write_text(json.dumps(manifest))
                self.report["suites"][0]["fixture_sha256"] = native.sha256(manifest_path)
                with self.assertRaises(native.EvidenceError):
                    self.verify()
                manifest[key] = original
        manifest["secondary"]["run_id"] = "route-primary"
        manifest_path.write_text(json.dumps(manifest))
        self.report["suites"][0]["fixture_sha256"] = native.sha256(manifest_path)
        with self.assertRaises(native.EvidenceError):
            self.verify()


if __name__ == "__main__":
    unittest.main()
