#!/usr/bin/env python3
"""Owned, repeatable TM-002 directory and account oracles.

The product under test never supplies expected values. This module creates only
synthetic roots below a caller-owned, new 0700 directory. It does not use a
real Codex/Claude directory, Keychain, App profile, or production database.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import time
from typing import Any


CASE_ID = re.compile(r"TC-TM002-[A-Z]+-\d{2}(?:#[A-Z0-9_]+)?\Z")
OWNER = "tokenmeter-tm002-fixture-v1"
FIXED_MTIME = 1790812800  # 2026-10-01T00:00:00Z
ALICE_ID = "00000000-0000-4000-8000-000000000002"
BOB_ID = "00000000-0000-4000-8000-000000000003"
ACCOUNT_QUERY = ("SELECT id, username, role, is_active FROM users WHERE id IN "
                 "('00000000-0000-4000-8000-000000000002',"
                 "'00000000-0000-4000-8000-000000000003') ORDER BY id")
ACCOUNT_EXPECTED = [
    {"id": ALICE_ID, "username": "test-alice", "role": "member", "is_active": 1},
    {"id": BOB_ID, "username": "test-bob", "role": "member", "is_active": 1},
]
A1 = "sessions/2026/10/01/a-01.jsonl"
A2 = "sessions/2026/10/01/a-02.jsonl"
AN = "sessions/2026/10/01/a-new.jsonl"
B1 = "sessions/2026/10/01/b-01.jsonl"
BN = "sessions/2026/10/01/b-new.jsonl"
C1 = "projects/sample/claude-01.jsonl"
CB = "projects/sample/claude-b-01.jsonl"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _write_new(path: Path, data: bytes, *, fixed_mtime: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("xb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
    if fixed_mtime:
        os.utime(path, (FIXED_MTIME, FIXED_MTIME))


def _record(relative: str, data: bytes) -> dict:
    return {"relative_name": relative, "bytes": len(data), "mtime_utc": "2026-10-01T00:00:00Z",
            "sha256": _sha(data)}


def _parents_no_symlinks(path: Path) -> None:
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError("Fixture path has a symlink component")


def _owned_root(path: Path, owner_id: str, inode: int, device: int) -> None:
    _parents_no_symlinks(path)
    details = path.stat(follow_symlinks=False)
    if (not stat.S_ISDIR(details.st_mode) or details.st_uid != os.getuid()
            or details.st_ino != inode or details.st_dev != device):
        raise ValueError("Fixture root identity changed")
    marker = path / ".owner.json"
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_uid != os.getuid():
        raise ValueError("Fixture owner marker is missing or linked")
    value = json.loads(marker.read_text(encoding="utf-8"))
    if value != {"owner": OWNER, "owner_id": owner_id, "root_inode": inode, "root_device": device}:
        raise ValueError("Fixture owner marker differs")


@dataclass(frozen=True)
class Fixture:
    root: Path
    a: Path
    b: Path
    owner_id: str
    inode: int
    device: int
    expected: dict
    manifest_path: Path

    def verify_owner(self) -> None:
        _owned_root(self.root, self.owner_id, self.inode, self.device)

    def append_new(self) -> dict:
        """Add AN/BN only to this case's roots, then record the mutation."""
        self.verify_owner()
        if self.expected["tool"] != "codex":
            raise ValueError("AN/BN belong to the Codex fixture")
        values = {"A": (self.a / AN, b'{"private":"PRIVATE_A_NEW"}\n'),
                  "B": (self.b / BN, b'{"private":"PRIVATE_B_NEW"}\n')}
        for path, data in values.values():
            _write_new(path, data, fixed_mtime=True)
        record = {label: _record(AN if label == "A" else BN, data)
                  for label, (_, data) in values.items()}
        self._mutation("append_new", record)
        return record

    def append_a_only(self) -> dict:
        self.verify_owner()
        if self.expected["tool"] != "codex":
            raise ValueError("AN belongs to the Codex fixture")
        data = b'{"private":"PRIVATE_A_NEW"}\n'
        _write_new(self.a / AN, data, fixed_mtime=True)
        record = _record(AN, data)
        self._mutation("append_a_only", record)
        return record

    def deny_a(self) -> None:
        """POSIX denial applies only to the owned A root."""
        self.verify_owner()
        if self.a.is_symlink() or not self.a.is_dir() or self.a.stat().st_uid != os.getuid():
            raise ValueError("Owned A root changed")
        os.chmod(self.a, 0)
        self._mutation("deny_a", {"mode": "000"})

    def restore_a(self) -> None:
        self.verify_owner()
        if self.a.is_symlink() or not self.a.is_dir() or self.a.stat().st_uid != os.getuid():
            raise ValueError("Owned A root changed")
        os.chmod(self.a, 0o700)
        self._mutation("restore_a", {"mode": "0700"})

    def replace_a_inode(self) -> dict:
        """Move the original A inside the owned root and create a new A inode."""
        self.verify_owner()
        moved = self.root / "A-original"
        if moved.exists() or moved.is_symlink() or self.a.is_symlink():
            raise ValueError("A replacement target is not fresh")
        old = self.a.stat(follow_symlinks=False)
        os.rename(self.a, moved)
        self.a.mkdir(mode=0o700)
        _write_new(self.a / AN, b'{"private":"PRIVATE_A_NEW"}\n', fixed_mtime=True)
        new = self.a.stat(follow_symlinks=False)
        if (old.st_dev, old.st_ino) == (new.st_dev, new.st_ino):
            raise ValueError("Replacement did not change the directory identity")
        result = {"old_inode": old.st_ino, "new_inode": new.st_ino, "same_device": old.st_dev == new.st_dev}
        self._mutation("replace_a_inode", result)
        return result

    def _mutation(self, action: str, details: dict) -> None:
        path = self.root / "mutations.jsonl"
        with path.open("ab") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write((json.dumps({"action": action, "details": details,
                                      "at": datetime.now(timezone.utc).isoformat()},
                                     sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))

    def cleanup(self) -> None:
        """Delete only the unchanged, marked root. Never follow fixture links."""
        self.verify_owner()
        # Finish ownership validation before changing permissions or removing any entry.
        # A foreign directory must not be passed to rmtree merely because its parent
        # has this run's marker.
        def refuse_walk_error(error: OSError) -> None:
            raise error

        for current, directories, files in os.walk(self.root, topdown=True, followlinks=False,
                                                   onerror=refuse_walk_error):
            for name in directories + files:
                entry = Path(current) / name
                if entry.lstat().st_uid != os.getuid():
                    raise ValueError("Fixture contains an entry owned by another user")
            for name in directories:
                entry = Path(current) / name
                if not entry.is_symlink():
                    os.chmod(entry, 0o700)
        shutil.rmtree(self.root)
        if self.root.exists() or self.root.is_symlink():
            raise ValueError("Fixture cleanup did not remove its root")


def prepare(case_id: str, owner_root: Path, owner_id: str) -> Fixture:
    """Create one fresh A/B dataset and an independent expected manifest.

    ``owner_root`` is a new directory under an already isolated test run. The
    returned A/B absolute paths are private driver inputs and are never put in
    the review manifest or result workbook.
    """
    if not CASE_ID.fullmatch(case_id) or not re.fullmatch(r"[a-z0-9-]{8,64}", owner_id):
        raise ValueError("Invalid fixed case ID or owner identifier")
    # macOS commonly spells /private/var as /var. Resolve that system alias
    # before validating components, while refusing a linked fixture leaf.
    if owner_root.is_symlink():
        raise ValueError("Fixture root is a symlink")
    root = owner_root.resolve(strict=False)
    _parents_no_symlinks(root)
    if root.exists() or root.is_symlink():
        raise ValueError("Fixture root already exists")
    if not root.parent.is_dir() or root.parent.stat().st_uid != os.getuid():
        raise ValueError("Fixture parent is not owned by this user")
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    details = root.stat(follow_symlinks=False)
    marker = {"owner": OWNER, "owner_id": owner_id, "root_inode": details.st_ino, "root_device": details.st_dev}
    _write_new(root / ".owner.json", _json_bytes(marker))
    a, b = root / "A", root / "B"
    a.mkdir(mode=0o700)
    b.mkdir(mode=0o700)
    files: list[dict] = []
    symlinks: list[dict] = []
    variant = case_id.split("#", 1)[1] if "#" in case_id else ""
    tool = "claude_code" if case_id == "TC-TM002-SELECT-04" else "codex"

    def put(label: str, relative: str, data: bytes) -> None:
        _write_new((a if label == "A" else b) / relative, data, fixed_mtime=True)
        files.append({"root": label, **_record(relative, data)})

    if tool == "claude_code":
        put("A", C1, b'{"private":"PRIVATE_CLAUDE_1"}\n')
        put("A", "projects/sample/readme.txt", b"README\n")
        put("B", CB, b'{"private":"PRIVATE_CLAUDE_B"}\n')
    elif case_id == "TC-TM002-PREVIEW-02":
        put("A", "sessions/2026/10/01/ignore.txt", b"not-a-jsonl\n")
        put("B", B1, b'{"private":"PRIVATE_B1"}\n')
    elif case_id.startswith("TC-TM002-PREVIEW-04#"):
        if variant == "CANDIDATES_1001":
            for index in range(1001):
                put("A", f"c-{index:04d}.jsonl", b"{}\n")
        elif variant == "ENTRIES_5001":
            for index in range(5001):
                put("A", f"n-{index:04d}.txt", b"n\n")
        elif variant == "DEPTH_9":
            put("A", "d1/d2/d3/d4/d5/d6/d7/at8.jsonl", b"{}\n")
            put("A", "d1/d2/d3/d4/d5/d6/d7/d8/at9.jsonl", b"{}\n")
        else:
            raise ValueError("Unknown fixed PREVIEW-04 variant")
        put("B", B1, b'{"private":"PRIVATE_B1"}\n')
    else:
        put("A", A1, b'{"private":"PRIVATE_A1"}\n')
        put("A", A2, b'{"private":"PRIVATE_A2"}\n')
        put("A", "sessions/2026/10/01/ignore.txt", b"not-a-jsonl\n")
        put("B", B1, b'{"private":"PRIVATE_B1"}\n')
        link_file = a / "sessions/2026/10/01/link-out.jsonl"
        link_dir = a / "sessions/2026/10/01/escape"
        link_file.symlink_to(b / B1)
        link_dir.symlink_to(b / "sessions/2026/10/01", target_is_directory=True)
        symlinks.extend([{"root": "A", "relative_name": "sessions/2026/10/01/link-out.jsonl", "kind": "file"},
                         {"root": "A", "relative_name": "sessions/2026/10/01/escape", "kind": "directory"}])

    a_candidates = sorted((item for item in files if item["root"] == "A" and item["relative_name"].endswith(".jsonl")),
                          key=lambda item: item["relative_name"].encode("utf-8"))
    expected = {"schema_version": 1, "case_id": case_id, "tool": tool,
                "preview": {"candidates": a_candidates, "complete": variant not in
                            ("CANDIDATES_1001", "ENTRIES_5001", "DEPTH_9"),
                            "incomplete_reason": {"CANDIDATES_1001": "candidate_limit",
                                                  "ENTRIES_5001": "entry_limit", "DEPTH_9": "depth_limit"}.get(variant)},
                "files": sorted(files, key=lambda item: (item["root"], item["relative_name"].encode("utf-8"))),
                "symlinks": symlinks,
                "sql_expected": {"query": ACCOUNT_QUERY, "rows": ACCOUNT_EXPECTED},
                "privacy": {"body_reads_allowed": 0, "unselected_root_reads_allowed": 0}}
    if variant == "CANDIDATES_1001":
        expected["preview"]["candidates"] = a_candidates[:1000]
    elif variant == "DEPTH_9":
        expected["preview"]["candidates"] = [item for item in a_candidates if item["relative_name"].endswith("at8.jsonl")]
    manifest_path = root / "expected.json"
    _write_new(manifest_path, _json_bytes(expected))
    fixture = Fixture(root, a, b, owner_id, details.st_ino, details.st_dev, expected, manifest_path)
    fixture.verify_owner()
    return fixture


def verify_accounts(database: Path) -> dict:
    """Read-only check against the fixed independent SQL oracle."""
    if database.is_symlink() or not database.is_file():
        raise ValueError("Owned synthetic database is absent or linked")
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
        rows = [dict(zip(("id", "username", "role", "is_active"), row))
                for row in connection.execute(ACCOUNT_QUERY)]
        sessions = connection.execute("SELECT count(*) FROM sessions").fetchone()[0]
        audit = connection.execute("SELECT count(*) FROM audit").fetchone()[0]
    if rows != ACCOUNT_EXPECTED:
        raise ValueError("Synthetic Alice/Bob rows differ from fixed SQL oracle")
    return {"query_sha256": _sha(ACCOUNT_QUERY.encode()), "rows": rows,
            "session_count": sessions, "audit_count": audit}


def volume_preprobe(fixture: Fixture) -> dict:
    """Independent timing and depth/count check for PREVIEW-04 fixtures."""
    fixture.verify_owner()
    started = time.monotonic()
    entries = 0
    candidates = 0
    maximum_depth = 0
    for current, directories, files in os.walk(fixture.a, followlinks=False):
        relative = Path(current).relative_to(fixture.a)
        directory_depth = len(relative.parts) if relative != Path(".") else 0
        maximum_depth = max(maximum_depth, directory_depth)
        entries += len(directories) + len(files)
        candidates += sum(name.endswith(".jsonl") for name in files)
    elapsed_ms = (time.monotonic() - started) * 1000
    result = {"entries": entries, "candidates": candidates, "max_directory_depth": maximum_depth,
              "elapsed_ms": round(elapsed_ms, 3), "under_2_seconds": elapsed_ms < 2000}
    variant = fixture.expected["case_id"].split("#", 1)[-1]
    required = {"CANDIDATES_1001": (1001, 1001), "ENTRIES_5001": (5001, 0),
                "DEPTH_9": (10, 2)}.get(variant)
    if required and (entries, candidates) != required:
        raise ValueError("Volume fixture count differs from fixed input")
    return result


def redacted_expected(fixture: Fixture, nonce: bytes) -> dict:
    """Persistent evidence contains no original relative name or host path."""
    fixture.verify_owner()
    if len(nonce) < 32:
        raise ValueError("Audit nonce is too short")
    digest_name = lambda value: hmac.new(nonce, value.encode("utf-8"), hashlib.sha256).hexdigest()
    return {"schema_version": 1, "case_id": fixture.expected["case_id"],
            "tool": fixture.expected["tool"],
            "private_oracle_sha256": _sha(fixture.manifest_path.read_bytes()),
            "preview": {"count": len(fixture.expected["preview"]["candidates"]),
                        "complete": fixture.expected["preview"]["complete"],
                        "incomplete_reason": fixture.expected["preview"]["incomplete_reason"],
                        "relative_name_hmac_sha256": [digest_name(item["relative_name"])
                                                       for item in fixture.expected["preview"]["candidates"]]},
            "roots": {label: {"file_count": sum(item["root"] == label for item in fixture.expected["files"]),
                              "file_hashes": [item["sha256"] for item in fixture.expected["files"]
                                              if item["root"] == label]}
                      for label in ("A", "B")},
            "sql_query_sha256": _sha(ACCOUNT_QUERY.encode("utf-8"))}


def load(owner_root: Path, owner_id: str) -> Fixture:
    """Reopen only the exact owner-marked fixture for a fixed mutation."""
    if owner_root.is_symlink():
        raise ValueError("Fixture root is linked")
    root = owner_root.resolve(strict=True)
    marker_path = root / ".owner.json"
    if marker_path.is_symlink() or not marker_path.is_file():
        raise ValueError("Fixture marker is missing or linked")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("owner") != OWNER or marker.get("owner_id") != owner_id:
        raise ValueError("Fixture owner mismatch")
    expected_path = root / "expected.json"
    if expected_path.is_symlink() or not expected_path.is_file():
        raise ValueError("Fixture oracle is missing or linked")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    fixture = Fixture(root, root / "A", root / "B", owner_id,
                      marker["root_inode"], marker["root_device"], expected, expected_path)
    fixture.verify_owner()
    return fixture


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("append-new", "append-a", "deny-a", "restore-a", "replace-a-inode"))
    parser.add_argument("--owner-root", type=Path, required=True)
    parser.add_argument("--owner-id", required=True)
    args = parser.parse_args(argv)
    fixture = load(args.owner_root, args.owner_id)
    if args.action == "append-new":
        fixture.append_new()
    elif args.action == "append-a":
        fixture.append_a_only()
    elif args.action == "deny-a":
        fixture.deny_a()
    elif args.action == "restore-a":
        fixture.restore_a()
    else:
        fixture.replace_a_inode()
    print(json.dumps({"action": args.action, "case_id": fixture.expected["case_id"], "owner_verified": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
