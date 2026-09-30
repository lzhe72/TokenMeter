"""Short-lived CI code-signing identity for real Keychain-preserving upgrades.

This is an isolated development identity, never Developer ID or notarization.
The self-signed identity stays in a private keychain; system trust is untouched.
Private files and keychain passwords are not written to release evidence.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import time


class SigningIdentity:
    def __init__(self, private: Path):
        self.private = private
        self.private.mkdir(mode=0o700)
        self.keychain = private / "codesign.keychain-db"
        self.certificate = private / "codesign.pem"
        self.password = secrets.token_urlsafe(32)
        self.bundle_password = secrets.token_urlsafe(32)
        self.bundle_password_file = private / "bundle-password"
        self.previous_keychains: list[str] | None = None
        self.keychain_created = False
        self.identity: str | None = None

    def _run(self, arguments: list[str], operation: str) -> str:
        started = time.monotonic()
        def progress(state: str, **details) -> None:
            print(json.dumps({"event": "fixture_operation", "fixture": "code_signing", "operation": operation,
                              "state": state, "elapsed_seconds": round(time.monotonic() - started, 3), **details}), flush=True)
        progress("STARTED")
        try:
            result = subprocess.run(arguments, capture_output=True, text=True, check=False, timeout=60)
        except subprocess.TimeoutExpired as exc:
            progress("TIMED_OUT")
            raise RuntimeError(f"Isolated code-signing {operation} timed out after 60 seconds") from exc
        except OSError as exc:
            progress("FAILED", errno=exc.errno)
            raise RuntimeError(f"Isolated code-signing {operation} unavailable (errno={exc.errno})") from exc
        if result.returncode:
            progress("FAILED", exit_code=result.returncode)
            # Never print arguments or security/openssl output: some commands
            # accept the temporary password as a process argument.
            raise RuntimeError(f"Isolated code-signing {operation} failed ({result.returncode})")
        progress("SUCCEEDED")
        return result.stdout.strip()

    def create_private_bundle(self) -> Path:
        """Create only owned files; importing remains guarded in prepare."""
        config = self.private / "codesign.cnf"
        config.write_text("[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=signing\n"
                          "[dn]\nCN=TokenMeter E2E " + secrets.token_hex(12) + "\n"
                          "[signing]\nbasicConstraints=critical,CA:FALSE\n"
                          "keyUsage=critical,digitalSignature\nextendedKeyUsage=critical,codeSigning\n")
        key = self.private / "codesign.key"
        p12 = self.private / "codesign.p12"
        self._run(["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-x509", "-days", "1", "-sha256",
                   "-config", str(config), "-keyout", str(key), "-out", str(self.certificate)], "create certificate")
        key.chmod(0o600)
        self.bundle_password_file.write_text(self.bundle_password + "\n")
        self.bundle_password_file.chmod(0o600)
        # Apple's PKCS12 importer requires interoperable legacy wrapping. This
        # changes this temporary encrypted container only; certificate and App
        # signatures remain RSA/SHA256 and update archives remain Ed25519.
        self._run(["openssl", "pkcs12", "-export", "-inkey", str(key), "-in", str(self.certificate),
                   "-keypbe", "PBE-SHA1-3DES", "-certpbe", "PBE-SHA1-3DES", "-macalg", "sha1",
                   "-out", str(p12), "-passout", "file:" + str(self.bundle_password_file)], "create private bundle")
        p12.chmod(0o600)
        return p12

    def prepare(self) -> str:
        if (os.environ.get("GITHUB_ACTIONS") != "true" or not os.environ.get("RUNNER_TEMP")
                or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted" or os.environ.get("RUNNER_OS") != "macOS"):
            raise RuntimeError("Temporary signing identity requires an isolated GitHub runner")
        self.previous_keychains = shlex.split(self._run(["security", "list-keychains", "-d", "user"], "read keychain list"))
        p12 = self.create_private_bundle()
        fingerprint = self._run(["openssl", "x509", "-in", str(self.certificate), "-noout", "-fingerprint", "-sha1"], "certificate fingerprint")
        self.identity = fingerprint.split("=", 1)[1].replace(":", "").strip()
        if len(self.identity) != 40 or any(character not in "0123456789abcdefABCDEF" for character in self.identity):
            raise RuntimeError("Invalid code-signing certificate identity")
        self.keychain_created = True  # Also clean up partially successful creation.
        self._run(["security", "create-keychain", "-p", self.password, str(self.keychain)], "create keychain")
        self._run(["security", "set-keychain-settings", "-lut", "21600", str(self.keychain)], "keychain settings")
        self._run(["security", "unlock-keychain", "-p", self.password, str(self.keychain)], "unlock keychain")
        self._run(["security", "import", str(p12), "-k", str(self.keychain), "-P", self.bundle_password,
                   "-T", "/usr/bin/codesign"], "import identity")
        self._run(["security", "set-key-partition-list", "-S", "apple-tool:,apple:,codesign:", "-s", "-k", self.password,
                   str(self.keychain)], "grant codesign access")
        self._run(["security", "list-keychains", "-d", "user", "-s", *self.previous_keychains, str(self.keychain)], "register keychain")
        # The -v filter requires a trusted certificate chain, which is not
        # necessary for a stable self-signed designated requirement. Prove that
        # this identity can sign and verify code without installing trust.
        identities = self._run(["security", "find-identity", "-p", "codesigning", str(self.keychain)], "find signing identity")
        if self.identity.upper() not in identities.upper():
            raise RuntimeError("Ephemeral signing identity is missing from its private keychain")
        probe_source = self.private / "identity-probe.c"
        probe_source.write_text("int main(void) { return 0; }\n")
        probe = self.private / "identity-probe"
        self._run(["xcrun", "clang", "-x", "c", str(probe_source), "-o", str(probe)], "build identity probe")
        self._run(["codesign", "--force", "--sign", self.identity, "--keychain", str(self.keychain),
                   "--timestamp=none", str(probe)], "sign identity probe")
        self._run(["codesign", "--verify", "--strict", str(probe)], "verify identity probe")
        return self.identity

    def close(self) -> None:
        errors = []
        actions = []
        if self.previous_keychains is not None:
            actions.append((["security", "list-keychains", "-d", "user", "-s", *self.previous_keychains], "restore keychain list"))
        if self.keychain_created and self.keychain.exists():
            actions.append((["security", "delete-keychain", str(self.keychain)], "delete signing keychain"))
        for arguments, operation in actions:
            try:
                self._run(arguments, operation)
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                errors.append(str(exc))
        if self.previous_keychains is not None:
            try:
                observed = shlex.split(self._run(["security", "list-keychains", "-d", "user"], "verify restored keychain list"))
                if observed != self.previous_keychains:
                    errors.append("Signing keychain search list was not restored")
                else:
                    self.previous_keychains = None
            except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
                errors.append(str(exc))
        if self.keychain_created and not self.keychain.exists():
            self.keychain_created = False
        elif self.keychain_created:
            errors.append("Isolated signing keychain still exists after cleanup")
        if errors:
            raise RuntimeError("; ".join(errors))
