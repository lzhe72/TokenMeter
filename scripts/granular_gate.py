#!/usr/bin/env python3
"""Read-only TM-001 detailed-case contract verifier; never issues a passport.

This checks set identity, documented bindings, step records and local artifact
hashes. It is a rule component, not the full installed-App release gate.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

try:
    from . import granular_test_result as results
except ImportError:
    import granular_test_result as results


ROOT = Path(__file__).resolve().parents[1]
GIT_SHA = re.compile(r"(?:[a-f0-9]{40}|[a-f0-9]{64})\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
RELEASE = re.compile(r"v(\d+)\.(\d+)\.(\d+)-(\d{8}T\d{6}Z)\Z")


def timestamp(value: object) -> datetime | None:
    return results.timestamp(value)


def combine_variants(login: dict, update: dict | None, release_id: str) -> dict:
    """Combine TM-001 source manifests for a possibly newer candidate release."""
    if not isinstance(login, dict) or (update is not None and not isinstance(update, dict)):
        raise results.Invalid("Variant manifests must be objects")
    documents = [login, *([update] if update is not None else [])]
    combined = []
    source_release = login.get("release_id")
    source_match = RELEASE.fullmatch(source_release) if isinstance(source_release, str) else None
    target_match = RELEASE.fullmatch(release_id) if isinstance(release_id, str) else None
    if source_match is None or target_match is None:
        raise results.Invalid("Variant manifest or candidate release ID is invalid")
    if source_release != release_id:
        source_version = tuple(map(int, source_match.groups()[:3]))
        target_version = tuple(map(int, target_match.groups()[:3]))
        if source_version >= target_version or source_match.group(4) >= target_match.group(4):
            raise results.Invalid("Variant source release is not earlier than the candidate")
    for document in documents:
        if document.get("release_id") != source_release or not isinstance(document.get("variants"), list):
            raise results.Invalid("Variant manifests have mixed source releases or invalid shape")
        combined.extend(document["variants"])
    identities = [item.get("id") for item in combined if isinstance(item, dict)]
    if len(identities) != len(combined) or len(set(identities)) != len(identities):
        raise results.Invalid("Variant manifest has foreign or repeated IDs")
    return {"release_id": source_release, "variants": combined}


def test_plan_ready(plan: dict, release_id: str, document_catalog: dict | None, *, fixture: bool) -> bool:
    if plan.get("execution_bindings_status") != "ready":
        return False
    if fixture:
        return plan.get("test_plan_status") == "baselined"
    expected = f"releases/{release_id}/04-test-plan.md"
    documents = plan.get("documents")
    entries = document_catalog.get("documents") if isinstance(document_catalog, dict) else None
    matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("path") == expected] if isinstance(entries, list) else []
    return (plan.get("release_id") == release_id and
            isinstance(documents, dict) and documents.get("test_plan") == expected and
            len(matches) == 1 and matches[0].get("status") == "baselined" and
            (ROOT / expected).is_file())


def registered_source(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        return False
    source = ROOT / value
    return source.is_file() and not source.is_symlink() and source.resolve().is_relative_to(ROOT.resolve())


def verify_candidate(catalog: dict, report: dict, *, run_root: Path, plan: dict,
                     variants: dict, auxiliary: dict | None = None,
                     auxiliary_root: Path | None = None, audit: dict | None = None,
                     audit_root: Path | None = None, document_catalog: dict | None = None,
                     fixture: bool = False) -> dict:
    """Return component result without modifying inputs or granting release eligibility."""
    reasons = []
    release = catalog.get("release_id")
    current = [case for case in catalog.get("cases", []) if isinstance(case, dict) and case.get("feature_id") == "TM-001"]
    source_releases = [case.get("release_id", release) for case in current]
    if (not source_releases or any(not isinstance(value, str) or not value for value in source_releases)
            or len(set(source_releases)) != 1 or variants.get("release_id") != source_releases[0]):
        reasons.append("TM-001 变体来源版本与父用例不一致")
    identities = [case.get("id") for case in current]
    variant_ids = [item.get("id") for item in variants.get("variants", []) if isinstance(item, dict)]
    required = identities + variant_ids
    if len(current) != 78 or len(variant_ids) != 38 or len(set(required)) != len(required):
        reasons.append("冻结 TM-001 用例或变体集合缺失、重复")
    if not test_plan_ready(plan, release, document_catalog, fixture=fixture):
        reasons.append("测试计划或执行绑定未完成")
    for case in current:
        if case.get("design_status") not in ("designed", "baselined"):
            reasons.append(f"{case.get('id')} 基线未完成")
        binding = case.get("binding")
        if not isinstance(binding, dict) or not binding:
            reasons.append(f"{case.get('id')} 缺独立执行绑定")
        elif not fixture and (binding.get("tc_identity") != case.get("id") or
                              binding.get("status") not in ("implemented_pending_execution", "ready") or
                              not registered_source(binding.get("program")) or
                              not registered_source(binding.get("runner")) or
                              binding.get("selector") != ["--case-id", case.get("id")]):
            reasons.append(f"{case.get('id')} 独立执行绑定无效或程序缺失")
    expected = report.get("expected_cases")
    if (not isinstance(expected, list) or any(not isinstance(value, str) for value in expected)
            or len(expected) != len(required) or set(expected) != set(required)):
        reasons.append("本次必测 TC/变体集合不精确")
    observed = report.get("tc_results")
    if not isinstance(observed, list):
        reasons.append("本次没有逐 TC 结果数组")
    else:
        observed_ids = [item.get("case_id") if isinstance(item, dict) else None for item in observed]
        if len(observed_ids) != len(required) or len(set(observed_ids)) != len(required) or set(observed_ids) != set(required):
            reasons.append("逐 TC 结果有漏例、重例或外来编号")
    if report.get("release_id") != release:
        reasons.append("运行版本与用例目录不一致")
    if not fixture and report.get("scope") != "granular_final_package":
        reasons.append("产品报告不是最终安装包范围")
    if fixture and report.get("scope") != "governance_fixture":
        reasons.append("治理 fixture 没有隔离范围标记")
    for label, value, pattern in (("候选提交", report.get("source_commit"), GIT_SHA),
                                  ("候选树", report.get("candidate_tree"), GIT_SHA),
                                  ("DMG", (report.get("package") or {}).get("dmg_sha256"), SHA256)):
        if not isinstance(value, str) or not pattern.fullmatch(value):
            reasons.append(f"{label} 摘要缺失或格式错误")
    started, finished = timestamp(report.get("started_at")), timestamp(report.get("finished_at"))
    if started is None or finished is None or not started <= finished <= datetime.now(timezone.utc):
        reasons.append("主运行时间无效")
    if report.get("cleanup_completed") is not True:
        reasons.append("主运行清理未完成")
    if not fixture:
        if report.get("state") != "BLOCKED":
            reasons.append("主批次原始状态与独立辅助占位不一致")
        if auxiliary is None:
            reasons.append("缺少本次独立辅助批次原件")
        if audit is None:
            reasons.append("缺少本次独立审计原件")
        aux_ids = {identity for identity in identities if identity.startswith(results.AUX_PREFIXES)}
        if isinstance(observed, list):
            for item in observed:
                if not isinstance(item, dict):
                    continue
                identity = item.get("case_id")
                if identity in aux_ids:
                    if (item.get("state") != "BLOCKED" or item.get("step_results") != [] or
                            item.get("evidence") != {} or item.get("started_at") is not None or
                            item.get("finished_at") is not None or
                            not isinstance(item.get("reason"), str) or
                            "No independently registered" not in item["reason"]):
                        reasons.append(f"{identity} 主批次不是未执行的辅助占位")
                elif item.get("state") != "PASS":
                    reasons.append(f"{identity} 主批次原始结果未通过")
    if auxiliary is not None:
        aux_ids = {identity for identity in identities if identity.startswith(results.AUX_PREFIXES)}
        bound, reason = results.auxiliary_binding(report, auxiliary, aux_ids)
        if not bound:
            reasons.append(reason)
        aux_results = auxiliary.get("tc_results")
        if (not isinstance(aux_results, list) or len(aux_results) != len(aux_ids)
                or {item.get("case_id") for item in aux_results if isinstance(item, dict)} != aux_ids):
            reasons.append("辅助批次 11 条逐例结果不精确")
        if auxiliary.get("cleanup_completed") is not True:
            reasons.append("辅助批次清理未完成")
        if not fixture and auxiliary.get("state") != "PASS":
            reasons.append("辅助批次原始结果未通过")
    if audit is not None and not fixture:
        try:
            from . import audit_granular_evidence as audit_rules
        except ImportError:
            import audit_granular_evidence as audit_rules
        source = run_root / "result.json"
        if (audit.get("state") != "PASS" or audit.get("audited_cases") != list(audit_rules.AUDITED_CASES) or
                not source.is_file() or audit.get("source_report_sha256") != hashlib.sha256(source.read_bytes()).hexdigest()):
            reasons.append("独立审计不是本批次完整 PASS 原件")
    try:
        model = results.build_model(catalog, report, run_root=run_root, variants=variants,
                                    auxiliary_report=auxiliary, auxiliary_root=auxiliary_root,
                                    audit_report=audit, audit_root=audit_root)
    except (results.Invalid, KeyError, TypeError, ValueError) as error:
        reasons.append(f"逐步原件无法核对：{error}")
        model = None
    if model is not None:
        incomplete = [case["id"] for case in model["cases"] if case["state"] != "PASS"]
        incomplete.extend(item["id"] for item in model["variants"] if item["state"] != "PASS")
        if incomplete:
            reasons.append("逐例证据不完整：" + ", ".join(incomplete[:10]) + ("…" if len(incomplete) > 10 else ""))
        if auxiliary is not None and any(item["state"] != "PASS" for item in model["auxiliary"]):
            reasons.append("辅助批次有未通过的独立 TC")
        if audit is not None and not fixture and (len(model["audit"]) != 12 or
                any(item["state"] != "PASS" for item in model["audit"])):
            reasons.append("独立审计有缺例或非 PASS 结论")
    return {"schema_version": 1, "scope": "granular_candidate_rule_component",
            "state": "PASS" if not reasons else "FAIL", "release_eligible": False,
            "run_id": report.get("run_id", ""), "release_id": release,
            "expected_cases": len(required), "verified_cases": len(model["cases"]) if model else 0,
            "verified_variants": len(model["variants"]) if model else 0, "reasons": reasons}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--aux-report", type=Path)
    parser.add_argument("--audit-report", type=Path)
    parser.add_argument("--catalog", type=Path, default=ROOT / "tests/test_cases.json")
    parser.add_argument("--login-variants", type=Path, default=ROOT / "tests/granular_login_variants.json")
    parser.add_argument("--update-variants", type=Path)
    parser.add_argument("--plan", type=Path, default=ROOT / "releases" /
                        json.loads((ROOT / "releases/current.json").read_text(encoding="utf-8"))["release_id"] /
                        "00-manifest.json")
    parser.add_argument("--governance-fixture", action="store_true")
    args = parser.parse_args(argv)
    try:
        report, _ = results.read_json(args.report)
        catalog, _ = results.read_json(args.catalog)
        login, _ = results.read_json(args.login_variants)
        update_path = args.update_variants or ROOT / "tests/granular_update_variants.json"
        update, _ = results.read_json(update_path) if update_path.is_file() else (None, None)
        plan, _ = results.read_json(args.plan)
        auxiliary, _ = results.read_json(args.aux_report) if args.aux_report else (None, None)
        audit, _ = results.read_json(args.audit_report) if args.audit_report else (None, None)
        document_catalog, _ = results.read_json(ROOT / "docs/catalog.json") if not args.governance_fixture else (None, None)
        combined = combine_variants(login, update, catalog.get("release_id"))
        outcome = verify_candidate(catalog, report, run_root=args.report.parent, plan=plan, variants=combined,
                                   auxiliary=auxiliary, auxiliary_root=args.aux_report.parent if args.aux_report else None,
                                   audit=audit, audit_root=args.audit_report.parent if args.audit_report else None,
                                   document_catalog=document_catalog,
                                   fixture=args.governance_fixture)
        print(json.dumps(outcome, ensure_ascii=False))
        return 0 if outcome["state"] == "PASS" else 1
    except (OSError, ValueError, TypeError, KeyError, results.Invalid) as error:
        print(json.dumps({"scope": "granular_candidate_rule_component", "state": "FAIL",
                          "release_eligible": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
