"""Package an already signed Release app as a notarized, stapled DMG.

The Keychain profile must be provisioned by the protected release environment.
This program never accepts a password or private key on its command line, and
its report is packaging evidence only, not a product E2E or release passport.
"""

import argparse
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit


PRODUCTION_BUNDLE_ID = "org.tokenmeter.TokenMeter"
RUNTIME_FLAG = 0x10000
ADHOC_FLAG = 0x2


class PackagingError(Exception):
    """The input or final package failed a required check."""


class PackagingBlocked(PackagingError):
    """A required local tool or notary service is unavailable."""


def run_command(args, label, *, blocked_on_failure=False, stdout_only=False):
    """Capture tool output privately; never echo a credential-bearing error."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
    except OSError as error:
        raise PackagingBlocked(f"{label} could not start") from error
    if result.returncode:
        failure = PackagingBlocked if blocked_on_failure else PackagingError
        raise failure(f"{label} failed (exit {result.returncode})")
    return result.stdout if stdout_only else result.stdout + "\n" + result.stderr


def require_tools(*names):
    if sys.platform != "darwin":
        raise PackagingBlocked("macOS is required")
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise PackagingBlocked("Required macOS tools are unavailable: " + ", ".join(missing))


def tree_sha256(directory):
    """Stable digest of paths, file contents, and symlink targets in an app."""
    digest = hashlib.sha256()
    for entry in sorted(directory.rglob("*")):
        relative = entry.relative_to(directory).as_posix()
        digest.update(relative.encode("utf-8") + b"\0")
        if entry.is_symlink():
            digest.update(b"link\0" + os.readlink(entry).encode("utf-8") + b"\0")
        elif entry.is_file():
            digest.update(b"file\0")
            with entry.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
        elif entry.is_dir():
            digest.update(b"dir\0")
        else:
            raise PackagingError(f"Unsupported app entry: {relative}")
    return digest.hexdigest()


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_app_info(app):
    if not app.is_absolute() or app.is_symlink() or app.name != "TokenMeter.app" or not app.is_dir():
        raise PackagingError("Input must be an absolute TokenMeter.app directory, not a symlink")
    try:
        with (app / "Contents" / "Info.plist").open("rb") as stream:
            info = plistlib.load(stream)
    except (OSError, ValueError, TypeError) as error:
        raise PackagingError("The app Info.plist is unreadable") from error
    if info.get("CFBundleIdentifier") != PRODUCTION_BUNDLE_ID:
        raise PackagingError("A production TokenMeter bundle is required; UITesting builds are refused")
    if info.get("CFBundlePackageType") != "APPL":
        raise PackagingError("The input is not an application bundle")
    version = info.get("CFBundleShortVersionString")
    build = info.get("CFBundleVersion")
    if not isinstance(version, str) or not version.strip() or not isinstance(build, str) or not build.strip():
        raise PackagingError("App version and build must be set")
    feed = info.get("SUFeedURL")
    if not isinstance(feed, str) or not feed.strip():
        raise PackagingError("The production Sparkle update feed is empty")
    try:
        parsed = urlsplit(feed)
        hostname = parsed.hostname
        parsed.port
    except ValueError as error:
        raise PackagingError("The production Sparkle update feed URL is malformed") from error
    if (parsed.scheme != "https" or not hostname or parsed.username or parsed.password
            or parsed.fragment or hostname.lower() in {"localhost", "127.0.0.1", "::1"}):
        raise PackagingError("The production Sparkle update feed must be a remote HTTPS URL")
    key = info.get("SUPublicEDKey")
    if not isinstance(key, str) or not key.strip():
        raise PackagingError("The production Sparkle public key is empty")
    try:
        decoded_key = base64.b64decode(key, validate=True)
    except (ValueError, binascii.Error) as error:
        raise PackagingError("The Sparkle public key is invalid base64") from error
    if len(decoded_key) != 32:
        raise PackagingError("The Sparkle Ed25519 public key must be 32 bytes")
    return {"bundle_id": PRODUCTION_BUNDLE_ID, "version": version, "build": build,
            "update_feed_sha256": hashlib.sha256(feed.encode("utf-8")).hexdigest(),
            "update_public_key_sha256": hashlib.sha256(decoded_key).hexdigest()}


def parse_signature(details, expected_identifier):
    identifier = re.search(r"^Identifier=(.+)$", details, re.MULTILINE)
    team = re.search(r"^TeamIdentifier=([A-Z0-9]{10})$", details, re.MULTILINE)
    flags = re.search(r"\bflags=0x([0-9a-fA-F]+)", details)
    authorities = re.findall(r"^Authority=(.+)$", details, re.MULTILINE)
    timestamp = re.search(r"^Timestamp=(.+)$", details, re.MULTILINE)
    if identifier is None or identifier.group(1) != expected_identifier:
        raise PackagingError("The code signature identifier does not match the production bundle")
    if (team is None or flags is None or timestamp is None
            or timestamp.group(1).strip().lower() in {"none", "not set"}):
        raise PackagingError("The code signature lacks a team, flags, or secure timestamp")
    flags_value = int(flags.group(1), 16)
    if flags_value & ADHOC_FLAG or not flags_value & RUNTIME_FLAG:
        raise PackagingError("The app requires a non-ad-hoc hardened runtime signature")
    if (len(authorities) < 3 or not authorities[0].startswith("Developer ID Application: ")
            or not authorities[1].startswith("Developer ID Certification Authority")
            or authorities[2] != "Apple Root CA"
            or not authorities[0].endswith("(" + team.group(1) + ")")):
        raise PackagingError("The app requires a Developer ID Application certificate chain")
    return {"team_id": team.group(1), "authority": authorities[0],
            "identifier": identifier.group(1)}


def verify_app_signature(app):
    run_command(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)],
                "App code signature verification")
    details = run_command(["codesign", "--display", "--verbose=4", str(app)],
                          "App code signature inspection")
    return parse_signature(details, PRODUCTION_BUNDLE_ID)


def preflight(app):
    require_tools("codesign")
    app = Path(app)
    info = read_app_info(app)
    signature = verify_app_signature(app)
    return {**info, **signature, "app_tree_sha256": tree_sha256(app)}


def verify_dmg_signature(dmg, app_signature):
    run_command(["codesign", "--verify", "--strict", "--verbose=2", str(dmg)],
                "DMG code signature verification")
    details = run_command(["codesign", "--display", "--verbose=4", str(dmg)],
                          "DMG code signature inspection")
    authorities = re.findall(r"^Authority=(.+)$", details, re.MULTILINE)
    team = re.search(r"^TeamIdentifier=([A-Z0-9]{10})$", details, re.MULTILINE)
    timestamp = re.search(r"^Timestamp=(.+)$", details, re.MULTILINE)
    if (team is None or team.group(1) != app_signature["team_id"] or len(authorities) < 3
            or timestamp is None or timestamp.group(1).strip().lower() in {"none", "not set"}
            or authorities[0] != app_signature["authority"]
            or not authorities[1].startswith("Developer ID Certification Authority")
            or authorities[2] != "Apple Root CA"):
        raise PackagingError("DMG and app Developer ID signing identities differ")


def notarize(dmg, profile):
    submission = run_command(
        ["xcrun", "notarytool", "submit", str(dmg), "--keychain-profile", profile,
         "--wait", "--timeout", "2h", "--output-format", "json"],
        "Notarization submission", blocked_on_failure=True, stdout_only=True)
    try:
        submitted = json.loads(submission)
        submission_id = submitted["id"]
        status = submitted["status"]
    except (ValueError, KeyError, TypeError) as error:
        raise PackagingError("Notarization returned no parseable final status") from error
    if not isinstance(submission_id, str) or not submission_id:
        raise PackagingError("Notarization returned no submission ID")
    if status != "Accepted":
        raise PackagingError("Notarization was not accepted")
    confirmation = run_command(
        ["xcrun", "notarytool", "info", submission_id, "--keychain-profile", profile,
         "--output-format", "json"],
        "Notarization status confirmation", blocked_on_failure=True, stdout_only=True)
    try:
        confirmed = json.loads(confirmation)
    except ValueError as error:
        raise PackagingError("Notarization confirmation is not valid JSON") from error
    if confirmed.get("id") != submission_id or confirmed.get("status") != "Accepted":
        raise PackagingError("Notarization confirmation does not match the accepted submission")
    return submission_id


def verify_image_contents(dmg, mount, app_sha256, app_signature):
    run_command(["hdiutil", "verify", str(dmg)], "DMG integrity verification")
    mount.mkdir()
    run_command(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint",
                 str(mount), str(dmg)], "DMG mount")
    check_error = None
    try:
        packaged_app = mount / "TokenMeter.app"
        applications = mount / "Applications"
        if not packaged_app.is_dir() or packaged_app.is_symlink():
            raise PackagingError("The mounted DMG lacks a regular TokenMeter.app")
        if not applications.is_symlink() or os.readlink(applications) != "/Applications":
            raise PackagingError("The mounted DMG lacks its Applications link")
        if tree_sha256(packaged_app) != app_sha256:
            raise PackagingError("The mounted app differs from the signed source app")
        if verify_app_signature(packaged_app) != app_signature:
            raise PackagingError("The mounted app signing identity differs from the source")
    except Exception as error:
        check_error = error
    try:
        run_command(["hdiutil", "detach", str(mount)], "DMG detach")
    except PackagingError as error:
        if check_error is None:
            check_error = error
    if check_error is not None:
        raise check_error


def new_output_path(path, suffix):
    path = Path(path)
    if not path.is_absolute() or path.suffix.lower() != suffix or not path.parent.is_dir():
        raise PackagingError(f"Output must be an absolute new {suffix} path in an existing directory")
    if os.path.lexists(path):
        raise PackagingError("Output already exists")
    return path


def publish(dmg, output, report_data, report):
    """Only expose the package after every check; create both outputs exclusively."""
    with tempfile.TemporaryDirectory(prefix=".tokenmeter-report-", dir=report.parent) as directory:
        staged_report = Path(directory) / "report.json"
        staged_report.write_text(json.dumps(report_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.link(dmg, output)
        try:
            os.link(staged_report, report)
        except OSError:
            if output.stat().st_ino == dmg.stat().st_ino:
                output.unlink()
            raise


def package(app, output, report, profile, signing_identity):
    if not profile or not signing_identity:
        raise PackagingBlocked("A Keychain notary profile and Developer ID signing identity are required")
    output = new_output_path(output, ".dmg")
    report = new_output_path(report, ".json")
    if output == report:
        raise PackagingError("DMG and report paths must differ")
    app = Path(app)
    source = preflight(app)
    if signing_identity != source["authority"]:
        raise PackagingError("The DMG signing identity must exactly match the app Developer ID authority")
    source_directory = app.resolve(strict=True)
    for destination in (output, report):
        parent = destination.parent.resolve(strict=True)
        if parent == source_directory or source_directory in parent.parents:
            raise PackagingError("DMG and report must be written outside the source app")
    require_tools("ditto", "hdiutil", "spctl", "xcrun")
    run_command(["xcrun", "--find", "notarytool"], "Notary tool lookup", blocked_on_failure=True)
    run_command(["xcrun", "--find", "stapler"], "Stapler tool lookup", blocked_on_failure=True)
    app_sha256 = source["app_tree_sha256"]
    signature = {key: source[key] for key in ("team_id", "authority", "identifier")}
    with tempfile.TemporaryDirectory(prefix=".tokenmeter-release-", dir=output.parent) as directory:
        scratch = Path(directory)
        stage = scratch / "stage"
        stage.mkdir()
        candidate = scratch / "candidate.dmg"
        run_command(["ditto", str(app), str(stage / "TokenMeter.app")], "App staging")
        if tree_sha256(stage / "TokenMeter.app") != app_sha256:
            raise PackagingError("Staged app differs from the signed source app")
        (stage / "Applications").symlink_to("/Applications")
        run_command(["hdiutil", "create", "-srcfolder", str(stage), "-volname", "TokenMeter",
                     "-format", "UDZO", str(candidate)], "DMG creation")
        run_command(["hdiutil", "verify", str(candidate)], "DMG integrity verification")
        run_command(["codesign", "--sign", signing_identity, "--timestamp", str(candidate)],
                    "DMG Developer ID signing")
        verify_dmg_signature(candidate, signature)
        submitted_sha256 = file_sha256(candidate)
        submission_id = notarize(candidate, profile)
        if file_sha256(candidate) != submitted_sha256:
            raise PackagingError("The DMG changed after notarization submission")
        run_command(["xcrun", "stapler", "staple", str(candidate)], "Notarization ticket stapling")
        run_command(["xcrun", "stapler", "validate", str(candidate)], "Stapled ticket verification")
        verify_dmg_signature(candidate, signature)
        gatekeeper = run_command(
            ["spctl", "--assess", "--type", "open", "--context", "context:primary-signature",
             "--verbose", str(candidate)], "Gatekeeper DMG assessment")
        if "source=Notarized Developer ID" not in gatekeeper:
            raise PackagingError("Gatekeeper did not report a notarized Developer ID DMG")
        verify_image_contents(candidate, scratch / "mount", app_sha256, signature)
        if tree_sha256(app) != app_sha256:
            raise PackagingError("The source app changed during packaging")
        result = {"kind": "formal-dmg-packaging-evidence", "release_eligible": False,
                  "app_bundle": app.name, "app_tree_sha256": app_sha256,
                  "dmg_file": output.name, "dmg_sha256": file_sha256(candidate),
                  "dmg_bytes": candidate.stat().st_size,
                  "bundle_id": source["bundle_id"], "version": source["version"],
                  "build": source["build"], "team_id": source["team_id"],
                  "developer_id_authority": source["authority"],
                  "update_feed_sha256": source["update_feed_sha256"],
                  "update_public_key_sha256": source["update_public_key_sha256"],
                  "notarization": {"submission_id": submission_id, "status": "Accepted",
                                   "dmg_ticket_stapled_and_verified": True,
                                   "gatekeeper_source": "Notarized Developer ID"}}
        publish(candidate, output, result, report)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("preflight", help="Inspect an existing signed Release app only")
    check.add_argument("--app", type=Path, required=True)
    build = commands.add_parser("package", help="Sign, notarize, staple, and verify a new DMG")
    build.add_argument("--app", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--report", type=Path, required=True)
    build.add_argument("--notary-profile", required=True,
                       help="Name of an existing notarytool Keychain profile; never a password")
    build.add_argument("--signing-identity", required=True,
                       help="Exact Developer ID Application authority shown by codesign")
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = {"kind": "formal-dmg-app-preflight", "release_eligible": False,
                      **preflight(args.app)}
        else:
            result = package(args.app, args.output, args.report,
                             args.notary_profile, args.signing_identity)
    except PackagingBlocked as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error)}, sort_keys=True), file=sys.stderr)
        return 2
    except (PackagingError, OSError) as error:
        print(json.dumps({"status": "FAIL", "reason": str(error)}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
