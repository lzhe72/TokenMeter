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
CASE_ID = re.compile(r"(?:TC-TM[0-9]{3}-[A-Z]+-[0-9]{2}|E2E-TM[0-9]{3}-[0-9]{3})\Z")
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
    if not isinstance(release, str) or not re.fullmatch(r"v\d+\.\d+\.\d+-\d{8}T\d{6}Z", release):
        return ["Catalog release_id is missing or invalid"]
    breakdown = root / "releases" / release / "02-breakdown.md"
    if not breakdown.is_file():
        return ["Release task breakdown does not exist"]
    task_ids = set(re.findall(r"TASK-[A-Z0-9-]+", breakdown.read_text(encoding="utf-8")))
    seen: set[str] = set()
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
        if not isinstance(row["task_ids"], list) or any(not isinstance(v, str) for v in row["task_ids"]):
            errors.append(prefix + "task_ids must be a string array")
        else:
            if not aggregate and not row["task_ids"]:
                errors.append(prefix + "a detailed case requires a concrete TASK")
            for task in row["task_ids"]:
                if task not in task_ids:
                    errors.append(prefix + "unregistered TASK " + task)
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
        source = row["source"]
        if not isinstance(source, dict) or not isinstance(source.get("path"), str):
            errors.append(prefix + "source must identify its document path")
            continue
        relative = Path(source["path"])
        candidate = root / relative
        if relative.is_absolute() or ".." in relative.parts or not candidate.is_file() or not candidate.resolve().is_relative_to(root.resolve()):
            errors.append(prefix + "source is not a repository file")
            continue
        matches = [n for n, line in enumerate(candidate.read_text(encoding="utf-8").splitlines(), 1)
                   if re.match(r"^#{2,3} " + re.escape(str(cid)) + r"(?:\s|$)", line)]
        if len(matches) != 1 or source.get("line") != matches[0]:
            errors.append(prefix + "source heading/line is absent, duplicated or stale")
    return errors


def cell(value: object) -> str:
    """Escape Markdown table metacharacters without turning inputs into markup."""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "&#124;").replace("\r", "").replace("\n", "<br>")


def format_steps(row: dict, key: str) -> str:
    return "<br>".join(f"{step['step']}. {cell(step[key])}" for step in row["steps"])


def render_markdown(data: dict) -> str:
    rows = data["cases"]
    statuses = Counter(row["design_status"] for row in rows)
    future = sum(row.get("aggregate_planned", False) for row in rows)
    sections = ["# TokenMeter 全部测试用例\n",
                "由 `tests/test_cases.json` 生成；逐项修改数据源后运行 `python3 scripts/export_test_cases.py`。一致性检查：`python3 scripts/export_test_cases.py --check`。\n",
                "主要查看入口：[TokenMeter项目总表.xlsx](TokenMeter项目总表.xlsx)。本页提供 Git 可审查索引，详细前置、SQL、逐步观察面和缺项见机器清单及各来源文档。\n",
                f"当前共 **{len(rows)} 条设计记录、{sum(len(row['steps']) for row in rows)} 个步骤**；其中{future}条是未来功能聚合计划，进入开发前还需具体任务与逐步细化。\n",
                "设计状态：" + "、".join(f"{key} {value}" for key, value in sorted(statuses.items())) + "。执行状态与设计状态分别列出；未执行不代表通过，本索引不授予发布资格。\n",
                "本页保存用例设计，不回填运行结果；每批次实际PASS/FAIL/BLOCKED见独立测试结果Excel。新增TC不能继承旧聚合场景的结果。\n",
                "测试由仓库中的固定代码执行，AI只调用程序。产品单例入口为`python3 scripts/run_test_case.py --case-id TC-ID --package-manifest <实际包清单>`，完整回归使用`--all`；开发包另加`--development`。参数变体可按`TC-ID#变体`独立重跑，操作、预期、数据和原始证据均按run保存。\n"]
    for feature in sorted({row["feature_id"] for row in rows}):
        subset = [row for row in rows if row["feature_id"] == feature]
        sections.extend([f"\n## {feature} · {len(subset)} 条\n",
                         "| 功能 / 需求 | 用例及详情 | 开发任务 | 类型 | 输入 | 操作步骤 | 独立预期 | DB 准备、变更与核验 | 设计 / 执行状态 |\n",
                         "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"])
        for row in subset:
            source = row["source"]
            detail = f"[{row['id']}]({source['path']}) · {cell(row['title'])}"
            db = row["db_operations"]
            checks = db.get("verification") or "；".join(check["id"] for check in db.get("read_only_checks", []))
            db_text = f"准备：{db['prepare']}\n变更：{db['expected_changes']}\n核验：{checks}"
            status = row["design_status"] + " / " + row["execution_status"]
            if row["missing"]:
                status += "\n缺项：" + "；".join(row["missing"])
            values = [cell(row["feature_id"] + " / " + row["requirement_id"]), detail,
                      cell("、".join(row["task_ids"]) or "待拆解"), cell(row["type"]), cell(row["input"]),
                      format_steps(row, "action"), format_steps(row, "expected"), cell(db_text), cell(status)]
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
