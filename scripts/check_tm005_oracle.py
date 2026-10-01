#!/usr/bin/env python3
"""Verify the independent TM-005 design oracle against normalized fixture events.

This checks fixed arithmetic and calendar rules. It never opens product logs, a
database, or the desktop app, and a PASS is not an E2E result.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timezone
import importlib.util
import json
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ORACLE = ROOT / "tests/fixtures/tm005-semantic-expected.json"


def normalized_events() -> list[dict]:
    spec = importlib.util.spec_from_file_location("tm005_fixture_source", ROOT / "scripts/test_data.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._events(42)


def utc_instant(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def bounds(start: str, end: str, zone: ZoneInfo) -> tuple[datetime, datetime]:
    first = datetime.combine(date.fromisoformat(start), time.min, zone).astimezone(timezone.utc)
    last = datetime.combine(date.fromisoformat(end), time.min, zone).astimezone(timezone.utc)
    return first, last


def token_total(event: dict) -> int:
    return event["input_tokens"] + event["output_tokens"]


def validate(oracle: dict) -> list[str]:
    errors: list[str] = []

    def expect(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    expect(oracle["status"] == "design_only" and oracle["raw_log_compatibility_verified"] is False,
           "oracle must remain design_only with unverified raw compatibility")
    events = normalized_events()
    unique = {(event["source"], event["event_id"]): event for event in events}
    expect(len(events) == 13 and len(unique) == 12, "normalized fixture must contain 13 rows/12 calls")
    calls = list(unique.values())
    source_name = {"codex": "codex", "claude-code": "claude_code"}
    shanghai = ZoneInfo("Asia/Shanghai")

    for section, zone in (("periods_shanghai", shanghai), ("utc_checks", ZoneInfo("UTC"))):
        for period, expected in oracle[section].items():
            first, last = bounds(expected["start"], expected["end_exclusive"], zone)
            selected = [event for event in calls if first <= utc_instant(event["occurred_at"]) < last]
            actual_ids = [event["event_id"] for event in selected]
            if "event_ids" in expected:
                expect(set(actual_ids) == set(expected["event_ids"]) and
                       len(actual_ids) == len(expected["event_ids"]),
                       f"{section}.{period}: selected event IDs differ")
            expect(sum(map(token_total, selected)) == expected["total_tokens"],
                   f"{section}.{period}: total tokens differ")
            for field in ("input_tokens", "output_tokens", "cached_input_tokens",
                          "reasoning_output_tokens"):
                if field in expected:
                    expect(sum(event[field] for event in selected) == expected[field],
                           f"{section}.{period}: {field} differs")
            if section == "periods_shanghai" and period in ("today", "last30"):
                actual_sources = {name: sum(token_total(event) for event in selected
                                            if source_name[event["source"]] == name)
                                  for name in ("codex", "claude_code")}
                source_expected = oracle["period_source_totals_design"][period]
                expect(actual_sources == {name: source_expected[name] for name in actual_sources} and
                       sum(actual_sources.values()) == source_expected["total_tokens"],
                       f"{period}: source totals differ")

    today = oracle["periods_shanghai"]["today"]
    today_start, today_end = bounds(today["start"], today["end_exclusive"], shanghai)
    today_calls = [event for event in calls if today_start <= utc_instant(event["occurred_at"]) < today_end]
    by_model = {model: {"event_ids": [event["event_id"] for event in today_calls if event["model"] == model],
                        "total_tokens": sum(token_total(event) for event in today_calls if event["model"] == model)}
                for model in oracle["today_models_shanghai"]}
    expect(by_model == oracle["today_models_shanghai"], "today model totals differ")
    expect(today["cache_write_input_tokens"] is None and
           today["cache_write_status"] == "unknown_in_normalized_fixture",
           "missing cache-write values must stay unknown")

    model_design = oracle["unknown_model_design"]
    grouped: dict[str, int] = {}
    for call in model_design["calls"]:
        label = call["model_id"] if call["model_id"] is not None else "unknown_model"
        grouped[label] = grouped.get(label, 0) + token_total(call)
    expect(grouped == model_design["expected_model_totals"] and
           sum(grouped.values()) == model_design["expected_total_tokens"] and
           len(model_design["calls"]) == model_design["expected_unique_calls"],
           "unknown model must retain its trusted usage")

    for state in oracle["state_algebra_design"]:
        known = sum(state["trusted_totals"])
        complete = (state["codex_coverage"] == "complete" and
                    state["claude_coverage"] == "complete")
        if not complete and not state["trusted_totals"]:
            status = "missing"
        elif not complete or state["unknown_events"] and state["trusted_totals"]:
            status = "partial"
        elif state["unknown_events"]:
            status = "unknown"
        else:
            status = "complete"
        total = known if status == "complete" else None
        expect(status == state["expected_status"] and total == state["expected_total_tokens"],
               f"state {state['id']}: coverage/unknown result differs")
        if "expected_known_tokens" in state:
            expect(known == state["expected_known_tokens"], f"state {state['id']}: known sum differs")

    design = oracle["dst_boundary_design"]
    zone = ZoneInfo(design["timezone"])
    for variant in design["variants"]:
        local_day = date.fromisoformat(variant["local_day"])
        next_day = date.fromordinal(local_day.toordinal() + 1)
        first, last = bounds(local_day.isoformat(), next_day.isoformat(), zone)
        expect(first == utc_instant(variant["start_utc"]) and
               last == utc_instant(variant["end_exclusive_utc"]) and
               (last - first).total_seconds() == variant["hours"] * 3600,
               f"{variant['id']}: IANA day boundaries differ")
        selected = [event for event in variant["events"]
                    if first <= utc_instant(event["occurred_at_utc"]) < last]
        expect([event["id"] for event in selected] ==
               [event["id"] for event in variant["events"] if event["included"]],
               f"{variant['id']}: boundary inclusion differs")
        expect(sum(map(token_total, selected)) == variant["expected_total_tokens"] and
               len(selected) == variant["expected_unique_calls"],
               f"{variant['id']}: call count/total differs")

    native = oracle["codex_native_usage_design"]
    expect(native["source"] == "codex" and
           native["total_tokens"] == native["input_tokens"] + native["output_tokens"] and
           0 <= native["cached_input_tokens"] <= native["input_tokens"] and
           0 <= native["cache_write_input_tokens"] <= native["input_tokens"] and
           0 <= native["reasoning_output_tokens"] <= native["output_tokens"],
           "Codex response total or subset counters differ")
    codex_fork = oracle["codex_fork_cumulative_design"]
    codex_calls = codex_fork["parent_calls"] + [codex_fork["fork_file_new_call"]]
    codex_expected = codex_fork["expected_when_source_identity_is_verified"]
    expect(len({call["id"] for call in codex_calls}) == codex_expected["unique_calls"] and
           sum(map(token_total, codex_calls)) == codex_expected["total_tokens"] ==
           codex_fork["fork_file_new_call"]["thread_token_usage_total"] and
           token_total(codex_fork["fork_file_new_call"]) == codex_expected["new_tokens_from_fork"],
           "Codex fork must count incremental responses once")

    claude_fork = oracle["fork_history_design"]
    fork_calls = [claude_fork["parent_call"], claude_fork["fork_new_call"]]
    fork_expected = claude_fork["expected_when_lineage_is_verified"]
    expect(len({call["id"] for call in fork_calls}) == fork_expected["unique_calls"] and
           sum(map(token_total, fork_calls)) == fork_expected["total_tokens"],
           "Claude fork copied history must not be added twice")
    subagent = oracle["subagent_usage_design"]
    agent_calls = [subagent["parent_call"], subagent["subagent_call"]]
    agent_expected = subagent["expected_when_identity_is_verified"]
    expect(len({call["id"] for call in agent_calls}) == agent_expected["unique_calls"] and
           sum(map(token_total, agent_calls)) == agent_expected["total_tokens"],
           "Claude parent and subagent trusted calls must both count")
    repeated = oracle["claude_same_message_multiple_lines_design"]
    repeated_expected = repeated["expected_when_call_identity_is_verified"]
    expect(repeated_expected["unique_calls"] == 1 and
           token_total(repeated["design_call"]) == repeated_expected["total_tokens"],
           "Claude repeated message lines must represent one call")

    collision = oracle["cross_source_id_collision_design"]
    collision_expected = collision["expected_when_source_identity_is_verified"]
    source_totals = {"codex": token_total(collision["codex_call"]),
                     "claude_code": token_total(collision["claude_call"])}
    expect(collision_expected["unique_calls"] == 2 and
           collision["claude_same_source_replay_count"] == 1 and
           collision_expected["per_source_totals"] == source_totals and
           collision_expected["total_tokens"] == sum(source_totals.values()),
           "identical native IDs from two sources must remain distinct")
    unverified = oracle["claude_unverified_inheritance_design"]
    expect(token_total(unverified["first_trusted"]) == unverified["expected_known_tokens"] and
           unverified["expected_total_tokens"] is None and
           unverified["expected_coverage"] == "incomplete" and
           unverified["expected_diagnostic"] == "unverified_inheritance_only" and
           unverified["second_cross_agent_same_id"]["copy_relation"] == "unproven",
           "unverified Claude inheritance must retain uncertainty")
    conflict = oracle["claude_identity_conflict_design"]
    first = conflict["first_trusted"]
    variants = {item["id"]: item for item in conflict["variants"]}
    usage = variants["usage_conflict"]
    model = variants["model_conflict"]
    expect(token_total(first) == conflict["expected_known_tokens"] and
           conflict["expected_diagnostic"] == "identity_conflict" and
           conflict["preserve"] == "first_trusted_event" and
           (usage["second_input_tokens"], usage["second_output_tokens"]) !=
           (first["input_tokens"], first["output_tokens"]) and
           usage["second_model"] == first["model"] and
           (model["second_input_tokens"], model["second_output_tokens"]) ==
           (first["input_tokens"], first["output_tokens"]) and
           model["second_model"] != first["model"],
           "Claude usage/model conflict variants must isolate each conflict")

    paged = oracle["claude_paged_coverage_design"]
    first_tokens = token_total(paged["first_page_trusted_call"])
    both_tokens = first_tokens + token_total(paged["later_page_trusted_call"])
    expect(paged["candidate_files_at_least"] > paged["preview_limit_files"] and
           paged["scan_pages_at_least"] >= 5 and
           paged["expected_before_completion"] ==
           {"known_tokens": first_tokens, "coverage": "incomplete"} and
           paged["expected_after_verified_full_scan"] ==
           {"known_tokens": both_tokens, "coverage": "according_to_verified_interval"} and
           paged["expected_after_between_page_revocation"] ==
           {"known_tokens": first_tokens, "coverage": "incomplete", "do_not_read_later_page": True},
           "Claude pagination/revocation coverage expectation differs")
    zero = oracle["claude_zero_ambiguity_design"]
    expect(zero["observed_raw_usage"] == {"input_tokens": 0, "output_tokens": 0} and
           zero["without_additional_proof"] == "unknown_not_confirmed_zero",
           "Claude raw zero without proof must stay unknown")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle", type=Path, default=DEFAULT_ORACLE)
    args = parser.parse_args()
    try:
        errors = validate(json.loads(args.oracle.read_text(encoding="utf-8")))
    except (KeyError, TypeError, ValueError, OSError) as error:
        errors = [f"invalid oracle: {error}"]
    print(json.dumps({"state": "PASS" if not errors else "FAIL",
                      "scope": "tm005_independent_normalized_design_oracle_only",
                      "product_tests_executed": 0, "release_eligible": False,
                      "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
