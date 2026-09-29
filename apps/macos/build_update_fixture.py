#!/usr/bin/env python3
"""Build and EdDSA-sign an isolated higher-version UITesting app. Never publish it."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys
from urllib.parse import urlsplit


def real_path(value: str) -> Path:
    path = Path(value).absolute()
    if any(parent.is_symlink() for parent in [path, *path.parents]):
        raise ValueError("Symbolic-link input/output paths are not allowed")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("derived-data", "output", "feed-url", "public-key", "private-key-file", "api-url", "run-id", "build-version", "code-sign-identity", "signing-keychain"):
        parser.add_argument("--" + flag, required=True)
    args = parser.parse_args()
    try:
        if platform.system() != "Darwin":
            raise ValueError("A macOS host with full Xcode is required")
        selected = subprocess.run(["xcode-select", "-p"], text=True, capture_output=True)
        if selected.returncode != 0 or not selected.stdout.strip().endswith(".app/Contents/Developer"):
            raise ValueError("Full Xcode is not selected; build remains BLOCKED")
        architecture = platform.machine()
        if architecture not in ("arm64", "x86_64"):
            raise ValueError("The update fixture requires an arm64 or x86_64 macOS host")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_id) or not re.fullmatch(r"[1-9][0-9]*", args.build_version):
            raise ValueError("Invalid run ID or build version")
        if not re.fullmatch(r"[0-9A-Fa-f]{40}", args.code_sign_identity):
            raise ValueError("Updates require the same real test signing identity as the candidate, not ad-hoc signing")
        signing_keychain = real_path(args.signing_keychain)
        if not signing_keychain.is_file():
            raise ValueError("The isolated signing keychain is missing")
        feed = urlsplit(args.feed_url)
        if feed.scheme != "https" or not feed.hostname or feed.username or feed.password:
            raise ValueError("The fixture feed must use HTTPS without embedded credentials")
        api = urlsplit(args.api_url)
        if api.scheme != "https" and not (api.scheme == "http" and api.hostname in ("localhost", "127.0.0.1", "::1")):
            raise ValueError("The test API must use HTTPS or isolated loopback HTTP")
        if len(base64.b64decode(args.public_key, validate=True)) != 32:
            raise ValueError("Expected a 32-byte Ed25519 public key")
        private_key = real_path(args.private_key_file)
        if private_key.stat().st_uid != os.getuid() or private_key.stat().st_mode & 0o077:
            raise ValueError("The ephemeral signing key must be owned by this user with mode 0600")
        # Validate before calling Sparkle, whose malformed-input error can echo key text.
        if len(base64.b64decode(private_key.read_text().strip(), validate=True)) != 32:
            raise ValueError("Expected a base64 32-byte ephemeral Ed25519 seed")
        derived = real_path(args.derived_data)
        output = real_path(args.output)
        if output.exists() or derived.exists():
            raise ValueError("Refusing to overwrite an existing build or package directory")
        output.mkdir(parents=True, mode=0o700)
        project = Path(__file__).resolve().parent / "TokenMeter.xcodeproj"
        command = ["xcodebuild", "build", "-project", str(project), "-scheme", "TokenMeter",
                   "-configuration", "UITesting", "-destination", "platform=macOS,arch=" + architecture,
                   "-derivedDataPath", str(derived), "-disableAutomaticPackageResolution",
                   "CODE_SIGN_IDENTITY=" + args.code_sign_identity,
                   "OTHER_CODE_SIGN_FLAGS=--keychain " + shlex.quote(str(signing_keychain)),
                   "CURRENT_PROJECT_VERSION=" + args.build_version,
                   "TM_UPDATE_FEED_URL=" + args.feed_url, "TM_UPDATE_PUBLIC_KEY=" + args.public_key,
                   "TM_TEST_API_URL=" + args.api_url, "TM_TEST_RUN_ID=" + args.run_id]
        with (output / "build.log").open("w") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ValueError("Update package build failed; inspect the isolated build.log")
        app = derived / "Build/Products/UITesting/TokenMeter.app"
        if not app.is_dir():
            raise ValueError("Build produced no application bundle")
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        displayed = subprocess.run(["codesign", "-d", "-r-", str(app)], capture_output=True, text=True, check=True)
        requirements = [line for line in (displayed.stdout + displayed.stderr).splitlines() if line.startswith("designated =>")]
        if len(requirements) != 1 or "cdhash" in requirements[0]:
            raise ValueError("The update package lacks a stable signing identity requirement")
        archive = output / "update.zip"
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app), str(archive)], check=True)
        signers = [p for p in (derived / "SourcePackages/artifacts").rglob("sign_update") if p.is_file() and p.parent.name == "bin"]
        if len(signers) != 1:
            raise ValueError("Expected exactly one sign_update tool from the pinned Sparkle package")
        signed = subprocess.run([str(signers[0]), "--ed-key-file", str(private_key), "-p", str(archive)],
                                text=True, capture_output=True)
        if signed.returncode:
            raise ValueError("Sparkle signing failed; secret-bearing tool output was suppressed")
        signature = signed.stdout.strip()
        if len(base64.b64decode(signature, validate=True)) != 64:
            raise ValueError("Sparkle produced an invalid Ed25519 signature")
        verified = subprocess.run([str(signers[0]), "--ed-key-file", str(private_key), "--verify", str(archive), signature],
                                  capture_output=True)
        if verified.returncode:
            raise ValueError("Sparkle could not verify its generated archive signature")
        digest = hashlib.sha256()
        with archive.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        metadata = {"schema_version": 1, "signature": signature, "length": archive.stat().st_size,
                    "sha256": digest.hexdigest(), "build_version": args.build_version,
                    "sparkle_version": "2.10.0", "fixture_kind": "isolated_development_update",
                    "code_sign_identity": args.code_sign_identity, "designated_requirement": requirements[0],
                    "release_eligible": False}
        (output / "signature.json").write_text(json.dumps(metadata, indent=2) + "\n")
        print(json.dumps({"status": "BUILT", "output": str(output), "release_eligible": False}))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "BLOCKED" if "Xcode" in str(error) else "FAIL", "error": str(error), "release_eligible": False}))
        return 2 if "Xcode" in str(error) else 1


if __name__ == "__main__":
    sys.exit(main())
