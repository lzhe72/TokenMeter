#!/usr/bin/env python3
"""Create reproducible, synthetic fixture files; never connect to an application DB.

These are normalized test specifications, NOT verified Codex/Claude raw logs.
They do not implement account provisioning, source parsing, or product E2E.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys


FIXED_CLOCK = "2026-09-29T04:00:00Z"
TIMEZONE = "Asia/Shanghai"
MARKER = ".tokenmeter-fixture.json"
OWNED_FILES = (MARKER, "users.json", "usage.jsonl", "prices.json", "expected.json", "manifest.json")
RUN_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")


class FixtureError(ValueError):
    """Unsafe or invalid fixture operation."""


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _marker(run_id: str) -> dict:
    return {"schema_version": 1, "owner": "tokenmeter-test-fixtures", "run_id": run_id,
            "owned_files": list(OWNED_FILES)}


def _check_path(path: Path) -> None:
    # Check all ancestors without resolving away symlinks first.
    for item in reversed((path, *path.parents)):
        if item.is_symlink():
            raise FixtureError(f"Refusing symlink: {item}")
        if item.exists() and not item.is_dir():
            raise FixtureError(f"Expected a directory: {item}")


def _target(run_id: str, workspace: Path | None) -> Path:
    if not RUN_ID.fullmatch(run_id):
        raise FixtureError("run-id must match [a-z0-9][a-z0-9_-]{0,63}")
    base = Path(os.path.abspath(workspace if workspace is not None else Path.cwd()))
    target = base / ".local" / "test-runs" / run_id
    _check_path(target)
    return target


def _event(event_id: str, timestamp: str, user: str, device: str, source: str,
           model: str, input_tokens: int, cached: int, output: int, reasoning: int,
           case: str) -> dict:
    return {"event_id": event_id, "occurred_at": timestamp, "user_id": user,
            "device_id": device, "source": source, "model": model,
            "project_id": "test-project-a" if user == "test-alice" else "test-project-b",
            "input_tokens": input_tokens, "cached_input_tokens": cached,
            "output_tokens": output, "reasoning_output_tokens": reasoning,
            "case": case}


def _events(seed: int) -> list[dict]:
    events = [
        _event("today-gpt", "2026-09-28T16:00:00Z", "test-alice", "alice-mac-1", "codex",
               "gpt-5", 1000, 200, 100, 20, "today_start"),
        _event("today-sonnet", "2026-09-29T01:00:00Z", "test-alice", "alice-mac-2", "claude-code",
               "sonnet-test", 2000, 500, 200, 0, "second_device"),
        _event("today-qwen", "2026-09-29T02:00:00Z", "test-bob", "bob-mac-1", "codex",
               "qwen-test", 3000, 1000, 300, 50, "cached_and_reasoning_subsets"),
        _event("today-glm", "2026-09-29T03:00:00Z", "test-bob", "bob-mac-1", "claude-code",
               "glm-test", 4000, 0, 400, 100, "glm_model"),
        _event("today-unknown", "2026-09-29T03:30:00Z", "test-bob", "bob-mac-1", "codex",
               "unknown-model", 5000, 0, 500, 0, "missing_price"),
        _event("yesterday", "2026-09-28T15:59:59Z", "test-alice", "alice-mac-1", "codex",
               "gpt-5", 100, 20, 10, 2, "yesterday_end"),
        _event("day7", "2026-09-22T16:00:00Z", "test-alice", "alice-mac-1", "codex",
               "gpt-5", 700, 140, 70, 14, "day7_start"),
        _event("day15", "2026-09-14T16:00:00Z", "test-bob", "bob-mac-1", "codex",
               "qwen-test", 1500, 500, 150, 25, "day15_start"),
        _event("day30", "2026-08-30T16:00:00Z", "test-alice", "alice-mac-2", "claude-code",
               "sonnet-test", 3000, 750, 300, 0, "day30_start"),
        _event("outside30", "2026-08-30T15:59:59Z", "test-bob", "bob-mac-1", "claude-code",
               "glm-test", 10000, 0, 1000, 250, "outside_day30"),
        _event("custom-start", "2026-09-19T16:00:00Z", "test-bob", "bob-mac-1", "codex",
               "qwen-test", 2000, 1000, 200, 40, "custom_start_included"),
        _event("custom-end", "2026-09-21T16:00:00Z", "test-bob", "bob-mac-1", "claude-code",
               "glm-test", 6000, 0, 600, 150, "custom_end_excluded"),
    ]
    events.append(dict(events[0]))  # Exact replay; must not increase any total.
    random.Random(seed).shuffle(events)
    return events


def _totals(events: int, inputs: int, cached: int, outputs: int, reasoning: int,
            total: int, cost: str, missing: int) -> dict:
    # Values below are an explicit test oracle, not calculated by the generator.
    return {"unique_events": events, "input_tokens": inputs, "cached_input_tokens": cached,
            "output_tokens": outputs, "reasoning_output_tokens": reasoning,
            "total_tokens": total, "known_estimated_cost_usd": cost,
            "unpriced_events": missing, "cost_complete": missing == 0}


def _expected() -> dict:
    return {
        "schema_version": 1, "fixture_kind": "normalized-test-spec",
        "fixed_clock": FIXED_CLOCK, "timezone": TIMEZONE,
        "raw_event_count": 13, "unique_event_count": 12, "duplicate_event_id": "today-gpt",
        "token_rule": "total=input+output; cached is a subset of input; reasoning is a subset of output",
        "cost_rule": "(input-cached)*input_price + cached*cached_price + output*output_price, divided by 1000000; unpriced events are excluded from known cost",
        "range_rule": "Local dates, start inclusive and end exclusive; trailing N days include today",
        "periods": {
            "today": {"start": "2026-09-29", "end_exclusive": "2026-09-30",
                      "totals": _totals(5, 15000, 1700, 1500, 170, 16500, "0.015190", 1)},
            "yesterday": {"start": "2026-09-28", "end_exclusive": "2026-09-29",
                          "totals": _totals(1, 100, 20, 10, 2, 110, "0.000244", 0)},
            "last7": {"start": "2026-09-23", "end_exclusive": "2026-09-30",
                      "totals": _totals(7, 15800, 1860, 1580, 186, 17380, "0.017142", 1)},
            "last15": {"start": "2026-09-15", "end_exclusive": "2026-09-30",
                       "totals": _totals(10, 25300, 3360, 2530, 401, 27830, "0.023592", 1)},
            "last30": {"start": "2026-08-31", "end_exclusive": "2026-09-30",
                       "totals": _totals(11, 28300, 4110, 2830, 401, 31130, "0.035067", 1)},
            "custom": {"start": "2026-09-20", "end_exclusive": "2026-09-22",
                       "totals": _totals(1, 2000, 1000, 200, 40, 2200, "0.001500", 0)},
        },
        "all_time": _totals(12, 38300, 4110, 3830, 651, 42130, "0.041067", 1),
        "today_by_member": {
            "test-alice": _totals(2, 3000, 700, 300, 20, 3300, "0.010090", 0),
            "test-bob": _totals(3, 12000, 1000, 1200, 150, 13200, "0.005100", 1),
        },
    }


def _payloads(run_id: str, seed: int) -> dict[str, bytes]:
    users = {"schema_version": 1, "test_only": True,
             "warning": "SYNTHETIC TEST CREDENTIALS. Import only into an isolated disposable test database; this tool creates no application accounts.",
             "users": [{"id": f"test-{name}", "username": f"test-{name}",
                        "password": f"TEST-ONLY-{name}-{seed}!",
                        "role": "admin" if name == "admin" else "member",
                        "enabled": name != "disabled"}
                       for name in ("admin", "alice", "bob", "disabled")]}
    prices = {"schema_version": 1, "test_only": True, "currency": "USD",
              "warning": "Synthetic nonbillable fixture prices, NOT current vendor pricing.",
              "unit": "per_million_tokens", "effective_at": "2026-01-01T00:00:00Z",
              "models": {
                  "gpt-5": {"input": "2", "cached_input": "0.2", "output": "8"},
                  "sonnet-test": {"input": "3", "cached_input": "0.3", "output": "15"},
                  "qwen-test": {"input": "1", "cached_input": "0.1", "output": "2"},
                  "glm-test": {"input": "0.5", "cached_input": "0.05", "output": "1"}}}
    payloads = {MARKER: _json_bytes(_marker(run_id)), "users.json": _json_bytes(users),
                "usage.jsonl": ("".join(json.dumps(e, sort_keys=True) + "\n" for e in _events(seed))).encode(),
                "prices.json": _json_bytes(prices), "expected.json": _json_bytes(_expected())}
    manifest = {"schema_version": 1, "run_id": run_id, "seed": seed,
                "fixed_clock": FIXED_CLOCK, "timezone": TIMEZONE,
                "fixture_kind": "normalized-test-spec",
                "warning": "Synthetic normalized fixtures, NOT verified Codex/Claude raw log schemas or product E2E evidence.",
                "datasets": {"identity": ["users.json"],
                             "usage_normalized": ["usage.jsonl", "expected.json"],
                             "pricing": ["prices.json", "expected.json"],
                             "date_ranges": ["usage.jsonl", "expected.json"],
                             "duplicates": ["usage.jsonl", "expected.json"]},
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}}
    payloads["manifest.json"] = _json_bytes(manifest)
    return payloads


def generate(run_id: str, seed: int = 42, *, workspace: Path | None = None) -> Path:
    """Generate under a workspace; workspace injection is for isolated unit tests."""
    target = _target(run_id, workspace)
    if target.exists():
        raise FixtureError(f"Run already exists; no files changed: {target}")
    payloads = _payloads(run_id, seed)
    target.parent.mkdir(parents=True, exist_ok=True)
    _check_path(target.parent)
    target.mkdir()  # Never reuse or overwrite an existing run.
    for name, data in payloads.items():
        with (target / name).open("xb") as output:
            output.write(data)
    return target


def reset(run_id: str, *, workspace: Path | None = None) -> Path:
    """Delete exactly the generated flat file set after a complete safety check."""
    target = _target(run_id, workspace)
    if not target.is_dir():
        raise FixtureError(f"Run does not exist: {target}")
    children = list(target.iterdir())
    if {item.name for item in children} != set(OWNED_FILES):
        raise FixtureError("Refusing reset: missing generated files or unknown/foreign files")
    for item in children:
        if item.is_symlink() or not item.is_file():
            raise FixtureError(f"Refusing reset: symlink or non-file: {item}")
    try:
        marker = json.loads((target / MARKER).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FixtureError("Refusing reset: unreadable ownership marker") from error
    if marker != _marker(run_id):
        raise FixtureError("Refusing reset: invalid ownership marker")
    # No recursive removal: delete only the exact validated owned filenames.
    for name in OWNED_FILES[1:]:
        (target / name).unlink()
    (target / MARKER).unlink()
    target.rmdir()
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("generate", help="Write synthetic normalized test fixtures")
    create.add_argument("--run-id", required=True)
    create.add_argument("--seed", type=int, default=42)
    remove = subparsers.add_parser("reset", help="Remove only a validated owned fixture run")
    remove.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            target = generate(args.run_id, args.seed)
            print(f"Generated synthetic fixture specification: {target}")
            print("This is fixture preparation only, not application provisioning or product E2E.")
        else:
            target = reset(args.run_id)
            print(f"Removed owned fixture run: {target}")
    except (FixtureError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
