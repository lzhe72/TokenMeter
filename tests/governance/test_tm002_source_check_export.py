"""Exercise the TM-002 source_check XLSX exporter with immutable synthetic evidence."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import tm002_source_check_export as bridge


ROOT = Path(__file__).resolve().parents[2]
NODE = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
PACKAGES = NODE.parent.parent / "node_modules"
EXPORTER = ROOT / "scripts/export_tm002_source_check.mjs"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(*args: str, cwd: Path) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


class SourceCheckExportTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(NODE.is_file(), "Codex bundled Node runtime is required for source_check export tests")
        self.assertTrue((PACKAGES / "@oai/artifact-tool").is_dir(),
                        "Codex bundled artifact-tool is required for source_check export tests")
        self.temporary = tempfile.TemporaryDirectory(prefix="tm002-source-export-")
        self.addCleanup(self.temporary.cleanup)
        self.repo = (Path(self.temporary.name).resolve() / "repo")
        self.repo.mkdir()
        for directory in ("scripts", "tests", ".local/workbook", "runs", "exports"):
            (self.repo / directory).mkdir(parents=True)
        shutil.copyfile(EXPORTER, self.repo / "scripts/export_tm002_source_check.mjs")
        (self.repo / ".local/workbook/node_modules").symlink_to(PACKAGES, target_is_directory=True)
        catalog = b'{"release_id":"synthetic"}\n'
        runner = b'# synthetic source check runner\n'
        fixed = b'// synthetic fixed single-test binding\n'
        harness = b'/* synthetic fixed C harness */\n'
        native = b'/* synthetic production C source */\n'
        (self.repo / "apps/desktop/tests").mkdir(parents=True)
        (self.repo / "apps/desktop/native").mkdir(parents=True)
        (self.repo / "tests/test_cases.json").write_bytes(catalog)
        (self.repo / "scripts/tm002_source_check.py").write_bytes(runner)
        (self.repo / "tests/fixed.test.ts").write_bytes(fixed)
        (self.repo / "apps/desktop/tests/tm002-limit-harness.c").write_bytes(harness)
        (self.repo / "apps/desktop/native/source-helper.c").write_bytes(native)
        run("git", "init", "-q", cwd=self.repo)
        run("git", "config", "user.name", "Export Test", cwd=self.repo)
        run("git", "config", "user.email", "export@example.invalid", cwd=self.repo)
        run("git", "add", "tests/test_cases.json", "scripts/tm002_source_check.py", "tests/fixed.test.ts",
            "apps/desktop/tests/tm002-limit-harness.c", "apps/desktop/native/source-helper.c", cwd=self.repo)
        run("git", "commit", "-qm", "synthetic frozen candidate", cwd=self.repo)
        commit = run("git", "rev-parse", "HEAD", cwd=self.repo)
        tree = run("git", "rev-parse", "HEAD^{tree}", cwd=self.repo)
        self.run_id = "synthetic-tm002-001"
        self.run_dir = self.repo / "runs" / self.run_id
        (self.run_dir / "logs").mkdir(parents=True)
        self.run_dir.chmod(0o700)
        groups = {
            "LIMIT-01": [None],
            "STORE-01": ["KEY_UNAVAILABLE", "DECRYPT_FAIL", "WRITE_FAIL_KEEP_OLD"],
            "ACCESS-06": ["PAGE_COMPLETION", "REVOKE_CURSOR", "TREE_CHANGED"],
            "SECURITY-01": ["ABSOLUTE", "FILE_URL", "DOTDOT", "TOKEN", "STALE_SELECTION",
                            "REVOKE_DURING_REFRESH", "SWITCH_DURING_REFRESH"],
            "DATA-01": [None],
            "CATALOG-01": ["VALID", "MISSING_TASK", "WRONG_RELEASE"],
            "EVIDENCE-01": ["COMPLETE", "MISSING_STEP", "MISSING_PICKER", "MISSING_CHOOSER_WITNESS",
                            "MISSING_FS", "WRONG_PACKAGE", "FAILED_CLEANUP"],
        }
        ids = ["TC-TM002-" + parent + ("#" + variant if variant else "")
               for parent, variants in groups.items() for variant in variants]
        self.assertEqual(len(ids), 25)
        marker = {"case_id": "TC-TM002-LIMIT-01", "input_sha256": sha(harness),
                  "algorithm_sha256": sha(native),
                  "stdout_lines": ["AUDIT enumerated candidate QTEuanNvbmw 1 101",
                                   "AUDIT metadata candidate QTEuanNvbmw 1 101",
                                   "PREVIEW timeout 1 1",
                                   "ITEM QTEuanNvbmw 25 1700000000 123456789 " + "a" * 64 + " -", "END"],
                  "stderr": "HARNESS clock=3 open=2 openat=0 read=0 fstat=4 dup=2 close=4 fdopendir=1 readdir=1 fstatat=1 closedir=1 unexpected=0 names=2",
                  "exit_code": 0, "scratch_removed": True}
        marker_line = "# TM002_LIMIT_ACTUAL " + json.dumps(marker, separators=(",", ":")) + "\n"
        tap = ("TAP version 13\n" + marker_line +
               "".join(f"ok {i} - Case {identity}\n" for i, identity in enumerate(ids, 1)) +
               "# tests 25\n# pass 25\n# fail 0\n# cancelled 0\n# skipped 0\n# todo 0\n").encode()
        (self.run_dir / "logs/cases.tap").write_bytes(tap)
        (self.run_dir / "logs/cases.stderr.log").write_bytes(b"")
        out = {"path": "logs/cases.tap", "sha256": sha(tap), "bytes": len(tap)}
        err = {"path": "logs/cases.stderr.log", "sha256": sha(b""), "bytes": 0}
        command = ["node", "--test", "tests/fixed.test.ts"]
        results = [{"id": identity, "parent_id": identity.split("#")[0],
                    "test_state": "PASS", "state": "PASS", "reason": "Exact synthetic TAP line and step evidence",
                    "input": "Synthetic owned input", "expected": "Fixed assertion succeeds",
                    "actual_assertions": ["Observed exact TAP success"],
                    "steps": [{"number": 1, "action": "Run fixed assertion", "expected": "Pass",
                               "actual": "Exact TAP line passed", "state": "PASS", "evidence": "logs/cases.tap"}],
                    "binding": {"file": "tests/fixed.test.ts", "test_name": f"Case {identity}",
                                "code_sha256": sha(fixed), "command": command},
                    "logs": [out, err], "data_reset": "Owned synthetic root removed",
                    "cleanup": {"mode": "owned_root", "state": "PASS", "evidence": "logs/cases.tap: cleanup witness"}}
                   for identity in ids]
        results[0]["binding"]["sources"] = [
            {"file": "apps/desktop/tests/tm002-limit-harness.c", "sha256": sha(harness)},
            {"file": "apps/desktop/native/source-helper.c", "sha256": sha(native)},
        ]
        results[0]["steps"].extend([
            {"number": 2, "action": "Observe timeout", "expected": "Timeout at 2001 ms",
             "actual": "PREVIEW timeout 1 1", "state": "PASS", "evidence": "logs/cases.tap"},
            {"number": 3, "action": "Verify cleanup", "expected": "Owned scratch removed",
             "actual": "scratch_removed=true", "state": "PASS", "evidence": "logs/cases.tap"},
        ])
        self.report = {"schema_version": 1, "execution_type": "source_check", "run_id": self.run_id,
                       "release_id": "v0.2.0-synthetic", "candidate_sha": commit, "candidate_tree": tree,
                       "catalog": {"path": "tests/test_cases.json", "sha256": sha(catalog)},
                       "runner": {"path": "scripts/tm002_source_check.py", "sha256": sha(runner)},
                       "environment": {"os": "synthetic macOS", "architecture": "x86_64", "node": str(NODE),
                                       "python": "python3", "started_at": "2026-10-02T00:00:00Z",
                                       "finished_at": "2026-10-02T00:01:00Z"},
                       "expected_ids": ids, "results": results, "counts": {"PASS": 25, "FAIL": 0, "BLOCKED": 0},
                       "test_counts": {"PASS": 25, "FAIL": 0, "BLOCKED": 0},
                       "state": "PASS", "product_e2e_state": "NOT_RUN", "release_eligible": False,
                       "commands": [{"command": command, "exit_code": 0, "timeout": False,
                                     "stdout": out, "stderr": err}]}
        self.report_path = self.run_dir / "source-check.json"
        self.output = self.repo / "exports" / "first"
        self.save_report()

    def save_report(self):
        self.report_path.write_text(json.dumps(self.report, ensure_ascii=False), encoding="utf-8")

    def export(self, output: Path | None = None):
        return subprocess.run([str(NODE), str(self.repo / "scripts/export_tm002_source_check.mjs"),
                               "--report", str(self.report_path), "--output", str(output or self.output)],
                              cwd=self.repo, capture_output=True, text=True, timeout=120, check=False)

    def test_exports_and_reads_back_every_id_step_and_log_without_changing_source(self):
        before = self.report_path.read_bytes()
        first = self.export()
        self.assertEqual(first.returncode, 0, first.stderr)
        receipt = json.loads(first.stdout)
        self.assertEqual(receipt["execution_type"], "source_check")
        self.assertEqual(receipt["test_counts"], {"PASS": 25, "FAIL": 0, "BLOCKED": 0})
        self.assertEqual(receipt["readback"]["result_rows"], 25)
        self.assertEqual(receipt["readback"]["step_rows"], 27)
        self.assertEqual(receipt["readback"]["evidence_rows"], 52)
        self.assertEqual(receipt["readback"]["ids"], self.report["expected_ids"])
        self.assertEqual(self.report_path.read_bytes(), before)
        self.assertTrue((self.output / receipt["workbook"]["path"]).is_file())
        second = self.export()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout)["export_status"], "VERIFIED_UNCHANGED")

    def test_rejects_wrong_type_duplicate_id_wrong_candidate_missing_log_and_false_pass(self):
        mutations = [
            ("type", lambda report: report.update(execution_type="product_e2e")),
            ("duplicate", lambda report: report["results"][1].update(id=report["results"][0]["id"])),
            ("wrong-variant", lambda report: (
                report["expected_ids"].__setitem__(1, "TC-TM002-STORE-01#UNFROZEN"),
                report["results"][1].update(id="TC-TM002-STORE-01#UNFROZEN"))),
            ("candidate", lambda report: report.update(candidate_tree="0" * 40)),
            ("missing-c-source", lambda report: report["results"][0]["binding"]["sources"].pop()),
            ("wrong-c-source", lambda report: report["results"][0]["binding"]["sources"][0].update(sha256="0" * 64)),
            ("test-counts", lambda report: report["test_counts"].update(PASS=24)),
            ("digest", lambda report: report["results"][0]["logs"][0].update(sha256="0" * 64)),
            ("missing", lambda report: report["results"][0].update(logs=[])),
            ("false-pass", lambda report: report["results"][0]["binding"].update(test_name="Case absent")),
            ("no-step-proof", lambda report: report["results"][0]["steps"][0].update(evidence="unbound.txt")),
        ]
        original = copy.deepcopy(self.report)
        for name, mutate in mutations:
            with self.subTest(name=name):
                self.report = copy.deepcopy(original)
                mutate(self.report)
                self.save_report()
                output = self.repo / "exports" / name
                completed = self.export(output)
                self.assertNotEqual(completed.returncode, 0, completed.stdout)
                self.assertFalse((output / "verification.json").exists())

    def test_rejects_run_directory_without_private_mode(self):
        self.run_dir.chmod(0o755)
        completed = self.export()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("mode 0700", completed.stderr)
        self.assertFalse(self.output.exists())

    def test_limit_marker_must_be_unique_and_bound_to_candidate_c_sources(self):
        log = self.run_dir / "logs/cases.tap"
        original_bytes = log.read_bytes()
        original = original_bytes.decode()
        marker_line = next(line for line in original.splitlines() if line.startswith("# TM002_LIMIT_ACTUAL "))
        marker = json.loads(marker_line.removeprefix("# TM002_LIMIT_ACTUAL "))
        wrong = dict(marker, input_sha256="0" * 64)
        cases = [
            ("missing-marker", original.replace(marker_line + "\n", "")),
            ("duplicate-marker", original.replace(marker_line, marker_line + "\n" + marker_line)),
            ("wrong-marker-sha", original.replace(marker_line,
                "# TM002_LIMIT_ACTUAL " + json.dumps(wrong, separators=(",", ":")))),
        ]
        report = copy.deepcopy(self.report)
        for name, value in cases:
            with self.subTest(name=name):
                self.report = copy.deepcopy(report)
                bytes_ = value.encode()
                log.write_bytes(bytes_)
                self.report["results"][0]["logs"][0].update(sha256=sha(bytes_), bytes=len(bytes_))
                self.save_report()
                completed = self.export(self.repo / "exports" / name)
                self.assertNotEqual(completed.returncode, 0, completed.stdout)
                self.assertFalse((self.repo / "exports" / name / "verification.json").exists())

    def test_incomplete_limit_marker_is_retained_as_blocked_evidence(self):
        log = self.run_dir / "logs/cases.tap"
        original = log.read_text()
        marker_line = next(line for line in original.splitlines() if line.startswith("# TM002_LIMIT_ACTUAL "))
        partial = original.replace(marker_line, "# TM002_LIMIT_ACTUAL {partial")
        log.write_text(partial)
        bytes_ = partial.encode()
        self.report["results"][0]["logs"][0].update(sha256=sha(bytes_), bytes=len(bytes_))
        blocked = self.report["results"][0]
        blocked["state"] = "BLOCKED"
        blocked["reason"] = "C marker was incomplete after the fixed test line"
        for step in blocked["steps"]:
            step["state"] = "BLOCKED"
            step["actual"] = "No complete C marker"
        blocked["cleanup"]["state"] = "BLOCKED"
        self.report["counts"] = {"PASS": 24, "FAIL": 0, "BLOCKED": 1}
        self.report["state"] = "BLOCKED"
        self.save_report()
        completed = self.export()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["readback"]["states"][blocked["id"]], "BLOCKED")

    def test_existing_output_refuses_changed_report_and_workbook(self):
        completed = self.export()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.report["results"][0]["reason"] = "Changed after first export"
        self.save_report()
        changed = self.export()
        self.assertNotEqual(changed.returncode, 0)
        self.assertIn("different source evidence", changed.stderr)
        self.report["results"][0]["reason"] = "Exact synthetic TAP line and step evidence"
        self.save_report()
        workbook = self.output / f"TokenMeter测试结果-{self.run_id}.xlsx"
        workbook.write_bytes(b"tampered")
        tampered = self.export()
        self.assertNotEqual(tampered.returncode, 0)
        self.assertIn("changed workbook", tampered.stderr)

    def test_fail_and_blocked_evidence_rows_survive_export_without_becoming_pass(self):
        failed = self.report["results"][0]
        failed["state"] = "FAIL"
        failed["reason"] = "Second fixed harness assertion differed"
        failed["actual_assertions"].append("Observed fixed harness mismatch")
        failed["steps"][0]["state"] = "FAIL"
        failed["steps"][0]["actual"] = "Observed mismatch"
        blocked = self.report["results"][1]
        blocked["state"] = "BLOCKED"
        blocked["reason"] = "No owned-root cleanup witness"
        blocked["steps"][0]["state"] = "BLOCKED"
        blocked["steps"][0]["actual"] = "No step-specific runtime event"
        blocked["cleanup"] = {"mode": "owned_root", "state": "BLOCKED",
                              "evidence": "No cleanup witness in the raw test output"}
        self.report["counts"] = {"PASS": 23, "FAIL": 1, "BLOCKED": 1}
        self.report["state"] = "FAIL"
        self.save_report()
        completed = self.export()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["counts"], self.report["counts"])
        self.assertEqual(receipt["test_counts"], {"PASS": 25, "FAIL": 0, "BLOCKED": 0})
        self.assertEqual(receipt["readback"]["states"][failed["id"]], "FAIL")
        self.assertEqual(receipt["readback"]["states"][blocked["id"]], "BLOCKED")
        self.assertEqual(receipt["readback"]["step_rows"], 27)

    def test_python_bridge_accepts_real_js_receipt_and_reverifies_without_rewrite(self):
        original = self.report_path.read_bytes()
        with patch.object(bridge, "ROOT", self.repo), patch.dict(os.environ, {"TOKENMETER_WORKBOOK_NODE": str(NODE)}):
            first = bridge.export(self.report_path, self.output)
            self.assertEqual(first["state"], "PASS", first.get("error"))
            receipt_path = Path(first["receipt_path"])
            self.assertTrue(receipt_path.name.startswith("excel-export-"))
            receipt_bytes = receipt_path.read_bytes()
            self.assertEqual(first["report_state"], "PASS")
            self.assertEqual(first["report_sha256"], sha(original))
            self.assertEqual(self.report_path.read_bytes(), original)
            second = bridge.export(self.report_path, self.output)
        self.assertEqual(second, first)
        self.assertEqual(receipt_path.read_bytes(), receipt_bytes)

    def test_python_bridge_reverification_rejects_changed_raw_log(self):
        with patch.object(bridge, "ROOT", self.repo), patch.dict(os.environ, {"TOKENMETER_WORKBOOK_NODE": str(NODE)}):
            first = bridge.export(self.report_path, self.output)
            self.assertEqual(first["state"], "PASS", first.get("error"))
            receipt_path = Path(first["receipt_path"])
            before = receipt_path.read_bytes()
            log = self.run_dir / "logs/cases.tap"
            log.write_bytes(log.read_bytes() + b"\nchanged after export\n")
            second = bridge.export(self.report_path, self.output)
        self.assertEqual(second["state"], "FAIL")
        self.assertIn("log SHA/length mismatch", second["error"])
        self.assertEqual(receipt_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
