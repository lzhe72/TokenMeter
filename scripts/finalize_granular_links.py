#!/usr/bin/env python3
"""Add native OOXML links after artifact-tool renders the granular workbook.

The bundled renderer cannot calculate Excel's HYPERLINK formula. This small
package edit changes only the evidence sheet's hyperlink relationships.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile


MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_PACKAGE = "http://schemas.openxmlformats.org/package/2006/relationships"
SHEET = "xl/worksheets/sheet8.xml"
RELS = "xl/worksheets/_rels/sheet8.xml.rels"
SHA = re.compile(r"[a-f0-9]{64}\Z")
ET.register_namespace("x", MAIN)
ET.register_namespace("r", REL_DOC)


def finalize(workbook: Path, model_path: Path) -> int:
    workbook = workbook.absolute()
    model_path = model_path.absolute()
    if workbook.parent != model_path.parent or workbook.suffix != ".xlsx" or model_path.name != "granular-source.json":
        raise ValueError("Workbook and model must share the export directory")
    model = json.loads(model_path.read_text(encoding="utf-8"))
    entries = [*model["source_files"], *model["evidence"]]
    links = []
    for index, entry in enumerate(entries):
        relative = entry.get("link")
        if not relative:
            continue
        if (not isinstance(relative, str) or not relative.startswith("evidence/")
                or "\\" in relative or any(part in ("", ".", "..") for part in relative.split("/"))):
            raise ValueError("An evidence link is not an owned relative file")
        digest = entry.get("sha256")
        if not isinstance(digest, str) or not SHA.fullmatch(digest):
            raise ValueError("Linked evidence has no valid SHA-256")
        target = workbook.parent / relative
        if any(part.is_symlink() for part in (target, *target.parents)):
            raise ValueError("Linked evidence path contains a symlink")
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("Linked evidence changed before XLSX finalization")
        links.append((f"E{index + 5}", relative))
    with ZipFile(workbook) as source:
        names = source.namelist()
        if SHEET not in names or RELS in names:
            raise ValueError("Unexpected evidence worksheet or existing relationships")
        book = ET.fromstring(source.read("xl/workbook.xml"))
        ordered = book.find(f"{{{MAIN}}}sheets")
        if ordered is None or len(ordered) < 8 or ordered[7].get("name") != "07证据来源":
            raise ValueError("Evidence sheet identity changed")
        sheet = ET.fromstring(source.read(SHEET))
        existing = sheet.find(f"{{{MAIN}}}hyperlinks")
        if existing is not None:
            raise ValueError("Evidence sheet already contains links")
        hyperlinks = ET.Element(f"{{{MAIN}}}hyperlinks")
        relationships = ET.Element(f"{{{REL_PACKAGE}}}Relationships")
        for number, (cell, target) in enumerate(links, 1):
            rid = f"rId{number}"
            ET.SubElement(hyperlinks, f"{{{MAIN}}}hyperlink",
                          {"ref": cell, f"{{{REL_DOC}}}id": rid, "display": "打开原件"})
            ET.SubElement(relationships, f"{{{REL_PACKAGE}}}Relationship",
                          {"Id": rid, "Type": REL_DOC + "/hyperlink",
                           "Target": target, "TargetMode": "External"})
        before = next((i for i, child in enumerate(sheet)
                       if child.tag in {f"{{{MAIN}}}printOptions", f"{{{MAIN}}}pageMargins",
                                        f"{{{MAIN}}}drawing", f"{{{MAIN}}}extLst"}), len(sheet))
        sheet.insert(before, hyperlinks)
        edited_sheet = ET.tostring(sheet, encoding="utf-8", xml_declaration=True)
        edited_rels = ET.tostring(relationships, encoding="utf-8", xml_declaration=True)
        temporary = workbook.with_name("." + workbook.name + f".{os.getpid()}.links.tmp")
        with ZipFile(temporary, "w") as output:
            for item in source.infolist():
                data = edited_sheet if item.filename == SHEET else source.read(item.filename)
                output.writestr(item, data)
            output.writestr(RELS, edited_rels)
    os.chmod(temporary, 0o600)
    with ZipFile(temporary) as final:
        if final.testzip() is not None or len(ET.fromstring(final.read(RELS))) != len(links):
            raise ValueError("Final XLSX relationships failed readback")
    os.replace(temporary, workbook)
    return len(links)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps({"state": "PASS", "links": finalize(arguments.workbook, arguments.model)}))


if __name__ == "__main__":
    main()
