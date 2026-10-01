"""Synthetic negative evidence for the release verifier; never product E2E."""
import base64
import copy
import hashlib
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("internal_release_gate", ROOT / "scripts/internal_release_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

SHA = "a" * 40
RID = "v0.1.0-20260929T074814Z"
RUN = "release-test-234-1"
CASES = {f"E2E-TM001-{i:03}": f"TokenMeterUITests/TM001AccountUITests/testE2E_TM001_{i:03}"
         for i in range(1, 7)}


class InternalGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.now = time.time()
        self.env = {
            "GITHUB_ACTIONS": "true", "RUNNER_OS": "macOS", "RUNNER_ENVIRONMENT": "github-hosted",
            "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/master",
            "GITHUB_REF_PROTECTED": "true", "GITHUB_REPOSITORY": "lzhe72/TokenMeter",
            "GITHUB_SHA": SHA, "GITHUB_WORKFLOW_SHA": SHA,
            "GITHUB_WORKFLOW_REF": "lzhe72/TokenMeter/.github/workflows/internal-release.yml@refs/heads/master",
            "GITHUB_RUN_ID": "234", "GITHUB_RUN_ATTEMPT": "1",
        }
        self.ci = gate.ci_context(self.env, SHA)
        for path in ("releases/current.json", "tests/feature_matrix.json", "tests/acceptance.json",
                     "tests/datasets.json", "docs/catalog.json"):
            self.json(path, {"fixture": "governance only"})
        self.package = {
            "artifacts": {"dmg": {"sha256": "d" * 64}, "update_zip": {"sha256": "e" * 64, "bytes": 321}},
            "app": {"tree_sha256": "f" * 64, "bundle_id": "org.tokenmeter.TokenMeter", "build": "100",
                    "architectures": ["arm64", "x86_64"], "code_sign_identity": "b" * 40,
                    "signature_kind": "internal_self_signed"},
            "update_app": {"tree_sha256": "9" * 64, "build": "101"},
            "signatures": {"update_ed_signature": base64.b64encode(b"s" * 64).decode()},
        }
        self.config = {"release_id": RID}
        self.evidence = self.root / "evidence"
        self.reports = {}
        for arch in ("arm64", "x86_64"):
            self.reports[arch] = self.make_report(arch)
        self.write_reports()
        patches = [mock.patch.object(gate.native, "required_cases", return_value=CASES),
                   mock.patch.object(gate.native, "parse_bundle", side_effect=self.parse_bundle)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def json(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def descriptor(self, base, relative, value):
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return {"path": relative, "sha256": gate.native.sha256(path)}

    def stamp(self, offset=0):
        return datetime.fromtimestamp(self.now + offset, timezone.utc).isoformat()

    def make_report(self, arch):
        base = self.evidence / arch
        base.mkdir(parents=True)
        report = {"schema_version": 1, "run_id": RUN, "release_id": RID, "phase": "release",
                  "state": "PASS", "distribution_profile": "internal", "scope": "final_package",
                  "release_eligible": False, "source_commit": SHA, "working_tree_dirty": False,
                  "started_at": self.stamp(-60), "finished_at": self.stamp(-1), "ci": self.ci,
                  "platform": {"architecture": arch, "macos": "15.7.9", "xcode": "Xcode 16.4\nBuild version 16F6"},
                  "manifest_sha256": gate.native.snapshot(self.root), "expected_cases": list(CASES),
                  "executed_cases": 6, "passed_cases": 6, "cleanup_completed": True, "cleanup_errors": [],
                  "credential_cleanup": dict.fromkeys(CASES, True), "defaults_cleanup": dict.fromkeys(CASES, True),
                  "service_cleanup": dict.fromkeys(CASES, True), "suites": []}
        report["package"] = {
            "dmg_sha256": "d" * 64, "app_tree_sha256": "f" * 64, "update_zip_sha256": "e" * 64,
            "app_bundle_id": "org.tokenmeter.TokenMeter", "build": "100",
            "architectures": ["arm64", "x86_64"], "code_sign_identity": "b" * 40,
            "signature_kind": "internal_self_signed",
            "spctl_before": {"exit_code": 3, "output": "rejected"},
            "spctl_after": {"exit_code": 3, "output": "rejected"},
        }
        report["installation"] = {"owned_paths": {case: f"/tmp/{RUN}/{arch}/{case}/TokenMeter.app" for case in CASES},
                                   "source_dmg_sha256": "d" * 64}
        for case, identifier in CASES.items():
            bundle = base / case / "native.xcresult"
            bundle.mkdir(parents=True)
            tree = {"testNodes": [{"nodeType": "Test Case", "nodeIdentifier": identifier,
                                    "result": "Passed"}]}
            device = {"architecture": arch, "deviceId": "synthetic-" + arch,
                      "osVersion": "15.7.9", "platform": "macOS"}
            summary = {"result": "Passed", "totalTestCount": 1, "passedTests": 1, "failedTests": 0,
                       "skippedTests": 0, "expectedFailures": 0, "testFailures": [],
                       "startTime": self.now - 40, "finishTime": self.now - 20,
                       "devicesAndConfigurations": [{"device": device}]}
            (bundle / "synthetic-tree.json").write_text(json.dumps(tree))
            (bundle / "synthetic-summary.json").write_text(json.dumps(summary))
            (bundle / "database.sqlite3").write_bytes(b"synthetic xcresult bytes")
            fixture = gate.expected_account_manifest((RUN + "-" + case).lower(), 42)
            if case.endswith("005"):
                fixture = {"fixture_kind": "production_bootstrap", "database": "database/production/production.db",
                           "database_sha256": "1" * 64, "seed_sql_sha256": "2" * 64,
                           "initial_state": gate.native.expected_bootstrap_state(after_ui=False)}
            if case.endswith("006"):
                fixture = {"fixture_kind": "dual_service_routes", "default_port": 49176,
                           "primary": {"run_id": RUN + "-primary", "seed": 42, "account_manifest_sha256": "1" * 64},
                           "secondary": {"run_id": RUN + "-secondary", "seed": 43, "account_manifest_sha256": "2" * 64}}
                for item in (fixture["primary"], fixture["secondary"]):
                    expected = gate.expected_account_manifest(item["run_id"], item["seed"])
                    item["account_manifest_sha256"] = hashlib.sha256(gate.account_tool._encode(expected)).hexdigest()
            desc = self.descriptor(base, case + "/fixture.json", fixture)
            picture = base / case / "attachments/window.png"
            picture.parent.mkdir()
            picture.write_bytes(b"\x89PNG\r\n\x1a\nsynthetic image")
            suite = {"case_id": case, "native_test": identifier, "state": "PASS", "exit_code": 0,
                     "native_failures": [], "xcresult": case + "/native.xcresult",
                     "xcresult_sha256": gate.native.tree_digest(bundle),
                     "fixture_manifest": desc["path"], "fixture_sha256": desc["sha256"],
                     "destination": device | {"architecture_family": arch},
                     "screenshots": [{"path": "attachments/window.png", "sha256": gate.native.sha256(picture)}],
                     "installed_app_path": f"/tmp/{RUN}/{arch}/{case}/TokenMeter.app",
                     "installed_app_before_sha256": "f" * 64}
            if case.endswith("005"):
                state = self.descriptor(base, case + "/state.json", {
                    "post_ui_state": gate.native.expected_bootstrap_state(after_ui=True), "reinitialization_refused": True})
                suite.update(bootstrap_state_artifact=state["path"], bootstrap_state_sha256=state["sha256"])
            report["suites"].append(suite)
        self.add_update(base, report)
        self.add_restore(base, report)
        return report

    def add_update(self, base, report):
        case = "E2E-TM001-004"
        fixture = gate.expected_update_fixture(self.package) | {"source_nonce_sha256": "7" * 64}
        desc = self.descriptor(base, case + "/update-fixture.json", fixture)
        events = []
        for mode in ("forbidden", "redirect", "invalid", "valid"):
            events.extend([{"at": self.stamp(-30), "path": "/control/" + mode, "status": 200},
                           {"at": self.stamp(-30), "path": "/appcast.xml", "status": 200,
                            "mode": mode, "served_bytes": 12}])
            if mode == "redirect":
                events.append({"at": self.stamp(-30), "path": "/redirect.zip", "status": 302, "mode": mode})
            if mode in ("invalid", "valid"):
                events.append({"at": self.stamp(-30), "path": "/update.zip", "status": 200,
                               "mode": mode, "served_bytes": 321})
        requests = self.descriptor(base, case + "/update-requests.json", events)
        suite = next(s for s in report["suites"] if s["case_id"] == case)
        suite.update(upgraded_app_sha256="9" * 64, upgraded_build="101",
                     update_fixture_artifact=desc["path"], update_fixture_sha256=desc["sha256"],
                     update_requests_artifact=requests["path"], update_requests_sha256=requests["sha256"])

    def add_restore(self, base, report):
        paths = []
        for name in ("backup.db", "restored.db"):
            path = base / name
            with sqlite3.connect(path) as db:
                db.executescript("CREATE TABLE alembic_version(version_num TEXT); INSERT INTO alembic_version VALUES('0001');"
                                 "CREATE TABLE tokenmeter_seed_owner(environment TEXT,run_id TEXT); INSERT INTO tokenmeter_seed_owner VALUES('production','production-init');"
                                 "CREATE TABLE users(id TEXT,username TEXT,password_hash TEXT,role TEXT,is_active INTEGER,must_change_password INTEGER,credential_version INTEGER);"
                                 "INSERT INTO users VALUES('00000000-0000-4000-8000-000000000005','admin','$argon2id$synthetic','admin',1,1,1);"
                                 "CREATE TABLE sessions(token_hash TEXT,user_id TEXT,credential_version INTEGER,expires_at INTEGER);"
                                 "CREATE TABLE audit(id TEXT,actor_id TEXT,target_id TEXT,action TEXT,occurred_at INTEGER);"
                                 "INSERT INTO audit VALUES('synthetic',NULL,'00000000-0000-4000-8000-000000000005','account_provisioned',1);"
                                 "CREATE TABLE login_buckets(key TEXT,failures INTEGER,window_start INTEGER);")
            paths.append(path)
        state = self.descriptor(base, "restore-state.json", {"integrity_check": "ok", "schema_version": "0001",
                         "table_rows_match": True, "api_login_verified": True})
        report["sqlite_restore"] = {"verified": True, "fixture_kind": "production_bootstrap", "synthetic_only": True,
            "backup_artifact": "backup.db",
            "backup_sha256": gate.native.sha256(paths[0]), "restored_artifact": "restored.db",
            "restored_sha256": gate.native.sha256(paths[1]), "restored_state_artifact": state["path"],
            "restored_state_sha256": state["sha256"]}

    def write_reports(self):
        for arch, report in self.reports.items():
            (self.evidence / arch / "result.json").write_text(json.dumps(report))

    def parse_bundle(self, root, bundle):
        return (json.loads((bundle / "synthetic-tree.json").read_text()),
                json.loads((bundle / "synthetic-summary.json").read_text()))

    def verify(self):
        self.write_reports()
        return gate.verify_platforms(self.root, self.evidence, self.package, self.config,
                                     candidate_sha=SHA, run_id=RUN, ci=self.ci, now=self.now)

    def test_synthetic_verifier_contract_passes_both_platforms(self):
        result = self.verify()
        self.assertEqual(set(result), {"arm64", "x86_64"})

    def test_ci_context_rejects_unprotected_wrong_workflow_or_attempt(self):
        for key, value in [("GITHUB_ACTIONS", "false"), ("GITHUB_REF_PROTECTED", "false"),
                           ("GITHUB_REF", "refs/heads/topic"), ("GITHUB_EVENT_NAME", "pull_request"),
                           ("GITHUB_WORKFLOW_SHA", "c" * 40), ("GITHUB_SHA", "c" * 40),
                           ("GITHUB_WORKFLOW_REF", "lzhe72/TokenMeter/.github/workflows/quality.yml@refs/heads/master"),
                           ("GITHUB_RUN_ATTEMPT", "0"), ("RUNNER_ENVIRONMENT", "self-hosted")]:
            with self.subTest(key=key), self.assertRaises(gate.GateError):
                gate.ci_context(self.env | {key: value}, SHA)

    def test_ci_identity_contract_matches_builder_and_publisher(self):
        environment = self.env | {"RUNNER_TEMP": str(self.root)}
        self.assertEqual(gate.package_tool.validate_ci(SHA, environment), self.ci)
        with mock.patch.dict(os.environ, environment, clear=True), mock.patch.object(
                gate.publish_tool, "command", side_effect=lambda args: SHA if "rev-parse" in args else ""):
            self.assertEqual(gate.publish_tool.context(SHA), self.ci)

    def test_missing_platform_is_blocked(self):
        (self.evidence / "x86_64/result.json").unlink()
        with self.assertRaises(gate.GateError):
            gate.verify_platforms(self.root, self.evidence, self.package, self.config,
                                  candidate_sha=SHA, run_id=RUN, ci=self.ci, now=self.now)

    def test_wrong_sha_package_run_attempt_and_cleanup_refused(self):
        original = copy.deepcopy(self.reports["arm64"])
        changes = [lambda r: r.update(source_commit="c" * 40), lambda r: r.update(run_id="other"),
                   lambda r: r["ci"].update(run_attempt="2"), lambda r: r["package"].update(dmg_sha256="c" * 64),
                   lambda r: r.update(cleanup_completed=False), lambda r: r["service_cleanup"].update({next(iter(CASES)): False}),
                   lambda r: r.update(release_eligible=True), lambda r: r.update(working_tree_dirty=True),
                   lambda r: r.update(started_at=self.stamp(-15000))]
        for change in changes:
            self.reports["arm64"] = copy.deepcopy(original)
            change(self.reports["arm64"])
            with self.subTest(change=changes.index(change)), self.assertRaises(gate.GateError):
                self.verify()

    def test_fake_json_zero_cases_and_skips_do_not_pass(self):
        for count in (0, 5, True):
            self.reports["arm64"]["executed_cases"] = count
            with self.assertRaises(gate.GateError):
                self.verify()
        self.reports["arm64"]["executed_cases"] = 6
        self.reports["arm64"]["suites"].pop()
        with self.assertRaises(gate.GateError):
            self.verify()

    def test_raw_bundle_tampering_fails_before_parse(self):
        bundle = self.evidence / "arm64/E2E-TM001-001/native.xcresult"
        (bundle / "database.sqlite3").write_bytes(b"tampered")
        with mock.patch.object(gate.native, "parse_bundle") as parse, self.assertRaises(gate.GateError):
            self.verify()
        parse.assert_not_called()

    def test_parser_mutation_of_sqlite_fails_after_all_reads(self):
        def mutate(root, bundle):
            answer = self.parse_bundle(root, bundle)
            (bundle / "database.sqlite3").write_bytes(b"changed by native reader")
            return answer
        with mock.patch.object(gate.native, "parse_bundle", side_effect=mutate), self.assertRaises(gate.GateError):
            self.verify()

    def test_native_zero_skip_wrong_arch_and_stale_times_refused(self):
        for field, value in (("totalTestCount", 0), ("skippedTests", 1), ("expectedFailures", 1),
                             ("startTime", self.now - 15000)):
            def altered(root, bundle, field=field, value=value):
                tree, summary = self.parse_bundle(root, bundle)
                summary[field] = value
                return tree, summary
            with self.subTest(field=field), mock.patch.object(gate.native, "parse_bundle", side_effect=altered), self.assertRaises(gate.GateError):
                self.verify()
        def wrong_arch(root, bundle):
            tree, summary = self.parse_bundle(root, bundle)
            summary["devicesAndConfigurations"][0]["device"]["architecture"] = "x86_64"
            return tree, summary
        with mock.patch.object(gate.native, "parse_bundle", side_effect=wrong_arch), self.assertRaises(gate.GateError):
            self.verify()
        self.reports["arm64"]["platform"]["macos"] = "14.8"
        with self.assertRaises(gate.GateError):
            self.verify()

    def test_duplicate_or_foreign_native_case_cannot_fill_required_count(self):
        original = copy.deepcopy(self.reports["arm64"]["suites"])
        self.reports["arm64"]["suites"][-1] = copy.deepcopy(original[0])
        with self.assertRaises(gate.GateError):
            self.verify()
        self.reports["arm64"]["suites"] = original
        self.reports["arm64"]["suites"][-1]["native_test"] = "OtherTests/OtherSuite/testFakeSuccess"
        with self.assertRaises(gate.GateError):
            self.verify()

    def test_fixture_hashes_are_recomputed_from_fixed_data_program(self):
        suite = self.reports["arm64"]["suites"][0]
        path = self.evidence / "arm64" / suite["fixture_manifest"]
        fixture = json.loads(path.read_text())
        fixture["files"]["expected.json"] = "0" * 64
        path.write_text(json.dumps(fixture))
        suite["fixture_sha256"] = gate.native.sha256(path)
        with self.assertRaises(gate.GateError):
            self.verify()

    def test_artifact_escape_and_symlink_parent_refused(self):
        for relative in ("../outside", "/etc/hosts", "case/../result.json", "", "a\\b"):
            with self.subTest(relative=relative), self.assertRaises(gate.GateError):
                gate.safe_artifact(self.evidence, relative)
        (self.evidence / "alias").symlink_to(self.evidence / "arm64", target_is_directory=True)
        with self.assertRaises(gate.GateError):
            gate.safe_artifact(self.evidence, "alias/result.json")

    def test_update_request_log_cannot_skip_invalid_signature_download(self):
        suite = self.reports["arm64"]["suites"][3]
        path = self.evidence / "arm64" / suite["update_requests_artifact"]
        events = json.loads(path.read_text())
        path.write_text(json.dumps([e for e in events if not (e["path"] == "/update.zip" and e.get("mode") == "invalid")]))
        suite["update_requests_sha256"] = gate.native.sha256(path)
        with self.assertRaises(gate.GateError):
            self.verify()

    def test_database_restore_is_compared_from_raw_sqlite(self):
        report = self.reports["arm64"]
        path = self.evidence / "arm64/restored.db"
        with sqlite3.connect(path) as db:
            db.execute("UPDATE users SET role='member'")
        report["sqlite_restore"]["restored_sha256"] = gate.native.sha256(path)
        with self.assertRaises(gate.GateError):
            self.verify()

    def test_restore_rejects_incomplete_schema_even_with_matching_initial_user(self):
        path = self.root / "incomplete.db"
        with sqlite3.connect(path) as db:
            db.executescript("CREATE TABLE alembic_version(version_num TEXT); INSERT INTO alembic_version VALUES('0001');"
                             "CREATE TABLE tokenmeter_seed_owner(environment TEXT,run_id TEXT); INSERT INTO tokenmeter_seed_owner VALUES('production','production-init');"
                             "CREATE TABLE users(username TEXT,role TEXT,is_active INTEGER); INSERT INTO users VALUES('admin','admin',1);")
        with self.assertRaises(gate.GateError):
            gate.sqlite_contents(path)

    def test_restore_requires_forced_change_and_complete_account_columns(self):
        for index, sql in enumerate(("UPDATE users SET must_change_password=0", "ALTER TABLE users DROP COLUMN password_hash")):
            path = self.root / f"bad-schema-{index}.db"
            with sqlite3.connect(self.evidence / "arm64/backup.db") as source, sqlite3.connect(path) as target:
                source.backup(target)
                target.execute(sql)
                target.commit()
            with self.subTest(sql=sql), self.assertRaises(gate.GateError):
                gate.sqlite_contents(path)

    def protection(self):
        return {"state": "PASS", "scope": "release_context_only", "release_eligible": False,
                "release_id": RID, "candidate_sha": SHA, "run_id": RUN, "ci": self.ci,
                "verified_at": self.stamp(-120), "remote": {
                    "branch": {"protected": True, "commit": {"sha": SHA}, "protection": {"enabled": True,
                        "required_status_checks": {"enforcement_level": "everyone", "contexts": sorted(gate.publish_tool.CHECKS)}}},
                    "checks": [{"name": name, "status": "completed", "conclusion": "success", "head_sha": SHA,
                                "app": {"slug": "github-actions"}} for name in gate.publish_tool.CHECKS],
                    "environment": {"deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True}},
                    "policies": {"branch_policies": [{"name": "master", "type": "branch"}]}}}

    def test_protection_evidence_requires_exact_run_checks_and_master_policy(self):
        original = self.protection()
        path = self.json("preflight.json", original)
        self.assertEqual(gate.verify_protection(path, RID, SHA, RUN, self.ci, self.now)["sha256"], gate.native.sha256(path))
        changes = [lambda x: x.update(run_id="old-run"), lambda x: x.update(verified_at=self.stamp(-15000)),
                   lambda x: x["remote"]["branch"].update(protected=False),
                   lambda x: x["remote"]["checks"][0].update(conclusion="skipped"),
                   lambda x: x["remote"]["policies"]["branch_policies"].append({"name": "*", "type": "branch"}),
                   lambda x: x.update(release_eligible=0)]
        for change in changes:
            value = copy.deepcopy(original)
            change(value)
            path.write_text(json.dumps(value))
            with self.subTest(change=changes.index(change)), self.assertRaises(gate.GateError):
                gate.verify_protection(path, RID, SHA, RUN, self.ci, self.now)

    def test_package_claims_reject_wrong_sha_cleanup_or_changed_asset_before_native_tools(self):
        folder = self.root / "package"
        folder.mkdir()
        config = self.json(f"releases/{RID}/internal-release.json", self.config)
        manifest = {"schema_version": 1, "release_id": RID, "distribution_profile": "internal",
                    "candidate_sha": SHA, "config_sha256": gate.native.sha256(config), "ci": self.ci,
                    "cleanup_completed": True, "release_eligible": False,
                    "started_at": self.stamp(-90), "finished_at": self.stamp(-70), "artifacts": {}}
        for name in ("dmg", "candidate_zip", "update_zip", "server_zip"):
            path = folder / name
            path.write_bytes(b"synthetic package bytes: " + name.encode())
            manifest["artifacts"][name] = {"path": name, "sha256": gate.native.sha256(path), "bytes": path.stat().st_size}
        manifest_path = folder / "manifest.json"
        cases = [("candidate_sha", "c" * 40), ("cleanup_completed", False), ("release_eligible", 0), ("schema_version", True)]
        for field, value in cases:
            manifest_path.write_text(json.dumps(manifest | {field: value}))
            with self.subTest(field=field), self.assertRaises(gate.GateError):
                gate.verify_package(self.root, manifest_path, self.config, SHA, self.ci, self.now)
        manifest_path.write_text(json.dumps(manifest))
        (folder / "dmg").write_bytes(b"changed")
        with self.assertRaises(gate.GateError):
            gate.verify_package(self.root, manifest_path, self.config, SHA, self.ci, self.now)

    def test_package_archive_rejects_traversal_and_external_symlink(self):
        import zipfile
        for index, name in enumerate(("../escape", "/outside", "TokenMeter.app/../../escape")):
            path = self.root / f"bad-{index}.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(name, "synthetic")
            with self.assertRaises(gate.GateError):
                gate.validate_zip(path, app_only=True)
        path = self.root / "link.zip"
        with zipfile.ZipFile(path, "w") as archive:
            entry = zipfile.ZipInfo("TokenMeter.app/Contents/link")
            entry.external_attr = 0o120777 << 16
            archive.writestr(entry, "/etc/passwd")
        with self.assertRaises(gate.GateError):
            gate.validate_zip(path, app_only=True)

    def test_archived_restore_must_not_contain_sessions(self):
        for name in ("backup.db", "restored.db"):
            path = self.evidence / "arm64" / name
            with sqlite3.connect(path) as db:
                db.execute("INSERT INTO sessions VALUES('synthetic-hash','synthetic-user',1,1)")
            key = "backup_sha256" if name.startswith("backup") else "restored_sha256"
            self.reports["arm64"]["sqlite_restore"][key] = gate.native.sha256(path)
        with self.assertRaises(gate.GateError):
            self.verify()

    def test_failure_or_blocked_never_emits_a_passport(self):
        for index, exception in enumerate((gate.GateError("invalid evidence"), gate.GateBlocked("missing platform"))):
            output = self.root / f"output-{index}"
            with mock.patch.object(gate, "verify_release", side_effect=exception):
                status = gate.main(["--root", str(self.root), "--package-manifest", str(self.root / "package.json"),
                                    "--evidence", str(self.evidence), "--protection", str(self.root / "preflight.json"),
                                    "--candidate-sha", SHA, "--run-id", RUN, "--output", str(output)])
            self.assertNotEqual(status, 0)
            self.assertEqual(list(output.glob("*.passport.json")), [])
            self.assertIs(json.loads((output / "report.json").read_text())["release_eligible"], False)


if __name__ == "__main__":
    unittest.main()
