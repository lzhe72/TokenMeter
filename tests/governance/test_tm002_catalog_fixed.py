"""TC-TM002-CATALOG-01: fixed, isolated release/TASK ownership checks.

These are governance tests over copies of the design catalog. They never run
the App and cannot serve as product E2E evidence.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import export_test_cases


ROOT = Path(__file__).resolve().parents[2]
CASE_IDS = ("TC-TM001-LOGIN-01", "TC-TM002-SELECT-01")
OWNER = "TC-TM002-CATALOG-01"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FixedCatalogOwnershipTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ROOT / "tests/test_cases.json"
        self.source_sha = digest(self.source)
        source_catalog = json.loads(self.source.read_text(encoding="utf-8"))
        self.assertEqual(source_catalog["release_id"], "v0.2.0-20261001T034118Z")
        copied = {case["id"]: case for case in source_catalog["cases"] if case["id"] in CASE_IDS}
        self.assertEqual(set(copied), set(CASE_IDS))
        self.pristine = {"schema_version": 1, "release_id": source_catalog["release_id"],
                         "cases": [copy.deepcopy(copied[identity]) for identity in CASE_IDS]}
        self.temporary = tempfile.TemporaryDirectory(prefix="tm002-catalog-fixed-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / "owner.json").write_text(json.dumps({"owner": OWNER}), encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "docs/testing/cases").mkdir(parents=True)
        shutil.copyfile(ROOT / "tests/acceptance.json", self.root / "tests/acceptance.json")
        for row in self.pristine["cases"]:
            release_id = row.get("release_id", self.pristine["release_id"])
            release = self.root / "releases" / release_id
            release.mkdir(parents=True, exist_ok=True)
            for name in ("00-manifest.json", "02-breakdown.md"):
                shutil.copyfile(ROOT / "releases" / release_id / name, release / name)
            document = self.root / row["source"]["path"]
            document.write_text("## " + row["source"]["heading"] + "\n", encoding="utf-8")
            row["source"]["line"] = 1
        self.assertEqual(export_test_cases.validate_catalog(self.pristine, self.root), [])
        self.assertEqual(digest(self.source), self.source_sha)

    def run_variant(self, variant: str) -> tuple[int, dict, dict]:
        self.assertEqual(json.loads((self.root / "owner.json").read_text())["owner"], OWNER)
        value = copy.deepcopy(self.pristine)
        selected = value["cases"][1]
        if variant == "MISSING_TASK":
            selected.pop("task_ids")
        elif variant == "WRONG_RELEASE":
            selected["release_id"] = value["cases"][0].get("release_id", "v0.1.0-20260929T074814Z")
        elif variant != "VALID":
            self.fail("Unknown fixed variant")
        copied_catalog = self.root / "tests/test_cases.json"
        copied_catalog.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        copied_sha = digest(copied_catalog)
        (self.root / "TEST_CASES.md").write_text(export_test_cases.render_markdown(self.pristine), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            exit_code = export_test_cases.main(["--check"], root=self.root)
        result = json.loads(captured.getvalue())
        self.assertEqual(digest(copied_catalog), copied_sha, "validator must not overwrite its input")
        self.assertEqual(digest(self.source), self.source_sha, "repository source catalog must be untouched")
        self.assertEqual({case["id"] for case in json.loads(copied_catalog.read_text())["cases"]}, set(CASE_IDS))
        return exit_code, result, value

    def test_TC_TM002_CATALOG_01_VALID(self) -> None:
        code, output, value = self.run_variant("VALID")
        self.assertEqual(code, 0, output)
        self.assertEqual(output["state"], "CURRENT")
        self.assertEqual(output["cases"], 2)
        self.assertEqual(value["cases"][0]["task_ids"], ["TASK-TM001-LOGIN-AUTH"])
        self.assertEqual(value["cases"][1]["task_ids"], ["TASK-TM002-PICKER"])

    def test_TC_TM002_CATALOG_01_MISSING_TASK(self) -> None:
        code, output, value = self.run_variant("MISSING_TASK")
        self.assertNotEqual(code, 0)
        self.assertEqual(output["state"], "INVALID")
        self.assertNotIn("task_ids", value["cases"][1])
        self.assertTrue(any("TC-TM002-SELECT-01" in error and "task_ids" in error
                            for error in output["errors"]), output)

    def test_TC_TM002_CATALOG_01_WRONG_RELEASE(self) -> None:
        code, output, value = self.run_variant("WRONG_RELEASE")
        self.assertNotEqual(code, 0)
        self.assertEqual(output["state"], "INVALID")
        self.assertEqual(value["cases"][1]["release_id"], "v0.1.0-20260929T074814Z")
        self.assertTrue(any("TC-TM002-SELECT-01" in error and "does not belong to release" in error
                            for error in output["errors"]), output)
        self.assertTrue(any("TC-TM002-SELECT-01" in error and "unregistered TASK" in error
                            for error in output["errors"]), output)


if __name__ == "__main__":
    unittest.main()
