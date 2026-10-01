"""Fixed, non-Keychain checks for the TM002 isolated-account metadata probe."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "scripts" / "tm002_keychain_probe.swift"
EXPECTED_NEGATIVES = {
    "preexisting_item",
    "missing_postflight_item",
    "duplicate_exact_items",
    "wrong_item_attributes",
    "unsigned_app",
    "unbounded_acl",
    "wrong_acl_application",
    "wrong_owner",
    "changed_item_before_cleanup",
    "unexpected_item_for_absent_case",
}


class TM002KeychainProbeTests(unittest.TestCase):
    def test_tc_tm002_keychain_01_compiles_without_touching_keychain(self) -> None:
        self.assertTrue(PROBE.is_file(), "Fixed Swift probe is required")
        result = subprocess.run(
            ["swiftc", "-typecheck", str(PROBE)],
            text=True, capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_tc_tm002_keychain_02_fixed_negative_decisions(self) -> None:
        self.assertTrue(PROBE.is_file(), "Fixed Swift probe is required")
        result = subprocess.run(
            ["swift", str(PROBE), "--self-test"],
            text=True, capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["mode"], "self_test")
        self.assertEqual(report["state"], "PASS")
        self.assertEqual(set(report["blocked_cases"]), EXPECTED_NEGATIVES)

    def test_tc_tm002_keychain_03_secret_and_scope_guards_are_fixed(self) -> None:
        self.assertTrue(PROBE.is_file(), "Fixed Swift probe is required")
        source = PROBE.read_text(encoding="utf-8")
        self.assertIn("TokenMeter-Test-", source)
        self.assertIn("kSecAttrService", source)
        self.assertIn("kSecAttrAccount", source)
        self.assertIn("SecKeychainItemCopyAccess", source)
        self.assertIn("SecTrustedApplicationCopyData", source)
        self.assertIn("kSecReturnPersistentRef", source)
        self.assertNotIn("kSecReturnData", source)
        self.assertNotIn("SecKeychainItemCopyContent", source)
        self.assertNotIn("find-generic-password", source)


if __name__ == "__main__":
    unittest.main()
