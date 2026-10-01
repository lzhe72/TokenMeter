#!/usr/bin/env python3
"""Validate the design catalog and generate its Markdown index; no product runs.

The canonical input is tests/test_cases.json. --check is strictly read-only and
fails when either the catalog is invalid or the generated index is stale.
Excel generation is a separate consumer of the same canonical JSON.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
TC_CASE = r"TC-TM[0-9]{3}-(?:[A-Z][A-Z0-9]*-)+[0-9]{2}"
CASE_ID = re.compile(rf"(?:{TC_CASE}|E2E-TM[0-9]{{3}}-[0-9]{{3}})\Z")
RELEASE_ID = re.compile(r"v\d+\.\d+\.\d+-\d{8}T\d{6}Z\Z")
DETAIL_CASE_HEADING = re.compile(rf"^#{{2,3}} ({TC_CASE})(?=\s|$)", re.MULTILINE)
DOCUMENT_VARIANT = re.compile(rf"{TC_CASE}#[A-Z][A-Z0-9_]*")
REQUIRED = {"id", "title", "feature_id", "requirement_id", "task_ids", "ac_ids", "type", "input",
            "preconditions", "steps", "db_operations", "design_status", "execution_status", "binding", "source", "missing"}


def validate_catalog(data: object, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("cases"), list):
        return ["Catalog requires schema_version=1 and a cases array"]
    if not data["cases"]:
        return ["Catalog cannot contain zero cases"]
    acceptance = json.loads((root / "tests/acceptance.json").read_text(encoding="utf-8"))["acceptance_criteria"]
    known_ac = {row["id"]: row["feature_id"] for row in acceptance}
    known_features = {row["feature_id"] for row in acceptance}
    release = data.get("release_id")
    if not isinstance(release, str) or not RELEASE_ID.fullmatch(release):
        return ["Catalog release_id is missing or invalid"]

    contracts: dict[str, tuple[set[str], set[str]]] = {}

    def release_contract(release_id: str) -> tuple[set[str], set[str]]:
        """Load the feature owners and TASKs for this row's release once."""
        if release_id in contracts:
            return contracts[release_id]
        release_dir = root / "releases" / release_id
        manifest_path = release_dir / "00-manifest.json"
        if not manifest_path.is_file():
            raise ValueError(f"Release manifest does not exist: {release_id}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ValueError(f"Release manifest is unreadable: {release_id}: {error}") from error
        if not isinstance(manifest, dict) or manifest.get("release_id") != release_id:
            raise ValueError(f"Release manifest ID does not match: {release_id}")
        features = manifest.get("feature_ids")
        if not isinstance(features, list) or not features or any(not isinstance(v, str) or not v for v in features):
            raise ValueError(f"Release manifest has invalid feature_ids: {release_id}")
        breakdown = release_dir / "02-breakdown.md"
        if not breakdown.is_file():
            raise ValueError(f"Release task breakdown does not exist: {release_id}")
        tasks = set(re.findall(r"TASK-[A-Z0-9-]+", breakdown.read_text(encoding="utf-8")))
        contracts[release_id] = (set(features), tasks)
        return contracts[release_id]

    try:
        release_contract(release)
    except ValueError as error:
        return [str(error)]
    seen: set[str] = set()
    seen_variants: set[str] = set()
    catalog_cases: dict[str, set[str]] = {}
    catalog_variants: dict[str, set[str]] = {}
    for index, row in enumerate(data["cases"], 1):
        if not isinstance(row, dict):
            errors.append(f"Row {index} is not an object")
            continue
        cid = row.get("id", f"row {index}")
        prefix = str(cid) + ": "
        if not isinstance(cid, str) or not CASE_ID.fullmatch(cid):
            errors.append(prefix + "invalid stable case ID")
        if isinstance(cid, str):
            if cid in seen:
                errors.append(prefix + "duplicate case ID")
            seen.add(cid)
        absent = REQUIRED - row.keys()
        if absent:
            errors.append(prefix + "missing fields: " + ", ".join(sorted(absent)))
            continue
        for key in ("title", "type", "input", "preconditions"):
            if not isinstance(row[key], str) or not row[key].strip():
                errors.append(prefix + key + " must be nonempty text")
        feature = row["feature_id"]
        if feature not in known_features or row["requirement_id"] != "REQ-" + str(feature).replace("-", ""):
            errors.append(prefix + "feature/requirement mapping is invalid")
        aggregate = row.get("aggregate_planned", False)
        if not isinstance(aggregate, bool):
            errors.append(prefix + "aggregate_planned must be boolean")
        if aggregate and row["design_status"] != "planned":
            errors.append(prefix + "future aggregate must remain planned")
        row_release = row.get("release_id", release)
        release_tasks: set[str] | None = None
        if not isinstance(row_release, str) or not RELEASE_ID.fullmatch(row_release):
            errors.append(prefix + "release_id is invalid")
        else:
            try:
                release_features, release_tasks = release_contract(row_release)
            except ValueError as error:
                errors.append(prefix + str(error))
            else:
                # Old future aggregates predate per-row release IDs. Their TM owner
                # is established when they become detailed cases for a release.
                if (not aggregate or "release_id" in row) and feature not in release_features:
                    errors.append(prefix + f"feature {feature} does not belong to release {row_release} manifest")
        if not isinstance(row["task_ids"], list) or any(not isinstance(v, str) for v in row["task_ids"]):
            errors.append(prefix + "task_ids must be a string array")
        else:
            if not aggregate and not row["task_ids"]:
                errors.append(prefix + "a detailed case requires a concrete TASK")
            for task in row["task_ids"]:
                if release_tasks is not None:
                    if task not in release_tasks:
                        errors.append(prefix + "unregistered TASK " + task + f" in release {row_release}")
                    elif not task.startswith("TASK-" + str(feature).replace("-", "") + "-"):
                        errors.append(prefix + "TASK does not belong to feature " + str(feature) + ": " + task)
        if not isinstance(row["ac_ids"], list) or any(not isinstance(v, str) for v in row["ac_ids"]):
            errors.append(prefix + "ac_ids must be a string array")
        else:
            if not row["ac_ids"] and row["design_status"] != "baseline_pending":
                errors.append(prefix + "AC is required outside an explicit pending decision")
            for ac in row["ac_ids"]:
                if known_ac.get(ac) != feature:
                    errors.append(prefix + "AC does not belong to the feature: " + ac)
        if row["design_status"] not in {"planned", "draft", "designed", "baseline_pending", "baselined"}:
            errors.append(prefix + "invalid design status")
        if row["execution_status"] not in {"unexecuted", "not_run", "PASS", "FAIL", "BLOCKED"}:
            errors.append(prefix + "invalid execution status")
        if not isinstance(row["missing"], list) or any(not isinstance(v, str) or not v.strip() for v in row["missing"]):
            errors.append(prefix + "missing must be an array of concrete text items")
        if row["design_status"] == "baseline_pending" and not row["missing"]:
            errors.append(prefix + "pending design must name its unresolved inputs")
        binding = row["binding"]
        if binding is not None and not isinstance(binding, (str, dict)):
            errors.append(prefix + "binding must be null, a path, or a binding object")
        if row["execution_status"] == "PASS" and (not binding or not row.get("evidence")):
            errors.append(prefix + "PASS cannot exist without execution binding and evidence reference")
        if not isinstance(row["db_operations"], dict):
            errors.append(prefix + "db_operations must preserve preparation, changes and verification")
        else:
            db = row["db_operations"]
            for key in ("prepare", "expected_changes"):
                if not isinstance(db.get(key), str) or not db[key].strip():
                    errors.append(prefix + "DB " + key + " is required")
            if not db.get("verification") and not db.get("read_only_checks"):
                errors.append(prefix + "DB verification or an explicit unavailable explanation is required")
        steps = row["steps"]
        if not isinstance(steps, list) or not steps:
            errors.append(prefix + "ordered steps are required")
        else:
            for number, step in enumerate(steps, 1):
                if not isinstance(step, dict) or step.get("step") != number:
                    errors.append(prefix + f"step sequence is invalid at {number}")
                    continue
                for key in ("action", "expected_ui", "expected_api_db", "expected"):
                    if not isinstance(step.get(key), str):
                        errors.append(prefix + f"step {number} lacks text field {key}")
                if not step.get("action", "").strip() or not any(step.get(k, "").strip() for k in ("expected_ui", "expected_api_db", "expected")):
                    errors.append(prefix + f"step {number} lacks action or independent expected result")
                if row["type"] == "product_e2e" and not aggregate:
                    for key in ("expected_ui", "expected_api_db", "expected_file"):
                        if not isinstance(step.get(key), str) or not step[key].strip():
                            errors.append(prefix + f"product step {number} requires {key}")
        variants = row.get("variants", [])
        if not isinstance(variants, list):
            errors.append(prefix + "variants must be an array")
            variants = []
        for variant in variants:
            if not isinstance(variant, dict):
                errors.append(prefix + "variant must be an object")
                continue
            variant_id = variant.get("id")
            if not isinstance(variant_id, str) or not re.fullmatch(re.escape(str(cid)) + r"#[A-Z][A-Z0-9_]*", variant_id):
                errors.append(prefix + "invalid stable variant ID")
            else:
                if variant_id in seen_variants:
                    errors.append(prefix + "duplicate variant ID " + variant_id)
                seen_variants.add(variant_id)
            for key in ("input", "expected"):
                if not isinstance(variant.get(key), str) or not variant[key].strip():
                    errors.append(prefix + f"variant {key} must be nonempty")
        source = row["source"]
        if not isinstance(source, dict) or not isinstance(source.get("path"), str):
            errors.append(prefix + "source must identify its document path")
            continue
        relative = Path(source["path"])
        candidate = root / relative
        if relative.is_absolute() or ".." in relative.parts or not candidate.is_file() or not candidate.resolve().is_relative_to(root.resolve()):
            errors.append(prefix + "source is not a repository file")
            continue
        lines = candidate.read_text(encoding="utf-8").splitlines()
        matches = [n for n, line in enumerate(lines, 1)
                   if re.match(r"^#{2,3} " + re.escape(str(cid)) + r"(?:\s|$)", line)]
        if len(matches) != 1 or source.get("line") != matches[0]:
            errors.append(prefix + "source heading/line is absent, duplicated or stale")
        if len(matches) == 1:
            actual_heading = re.sub(r"^#{2,3}\s+", "", lines[matches[0] - 1]).strip()
            recorded_heading = source.get("heading")
            # Early 0.1 and planned aggregate rows stored only their stable ID.
            # New release rows must retain the exact heading, even when it is ID-only.
            allowed = {actual_heading} if "release_id" in row else {actual_heading, str(cid)}
            if not isinstance(recorded_heading, str) or recorded_heading not in allowed:
                errors.append(prefix + "source heading text differs from document")
            # Some detailed documents use the stable ID alone as a heading and
            # keep the human title in their case table. Compare title text only
            # when the heading actually supplies it.
            if actual_heading != str(cid):
                document_title = re.sub(r"^[·—-]\s*", "", actual_heading[len(str(cid)):].strip()).strip()
                if row["title"] != document_title:
                    errors.append(prefix + "catalog title differs from document")
        relative_name = relative.as_posix()
        if isinstance(cid, str) and cid.startswith("TC-"):
            catalog_cases.setdefault(relative_name, set()).add(cid)
        for variant in variants:
            if isinstance(variant, dict) and isinstance(variant.get("id"), str):
                catalog_variants.setdefault(relative_name, set()).add(variant["id"])

    # Read every detailed case document, not only those still referenced by rows:
    # deleting a whole TC or its final variant must remain a catalog error.
    documents = root / "docs/testing/cases"
    if documents.is_dir():
        for document in sorted(documents.glob("*.md")):
            relative_name = document.relative_to(root).as_posix()
            content = document.read_text(encoding="utf-8")
            document_cases: set[str] = set()
            document_variants: set[str] = set()
            current_case: str | None = None
            for line in content.splitlines():
                heading = DETAIL_CASE_HEADING.match(line)
                if heading:
                    current_case = heading.group(1)
                    document_cases.add(current_case)
                elif re.match(r"^#{2,3} ", line):
                    current_case = None
                if current_case:
                    document_variants.update(variant for variant in DOCUMENT_VARIANT.findall(line)
                                             if variant.startswith(current_case + "#"))
            for case_id in sorted(document_cases - catalog_cases.get(relative_name, set())):
                errors.append("document case missing from catalog: " + case_id + " (" + relative_name + ")")
            for variant_id in sorted(document_variants - catalog_variants.get(relative_name, set())):
                errors.append("document variant missing from catalog: " + variant_id + " (" + relative_name + ")")
            for variant_id in sorted(catalog_variants.get(relative_name, set()) - document_variants):
                errors.append("catalog variant missing from document: " + variant_id + " (" + relative_name + ")")
    return errors


def cell(value: object) -> str:
    """Escape Markdown table metacharacters without turning inputs into markup."""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;").replace("\r", "").replace("\n", "<br>")


def format_steps(row: dict, key: str) -> str:
    return "<br>".join(f"{step['step']}. {cell(step[key])}" for step in row["steps"])


def render_markdown(data: dict) -> str:
    rows = data["cases"]
    variant_count = sum(len(row.get("variants", [])) for row in rows)
    statuses = Counter(row["design_status"] for row in rows)
    future = sum(row.get("aggregate_planned", False) for row in rows)
    sections = ["# TokenMeter 全部测试用例\n",
                "由 `tests/test_cases.json` 生成；逐项修改数据源后运行 `python3 scripts/export_test_cases.py`。一致性检查：`python3 scripts/export_test_cases.py --check`。\n",
                "主要查看入口：[TokenMeter项目总表.xlsx](TokenMeter项目总表.xlsx)。本页提供 Git 可审查索引，详细前置、SQL、逐步观察面和缺项见机器清单及各来源文档。\n",
                f"当前主目录共 **{len(rows)} 条父用例、{variant_count} 条内嵌稳定变体、{sum(len(row['steps']) for row in rows)} 个父用例步骤**；其中{future}条是未来功能聚合计划，进入开发前还需具体任务与逐步细化。父用例与内嵌变体各占一行；独立参数清单另由对应固定门禁核对，不在这里重计。\n",
                "设计状态：" + "、".join(f"{key} {value}" for key, value in sorted(statuses.items())) + "。执行状态与设计状态分别列出；未执行不代表通过，本索引不授予发布资格。\n",
                "本页保存用例设计，不回填运行结果；每批次实际PASS/FAIL/BLOCKED见独立测试结果Excel。新增TC不能继承旧聚合场景的结果。\n",
                "测试由仓库中的固定代码执行，AI只调用程序。产品单例入口为`python3 scripts/run_test_case.py --case-id TC-ID --package-manifest <实际包清单>`，完整回归使用`--all`；开发包另加`--development`。参数变体可按`TC-ID#变体`独立重跑，操作、预期、数据和原始证据均按run保存。\n"]
    for feature in sorted({row["feature_id"] for row in rows}):
        subset = [row for row in rows if row["feature_id"] == feature]
        row_count = sum(1 + len(row.get("variants", [])) for row in subset)
        sections.extend([f"\n## {feature} · {row_count} 行\n",
                         "| 功能 / 需求 | 用例及详情 | 开发任务 | 类型 | 输入 | 操作步骤 | 独立预期 | DB 准备、变更与核验 | 设计 / 执行状态 |\n",
                         "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"])
        for row in subset:
            source = row["source"]
            db = row["db_operations"]
            checks = db.get("verification") or "；".join(check["id"] for check in db.get("read_only_checks", []))
            db_text = f"准备：{db['prepare']}\n变更：{db['expected_changes']}\n核验：{checks}"
            for variant in [None, *row.get("variants", [])]:
                case_id = variant["id"] if variant else row["id"]
                detail = f"[{cell(case_id)}]({source['path']}) · {cell(row['title'])}"
                status = row["design_status"] + " / " + (variant.get("execution_status", row["execution_status"]) if variant else row["execution_status"])
                if row["missing"]:
                    status += "\n缺项：" + "；".join(row["missing"])
                values = [cell(row["feature_id"] + " / " + row["requirement_id"]), detail,
                          cell("、".join(row["task_ids"]) or "待拆解"), cell(row["type"]), cell(variant["input"] if variant else row["input"]),
                          format_steps(row, "action"), cell(variant["expected"]) if variant else format_steps(row, "expected"), cell(db_text), cell(status)]
                sections.append("| " + " | ".join(values) + " |\n")
    return "\n".join(sections).rstrip() + "\n"


def main(argv: list[str] | None = None, *, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=root / "tests/test_cases.json")
    parser.add_argument("--output", type=Path, default=root / "TEST_CASES.md")
    parser.add_argument("--check", action="store_true", help="Validate and compare without writing any files")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        errors = validate_catalog(data, root=root)
        if errors:
            print(json.dumps({"state": "INVALID", "scope": "test_case_design_only", "errors": errors}, ensure_ascii=False, indent=2))
            return 1
        rendered = render_markdown(data)
        if args.check:
            if not args.output.is_file() or args.output.read_text(encoding="utf-8") != rendered:
                print(json.dumps({"state": "STALE", "scope": "test_case_design_only", "error": "Generated index differs; run scripts/export_test_cases.py"}, ensure_ascii=False))
                return 1
        else:
            args.output.write_text(rendered, encoding="utf-8")
        print(json.dumps({"state": "CURRENT" if args.check else "GENERATED", "scope": "test_case_design_only", "cases": len(data["cases"]),
                          "steps": sum(len(row["steps"]) for row in data["cases"]), "product_tests_executed": 0}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"state": "INVALID", "scope": "test_case_design_only", "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
