#!/usr/bin/env python3
"""Validate a pre-tag candidate's identity; this is never a release passport."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def validate_context(root, candidate_sha, event, workflow_ref, default_branch, dispatch_sha):
    errors = []
    if not re.fullmatch(r"[0-9a-f]{40}", candidate_sha):
        errors.append("candidate_sha must be a full lowercase 40-character commit SHA")
    if not re.fullmatch(r"[0-9a-f]{40}", dispatch_sha):
        errors.append("default-branch dispatch SHA must be a full lowercase 40-character commit SHA")
    elif candidate_sha != dispatch_sha:
        errors.append("candidate_sha must equal default-branch dispatch SHA")
    if event != "workflow_dispatch":
        errors.append("candidate validation requires workflow_dispatch before Tag creation")
    if not default_branch or workflow_ref != "refs/heads/" + default_branch:
        errors.append("dispatch must use the repository default branch workflow")
    try:
        def git(*args):
            return subprocess.check_output(["git", "-C", str(root), *args], text=True,
                                           stderr=subprocess.PIPE).strip()
        if git("rev-parse", "HEAD") != candidate_sha:
            errors.append("checked-out HEAD differs from candidate_sha")
        if git("status", "--porcelain", "--untracked-files=all"):
            errors.append("candidate checkout must be clean")
        current = json.loads((Path(root) / "releases/current.json").read_text())
        release_id = current.get("release_id") if isinstance(current, dict) else None
        if not isinstance(release_id, str) or not re.fullmatch(r"v\d+\.\d+\.\d+-\d{8}T\d{6}Z", release_id):
            errors.append("current release_id is invalid")
        elif git("tag", "--list", release_id):
            errors.append("official release Tag already exists; validate candidates before tagging")
    except (OSError, ValueError, RecursionError, subprocess.CalledProcessError) as exc:
        errors.append(f"cannot validate candidate checkout: {exc}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    for name in ("candidate-sha", "event", "workflow-ref", "default-branch", "dispatch-sha"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    errors = validate_context(**vars(args))
    print(json.dumps({"status": "FAIL" if errors else "PASS", "scope": "candidate_context_only",
                      "release_eligible": False, "candidate_sha": args.candidate_sha,
                      "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
