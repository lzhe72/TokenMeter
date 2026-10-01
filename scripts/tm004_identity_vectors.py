#!/usr/bin/env python3
"""Reference checker for the shared Codex/Claude usage identity v1 test vectors."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "tests/fixtures/tm004/identity-v1-vectors.json"
SCOPES = {"codex": "provider-response", "claude_code": "provider-message"}
VERSION = "usage-identity-v1"


def encode_fields(source: str, scope: str, call_id: str) -> bytes:
    if source not in SCOPES or scope != SCOPES[source]:
        raise ValueError("Invalid source/scope namespace")
    if not isinstance(call_id, str) or not call_id:
        raise ValueError("Provider call ID must be nonempty text")
    encoded = []
    for field in (VERSION, source, scope, call_id):
        raw = field.encode("utf-8", errors="strict")
        if len(raw) >= 2**32:
            raise ValueError("Identity field exceeds uint32 byte length")
        encoded.append(len(raw).to_bytes(4, "big") + raw)
    return b"".join(encoded)


def identity_key(secret: bytes, source: str, scope: str, call_id: str) -> str:
    if not isinstance(secret, bytes) or len(secret) != 32:
        raise ValueError("Identity secret must contain 32 bytes")
    return hmac.new(secret, encode_fields(source, scope, call_id), hashlib.sha256).hexdigest()


def verify_vectors() -> None:
    document = json.loads(VECTORS.read_text())
    if document["schema_version"] != 1 or document["identity_scheme_version"] != VERSION:
        raise ValueError("Identity vector version differs")
    secret = bytes.fromhex(document["test_secret_hex"])
    if len(document["vectors"]) != 5:
        raise ValueError("Identity vector set differs")
    keys = {}
    for vector in document["vectors"]:
        source, scope, call_id = (vector[name] for name in
                                  ("source", "provider_call_scope", "canonical_call_id"))
        preimage = encode_fields(source, scope, call_id)
        if preimage.hex() != vector["preimage_hex"]:
            raise ValueError(f"Preimage differs: {vector['label']}")
        if identity_key(secret, source, scope, call_id) != vector["source_event_key_hex"]:
            raise ValueError(f"HMAC differs: {vector['label']}")
        keys[vector["label"]] = vector["source_event_key_hex"]
    if (keys["codex_shared"] == keys["claude_shared"] or
            keys["claude_unicode_composed"] == keys["claude_unicode_decomposed"]):
        raise ValueError("Namespace or exact Unicode identity collapsed")


if __name__ == "__main__":
    verify_vectors()
