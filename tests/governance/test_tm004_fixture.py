import importlib.util
import json
from pathlib import Path
import uuid
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("tm004_fixture", ROOT / "scripts/tm004_fixture.py")
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


class TM004FixtureTests(unittest.TestCase):
    def test_committed_projection_and_independent_oracle(self):
        manifest = FIXTURE.check_projection()
        self.assertEqual(manifest["independent_expected"]["main_plus_fork"]["total_tokens"], 40)
        self.assertEqual(manifest["independent_expected"]["agent_parent_plus_sub"]["total_tokens"], 77)
        self.assertFalse(manifest["independent_expected"]["missing_upstream_usage"]["trusted_zero"])
        self.assertEqual(
            manifest["independent_expected"]["synthetic_faults"]["partial_after"]["total_tokens"], 20
        )

    def test_private_generation_verification_and_exact_reset(self):
        run_id = "governance-" + uuid.uuid4().hex
        target = FIXTURE.generate(run_id)
        try:
            self.assertEqual(target.stat().st_mode & 0o777, 0o700)
            self.assertEqual(FIXTURE.verify_owned(run_id)[0], target)
            before = (target / "fault-partial-before.jsonl").read_bytes()
            after = (target / "fault-partial-after.jsonl").read_bytes()
            self.assertFalse(before.endswith(b"\n"))
            self.assertTrue(after.endswith(b"\n"))
            with self.assertRaises(json.JSONDecodeError):
                json.loads(before.splitlines()[-1])
            conflict = json.loads((target / "fault-conflict.jsonl").read_text())
            self.assertEqual(conflict["message"]["usage"]["input_tokens"], 14)
            missing = json.loads((target / "fault-missing-field.jsonl").read_text())
            self.assertNotIn("usage", missing["message"])
            planned = json.loads((target / "planned-expected.json").read_text())
            self.assertEqual(planned["scenarios"]["fork_completed_p"]["total_tokens"], 187)
            self.assertEqual(planned["scenarios"]["sub_new_after_regrant"]["total_tokens"], 385)
            main = json.loads((target / "planned-main.jsonl").read_text())
            fork = [json.loads(line) for line in
                    (target / "planned-fork-after-p.jsonl").read_text().splitlines()]
            self.assertEqual(main["message"]["id"], fork[0]["message"]["id"])
            self.assertEqual(main["uuid"], fork[0]["uuid"])
            self.assertNotEqual(main["sessionId"], fork[0]["sessionId"])
            self.assertEqual([item["message"]["usage"]["input_tokens"] for item in fork],
                             [100, 50, 20])
            self.assertFalse((target / "planned-fork-before-p.jsonl").read_bytes().endswith(b"\n"))
            with self.assertRaises(FileExistsError):
                FIXTURE.generate(run_id)
            extra = target / "unknown-file"
            extra.write_text("owned test marker")
            with self.assertRaises(ValueError):
                FIXTURE.reset(run_id)
            extra.unlink()
        finally:
            FIXTURE.reset(run_id)
        self.assertFalse(target.exists())

    def test_reject_bad_run_id(self):
        for run_id in ("../outside", "", "bad/path", "a" * 65):
            with self.assertRaises(ValueError):
                FIXTURE.destination(run_id)


if __name__ == "__main__":
    unittest.main()
