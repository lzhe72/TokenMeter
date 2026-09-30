"""Run real Swift endpoint configuration checks with macOS Command Line Tools."""
from pathlib import Path
import platform
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    if platform.system() != "Darwin":
        print("BLOCKED: Swift configuration checks require macOS")
        return 2
    with tempfile.TemporaryDirectory(prefix="tokenmeter-configuration-tests-") as temporary:
        binary = str(Path(temporary) / "configuration-tests")
        build = subprocess.run([
            "xcrun", "swiftc", "-swift-version", "5", "-D", "UITESTING",
            str(ROOT / "apps/macos/TokenMeter/Auth.swift"),
            str(ROOT / "tests/macos/EndpointConfigurationTests.swift"), "-o", binary,
        ], cwd=ROOT, timeout=180)
        if build.returncode:
            return build.returncode
        return subprocess.run([binary], cwd=ROOT, timeout=60).returncode


if __name__ == "__main__":
    raise SystemExit(main())
