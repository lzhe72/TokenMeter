#!/usr/bin/env python3
"""Check the TM-005 fixed case set before product bindings become available."""

from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
RELEASE = "v0.5.0-20261001T034729Z"
RELEASE_DIR = Path("releases") / RELEASE
PRODUCT_DETAIL = RELEASE_DIR / "04a-test-cases.md"
PRODUCT_PARENT = re.compile(r"^### (?:`)?(TC-TM005-(?!CORE-)[A-Z0-9-]+)(?:`)? · ", re.MULTILINE)
CORE_PARENT = re.compile(r"^### (?:`)?(TC-TM005-CORE-[A-Z0-9-]+)(?:`)? · ", re.MULTILINE)
VARIANT = re.compile(r"TC-TM005-[A-Z0-9-]+#[A-Z][A-Z0-9_]*")
CORE_IDS = {f"TC-TM005-CORE-0{number}" for number in range(1, 7)}
SCENARIOS = {"E2E-TM005-001", "E2E-TM005-002"}


def expected_case_set(manifest: dict, detailed: str,
                      auxiliary_details: tuple[str, ...] = ()) -> tuple[list[str], set[str], set[str], set[str]]:
    errors = []
    traced = [row.get("test") for row in manifest.get("traceability", [])]
    parents = PRODUCT_PARENT.findall(detailed)
    variants = set(VARIANT.findall(detailed))
    core_headings = [case for text in (detailed, *auxiliary_details) for case in CORE_PARENT.findall(text)]
    core = set(core_headings)
    traced_core = {case for case in traced if isinstance(case, str) and case.startswith("TC-TM005-CORE-")}
    traced_product = [case for case in traced if case not in traced_core]
    if len(parents) != len(set(parents)) or len(parents) != 32:
        errors.append("detailed document must have 32 unique TM-005 parent headings")
    if len(variants) != 6:
        errors.append("detailed document must have six stable TM-005 variants")
    if len(traced_product) != len(set(traced_product)) or len(traced_product) != 40:
        errors.append("release manifest must have 40 unique product/variant/scenario references")
    if set(traced_product) != set(parents) | variants | SCENARIOS:
        errors.append("release manifest and product case set differ")
    if len(core_headings) != len(core):
        errors.append("duplicate CORE heading")
    if core != CORE_IDS or traced_core != CORE_IDS or len(set(traced)) != 46:
        errors.append("CORE auxiliary set must contain exactly six manifest and detailed cases")
    for variant in variants:
        if variant.split("#", 1)[0] not in parents:
            errors.append("variant has no parent: " + variant)
    return errors, set(parents), variants, core


def validate_catalog(catalog: dict, parents: set[str], variants: set[str],
                     core: set[str]) -> tuple[list[str], list[str], list[str]]:
    errors = []
    rows = [row for row in catalog.get("cases", []) if row.get("id", "").startswith("TC-TM005-")]
    product_rows = [row for row in rows if not row["id"].startswith("TC-TM005-CORE-")]
    core_rows = [row for row in rows if row["id"].startswith("TC-TM005-CORE-")]
    product_ids = [row["id"] for row in product_rows]
    core_ids = [row["id"] for row in core_rows]
    actual_variants = [item["id"] for row in product_rows for item in row.get("variants", [])]
    if len(product_ids) != len(set(product_ids)) or set(product_ids) != parents:
        errors.append("machine catalog TM-005 product parent set differs")
    if len(actual_variants) != len(set(actual_variants)) or set(actual_variants) != variants:
        errors.append("machine catalog TM-005 product variant set differs")
    if len(core_ids) != len(set(core_ids)) or set(core_ids) != core:
        errors.append("machine catalog TM-005 CORE auxiliary set differs")
    product_gaps = []
    core_gaps = []
    for row in rows:
        gaps = core_gaps if row["id"].startswith("TC-TM005-CORE-") else product_gaps
        if row.get("release_id") != RELEASE:
            errors.append("wrong release: " + row["id"])
        if row.get("execution_status") == "PASS" and not row.get("evidence"):
            errors.append("unbacked PASS: " + row["id"])
        if not row.get("binding"):
            gaps.append(row["id"])
        for variant in row.get("variants", []):
            if row["id"].startswith("TC-TM005-CORE-"):
                errors.append("CORE auxiliary cases cannot contain product variants: " + row["id"])
            if variant.get("execution_status") == "PASS" and not variant.get("evidence"):
                errors.append("unbacked PASS: " + variant["id"])
            if not variant.get("binding"):
                gaps.append(variant["id"])
    return errors, sorted(product_gaps), sorted(core_gaps)


def case_document_registration(manifest: dict) -> tuple[list[str], tuple[str, ...]]:
    registered = [Path(path) for path in manifest.get("test_case_documents", [])]
    discovered = {path.relative_to(ROOT) for path in (ROOT / RELEASE_DIR).glob("04*-test-cases.md")}
    errors = []
    if len(registered) != len(set(registered)) or set(registered) != discovered or PRODUCT_DETAIL not in discovered:
        errors.append("release case documents are not fully registered")
    auxiliary_details = tuple((ROOT / path).read_text() for path in sorted(set(registered) - {PRODUCT_DETAIL})
                              if path in discovered)
    return errors, auxiliary_details


def main() -> int:
    manifest = json.loads((ROOT / RELEASE_DIR / "00-manifest.json").read_text())
    detailed = (ROOT / PRODUCT_DETAIL).read_text()
    errors, auxiliary_details = case_document_registration(manifest)
    case_errors, parents, variants, core = expected_case_set(manifest, detailed, auxiliary_details)
    errors.extend(case_errors)
    catalog_path = ROOT / "tests/test_cases.json"
    if catalog_path.is_file():
        catalog_errors, product_gaps, core_gaps = validate_catalog(
            json.loads(catalog_path.read_text()), parents, variants, core)
        errors.extend(catalog_errors)
        catalog_present = True
    else:
        catalog_present = False
        product_gaps = sorted(parents | variants)
        core_gaps = sorted(core)
    print(json.dumps({"state": "FAIL" if errors else "BLOCKED",
                      "scope": "tm005_case_design_and_binding_preflight_only",
                      "release_eligible": False, "product_tests_executed": 0,
                      "product_parents": len(parents), "product_variants": len(variants),
                      "scenario_groups": len(SCENARIOS), "core_auxiliary": len(core),
                      "core_design_pending": sorted(CORE_IDS - core),
                      "machine_catalog_present": catalog_present,
                      "missing_product_bindings": product_gaps,
                      "missing_core_bindings": core_gaps, "errors": errors},
                     ensure_ascii=False, indent=2))
    return 1 if errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
