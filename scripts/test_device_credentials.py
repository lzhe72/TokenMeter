"""Compile and run the real Swift credential store tests with macOS CLT or Xcode.

This is a component check, never a substitute for the native product E2E gate.
"""
from pathlib import Path
import platform
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    if platform.system() != "Darwin":
        print("BLOCKED: Swift credential storage checks require macOS")
        return 2
    with tempfile.TemporaryDirectory(prefix="tokenmeter-storage-tests-") as temporary:
        binary = str(Path(temporary) / "credential-tests")
        build = subprocess.run([
            "xcrun", "swiftc", "-swift-version", "5", "-D", "UITESTING",
            str(ROOT / "apps/macos/TokenMeter/Auth.swift"),
            str(ROOT / "tests/macos/DeviceCredentialsTests.swift"), "-o", binary,
        ], cwd=ROOT)
        if build.returncode:
            return build.returncode
        return subprocess.run([binary], cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
