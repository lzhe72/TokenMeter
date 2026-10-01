#!/usr/bin/env python3
"""Build the local Electron candidate with electron-builder; never publish assets."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import plistlib
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.package_release_dmg import tree_sha256, file_sha256
from scripts.internal_package import validate_dmg_layout


class PackageError(ValueError):
    pass


def run(args, label, *, cwd=None, timeout=180, log=None):
    """Keep passwords and failing tool arguments out of public reports."""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("TM_TEST_", "TM_INTERNAL_", "TOKENMETER_", "CSC_"))}
    env["CSC_IDENTITY_AUTO_DISCOVERY"] = "false"
    try:
        if log:
            with Path(log).open("x") as stream:
                result = subprocess.run(args, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
            output = ""
        else:
            result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
            output = result.stdout + result.stderr
    except (OSError, subprocess.TimeoutExpired):
        raise PackageError(label + " could not complete") from None
    if result.returncode:
        raise PackageError(f"{label} failed (exit {result.returncode})")
    return output.strip()


def validate_config(config):
    required = {"schema_version", "release_id", "version", "upgrade_version", "distribution_profile", "bundle_id",
                "minimum_macos", "architectures", "build", "upgrade_build", "api_url", "update_feed_url",
                "update_public_key", "certificate_sha256", "signature_kind"}
    if not isinstance(config, dict) or set(config) != required:
        raise PackageError("Local release config has missing or unknown fields")
    fixed = {"schema_version": 1, "version": "0.1.0", "upgrade_version": "0.1.1", "build": "100", "upgrade_build": "101",
             "distribution_profile": "internal", "bundle_id": "org.tokenmeter.TokenMeter", "minimum_macos": "15.0",
             "architectures": ["x86_64"], "api_url": "http://127.0.0.1:49176",
             "update_feed_url": "http://127.0.0.1:49177/version.json", "signature_kind": "internal_self_signed"}
    if any(type(config[key]) is not type(value) or config[key] != value for key, value in fixed.items()):
        raise PackageError("Local scope, platform or defaults differ from approved config")
    if not re.fullmatch(r"v0\.1\.0-\d{8}T\d{6}Z", config["release_id"]):
        raise PackageError("Invalid release ID")
    try:
        datetime.strptime(config["release_id"].rsplit("-", 1)[1], "%Y%m%dT%H%M%SZ")
        public = base64.b64decode(config["update_public_key"], validate=True)
    except (ValueError, TypeError):
        raise PackageError("Invalid release time or public key") from None
    if len(public) != 32 or base64.b64encode(public).decode() != config["update_public_key"]:
        raise PackageError("Invalid update public key")
    if not isinstance(config["certificate_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", config["certificate_sha256"]):
        raise PackageError("Invalid public certificate fingerprint")
    return config


def artifact(path, base):
    path, base = Path(path), Path(base)
    if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
        raise PackageError("Artifact must be a nonempty regular file")
    try: relative = path.relative_to(base).as_posix()
    except ValueError: raise PackageError("Artifact escaped output") from None
    if any(parent.is_symlink() for parent in path.parents if parent != base.parent):
        raise PackageError("Artifact uses symlink parent")
    return {"path": relative, "sha256": file_sha256(path), "bytes": path.stat().st_size}


def expose_local_dmg(source, descriptor, release_id, candidate, *, development, dmg_root=None):
    """Put a verified, explicitly unapproved copy where the user can find it."""
    if (not isinstance(release_id, str) or not isinstance(candidate, str)
            or not re.fullmatch(r"v\d+\.\d+\.\d+-\d{8}T\d{6}Z", release_id)
            or not re.fullmatch(r"[a-f0-9]{40}", candidate)):
        raise PackageError("Invalid local DMG identity")
    if not isinstance(descriptor, dict):
        raise PackageError("Missing original DMG descriptor")
    source = Path(os.path.abspath(source))
    expected_name = f"TokenMeter-{release_id}-internal.dmg"
    if (source.name != expected_name or source.is_symlink() or not source.is_file()
            or any(parent.is_symlink() for parent in source.parents)):
        raise PackageError("Invalid original DMG")
    digest, size = descriptor.get("sha256"), descriptor.get("bytes")
    if (descriptor.get("path") != expected_name or not isinstance(digest, str)
            or not re.fullmatch(r"[a-f0-9]{64}", digest) or type(size) is not int or size <= 0
            or source.stat().st_size != size or file_sha256(source) != digest):
        raise PackageError("Original DMG differs from package manifest")

    root = Path(os.path.abspath(dmg_root if dmg_root is not None else ROOT / "dmg"))
    version_dir = root / release_id
    for directory in (root, version_dir):
        if any(parent.is_symlink() for parent in (directory, *directory.parents)):
            raise PackageError("Local DMG directory uses a symlink")
        if directory.exists() and not directory.is_dir():
            raise PackageError("Local DMG directory is not a directory")
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    label = "DEVELOPMENT-NOT-RELEASED" if development else "CANDIDATE-NOT-RELEASED"
    stem = f"TokenMeter-{release_id}"
    targets = (version_dir / f"{stem}-{label}.dmg",
               version_dir / f"{stem}-{candidate[:12]}-{digest[:12]}-{label}.dmg")

    def existing_matches(target):
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise PackageError("Local DMG destination is unsafe")
        return target.exists() and target.stat().st_size == size and file_sha256(target) == digest

    for target in targets:
        if existing_matches(target):
            return target

    fd, temporary_name = tempfile.mkstemp(prefix=".TokenMeter-copy-", suffix=".part", dir=version_dir)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as destination, source.open("rb") as original:
            os.fchmod(destination.fileno(), 0o600)
            shutil.copyfileobj(original, destination)
            destination.flush()
            os.fsync(destination.fileno())
        if temporary.stat().st_size != size or file_sha256(temporary) != digest or file_sha256(source) != digest:
            raise PackageError("Local DMG copy changed")
        for target in targets:
            if existing_matches(target):
                return target
            if target.exists():
                continue
            try:
                os.link(temporary, target, follow_symlinks=False)
            except FileExistsError:
                if existing_matches(target):
                    return target
                continue
            try:
                if not existing_matches(target):
                    raise PackageError("Local DMG readback changed")
            except (OSError, PackageError):
                target.unlink()
                raise
            return target
        raise PackageError("Local DMG filename collision")
    finally:
        temporary.unlink(missing_ok=True)


def archive_name(name):
    if not isinstance(name, str) or "\\" in name or any(item in {"", ".", ".."} for item in name.split("/")) or PurePosixPath(name).is_absolute():
        raise PackageError("Unsafe archive member")
    return name


def builder_configuration(config, candidate, version, build, output, resource):
    result = {"appId": config["bundle_id"], "productName": "TokenMeter", "electronVersion": "44.5.1",
            "directories": {"app": str(ROOT / "apps/desktop"), "output": str(output)},
            "files": ["out/**/*", "package.json"], "asar": True, "npmRebuild": False,
            "extraMetadata": {"version": version, "main": "out/main/index.cjs"},
            "extraResources": [{"from": str(resource), "to": "release-config.json"}],
            "buildVersion": build, "publish": None,
            "mac": {"target": ["dir"], "identity": None, "hardenedRuntime": False,
                    "icon": str(ROOT / "apps/desktop/resources/TokenMeter.icns"),
                    "minimumSystemVersion": config["minimum_macos"], "category": "public.app-category.developer-tools",
                    "extendInfo": {"ElectronSquirrelPreventDowngrades": True,
                                   "NSAppTransportSecurity": {"NSExceptionDomains": {
                                       "127.0.0.1": {"NSExceptionAllowsInsecureHTTPLoads": True}}}}}}
    # Reuse the pinned official runtime installed by npm run runtime:install.
    runtime = ROOT / "apps/desktop/node_modules/electron/dist"
    if (runtime / "Electron.app/Contents/MacOS/Electron").is_file():
        result["electronDist"] = str(runtime)
    return result


def validate_dependencies():
    desktop = ROOT / "apps/desktop"
    expected = {"electron": "44.5.1", "electron-builder": "26.15.3", "@electron/osx-sign": "2.7.1", "yauzl": "3.4.0"}
    for name, version in expected.items():
        try: actual = json.loads((desktop / "node_modules" / name / "package.json").read_text())["version"]
        except (OSError, ValueError, KeyError): raise PackageError("Missing locked package: " + name) from None
        if actual != version: raise PackageError("Installed dependency differs from locked design: " + name)
    run(["node", "-e", "const b=require('electron-builder');const s=require('@electron/osx-sign');"
         "if(typeof b.build!=='function'||typeof s.sign!=='function')process.exit(2)"],
        "Verify builder and signer installed API", cwd=desktop)


class LocalIdentity:
    def __init__(self, work, keys, config):
        self.work, self.keys, self.config = Path(work), Path(keys), config
        self.keychain = self.work / "signing.keychain-db"
        self.previous = None
        self.created = False
        self.identity = None

    def prepare(self):
        if self.keys.is_symlink() or not self.keys.is_dir() or self.keys.stat().st_uid != os.getuid():
            raise PackageError("Signing directory must belong to this user")
        for name in ("codesign.p12", "password", "seed"):
            item = self.keys / name
            if item.is_symlink() or not item.is_file() or item.stat().st_uid != os.getuid() or stat.S_IMODE(item.stat().st_mode) & 0o077:
                raise PackageError("Private signing input permissions are not restricted")
        bundle_password = (self.keys / "password").read_text().strip()
        if not bundle_password or "\n" in bundle_password:
            raise PackageError("Invalid private bundle credential")
        certificate = self.work / "public.pem"
        run(["openssl", "pkcs12", "-in", str(self.keys / "codesign.p12"), "-passin", "file:" + str(self.keys / "password"),
             "-clcerts", "-nokeys", "-out", str(certificate)], "Read signing certificate")
        der = self.work / "public.der"
        run(["openssl", "x509", "-in", str(certificate), "-outform", "DER", "-out", str(der)], "Read public certificate DER")
        if file_sha256(der) != self.config["certificate_sha256"]:
            raise PackageError("Signing certificate differs from pinned public identity")
        self.identity = hashlib.sha1(der.read_bytes()).hexdigest().upper()
        self.previous = shlex.split(run(["security", "list-keychains", "-d", "user"], "Read keychain list"))
        password = secrets.token_urlsafe(32)
        self.created = True
        run(["security", "create-keychain", "-p", password, str(self.keychain)], "Create isolated keychain")
        run(["security", "set-keychain-settings", "-lut", "21600", str(self.keychain)], "Set isolated keychain timeout")
        run(["security", "unlock-keychain", "-p", password, str(self.keychain)], "Unlock isolated keychain")
        run(["security", "import", str(self.keys / "codesign.p12"), "-k", str(self.keychain), "-P", bundle_password,
             "-T", "/usr/bin/codesign"], "Import stable signing identity")
        run(["security", "set-key-partition-list", "-S", "apple-tool:,apple:,codesign:", "-s", "-k", password,
             str(self.keychain)], "Authorize isolated signing")
        run(["security", "list-keychains", "-d", "user", "-s", *self.previous, str(self.keychain)], "Register isolated signing keychain")
        return self

    def close(self):
        errors = []
        if self.previous is not None:
            try: run(["security", "list-keychains", "-d", "user", "-s", *self.previous], "Restore keychain list")
            except PackageError as error: errors.append(str(error))
        if self.created and self.keychain.exists():
            try: run(["security", "delete-keychain", str(self.keychain)], "Delete isolated keychain")
            except PackageError as error: errors.append(str(error))
        if self.previous is not None:
            if shlex.split(run(["security", "list-keychains", "-d", "user"], "Recheck keychain list")) != self.previous:
                errors.append("Original keychain list was not restored")
        if self.keychain.exists(): errors.append("Temporary signing keychain remains")
        if errors: raise PackageError("; ".join(errors))


def resource_config(config, candidate, version, build):
    return {key: config[key] for key in ("release_id", "bundle_id", "api_url", "update_feed_url", "update_public_key", "certificate_sha256")} | {
        "candidate_sha": candidate, "version": version, "build": build}


def verify_internal_flags(details):
    flags = re.search(r"\bflags=0x([0-9a-fA-F]+)", details)
    if not flags or int(flags.group(1), 16) & (0x10000 | 0x2000):
        raise PackageError("Internal self-signed component enables hardened runtime or library validation")


def verify_app(app, config, candidate, version, build, scratch):
    app = Path(app); scratch = Path(scratch); scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
    if app.is_symlink() or not app.is_dir() or app.name != "TokenMeter.app": raise PackageError("Missing regular App bundle")
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    if (info.get("CFBundleIdentifier") != config["bundle_id"] or info.get("CFBundleShortVersionString") != version
            or str(info.get("CFBundleVersion")) != build or info.get("ElectronSquirrelPreventDowngrades") is not True
            or info.get("LSMinimumSystemVersion") != config["minimum_macos"]):
        raise PackageError("App metadata differs from local release config")
    if info.get("NSAppTransportSecurity") != {"NSExceptionDomains": {"127.0.0.1": {"NSExceptionAllowsInsecureHTTPLoads": True}}}:
        raise PackageError("Unexpected ATS exceptions")
    resource = json.loads((app / "Contents/Resources/release-config.json").read_text())
    if resource != resource_config(config, candidate, version, build): raise PackageError("App resource config mismatch")
    icon_name = info.get("CFBundleIconFile")
    if not isinstance(icon_name, str) or not icon_name or Path(icon_name).name != icon_name:
        raise PackageError("App does not name its own packaged icon")
    if not icon_name.endswith(".icns"): icon_name += ".icns"
    icon = app / "Contents/Resources" / icon_name
    icon_source = ROOT / "apps/desktop/resources/TokenMeter.icns"
    if icon.is_symlink() or not icon.is_file() or file_sha256(icon) != file_sha256(icon_source):
        raise PackageError("App icon differs from the approved product asset")
    architectures = run(["lipo", "-archs", str(app / "Contents/MacOS/TokenMeter")], "Read actual executable architecture").split()
    if architectures != config["architectures"]: raise PackageError("App architecture was not the approved local platform")
    run(["codesign", "--verify", "--deep", "--strict", str(app)], "Verify complete signed App")
    details = run(["codesign", "--display", "--verbose=4", str(app)], "Read signing identity")
    verify_internal_flags(details)
    # Check the real nested executables as well: a helper's runtime flag can
    # prevent dyld from loading a self-signed framework without an Apple Team ID.
    macho_magic = {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}
    for component in sorted((app / "Contents").rglob("*")):
        if component.is_symlink() or not component.is_file(): continue
        with component.open("rb") as stream: magic = stream.read(4)
        if magic in macho_magic:
            verify_internal_flags(run(["codesign", "--display", "--verbose=4", str(component)], "Read nested signing flags"))
    requirement_output = run(["codesign", "-d", "-r-", str(app)], "Read designated requirement")
    requirement = next((line[len("designated => "):] for line in requirement_output.splitlines() if line.startswith("designated => ")), "")
    if "Signature=adhoc" in details or "certificate" not in requirement or config["bundle_id"] not in requirement:
        raise PackageError("App lacks a stable certificate requirement")
    prefix = scratch / "certificate-"
    run(["codesign", "--display", "--extract-certificates=" + str(prefix), str(app)], "Read App certificate")
    if file_sha256(Path(str(prefix) + "0")) != config["certificate_sha256"]: raise PackageError("App certificate changed")
    return {"version": version, "build": build, "bundle_id": config["bundle_id"], "tree_sha256": tree_sha256(app),
            "architectures": architectures, "certificate_sha256": config["certificate_sha256"], "designated_requirement": requirement,
            "signature_kind": "internal_self_signed", "codesign_verify_exit": 0, "minimum_macos": config["minimum_macos"],
            "icon_path": "Contents/Resources/" + icon_name, "icon_sha256": file_sha256(icon)}


def build_app(config, candidate, version, build, output, private, signing):
    resource = private / ("resources-" + build + ".json")
    resource.write_text(json.dumps(resource_config(config, candidate, version, build), indent=2) + "\n")
    directory = output / ("candidate" if build == config["build"] else "update")
    script = private / ("builder-" + build + ".cjs")
    builder = ROOT / "apps/desktop/node_modules/electron-builder"
    signer = ROOT / "apps/desktop/node_modules/@electron/osx-sign/dist/index.js"
    entitlements = private / ("entitlements-" + build + ".plist")
    entitlements.write_bytes(plistlib.dumps({}))
    configuration = builder_configuration(config, candidate, version, build, directory, resource)
    script.write_text("const {build, createTargets, Platform} = require(" + json.dumps(str(builder)) + ");\n"
                      "const {sign} = require(" + json.dumps(str(signer)) + ");\n"
                      "(async()=>{ await build({targets:createTargets([Platform.MAC], 'dir', 'x64'), publish:'never', config:"
                      + json.dumps(configuration) + "}); const fs=require('node:fs'); const path=require('node:path');"
                      "const dirs=fs.readdirSync(" + json.dumps(str(directory)) + ").filter(n=>n.startsWith('mac'));"
                      "if(dirs.length!==1)throw Error('Expected one mac directory');"
                      "const app=path.join(" + json.dumps(str(directory)) + ",dirs[0],'TokenMeter.app');"
                      # Builder deep-merges the upstream Electron ATS dictionary. Replace
                      # it before signing, so its broad default cannot survive our policy.
                      "require('node:child_process').execFileSync('/usr/bin/plutil',['-replace','NSAppTransportSecurity','-json',"
                      + json.dumps(json.dumps(configuration["mac"]["extendInfo"]["NSAppTransportSecurity"]))
                      + ",path.join(app,'Contents/Info.plist')]);"
                      "await sign({app, identity:" + json.dumps(signing.identity) + ", keychain:" + json.dumps(str(signing.keychain))
                      + ",identityValidation:false,preAutoEntitlements:false,optionsForFile:()=>({hardenedRuntime:false,"
                      "signatureFlags:['0'],timestamp:'none',entitlements:" + json.dumps(str(entitlements)) + "})});"
                      "})().catch(e=>{console.error(e.message);process.exit(1)});\n")
    run(["node", str(script)], "Build and sign Electron App", cwd=ROOT / "apps/desktop", timeout=1800, log=output / ("build-" + build + ".log"))
    apps = list(directory.glob("mac*/TokenMeter.app"))
    if len(apps) != 1: raise PackageError("Builder did not produce one App")
    app = apps[0]
    information = verify_app(app, config, candidate, version, build, private / ("verify-" + build))
    information["relative_path"] = app.relative_to(output).as_posix()
    return app, information


def sign_archive(archive, keys, config, scratch):
    script = scratch / (archive.stem + "-sign.cjs")
    # PKCS8 Ed25519 prefix wraps the raw private seed; only the signature is printed.
    script.write_text("const fs=require('node:fs'),c=require('node:crypto');"
                      "const raw=Buffer.from(fs.readFileSync(process.argv[2],'utf8').trim(),'base64');"
                      "if(raw.length!==32)throw Error('Invalid seed');"
                      "const key=c.createPrivateKey({key:Buffer.concat([Buffer.from('302e020100300506032b657004220420','hex'),raw]),format:'der',type:'pkcs8'});"
                      "const pub=c.createPublicKey(key);if(pub.export({type:'spki',format:'der'}).subarray(-32).toString('base64')!==process.argv[4])throw Error('Wrong public key');"
                      "const bytes=fs.readFileSync(process.argv[3]); const signature=c.sign(null,bytes,key);"
                      "if(!c.verify(null,bytes,pub,signature))throw Error('Signature self-check failed');console.log(signature.toString('base64'));\n")
    signature = run(["node", str(script), str(keys / "seed"), str(archive), config["update_public_key"]], "Sign original ZIP bytes")
    if len(base64.b64decode(signature, validate=True)) != 64: raise PackageError("Invalid archive signature")
    return signature


def make_dmg(app, output, private, config, candidate, app_info):
    stage = private / "dmg-stage"; stage.mkdir()
    run(["ditto", str(app), str(stage / "TokenMeter.app")], "Stage original signed App")
    if tree_sha256(stage / "TokenMeter.app") != app_info["tree_sha256"]: raise PackageError("DMG staging changed App")
    (stage / "Applications").symlink_to("/Applications")
    installation = ROOT / "docs/releases/02-installation.md"
    shutil.copyfile(installation, stage / "INSTALLATION.txt")
    run(["hdiutil", "create", "-srcfolder", str(stage), "-volname", "TokenMeter", "-format", "UDZO", str(output)], "Create local DMG", timeout=600)
    run(["hdiutil", "verify", str(output)], "Verify final DMG", timeout=300)
    mount = private / "dmg-mount"; mount.mkdir()
    run(["hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", str(mount), str(output)], "Mount final DMG")
    try:
        validate_dmg_layout(mount, installation)
        actual = verify_app(mount / "TokenMeter.app", config, candidate, config["version"], config["build"], private / "mounted-verify")
        if actual != {key: value for key, value in app_info.items() if key != "relative_path"}: raise PackageError("DMG App differs from original")
    finally: run(["hdiutil", "detach", str(mount)], "Detach owned DMG")


def server_archive(config_path, target):
    tracked = run(["git", "ls-files", "-z"], "Read tracked server whitelist", cwd=ROOT).split("\0")
    names = [name for name in tracked if name.startswith("server/") and (name.endswith(".py") or re.fullmatch(r"server/requirements[^/]*\.txt", name))]
    names += ["scripts/bootstrap_sqlite.py", "scripts/local_distribution.py", "docs/releases/02-installation.md", config_path.relative_to(ROOT).as_posix()]
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(set(names)):
            archive_name(name); source = ROOT / name
            if source.is_symlink() or not source.is_file(): raise PackageError("Missing safe server input")
            archive.write(source, name)
    return sorted(set(names))


def package(config_path, output, candidate, run_id, keys, development=False):
    started = datetime.now(timezone.utc).isoformat()
    if platform.system() != "Darwin" or platform.machine() != "x86_64" or platform.mac_ver()[0].split(".")[0] != "15":
        raise PackageError("This release is validated only on local macOS 15 Intel")
    if not re.fullmatch(r"[a-f0-9]{40}", candidate) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id):
        raise PackageError("Invalid candidate or run ID")
    head = run(["git", "rev-parse", "HEAD"], "Read candidate", cwd=ROOT)
    dirty = bool(run(["git", "status", "--porcelain"], "Check source state", cwd=ROOT))
    if head != candidate or (dirty and not development): raise PackageError("Formal package requires clean exact candidate SHA")
    config_path = Path(config_path).resolve(); keys = Path(keys).resolve(); output = Path(os.path.abspath(output))
    if output.exists() or output.is_symlink() or not output.parent.is_dir() or any(p.is_symlink() for p in output.parents):
        raise PackageError("Output must be a new directory below a real existing parent")
    config = validate_config(json.loads(config_path.read_text()))
    config_digest = file_sha256(config_path); lock = ROOT / "apps/desktop/package-lock.json"
    lock_digest = file_sha256(lock)
    for tool in ("node", "npm", "codesign", "security", "openssl", "hdiutil", "ditto", "lipo"):
        if not shutil.which(tool): raise PackageError("Missing local tool: " + tool)
    validate_dependencies()
    output.mkdir(mode=0o700)
    run(["npm", "run", "build"], "Build desktop source", cwd=ROOT / "apps/desktop", timeout=600, log=output / "source-build.log")
    result = None
    with tempfile.TemporaryDirectory(prefix="tokenmeter-local-package-", dir=output) as temporary:
        private = Path(temporary); private.chmod(0o700)
        signing = LocalIdentity(private, keys, config)
        try:
            signing.prepare()
            app, app_info = build_app(config, candidate, config["version"], config["build"], output, private, signing)
            update, update_info = build_app(config, candidate, config["upgrade_version"], config["upgrade_build"], output, private, signing)
            if app_info["designated_requirement"] != update_info["designated_requirement"]: raise PackageError("Update signing requirement changed")
            archives = {}
            signatures = {}
            for name, bundle in (("candidate", app), ("update", update)):
                archive = output / (name + ".zip")
                run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(bundle), str(archive)], "Create original update ZIP", timeout=600)
                archives[name + "_zip"] = artifact(archive, output)
                signatures[name + "_ed_signature"] = sign_archive(archive, keys, config, private)
            dmg = output / ("TokenMeter-" + config["release_id"] + "-internal.dmg")
            make_dmg(app, dmg, private, config, candidate, app_info)
            server = output / "server.zip"; source_files = server_archive(config_path, server)
            if tree_sha256(app) != app_info["tree_sha256"] or tree_sha256(update) != update_info["tree_sha256"]: raise PackageError("Original App changed during packaging")
            if run(["git", "rev-parse", "HEAD"], "Recheck candidate", cwd=ROOT) != candidate or file_sha256(lock) != lock_digest or file_sha256(config_path) != config_digest:
                raise PackageError("Source inputs changed during packaging")
            if not development and run(["git", "status", "--porcelain"], "Recheck clean source", cwd=ROOT): raise PackageError("Source became dirty during packaging")
            result = {"schema_version": 2, "scope": "development" if development else "final_package", "distribution_profile": "internal",
                      "release_id": config["release_id"], "candidate_sha": candidate,
                      "candidate_tree": run(["git", "rev-parse", "HEAD^{tree}"], "Read candidate tree", cwd=ROOT),
                      "working_tree_dirty": dirty, "run_id": run_id, "config_sha256": config_digest, "lock_sha256": lock_digest,
                      "host": {"system": platform.system(), "macos_version": platform.mac_ver()[0], "architecture": platform.machine(),
                               "node": run(["node", "--version"], "Read Node version"), "npm": run(["npm", "--version"], "Read npm version")},
                      "artifacts": archives | {"dmg": artifact(dmg, output), "server_zip": artifact(server, output)},
                      "app": app_info, "update_app": update_info, "signatures": signatures, "server_source_files": source_files,
                      "started_at": started, "release_eligible": False}
        finally: signing.close()
    if result is None: raise PackageError("Packaging did not complete")
    result["cleanup_completed"] = True; result["finished_at"] = datetime.now(timezone.utc).isoformat()
    (output / "package-manifest.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    result["discoverable_dmg"] = str(expose_local_dmg(dmg, result["artifacts"]["dmg"], config["release_id"], candidate,
                                                    development=development))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-sha", required=True); parser.add_argument("--run-id", required=True)
    parser.add_argument("--key-dir", type=Path, required=True); parser.add_argument("--development", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = package(args.config, args.output, args.candidate_sha, args.run_id, args.key_dir, args.development)
        print(json.dumps({"state": "PASS", "scope": result["scope"], "release_eligible": False,
                          "manifest": str(args.output / "package-manifest.json"), "dmg": result["discoverable_dmg"]}))
        return 0
    except (PackageError, OSError, ValueError) as error:
        print(json.dumps({"state": "FAIL", "reason": str(error), "release_eligible": False})); return 1


if __name__ == "__main__": sys.exit(main())
