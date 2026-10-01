"""Fixed TM-002 source data, privacy and ownership checks (no App/Keychain)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("tm002_fixture", ROOT / "scripts/tm002_fixture.py")
assert SPEC and SPEC.loader
fixture_module = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = fixture_module
SPEC.loader.exec_module(fixture_module)


class TM002FixtureTest(unittest.TestCase):
    def test_fixed_roots_mutations_and_owned_cleanup(self):
        with tempfile.TemporaryDirectory(prefix="tm002-data-") as temp:
            parent = Path(temp)
            sentinel = parent / "unowned.txt"
            sentinel.write_text("keep", encoding="utf-8")
            fixture = fixture_module.prepare("TC-TM002-SELECT-01", parent / "owned", "owner-12345678")
            self.assertEqual([item["relative_name"] for item in fixture.expected["preview"]["candidates"]],
                             [fixture_module.A1, fixture_module.A2])
            self.assertEqual((fixture.a / fixture_module.A1).read_bytes(), b'{"private":"PRIVATE_A1"}\n')
            self.assertEqual((fixture.b / fixture_module.B1).read_bytes(), b'{"private":"PRIVATE_B1"}\n')
            self.assertEqual((fixture.a / fixture_module.A1).stat().st_size, 25)
            self.assertEqual((fixture.a / fixture_module.A1).stat().st_mtime, fixture_module.FIXED_MTIME)
            self.assertTrue((fixture.a / "sessions/2026/10/01/link-out.jsonl").is_symlink())
            self.assertTrue((fixture.a / "sessions/2026/10/01/escape").is_symlink())
            self.assertNotIn(str(parent), fixture.manifest_path.read_text(encoding="utf-8"))
            redacted = json.dumps(fixture_module.redacted_expected(fixture, b"test-nonce" * 4))
            self.assertNotIn("a-01.jsonl", redacted)
            self.assertNotIn(str(parent), redacted)
            mutation = fixture.append_new()
            self.assertEqual(mutation["A"]["bytes"], 28)
            fixture.deny_a()
            fixture.restore_a()
            replacement = fixture.replace_a_inode()
            self.assertNotEqual(replacement["old_inode"], replacement["new_inode"])
            fixture.cleanup()
            self.assertFalse(fixture.root.exists())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_fixed_variant_cardinality_and_byte_sorted_oracle(self):
        variants = {"CANDIDATES_1001": (1001, 1000, "candidate_limit"),
                    "ENTRIES_5001": (5001, 0, "entry_limit"),
                    "DEPTH_9": (10, 1, "depth_limit")}
        with tempfile.TemporaryDirectory(prefix="tm002-volume-") as temp:
            for name, (entry_count, preview_count, reason) in variants.items():
                with self.subTest(name=name):
                    fixture = fixture_module.prepare(f"TC-TM002-PREVIEW-04#{name}", Path(temp) / name,
                                                     "owner-12345678")
                    self.assertEqual(len(fixture.expected["preview"]["candidates"]), preview_count)
                    self.assertEqual(fixture.expected["preview"]["incomplete_reason"], reason)
                    self.assertEqual(fixture_module.volume_preprobe(fixture)["entries"], entry_count)
                    if name == "CANDIDATES_1001":
                        names = [item["relative_name"] for item in fixture.expected["preview"]["candidates"]]
                        self.assertEqual(names[0], "c-0000.jsonl")
                        self.assertEqual(names[-1], "c-0999.jsonl")
                        self.assertNotIn("c-1000.jsonl", names)
                    fixture.cleanup()

    def test_owner_mismatch_refuses_delete_and_account_query_has_fixed_values(self):
        with tempfile.TemporaryDirectory(prefix="tm002-owner-") as temp:
            parent = Path(temp)
            fixture = fixture_module.prepare("TC-TM002-PREVIEW-02", parent / "owned", "owner-12345678")
            marker = fixture.root / ".owner.json"
            value = json.loads(marker.read_text(encoding="utf-8"))
            value["owner_id"] = "foreign-owner"
            marker.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ValueError):
                fixture.cleanup()
            self.assertTrue(fixture.root.exists())
            marker.write_text(json.dumps({**value, "owner_id": fixture.owner_id}), encoding="utf-8")
            fixture.cleanup()
            database = parent / "synthetic.sqlite"
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE users(id TEXT, username TEXT, role TEXT, is_active INTEGER)")
                connection.execute("CREATE TABLE sessions(id TEXT)")
                connection.execute("CREATE TABLE audit(id TEXT)")
                connection.executemany("INSERT INTO users VALUES(:id,:username,:role,:is_active)",
                                       fixture_module.ACCOUNT_EXPECTED)
            self.assertEqual(fixture_module.verify_accounts(database)["rows"], fixture_module.ACCOUNT_EXPECTED)
            with sqlite3.connect(database) as connection:
                connection.execute("UPDATE users SET role='admin' WHERE id=?", (fixture_module.ALICE_ID,))
            with self.assertRaises(ValueError):
                fixture_module.verify_accounts(database)


if __name__ == "__main__":
    unittest.main()
