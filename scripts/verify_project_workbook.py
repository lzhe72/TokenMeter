#!/usr/bin/env python3
"""Read the exported project index and compare it with its source records.

This is a document check. It never executes the App or grants release eligibility.
"""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def check() -> dict:
    context = json.loads((ROOT / "docs/project-register.json").read_text())
    catalog = json.loads((ROOT / "tests/test_cases.json").read_text())
    expanded_cases = [(case, variant) for case in catalog["cases"]
                      for variant in [None, *case.get("variants", [])]]
    workbook = ROOT / "TokenMeter项目总表.xlsx"
    errors = []
    with ZipFile(workbook) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ["".join(item.itertext()) for item in
                       ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        relations = {item.attrib["Id"]: item.attrib["Target"] for item in
                     ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))}
        sheets = {}
        for sheet in ET.fromstring(archive.read("xl/workbook.xml")).findall("s:sheets/s:sheet", NS):
            target = relations[sheet.attrib[f"{{{REL}}}id"]]
            target = target.lstrip("/") if target.startswith("/") else "xl/" + target
            cells = {}
            for cell in ET.fromstring(archive.read(target)).findall(".//s:sheetData/s:row/s:c", NS):
                value = cell.findtext("s:v", default="", namespaces=NS)
                if cell.attrib.get("t") == "s":
                    value = strings[int(value)]
                elif cell.attrib.get("t") == "inlineStr":
                    value = "".join(cell.find("s:is", NS).itertext())
                elif cell.attrib.get("t") == "e":
                    errors.append(f"{sheet.attrib['name']}!{cell.attrib['r']}: {value}")
                cells[cell.attrib["r"]] = value
            sheets[sheet.attrib["name"]] = cells

    def equal(actual, expected, label):
        if str(actual) != str(expected):
            errors.append(f"{label}: expected {expected!r}, got {actual!r}")

    equal(len(sheets), 11, "sheet count")
    overview = sheets["00项目总览"]
    equal(overview["B5"], context["metadata"]["release_id"], "current release")
    for address, count in (("B6", len(context["requirements"])),
                           ("B7", len(context["acceptance_criteria"])),
                           ("B8", len(expanded_cases)), ("B9", len(context["test_runs"]))):
        equal(overview[address], count, "summary " + address)
    auxiliary = lambda case: case["id"].startswith(("TC-TM001-UI-", "TC-TM001-CATALOG-", "TC-TM001-RECORDS-", "TC-TM001-GATE-")) or case["type"] in {"source_check", "security_unit", "governance_unit", "delivery_gate", "unit"}
    equal(overview["B10"], sum(not case.get("aggregate_planned", False) and not auxiliary(case) for case, _ in expanded_cases), "product case count")
    equal(overview["B11"], sum(auxiliary(case) for case, _ in expanded_cases), "auxiliary case count")
    equal(overview["B12"], sum(case.get("aggregate_planned", False) for case in catalog["cases"]), "future aggregate count")
    equal(overview["B13"], sum(case["design_status"] == "baseline_pending" for case, _ in expanded_cases), "pending design count")
    current_run = next((run for run in context["test_runs"] if run["run_id"] == context["metadata"].get("observed_run_id") and run["release_id"] == context["metadata"]["release_id"]), None)
    equal(overview["B14"], current_run["state"] if current_run else "未执行", "current release full regression state")
    for row, (case, variant) in enumerate(expanded_cases, start=5):
        cells = sheets["05测试用例"]
        case_id = variant["id"] if variant else case["id"]
        equal(cells[f"B{row}"], case_id, "case ID")
        expected_state = context["latest_case_states"].get(case_id, variant.get("execution_status", case["execution_status"]) if variant else case["execution_status"])
        if expected_state in {"unexecuted", "not_run"}:
            expected_state = "未执行"
        equal(cells[f"J{row}"], expected_state, case_id + " state")
        equal(cells[f"M{row}"], context["latest_case_runs"].get(case_id, "尚未执行"), case_id + " evidence run")
        equal(cells[f"N{row}"], case.get("release_id", catalog["release_id"]), case_id + " release")
    for row, run in enumerate(context["test_runs"], start=5):
        cells = sheets["06测试批次"]
        counts = [run["passed_cases"], run["failed_cases"], run.get("blocked_cases", 0)]
        for column, value in zip("AEFGHIM", [run["run_id"], run["state"], sum(counts), *counts, run["result_workbook"]]):
            equal(cells[f"{column}{row}"], value, run["run_id"] + " " + column)
        equal(cells[f"C{row}"], run["execution_type"], run["run_id"] + " execution type")
        equal(cells[f"N{row}"], run.get("product_e2e_state", "NOT_RUN" if run["execution_type"] == "source_check" else run["state"]), run["run_id"] + " product state")
        if run["execution_type"] == "source_check" and (run.get("release_eligible") or run.get("product_e2e_state", "NOT_RUN") != "NOT_RUN"):
            errors.append(run["run_id"] + ": module result cannot be product PASS or release eligible")
        if not (ROOT / run["result_workbook"]).is_file():
            errors.append(run["run_id"] + ": result workbook missing")
    return {"state": "FAIL" if errors else "PASS", "scope": "project_workbook_readback_only",
            "product_tests_executed": False, "release_eligible": False,
            "sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
            "sheets": len(sheets), "parent_cases": len(catalog["cases"]),
            "variant_cases": len(expanded_cases) - len(catalog["cases"]),
            "case_rows": len(expanded_cases),
            "runs": len(context["test_runs"]), "errors": errors}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["state"] == "PASS" else 1)
