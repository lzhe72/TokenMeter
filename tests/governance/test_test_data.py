"""Tests for fixture tooling only; passing these does not verify product E2E."""

from datetime import datetime
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zoneinfo import ZoneInfo


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "test_data.py"
SPEC = importlib.util.spec_from_file_location("test_data", SCRIPT)
test_data = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(test_data)


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name).resolve()

    def generate(self, run_id="demo", seed=42, workspace=None):
        return test_data.generate(run_id, seed, workspace=workspace or self.workspace)

    @staticmethod
    def snapshot(path):
        return {item.name: item.read_bytes() for item in path.iterdir() if item.is_file()}

    @staticmethod
    def read_json(path, filename):
        return json.loads((path / filename).read_text())

    def test_generation_is_byte_deterministic_across_workspaces(self):
        first = self.generate(workspace=self.workspace / "one")
        second = self.generate(workspace=self.workspace / "two")
        self.assertEqual(self.snapshot(first), self.snapshot(second))
        for data in self.snapshot(first).values():
            self.assertNotIn(str(self.workspace).encode(), data)
        manifest = self.read_json(first, "manifest.json")
        self.assertEqual(manifest["fixed_clock"], "2026-09-29T04:00:00Z")
        self.assertEqual(manifest["timezone"], "Asia/Shanghai")
        self.assertEqual(manifest["fixture_kind"], "normalized-test-spec")
        self.assertEqual(set(manifest["files"]), set(test_data.OWNED_FILES) - {"manifest.json"})
        self.assertEqual(set(manifest["datasets"]),
                         {"identity", "usage_normalized", "pricing", "date_ranges", "duplicates"})
        for filename, digest in manifest["files"].items():
            self.assertEqual(digest, hashlib.sha256((first / filename).read_bytes()).hexdigest())

    def test_seed_changes_order_and_credentials_but_not_expected_values(self):
        first = self.generate(workspace=self.workspace / "one")
        second = self.generate(seed=7, workspace=self.workspace / "two")
        self.assertNotEqual((first / "usage.jsonl").read_bytes(), (second / "usage.jsonl").read_bytes())
        self.assertNotEqual((first / "users.json").read_bytes(), (second / "users.json").read_bytes())
        self.assertEqual((first / "expected.json").read_bytes(), (second / "expected.json").read_bytes())

    def test_synthetic_identity_roles_and_disabled_account(self):
        path = self.generate()
        document = self.read_json(path, "users.json")
        self.assertTrue(document["test_only"])
        users = {user["id"]: user for user in document["users"]}
        self.assertEqual(set(users), {"test-admin", "test-alice", "test-bob", "test-disabled"})
        self.assertEqual(users["test-admin"]["role"], "admin")
        self.assertFalse(users["test-disabled"]["enabled"])
        self.assertTrue(all(user["password"].startswith("TEST-ONLY-") for user in users.values()))
        self.assertTrue(all(user["enabled"] for key, user in users.items() if key != "test-disabled"))

    def test_explicit_oracle_matches_independent_reference_calculation(self):
        path = self.generate()
        rows = [json.loads(line) for line in (path / "usage.jsonl").read_text().splitlines()]
        expected = self.read_json(path, "expected.json")
        prices = self.read_json(path, "prices.json")["models"]
        by_id = {}
        for row in rows:
            if row["event_id"] in by_id:
                self.assertEqual(row, by_id[row["event_id"]])
            by_id[row["event_id"]] = row
        self.assertEqual(len(rows), 13)
        self.assertEqual(len(by_id), 12)
        self.assertEqual(expected["raw_event_count"], len(rows))
        self.assertEqual(expected["unique_event_count"], len(by_id))
        self.assertEqual(sum(row["event_id"] == "today-gpt" for row in rows), 2)
        self.assertEqual({row["device_id"] for row in rows}, {"alice-mac-1", "alice-mac-2", "bob-mac-1"})
        for row in rows:
            self.assertLessEqual(row["cached_input_tokens"], row["input_tokens"])
            self.assertLessEqual(row["reasoning_output_tokens"], row["output_tokens"])

        def aggregate(events):
            result = {field: sum(row[field] for row in events) for field in
                      ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")}
            cost = Decimal(0)
            missing = 0
            for row in events:
                price = prices.get(row["model"])
                if price is None:
                    missing += 1
                    continue
                # Calculate each separately billed component using exact arithmetic.
                quantities = {"input": row["input_tokens"] - row["cached_input_tokens"],
                              "cached_input": row["cached_input_tokens"], "output": row["output_tokens"]}
                cost += sum(Decimal(price[kind]) * count for kind, count in quantities.items()) / 1000000
            result.update(unique_events=len(events), total_tokens=result["input_tokens"] + result["output_tokens"],
                          known_estimated_cost_usd=format(cost, ".6f"), unpriced_events=missing,
                          cost_complete=missing == 0)
            return result

        zone = ZoneInfo("Asia/Shanghai")

        def local_date(row):
            return datetime.fromisoformat(row["occurred_at"].replace("Z", "+00:00")).astimezone(zone).date().isoformat()

        events = list(by_id.values())
        self.assertEqual(aggregate(events), expected["all_time"])
        self.assertEqual(expected["all_time"]["total_tokens"], 42130)
        for name, period in expected["periods"].items():
            selected = [row for row in events if period["start"] <= local_date(row) < period["end_exclusive"]]
            with self.subTest(period=name):
                self.assertEqual(aggregate(selected), period["totals"])
        today = [row for row in events if local_date(row) == "2026-09-29"]
        for member, totals in expected["today_by_member"].items():
            self.assertEqual(aggregate([row for row in today if row["user_id"] == member]), totals)
        custom = expected["periods"]["custom"]
        self.assertEqual([row["event_id"] for row in events
                          if custom["start"] <= local_date(row) < custom["end_exclusive"]], ["custom-start"])

    def test_existing_generation_fails_without_changing_any_file(self):
        path = self.generate()
        before = self.snapshot(path)
        with self.assertRaises(test_data.FixtureError):
            self.generate(seed=3)
        self.assertEqual(before, self.snapshot(path))

    def test_invalid_run_ids_do_not_create_directories(self):
        for run_id in ("", ".", "..", "../escape", "/tmp/x", "UPPER", "a/b", "a\\b", "x" * 65, "test\n"):
            with self.subTest(run_id=run_id):
                with self.assertRaises(test_data.FixtureError):
                    self.generate(run_id)
                with self.assertRaises(test_data.FixtureError):
                    test_data.reset(run_id, workspace=self.workspace)
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_reset_removes_only_the_owned_run_and_preserves_sibling(self):
        path = self.generate()
        sibling = self.generate("other")
        sibling_before = self.snapshot(sibling)
        test_data.reset("demo", workspace=self.workspace)
        self.assertFalse(path.exists())
        self.assertTrue(path.parent.is_dir())
        self.assertEqual(sibling_before, self.snapshot(sibling))

    def test_missing_or_forged_marker_refuses_reset_without_partial_deletion(self):
        for mode in ("missing", "invalid-json", "wrong-owner"):
            with self.subTest(mode=mode):
                path = self.generate(mode)
                marker = path / test_data.MARKER
                if mode == "missing":
                    marker.unlink()
                elif mode == "invalid-json":
                    marker.write_text("not json")
                else:
                    marker.write_text(json.dumps({"owner": "foreign"}))
                before = self.snapshot(path)
                with self.assertRaises(test_data.FixtureError):
                    test_data.reset(mode, workspace=self.workspace)
                self.assertEqual(before, self.snapshot(path))

    def test_foreign_file_or_directory_refuses_reset(self):
        for kind in ("file", "directory"):
            with self.subTest(kind=kind):
                path = self.generate(kind)
                foreign = path / "valuable"
                foreign.write_text("keep") if kind == "file" else foreign.mkdir()
                before = self.snapshot(path)
                with self.assertRaises(test_data.FixtureError):
                    test_data.reset(kind, workspace=self.workspace)
                self.assertTrue(foreign.exists())
                self.assertEqual(before, self.snapshot(path))

    def test_parent_symlinks_refused_for_both_operations(self):
        for parent_name in (".local", "test-runs"):
            with self.subTest(parent=parent_name):
                workspace = self.workspace / parent_name.replace(".", "")
                workspace.mkdir()
                foreign = self.workspace / (parent_name + "-foreign")
                foreign.mkdir()
                link = workspace / ".local"
                if parent_name == "test-runs":
                    link.mkdir()
                    link = link / "test-runs"
                link.symlink_to(foreign, target_is_directory=True)
                with self.assertRaises(test_data.FixtureError):
                    self.generate(workspace=workspace)
                with self.assertRaises(test_data.FixtureError):
                    test_data.reset("demo", workspace=workspace)
                self.assertEqual(list(foreign.iterdir()), [])

    def test_target_and_generated_file_symlinks_refused(self):
        path = self.generate()
        foreign = self.workspace / "keep.json"
        foreign.write_text("valuable")
        (path / "users.json").unlink()
        (path / "users.json").symlink_to(foreign)
        with self.assertRaises(test_data.FixtureError):
            test_data.reset("demo", workspace=self.workspace)
        self.assertEqual(foreign.read_text(), "valuable")
        self.assertTrue((path / "manifest.json").exists())
        linked = path.parent / "linked"
        linked.symlink_to(path, target_is_directory=True)
        with self.assertRaises(test_data.FixtureError):
            self.generate("linked")
        with self.assertRaises(test_data.FixtureError):
            test_data.reset("linked", workspace=self.workspace)

    def test_cli_full_lifecycle_and_rejects_custom_output(self):
        def run(*args):
            return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.workspace,
                                  capture_output=True, text=True)
        generated = run("generate", "--run-id", "demo", "--seed", "42")
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.assertIn("not application provisioning or product E2E", generated.stdout)
        self.assertEqual(run("generate", "--run-id", "demo").returncode, 1)
        self.assertNotEqual(run("generate", "--run-id", "extra", "--output", "elsewhere").returncode, 0)
        removed = run("reset", "--run-id", "demo")
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertFalse((self.workspace / ".local/test-runs/demo").exists())
        self.assertEqual(run("reset", "--run-id", "demo").returncode, 1)


if __name__ == "__main__":
    unittest.main()
