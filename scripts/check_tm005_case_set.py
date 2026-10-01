#!/usr/bin/env python3
"""Check the TM-005 fixed case set before product bindings become available."""

from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
RELEASE = "v0.5.0-20261001T034729Z"
RELEASE_DIR = Path("releases") / RELEASE
PARENT = re.compile(r"^### (?:`)?(TC-TM005-[A-Z0-9-]+)(?:`)? · ", re.MULTILINE)
VARIANT = re.compile(r"TC-TM005-[A-Z0-9-]+#[A-Z][A-Z0-9_]*")


def expected_case_set(manifest: dict, detailed: str) -> tuple[list[str], set[str], set[str]]:
    errors = []
    traced = [row.get("test") for row in manifest.get("traceability", [])]
    parents = PARENT.findall(detailed)
    variants = set(VARIANT.findall(detailed))
    if len(parents) != len(set(parents)) or len(parents) != 32:
        errors.append("detailed document must have 32 unique TM-005 parent headings")
    if len(variants) != 6:
        errors.append("detailed document must have six stable TM-005 variants")
    if len(traced) != len(set(traced)) or len(traced) != 40:
        errors.append("release manifest must have 40 unique test references")
    if set(traced) != set(parents) | variants | {"E2E-TM005-001", "E2E-TM005-002"}:
        errors.append("release manifest and detailed case set differ")
    for variant in variants:
        if variant.split("#", 1)[0] not in parents:
            errors.append("variant has no parent: " + variant)
    return errors, set(parents), variants


def validate_catalog(catalog: dict, parents: set[str], variants: set[str]) -> tuple[list[str], list[str]]:
    errors = []
    rows = [row for row in catalog.get("cases", []) if row.get("id", "").startswith("TC-TM005-")]
    ids = [row["id"] for row in rows]
    actual_variants = [item["id"] for row in rows for item in row.get("variants", [])]
    if len(ids) != len(set(ids)) or set(ids) != parents:
        errors.append("machine catalog TM-005 parent set differs")
    if len(actual_variants) != len(set(actual_variants)) or set(actual_variants) != variants:
        errors.append("machine catalog TM-005 variant set differs")
    gaps = []
    for row in rows:
        if row.get("release_id") != RELEASE:
            errors.append("wrong release: " + row["id"])
        if row.get("execution_status") == "PASS" and not row.get("evidence"):
            errors.append("unbacked PASS: " + row["id"])
        if not row.get("binding"):
            gaps.append(row["id"])
        for variant in row.get("variants", []):
            if variant.get("execution_status") == "PASS" and not variant.get("evidence"):
                errors.append("unbacked PASS: " + variant["id"])
            if not variant.get("binding"):
                gaps.append(variant["id"])
    return errors, sorted(gaps)


def main() -> int:
    manifest = json.loads((ROOT / RELEASE_DIR / "00-manifest.json").read_text())
    detailed = (ROOT / RELEASE_DIR / "04a-test-cases.md").read_text()
    errors, parents, variants = expected_case_set(manifest, detailed)
    catalog_path = ROOT / "tests/test_cases.json"
    if catalog_path.is_file():
        catalog_errors, gaps = validate_catalog(json.loads(catalog_path.read_text()), parents, variants)
        errors.extend(catalog_errors)
        catalog_present = True
    else:
        catalog_present = False
        gaps = sorted(parents | variants)
    print(json.dumps({"state": "FAIL" if errors else "BLOCKED",
                      "scope": "tm005_case_design_and_binding_preflight_only",
                      "release_eligible": False, "product_tests_executed": 0,
                      "parents": len(parents), "variants": len(variants),
                      "machine_catalog_present": catalog_present,
                      "missing_bindings": gaps, "errors": errors},
                     ensure_ascii=False, indent=2))
    return 1 if errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
