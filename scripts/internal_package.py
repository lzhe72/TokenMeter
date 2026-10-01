"""Build one protected-master internal Universal DMG and its signed archives.

The manifest proves packaging only. Final-package E2E and the release gate must
validate these exact bytes before distribution. Secrets never enter artifacts.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.package_release_dmg import tree_sha256, file_sha256
from tests.e2e.code_signing import SigningIdentity

BUNDLE_ID = "org.tokenmeter.TokenMeter"
DEFAULT_FEED = "http://127.0.0.1:49177/appcast.xml"
DEFAULT_API = "http://127.0.0.1:49176"
ARCHITECTURES = ["arm64", "x86_64"]


class PackageError(ValueError):
    """A packaging input or observed artifact violates the release contract."""


class PackageBlocked(PackageError):
    """A required protected credential or execution environment is missing."""


def decode_secret(value, expected_length, label):
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError, binascii.Error):
        raise PackageError(f"Invalid {label} encoding") from None
    if len(raw) != expected_length:
        raise PackageError(f"Invalid {label} length")
    return raw


def validate_config(config):
    required = {"release_id", "version", "bundle_id", "minimum_macos", "architectures", "platform_matrix",
                "build", "upgrade_build", "update_feed_url", "update_public_key", "certificate_sha256"}
    if not isinstance(config, dict) or not required.issubset(config):
        raise PackageError("Incomplete internal release config")
    version = config["version"]
    rid = config["release_id"]
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise PackageError("Invalid release version")
    if not isinstance(rid, str) or not re.fullmatch(r"v" + re.escape(version) + r"-\d{8}T\d{6}Z", rid):
        raise PackageError("Release ID and version must match")
    try:
        datetime.strptime(rid.rsplit("-", 1)[1], "%Y%m%dT%H%M%SZ")
    except ValueError:
        raise PackageError("Invalid release timestamp") from None
    if (config["bundle_id"] != BUNDLE_ID or config["minimum_macos"] != "15.0"
            or config["architectures"] != ARCHITECTURES or config["update_feed_url"] != DEFAULT_FEED
            or config.get("api_url", DEFAULT_API) != DEFAULT_API
            or config.get("distribution_profile", "internal") != "internal"
            or config.get("signature_kind", "internal_self_signed") != "internal_self_signed"):
        raise PackageError("Internal scope, production defaults, or platform differs from approved config")
    expected = [{"runner": "macos-15", "macos_major": "15", "architecture": "arm64"},
                {"runner": "macos-15-intel", "macos_major": "15", "architecture": "x86_64"}]
    if config["platform_matrix"] != expected:
        raise PackageError("Expected the exact two macOS 15 platform entries")
    for name in ("build", "upgrade_build"):
        if isinstance(config[name], bool) or not re.fullmatch(r"[1-9][0-9]*", str(config[name])):
            raise PackageError("Build numbers must be positive decimal integers")
    if str(config["build"]) != "100" or str(config["upgrade_build"]) != "101":
        raise PackageError("The initial internal candidate and controlled update must be builds 100 and 101")
    decode_secret(config["update_public_key"], 32, "public key")
    if not isinstance(config["certificate_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", config["certificate_sha256"]):
        raise PackageError("Expected a pinned certificate DER SHA256")
    return config


def validate_ci(candidate_sha, environment=None):
    env = os.environ if environment is None else environment
    expected = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS",
                "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/master",
                "GITHUB_REF_PROTECTED": "true", "GITHUB_REPOSITORY": "lzhe72/TokenMeter"}
    if (not re.fullmatch(r"[0-9a-f]{40}", candidate_sha or "")
            or any(env.get(k) != v for k, v in expected.items()) or env.get("GITHUB_SHA") != candidate_sha
            or not env.get("RUNNER_TEMP")
            or not re.fullmatch(r"[1-9][0-9]*", env.get("GITHUB_RUN_ID", ""))
            or not re.fullmatch(r"[1-9][0-9]*", env.get("GITHUB_RUN_ATTEMPT", ""))
            or env.get("GITHUB_WORKFLOW_REF") != "lzhe72/TokenMeter/.github/workflows/internal-release.yml@refs/heads/master"):
        raise PackageError("Internal packaging requires this protected master workflow and its exact candidate SHA")
    return {"repository": env["GITHUB_REPOSITORY"], "workflow": env["GITHUB_WORKFLOW_REF"],
            "run_id": env["GITHUB_RUN_ID"], "run_attempt": env["GITHUB_RUN_ATTEMPT"],
            "sha": candidate_sha, "event_name": env["GITHUB_EVENT_NAME"], "ref": env["GITHUB_REF"]}


def child_environment(environment=None):
    return {k: v for k, v in (os.environ if environment is None else environment).items()
            if not k.startswith(("TM_INTERNAL_", "TM_TEST_", "TOKENMETER_"))}


def run(arguments, label, *, cwd=None, log=None, timeout=120):
    """Run only fixed tools; never expose command arguments or raw failing output."""
    try:
        if log:
            with Path(log).open("x") as stream:
                result = subprocess.run(arguments, cwd=cwd, env=child_environment(), stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=timeout, check=False)
            output = ""
        else:
            result = subprocess.run(arguments, cwd=cwd, env=child_environment(), capture_output=True,
                                    text=True, timeout=timeout, check=False)
            output = result.stdout + "\n" + result.stderr
    except (OSError, subprocess.TimeoutExpired):
        raise PackageError(f"{label} could not complete") from None
    if result.returncode:
        raise PackageError(f"{label} failed (exit {result.returncode})")
    return output.strip()


def regular_path(path):
    path = Path(os.path.abspath(path))
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise PackageError("Symbolic-link input/output paths are refused")
    return path


def prepare_output(path):
    path = regular_path(path)
    if os.path.lexists(path) or not path.parent.is_dir():
        raise PackageError("Output must be a new directory in an existing parent")
    path.mkdir(mode=0o700)
    return path


def validate_app_info(app, config, build):
    app = regular_path(app)
    if app.name != "TokenMeter.app" or not app.is_dir():
        raise PackageError("Expected a regular production TokenMeter.app")
    info_path = app / "Contents/Info.plist"
    if info_path.is_symlink() or not info_path.is_file():
        raise PackageError("App Info.plist is not a regular file")
    try:
        info = plistlib.loads(info_path.read_bytes())
    except (ValueError, TypeError, plistlib.InvalidFileException):
        raise PackageError("Unreadable App Info.plist") from None
    if (not isinstance(info, dict) or info.get("CFBundleIdentifier") != BUNDLE_ID
            or info.get("CFBundlePackageType") != "APPL" or info.get("CFBundleExecutable") != "TokenMeter"
            or info.get("CFBundleVersion") != str(build) or info.get("CFBundleShortVersionString") != config["version"]
            or info.get("LSMinimumSystemVersion") != config["minimum_macos"]
            or info.get("SUFeedURL") != "" or info.get("SUPublicEDKey") != config["update_public_key"]
            or info.get("SUVerifyUpdateBeforeExtraction") is not True
            or any(str(key).startswith(("TMTest", "TM_TEST_")) for key in info)):
        raise PackageError("App contains a wrong production identity, version, default, key, or test setting")
    ats = info.get("NSAppTransportSecurity", {})
    domains = ats.get("NSExceptionDomains", {})
    if (set(ats) != {"NSExceptionDomains"} or set(domains) != {"127.0.0.1", "localhost", "::1"}
            or any(entry != {"NSExceptionAllowsInsecureHTTPLoads": True} for entry in domains.values())):
        raise PackageError("Only exact loopback ATS exceptions are allowed")
    return {"bundle_id": BUNDLE_ID, "version": config["version"], "build": str(build),
            "minimum_macos": config["minimum_macos"], "public_key": config["update_public_key"]}


def validate_signature(details, requirement, certificate_sha256, config):
    identifier = re.search(r"^Identifier=(.+)$", details, re.M)
    flags = re.search(r"\bflags=0x([0-9A-Fa-f]+)", details)
    requirements = [line for line in requirement.splitlines() if line.startswith("designated =>")]
    if (identifier is None or identifier.group(1) != BUNDLE_ID or flags is None
            or int(flags.group(1), 16) & (0x2 | 0x2000 | 0x10000)
            or len(requirements) != 1 or "cdhash" in requirements[0] or "certificate" not in requirements[0]
            or certificate_sha256 != config["certificate_sha256"]):
        raise PackageError("Internal App needs the pinned non-ad-hoc signature, stable requirement, and no Team-ID library validation flags")
    return {"certificate_sha256": certificate_sha256, "signature_kind": "internal_self_signed",
            "designated_requirement": requirements[0]}


def verify_app(app, config, build, scratch):
    """Read production metadata/signature from actual bytes; also used by parent gate."""
    info = validate_app_info(app, config, build)
    executable = Path(app) / "Contents/MacOS/TokenMeter"
    binary = executable.read_bytes()
    if any(marker in binary for marker in (b"TM_TEST_RUN_ID", b"TM_TEST_API_URL", b"TM_TEST_CREDENTIALS_DIR", b"TMTestCredentialsDirectory")):
        raise PackageError("Production executable includes test-environment lookup strings")
    archs = run(["lipo", "-archs", str(executable)], "Read executable architectures").split()
    if sorted(archs) != sorted(config["architectures"]):
        raise PackageError("The production executable must contain both declared architectures")
    run(["codesign", "--verify", "--deep", "--strict", str(app)], "Verify production code signature")
    details = run(["codesign", "--display", "--verbose=4", str(app)], "Inspect production code signature")
    requirement = run(["codesign", "-d", "-r-", str(app)], "Inspect stable code requirement")
    certificate_prefix = Path(scratch) / ("certificate-" + str(build) + "-")
    run(["codesign", "--display", "--extract-certificates", str(certificate_prefix), str(app)], "Extract signing certificate")
    certificate = Path(str(certificate_prefix) + "0")
    if not certificate.is_file() or certificate.is_symlink():
        raise PackageError("Code signature has no signing certificate")
    signature = validate_signature(details, requirement, file_sha256(certificate), config)
    import hashlib
    identity = hashlib.sha1(certificate.read_bytes()).hexdigest().upper()
    return {**info, **signature, "architectures": ARCHITECTURES, "code_sign_identity": identity,
            "tree_sha256": tree_sha256(Path(app))}


def artifact(path, base):
    path = Path(path); base = Path(base)
    if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
        raise PackageError("Artifact must be a non-empty regular file")
    try:
        relative = path.relative_to(base).as_posix()
    except ValueError:
        raise PackageError("Artifact is outside its output directory") from None
    return {"path": relative, "sha256": file_sha256(path), "bytes": path.stat().st_size}


class StableSigningIdentity(SigningIdentity):
    def __init__(self, private, config):
        super().__init__(private)
        self.config = config

    def _run(self, arguments, operation):
        return run(arguments, "Private signing: " + operation, timeout=60)

    def create_private_bundle(self):
        value = os.environ.get("TM_INTERNAL_P12_BASE64", "")
        if not value or not os.environ.get("TM_INTERNAL_P12_PASSWORD"):
            raise PackageBlocked("Stable code-signing environment credentials are missing")
        try:
            content = base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error):
            raise PackageError("Invalid signing bundle encoding") from None
        password = os.environ.get("TM_INTERNAL_P12_PASSWORD", "")
        if not 256 <= len(content) <= 65536 or not password or "\n" in password or "\r" in password:
            raise PackageError("Missing or invalid stable signing credentials")
        self.bundle_password = password
        p12 = self.private / "codesign.p12"
        p12.write_bytes(content); p12.chmod(0o600)
        self.bundle_password_file.write_text(password + "\n"); self.bundle_password_file.chmod(0o600)
        self._run(["openssl", "pkcs12", "-in", str(p12), "-passin", "file:" + str(self.bundle_password_file),
                   "-clcerts", "-nokeys", "-out", str(self.certificate)], "extract public certificate")
        der = self.private / "certificate.der"
        self._run(["openssl", "x509", "-in", str(self.certificate), "-outform", "DER", "-out", str(der)], "encode public certificate")
        if file_sha256(der) != self.config["certificate_sha256"]:
            raise PackageError("Stable signing certificate does not match public config")
        return p12


def verify_ed_signature(archive, signature, public_key, scratch):
    decode_secret(signature, 64, "archive signature")
    decode_secret(public_key, 32, "public key")
    source = Path(scratch) / "verify-update-signature.swift"
    source.write_text('import Foundation\nimport CryptoKit\n'
                      'let key = try Curve25519.Signing.PublicKey(rawRepresentation: Data(base64Encoded: CommandLine.arguments[1])!)\n'
                      'let signature = Data(base64Encoded: CommandLine.arguments[2])!\n'
                      'let archive = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[3]))\n'
                      'if !key.isValidSignature(signature, for: archive) { exit(1) }\n')
    run(["xcrun", "swift", str(source), public_key, signature, str(archive)], "Verify Ed25519 archive signature")


def prepare_seed(private, config):
    if not os.environ.get("TM_INTERNAL_ED25519_SEED"):
        raise PackageBlocked("Stable update-signing environment credential is missing")
    raw = decode_secret(os.environ.get("TM_INTERNAL_ED25519_SEED", ""), 32, "Ed25519 seed")
    seed = private / "update-seed"
    seed.write_text(base64.b64encode(raw).decode() + "\n"); seed.chmod(0o600)
    source = private / "derive-public.swift"
    source.write_text('import Foundation\nimport CryptoKit\n'
                      'let data = try String(contentsOfFile: CommandLine.arguments[1]).trimmingCharacters(in: .whitespacesAndNewlines)\n'
                      'let key = try Curve25519.Signing.PrivateKey(rawRepresentation: Data(base64Encoded: data)!)\n'
                      'print(key.publicKey.rawRepresentation.base64EncodedString())\n')
    public = run(["xcrun", "swift", str(source), str(seed)], "Derive stable update public key")
    if public != config["update_public_key"]:
        raise PackageError("Stable update seed does not match public config")
    return seed


def build_app(root, private, output, config, build, signing):
    derived = private / ("build-" + str(build))
    command = ["xcodebuild", "build", "-project", str(root / "apps/macos/TokenMeter.xcodeproj"),
               "-scheme", "TokenMeter", "-configuration", "Release", "-destination", "generic/platform=macOS",
               "-derivedDataPath", str(derived), "-disableAutomaticPackageResolution",
               "CODE_SIGN_IDENTITY=" + signing.identity, "CODE_SIGN_STYLE=Manual",
               "OTHER_CODE_SIGN_FLAGS=--keychain " + shlex.quote(str(signing.keychain)) + " --timestamp=none",
               "ARCHS=arm64 x86_64", "ONLY_ACTIVE_ARCH=NO", "MACOSX_DEPLOYMENT_TARGET=15.0",
               "ENABLE_HARDENED_RUNTIME=NO", "SWIFT_ACTIVE_COMPILATION_CONDITIONS=",
               "CURRENT_PROJECT_VERSION=" + str(build), "MARKETING_VERSION=" + config["version"],
               "TM_UPDATE_FEED_URL=", "TM_UPDATE_PUBLIC_KEY=" + config["update_public_key"]]
    run(command, "Build production Universal App", cwd=root, log=output / ("build-" + str(build) + ".log"), timeout=1800)
    app = derived / "Build/Products/Release/TokenMeter.app"
    info = verify_app(app, config, build, private)
    if info["code_sign_identity"].upper() != signing.identity.upper():
        raise PackageError("Built App is not signed by this stable identity")
    return app, info, derived


def make_archive(app, path, seed, signer, config, scratch):
    run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app), str(path)], "Create signed update archive")
    signature = run([str(signer), "--ed-key-file", str(seed), "-p", str(path)], "Sign update archive")
    decode_secret(signature, 64, "archive signature")
    verify_ed_signature(path, signature, config["update_public_key"], scratch)
    return signature


def server_archive(root, config_path, output):
    inputs = [p for p in (root / "server").rglob("*.py") if "__pycache__" not in p.parts]
    inputs += list((root / "server").glob("requirements*.txt"))
    inputs += [root / "scripts/bootstrap_sqlite.py", root / "scripts/local_distribution.py",
               root / "docs/releases/02-installation.md", config_path]
    if any(not p.is_file() or p.is_symlink() for p in inputs):
        raise PackageError("Server asset lacks required source, startup program, config, or installation instructions")
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(inputs)):
            if run(["git", "ls-files", "--error-unmatch", str(path.relative_to(root))], "Check server input is tracked", cwd=root) == "":
                raise PackageError("Server input is not tracked")
            archive.write(path, path.relative_to(root).as_posix())
    return sorted(p.relative_to(root).as_posix() for p in set(inputs))


def validate_dmg_layout(mount, installation):
    """Only intentional distribution content may be present at the DMG root."""
    mount = Path(mount)
    if {entry.name for entry in mount.iterdir()} != {"TokenMeter.app", "Applications", "INSTALLATION.txt"}:
        raise PackageError("DMG must contain only the App, Applications link, and installation instructions")
    app = mount / "TokenMeter.app"
    if app.is_symlink() or not app.is_dir():
        raise PackageError("DMG App must be a regular bundle directory")
    destination = mount / "Applications"
    if not destination.is_symlink() or os.readlink(destination) != "/Applications":
        raise PackageError("DMG lacks Applications destination link")
    instructions = mount / "INSTALLATION.txt"
    if instructions.is_symlink() or not instructions.is_file() or instructions.read_bytes() != Path(installation).read_bytes():
        raise PackageError("DMG installation instructions differ from source")


def make_dmg(app, output, private, config, app_info, installation):
    stage = private / "dmg-stage"; stage.mkdir()
    run(["ditto", str(app), str(stage / "TokenMeter.app")], "Stage final App")
    if tree_sha256(stage / "TokenMeter.app") != app_info["tree_sha256"]:
        raise PackageError("Staging changed the production App")
    (stage / "Applications").symlink_to("/Applications")
    shutil.copyfile(installation, stage / "INSTALLATION.txt")
    run(["hdiutil", "create", "-srcfolder", str(stage), "-volname", "TokenMeter", "-format", "UDZO", str(output)], "Create internal DMG", timeout=300)
    run(["hdiutil", "verify", str(output)], "Verify internal DMG", timeout=300)
    mount = private / "dmg-mount"; mount.mkdir()
    run(["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", str(mount), str(output)], "Mount internal DMG", timeout=120)
    try:
        validate_dmg_layout(mount, installation)
        observed = verify_app(mount / "TokenMeter.app", config, config["build"], private / "mounted-signature")
        if observed != app_info:
            raise PackageError("The mounted final App differs from the signed production App")
    finally:
        run(["hdiutil", "detach", str(mount)], "Detach internal DMG", timeout=120)


def package(config_path, output, candidate_sha):
    started = datetime.now(timezone.utc).isoformat()
    ci = validate_ci(candidate_sha)
    if sys.platform != "darwin":
        raise PackageBlocked("macOS with complete Xcode is required")
    config_path = regular_path(config_path)
    if not config_path.is_file():
        raise PackageError("Release config does not exist")
    config = validate_config(json.loads(config_path.read_text()))
    config_digest = file_sha256(config_path)
    head = run(["git", "rev-parse", "HEAD"], "Read candidate HEAD", cwd=ROOT)
    dirty = run(["git", "status", "--porcelain"], "Check clean candidate", cwd=ROOT)
    if head != candidate_sha or dirty:
        raise PackageError("Packaging requires the clean exact candidate checkout")
    run(["git", "ls-files", "--error-unmatch", str(config_path.relative_to(ROOT))], "Check tracked release config", cwd=ROOT)
    selected = run(["xcode-select", "-p"], "Read Xcode path")
    if not selected.endswith(".app/Contents/Developer"):
        raise PackageBlocked("Complete Xcode is not selected")
    output = prepare_output(output)
    result = None
    with tempfile.TemporaryDirectory(prefix="tokenmeter-internal-signing-", dir=Path(os.environ["RUNNER_TEMP"]).resolve()) as work:
        private = Path(work); private.chmod(0o700)
        signing = StableSigningIdentity(private / "identity", config)
        try:
            signing.prepare()
            seed = prepare_seed(private, config)
            app, app_info, derived = build_app(ROOT, private, output, config, config["build"], signing)
            update, update_info, _ = build_app(ROOT, private, output, config, config["upgrade_build"], signing)
            if app_info["designated_requirement"] != update_info["designated_requirement"]:
                raise PackageError("Candidate and higher version have different signing requirements")
            signers = [p for p in (derived / "SourcePackages/artifacts").rglob("sign_update") if p.is_file() and p.parent.name == "bin"]
            if len(signers) != 1:
                raise PackageError("Expected one signing tool from pinned Sparkle")
            candidate_zip = output / "candidate.zip"; update_zip = output / "update.zip"
            candidate_signature = make_archive(app, candidate_zip, seed, signers[0], config, private)
            update_signature = make_archive(update, update_zip, seed, signers[0], config, private)
            dmg = output / ("TokenMeter-" + config["release_id"] + "-internal.dmg")
            (private / "mounted-signature").mkdir()
            make_dmg(app, dmg, private, config, app_info, ROOT / "docs/releases/02-installation.md")
            server_zip = output / "server.zip"
            server_files = server_archive(ROOT, config_path, server_zip)
            if tree_sha256(app) != app_info["tree_sha256"] or tree_sha256(update) != update_info["tree_sha256"]:
                raise PackageError("A production App changed while packaging")
            if (file_sha256(config_path) != config_digest
                    or run(["git", "rev-parse", "HEAD"], "Recheck candidate HEAD", cwd=ROOT) != candidate_sha
                    or run(["git", "status", "--porcelain"], "Recheck clean candidate", cwd=ROOT)):
                raise PackageError("Source candidate or release config changed during packaging")
            result = {"schema_version": 1, "release_id": config["release_id"], "distribution_profile": "internal",
                      "candidate_sha": candidate_sha, "config_sha256": config_digest, "ci": ci,
                      "artifacts": {"dmg": artifact(dmg, output), "candidate_zip": artifact(candidate_zip, output),
                                    "update_zip": artifact(update_zip, output), "server_zip": artifact(server_zip, output)},
                      "app": app_info, "update_app": update_info,
                      "signatures": {"candidate_ed_signature": candidate_signature, "update_ed_signature": update_signature},
                      "server_source_files": server_files, "started_at": started, "release_eligible": False}
        finally:
            signing.close()
    if result is None:
        raise PackageError("Packaging did not produce its complete manifest")
    result["cleanup_completed"] = True
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    with (output / "package-manifest.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True); stream.write("\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-sha", required=True)
    args = parser.parse_args(argv)
    try:
        result = package(args.config, args.output, args.candidate_sha)
    except PackageBlocked as error:
        print(json.dumps({"state": "BLOCKED", "reason": str(error), "release_eligible": False}))
        return 2
    except PackageError as error:
        print(json.dumps({"state": "FAIL", "reason": str(error), "release_eligible": False}))
        return 1
    except (OSError, RuntimeError, ValueError):
        # Never echo unclassified exceptions that could carry private inputs.
        print(json.dumps({"state": "FAIL", "reason": "Internal package preparation or cleanup failed; no publishable manifest was issued", "release_eligible": False}))
        return 1
    print(json.dumps({"state": "PACKAGED", "manifest": str(args.output / "package-manifest.json"),
                      "candidate_sha": result["candidate_sha"], "release_eligible": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
