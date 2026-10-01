"""TC-TM002-DATA-01: fixed ownership, source bytes and reset boundaries."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("tm002_fixture_fixed", ROOT / "scripts/tm002_fixture.py")
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TM002DataFixedTest(unittest.TestCase):
    def test_tc_tm002_data_01_owned_generation_mutation_and_reset(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tm002-data-fixed-") as temporary:
            parent = Path(temporary).resolve()
            owned = parent / "owned"
            unmarked = parent / "unmarked"
            unmarked.mkdir(mode=0o700)
            sentinel = unmarked / "sentinel.txt"
            sentinel.write_bytes(b"must remain untouched\n")
            sentinel_before = sha(sentinel)
            fixture = module.prepare("TC-TM002-DATA-01", owned, "owner-12345678")
            self.assertEqual(stat.S_IMODE(fixture.root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((fixture.root / ".owner.json").stat().st_mode), 0o600)
            self.assertEqual(len(fixture.expected["preview"]["candidates"]), 2)
            self.assertEqual([item["relative_name"] for item in fixture.expected["preview"]["candidates"]],
                             [module.A1, module.A2])
            files = {(item["root"], item["relative_name"]): item for item in fixture.expected["files"]}
            fixed = {("A", module.A1): 25, ("A", module.A2): 25, ("B", module.B1): 25}
            for (label, relative), size in fixed.items():
                source = (fixture.a if label == "A" else fixture.b) / relative
                self.assertEqual(source.stat().st_size, size)
                self.assertEqual(source.stat().st_mtime, module.FIXED_MTIME)
                self.assertEqual(sha(source), files[(label, relative)]["sha256"])
                self.assertEqual(stat.S_IMODE(source.stat().st_mode), 0o600)
            self.assertEqual((fixture.a / "sessions/2026/10/01/ignore.txt").stat().st_size, 12)
            self.assertTrue((fixture.a / "sessions/2026/10/01/link-out.jsonl").is_symlink())
            self.assertTrue((fixture.a / "sessions/2026/10/01/escape").is_symlink())
            expected_bytes = fixture.manifest_path.read_bytes()
            self.assertNotIn(str(parent).encode(), expected_bytes)
            marker = json.loads((fixture.root / ".owner.json").read_text())
            self.assertEqual(marker["owner_id"], fixture.owner_id)
            self.assertEqual(marker["root_inode"], fixture.inode)
            self.assertEqual(marker["root_device"], fixture.device)

            mutation = fixture.append_new()
            self.assertEqual((mutation["A"]["bytes"], mutation["B"]["bytes"]), (28, 28))
            b_before = sha(fixture.b / module.B1)
            old_a = fixture.a.stat(follow_symlinks=False)
            fixture.deny_a()
            self.assertEqual(stat.S_IMODE(fixture.a.stat(follow_symlinks=False).st_mode), 0)
            if os.geteuid() != 0:
                with self.assertRaises(PermissionError):
                    os.listdir(fixture.a)
            fixture.restore_a()
            self.assertEqual(stat.S_IMODE(fixture.a.stat().st_mode), 0o700)
            changed = fixture.replace_a_inode()
            new_a = fixture.a.stat(follow_symlinks=False)
            self.assertEqual(changed["old_inode"], old_a.st_ino)
            self.assertEqual(changed["new_inode"], new_a.st_ino)
            self.assertNotEqual(old_a.st_ino, new_a.st_ino)
            self.assertEqual(sha(fixture.root / "A-original" / module.A1), files[("A", module.A1)]["sha256"])
            self.assertEqual(sha(fixture.root / "A-original" / module.A2), files[("A", module.A2)]["sha256"])
            self.assertEqual(sha(fixture.b / module.B1), b_before)

            foreign = unmarked.stat(follow_symlinks=False)
            unowned_fixture = module.Fixture(unmarked, unmarked / "A", unmarked / "B", fixture.owner_id,
                                             foreign.st_ino, foreign.st_dev, {}, unmarked / "expected.json")
            with self.assertRaises(ValueError):
                unowned_fixture.cleanup()
            self.assertEqual(sha(sentinel), sentinel_before)
            fixture.cleanup()
            self.assertFalse(owned.exists())
            self.assertTrue(unmarked.is_dir())
            self.assertEqual(sha(sentinel), sentinel_before)


if __name__ == "__main__":
    unittest.main()
