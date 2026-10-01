#!/usr/bin/env python3
"""Build and export a per-run TC workbook without borrowing suite PASS results.

Usage: python3 scripts/granular_test_result.py --report <run>/result.json
       --output <new-directory> [--aggregate-report <run>/result.json]
       [--aux-report <run>/result.json] [--audit-report <audit.json>]
       [--checks <checks.json>]

Only raw suite events with an explicit TC ID, baseline step, observed value and
verified source file can establish an individual TC result. Older runs without
that binding are reported as BLOCKED for each TM-001 TC.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
from io import BytesIO
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
NODE = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
SHA = re.compile(r"[a-f0-9]{64}\Z")
STATES = {"PASS", "FAIL", "BLOCKED"}
AUX_PREFIXES = ("TC-TM001-UI-", "TC-TM001-CATALOG-", "TC-TM001-RECORDS-", "TC-TM001-GATE-")
SPEC_BY_GROUP = {"LOGIN": "granular-login.spec.ts", "PASSWORD": "granular-login.spec.ts",
                 "SESSION": "granular-account.spec.ts", "ADMIN": "granular-account.spec.ts",
                 "BOOTSTRAP": "granular-account.spec.ts", "CONFIG": "granular-config.spec.ts",
                 "UPDATE": "granular-update.spec.ts", "UI": "granular-auxiliary.spec.ts"}


class Invalid(ValueError):
    """Input identity, source evidence or destination contradicts the contract."""


class Blocked(Invalid):
    """A required export runtime or input is unavailable."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(path: Path) -> Path:
    path = Path(path).absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise Invalid(f"Symlink is not an allowed input or output path: {path}")
    return path


def read_file(path: Path) -> bytes:
    path = safe_path(path)
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise Invalid(f"Expected a regular file: {path}")
        data = stream.read()
        after = os.fstat(stream.fileno())
    now = path.lstat()
    signature = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
    if signature(before) != signature(after) or signature(after) != signature(now):
        raise Invalid(f"Source changed while being read: {path}")
    return data


def read_json(path: Path) -> tuple[dict, bytes]:
    data = read_file(path)
    value = json.loads(data)
    if not isinstance(value, dict):
        raise Invalid(f"JSON source must be an object: {path}")
    return value, data


def display_path(path: Path, run_root: Path | None = None) -> str:
    path = Path(path).absolute()
    for root, prefix in ((ROOT, ""), (run_root, "本次运行/")):
        if root is not None and path.is_relative_to(root):
            return prefix + str(path.relative_to(root))
    return path.name


def evidence_file(run_root: Path, descriptor: object) -> tuple[bytes | None, str, str]:
    if not isinstance(descriptor, dict):
        return None, "缺失", ""
    relative = descriptor.get("path")
    digest = descriptor.get("sha256")
    size = descriptor.get("bytes")
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or Path(relative).is_absolute() or any(part in ("", ".", "..") for part in relative.split("/"))
            or not isinstance(digest, str) or not SHA.fullmatch(digest)
            or type(size) is not int or size < 1):
        return None, "描述无效", str(relative or "")
    target = run_root / relative
    try:
        data = read_file(target)
    except (OSError, Invalid):
        return None, "文件缺失或路径不安全", relative
    if len(data) != size or sha(data) != digest:
        return None, "摘要或大小不符", relative
    return data, "已核对", relative


def completed_playwright_calls(identity: str, raw: bytes | None,
                               trace: bytes | None) -> tuple[list[dict], str | None]:
    """Bind one passed no-retry Playwright attempt to its completed UI trace."""
    if raw is None or trace is None:
        return [], "缺少已核对的 Playwright 原始结果或 UI trace"
    try:
        report = json.loads(raw)
        suites = report.get("suites", [])
        specs = [spec for suite in suites for spec in suite.get("specs", [])]
        tests = [test for spec in specs for test in spec.get("tests", [])]
        results = [result for test in tests for result in test.get("results", [])]
        group = identity.split("-")[2]
        expected_spec = ("granular-update-validation.spec.ts" if identity.startswith("TC-TM001-UPDATE-05#")
                         else SPEC_BY_GROUP.get(group))
        if (len(suites) != 1 or len(specs) != 1 or len(tests) != 1 or len(results) != 1
                or specs[0].get("title") != identity or specs[0].get("file") != expected_spec
                or specs[0].get("ok") is not True or results[0].get("status") != "passed"
                or results[0].get("retry") != 0):
            return [], "Playwright 原始结果不是此 TC 的单次通过尝试"
        with zipfile.ZipFile(BytesIO(trace)) as archive:
            member = archive.getinfo("trace.trace")
            if member.file_size > 20_000_000:
                return [], "UI trace 事件文件异常大"
            events = [json.loads(line) for line in archive.read(member).splitlines() if line]
        completed = {event.get("callId") for event in events
                     if event.get("type") == "after" and not event.get("error")}
        calls = [event for event in events if event.get("type") == "before"
                 and event.get("callId") in completed and event.get("class") == "Frame"]
        return calls, None
    except (ValueError, TypeError, KeyError, zipfile.BadZipFile, UnicodeError, OSError):
        return [], "Playwright 原始结果或 UI trace 无法解析"


def playwright_ui_proof(identity: str, raw: bytes | None, trace: bytes | None) -> str | None:
    """Use fixed UI trace checks when step source names the assertion surface."""
    calls, problem = completed_playwright_calls(identity, raw, trace)
    if problem:
        return problem
    if identity not in {"TC-TM001-LOGIN-13", "TC-TM001-LOGIN-14", "TC-TM001-LOGIN-15"}:
        actions = {"click", "dblclick", "fill", "press", "check", "uncheck", "selectOption"}
        observations = {"expect", "isVisible", "textContent", "inputValue", "getAttribute"}
        def indexes(methods: set[str]) -> list[int]:
            return [index for index, event in enumerate(calls)
                    if event.get("method") in methods
                    and "data-testid=" in str(event.get("params", {}).get("selector", ""))]
        acted, observed = indexes(actions), indexes(observations)
        if not acted or not observed or acted[0] >= observed[-1]:
            return "UI trace 未证明真实 App 控件操作及后续界面观察"
        return None
    try:
        def observed(selector: str, methods: set[str]) -> list[int]:
            return [index for index, event in enumerate(calls)
                    if event.get("method") in methods
                    and f'data-testid="{selector}"' in str(event.get("params", {}).get("selector", ""))]
        username = observed("auth.username", {"fill"})
        password = observed("auth.password", {"fill"})
        login = observed("auth.login", {"click"})
        error = observed("auth.error", {"expect", "textContent", "isVisible"})
        recovered = observed("session.username", {"expect", "textContent"})
        if (len(username) < 2 or len(password) < 2 or len(login) < 2 or not error or not recovered
                or not (username[0] < password[0] < login[0] < error[0] < username[1]
                        < password[1] < login[1] < recovered[0])):
            return "UI trace 未证明两次真实登录动作、错误呈现与恢复后的身份观察"
    except (ValueError, TypeError, KeyError, zipfile.BadZipFile, UnicodeError, OSError):
        return "UI trace 登录动作无法解析"
    return None


def valid_png(data: bytes) -> bool:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    index, first, image, ended = 8, True, False, False
    while index + 12 <= len(data):
        length = struct.unpack_from(">I", data, index)[0]
        ending = index + 12 + length
        if length > 100_000_000 or ending > len(data):
            return False
        kind = data[index + 4:index + 8]
        chunk = data[index + 8:index + 8 + length]
        expected_crc = struct.unpack_from(">I", data, index + 8 + length)[0]
        if zlib.crc32(kind + chunk) & 0xffffffff != expected_crc:
            return False
        if first:
            if kind != b"IHDR" or length != 13:
                return False
            width, height = struct.unpack_from(">II", chunk)
            if width < 1 or height < 1:
                return False
            first = False
        if kind == b"IDAT":
            image = True
        if kind == b"IEND":
            ended = True
            index = ending
            break
        index = ending
    return image and ended and index == len(data)


def copy_verified_evidence(model: dict, output_dir: Path, *, reuse: bool = False) -> dict:
    """Snapshot every verified original next to the workbook with SHA readback."""
    copied = deepcopy(model)
    destination = output_dir / "evidence"
    if reuse:
        if not destination.is_dir() or destination.is_symlink():
            raise Invalid("Existing export has no safe evidence directory")
    else:
        destination.mkdir(mode=0o700)
    copied_count = 0
    copied_bytes = 0
    seen = set()
    for item in [*copied["source_files"], *copied["evidence"]]:
        source_text = item.pop("absolute_path", "")
        item["link"] = ""
        if not source_text:
            continue
        source = safe_path(Path(source_text))
        original = read_file(source)
        digest = item.get("sha256")
        if sha(original) != digest:
            raise Invalid(f"Original evidence changed before copying: {item.get('path')}")
        suffix = source.suffix.lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
            suffix = ".bin"
        folder = destination / digest[:2]
        if reuse:
            if not folder.is_dir() or folder.is_symlink():
                raise Invalid("Existing evidence hash directory is missing or unsafe")
        else:
            folder.mkdir(mode=0o700, exist_ok=True)
        target = folder / f"{digest}{suffix}"
        if target not in seen:
            if reuse:
                if not target.is_file() or target.is_symlink():
                    raise Invalid(f"Existing evidence copy is missing: {item.get('path')}")
            else:
                fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(original)
                    stream.flush()
                    os.fsync(stream.fileno())
            copied_count += 1
            copied_bytes += len(original)
            seen.add(target)
        if read_file(target) != original:
            raise Invalid(f"Copied evidence differs from the original: {item.get('path')}")
        item["link"] = str(target.relative_to(output_dir)).replace(os.sep, "/")
    copied["copied_evidence_count"] = copied_count
    copied["copied_evidence_bytes"] = copied_bytes
    return copied


def verify_existing_export(output_dir: Path, model: dict) -> dict:
    saved, saved_bytes = read_json(output_dir / "granular-source.json")
    receipt, _ = read_json(output_dir / "verification.json")
    if saved != model or receipt.get("state") != "PASS" or receipt.get("run_id") != model["run_id"]:
        raise Invalid("Existing export belongs to different source evidence")
    if receipt.get("source_model_sha256") != sha(saved_bytes):
        raise Invalid("Existing export source-model hash changed")
    entry = receipt.get("workbook")
    if not isinstance(entry, dict) or entry.get("path") != f"TokenMeter测试结果-{model['run_id']}.xlsx":
        raise Invalid("Existing export workbook identity changed")
    workbook = output_dir / entry["path"]
    content = read_file(workbook)
    if len(content) != entry.get("bytes") or sha(content) != entry.get("sha256"):
        raise Invalid("Existing workbook hash changed")
    with zipfile.ZipFile(workbook) as package:
        if (package.testzip() is not None or "xl/worksheets/_rels/sheet8.xml.rels" not in package.namelist()
                or b"HYPERLINK is not implemented" in package.read("xl/worksheets/sheet8.xml")):
            raise Invalid("Existing workbook evidence links are not valid")
    return receipt


def _short(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def replay_binding(identity: str, report: dict, run_root: Path) -> tuple[str, str]:
    replay = report.get("replay") if isinstance(report.get("replay"), dict) else {}
    registered = replay.get("cases", {}).get(identity) if isinstance(replay.get("cases"), dict) else None
    if isinstance(registered, dict) and isinstance(registered.get("code"), str) and isinstance(registered.get("command"), str):
        return registered["code"], registered["command"]
    report_file = display_path(run_root / "result.json", run_root)
    if identity.startswith(AUX_PREFIXES):
        code = ("apps/desktop/e2e/granular-auxiliary.spec.ts" if identity.startswith("TC-TM001-UI-")
                else "scripts/granular_auxiliary.py")
        command = ("python3 scripts/granular_auxiliary.py --parent-report " + report_file
                   + " --run-id <新唯一批次> --output <新空目录> --case-id " + identity)
        if identity.startswith("TC-TM001-UI-"):
            command += " --with-ui --package-manifest <原包清单> --dmg <原包> --update-zip <升级包>"
        return code, command
    group = identity.split("-")[2] if len(identity.split("-")) >= 4 else ""
    spec = SPEC_BY_GROUP.get(group)
    code = "apps/desktop/e2e/" + spec if spec else "未绑定固定测试代码"
    candidate = report.get("source_commit") or "<候选SHA>"
    command = ("python3 scripts/granular_e2e.py --package-manifest <原包清单> --dmg <原包> "
               "--update-zip <升级包> --candidate-sha " + candidate
               + " --run-id <新唯一批次> --output <新空目录> --case-id " + identity)
    if report.get("package", {}).get("installed_source") == "development_dmg":
        command += " --development"
    return code, command


def code_snapshot(report: dict, root: Path, role: str) -> tuple[list[dict], set[str]]:
    rows, verified = [], set()
    for descriptor in report.get("test_code_snapshot") or []:
        content, state, relative = evidence_file(root, descriptor)
        rows.append({"role": role, "path": relative, "state": state,
                     "sha256": descriptor.get("sha256", "") if isinstance(descriptor, dict) else "",
                     "absolute_path": str(root / relative) if content is not None else ""})
        if content is not None:
            verified.add(relative.removeprefix("test-code/"))
    return rows, verified


def bound_code_verified(code: str, verified: set[str]) -> bool:
    return bool(code and any(path == code or path.endswith("/" + code) for path in verified))


def timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def auxiliary_binding(primary: dict, auxiliary: dict, expected_ids: set[str]) -> tuple[bool, str]:
    aux_run = auxiliary.get("run_id")
    if not isinstance(aux_run, str) or not RUN_ID.fullmatch(aux_run) or aux_run == primary.get("run_id"):
        return False, "辅助批次 run_id 无效或与主批次相同"
    if auxiliary.get("parent_run_id") != primary.get("run_id"):
        return False, "辅助批次未绑定主 run_id"
    if auxiliary.get("cleanup_completed") is not True:
        return False, "辅助批次独占资源清理未完成"
    listed = auxiliary.get("expected_cases")
    if (not isinstance(listed, list) or any(not isinstance(item, str) for item in listed)
            or len(listed) != len(expected_ids) or set(listed) != expected_ids):
        return False, "辅助批次必测 11 条集合不完整"
    observed = auxiliary.get("tc_results")
    if (not isinstance(observed, list) or len(observed) != len(expected_ids)
            or {item.get("case_id") for item in observed if isinstance(item, dict)} != expected_ids):
        return False, "辅助批次没有 11 条各自独立的结果记录"
    for key in ("release_id", "source_commit", "candidate_tree"):
        if not primary.get(key) or auxiliary.get(key) != primary.get(key):
            return False, f"辅助批次 {key} 与主批次不一致"
    frozen = primary.get("test_inputs_sha256")
    if isinstance(frozen, dict):
        for key, relative in (("catalog_sha256", "tests/test_cases.json"),
                              ("login_variants_sha256", "tests/granular_login_variants.json"),
                              ("update_variants_sha256", "tests/granular_update_variants.json")):
            if auxiliary.get(key) != frozen.get(relative):
                return False, f"辅助批次 {relative} 与主批次冻结清单不一致"
    source_dmg = (primary.get("package") or {}).get("dmg_sha256")
    if not source_dmg or (auxiliary.get("package") or {}).get("dmg_sha256") != source_dmg:
        return False, "辅助批次 DMG 摘要与主批次不一致"
    main_end, aux_begin, aux_end = (timestamp(primary.get("finished_at")), timestamp(auxiliary.get("started_at")),
                                   timestamp(auxiliary.get("finished_at")))
    if (main_end is None or aux_begin is None or aux_end is None
            or not main_end <= aux_begin <= aux_end <= datetime.now(timezone.utc)):
        return False, "辅助批次时间不属于本次候选执行之后"
    return True, "同一 run 关联、候选、原包与时间均一致"


def audit_findings(primary: dict, audit: dict, run_root: Path, audit_root: Path) -> tuple[list[dict], list[dict]]:
    """Read-only independent findings. A finding can only lower an existing PASS."""
    if audit.get("schema_version") != 2 or audit.get("run_id") != primary.get("run_id"):
        raise Invalid("Supplemental audit schema or run ID differs from the primary run")
    if audit.get("source_commit") != primary.get("source_commit"):
        raise Invalid("Supplemental audit candidate differs from the primary run")
    observed = primary.get("tc_results")
    if not isinstance(observed, list):
        raise Invalid("Primary detailed TC records are unavailable for supplemental audit")
    by_id = {item.get("case_id"): item for item in observed if isinstance(item, dict)}
    findings = audit.get("findings")
    if not isinstance(findings, list) or not findings:
        raise Invalid("Supplemental audit has no individual findings")
    ids = [item.get("case_id") if isinstance(item, dict) else None for item in findings]
    if len(ids) != len(set(ids)) or any(identity not in by_id for identity in ids):
        raise Invalid("Supplemental audit has duplicate or foreign TC findings")
    declared = audit.get("audited_cases")
    if not isinstance(declared, list) or declared != ids:
        raise Invalid("Supplemental audit declared case set differs from its findings")
    code = audit.get("auditor_code")
    code_bytes, code_state, code_path = evidence_file(audit_root, code)
    if (code_state != "已核对" or audit.get("auditor_code_sha256") != sha(code_bytes)
            or code_path != "audit-code/audit_granular_evidence.py"):
        raise Invalid("Supplemental auditor fixed-code snapshot is missing or changed")
    rows = []
    evidence_rows = [{"role": "独立复核固定代码", "path": code_path, "state": code_state,
                      "sha256": sha(code_bytes), "absolute_path": str(audit_root / code_path)}]
    frozen_code = {item.get("path"): item.get("sha256") for item in primary.get("test_code_snapshot", [])
                   if isinstance(item, dict)}
    replay = (primary.get("replay") or {}).get("cases") or {}
    for item in findings:
        identity = item["case_id"]
        raw_state = by_id[identity].get("state")
        state = item.get("state")
        if item.get("original_state") != raw_state:
            raise Invalid(f"Supplemental audit original state differs for {identity}")
        if (raw_state == "PASS" and state not in STATES) or (raw_state != "PASS" and state != "NOT_APPLICABLE"):
            raise Invalid(f"Supplemental audit state cannot upgrade {identity}")
        problems = []
        binding = replay.get(identity) if isinstance(replay, dict) else None
        binding_code = binding.get("code") if isinstance(binding, dict) else None
        if (raw_state == "PASS" and (not isinstance(binding_code, str)
                or frozen_code.get("test-code/" + binding_code) != item.get("test_code_sha256"))):
            problems.append("主批次固定测试代码 SHA 与复核记录不一致")
        audit_evidence = item.get("evidence")
        verified = []
        if raw_state == "PASS" and (not isinstance(audit_evidence, dict) or not audit_evidence):
            problems.append("复核没有逐例原始证据")
        if isinstance(audit_evidence, dict):
            for role, raw_descriptors in audit_evidence.items():
                descriptors = raw_descriptors if isinstance(raw_descriptors, list) else [raw_descriptors]
                for source in descriptors:
                    content, status, relative = evidence_file(run_root, source)
                    evidence_rows.append({"role": f"独立复核 {identity} {role}", "path": relative,
                                          "state": status,
                                          "sha256": source.get("sha256", "") if isinstance(source, dict) else "",
                                          "absolute_path": str(run_root / relative) if content is not None else ""})
                    if status != "已核对":
                        problems.append(f"{role} {status}")
                    else:
                        verified.append(f"{relative} (SHA-256 {sha(content)[:12]})")
        effective = "BLOCKED" if problems and raw_state == "PASS" else state
        reason = str(item.get("reason") or "")
        if problems:
            reason += "；复核证据缺口：" + "；".join(dict.fromkeys(problems))
        rows.append({"id": identity, "original_state": raw_state, "audit_claim": state,
                     "state": effective, "reason": reason, "evidence": "\n".join(verified),
                     "test_code_sha256": item.get("test_code_sha256", ""),
                     "auditor_code_sha256": sha(code_bytes)})
    return rows, evidence_rows


def load_suite_events(report: dict, run_root: Path, case_ids: set[str]):
    expected = report.get("expected_cases")
    suites = report.get("suites")
    if not isinstance(expected, list) or not expected or len(expected) != len(set(expected)):
        raise Invalid("Expected aggregate suite IDs are missing or duplicated")
    if not isinstance(suites, list):
        raise Invalid("The run has no suite result list")
    suite_map = {}
    for suite in suites:
        if not isinstance(suite, dict) or suite.get("case_id") not in expected or suite["case_id"] in suite_map:
            raise Invalid("Suite result is foreign or duplicated")
        suite_map[suite["case_id"]] = suite
    observations = defaultdict(list)
    issues = defaultdict(list)
    suite_rows = []
    evidence_rows = []
    for suite_id in expected:
        suite = suite_map.get(suite_id)
        raw_state = suite.get("state") if suite else "BLOCKED"
        if raw_state not in STATES:
            raise Invalid(f"Invalid aggregate suite state: {suite_id}")
        data, evidence_state, relative = evidence_file(run_root, suite.get("events") if suite else None)
        evidence_rows.append({"role": f"{suite_id} 逐步原件", "path": relative, "state": evidence_state,
                              "sha256": suite.get("events", {}).get("sha256", "") if suite and isinstance(suite.get("events"), dict) else "",
                              "absolute_path": str(run_root / relative) if data is not None else ""})
        events_index = len(evidence_rows) - 1
        if suite:
            for role in ("playwright_json", "trace", "traces", "screenshots", "service_audit", "database_summary", "fixture_manifest", "sql"):
                items = suite.get(role)
                items = items if isinstance(items, list) else [items]
                for item in items:
                    if item is None:
                        continue
                    content, status, artifact = evidence_file(run_root, item)
                    if role == "screenshots" and content is not None and not valid_png(content):
                        content, status = None, "不是有效 PNG"
                    evidence_rows.append({"role": f"{suite_id} {role}", "path": artifact, "state": status,
                                          "sha256": item.get("sha256", "") if isinstance(item, dict) else "",
                                          "absolute_path": str(run_root / artifact) if content is not None else ""})
        event_count = 0
        if data is not None:
            try:
                lines = [(number, json.loads(line)) for number, line in enumerate(data.decode("utf-8").splitlines(), 1) if line.strip()]
            except (UnicodeError, ValueError):
                evidence_state = "JSONL 无法解析"
                lines = []
            for number, event in lines:
                if not isinstance(event, dict) or event.get("run_id") != report["run_id"] or event.get("case_id") != suite_id:
                    evidence_state = "运行身份不符"
                    lines = []
                    break
            for number, event in lines:
                event_count += 1
                tc_id = event.get("tc_id")
                if tc_id is None:
                    continue  # Legacy aggregate assertion; never inherited by a TC.
                if tc_id not in case_ids:
                    continue
                step = event.get("tc_step")
                if type(step) is not int or step < 1:
                    issues[tc_id].append(f"{relative}:{number} 缺有效 TC 步骤编号")
                    continue
                event["_source"] = f"{relative}:{number} (SHA-256 {sha(data)[:12]})"
                observations[tc_id].append(event)
        suite_rows.append({"id": suite_id, "state": raw_state, "reason": "\n".join(suite.get("failures", [])) if suite else "本次未执行",
                           "started": suite.get("started_at", "") if suite else "",
                           "finished": suite.get("finished_at", "") if suite else "",
                           "cleanup": suite.get("cleanup_completed") if suite else None,
                           "events": relative, "evidence_state": evidence_state, "event_count": event_count})
        evidence_rows[events_index]["state"] = evidence_state
    return observations, issues, suite_rows, evidence_rows


def evaluate_tc_record(case: dict, record: dict | None, run_root: Path, run_id: str,
                       identity: str | None = None):
    """Accept TC PASS only from this run's complete step and artifact records."""
    identity = identity or case["id"]
    baseline = case.get("steps") or []
    if record is None:
        reason = ("用例预期仍待基线确认；" + "；".join(case.get("missing", []))
                  if case.get("design_status") != "designed"
                  else "本次运行没有按 TC ID 记录独立执行与逐步证据")
        steps = [{"tc_id": identity, "step": step.get("step"), "action": step.get("action", ""),
                  "expected_ui": step.get("expected_ui", ""), "expected_db": step.get("expected_api_db", ""),
                  "expected": step.get("expected", ""), "runtime_action": "", "runtime_expected": "",
                  "actual": "", "state": "BLOCKED", "evidence": ""}
                 for step in baseline]
        return "BLOCKED", reason, steps, "", [], ""
    raw_steps = record.get("step_results") if isinstance(record, dict) else None
    raw_steps = raw_steps if isinstance(raw_steps, list) else []
    evidence = record.get("evidence") if isinstance(record, dict) else None
    evidence = evidence if isinstance(evidence, dict) else {}
    problems = []
    evidence_rows = []
    verified_paths = []
    verified_data = {}
    event_bytes = None
    event_path = ""
    if case["id"].startswith(("TC-TM001-CATALOG-", "TC-TM001-RECORDS-", "TC-TM001-GATE-")):
        required = ("events", "command_log")
        required_source = "command"
    elif case["id"].startswith("TC-TM001-UI-"):
        required = ("events", "trace", "screenshots")
        required_source = "ui"
    else:
        required = ("events", "trace", "screenshots", "database_before", "database_after", "service_audit")
        required_source = "ui"
    for role in (*required, *(name for name in evidence if name not in required)):
        items = evidence.get(role)
        items = items if isinstance(items, list) else [items]
        if (not items or any(item is None for item in items)) and record.get("state") != "BLOCKED":
            problems.append(f"缺少 {role} 原始证据")
        for item in items:
            if item is None:
                continue
            data, status, relative = evidence_file(run_root, item)
            if role == "screenshots" and data is not None and not valid_png(data):
                data, status = None, "不是有效 PNG"
            evidence_rows.append({"role": f"{identity} {role}", "path": relative, "state": status,
                                  "sha256": item.get("sha256", "") if isinstance(item, dict) else "",
                                  "absolute_path": str(run_root / relative) if data is not None else ""})
            if status != "已核对":
                problems.append(f"{role} {status}")
            else:
                verified_paths.append(f"{relative} (SHA-256 {sha(data)[:12]})")
                verified_data.setdefault(role, data)
                if role == "events":
                    event_bytes, event_path = data, relative
    if event_bytes is None and record is not None:
        problems.append("缺少可核对的逐 TC 事件")
    event_steps = {}
    if event_bytes is not None:
        try:
            for line_no, line in enumerate(event_bytes.decode("utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                event = json.loads(line)
                number = event.get("step") if isinstance(event, dict) else None
                if (not isinstance(event, dict) or event.get("run_id") != run_id
                        or event.get("case_id") != identity or type(number) is not int
                        or number in event_steps):
                    problems.append(f"{event_path}:{line_no} 逐 TC 事件身份或步骤不一致")
                    continue
                event_steps[number] = (event, line_no)
        except (UnicodeError, ValueError):
            problems.append("逐 TC 事件 JSONL 无法解析")
            event_steps = {}
    indexed = {}
    for item in raw_steps:
        number = item.get("step") if isinstance(item, dict) else None
        if type(number) is not int or number in indexed:
            problems.append("逐 TC 步骤缺编号或重复")
        else:
            indexed[number] = item
    planned_numbers = {step.get("step") for step in baseline}
    if set(indexed) - planned_numbers or set(event_steps) - planned_numbers:
        problems.append("原始记录包含未设计的步骤")
    step_rows = []
    observed_failure = False
    ui_seen = False
    for planned in baseline:
        number = planned.get("step")
        item = indexed.get(number)
        event_pair = event_steps.get(number)
        step_state = "BLOCKED"
        actual = ""
        runtime_action = ""
        runtime_expected = ""
        source = ""
        if item is not None:
            actual = _short(item.get("actual", ""))
            runtime_action = _short(item.get("action", ""))
            runtime_expected = _short(item.get("expected", ""))
            if (not isinstance(item.get("action"), str) or not item["action"].strip()
                    or "expected" not in item or item.get("expected") in (None, "")
                    or "actual" not in item or type(item.get("passed")) is not bool):
                problems.append(f"第{number}步缺实际动作、断言预期、实测或判定")
            elif event_pair is None:
                problems.append(f"第{number}步缺逐 TC 原始事件")
            else:
                event, line_no = event_pair
                source = f"{event_path}:{line_no} (SHA-256 {sha(event_bytes)[:12]})"
                for key in ("action", "expected", "actual", "passed", "timestamp", "source"):
                    if event.get(key) != item.get(key):
                        problems.append(f"第{number}步结果与原始事件的 {key} 不一致")
                if item.get("source") == required_source:
                    ui_seen = True
                if type(item.get("passed")) is bool:
                    step_state = "PASS" if item["passed"] else "FAIL"
                    observed_failure |= step_state == "FAIL"
        elif event_pair is not None:
            problems.append(f"第{number}步只有事件，没有结果记录")
        step_rows.append({"tc_id": identity, "step": number, "action": planned.get("action", ""),
                          "expected_ui": planned.get("expected_ui", ""), "expected_db": planned.get("expected_api_db", ""),
                          "expected": planned.get("expected", ""), "runtime_action": runtime_action,
                          "runtime_expected": runtime_expected, "actual": actual,
                          "state": step_state, "evidence": source})
    claim = record.get("state") if isinstance(record, dict) else None
    if record.get("case_id") != identity:
        problems.append("逐 TC 身份与本次记录不一致")
    if case.get("design_status") != "designed":
        result = "BLOCKED"
        reason = "用例预期仍待基线确认；" + "；".join(case.get("missing", []))
    elif record is None:
        result = "BLOCKED"
        reason = "本次运行没有按 TC ID 记录独立执行与逐步证据"
    elif claim not in STATES:
        result = "BLOCKED"
        reason = "逐 TC 原始结果没有有效 PASS、FAIL 或 BLOCKED 状态"
    elif claim == "BLOCKED":
        result = "BLOCKED"
        reason = record.get("reason") or "原始运行标记本例 BLOCKED，未提供原因"
    elif claim == "FAIL":
        result = "FAIL"
        reason = record.get("reason") or ("原始步骤断言失败" if observed_failure else "原始运行标记本例 FAIL")
        if problems:
            reason += "；证据缺口：" + "；".join(dict.fromkeys(problems))
    elif problems:
        result = "BLOCKED"
        reason = "原始结果标记 PASS，但证据缺口：" + "；".join(dict.fromkeys(problems))
    elif not baseline or set(indexed) != planned_numbers or set(event_steps) != planned_numbers:
        result = "BLOCKED"
        reason = "原始结果标记 PASS，但没有覆盖全部已设计步骤"
    elif observed_failure:
        result = "FAIL"
        reason = "原始结果标记 PASS，但逐步原始断言失败"
    elif not ui_seen:
        proof_gap = (playwright_ui_proof(identity, verified_data.get("playwright"), verified_data.get("trace"))
                     if required_source == "ui" else f"缺少 {required_source} 来源的观察")
        result = "BLOCKED" if proof_gap else "PASS"
        reason = ("原始结果标记 PASS，但" + proof_gap) if proof_gap else "逐步原件与 Playwright UI 动作 trace 均已核对"
    else:
        result = "PASS"
        reason = "本次逐 TC 步骤和原始证据完整"
    return result, reason, step_rows, "\n".join(verified_paths), evidence_rows, claim or ""


def build_model(catalog: dict, report: dict, *, run_root: Path, checks: dict | None = None,
                aggregate_report: dict | None = None, aggregate_root: Path | None = None,
                auxiliary_report: dict | None = None, auxiliary_root: Path | None = None,
                audit_report: dict | None = None, audit_root: Path | None = None,
                variants: dict | None = None, source_hashes: dict | None = None,
                source_files: list[dict] | None = None) -> dict:
    run_id = report.get("run_id")
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id) or report.get("state") not in STATES:
        raise Invalid("Product report lacks a safe run ID or actual state")
    if catalog.get("release_id") != report.get("release_id") or not isinstance(catalog.get("cases"), list):
        raise Invalid("Test catalog release differs from this run")
    all_cases = catalog["cases"]
    ids = [case.get("id") for case in all_cases if isinstance(case, dict)]
    if len(ids) != len(all_cases) or len(ids) != len(set(ids)):
        raise Invalid("Test catalog contains malformed or repeated case IDs")
    all_current = [case for case in all_cases if case.get("feature_id") == "TM-001"]
    future = [case for case in all_cases if case.get("feature_id") != "TM-001"]
    if not all_current:
        raise Invalid("No TM-001 detailed cases in the catalog")
    source_releases = [case.get("release_id", catalog["release_id"]) for case in all_current]
    if (any(not isinstance(value, str) or not value for value in source_releases)
            or len(set(source_releases)) != 1):
        raise Invalid("TM-001 parent cases have mixed or invalid source releases")
    source_release = source_releases[0]
    current_map = {case["id"]: case for case in all_current}
    variant_list = variants.get("variants", []) if variants is not None else []
    if variants is not None and (not isinstance(variant_list, list)
            or (variant_list and variants.get("release_id") != source_release)
            or (not variant_list and variants.get("release_id") not in (source_release, report["release_id"]))):
        raise Invalid("Variant source release or shape differs from TM-001 parent cases")
    variant_map = {}
    variants_by_parent = defaultdict(list)
    for variant in variant_list:
        if (not isinstance(variant, dict) or not isinstance(variant.get("id"), str)
                or variant.get("id") in variant_map or variant.get("parent_id") not in current_map
                or not variant["id"].startswith(variant["parent_id"] + "#")):
            raise Invalid("Variant ID is foreign, duplicated or not bound to a TM-001 parent")
        variant_map[variant["id"]] = variant
        variants_by_parent[variant["parent_id"]].append(variant)
        planned = [step["step"] for step in current_map[variant["parent_id"]].get("steps", [])]
        selected = variant.get("step_numbers", planned)
        if (not isinstance(selected, list) or not selected or any(type(number) is not int for number in selected)
                or selected != sorted(set(selected)) or not set(selected) <= set(planned)):
            raise Invalid(f"Variant {variant['id']} has invalid step_numbers")
    targeted = report.get("scope") in ("granular_targeted_probe", "granular_auxiliary_targeted_probe")
    expected_tc = report.get("expected_cases")
    if targeted:
        if (not isinstance(expected_tc, list) or not expected_tc
                or any(not isinstance(identity, str) for identity in expected_tc)
                or len(expected_tc) != len(set(expected_tc))
                or not set(expected_tc) <= (set(current_map) | set(variant_map))):
            raise Invalid("Targeted report has no valid expected TC/variant set")
        selected_parents = {identity if identity in current_map else variant_map[identity]["parent_id"]
                            for identity in expected_tc}
        current = [case for case in all_current if case["id"] in selected_parents]
        out_of_scope = [case for case in all_current if case["id"] not in selected_parents]
    else:
        current = all_current
        out_of_scope = []
    aggregate = aggregate_report or (report if report.get("suites") else None)
    aggregate_root = aggregate_root or run_root
    if aggregate is not None and aggregate.get("suites"):
        _, _, suite_rows, evidence_rows = load_suite_events(aggregate, aggregate_root, {case["id"] for case in current})
    else:
        suite_rows, evidence_rows = [], []
    main_code_evidence, main_verified_code = code_snapshot(report, run_root, "逐 TC 固定测试代码")
    evidence_rows.extend(main_code_evidence)
    raw_tc = report.get("tc_results") or []
    if not isinstance(raw_tc, list):
        raise Invalid("tc_results must be a list when supplied")
    if raw_tc and (not isinstance(expected_tc, list) or len(expected_tc) != len(set(expected_tc))):
        raise Invalid("Detailed run has no unique expected TC set")
    tc_map = {}
    for item in raw_tc:
        if (not isinstance(item, dict) or item.get("case_id") not in (set(current_map) | set(variant_map))
                or item["case_id"] not in expected_tc or item["case_id"] in tc_map):
            raise Invalid("Detailed TC result is foreign or duplicated")
        tc_map[item["case_id"]] = item
    aux_ids = {identity for identity in current_map if identity.startswith(AUX_PREFIXES)}
    if len(aux_ids) != 11:
        raise Invalid("TM-001 auxiliary TC catalog must have exactly 11 cases")
    auxiliary_rows = []
    auxiliary_steps = []
    auxiliary_evidence = []
    auxiliary_map = {}
    aux_bound, aux_binding_reason = False, "未提供辅助批次原件"
    if auxiliary_report is not None:
        auxiliary_root = auxiliary_root or run_root
        aux_code_evidence, aux_verified_code = code_snapshot(auxiliary_report, auxiliary_root, "辅助固定测试代码")
        auxiliary_evidence.extend(aux_code_evidence)
        aux_bound, aux_binding_reason = auxiliary_binding(report, auxiliary_report, aux_ids)
        raw_aux = auxiliary_report.get("tc_results")
        if not isinstance(raw_aux, list):
            raise Invalid("Auxiliary report tc_results must be a list")
        for item in raw_aux:
            if (not isinstance(item, dict) or item.get("case_id") not in aux_ids
                    or item["case_id"] in auxiliary_map):
                raise Invalid("Auxiliary TC result is foreign or duplicated")
            auxiliary_map[item["case_id"]] = item
        for identity in sorted(aux_ids):
            value, detail, steps, evidence, tc_evidence, claim = evaluate_tc_record(
                current_map[identity], auxiliary_map.get(identity), auxiliary_root,
                auxiliary_report.get("run_id", ""))
            code, command = replay_binding(identity, auxiliary_report, auxiliary_root)
            if (value in ("PASS", "FAIL") and auxiliary_report.get("schema_version", 0) >= 3
                    and not bound_code_verified(code, aux_verified_code)):
                value, detail = "BLOCKED", "辅助用例固定测试代码没有本次 SHA-256 原件"
            auxiliary_rows.append({"id": identity, "run_id": auxiliary_report.get("run_id", ""),
                                   "reported_state": claim, "state": value,
                                   "binding": "已核对" if aux_bound else "未绑定主批次",
                                   "binding_reason": aux_binding_reason, "reason": detail, "evidence": evidence,
                                   "binding_code": code, "replay_command": command})
            auxiliary_steps.extend({**step, "run_id": auxiliary_report.get("run_id", "")} for step in steps)
            auxiliary_evidence.extend(tc_evidence)
    case_rows = []
    step_rows = []
    variant_rows = []
    for case in current:
        all_declared = variants_by_parent.get(case["id"], [])
        declared = ([variant for variant in all_declared if variant["id"] in expected_tc]
                    if targeted else all_declared)
        if declared:
            states = []
            evidence_parts = []
            covered_steps = set()
            for variant in declared:
                selected = variant.get("step_numbers", [step["step"] for step in case.get("steps", [])])
                covered_steps.update(selected)
                variant_case = {**case, "steps": [step for step in case.get("steps", []) if step["step"] in selected]}
                value, detail, steps, evidence, tc_evidence, claim = evaluate_tc_record(
                    variant_case, tc_map.get(variant["id"]), run_root, run_id, variant["id"])
                code, command = replay_binding(variant["id"], report, run_root)
                if (value == "PASS" and report.get("schema_version", 0) >= 3
                        and not bound_code_verified(code, main_verified_code)):
                    value, detail = "BLOCKED", "固定测试代码没有本次 SHA-256 原件"
                states.append((variant["id"], value, detail))
                evidence_parts.append(evidence)
                step_rows.extend({**step, "run_id": run_id} for step in steps)
                evidence_rows.extend(tc_evidence)
                variant_rows.append({"id": variant["id"], "parent_id": case["id"],
                                     "input": variant.get("input_ref", ""), "expected": variant.get("expected_ref", ""),
                                     "fixture": variant.get("fixture_kind", ""), "steps": ", ".join(map(str, selected)),
                                     "reported_state": claim,
                                     "state": value, "reason": detail, "evidence": evidence,
                                     "binding_code": code, "replay_command": command})
            parent_record = tc_map.get(case["id"])
            claim = parent_record.get("state", "") if parent_record else ""
            failures = [variant_id for variant_id, state, _ in states if state == "FAIL"]
            blocked = [variant_id for variant_id, state, _ in states if state == "BLOCKED"]
            if case.get("design_status") != "designed":
                result, reason = "BLOCKED", "父用例预期仍待基线确认"
            elif failures:
                result, reason = "FAIL", "变体失败：" + ", ".join(failures)
            elif claim == "FAIL":
                result, reason = "FAIL", parent_record.get("reason") or "父用例原始结果为 FAIL"
            elif claim == "BLOCKED":
                result, reason = "BLOCKED", parent_record.get("reason") or "父用例原始结果为 BLOCKED"
            elif targeted and len(declared) != len(all_declared):
                result, reason = "BLOCKED", "目标运行未覆盖父用例全部声明变体"
            elif blocked:
                result, reason = "BLOCKED", "变体缺少完整 PASS：" + ", ".join(blocked)
            elif covered_steps != {step["step"] for step in case.get("steps", [])}:
                result, reason = "BLOCKED", "声明变体没有覆盖父用例全部设计步骤"
            elif claim != "PASS":
                result, reason = "BLOCKED", "缺少本次父用例 PASS 汇总记录"
            else:
                result, reason = "PASS", f"{len(declared)} 个声明变体各自完整 PASS，父用例本次汇总 PASS"
            evidence = "\n".join(part for part in evidence_parts if part)
        else:
            result, reason, steps, evidence, tc_evidence, claim = evaluate_tc_record(case, tc_map.get(case["id"]), run_root, run_id)
            code, _ = replay_binding(case["id"], report, run_root)
            if (result == "PASS" and report.get("schema_version", 0) >= 3
                    and not bound_code_verified(code, main_verified_code)):
                result, reason = "BLOCKED", "固定测试代码没有本次 SHA-256 原件"
            step_rows.extend({**step, "run_id": run_id} for step in steps)
            evidence_rows.extend(tc_evidence)
        result_run_id = run_id
        auxiliary_state = ""
        if case["id"] in aux_ids and auxiliary_report is not None:
            aux_row = next(row for row in auxiliary_rows if row["id"] == case["id"])
            auxiliary_state = aux_row["state"]
            if result == "BLOCKED" and aux_bound:
                result = aux_row["state"]
                reason = (f"辅助批次 {aux_row['run_id']} 的逐例步骤、证据和同候选绑定均已核对"
                          if result == "PASS" else f"辅助批次 {aux_row['run_id']}：{aux_row['reason']}")
                evidence = aux_row["evidence"]
                result_run_id = aux_row["run_id"]
        db = case.get("db_operations") or {}
        binding_report, binding_root = (auxiliary_report, auxiliary_root) if result_run_id != run_id else (report, run_root)
        binding_code, replay_command = replay_binding(case["id"], binding_report, binding_root)
        case_rows.append({"id": case["id"], "title": case.get("title", ""), "tasks": ", ".join(case.get("task_ids", [])),
                          "ac": ", ".join(case.get("ac_ids", [])), "type": case.get("type", ""),
                          "design": case.get("design_status", ""), "reported_state": claim,
                          "state": result, "reason": reason,
                          "result_run_id": result_run_id, "auxiliary_state": auxiliary_state,
                          "binding_code": binding_code, "replay_command": replay_command,
                          "input": case.get("input", ""), "preconditions": case.get("preconditions", ""),
                          "expected": case.get("overall_expected", "") or "\n".join(step.get("expected", "") for step in case.get("steps", [])),
                          "db_prepare": db.get("prepare", ""), "db_changes": db.get("expected_changes", ""),
                          "db_verify": db.get("verification", ""), "reset": db.get("reset", case.get("reset", "")),
                          "evidence": evidence, "source": case.get("source", {}).get("path", "")})
    audit_rows = []
    if audit_report is not None:
        audit_rows, audit_evidence = audit_findings(report, audit_report, run_root, audit_root or run_root)
        evidence_rows.extend(audit_evidence)
        audited = {item["id"]: item for item in audit_rows}
        for row in case_rows:
            finding = audited.get(row["id"])
            row["audit_claim"] = finding["audit_claim"] if finding else ""
            row["audit_state"] = finding["state"] if finding else ""
            row["audit_reason"] = finding["reason"] if finding else ""
            if finding and row["state"] == "PASS" and finding["state"] in ("FAIL", "BLOCKED"):
                row["state"] = finding["state"]
                row["reason"] += "；独立复核降级：" + finding["reason"]
    else:
        for row in case_rows:
            row["audit_claim"] = row["audit_state"] = row["audit_reason"] = ""
    check_rows = []
    if checks is not None:
        if checks.get("run_id") != run_id or not isinstance(checks.get("checks"), list):
            raise Invalid("Basic check results do not belong to this run")
        seen = set()
        for item in checks["checks"]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in seen or item.get("state") not in STATES:
                raise Invalid("Basic check ID or state is missing, invalid or duplicated")
            seen.add(item["id"])
            for field in ("passed", "total", "exit_code"):
                value = item.get(field)
                if value is not None and type(value) is not int:
                    raise Invalid(f"Basic check {field} must be an integer or missing")
            row = {key: item.get(key) for key in ("id", "command", "scope", "state", "passed", "total", "exit_code", "evidence", "note")}
            if isinstance(row["evidence"], str) and row["evidence"]:
                source = Path(row["evidence"])
                source = source if source.is_absolute() else ROOT / source
                row["evidence"] = display_path(source, run_root)
                try:
                    content = read_file(source)
                except (OSError, Invalid):
                    evidence_rows.append({"role": f"基础检查 {row['id']}", "path": row["evidence"],
                                          "state": "文件缺失或路径不安全", "sha256": "", "absolute_path": ""})
                else:
                    evidence_rows.append({"role": f"基础检查 {row['id']}", "path": row["evidence"],
                                          "state": "已读取", "sha256": sha(content), "absolute_path": str(source)})
            check_rows.append(row)
    counts = Counter(row["state"] for row in case_rows)
    product_counts = Counter(row["state"] for row in case_rows if row["id"] not in aux_ids)
    auxiliary_counts = Counter(row["state"] for row in case_rows if row["id"] in aux_ids)
    variant_counts = Counter(row["state"] for row in variant_rows)
    evidence_rows.extend(auxiliary_evidence)
    step_rows.extend(auxiliary_steps)
    model = {"schema_version": 1, "run_id": run_id, "release_id": report["release_id"], "product_state": report["state"],
             "scope": report.get("scope", ""), "candidate_sha": report.get("source_commit", ""),
             "parent_run_id": report.get("parent_run_id", ""),
             "parent_report_sha256": report.get("parent_report_sha256", ""),
             "started_at": report.get("started_at", ""), "finished_at": report.get("finished_at", ""),
             "release_eligible_claim": report.get("release_eligible") is True,
             "package_dmg_sha256": (report.get("package") or {}).get("dmg_sha256", ""),
             "aggregate_run_id": aggregate.get("run_id", "") if aggregate else "",
             "aggregate_product_state": aggregate.get("state", "") if aggregate else "",
             "aggregate_candidate_sha": aggregate.get("source_commit", "") if aggregate else "",
             "aggregate_dmg_sha256": (aggregate.get("package") or {}).get("dmg_sha256", "") if aggregate else "",
             "auxiliary_run_id": auxiliary_report.get("run_id", "") if auxiliary_report else "",
             "auxiliary_product_state": auxiliary_report.get("state", "") if auxiliary_report else "",
             "auxiliary_bound": aux_bound, "auxiliary_binding_reason": aux_binding_reason,
             "auxiliary_started_at": auxiliary_report.get("started_at", "") if auxiliary_report else "",
             "auxiliary_finished_at": auxiliary_report.get("finished_at", "") if auxiliary_report else "",
             "audit_state": audit_report.get("state", "") if audit_report else "",
             "audit_run_id": audit_report.get("run_id", "") if audit_report else "",
             "tc_counts": {state: counts[state] for state in ("PASS", "FAIL", "BLOCKED")},
             "product_tc_counts": {state: product_counts[state] for state in ("PASS", "FAIL", "BLOCKED")},
             "auxiliary_tc_counts": {state: auxiliary_counts[state] for state in ("PASS", "FAIL", "BLOCKED")},
             "variant_counts": {state: variant_counts[state] for state in ("PASS", "FAIL", "BLOCKED")},
             "suite_counts": dict(Counter(row["state"] for row in suite_rows)),
             "cases": case_rows, "variants": variant_rows, "steps": step_rows, "suites": suite_rows, "checks": check_rows,
             "auxiliary": auxiliary_rows,
             "audit": audit_rows,
             "future": [{"id": case["id"], "feature": case.get("feature_id", ""), "title": case.get("title", ""),
                         "design": case.get("design_status", ""), "state": "不适用（未来功能）"} for case in future],
             "out_of_scope": [{"id": case["id"], "title": case.get("title", ""),
                               "state": "本次定向运行未执行"} for case in out_of_scope],
             "evidence": evidence_rows, "source_hashes": source_hashes or {}, "source_files": source_files or []}
    return model


def frozen_input(report: dict, run_root: Path, relative: str, override: Path | None) -> Path | None:
    """Choose this run's SHA-verified catalog/variant source, never a moving checkout."""
    descriptors = [item for item in report.get("test_code_snapshot", [])
                   if isinstance(item, dict) and item.get("path") == "test-code/" + relative]
    expected = report.get("test_inputs_sha256")
    if report.get("scope") == "granular_auxiliary_targeted_probe":
        expected = {"tests/test_cases.json": report.get("catalog_sha256"),
                    "tests/granular_login_variants.json": report.get("login_variants_sha256"),
                    "tests/granular_update_variants.json": report.get("update_variants_sha256")}
    if report.get("schema_version", 0) >= 3 and (len(descriptors) != 1 or not isinstance(expected, dict)):
        raise Invalid(f"This run has no frozen source input: {relative}")
    if descriptors:
        data, status, _ = evidence_file(run_root, descriptors[0])
        if status != "已核对" or expected.get(relative) != sha(data):
            raise Invalid(f"This run's frozen source input is missing or changed: {relative}")
        frozen = run_root / descriptors[0]["path"]
        if override is not None and sha(read_file(override)) != sha(data):
            raise Invalid(f"Explicit {relative} differs from this run's frozen source")
        return frozen
    if override is not None:
        return safe_path(override)
    default = ROOT / relative
    return default if default.is_file() else None


def export(report_path: Path, output_dir: Path, checks_path: Path | None = None,
           catalog_path: Path | None = None,
           aggregate_path: Path | None = None,
           variants_path: Path | None = None,
           auxiliary_path: Path | None = None,
           update_variants_path: Path | None = None,
           audit_path: Path | None = None,
           parent_path: Path | None = None) -> dict:
    report_path = safe_path(report_path)
    output_dir = safe_path(output_dir)
    if report_path.name != "result.json" or output_dir == report_path.parent or output_dir in report_path.parents:
        raise Invalid("Use an original result.json and a separate output directory")
    report, report_bytes = read_json(report_path)
    catalog_path = frozen_input(report, report_path.parent, "tests/test_cases.json", catalog_path)
    variants_path = frozen_input(report, report_path.parent, "tests/granular_login_variants.json", variants_path)
    update_variants_path = frozen_input(report, report_path.parent, "tests/granular_update_variants.json", update_variants_path)
    if catalog_path is None or variants_path is None:
        raise Invalid("Catalog or login variant manifest is unavailable")
    catalog, catalog_bytes = read_json(catalog_path)
    variants, variants_bytes = read_json(variants_path)
    if not isinstance(variants.get("variants"), list):
        raise Invalid("Login variant manifest has no variants list")
    update_variants = None
    update_variants_bytes = None
    if update_variants_path is not None:
        update_variants_path = safe_path(update_variants_path)
        if update_variants_path == variants_path:
            raise Invalid("Login and update variant manifests must be separate files")
        update_variants, update_variants_bytes = read_json(update_variants_path)
        if (update_variants.get("release_id") != variants.get("release_id")
                or not isinstance(update_variants.get("variants"), list)):
            raise Invalid("Update variant manifest differs from the login source release")
        variants = {**variants, "variants": [*variants.get("variants", []), *update_variants["variants"]]}
    checks = None
    source_hashes = {display_path(report_path): sha(report_bytes), display_path(catalog_path): sha(catalog_bytes),
                     display_path(variants_path): sha(variants_bytes)}
    source_files = [{"role": "逐 TC 主原件", "path": display_path(report_path), "sha256": sha(report_bytes),
                     "absolute_path": str(report_path)},
                    {"role": "用例目录", "path": display_path(catalog_path), "sha256": sha(catalog_bytes),
                     "absolute_path": str(catalog_path)},
                    {"role": "参数变体目录", "path": display_path(variants_path), "sha256": sha(variants_bytes),
                     "absolute_path": str(variants_path)}]
    if update_variants_path is not None:
        source_hashes[display_path(update_variants_path)] = sha(update_variants_bytes)
        source_files.append({"role": "更新参数变体目录", "path": display_path(update_variants_path),
                             "sha256": sha(update_variants_bytes), "absolute_path": str(update_variants_path)})
    parent_bytes = None
    if report.get("scope") == "granular_auxiliary_targeted_probe":
        if parent_path is None:
            raise Invalid("Auxiliary single-TC workbook requires --parent-report")
        parent_path = safe_path(parent_path)
        if parent_path.name != "result.json" or parent_path == report_path:
            raise Invalid("Auxiliary parent must be a separate original result.json")
        parent, parent_bytes = read_json(parent_path)
        if (report.get("parent_run_id") != parent.get("run_id")
                or report.get("parent_report_sha256") != sha(parent_bytes)
                or any(report.get(key) != parent.get(key) for key in ("release_id", "source_commit", "candidate_tree"))
                or (report.get("package") or {}).get("dmg_sha256") != (parent.get("package") or {}).get("dmg_sha256")
                or any(report.get(key) != (parent.get("test_inputs_sha256") or {}).get(relative)
                       for key, relative in (("catalog_sha256", "tests/test_cases.json"),
                                             ("login_variants_sha256", "tests/granular_login_variants.json"),
                                             ("update_variants_sha256", "tests/granular_update_variants.json")))
                or timestamp(parent.get("finished_at")) is None
                or timestamp(report.get("started_at")) is None
                or timestamp(parent["finished_at"]) > timestamp(report["started_at"])):
            raise Invalid("Auxiliary single-TC run is not bound to the parent report and DMG")
        source_hashes["parent/" + display_path(parent_path)] = sha(parent_bytes)
        source_files.append({"role": "父产品批次原件", "path": display_path(parent_path),
                             "sha256": sha(parent_bytes), "absolute_path": str(parent_path)})
    elif parent_path is not None:
        raise Invalid("--parent-report applies only to an auxiliary single-TC run")
    aggregate = None
    aggregate_bytes = None
    if aggregate_path is not None:
        aggregate_path = safe_path(aggregate_path)
        if aggregate_path == report_path or aggregate_path.name != "result.json":
            raise Invalid("Aggregate report must be a separate original result.json")
        aggregate, aggregate_bytes = read_json(aggregate_path)
        if aggregate.get("run_id") == report.get("run_id") or aggregate.get("release_id") != report.get("release_id"):
            raise Invalid("Aggregate report must be a different run of the same release")
        source_hashes["aggregate/" + display_path(aggregate_path)] = sha(aggregate_bytes)
        source_files.append({"role": "六组聚合原件", "path": display_path(aggregate_path),
                             "sha256": sha(aggregate_bytes),
                             "absolute_path": str(aggregate_path)})
    auxiliary = None
    auxiliary_bytes = None
    if auxiliary_path is not None:
        auxiliary_path = safe_path(auxiliary_path)
        if auxiliary_path in (report_path, aggregate_path) or auxiliary_path.name != "result.json":
            raise Invalid("Auxiliary report must be a separate original result.json")
        auxiliary, auxiliary_bytes = read_json(auxiliary_path)
        source_hashes["auxiliary/" + display_path(auxiliary_path)] = sha(auxiliary_bytes)
        source_files.append({"role": "辅助 11 TC 原件", "path": display_path(auxiliary_path),
                             "sha256": sha(auxiliary_bytes),
                             "absolute_path": str(auxiliary_path)})
    audit = None
    audit_bytes = None
    if audit_path is not None:
        audit_path = safe_path(audit_path)
        if audit_path in (report_path, aggregate_path, auxiliary_path):
            raise Invalid("Supplemental audit must be a separate original JSON file")
        audit, audit_bytes = read_json(audit_path)
        if audit.get("source_report_sha256") != sha(report_bytes):
            raise Invalid("Supplemental audit is bound to a different original report SHA-256")
        source_hashes["audit/" + display_path(audit_path)] = sha(audit_bytes)
        source_files.append({"role": "独立复核原件", "path": display_path(audit_path),
                             "sha256": sha(audit_bytes), "absolute_path": str(audit_path)})
    if checks_path is not None:
        checks_path = safe_path(checks_path)
        checks, checks_bytes = read_json(checks_path)
        source_hashes[display_path(checks_path)] = sha(checks_bytes)
        source_files.append({"role": "基础检查原件", "path": display_path(checks_path),
                             "sha256": sha(checks_bytes),
                             "absolute_path": str(checks_path)})
    raw_model = build_model(catalog, report, run_root=report_path.parent, checks=checks,
                            aggregate_report=aggregate, aggregate_root=aggregate_path.parent if aggregate_path else None,
                            auxiliary_report=auxiliary, auxiliary_root=auxiliary_path.parent if auxiliary_path else None,
                            audit_report=audit, audit_root=audit_path.parent if audit_path else None,
                            variants=variants, source_hashes=source_hashes, source_files=source_files)
    if output_dir.exists():
        return verify_existing_export(output_dir, copy_verified_evidence(raw_model, output_dir, reuse=True))
    node = Path(os.environ.get("TOKENMETER_WORKBOOK_NODE", str(NODE))).expanduser()
    if not node.is_absolute() or not node.is_file() or not os.access(node, os.X_OK):
        raise Blocked("Bundled Node runtime is unavailable")
    if not (ROOT / ".local/workbook/node_modules").is_symlink():
        raise Blocked("Prepare .local/workbook/node_modules using load_workspace_dependencies")
    output_dir.mkdir(parents=True, mode=0o700)
    os.chmod(output_dir, 0o700)
    model = copy_verified_evidence(raw_model, output_dir)
    model_path = output_dir / "granular-source.json"
    with model_path.open("x", encoding="utf-8") as stream:
        json.dump(model, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    os.chmod(model_path, 0o600)
    command = [str(node), str(ROOT / "scripts/export_granular_test_result.mjs"), "--model", str(model_path), "--output", str(output_dir)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False, timeout=240)
    if result.returncode:
        raise Invalid(f"Granular workbook export failed ({result.returncode}): {(result.stderr or result.stdout)[-1800:]}")
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    workbook = output_dir / receipt["workbook"]["path"]
    data = read_file(workbook)
    if sha(data) != receipt["workbook"]["sha256"] or len(data) != receipt["workbook"]["bytes"]:
        raise Invalid("Saved workbook differs from export receipt")
    with zipfile.ZipFile(workbook) as archive:
        if archive.testzip() is not None or "xl/workbook.xml" not in archive.namelist():
            raise Invalid("Saved workbook is not a readable XLSX")
        book = archive.read("xl/workbook.xml").decode("utf-8")
        for name in ("00运行概览", "01逐例结果", "02参数变体", "03逐步记录", "04聚合场景", "05基础检查", "06未来功能", "07证据来源", "08辅助用例", "09截图预览", "10范围外用例", "11独立复核"):
            if f'name="{name}"' not in book:
                raise Invalid(f"Saved workbook lost sheet {name}")
    if read_file(report_path) != report_bytes or read_file(catalog_path) != catalog_bytes or read_file(variants_path) != variants_bytes:
        raise Invalid("Source changed during workbook export")
    if update_variants_path is not None and read_file(update_variants_path) != update_variants_bytes:
        raise Invalid("Update variant manifest changed during workbook export")
    if aggregate_path is not None and read_file(aggregate_path) != aggregate_bytes:
        raise Invalid("Aggregate report changed during workbook export")
    if auxiliary_path is not None and read_file(auxiliary_path) != auxiliary_bytes:
        raise Invalid("Auxiliary report changed during workbook export")
    if parent_path is not None and read_file(parent_path) != parent_bytes:
        raise Invalid("Parent report changed during auxiliary workbook export")
    if audit_path is not None and read_file(audit_path) != audit_bytes:
        raise Invalid("Supplemental audit changed during workbook export")
    if checks_path is not None and sha(read_file(checks_path)) != source_hashes[display_path(checks_path)]:
        raise Invalid("Basic check source changed during workbook export")
    refreshed = build_model(catalog, report, run_root=report_path.parent, checks=checks,
                            aggregate_report=aggregate, aggregate_root=aggregate_path.parent if aggregate_path else None,
                            auxiliary_report=auxiliary, auxiliary_root=auxiliary_path.parent if auxiliary_path else None,
                            audit_report=audit, audit_root=audit_path.parent if audit_path else None,
                            variants=variants, source_hashes=source_hashes, source_files=source_files)
    if refreshed != raw_model:
        raise Invalid("Original step or artifact evidence changed during workbook export")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checks", type=Path)
    parser.add_argument("--aggregate-report", type=Path)
    parser.add_argument("--aux-report", type=Path)
    parser.add_argument("--audit-report", type=Path, help="Independent read-only audit; can only lower a PASS")
    parser.add_argument("--parent-report", type=Path, help="Required for a standalone auxiliary single-TC workbook")
    parser.add_argument("--cases", type=Path, help="Explicit source must match this run's frozen catalog")
    parser.add_argument("--variants", type=Path, help="Explicit source must match this run's frozen login variants")
    parser.add_argument("--update-variants", type=Path, help="Explicit source must match this run's frozen update variants")
    args = parser.parse_args(argv)
    try:
        receipt = export(args.report, args.output, args.checks, args.cases, args.aggregate_report,
                         args.variants, args.aux_report, args.update_variants, args.audit_report,
                         args.parent_report)
        print(json.dumps(receipt, ensure_ascii=False))
        return 0
    except (Blocked, FileNotFoundError, PermissionError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"state": "BLOCKED", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except (Invalid, OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile) as error:
        print(json.dumps({"state": "FAIL", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
