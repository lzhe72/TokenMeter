import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("tm004_identity_vectors", ROOT / "scripts/tm004_identity_vectors.py")
IDENTITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IDENTITY)


class IdentityVectorTests(unittest.TestCase):
    def test_public_vectors_are_byte_exact(self):
        IDENTITY.verify_vectors()

    def test_source_namespace_and_exact_provider_id(self):
        secret = bytes(range(32))
        codex = IDENTITY.identity_key(secret, "codex", "provider-response", "shared-call-01")
        claude = IDENTITY.identity_key(secret, "claude_code", "provider-message", "shared-call-01")
        self.assertNotEqual(codex, claude)
        self.assertNotEqual(claude, IDENTITY.identity_key(
            secret, "claude_code", "provider-message", "Shared-call-01"))
        self.assertNotEqual(claude, IDENTITY.identity_key(
            secret, "claude_code", "provider-message", "shared-call-01 "))

    def test_reject_invalid_namespace_or_unicode(self):
        secret = bytes(range(32))
        for source, scope, call_id in (("codex", "provider-message", "x"),
                                       ("claude_code", "provider-message", ""),
                                       ("claude_code", "provider-message", "\ud800")):
            with self.subTest(source=source, call_id=repr(call_id)):
                with self.assertRaises((ValueError, UnicodeError)):
                    IDENTITY.identity_key(secret, source, scope, call_id)


if __name__ == "__main__":
    unittest.main()
