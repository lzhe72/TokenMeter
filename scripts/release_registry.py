#!/usr/bin/env python3
"""Read a release's traceability index; a lookup never grants release eligibility."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DOCS = {
    "requirements": "01-requirements.md",
    "breakdown": "02-breakdown.md",
    "development_plan": "03-development-plan.md",
    "test_plan": "04-test-plan.md",
    "release_plan": "05-release-plan.md",
    "iteration_record": "06-iteration-record.md",
}
RELEASE = re.compile(r"v(\d+\.\d+\.\d+)-(\d{8}T\d{6}Z)\Z")


def git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def show(root: Path, release_id: str | None = None) -> dict:
    root = root.resolve()

    def read(path: str, tag: str | None = None) -> str:
        if not isinstance(path, str) or not path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
            raise ValueError("Release reference must be relative and confined to repository")
        if tag:
            value = git(root, "show", f"{tag}:{path}")
            if value is None:
                raise ValueError(f"Missing release reference at tag: {path}")
            return value
        candidate = (root / path).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("Release reference must remain inside repository")
        return candidate.read_text(encoding="utf-8")

    def obj(path: str, tag: str | None = None) -> dict:
        value = json.loads(read(path, tag))
        if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
            raise ValueError(f"{path}: expected schema_version 1 object")
        return value

    if release_id is None:
        release_id = obj("releases/current.json").get("release_id")
    match = RELEASE.fullmatch(release_id) if isinstance(release_id, str) else None
    if not match:
        raise ValueError("Invalid release ID; expected vMAJOR.MINOR.PATCH-YYYYMMDDTHHMMSSZ")
    created_at = datetime.strptime(match[2], "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%dT%H:%M:%SZ")
    ref = f"refs/tags/{release_id}"
    tag_commit = git(root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    tag = tag_commit  # Every archived read uses one resolved immutable snapshot.
    manifest_path = f"releases/{release_id}/00-manifest.json"
    manifest = obj(manifest_path, tag)
    if manifest.get("release_id") != release_id or manifest.get("version") != match[1] or manifest.get("created_at") != created_at:
        raise ValueError("Manifest release_id, version or created_at does not match requested ID")
    documents = manifest.get("documents")
    if not isinstance(documents, dict) or not RELEASE_DOCS.keys() <= documents.keys():
        raise ValueError("Incomplete lifecycle documents")
    for key, filename in RELEASE_DOCS.items():
        if documents[key] != f"releases/{release_id}/{filename}":
            raise ValueError(f"Lifecycle document {key} must use ordered filename {filename}")
    for path in documents.values():
        if not isinstance(path, str) or not path.startswith(f"releases/{release_id}/"):
            raise ValueError("Lifecycle documents must belong to this release")
        if release_id not in read(path, tag):
            raise ValueError(f"Lifecycle document missing release ID: {path}")
    changelog_path = manifest.get("changelog")
    changelog = read(changelog_path, tag)
    heading = f"## {release_id}"
    lines = changelog.splitlines()
    if heading not in lines:
        raise ValueError("Changelog missing exact release heading")
    start = lines.index(heading)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    feature_ids = manifest.get("feature_ids")
    if not isinstance(feature_ids, list) or not feature_ids or not all(isinstance(v, str) for v in feature_ids):
        raise ValueError("Manifest needs feature IDs")
    matrix = obj(manifest.get("product_feature_matrix"), tag)
    features = matrix.get("features")
    if not isinstance(features, list) or not all(isinstance(v, dict) for v in features):
        raise ValueError("Invalid feature matrix")
    history = git(root, "log", tag_commit or "--all", "--fixed-strings", f"--grep=[{release_id}]", "--format=%H%x09%s")
    commits = [{"sha": row.split("\t", 1)[0], "subject": row.split("\t", 1)[1]}
               for row in (history or "").splitlines() if "\t" in row]
    publication = manifest.get("publication")
    if not isinstance(publication, dict):
        raise ValueError("Missing publication contract")
    return {
        "schema_version": 1, "release_id": release_id,
        "source": {"kind": "git_tag" if tag else "working_tree", "tag": release_id if tag else None,
                   "commit": tag_commit, "manifest": manifest_path},
        "version": manifest["version"], "feature_ids": feature_ids, "documents": documents,
        "traceability": manifest.get("traceability", []),
        "product_features": [f for f in features if f.get("id") in feature_ids],
        "planned_product_features": [f.get("id") for f in features],
        "test_programs": manifest.get("test_programs", []),
        "test_data_program": manifest.get("test_data_program"), "test_sop": manifest.get("test_sop"),
        "gate_commands": manifest.get("gate_commands", {}),
        "changelog": {"path": changelog_path, "heading": release_id, "entry": "\n".join(lines[start:end]).strip()},
        "commits": commits, "publication": publication,
        "passport": {"expected_asset": publication.get("expected_passport_asset"),
                     "location": "同名 Git Release 的发布资产", "verified": False},
        "release_eligible": None,
        "notice": "查询只展示索引；Git Tag 或规划的通行证名称均不能证明已通过发布门禁。",
    }


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("show",))
    parser.add_argument("--release-id")
    args = parser.parse_args(argv)
    try:
        result = show(root, args.release_id)
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        print(json.dumps({"state": "FAIL", "error": str(exc), "release_eligible": False}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
