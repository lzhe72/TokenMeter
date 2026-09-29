"""Release lookup regressions; local temporary Git repositories, no network."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("release_registry", ROOT / "scripts/release_registry.py")
registry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registry)
ID = "v0.1.0-20260929T040000Z"


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.documents = {key: f"releases/{ID}/{filename}" for key, filename in (
            ("requirements", "01-requirements.md"), ("breakdown", "02-breakdown.md"),
            ("development_plan", "03-development-plan.md"), ("test_plan", "04-test-plan.md"),
            ("release_plan", "05-release-plan.md"), ("iteration_record", "06-iteration-record.md"))}
        for path in self.documents.values():
            self.write(path, f"# {ID}\nSynthetic lifecycle record\n")
        self.write("releases/current.json", {"schema_version": 1, "release_id": ID})
        self.write("tests/features.json", {"schema_version": 1, "features": [{"id": "TM-001", "cases": ["case-1"]}]})
        self.write("CHANGELOG.md", f"# Changelog\n\n## {ID}\n\nTest release\n\n## v0.0.1-20260928T000000Z\nOld\n")
        self.manifest = {"schema_version": 1, "release_id": ID, "version": "0.1.0",
                         "created_at": "2026-09-29T04:00:00Z", "feature_ids": ["TM-001"],
                         "documents": self.documents, "changelog": "CHANGELOG.md",
                         "product_feature_matrix": "tests/features.json",
                         "traceability": [{"requirement": "REQ-TM001-001", "feature": "TM-001",
                                          "task": "TASK-TM001-001", "test": "E2E-TM001-001"}],
                         "test_programs": ["tests/test_fixture.py"], "test_data_program": "scripts/data.py",
                         "test_sop": "sop/SOP-014-e2e.md",
                         "publication": {"planned_git_tag": ID, "state": "not_published", "expected_passport_asset": ID + ".passport.json"}}
        for key, identifiers in (("requirements", "REQ-TM001-001"),
                                 ("breakdown", "TM-001 TASK-TM001-001"), ("test_plan", "E2E-TM001-001")):
            self.write(self.documents[key], f"# {ID}\n\n{identifiers}\n")
        self.write("tests/test_fixture.py", "# Synthetic test program\n")
        self.write("scripts/data.py", "# Synthetic data program\n")
        self.write("sop/SOP-014-e2e.md", "# SOP-014 E2E\n")
        self.write("sop/README.md", "[SOP-014](SOP-014-e2e.md)\n")
        self.catalog = {"schema_version": 1, "documents": [
            {"path": path, "applicable_release": ID, "status": "baselined"} for path in self.documents.values()]}
        self.write("docs/catalog.json", self.catalog)
        self.persist()

    def write(self, path, value):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
        return file

    def persist(self):
        self.write(f"releases/{ID}/00-manifest.json", self.manifest)

    def test_default_and_explicit_lookup_preserve_unpublished_status(self):
        for identifier in (None, ID):
            result = registry.show(self.root, identifier)
            self.assertEqual(result["release_id"], ID)
            self.assertEqual(result["source"]["kind"], "working_tree")
            self.assertEqual(result["source"]["manifest"], f"releases/{ID}/00-manifest.json")
            self.assertEqual(result["documents"], self.documents)
            self.assertEqual(result["product_features"][0]["cases"], ["case-1"])
            self.assertNotIn("Old", result["changelog"]["entry"])
            self.assertIsNone(result["release_eligible"])
            self.assertFalse(result["passport"]["verified"])

    def test_bad_id_or_calendar_date_rejected(self):
        for value in ("../../secret", "--all", "v0.1.0-20260230T000000Z", "v0.1.0-20260929T040000Zx"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                registry.show(self.root, value)

    def test_manifest_version_mismatch_and_missing_documents_rejected(self):
        self.manifest["version"] = "0.2.0"
        self.persist()
        with self.assertRaises(ValueError):
            registry.show(self.root)
        self.manifest["version"] = "0.1.0"
        self.manifest["documents"].pop("test_plan")
        self.persist()
        with self.assertRaises(ValueError):
            registry.show(self.root)

    def test_lifecycle_documents_require_ordered_paths_in_same_release(self):
        for path in ("other.md", f"releases/{ID}/test-plan.md", f"releases/{ID}/05-test-plan.md"):
            with self.subTest(path=path):
                self.manifest["documents"]["test_plan"] = path
                self.write(path, ID)
                self.persist()
                with self.assertRaises(ValueError):
                    registry.show(self.root)

    def test_external_references_and_symlinks_refused(self):
        self.manifest["changelog"] = "../outside.md"
        self.persist()
        with self.assertRaises(ValueError):
            registry.show(self.root)
        self.manifest["changelog"] = "CHANGELOG.md"
        self.persist()
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "outside.md"
            outside.write_text(ID)
            link = self.root / "CHANGELOG.md"
            link.unlink()
            link.symlink_to(outside)
            with self.assertRaises(ValueError):
                registry.show(self.root)

    def test_tag_query_reads_immutable_archive_instead_of_changed_working_tree(self):
        def git(*args):
            return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True)
        git("init", "-q")
        git("add", ".")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", f"[{ID}][TM-001] test: fixture")
        git("tag", ID)
        self.manifest["version"] = "later development"
        self.persist()
        git("add", ".")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", f"[{ID}][TM-001] test: after tag")
        self.manifest["version"] = "bad working copy"
        self.persist()
        result = registry.show(self.root, ID)
        self.assertEqual(result["source"]["kind"], "git_tag")
        self.assertEqual(result["source"]["manifest"], f"releases/{ID}/00-manifest.json")
        self.assertEqual(result["source"]["commit"], git("rev-parse", f"{ID}^{{commit}}").stdout.strip())
        self.assertEqual(result["version"], "0.1.0")
        self.assertEqual(len(result["commits"]), 1)
        self.assertFalse(result["passport"]["verified"])

    def test_broken_traceability_or_program_references_cannot_be_queried(self):
        original = json.loads(json.dumps(self.manifest))
        for field, value in (("traceability", []), ("test_programs", ["tests/missing.py"]),
                             ("test_data_program", "scripts/missing.py"), ("test_sop", "sop/missing.md")):
            with self.subTest(field=field):
                self.manifest = {**original, field: value}
                self.persist()
                with self.assertRaises(ValueError):
                    registry.show(self.root)
        self.manifest = dict(original)
        del self.manifest["traceability"]
        self.persist()
        with self.assertRaises(ValueError):
            registry.show(self.root)

    def test_catalog_release_identity_is_part_of_lookup_contract(self):
        self.catalog["documents"][0]["applicable_release"] = "all"
        self.write("docs/catalog.json", self.catalog)
        with self.assertRaises(ValueError):
            registry.show(self.root)

    def test_tag_snapshot_with_invalid_contract_is_refused_even_if_worktree_fixed(self):
        self.manifest["traceability"] = []
        self.persist()
        for args in (("init", "-q"), ("add", "."),
                     ("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "bad contract"),
                     ("tag", ID)):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)
        self.manifest["traceability"] = [{"requirement": "REQ-TM001-001", "feature": "TM-001",
                                           "task": "TASK-TM001-001", "test": "E2E-TM001-001"}]
        self.persist()
        with self.assertRaises(ValueError):
            registry.show(self.root, ID)

    def test_tag_program_symlink_is_not_a_real_test_program(self):
        program = self.root / "tests/test_fixture.py"
        program.unlink()
        program.symlink_to("../scripts/data.py")
        for args in (("init", "-q"), ("add", "."),
                     ("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "symlink contract"),
                     ("tag", ID)):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)
        program.unlink()
        program.write_text("# Real file in working copy cannot repair immutable tag\n")
        with self.assertRaisesRegex(ValueError, "regular file"):
            registry.show(self.root, ID)

    def test_lookup_refuses_draft_baseline_and_unmapped_sop(self):
        self.catalog["documents"][0]["status"] = "draft"
        self.write("docs/catalog.json", self.catalog)
        with self.assertRaisesRegex(ValueError, "baselined"):
            registry.show(self.root)
        self.catalog["documents"][0]["status"] = "baselined"
        self.write("docs/catalog.json", self.catalog)
        self.write("sop/SOP-015-bugfix.md", "# SOP-015 Bugfix\n")
        self.manifest["test_sop"] = "sop/SOP-015-bugfix.md"
        self.persist()
        with self.assertRaisesRegex(ValueError, "mapped in the SOP index"):
            registry.show(self.root)

    def test_planned_program_bindings_are_visible_without_claiming_execution_readiness(self):
        self.manifest.update(program_bindings_status="planned", test_programs=[], test_data_program=None)
        self.persist()
        result = registry.show(self.root)
        self.assertEqual(result["program_bindings_status"], "planned")
        self.assertFalse(result["program_bindings_ready"])
        self.assertEqual(result["test_programs"], [])
        self.assertIsNone(result["test_data_program"])
        self.assertFalse(result["passport"]["verified"])
        self.assertIsNone(result["release_eligible"])
        self.manifest["program_bindings_status"] = "ready"
        self.persist()
        with self.assertRaises(ValueError):
            registry.show(self.root)

    def test_missing_record_is_structured_cli_failure(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = registry.main(["show", "--release-id", "v9.0.0-20260929T040000Z"], root=self.root)
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output.getvalue())["release_eligible"])


if __name__ == "__main__":
    unittest.main()
