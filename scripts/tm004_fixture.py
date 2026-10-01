#!/usr/bin/env python3
"""Build private TM-004 probe fixtures; never read a default Claude directory."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat


REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "tests/fixtures/tm004/native-2.1.126-projection"
RUNS = REPO / ".local/test-runs"
OWNER = ".tm004-owner.json"
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
ROW_FIELDS = (
    "type", "version", "timestamp", "sessionId", "uuid", "parentUuid",
    "isSidechain", "agentId", "attributionAgent", "leafUuid", "forkedFrom",
)
MESSAGE_FIELDS = ("id", "model", "role", "type", "stop_reason", "usage")
TOOL_FIELDS = ("agentId", "totalTokens", "usage")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest() -> dict:
    return json.loads((SOURCE / "provenance-and-expected.json").read_text())


def projection(raw: bytes) -> bytes:
    projected = []
    for line in raw.splitlines():
        original = json.loads(line)
        row = {key: original[key] for key in ROW_FIELDS if key in original}
        if isinstance(original.get("message"), dict):
            message = original["message"]
            row["message"] = {key: message[key] for key in MESSAGE_FIELDS if key in message}
            if isinstance(message.get("content"), list):
                row["message"]["content"] = [
                    {"type": block.get("type")}
                    for block in message["content"] if isinstance(block, dict)
                ]
        if isinstance(original.get("toolUseResult"), dict):
            tool = original["toolUseResult"]
            row["toolUseResult"] = {key: tool[key] for key in TOOL_FIELDS if key in tool}
        projected.append(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return ("\n".join(projected) + "\n").encode()


def check_projection() -> dict:
    data = manifest()
    if data["schema_version"] != 1 or len(data["files"]) != 6:
        raise ValueError("TM-004 projection manifest shape changed")
    for name, expected in data["files"].items():
        if not re.fullmatch(r"raw-[a-z-]+\.jsonl", name):
            raise ValueError("Unexpected fixture name")
        blob = (SOURCE / name).read_bytes()
        if sha(blob) != expected["projection_sha256"]:
            raise ValueError(f"Fixture digest differs: {name}")
        if b"/Users/" in blob or b'"cwd"' in blob or b'"lastPrompt"' in blob:
            raise ValueError(f"Sensitive field remains: {name}")
        rows = [json.loads(line) for line in blob.splitlines()]
        if len(rows) != expected["rows"]:
            raise ValueError(f"Row count differs: {name}")
        for row in rows:
            message = row.get("message", {})
            if any(set(block) != {"type"} for block in message.get("content", [])):
                raise ValueError(f"Content body remains: {name}")
    return data


def check_origin(research_root: Path) -> None:
    data = check_projection()
    if research_root.is_symlink() or not research_root.is_dir():
        raise ValueError("Research root must be an existing ordinary directory")
    for name, expected in data["files"].items():
        path = research_root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Original missing or symlink: {name}")
        raw = path.read_bytes()
        if sha(raw) != expected["original_sha256"]:
            raise ValueError(f"Original digest differs: {name}")
        if projection(raw) != (SOURCE / name).read_bytes():
            raise ValueError(f"Projection differs: {name}")


def synthetic_faults() -> dict[str, bytes]:
    """Derive explicit faults from a projection, never label them native output."""
    rows = (SOURCE / "raw-main.jsonl").read_bytes().splitlines(keepends=True)
    index = next(i for i, line in enumerate(rows) if json.loads(line)["type"] == "assistant")
    prefix, assistant = b"".join(rows[:index]), rows[index]
    partial = prefix + assistant[: len(assistant) // 2]
    if partial.endswith(b"\n"):
        raise ValueError("Partial fault unexpectedly contains a complete line")
    original = json.loads(assistant)
    conflict = json.loads(assistant)
    conflict["uuid"] = "synthetic-conflict-row"
    conflict["message"]["usage"]["input_tokens"] = 14
    missing = json.loads(assistant)
    missing["uuid"] = "synthetic-missing-usage-row"
    missing["message"]["id"] = "msg_tm004_synthetic_missing_usage_001"
    del missing["message"]["usage"]
    if original["message"]["usage"]["input_tokens"] != 13:
        raise ValueError("Source projection no longer matches fixed oracle")
    encode = lambda row: (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return {
        "fault-partial-before.jsonl": partial,
        "fault-partial-after.jsonl": prefix + assistant,
        "fault-conflict.jsonl": encode(conflict),
        "fault-missing-field.jsonl": encode(missing),
    }


def synthetic_planned() -> dict[str, bytes]:
    """Materialize M/S/N/P requirement numbers as synthetic, projected JSONL."""
    def assistants(name: str) -> list[dict]:
        return [json.loads(line) for line in (SOURCE / name).read_bytes().splitlines()
                if json.loads(line).get("type") == "assistant"]

    def set_call(row: dict, uid: str, message_id: str, session: str,
                 input_tokens: int, output_tokens: int) -> dict:
        result = copy.deepcopy(row)
        result["uuid"] = uid
        result["sessionId"] = session
        result["message"]["id"] = message_id
        result["message"]["usage"]["input_tokens"] = input_tokens
        result["message"]["usage"]["output_tokens"] = output_tokens
        result["timestamp"] = "2026-10-01T00:00:00.000Z"
        return result

    main_session = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    fork_session = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    m = set_call(assistants("raw-main.jsonl")[0],
                 "11111111-1111-4111-8111-111111111111", "msg_tm004_plan_m_001",
                 main_session, 100, 10)
    s = set_call(assistants("raw-agent-sub.jsonl")[0],
                 "22222222-2222-4222-8222-222222222222", "msg_tm004_plan_s_001",
                 main_session, 200, 20)
    s["agentId"] = "tm004-synthetic-agent-s"
    s["parentUuid"] = m["uuid"]
    inherited = copy.deepcopy(m)
    inherited["sessionId"] = fork_session
    n = set_call(assistants("raw-fork.jsonl")[-1],
                 "33333333-3333-4333-8333-333333333333", "msg_tm004_plan_n_001",
                 fork_session, 50, 5)
    n["parentUuid"] = inherited["uuid"]
    p = set_call(assistants("raw-fork.jsonl")[-1],
                 "44444444-4444-4444-8444-444444444444", "msg_tm004_plan_p_001",
                 fork_session, 20, 2)
    p["parentUuid"] = n["uuid"]
    s_next = set_call(assistants("raw-agent-sub.jsonl")[0],
                      "55555555-5555-4555-8555-555555555555", "msg_tm004_plan_s_next_001",
                      main_session, 50, 5)
    s_next["agentId"] = s["agentId"]
    s_next["parentUuid"] = s["uuid"]
    encode = lambda row: (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
    before_p = encode(inherited) + encode(n) + encode(p)[: len(encode(p)) // 2]
    return {
        "planned-main.jsonl": encode(m),
        "planned-sub.jsonl": encode(s),
        "planned-fork-before-p.jsonl": before_p,
        "planned-fork-after-p.jsonl": encode(inherited) + encode(n) + encode(p),
        "planned-sub-after-regrant.jsonl": encode(s) + encode(s_next),
    }


def ordinary_owned_directory(path: Path, create: bool) -> None:
    if not path.exists() and create:
        path.mkdir(mode=0o700)
    details = path.lstat()
    if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.getuid():
        raise ValueError(f"Directory is not owned ordinary directory: {path}")


def destination(run_id: str, create_parents: bool = False) -> Path:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid run ID")
    local = REPO / ".local"
    if create_parents:
        ordinary_owned_directory(local, True)
        ordinary_owned_directory(RUNS, True)
    else:
        ordinary_owned_directory(local, False)
        ordinary_owned_directory(RUNS, False)
    return RUNS / f"tm004-{run_id}"


def write_exclusive(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(data)


def generate(run_id: str) -> Path:
    data = check_projection()
    target = destination(run_id, True)
    target.mkdir(mode=0o700)
    contents = {name: (SOURCE / name).read_bytes() for name in data["files"]}
    contents["expected.json"] = (SOURCE / "provenance-and-expected.json").read_bytes()
    contents.update(synthetic_faults())
    contents["planned-expected.json"] = (SOURCE.parent / "planned-expected.json").read_bytes()
    contents.update(synthetic_planned())
    for name, blob in contents.items():
        write_exclusive(target / name, blob)
    owner = {"format": "tm004-probe-v1", "run_id": run_id,
             "files": {name: sha(blob) for name, blob in contents.items()}}
    write_exclusive(target / OWNER, (json.dumps(owner, sort_keys=True) + "\n").encode())
    return target


def verify_owned(run_id: str) -> tuple[Path, dict]:
    target = destination(run_id)
    details = target.lstat()
    if (not stat.S_ISDIR(details.st_mode) or details.st_uid != os.getuid()
            or stat.S_IMODE(details.st_mode) != 0o700):
        raise ValueError("Fixture root ownership/type differs")
    marker = target / OWNER
    marker_details = marker.lstat()
    if (not stat.S_ISREG(marker_details.st_mode)
            or marker_details.st_uid != os.getuid()
            or stat.S_IMODE(marker_details.st_mode) != 0o600):
        raise ValueError("Owner marker missing or redirected")
    owner = json.loads(marker.read_text())
    if owner.get("format") != "tm004-probe-v1" or owner.get("run_id") != run_id:
        raise ValueError("Owner marker differs")
    if {p.name for p in target.iterdir()} != set(owner["files"]) | {OWNER}:
        raise ValueError("Unexpected fixture contents")
    for name, digest in owner["files"].items():
        path = target / name
        details = path.lstat()
        if (not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid()
                or stat.S_IMODE(details.st_mode) != 0o600):
            raise ValueError(f"Fixture file ownership/type differs: {name}")
        if sha(path.read_bytes()) != digest:
            raise ValueError(f"Fixture file digest differs: {name}")
    return target, owner


def reset(run_id: str) -> None:
    target, owner = verify_owned(run_id)
    for name in owner["files"]:
        (target / name).unlink()
    (target / OWNER).unlink()
    target.rmdir()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify-projection")
    origin = sub.add_parser("verify-origin")
    origin.add_argument("--research-root", type=Path, required=True)
    for command in ("generate", "verify-run", "reset"):
        sub.add_parser(command).add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.command == "verify-projection":
        check_projection()
    elif args.command == "verify-origin":
        check_origin(args.research_root)
    elif args.command == "generate":
        print(generate(args.run_id))
    elif args.command == "verify-run":
        print(verify_owned(args.run_id)[0])
    else:
        reset(args.run_id)


if __name__ == "__main__":
    main()
