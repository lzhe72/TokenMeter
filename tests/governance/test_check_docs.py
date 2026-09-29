"""Read-only documentation governance tests; never product E2E evidence."""

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/check_docs.py"
SPEC = importlib.util.spec_from_file_location("check_docs", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)
RELEASE_ID = "v0.0.1-20260929T060944Z"


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "repository"
        self.root.mkdir()
        self.current = {"schema_version": 1, "release_id": RELEASE_ID}
        release_docs = {key: f"releases/{RELEASE_ID}/{key.replace('_', '-')}.md"
                        for key in checker.RELEASE_DOCS}
        self.manifest = {"schema_version": 1, "release_id": RELEASE_ID, "version": "0.0.1",
                         "created_at": "2026-09-29T06:09:44Z", "documents": release_docs,
                         "publication": {"planned_git_tag": RELEASE_ID}, "changelog": "CHANGELOG.md"}
        document_paths = ["AGENTS.md", "readme.md", "CHANGELOG.md", "docs/standard.md", "sop/README.md",
                          *("sop/" + name for name in checker.SOP_FILES.values()), *sorted(release_docs.values())]
        self.catalog = {"schema_version": 1, "documents": []}
        for number, path in enumerate(document_paths):
            self.write(path, f"# Synthetic governance document\n\n{RELEASE_ID}\n")
            self.catalog["documents"].append({
                "doc_id": f"DOC-{number:03d}", "path": path, "type": "standard", "status": "baselined",
                "applicable_release": "all", "base_release": None, "inputs": ["docs/standard.md"],
                "updated_at": "2026-09-29", "sop": "sop/SOP-000-maintenance.md"})
        for identifier, filename in checker.SOP_FILES.items():
            body = f"# {identifier} Synthetic workflow\n\n"
            body += "\n\n".join(f"## {section}\n\nSynthetic unit-test section content." for section in checker.SOP_SECTIONS)
            self.write("sop/" + filename, body + "\n")
        self.index_body = "# SOP work index\n\n| 工作 | SOP | 状态 | 修订 |\n| --- | --- | --- | --- |\n"
        self.index_body += "".join(f"| Work | [{identifier}]({filename}) | baselined | 1 |\n"
                                   for identifier, filename in checker.SOP_FILES.items())
        self.index_body += "\n" + "\n\n".join(f"## {route}\n\nFollow the workflow." for route in checker.SOP_ROUTES) + "\n"
        self.write("sop/README.md", self.index_body)
        self.write("AGENTS.md", "# Agent instructions\n\nRead the [SOP index](sop/README.md) first.\n")
        self.write("CHANGELOG.md", f"# Changelog\n\n## {RELEASE_ID}\n\nSynthetic release.\n")
        self.persist()

    def write(self, relative, body):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def persist(self):
        self.write("docs/catalog.json", json.dumps(self.catalog))
        self.write("releases/current.json", json.dumps(self.current))
        self.write(f"releases/{RELEASE_ID}/manifest.json", json.dumps(self.manifest))

    def errors(self):
        self.persist()
        return checker.validate_docs(self.root)[0]

    def test_valid_baseline_is_read_only_and_never_grants_release_eligibility(self):
        before = {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        errors, counts = checker.validate_docs(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(counts["documents"], len(self.catalog["documents"]))
        self.assertEqual(counts["baselined"], counts["documents"])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(checker.main([], root=self.root), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["scope"], "documentation_baseline_only")
        self.assertFalse(result["release_eligible"])
        after = {str(path): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_missing_metadata_sop_and_inputs_are_reported(self):
        first = self.catalog["documents"][0]
        del first["updated_at"]
        first["sop"] = "docs/absent.md#sop-000"
        first["inputs"] = []
        errors = self.errors()
        for message in ("missing metadata", ".sop", "nonempty inputs list"):
            self.assertTrue(any(message in error for error in errors), errors)

    def test_unregistered_markdown_fails_but_local_artifacts_are_excluded(self):
        self.write(".local/notes.md", "Private output not part of baseline.\n")
        self.assertEqual(self.errors(), [])
        for path in ("docs/unregistered.md", "tests/unregistered.md", "releases/unregistered.md"):
            self.write(path, "Missing catalog entry.\n")
        errors = self.errors()
        self.assertEqual(sum("unregistered Markdown" in error for error in errors), 3)

    def test_duplicate_ids_and_paths_fail(self):
        self.catalog["documents"].append(copy.deepcopy(self.catalog["documents"][0]))
        errors = self.errors()
        self.assertTrue(any("duplicate doc_id" in error for error in errors))
        self.assertTrue(any("duplicate document path" in error for error in errors))

    def test_current_and_all_drafts_block_but_superseded_is_allowed(self):
        row = self.catalog["documents"][0]
        row["status"] = "draft"
        for applicable in ("all", RELEASE_ID):
            row["applicable_release"] = applicable
            self.assertTrue(any("active document is draft" in error for error in self.errors()))
        row["status"] = "superseded"
        self.assertEqual(self.errors(), [])

    def test_invalid_metadata_types_and_dates_fail_without_crashing(self):
        original = copy.deepcopy(self.catalog["documents"][0])
        invalid_fields = {"doc_id": [], "type": [], "status": {}, "applicable_release": [],
                          "base_release": 1, "inputs": "docs/standard.md", "updated_at": "2026-02-30",
                          "sop": {}, "path": []}
        for field, value in invalid_fields.items():
            with self.subTest(field=field):
                self.catalog["documents"][0] = copy.deepcopy(original)
                self.catalog["documents"][0][field] = value
                self.assertTrue(self.errors())

    def test_catalog_and_release_schema_require_integer_one(self):
        for document in (self.catalog, self.current, self.manifest):
            for invalid in (True, "1", 2):
                with self.subTest(value=invalid):
                    document["schema_version"] = invalid
                    self.assertTrue(self.errors())
            document["schema_version"] = 1

    def test_release_id_version_time_and_tag_must_agree(self):
        original = copy.deepcopy(self.manifest)
        for field, value in (("release_id", "v0.0.2-20260929T060944Z"), ("version", "0.0.2"),
                             ("created_at", "2026-09-29T06:09:45Z")):
            with self.subTest(field=field):
                self.manifest = copy.deepcopy(original)
                self.manifest[field] = value
                self.assertTrue(any(field in error for error in self.errors()))
        self.manifest = original
        self.manifest["publication"]["planned_git_tag"] = "other"
        self.assertTrue(any("planned_git_tag" in error for error in self.errors()))

    def test_release_id_timestamp_must_exist_on_calendar(self):
        for invalid in ("0.0.1", "v0.0.1-20260230T060944Z", "v0.0.1-20260929T256000Z",
                        "../../elsewhere", None):
            with self.subTest(release=invalid):
                self.current["release_id"] = invalid
                self.assertTrue(any("invalid release_id" in error for error in self.errors()))

    def test_each_release_document_and_exact_changelog_heading_are_required(self):
        path = self.manifest["documents"]["requirements"]
        self.write(path, "No release identity in this requirement document.\n")
        del self.manifest["documents"]["test_plan"]
        self.write("CHANGELOG.md", f"# Changelog\n\n## {RELEASE_ID}-wrong\n")
        errors = self.errors()
        for message in ("body must contain", "release.documents.test_plan", "missing exact heading"):
            self.assertTrue(any(message in error for error in errors), errors)

    def test_paths_and_manifest_symlinks_cannot_escape_repository(self):
        outside = self.base / "outside.md"
        outside.write_text("Outside the workspace.\n")
        link = self.root / "docs/foreign.md"
        link.symlink_to(outside)
        for value in ("../outside.md", str(outside), "docs/foreign.md"):
            self.catalog["documents"][0]["inputs"] = [value]
            self.assertTrue(any("remain inside repository" in error for error in self.errors()))
        link.unlink()
        self.catalog["documents"][0]["inputs"] = ["docs/standard.md"]
        self.persist()
        path = self.root / "docs/catalog.json"
        foreign_catalog = self.base / "catalog.json"
        foreign_catalog.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(foreign_catalog)
        self.assertTrue(any("remain inside repository" in error for error in checker.validate_docs(self.root)[0]))

    def test_internal_markdown_links_are_checked_and_code_samples_are_ignored(self):
        self.write("docs/standard.md", """# Standard

[SOP](../sop/SOP-000-maintenance.md) [External](https://example.com/missing)
[Contact](mailto:test@example.com) [Section](#missing-anchor)
`[not a link](nonexistent-inline.md)`

```markdown
[Example only](nonexistent-code.md)
```

~~~markdown
[Example only](nonexistent-tilde-code.md)
~~~
""")
        self.assertEqual(self.errors(), [])
        with (self.root / "docs/standard.md").open("a") as output:
            output.write("\n[Broken](missing.md)\n[reference]: missing-reference.md\n")
        errors = self.errors()
        self.assertEqual(sum(".link" in error for error in errors), 2)

    def test_sop_index_requires_each_of_the_25_ids_once(self):
        row = "| Work | [SOP-000](SOP-000-maintenance.md) | baselined | 1 |\n"
        for altered, expected in ((self.index_body.replace(row, ""), "missing file mappings: SOP-000"),
                                  (self.index_body + row, "duplicate file mapping for SOP-000")):
            with self.subTest(expected=expected):
                self.write("sop/README.md", altered)
                self.assertTrue(any(expected in error for error in self.errors()))

    def test_sop_file_requires_matching_title_and_nonempty_contract_sections(self):
        path = self.root / "sop/SOP-010-test-data.md"
        original = path.read_text()
        replacements = (("# SOP-010", "# SOP-011", "H1 must start"),
                        ("## 前置条件", "## Another heading", "required section '前置条件'"),
                        ("## 输入\n\nSynthetic unit-test section content.", "## 输入", "section '输入' is empty"),
                        ("## 执行步骤", "```markdown\n## 执行步骤\n```", "required section '执行步骤'"))
        for before, after, expected in replacements:
            with self.subTest(expected=expected):
                path.write_text(original.replace(before, after))
                self.assertTrue(any(expected in error for error in self.errors()))
        path.unlink()
        self.assertTrue(any("SOP-010" in error and "does not exist" in error for error in self.errors()))

    def test_sop_role_filename_cannot_replace_approved_workflow(self):
        original = "SOP-001-version-start.md"
        substituted = "SOP-001-product-manager.md"
        (self.root / "sop" / original).rename(self.root / "sop" / substituted)
        self.write("sop/README.md", self.index_body.replace(original, substituted))
        for row in self.catalog["documents"]:
            if row["path"] == "sop/" + original:
                row["path"] = "sop/" + substituted
        self.assertTrue(any("approved work-based filename" in error for error in self.errors()))

    def test_catalog_rejects_old_aggregated_sop_references(self):
        self.write("docs/sop/lifecycle.md", "# Historical aggregate\n\n## SOP-000\n")
        self.catalog["documents"][0]["sop"] = "docs/sop/lifecycle.md#sop-000"
        self.assertTrue(any("mapped independent root" in error for error in self.errors()))

    def test_root_agent_instructions_must_link_to_sop_index(self):
        self.write("AGENTS.md", "# Agent instructions\n\nThe SOP index is sop/README.md.\n")
        self.assertTrue(any("AGENTS.md: must link" in error for error in self.errors()))

    def test_index_requires_common_routes_status_and_revision(self):
        altered = self.index_body.replace("## 修复问题", "## Other route").replace("| baselined | 1 |", "| baselined | |", 1)
        self.write("sop/README.md", altered)
        errors = self.errors()
        self.assertTrue(any("missing common task route 修复问题" in error for error in errors))
        self.assertTrue(any("nonempty revision" in error for error in errors))

    def test_unknown_sop_markdown_requires_registration_and_is_not_a_workflow(self):
        self.write("sop/manager.md", "# A role-specific extra document\n")
        errors = self.errors()
        self.assertTrue(any("unexpected Markdown files" in error for error in errors))
        self.assertTrue(any("unregistered Markdown document: sop/manager.md" in error for error in errors))

    def test_referenced_release_must_have_existing_manifest_with_same_id(self):
        historical = "v0.0.0-20260928T060944Z"
        row = self.catalog["documents"][0]
        row.update(status="draft", applicable_release=historical, base_release=historical)
        self.assertTrue(any("existing same-ID manifest" in error for error in self.errors()))
        self.write(f"releases/{historical}/manifest.json", json.dumps({"schema_version": 1, "release_id": RELEASE_ID}))
        self.assertTrue(any("existing same-ID manifest" in error for error in self.errors()))
        self.write(f"releases/{historical}/manifest.json", json.dumps({"schema_version": 1, "release_id": historical}))
        self.assertEqual(self.errors(), [])
        manifest = self.root / f"releases/{historical}/manifest.json"
        external = self.base / "external-manifest.json"
        external.write_bytes(manifest.read_bytes())
        manifest.unlink()
        manifest.symlink_to(external)
        self.assertTrue(any("remain inside repository" in error for error in self.errors()))

    def test_release_plan_cannot_be_replaced_by_release_notes(self):
        old = self.manifest["documents"]["release_plan"]
        replacement = old.replace("release-plan.md", "release-notes.md")
        (self.root / old).rename(self.root / replacement)
        self.manifest["documents"]["release_plan"] = replacement
        for row in self.catalog["documents"]:
            if row["path"] == old:
                row["path"] = replacement
        self.assertTrue(any("expected release-plan.md" in error for error in self.errors()))

    def test_release_document_keys_cannot_reuse_one_file(self):
        target = self.manifest["documents"]["release_plan"]
        self.manifest["documents"] = {key: target for key in self.manifest["documents"]}
        errors = self.errors()
        self.assertEqual(sum("release.documents." in error and ": expected " in error for error in errors), 5)

    def test_sop_hidden_in_html_comment_does_not_satisfy_contract(self):
        path = self.root / "sop/SOP-010-test-data.md"
        path.write_text("<!--\n" + path.read_text() + "\n-->\n")
        errors = self.errors()
        self.assertTrue(any("SOP-010: H1 must start" in error for error in errors))
        self.assertTrue(any("SOP-010: required section '执行步骤'" in error for error in errors))

    def test_changelog_release_heading_must_be_visible_outside_examples(self):
        for hidden in (f"```markdown\n## {RELEASE_ID}\n```", f"<!--\n## {RELEASE_ID}\n-->"):
            with self.subTest(hidden=hidden):
                self.write("CHANGELOG.md", "# Changelog\n\n" + hidden + "\n")
                self.assertTrue(any("missing exact heading" in error for error in self.errors()))

    def test_unregistered_symlink_cannot_borrow_registered_document_identity(self):
        alias = self.root / "docs/undeclared-alias.md"
        alias.symlink_to(self.root / "docs/standard.md")
        self.assertTrue(any("unregistered Markdown document: docs/undeclared-alias.md" in error for error in self.errors()))
        registered = copy.deepcopy(self.catalog["documents"][0])
        registered.update(doc_id="DOC-ALIAS", path="docs/undeclared-alias.md")
        self.catalog["documents"].append(registered)
        self.assertTrue(any("duplicate document path: docs/undeclared-alias.md" in error for error in self.errors()))

    def test_failed_cli_returns_one_and_false_release_eligibility(self):
        self.catalog["documents"][0]["status"] = "draft"
        self.persist()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(checker.main([], root=self.root), 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result["state"], "FAIL")
        self.assertFalse(result["release_eligible"])
        self.assertTrue(result["errors"])


if __name__ == "__main__":
    unittest.main()
