#!/usr/bin/env python3
"""Read-only documentation baseline checks. This does not authorize release."""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_TYPES = {"standard", "design", "plan", "sop", "template", "record", "index", "instructions", "changelog"}
STATUSES = {"draft", "baselined", "superseded"}
RELEASE_PATTERN = re.compile(r"v(\d+\.\d+\.\d+)-(\d{8}T\d{6}Z)\Z")
RELEASE_DOCS = {
    "requirements": "01-requirements.md",
    "breakdown": "02-breakdown.md",
    "development_plan": "03-development-plan.md",
    "test_plan": "04-test-plan.md",
    "release_plan": "05-release-plan.md",
    "iteration_record": "06-iteration-record.md",
}
SOP_SECTIONS = ("目的与范围", "触发条件", "前置条件", "输入", "执行步骤", "输出", "成功与失败判据", "异常恢复", "证据位置", "下一步")
SOP_ROUTES = ("新增功能", "修复问题", "准备发布", "维护文档")
SOP_SLUGS = ("maintenance", "version-start", "requirements", "feature-breakdown", "technical-design",
             "development-plan", "test-plan", "release-plan", "baseline-check", "environment", "test-data",
             "test-implementation", "development", "build-and-check", "e2e", "bugfix", "database-migration",
             "package-validation", "release-gate", "git-release", "deployment", "rollback", "archive-handoff",
             "iteration", "document-change")
SOP_FILES = {f"SOP-{number:03d}": f"SOP-{number:03d}-{slug}.md" for number, slug in enumerate(SOP_SLUGS)}
SOP_IDS = set(SOP_FILES)


def _release_parts(value: Any) -> tuple[str, str] | None:
    match = RELEASE_PATTERN.fullmatch(value) if isinstance(value, str) else None
    if not match:
        return None
    try:
        timestamp = datetime.strptime(match[2], "%Y%m%dT%H%M%SZ")
    except ValueError:
        return None
    return match[1], timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _markdown_content(body: str) -> str:
    """Remove fenced and inline code before interpreting Markdown structure."""
    visible = []
    fence = None
    for line in body.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker[1]
            elif marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            continue
        if fence is None:
            visible.append(re.sub(r"(`+).*?\1", "", line))
    # HTML comments are not visible documentation; ignore them after removing
    # code examples so literal comment markers inside code do not hide prose.
    return re.sub(r"<!--.*?(?:-->|$)", "", "\n".join(visible), flags=re.DOTALL)


def _markdown_targets(body: str) -> list[str]:
    """Read ordinary inline/reference links, excluding fenced and inline code."""
    content = _markdown_content(body)
    inline = re.findall(r"!?\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s)]+))[^\n)]*\)", content)
    references = re.findall(r"^\s{0,3}\[[^\]\n]+\]:\s*(?:<([^>\n]+)>|(\S+))", content, re.MULTILINE)
    return [angle or plain for angle, plain in inline + references]


def validate_docs(root: Path) -> tuple[list[str], dict[str, int]]:
    root = root.resolve()
    errors: list[str] = []
    counts = {"documents": 0, "baselined": 0, "superseded": 0, "links": 0}

    def nonempty(value: Any, label: str) -> bool:
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label}: nonempty text required")
            return False
        return True

    def reference(value: Any, label: str, *, base: Path = root, allow_directory: bool = False) -> Path | None:
        if not nonempty(value, label):
            return None
        try:
            candidate = Path(value)
            path = (base / candidate).resolve()
            if candidate.is_absolute() or not path.is_relative_to(root):
                raise ValueError("path must remain inside repository")
            if not path.exists():
                raise ValueError("referenced path does not exist")
            if not allow_directory and (not path.is_file() or path.stat().st_size == 0):
                raise ValueError("referenced file is absent or empty")
            return path
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f"{label}: {exc}: {value}")
            return None

    def document(relative: str) -> dict:
        path = reference(relative, relative)
        if path is None:
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            errors.append(f"{relative}: {exc}")
            return {}
        if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
            errors.append(f"{relative}: schema_version must be integer 1")
            return {}
        return value

    def text(path: Path | None, label: str) -> str:
        if path is None:
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{label}: {exc}")
            return ""

    current = document("releases/current.json")
    release_id = current.get("release_id")
    parts = _release_parts(release_id)
    if parts is None:
        errors.append("releases/current.json: invalid release_id or timestamp")
        manifest = {}
    else:
        manifest = document(f"releases/{release_id}/00-manifest.json")
        for key, expected in (("release_id", release_id), ("version", parts[0]), ("created_at", parts[1])):
            if manifest.get(key) != expected:
                errors.append(f"release manifest: {key} must match current release ID")
        release_documents = manifest.get("documents")
        if not isinstance(release_documents, dict):
            errors.append("release manifest: documents object required")
            release_documents = {}
        for key, filename in RELEASE_DOCS.items():
            path = reference(release_documents.get(key), f"release.documents.{key}")
            expected_relative = f"releases/{release_id}/{filename}"
            if release_documents.get(key) != expected_relative or (path is not None and path != root / expected_relative):
                errors.append(f"release.documents.{key}: expected {filename} at {expected_relative}")
            if path is not None and release_id not in text(path, f"release.documents.{key}"):
                errors.append(f"release.documents.{key}: body must contain {release_id}")
        publication = manifest.get("publication")
        if not isinstance(publication, dict) or publication.get("planned_git_tag") != release_id:
            errors.append("release publication: planned_git_tag must match release_id")
        changelog = reference(manifest.get("changelog", "CHANGELOG.md"), "release.changelog")
        if not re.search(r"^## " + re.escape(release_id) + r"\s*$", _markdown_content(text(changelog, "release.changelog")), re.MULTILINE):
            errors.append(f"CHANGELOG: missing exact heading '## {release_id}'")
        if "changelog_heading" in manifest and manifest["changelog_heading"] != release_id:
            errors.append("release.changelog_heading must match release_id")

    referenced_releases = {release_id: manifest} if parts is not None else {}

    def release_reference(value: str, label: str) -> None:
        if value not in referenced_releases:
            referenced_releases[value] = document(f"releases/{value}/00-manifest.json")
        if referenced_releases[value].get("release_id") != value:
            errors.append(f"{label}: referenced release needs an existing same-ID manifest")

    sop_index = reference("sop/README.md", "SOP index")
    index_body = _markdown_content(text(sop_index, "SOP index"))
    sop_paths: dict[str, Path] = {}
    mapped_ids: set[str] = set()
    for target in _markdown_targets(index_body):
        filename = Path(target).name
        match = re.match(r"(SOP-\d{3})-.*\.md$", filename)
        if not match:
            continue
        identifier = match[1]
        if identifier not in SOP_IDS:
            errors.append(f"SOP index: unexpected ID {identifier}")
        elif filename != SOP_FILES[identifier]:
            errors.append(f"SOP index {identifier}: expected approved work-based filename {SOP_FILES[identifier]}")
        if identifier in mapped_ids:
            errors.append(f"SOP index: duplicate file mapping for {identifier}")
        mapped_ids.add(identifier)
        path = reference(target, f"SOP index {identifier}", base=root / "sop")
        if path is not None:
            if path.parent != root / "sop" or not re.fullmatch(r"SOP-\d{3}-[a-z0-9]+(?:-[a-z0-9]+)*\.md", filename):
                errors.append(f"SOP index {identifier}: requires one independent root sop/SOP-XXX-slug.md file")
            else:
                sop_paths[identifier] = path
    missing_sops = SOP_IDS - mapped_ids
    if missing_sops:
        errors.append("SOP index: missing file mappings: " + ", ".join(sorted(missing_sops)))
    if len(set(sop_paths.values())) != len(sop_paths):
        errors.append("SOP index: each ID must map to a distinct file")
    table_headers = [line for line in index_body.splitlines() if "|" in line and "状态" in line and "修订" in line]
    if not table_headers:
        errors.append("SOP index: inventory table needs 状态 and 修订 metadata columns")
    else:
        columns = [cell.strip() for cell in table_headers[0].strip().strip("|").split("|")]
        if "状态" not in columns or "修订" not in columns:
            errors.append("SOP index: 状态 and 修订 must be separate inventory columns")
        else:
            table_ids: set[str] = set()
            for line in index_body.splitlines():
                identifiers = re.findall(r"\]\((?:\./)?(SOP-\d{3})-", line)
                if "|" not in line or not identifiers:
                    continue
                table_ids.update(identifiers)
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                if (len(cells) != len(columns) or cells[columns.index("状态")] not in STATUSES
                        or not cells[columns.index("修订")]):
                    errors.append("SOP index: each mapped inventory row needs valid status and nonempty revision")
            if mapped_ids - table_ids:
                errors.append("SOP index: every SOP mapping must appear in the inventory table")
    for route in SOP_ROUTES:
        if not any(route in line and (line.startswith(("#", "- ")) or "|" in line) for line in index_body.splitlines()):
            errors.append(f"SOP index: missing common task route {route}")
    for identifier, path in sop_paths.items():
        body = _markdown_content(text(path, identifier))
        if not re.search(r"^# " + re.escape(identifier) + r"(?:\s|$)", body, re.MULTILINE):
            errors.append(f"{identifier}: H1 must start with matching SOP ID")
        headings = list(re.finditer(r"^##[ \t]+(.+?)[ \t]*$", body, re.MULTILINE))
        for section in SOP_SECTIONS:
            matching = [i for i, heading in enumerate(headings) if heading[1] == section]
            if len(matching) != 1:
                errors.append(f"{identifier}: required section '{section}' must occur exactly once")
            else:
                index = matching[0]
                end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
                if not body[headings[index].end():end].strip():
                    errors.append(f"{identifier}: required section '{section}' is empty")
    expected_sop_files = {root / "sop/README.md", *sop_paths.values()}
    unexpected = {path for path in (root / "sop").rglob("*.md")} - expected_sop_files
    if unexpected:
        errors.append("SOP directory: unexpected Markdown files: " + ", ".join(sorted(path.relative_to(root).as_posix() for path in unexpected)))
    agents = reference("AGENTS.md", "agent instructions")
    agent_links = _markdown_targets(text(agents, "agent instructions"))
    if "sop/README.md" not in agent_links and "./sop/README.md" not in agent_links:
        errors.append("AGENTS.md: must link to root sop/README.md as execution entrypoint")

    catalog = document("docs/catalog.json")
    rows = catalog.get("documents")
    if not isinstance(rows, list) or not rows:
        errors.append("docs/catalog.json: nonempty documents list required")
        rows = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    seen_resolved_paths: set[Path] = set()
    paths_to_check: dict[Path, str] = {}
    required_keys = {"doc_id", "path", "type", "status", "applicable_release", "base_release", "inputs", "updated_at", "sop"}
    for row in rows:
        if not isinstance(row, dict):
            errors.append("catalog document: object required")
            continue
        identifier = row.get("doc_id")
        label = identifier if isinstance(identifier, str) else "catalog document"
        missing = required_keys - row.keys()
        if missing:
            errors.append(f"{label}: missing metadata: {', '.join(sorted(missing))}")
        if nonempty(identifier, "doc_id"):
            if not re.fullmatch(r"DOC-[A-Za-z0-9_-]+", identifier):
                errors.append(f"{label}: invalid doc_id")
            if identifier in seen_ids:
                errors.append(f"duplicate doc_id: {identifier}")
            seen_ids.add(identifier)
        counts["documents"] += 1
        path = reference(row.get("path"), f"{label}.path")
        if path is not None:
            # Keep the declared pathname for inventory coverage; resolving it
            # would let an undeclared symlink borrow another document's entry.
            relative = Path(row["path"]).as_posix()
            if relative in seen_paths or path in seen_resolved_paths:
                errors.append(f"duplicate document path: {relative}")
            seen_paths.add(relative)
            seen_resolved_paths.add(path)
            paths_to_check[path] = label
        kind = row.get("type")
        status = row.get("status")
        if not isinstance(kind, str) or kind not in DOCUMENT_TYPES:
            errors.append(f"{label}: invalid document type")
        if not isinstance(status, str) or status not in STATUSES:
            errors.append(f"{label}: invalid document status")
        if status in ("baselined", "superseded"):
            counts[status] += 1
        applicable = row.get("applicable_release")
        if applicable != "all" and _release_parts(applicable) is None:
            errors.append(f"{label}: invalid applicable_release")
        elif applicable != "all":
            release_reference(applicable, f"{label}.applicable_release")
        if status == "draft" and applicable in ("all", release_id):
            errors.append(f"{label}: active document is draft, baseline required")
        if row.get("base_release") is not None and _release_parts(row.get("base_release")) is None:
            errors.append(f"{label}: invalid base_release")
        elif row.get("base_release") is not None:
            release_reference(row["base_release"], f"{label}.base_release")
        updated = row.get("updated_at")
        try:
            if not isinstance(updated, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated):
                raise ValueError
            date.fromisoformat(updated)
        except ValueError:
            errors.append(f"{label}: updated_at must be a valid YYYY-MM-DD date")
        inputs = row.get("inputs")
        if not isinstance(inputs, list) or not inputs:
            errors.append(f"{label}: nonempty inputs list required")
        else:
            for index, source in enumerate(inputs):
                reference(source, f"{label}.inputs[{index}]")
        sop = row.get("sop")
        if nonempty(sop, f"{label}.sop"):
            sop_path = reference(sop, f"{label}.sop")
            if sop_path not in sop_paths.values() or not sop.startswith("sop/SOP-"):
                errors.append(f"{label}.sop: must reference a mapped independent root sop/SOP-XXX file")

    required_paths = {root / name for name in ("AGENTS.md", "readme.md", "CHANGELOG.md")}
    for directory in ("docs", "tests", "releases", "sop"):
        required_paths.update((root / directory).rglob("*.md"))
    for path in sorted(required_paths):
        relative = path.relative_to(root).as_posix()
        resolved = reference(relative, f"documentation inventory: {relative}")
        if resolved is not None and relative not in seen_paths:
            errors.append(f"unregistered Markdown document: {relative}")

    for path, label in paths_to_check.items():
        if path.suffix.lower() != ".md":
            continue
        for target in _markdown_targets(text(path, label)):
            if target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            try:
                url = urlsplit(target)
                if url.scheme or url.netloc:
                    errors.append(f"{label}: unsupported local link: {target}")
                    continue
                local = unquote(url.path)
                if local:
                    counts["links"] += 1
                    reference(local, f"{label}.link", base=path.parent, allow_directory=True)
            except ValueError as exc:
                errors.append(f"{label}.link: {exc}")
    return errors, counts


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    errors, counts = validate_docs(root)
    print(json.dumps({"state": "FAIL" if errors else "PASS", "scope": "documentation_baseline_only",
                      "release_eligible": False, "counts": counts, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
