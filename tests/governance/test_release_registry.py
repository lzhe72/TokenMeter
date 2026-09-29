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
                         "publication": {"state": "not_published", "expected_passport_asset": ID + ".passport.json"}}
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

    def test_missing_record_is_structured_cli_failure(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = registry.main(["show", "--release-id", "v9.0.0-20260929T040000Z"], root=self.root)
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output.getvalue())["release_eligible"])


if __name__ == "__main__":
    unittest.main()
