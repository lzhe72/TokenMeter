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
    for address, count in (("B6", len(context["requirements"])),
                           ("B7", len(context["acceptance_criteria"])),
                           ("B8", len(catalog["cases"])), ("B9", len(context["test_runs"]))):
        equal(overview[address], count, "summary " + address)
    equal(overview["B14"], context["metadata"]["observed_run_state"], "full regression state")
    for row, case in enumerate(catalog["cases"], start=5):
        cells = sheets["05测试用例"]
        equal(cells[f"B{row}"], case["id"], "case ID")
        if case["id"] in context["latest_case_states"]:
            equal(cells[f"J{row}"], context["latest_case_states"][case["id"]], case["id"] + " state")
            equal(cells[f"M{row}"], context["latest_case_runs"][case["id"]], case["id"] + " evidence run")
    for row, run in enumerate(context["test_runs"], start=5):
        cells = sheets["06测试批次"]
        counts = [run["passed_cases"], run["failed_cases"], run.get("blocked_cases", 0)]
        for column, value in zip("ADEFGHL", [run["run_id"], run["state"], sum(counts), *counts, run["result_workbook"]]):
            equal(cells[f"{column}{row}"], value, run["run_id"] + " " + column)
        if not (ROOT / run["result_workbook"]).is_file():
            errors.append(run["run_id"] + ": result workbook missing")
    return {"state": "FAIL" if errors else "PASS", "scope": "project_workbook_readback_only",
            "product_tests_executed": False, "release_eligible": False,
            "sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
            "sheets": len(sheets), "cases": len(catalog["cases"]),
            "runs": len(context["test_runs"]), "errors": errors}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["state"] == "PASS" else 1)
