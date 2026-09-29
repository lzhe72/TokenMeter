"""Shared, read-only contract for a release manifest and its referenced snapshot."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import PurePosixPath
import re
from typing import Callable

RELEASE_DOCS = {
    "requirements": "01-requirements.md", "breakdown": "02-breakdown.md",
    "development_plan": "03-development-plan.md", "test_plan": "04-test-plan.md",
    "release_plan": "05-release-plan.md", "iteration_record": "06-iteration-record.md",
}
RELEASE = re.compile(r"v(\d+\.\d+\.\d+)-(\d{8}T\d{6}Z)\Z")


def visible_text(body: str) -> str:
    """Ignore examples/comments; inline-code IDs remain valid document identifiers."""
    lines, fence = [], None
    for line in body.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker[1]
            elif marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return re.sub(r"<!--.*?(?:-->|$)", "", "\n".join(lines), flags=re.DOTALL)


def validate_release(manifest: dict, release_id: str, read_text: Callable[[str], str], *,
                     mode: str = "baseline", catalog: dict | None = None) -> list[str]:
    """Validate one snapshot. Structure mode permits unfinished fields, never bad references."""
    if mode not in {"structure", "baseline"}:
        raise ValueError("Unknown release validation mode")
    complete = mode == "baseline"
    errors: list[str] = []

    def read(value: object, label: str) -> str:
        try:
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError("nonempty repository file path required")
            path = PurePosixPath(value)
            if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
                raise ValueError("path must remain inside repository and use its canonical relative name")
            body = read_text(value)
            if not isinstance(body, str) or not body.strip():
                raise ValueError("referenced file is absent or empty")
            return body
        except (OSError, ValueError, UnicodeError, RuntimeError) as exc:
            errors.append(f"{label}: {exc}: {value}")
            return ""

    match = RELEASE.fullmatch(release_id) if isinstance(release_id, str) else None
    try:
        if match is None:
            raise ValueError
        created = datetime.strptime(match[2], "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return ["release manifest: invalid release_id or timestamp"]
    if not isinstance(manifest, dict):
        return ["release manifest: object required"]
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        errors.append("release manifest: schema_version must be integer 1")
    for key, expected in (("release_id", release_id), ("version", match[1]), ("created_at", created)):
        if manifest.get(key) != expected:
            errors.append(f"release manifest: {key} must match requested release ID")
    documents = manifest.get("documents")
    if not isinstance(documents, dict):
        errors.append("release manifest: documents object required")
        documents = {}
    if set(documents) != set(RELEASE_DOCS):
        errors.append("release.documents: must contain exactly the six ordered lifecycle document keys")
    bodies = {}
    for key, filename in RELEASE_DOCS.items():
        path = documents.get(key)
        expected = f"releases/{release_id}/{filename}"
        if path != expected:
            errors.append(f"release.documents.{key}: expected {filename} at {expected}")
        bodies[key] = visible_text(read(path, f"release.documents.{key}"))
        if release_id not in bodies[key]:
            errors.append(f"release.documents.{key}: body must contain {release_id}")
    # Even unexpected document keys are references, so never ignore an unsafe path.
    for key in documents.keys() - RELEASE_DOCS.keys():
        read(documents[key], f"release.documents.{key}")

    publication = manifest.get("publication")
    if not isinstance(publication, dict) or publication.get("planned_git_tag") != release_id:
        errors.append("release publication: planned_git_tag must match release_id")
    changelog = visible_text(read(manifest.get("changelog"), "release.changelog"))
    if not re.search(r"^## " + re.escape(release_id) + r"[ \t]*$", changelog, re.MULTILINE):
        errors.append(f"CHANGELOG: missing exact heading '## {release_id}'")
    if "changelog_heading" in manifest and manifest["changelog_heading"] != release_id:
        errors.append("release.changelog_heading must match release_id")

    feature_ids = manifest.get("feature_ids")
    if (not isinstance(feature_ids, list) or not feature_ids
            or not all(isinstance(item, str) and re.fullmatch(r"TM-\d{3}", item) for item in feature_ids)
            or len(set(feature_ids)) != len(feature_ids)):
        errors.append("release.feature_ids: nonempty unique TM-NNN list required")
        feature_ids = []
    patterns = {"requirement": r"REQ-[A-Z0-9]+(?:-[A-Z0-9]+)*", "feature": r"TM-\d{3}",
                "task": r"TASK-[A-Z0-9]+(?:-[A-Z0-9]+)*", "test": r"(?:GOV|E2E|TEST|TC)-[A-Z0-9]+(?:-[A-Z0-9]+)*"}
    sources = {"requirement": "requirements", "feature": "breakdown", "task": "breakdown", "test": "test_plan"}
    declared = {key: set(re.findall(r"(?<![A-Za-z0-9_-])" + pattern + r"(?![A-Za-z0-9_-])", bodies[sources[key]]))
                for key, pattern in patterns.items()}
    traced = {key: set() for key in patterns}
    trace = manifest.get("traceability")
    if trace is None and not complete:
        trace = []
    if not isinstance(trace, list) or (complete and not trace):
        errors.append("release.traceability: nonempty list required for baseline; use an empty list while drafting")
        trace = []
    for index, row in enumerate(trace):
        if not isinstance(row, dict):
            errors.append(f"release.traceability[{index}]: object required")
            continue
        for key, pattern in patterns.items():
            value = row.get(key)
            label = f"release.traceability[{index}].{key}"
            if value is None and not complete:
                continue
            if not isinstance(value, str) or not re.fullmatch(pattern, value):
                errors.append(f"{label}: valid {key} ID required")
                continue
            traced[key].add(value)
            if value not in declared[key]:
                errors.append(f"{label}: {value} missing from {sources[key]} document")
            if key == "feature" and value not in feature_ids:
                errors.append(f"{label}: {value} is not in feature_ids")
    if complete:
        for key in patterns:
            missing = (set(feature_ids) if key == "feature" else declared[key]) - traced[key]
            if missing:
                errors.append(f"release.traceability: missing {key} coverage: {', '.join(sorted(missing))}")

    bindings_status = manifest.get("program_bindings_status", "ready")
    if not isinstance(bindings_status, str) or bindings_status not in {"planned", "ready"}:
        errors.append("release.program_bindings_status: must be planned or ready")
    require_programs = complete and bindings_status != "planned"
    programs = manifest.get("test_programs")
    if programs is None and not complete:
        programs = []
    if not isinstance(programs, list) or (require_programs and not programs):
        errors.append("release.test_programs: program list required; ready bindings need a nonempty list")
        programs = []
    for index, program in enumerate(programs):
        read(program, f"release.test_programs[{index}]")
    for key in ("test_data_program", "test_sop"):
        value = manifest.get(key)
        if value is None and (not complete or (key == "test_data_program" and not require_programs)):
            continue
        body = read(value, f"release.{key}")
        if key == "test_sop":
            match_sop = re.fullmatch(r"sop/(SOP-\d{3})-[a-z0-9]+(?:-[a-z0-9]+)*\.md", value) if isinstance(value, str) else None
            if not match_sop:
                errors.append("release.test_sop: independent root sop/SOP-XXX-slug.md required")
            else:
                index = visible_text(read("sop/README.md", "release.test_sop.index"))
                filename = PurePosixPath(value).name
                if not re.search(r"\]\((?:\./)?" + re.escape(filename) + r"\)", index):
                    errors.append("release.test_sop: file must be mapped in the SOP index")
                if not re.search(r"^# " + re.escape(match_sop[1]) + r"(?:\s|$)", visible_text(body), re.MULTILINE):
                    errors.append("release.test_sop: H1 must start with the matching SOP ID")

    if catalog is None:
        try:
            catalog = json.loads(read("docs/catalog.json", "release.document_catalog"))
        except ValueError:
            catalog = {}
    if (not isinstance(catalog, dict) or type(catalog.get("schema_version")) is not int
            or catalog.get("schema_version") != 1 or not isinstance(catalog.get("documents"), list)):
        errors.append("release.document_catalog: schema_version 1 documents list required")
        return errors
    rows = catalog["documents"]
    for key, filename in RELEASE_DOCS.items():
        path = f"releases/{release_id}/{filename}"
        matches = [row for row in rows if isinstance(row, dict) and row.get("path") == path]
        if len(matches) != 1:
            errors.append(f"release.document_catalog: exactly one entry required for {path}")
        elif complete and matches[0].get("status") != "baselined":
            errors.append(f"release.document_catalog: {path} must be baselined")
    prefix = f"releases/{release_id}/"
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("path"), str) and row["path"].startswith(prefix):
            if row.get("applicable_release") != release_id:
                errors.append(f"release.document_catalog: {row['path']} applicable_release must equal {release_id}")
    return errors
