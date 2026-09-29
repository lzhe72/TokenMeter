"""Short-lived CI code-signing identity for real Keychain-preserving upgrades.

This is an isolated development identity, never Developer ID or notarization.
Private files and keychain passwords are not written to release evidence.
"""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import shlex
import subprocess


class SigningIdentity:
    def __init__(self, private: Path):
        self.private = private
        self.private.mkdir(mode=0o700)
        self.keychain = private / "codesign.keychain-db"
        self.certificate = private / "codesign.pem"
        self.password = secrets.token_urlsafe(32)
        self.previous_keychains: list[str] | None = None
        self.keychain_created = False
        self.trust_attempted = False
        self.identity: str | None = None

    def _run(self, arguments: list[str], operation: str) -> str:
        result = subprocess.run(arguments, capture_output=True, text=True, check=False, timeout=60)
        if result.returncode:
            # Never print arguments or security/openssl output: some commands
            # accept the temporary password as a process argument.
            raise RuntimeError(f"Isolated code-signing {operation} failed ({result.returncode})")
        return result.stdout.strip()

    def prepare(self) -> str:
        if os.environ.get("GITHUB_ACTIONS") != "true" or not os.environ.get("RUNNER_TEMP"):
            raise RuntimeError("Temporary signing identity requires an isolated GitHub runner")
        self.previous_keychains = shlex.split(self._run(["security", "list-keychains", "-d", "user"], "read keychain list"))
        config = self.private / "codesign.cnf"
        config.write_text("[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=signing\n"
                          "[dn]\nCN=TokenMeter E2E " + secrets.token_hex(12) + "\n"
                          "[signing]\nbasicConstraints=critical,CA:FALSE\n"
                          "keyUsage=critical,digitalSignature\nextendedKeyUsage=critical,codeSigning\n")
        key = self.private / "codesign.key"
        p12 = self.private / "codesign.p12"
        self._run(["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-x509", "-days", "1", "-sha256",
                   "-config", str(config), "-keyout", str(key), "-out", str(self.certificate)], "create certificate")
        self._run(["openssl", "pkcs12", "-export", "-inkey", str(key), "-in", str(self.certificate),
                   "-out", str(p12), "-passout", "pass:"], "create private bundle")
        p12.chmod(0o600)
        self.keychain_created = True  # Also clean up partially successful creation.
        self._run(["security", "create-keychain", "-p", self.password, str(self.keychain)], "create keychain")
        self._run(["security", "set-keychain-settings", "-lut", "21600", str(self.keychain)], "keychain settings")
        self._run(["security", "unlock-keychain", "-p", self.password, str(self.keychain)], "unlock keychain")
        self._run(["security", "import", str(p12), "-k", str(self.keychain), "-P", "", "-T", "/usr/bin/codesign"], "import identity")
        self._run(["security", "set-key-partition-list", "-S", "apple-tool:,apple:,codesign:", "-s", "-k", self.password,
                   str(self.keychain)], "grant codesign access")
        self.trust_attempted = True
        self._run(["security", "add-trusted-cert", "-r", "trustRoot", "-p", "codeSign", "-k", str(self.keychain),
                   str(self.certificate)], "trust ephemeral code-signing certificate")
        self._run(["security", "list-keychains", "-d", "user", "-s", *self.previous_keychains, str(self.keychain)], "register keychain")
        fingerprint = self._run(["openssl", "x509", "-in", str(self.certificate), "-noout", "-fingerprint", "-sha1"], "certificate fingerprint")
        self.identity = fingerprint.split("=", 1)[1].replace(":", "").strip()
        if len(self.identity) != 40 or any(character not in "0123456789abcdefABCDEF" for character in self.identity):
            raise RuntimeError("Invalid code-signing certificate identity")
        identities = self._run(["security", "find-identity", "-v", "-p", "codesigning", str(self.keychain)], "verify identity")
        if self.identity.upper() not in identities.upper():
            raise RuntimeError("Ephemeral identity is not usable for code signing")
        return self.identity

    def close(self) -> None:
        errors = []
        actions = []
        if self.trust_attempted:
            actions.append((["security", "remove-trusted-cert", str(self.certificate)], "remove signing trust"))
        if self.previous_keychains is not None:
            actions.append((["security", "list-keychains", "-d", "user", "-s", *self.previous_keychains], "restore keychain list"))
        if self.keychain_created:
            actions.append((["security", "delete-keychain", str(self.keychain)], "delete signing keychain"))
        for arguments, operation in actions:
            try:
                self._run(arguments, operation)
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError("; ".join(errors))
        self.previous_keychains = None
        self.keychain_created = self.trust_attempted = False
