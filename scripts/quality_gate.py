#!/usr/bin/env python3
"""Check traceability, or invoke the product E2E gate (currently blocked).

Metadata PASS never grants product release eligibility. No command accepts an
external result file as proof of execution.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FEATURES = {f"TM-{n:03d}" for n in range(1, 13)}
FEATURE_STATES = {"planned", "in_progress", "implemented"}


def visible_specification(body: str) -> str:
    """Only rendered prose/table content can define an acceptance contract."""
    body = re.sub(r"<!--.*?(?:-->|$)", "", body, flags=re.DOTALL)
    lines, fence = [], None
    for line in body.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence is not None:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if marker:
            fence = marker[1]
        elif not line.startswith(("    ", "\t")):
            lines.append(line)
    return "\n".join(lines)


def validate_baseline(root: Path) -> tuple[list[str], dict[str, int]]:
    """Load the fixed sibling checker without depending on caller sys.path."""
    try:
        source = Path(__file__).resolve().with_name("check_docs.py")
        spec = importlib.util.spec_from_file_location("tokenmeter_documentation_checker", source)
        if spec is None or spec.loader is None:
            raise ImportError("documentation checker cannot be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.validate_docs(root)
    except (OSError, ValueError, RuntimeError, ImportError, SyntaxError) as exc:
        return [f"documentation checker unavailable: {exc}"], {}


def validate_manifest(root: Path) -> tuple[list[str], dict[str, int]]:
    root = root.resolve()
    errors: list[str] = []
    counts = {"features": 0, "cases": 0, "implemented": 0, "test_bindings": 0}

    def read(relative: str) -> dict[str, Any]:
        try:
            path = (root / relative).resolve()
            if not path.is_relative_to(root):
                raise ValueError("manifest must remain inside repository")
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RuntimeError, RecursionError) as exc:
            errors.append(f"{relative}: {exc}")
            return {}
        if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
            errors.append(f"{relative}: schema_version must be integer 1")
            return {}
        return value

    def nonempty(value: Any, label: str) -> bool:
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label}: nonempty text required")
            return False
        return True

    def file_ref(value: Any, label: str) -> bool:
        if not nonempty(value, label):
            return False
        candidate = Path(value)
        try:
            resolved = (root / candidate).resolve()
            if candidate.is_absolute() or not resolved.is_relative_to(root):
                raise ValueError("reference must remain inside repository")
            if not resolved.is_file() or resolved.stat().st_size == 0:
                raise ValueError("referenced file is absent or empty")
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f"{label}: {exc}: {value}")
            return False
        return True

    def text_list(value: Any, label: str) -> list[str]:
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            errors.append(f"{label}: list of nonempty strings required")
            return []
        if len(value) != len(set(value)):
            errors.append(f"{label}: duplicate entries")
        return value

    specs: dict[str, str] = {}

    def read_spec(reference: Any, label: str) -> str:
        if not file_ref(reference, label):
            return ""
        if reference not in specs:
            try:
                specs[reference] = visible_specification((root / reference).read_text(encoding="utf-8"))
            except (OSError, UnicodeError) as exc:
                errors.append(f"{label}: cannot read specification: {exc}")
                return ""
        return specs[reference]

    # This list is maintained from approved requirements, independently of the
    # test matrix. Never derive the required coverage set from existing cases.
    acceptance_doc = read("tests/acceptance.json")
    acceptance_rows = acceptance_doc.get("acceptance_criteria")
    if not isinstance(acceptance_rows, list) or not acceptance_rows:
        errors.append("acceptance_criteria: a nonempty independent list is required")
        acceptance_rows = []
    acceptances: dict[str, dict[str, Any]] = {}
    for row in acceptance_rows:
        if not isinstance(row, dict):
            errors.append("acceptance: object required")
            continue
        acceptance_id = row.get("id")
        if not nonempty(acceptance_id, "acceptance.id"):
            continue
        match = re.fullmatch(r"AC-TM(\d{3,})-\d{3,}", acceptance_id)
        if not match:
            errors.append(f"{acceptance_id}: invalid acceptance ID")
            continue
        if acceptance_id in acceptances:
            errors.append(f"duplicate acceptance: {acceptance_id}")
        acceptances[acceptance_id] = row
        if row.get("feature_id") != "TM-" + match[1]:
            errors.append(f"{acceptance_id}: feature_id must match acceptance ID")
        if row.get("requirement_id") != "REQ-TM" + match[1]:
            errors.append(f"{acceptance_id}: requirement_id must match acceptance ID")
        nonempty(row.get("criterion"), f"{acceptance_id}.criterion")
        text_list(row.get("data_requirements"), f"{acceptance_id}.data_requirements")
        read_spec(row.get("spec"), f"{acceptance_id}.spec")

    dataset_doc = read("tests/datasets.json")
    dataset_rows = dataset_doc.get("datasets")
    datasets: dict[str, dict[str, Any]] = {}
    if not isinstance(dataset_rows, list) or not dataset_rows:
        errors.append("datasets: a nonempty list is required")
        dataset_rows = []
    for dataset in dataset_rows:
        if not isinstance(dataset, dict):
            errors.append("dataset: object required")
            continue
        identifier = dataset.get("id")
        if not nonempty(identifier, "dataset.id"):
            continue
        if identifier in datasets:
            errors.append(f"duplicate dataset: {identifier}")
        datasets[identifier] = dataset
        nonempty(dataset.get("description"), f"{identifier}.description")
        text_list(dataset.get("capabilities", []), f"{identifier}.capabilities")
        if not isinstance(dataset.get("status"), str) or dataset.get("status") not in {"planned", "available"}:
            errors.append(f"{identifier}: invalid dataset status")
        if dataset.get("status") == "available" or dataset.get("generator") is not None:
            file_ref(dataset.get("generator"), f"{identifier}.generator")

    matrix = read("tests/feature_matrix.json")
    features = matrix.get("features")
    if not isinstance(features, list) or not features:
        errors.append("features: a nonempty list is required")
        features = []
    seen_features: set[str] = set()
    seen_cases: set[str] = set()
    covered_acceptances: set[str] = set()
    feature_rows: dict[str, dict[str, Any]] = {}
    for feature in features:
        if not isinstance(feature, dict):
            errors.append("feature: object required")
            continue
        identifier = feature.get("id")
        if not nonempty(identifier, "feature.id"):
            continue
        if not re.fullmatch(r"TM-\d{3,}", identifier):
            errors.append(f"{identifier}: invalid feature ID")
        if identifier in seen_features:
            errors.append(f"duplicate feature: {identifier}")
        seen_features.add(identifier)
        feature_rows[identifier] = feature
        counts["features"] += 1
        nonempty(feature.get("title"), f"{identifier}.title")
        if not isinstance(feature.get("version"), str) or not re.fullmatch(r"\d+\.\d+\.\d+", feature["version"]):
            errors.append(f"{identifier}: version must be MAJOR.MINOR.PATCH")
        status = feature.get("status")
        if not isinstance(status, str) or status not in FEATURE_STATES:
            errors.append(f"{identifier}: invalid feature status")
            status = ""
        active = status in {"in_progress", "implemented"}
        counts["implemented"] += int(status == "implemented")
        spec_text = read_spec(feature.get("spec"), f"{identifier}.spec")
        requirement = "REQ-" + identifier.replace("-", "")
        if feature.get("source_requirement") != requirement:
            errors.append(f"{identifier}.source_requirement: must equal {requirement}")
        elif not re.search(r"(?<![A-Za-z0-9_-])" + re.escape(requirement) + r"(?![A-Za-z0-9_-])", spec_text):
            errors.append(f"{identifier}.source_requirement: {requirement} not found in spec")
        cases = feature.get("cases")
        if not isinstance(cases, list) or not cases:
            errors.append(f"{identifier}: at least one E2E case required")
            continue
        for case in cases:
            if not isinstance(case, dict):
                errors.append(f"{identifier}: case object required")
                continue
            case_id = case.get("id")
            if not nonempty(case_id, f"{identifier}.case.id"):
                continue
            if not re.fullmatch(r"E2E-" + identifier.replace("-", "") + r"-\d{3,}", case_id):
                errors.append(f"{case_id}: ID must belong to {identifier}")
            if case_id in seen_cases:
                errors.append(f"duplicate case: {case_id}")
            seen_cases.add(case_id)
            counts["cases"] += 1
            for field in ("scenario", "expected"):
                nonempty(case.get(field), f"{case_id}.{field}")
            acceptance = "AC-" + case_id.removeprefix("E2E-")
            if case.get("acceptance_id") != acceptance:
                errors.append(f"{case_id}.acceptance_id: must equal {acceptance}")
            elif not re.search(r"(?<![A-Za-z0-9_-])" + re.escape(acceptance) + r"(?![A-Za-z0-9_-])", spec_text):
                errors.append(f"{case_id}.acceptance_id: {acceptance} not found in spec")
            contract = acceptances.get(acceptance)
            if contract is None:
                errors.append(f"{acceptance}: not registered in independent acceptance list")
            else:
                covered_acceptances.add(acceptance)
                for field, expected in (("feature_id", identifier), ("requirement_id", requirement),
                                        ("spec", feature.get("spec"))):
                    if contract.get(field) != expected:
                        errors.append(f"{acceptance}: {field} differs from feature contract")
            sop = case.get("sop")
            if not isinstance(sop, str) or not re.fullmatch(r"sop/SOP-\d{3}-[a-z0-9]+(?:-[a-z0-9]+)*\.md", sop):
                errors.append(f"{case_id}.sop: must reference a root sop/SOP-XXX-slug.md workflow")
            file_ref(sop, f"{case_id}.sop")
            dataset_id = case.get("dataset")
            dataset = datasets.get(dataset_id) if isinstance(dataset_id, str) else None
            if dataset is None:
                errors.append(f"{case_id}: unknown dataset {dataset_id!r}")
            elif active and dataset.get("status") != "available":
                errors.append(f"{case_id}: active feature needs available dataset")
            if dataset is not None and contract is not None:
                required = text_list(contract.get("data_requirements"), f"{acceptance}.data_requirements")
                available = text_list(dataset.get("capabilities", []), f"{dataset_id}.capabilities")
                missing_capabilities = sorted(set(required) - set(available))
                if missing_capabilities:
                    errors.append(f"{case_id}: dataset {dataset_id} does not cover " + ", ".join(missing_capabilities))
            program = case.get("data_program")
            if active or program is not None or (dataset and dataset.get("status") == "available"):
                file_ref(program, f"{case_id}.data_program")
                if dataset and program != dataset.get("generator"):
                    errors.append(f"{case_id}: data_program differs from registered generator")
            if "automated_test" not in case:
                errors.append(f"{case_id}: automated_test must be explicit, null only while planned")
            binding = case.get("automated_test")
            if active or binding is not None:
                if file_ref(binding, f"{case_id}.automated_test"):
                    counts["test_bindings"] += 1
    missing = sorted(REQUIRED_FEATURES - seen_features)
    if missing:
        errors.append("required v1 features removed: " + ", ".join(missing))
    for acceptance in sorted(set(acceptances) - covered_acceptances):
        errors.append(f"{acceptance}: no E2E case covers required acceptance")

    # The Markdown definition remains independently enumerable if a case and its
    # registry entry are both removed. A mention alone is not a definition.
    defined_acceptances: dict[str, tuple[str, str, str, str]] = {}
    for reference, content in specs.items():
        for acceptance in re.findall(r"(?<![A-Za-z0-9_-])AC-TM\d{3,}-\d{3,}(?![A-Za-z0-9_-])", content):
            if acceptance not in acceptances:
                errors.append(f"{acceptance}: specification acceptance not registered in independent list")
        for line in content.splitlines():
            match = re.fullmatch(r"\|\s*(REQ-TM\d{3,})\s*\|\s*(TM-\d{3,})\s*\|\s*(AC-TM\d{3,}-\d{3,})\s*\|\s*(.*?)\s*\|", line)
            if match:
                requirement, feature, acceptance, criterion = match.groups()
                if acceptance in defined_acceptances:
                    errors.append(f"{acceptance}: duplicate specification definition")
                defined_acceptances[acceptance] = (reference, requirement, feature, criterion)
    for acceptance, row in acceptances.items():
        definition = defined_acceptances.get(acceptance)
        if definition is None:
            errors.append(f"{acceptance}: acceptance definition not found in spec")
        elif definition[:3] != (row.get("spec"), row.get("requirement_id"), row.get("feature_id")):
            errors.append(f"{acceptance}: specification definition ownership differs from registry")
        elif definition[3] != row.get("criterion"):
            errors.append(f"{acceptance}: criterion differs from independent specification definition")

    dependencies: dict[str, list[str]] = {}
    for identifier, feature in feature_rows.items():
        dependencies[identifier] = text_list(feature.get("depends_on", []), f"{identifier}.depends_on")
        for dependency in dependencies[identifier]:
            predecessor = feature_rows.get(dependency)
            if predecessor is None:
                errors.append(f"{identifier}: unknown feature dependency {dependency}")
                continue
            versions = (feature.get("version"), predecessor.get("version"))
            if all(isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+", version) for version in versions):
                if tuple(map(int, versions[1].split("."))) > tuple(map(int, versions[0].split("."))):
                    errors.append(f"{identifier}: dependency {dependency} requires a future version")
            if feature.get("status") in ("in_progress", "implemented") and predecessor.get("status") != "implemented":
                errors.append(f"{identifier}: active feature dependency {dependency} is not implemented")
    visited: set[str] = set()

    def visit(identifier: str, ancestors: set[str]) -> None:
        if identifier in ancestors:
            errors.append(f"{identifier}: feature dependency cycle")
            return
        if identifier in visited:
            return
        for dependency in dependencies.get(identifier, []):
            visit(dependency, ancestors | {identifier})
        visited.add(identifier)

    for identifier in dependencies:
        visit(identifier, set())
    return errors, counts


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("check", "iteration", "release"))
    args = parser.parse_args(argv)
    baseline_errors, baseline_counts = validate_baseline(root)
    if baseline_errors:
        print(json.dumps({"state": "FAIL", "scope": "documentation_baseline_only",
                          "release_eligible": False, "counts": baseline_counts,
                          "errors": baseline_errors}, ensure_ascii=False, indent=2))
        return 1
    errors, counts = validate_manifest(root)
    if errors:
        print(json.dumps({"state": "FAIL", "scope": "traceability", "release_eligible": False,
                          "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({
        "state": "PASS", "scope": "traceability_only", "counts": counts,
        "release_eligible": False, "documentation_state": "PASS", "documentation_counts": baseline_counts,
        "message": "仅文档基线与规范引用检查通过；尚未证明任何产品 E2E。",
    }, ensure_ascii=False), flush=True)
    if args.phase == "check":
        return 0
    runner = root / "scripts/e2e.py"
    if not runner.resolve().is_relative_to(root.resolve()) or not runner.is_file():
        print(json.dumps({"state": "BLOCKED", "reason": "Missing product E2E runner", "release_eligible": False}))
        return 2
    # Fixed repository-owned entrypoint; external pass.json files are not inputs.
    try:
        result = subprocess.run([sys.executable, str(runner), "--phase", args.phase], cwd=root, check=False)
    except OSError as exc:
        print(json.dumps({"state": "BLOCKED", "reason": str(exc), "release_eligible": False}))
        return 2
    if result.returncode:
        return 2 if result.returncode == 2 else 1
    # Bootstrap safeguard: connecting an executor also requires implementing and
    # testing the evidence verifier defined in docs/standards/release.md. A stub exit 0
    # or forged PASS output must never be enough to unlock release.
    print(json.dumps({"state": "BLOCKED", "reason": "Native evidence verifier not implemented", "release_eligible": False}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
