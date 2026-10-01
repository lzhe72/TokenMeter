"""TC-TM002-EVIDENCE-01: seven fixed mutations of one synthetic runner report.

The complete fixture proves only the independent verifier's structure checks.
It is synthetic and must never be counted as product E2E or release evidence.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid
import zipfile

from scripts import verify_tm002_evidence


ROOT = Path(__file__).resolve().parents[2]
CASE_ID = "TC-TM002-SELECT-01"
RELEASE = "v0.2.0-20261001T034118Z"
SHA = "a" * 40
TREE = "b" * 40
RUN_ID = "tm002-synthetic-governance"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
                    "0000000b49444154789c636000020000050001a5f645400000000049454e44ae426082")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def descriptor(path: Path, root: Path) -> dict:
    return {"path": path.relative_to(root).as_posix(), "sha256": digest(path), "bytes": path.stat().st_size}


class FixedEvidenceVerifierTest(unittest.TestCase):
    def setUp(self) -> None:
        base = os.environ.get("TM002_AUX_EVIDENCE_DIR")
        if base:
            home = Path(base).resolve()
            home.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.root = home / (self._testMethodName + "-" + uuid.uuid4().hex)
            self.root.mkdir(mode=0o700)
        else:
            temporary = tempfile.TemporaryDirectory(prefix="tm002-evidence-fixed-")
            self.addCleanup(temporary.cleanup)
            self.root = Path(temporary.name).resolve()
        (self.root / "owner.json").write_text(json.dumps({"owner": "TC-TM002-EVIDENCE-01"}), encoding="utf-8")
        self.original = self.root / "original"
        self.original.mkdir(mode=0o700)
        self.package = self.root / "package-manifest.json"
        self.package.write_text(json.dumps({"schema_version": 2, "scope": "development",
                                            "release_id": RELEASE, "candidate_sha": SHA,
                                            "candidate_tree": TREE, "working_tree_dirty": False}), encoding="utf-8")
        catalog = json.loads((ROOT / "tests/test_cases.json").read_text(encoding="utf-8"))
        case = next(case for case in catalog["cases"] if case["id"] == CASE_ID)
        self.assertEqual([step["step"] for step in case["steps"]], [1, 2, 3])
        case_out = self.original / CASE_ID
        case_out.mkdir()
        steps = []
        screenshots = []
        for number in (1, 2, 3):
            screenshot = f"TC-step-{number:02}.png"
            screenshot_path = case_out / screenshot
            screenshot_path.write_bytes(PNG)
            screenshots.append(descriptor(screenshot_path, self.original))
            steps.append({"run_id": RUN_ID, "case_id": CASE_ID, "step": number,
                          "action": case["steps"][number - 1]["action"], "source": "ui",
                          "expected": "fixed synthetic marker", "actual": "fixed synthetic marker",
                          "passed": True, "timestamp": "2026-10-01T00:00:00Z",
                          "evidence": {"screenshot": screenshot}})
        events = case_out / "events.jsonl"
        events.write_text("".join(json.dumps(row) + "\n" for row in steps), encoding="utf-8")
        picker = case_out / "picker-01.json"
        picker.write_text(json.dumps({"operation": "select", "owner_pid": 4242,
                                      "panel_role": "AXSheet", "native_button": "Choose",
                                      "chooser_confirm_button": "Choose",
                                      "selection_label": "A", "selection_path_sha256": "c" * 64,
                                      "completed_at": "2026-10-01T00:00:01Z", "real_ax_action": True}), encoding="utf-8")
        audit = case_out / "source-access-audit.jsonl"
        audit.write_text("".join(json.dumps({"schema_version": 1, "sequence": number,
                                            "operation": operation, "decision": "allowed", "tool": "codex",
                                            "generation": 1, "root_digest": "d" * 64 if number > 2 else None,
                                            "entry_digest": None}) + "\n"
                                 for number, operation in enumerate(
                                     ("picker_open", "picker_result", "root_open", "enumerate"), 1)), encoding="utf-8")
        source_expected = case_out / "source-expected.json"
        source_expected.write_text(json.dumps({"schema_version": 1, "case_id": CASE_ID,
                                               "tool": "codex", "private_oracle_sha256": "e" * 64}), encoding="utf-8")
        playwright = case_out / "playwright.json"
        playwright.write_text(json.dumps({"suites": [{"specs": [{"title": CASE_ID,
            "tests": [{"results": [{"status": "passed", "retry": 0}]}]}]}]}), encoding="utf-8")
        trace = case_out / "trace-01.zip"
        with zipfile.ZipFile(trace, "w") as archive:
            archive.writestr("trace.trace", "fixed synthetic trace marker")
        result = {"case_id": CASE_ID, "state": "PASS", "reason": "",
                  "task_ids": case["task_ids"], "ac_ids": case["ac_ids"],
                  "step_results": steps, "cleanup": {"completed": True},
                  "evidence": {"events": descriptor(events, self.original),
                               "picker_events": [descriptor(picker, self.original)],
                               "source_access_audit": descriptor(audit, self.original),
                               "source_expected": descriptor(source_expected, self.original),
                               "playwright": descriptor(playwright, self.original),
                               "trace": descriptor(trace, self.original),
                               "screenshots": screenshots}}
        report = {"schema_version": 1, "scope": "tm002_granular_targeted_development_probe",
                  "release_id": RELEASE, "source_commit": SHA, "candidate_tree": TREE,
                  "working_tree_dirty": False, "run_id": RUN_ID,
                  "expected_cases": [CASE_ID], "tc_results": [result], "state": "PASS",
                  "release_eligible": False, "cleanup_completed": True,
                  "package": {"manifest_sha256": digest(self.package), "dmg_sha256": "f" * 64,
                              "app_tree_sha256": "1" * 64, "installed_source": "development_dmg"}}
        self.mother = self.original / "result.json"
        self.mother.write_text(json.dumps(report, indent=2), encoding="utf-8")
        self.mother_sha = digest(self.mother)

    def variant(self, name: str) -> tuple[dict, int, dict]:
        self.assertEqual(json.loads((self.root / "owner.json").read_text())["owner"], "TC-TM002-EVIDENCE-01")
        copied = self.root / name
        shutil.copytree(self.original, copied)
        report_path = copied / "result.json"
        value = json.loads(report_path.read_text(encoding="utf-8"))
        result = value["tc_results"][0]
        evidence = result["evidence"]
        if name == "MISSING_STEP":
            result["step_results"].pop(1)
            event_path = copied / evidence["events"]["path"]
            rows = event_path.read_text(encoding="utf-8").splitlines()
            event_path.write_text(rows[0] + "\n" + rows[2] + "\n", encoding="utf-8")
            evidence["events"] = descriptor(event_path, copied)
        elif name == "MISSING_PICKER":
            (copied / evidence["picker_events"][0]["path"]).unlink()
            evidence["picker_events"] = []
        elif name == "MISSING_CHOOSER_WITNESS":
            event_path = copied / evidence["picker_events"][0]["path"]
            picker_event = json.loads(event_path.read_text(encoding="utf-8"))
            picker_event.pop("chooser_confirm_button")
            event_path.write_text(json.dumps(picker_event), encoding="utf-8")
            evidence["picker_events"][0] = descriptor(event_path, copied)
        elif name == "MISSING_FS":
            (copied / evidence["source_access_audit"]["path"]).unlink()
            evidence.pop("source_access_audit")
        elif name == "WRONG_PACKAGE":
            value["package"]["manifest_sha256"] = "0" * 64
        elif name == "FAILED_CLEANUP":
            result["cleanup"]["completed"] = False
        elif name != "COMPLETE":
            self.fail("Unknown fixed variant")
        report_path.write_text(json.dumps(value, indent=2), encoding="utf-8")
        variant_sha = digest(report_path)
        self.assertEqual(digest(self.mother), self.mother_sha)
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            exit_code = verify_tm002_evidence.main(["--report", str(report_path),
                "--package-manifest", str(self.package)])
        output = json.loads(captured.getvalue())
        self.assertEqual(digest(report_path), variant_sha, "verifier must be read-only")
        self.assertEqual(digest(self.mother), self.mother_sha)
        (copied / "verification.json").write_text(json.dumps({"variant": name,
            "mother_sha256": self.mother_sha, "variant_sha256": variant_sha,
            "exit_code": exit_code, "result": output}, indent=2), encoding="utf-8")
        return output, exit_code, value

    def test_TC_TM002_EVIDENCE_01_COMPLETE(self) -> None:
        output, code, _ = self.variant("COMPLETE")
        self.assertEqual(code, 0, output)
        self.assertEqual(output["state"], "PASS")
        self.assertIs(output["release_eligible"], False)
        self.assertEqual(output["scope"], "tm002_evidence_structure_only")

    def test_TC_TM002_EVIDENCE_01_MISSING_STEP(self) -> None:
        output, code, _ = self.variant("MISSING_STEP")
        self.assertNotEqual(code, 0)
        self.assertNotEqual(output["state"], "PASS")
        self.assertIn("step", json.dumps(output).lower())

    def test_TC_TM002_EVIDENCE_01_MISSING_PICKER(self) -> None:
        output, code, _ = self.variant("MISSING_PICKER")
        self.assertNotEqual(code, 0)
        self.assertNotEqual(output["state"], "PASS")
        self.assertIn("picker", json.dumps(output).lower())

    def test_TC_TM002_EVIDENCE_01_MISSING_CHOOSER_WITNESS(self) -> None:
        output, code, _ = self.variant("MISSING_CHOOSER_WITNESS")
        self.assertNotEqual(code, 0)
        self.assertNotEqual(output["state"], "PASS")
        self.assertIn("native picker event", json.dumps(output).lower())

    def test_TC_TM002_EVIDENCE_01_MISSING_FS(self) -> None:
        output, code, value = self.variant("MISSING_FS")
        self.assertNotEqual(code, 0)
        self.assertNotEqual(output["state"], "PASS")
        self.assertIn("source audit", json.dumps(output).lower())
        self.assertEqual(value["tc_results"][0]["step_results"][2]["actual"], "fixed synthetic marker",
                         "UI assertion cannot replace missing filesystem audit")

    def test_TC_TM002_EVIDENCE_01_WRONG_PACKAGE(self) -> None:
        output, code, _ = self.variant("WRONG_PACKAGE")
        self.assertNotEqual(code, 0)
        self.assertNotEqual(output["state"], "PASS")
        self.assertIn("package manifest", json.dumps(output).lower())

    def test_TC_TM002_EVIDENCE_01_FAILED_CLEANUP(self) -> None:
        output, code, _ = self.variant("FAILED_CLEANUP")
        self.assertNotEqual(code, 0)
        self.assertNotEqual(output["state"], "PASS")
        self.assertIn("cleanup", json.dumps(output).lower())


if __name__ == "__main__":
    unittest.main()
