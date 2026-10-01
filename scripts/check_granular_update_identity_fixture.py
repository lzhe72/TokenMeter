#!/usr/bin/env python3
"""Fixed non-GUI component check for UPDATE-05 certificate and DR variants.

This verifies that the negative ZIP passes Ed25519 and its App passes local
code-signature verification, then fails the *current candidate's* designated
requirement. It does not claim an installed-App E2E result.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.granular_update_validation_fixture import ValidationFixture


KINDS = ("TC-TM001-UPDATE-05#CERT_MISMATCH", "TC-TM001-UPDATE-05#DR_MISMATCH")


def run(command: list[str], label: str, *, expect_success: bool = True) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    if (result.returncode == 0) != expect_success:
        raise ValueError(label + " did not produce the required outcome")
    return result.stdout + result.stderr


def check(fixture: ValidationFixture, package: dict, output: Path) -> dict:
    config = fixture.config
    archive = fixture.archive
    public = config["update_public_key"]
    signature = fixture.signature
    verifier = (
        "const fs=require('node:fs'),c=require('node:crypto');"
        "const pub=c.createPublicKey({key:Buffer.concat([Buffer.from('302a300506032b6570032100','hex'),"
        "Buffer.from(process.argv[1],'base64')]),format:'der',type:'spki'});"
        "if(!c.verify(null,fs.readFileSync(process.argv[3]),pub,Buffer.from(process.argv[2],'base64')))process.exit(2);"
    )
    run(["node", "-e", verifier, public, signature, str(archive)], "Pinned Ed25519 verification")
    extraction = output / "extracted"
    extraction.mkdir(mode=0o700)
    run(["/usr/bin/ditto", "-x", "-k", str(archive), str(extraction)], "Extract signed negative ZIP")
    bundle = extraction / "TokenMeter.app"
    info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
    if (info.get("CFBundleIdentifier") != config["bundle_id"]
            or info.get("CFBundleShortVersionString") != fixture.metadata["version"]
            or str(info.get("CFBundleVersion")) != fixture.metadata["build"]):
        raise ValueError("Negative App Info must match advertised identity and version")
    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(bundle)],
        "Independent code signature verification")
    requirement = package["app"]["designated_requirement"]
    if not isinstance(requirement, str) or "certificate" not in requirement:
        raise ValueError("Current App designated requirement is missing")
    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", "-R", "=" + requirement,
         str(bundle)], "Current App designated requirement rejection", expect_success=False)
    prefix = output / "certificate-"
    run(["/usr/bin/codesign", "--display", "--extract-certificates=" + str(prefix), str(bundle)],
        "Extract negative App leaf certificate")
    leaf = hashlib.sha256(Path(str(prefix) + "0").read_bytes()).hexdigest()
    original = package["app"]["certificate_sha256"]
    if fixture.kind == "CERT_MISMATCH":
        if leaf == original:
            raise ValueError("Certificate-negative App still uses candidate certificate")
    elif leaf != original:
        raise ValueError("DR-negative App unexpectedly changed its certificate")
    evidence = {"schema_version": 1, "scope": "update-identity-fixture-non-gui",
                "variant_id": fixture.variant_id, "state": "PASS",
                "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "pinned_ed25519_verified": True, "complete_app_codesign_verified": True,
                "candidate_designated_requirement_rejected": True,
                "info_bundle_id_matches_candidate": True,
                "advertised_info_version_build_match": True,
                "leaf_certificate_matches_candidate": leaf == original}
    target = output / "identity-layer-check.json"
    target.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    os.chmod(target, 0o600)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-manifest", required=True, type=Path)
    parser.add_argument("--update-zip", required=True, type=Path)
    parser.add_argument("--keys", required=True, type=Path)
    parser.add_argument("--variant", required=True, choices=KINDS)
    parser.add_argument("--owned-output", required=True, type=Path)
    args = parser.parse_args()
    package = json.loads(args.package_manifest.read_text(encoding="utf-8"))
    fixture = ValidationFixture(args.update_zip, package, args.owned_output, args.variant, args.keys)
    try:
        evidence = check(fixture, package, fixture.private)
        print(json.dumps({"variant_id": fixture.variant_id, "state": evidence["state"],
                          "evidence": str(fixture.private / "identity-layer-check.json")}))
        return 0
    finally:
        if not fixture.close():
            raise ValueError("Owned update source did not close")


if __name__ == "__main__":
    raise SystemExit(main())
