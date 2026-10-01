"""Owned negative update source for independently executed UPDATE-05 variants.

The source serves one variant only after explicit activation. Archives that need
to pass the Ed25519 layer are signed with the current internal release seed;
private key material is never copied into evidence or HTTP responses.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import plistlib
import secrets
import shutil
import stat
import struct
import subprocess
import sys
import threading
from datetime import datetime, timezone
from urllib.request import Request, ProxyHandler, build_opener
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.local_package import LocalIdentity, sign_archive


MAX_ARCHIVE = 512 * 1024 * 1024
MAX_UNPACKED = 2 * 1024 * 1024 * 1024
IMPLEMENTED = {
    "TC-TM001-UPDATE-05#BYTES", "TC-TM001-UPDATE-05#SHA",
    "TC-TM001-UPDATE-05#TRUNCATED", "TC-TM001-UPDATE-05#ZIP_LIMIT_METADATA",
    "TC-TM001-UPDATE-05#ZIP_LIMIT_HEADER", "TC-TM001-UPDATE-05#UNPACK_LIMIT",
    "TC-TM001-UPDATE-05#INFO_VERSION", "TC-TM001-UPDATE-05#INFO_BUILD",
    "TC-TM001-UPDATE-05#BUNDLE_ID", "TC-TM001-UPDATE-05#PATH_ESCAPE",
    "TC-TM001-UPDATE-05#SYMLINK_PARENT", "TC-TM001-UPDATE-05#CERT_MISMATCH",
    "TC-TM001-UPDATE-05#DR_MISMATCH",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _owned_directory(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    if path.exists() or path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Negative update fixture requires a new owned directory")
    if not path.parent.is_dir() or path.parent.stat().st_uid != os.getuid():
        raise ValueError("Negative update fixture parent is not owned")
    path.mkdir(mode=0o700)
    return path


def _read_config(package: dict, update_zip: Path) -> dict:
    release_id = package.get("release_id")
    if not isinstance(release_id, str) or not release_id.startswith("v0.1.0-"):
        raise ValueError("Unexpected local release manifest")
    root = Path(__file__).resolve().parents[1]
    config_path = root / "releases" / release_id / "local-release.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if package.get("artifacts", {}).get("update_zip", {}).get("sha256") != digest(update_zip):
        raise ValueError("Update ZIP differs from current package manifest")
    if package["artifacts"]["update_zip"]["bytes"] != update_zip.stat().st_size:
        raise ValueError("Update ZIP length differs from package manifest")
    if config["update_public_key"] is None or config["certificate_sha256"] != package["app"]["certificate_sha256"]:
        raise ValueError("Local release trust anchors differ from package")
    return config


def _check_key_dir(key_dir: Path) -> Path:
    key_dir = Path(os.path.abspath(key_dir))
    if key_dir.is_symlink() or not key_dir.is_dir() or key_dir.stat().st_uid != os.getuid():
        raise ValueError("Internal signing inputs are unavailable")
    for name in ("seed", "codesign.p12", "password"):
        item = key_dir / name
        if item.is_symlink() or not item.is_file() or item.stat().st_uid != os.getuid() or stat.S_IMODE(item.stat().st_mode) & 0o077:
            raise ValueError("Internal signing input ownership or permissions are unsafe")
    return key_dir


def _small_signed_zip(target: Path, kind: str, info: bytes) -> None:
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        archive.writestr("TokenMeter.app/Contents/Info.plist", info)
        if kind == "UNPACK_LIMIT":
            archive.writestr("TokenMeter.app/Contents/Resources/oversize.bin", b"X")
        elif kind == "PATH_ESCAPE":
            archive.writestr("TokenMeter.app/../../owned-sentinel", b"ESCAPE-ATTEMPT")
        elif kind == "SYMLINK_PARENT":
            link = zipfile.ZipInfo("TokenMeter.app/Contents/Resources/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, "target")
            archive.writestr("TokenMeter.app/Contents/Resources/link/child", b"SYMLINK-WRITE-ATTEMPT")
        else:
            raise ValueError("Unknown small archive variant")
    if kind == "UNPACK_LIMIT":
        raw = bytearray(target.read_bytes())
        name = b"TokenMeter.app/Contents/Resources/oversize.bin"
        cursor = 0
        found = False
        while True:
            cursor = raw.find(b"PK\x01\x02", cursor)
            if cursor < 0:
                break
            if cursor + 46 <= len(raw):
                name_length = struct.unpack_from("<H", raw, cursor + 28)[0]
                if raw[cursor + 46:cursor + 46 + name_length] == name:
                    struct.pack_into("<I", raw, cursor + 24, MAX_UNPACKED + 1)
                    found = True
                    break
            cursor += 4
        if not found:
            raise ValueError("Could not locate ZIP central-directory limit fixture")
        target.write_bytes(raw)


def _signed_wrong_bundle_zip(target: Path, update_zip: Path, package: dict, private: Path,
                             key_dir: Path, config: dict) -> None:
    relative = Path(package["update_app"]["relative_path"])
    source = (update_zip.parent / relative).resolve()
    if not source.is_relative_to(update_zip.parent.resolve()) or not source.is_dir() or source.name != "TokenMeter.app":
        raise ValueError("Current signed update App is unavailable")
    app = private / "signed-bundle-variant" / "TokenMeter.app"
    app.parent.mkdir(mode=0o700)
    shutil.copytree(source, app, symlinks=True)
    info_path = app / "Contents/Info.plist"
    info = plistlib.loads(info_path.read_bytes())
    if info.get("CFBundleIdentifier") != config["bundle_id"]:
        raise ValueError("Input App bundle identity differs from release config")
    info["CFBundleIdentifier"] = config["bundle_id"] + ".negative"
    info_path.write_bytes(plistlib.dumps(info))
    signing_root = private / "temporary-signing"
    signing_root.mkdir(mode=0o700)
    signer = LocalIdentity(signing_root, key_dir, config)
    try:
        signer.prepare()
        for command, label in ((["/usr/bin/codesign", "--force", "--sign", signer.identity,
                                "--keychain", str(signer.keychain), "--timestamp=none", str(app)], "Sign negative App"),
                               (["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)], "Verify negative App")):
            result = subprocess.run(command, capture_output=True, timeout=180, check=False)
            if result.returncode:
                raise ValueError(label + " failed")
    finally:
        signer.close()
    result = subprocess.run(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
                             str(app), str(target)], capture_output=True, timeout=300, check=False)
    if result.returncode or not target.is_file():
        raise ValueError("Could not package signed negative App")


def _run_identity(command: list[str], label: str, *, should_pass: bool = True) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError(label + " could not complete") from None
    if (result.returncode == 0) != should_pass:
        raise ValueError(label + " did not produce the required result")
    return result.stdout + result.stderr


def _second_identity(private: Path, config: dict) -> tuple[Path, dict]:
    """Generate a one-run self-signed code identity inside the owned private root."""
    keys = private / "second-identity"
    keys.mkdir(mode=0o700)
    configuration = keys / "codesign.cnf"
    configuration.write_text("[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=signing\n"
                             "[dn]\nCN=TokenMeter negative identity " + secrets.token_hex(10) + "\n"
                             "[signing]\nbasicConstraints=critical,CA:FALSE\n"
                             "keyUsage=critical,digitalSignature\n"
                             "extendedKeyUsage=critical,codeSigning\n", encoding="utf-8")
    key = keys / "codesign.key"
    certificate = keys / "codesign.pem"
    _run_identity(["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-x509", "-days", "1", "-sha256",
                   "-config", str(configuration), "-keyout", str(key), "-out", str(certificate)],
                  "Create isolated negative certificate")
    os.chmod(key, 0o600)
    password = keys / "password"
    password.write_text(secrets.token_urlsafe(32) + "\n", encoding="utf-8")
    os.chmod(password, 0o600)
    _run_identity(["openssl", "pkcs12", "-export", "-inkey", str(key), "-in", str(certificate),
                   "-keypbe", "PBE-SHA1-3DES", "-certpbe", "PBE-SHA1-3DES", "-macalg", "sha1",
                   "-out", str(keys / "codesign.p12"), "-passout", "file:" + str(password)],
                  "Create isolated negative identity bundle")
    os.chmod(keys / "codesign.p12", 0o600)
    seed = keys / "seed"
    seed.write_text(base64.b64encode(secrets.token_bytes(32)).decode() + "\n", encoding="utf-8")
    os.chmod(seed, 0o600)
    der = keys / "codesign.der"
    _run_identity(["openssl", "x509", "-in", str(certificate), "-outform", "DER", "-out", str(der)],
                  "Read isolated negative certificate")
    certificate_sha256 = digest(der)
    if certificate_sha256 == config["certificate_sha256"]:
        raise ValueError("Negative identity unexpectedly equals the candidate certificate")
    return keys, {**config, "certificate_sha256": certificate_sha256}


def _signed_requirement_negative_zip(target: Path, update_zip: Path, package: dict,
                                     private: Path, key_dir: Path, config: dict, kind: str) -> bool:
    """Return whether the signed negative uses the same leaf certificate."""
    relative = Path(package["update_app"]["relative_path"])
    source = (update_zip.parent / relative).resolve()
    if not source.is_relative_to(update_zip.parent.resolve()) or not source.is_dir() or source.name != "TokenMeter.app":
        raise ValueError("Current signed update App is unavailable")
    app = private / "signed-identity-variant" / "TokenMeter.app"
    app.parent.mkdir(mode=0o700)
    shutil.copytree(source, app, symlinks=True)
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    if (info.get("CFBundleIdentifier") != config["bundle_id"]
            or info.get("CFBundleShortVersionString") != package["update_app"]["version"]
            or str(info.get("CFBundleVersion")) != str(package["update_app"]["build"])):
        raise ValueError("Input App Info differs from valid update")
    signer_keys, signer_config = (key_dir, config) if kind == "DR_MISMATCH" else _second_identity(private, config)
    signing_root = private / "temporary-signing"
    signing_root.mkdir(mode=0o700)
    signer = LocalIdentity(signing_root, signer_keys, signer_config)
    try:
        signer.prepare()
        command = ["/usr/bin/codesign", "--force", "--sign", signer.identity,
                   "--keychain", str(signer.keychain), "--timestamp=none"]
        if kind == "DR_MISMATCH":
            # Keep Info and certificate unchanged: only CodeDirectory's
            # identifier differs from the currently installed App's DR.
            command += ["--identifier", config["bundle_id"] + ".negative"]
        _run_identity(command + [str(app)], "Sign complete negative App")
        _run_identity(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)],
                      "Verify complete negative App code signature")
        requirement = package["app"]["designated_requirement"]
        if not isinstance(requirement, str) or "certificate" not in requirement:
            raise ValueError("Candidate designated requirement is absent")
        _run_identity(["/usr/bin/codesign", "--verify", "--deep", "--strict", "-R", "=" + requirement,
                       str(app)], "Reject candidate designated requirement", should_pass=False)
        prefix = private / "negative-certificate-"
        _run_identity(["/usr/bin/codesign", "--display", "--extract-certificates=" + str(prefix), str(app)],
                      "Read negative App leaf certificate")
        same_certificate = digest(Path(str(prefix) + "0")) == config["certificate_sha256"]
        if same_certificate != (kind == "DR_MISMATCH"):
            raise ValueError("Negative App certificate relation differs from variant")
    finally:
        signer.close()
    _run_identity(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
                   str(app), str(target)], "Package complete negative App")
    if not target.is_file():
        raise ValueError("Signed negative App ZIP is unavailable")
    return same_certificate


class ValidationFixture:
    """One case-owned loopback source; .url + '/version.json' is the App feed."""

    def __init__(self, update_zip: Path, package_manifest: dict, private: Path,
                 variant_id: str, key_dir: Path):
        if variant_id not in IMPLEMENTED:
            raise ValueError("UPDATE-05 variant has no safe fixture binding")
        self.private = _owned_directory(private)
        self.update_zip = Path(update_zip).resolve()
        self.package = package_manifest
        self.variant_id = variant_id
        self.kind = variant_id.split("#", 1)[1]
        self.config = _read_config(package_manifest, self.update_zip)
        self.key_dir = _check_key_dir(key_dir)
        self.sentinel = self.private / "owned-sentinel"
        self.sentinel.write_bytes(b"TOKENMETER-NEGATIVE-UPDATE-SENTINEL\n")
        os.chmod(self.sentinel, 0o600)
        self.archive = self.update_zip
        self.signature = package_manifest["signatures"]["update_ed_signature"]
        self.code_signature_verified = False
        self.candidate_requirement_rejected = False
        self.certificate_matches_candidate = None
        info = (self.update_zip.parent / package_manifest["update_app"]["relative_path"] /
                "Contents/Info.plist").read_bytes()
        if self.kind in {"UNPACK_LIMIT", "PATH_ESCAPE", "SYMLINK_PARENT"}:
            self.archive = self.private / "negative.zip"
            _small_signed_zip(self.archive, self.kind, info)
            self.signature = sign_archive(self.archive, self.key_dir, self.config, self.private)
        elif self.kind == "BUNDLE_ID":
            self.archive = self.private / "negative.zip"
            _signed_wrong_bundle_zip(self.archive, self.update_zip, package_manifest,
                                     self.private, self.key_dir, self.config)
            self.signature = sign_archive(self.archive, self.key_dir, self.config, self.private)
            self.code_signature_verified = True
        elif self.kind in {"CERT_MISMATCH", "DR_MISMATCH"}:
            self.archive = self.private / "negative.zip"
            self.certificate_matches_candidate = _signed_requirement_negative_zip(
                self.archive, self.update_zip, package_manifest, self.private,
                self.key_dir, self.config, self.kind)
            self.signature = sign_archive(self.archive, self.key_dir, self.config, self.private)
            self.code_signature_verified = True
            self.candidate_requirement_rejected = True
        metadata = {"schema_version": 1, "version": package_manifest["update_app"]["version"],
                    "build": str(package_manifest["update_app"]["build"]), "url": "",
                    "sha256": digest(self.archive), "bytes": self.archive.stat().st_size,
                    "ed25519_signature": self.signature}
        if self.kind == "BYTES":
            metadata["bytes"] += 1
        elif self.kind == "SHA":
            metadata["sha256"] = ("0" if metadata["sha256"][0] != "0" else "1") + metadata["sha256"][1:]
        elif self.kind == "ZIP_LIMIT_METADATA":
            metadata["bytes"] = MAX_ARCHIVE + 1
        elif self.kind == "INFO_VERSION":
            metadata["version"] = "0.1.2"
        elif self.kind == "INFO_BUILD":
            metadata["build"] = "102"
        self.metadata = metadata
        self.stage = "current"
        self.nonce = secrets.token_hex(20)
        self.token = secrets.token_urlsafe(32)
        self.requests: list[dict] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def send_bytes(self, status: int, data: bytes = b"", content_type: str = "text/plain"):
                self.send_response(status)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                if data:
                    try:
                        self.wfile.write(data)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                owner.requests.append({"stage": owner.stage, "route": self.path,
                                       "method": self.command, "status": status,
                                       "bytes_sent": len(data), "body_sha256": hashlib.sha256(data).hexdigest(),
                                       "time": datetime.now(timezone.utc).isoformat()})

            def do_POST(self):
                if self.path != "/control/activate" or self.headers.get("Authorization") != "Bearer " + owner.token:
                    self.send_bytes(403)
                    return
                owner.stage = "negative"
                self.send_bytes(200, json.dumps({"stage": owner.stage, "nonce": owner.nonce}).encode(), "application/json")

            def do_GET(self):
                if self.path == "/health":
                    self.send_bytes(200, owner.nonce.encode())
                    return
                if self.path == "/observations":
                    if self.headers.get("Authorization") != "Bearer " + owner.token:
                        self.send_bytes(403)
                        return
                    self.send_bytes(200, json.dumps({"nonce": owner.nonce, "requests": owner.requests}).encode(), "application/json")
                    return
                if self.path == "/version.json":
                    if owner.stage == "current":
                        self.send_bytes(204)
                        return
                    self.send_bytes(200, json.dumps(owner.metadata).encode(), "application/json")
                    return
                if self.path != "/update.zip" or owner.stage != "negative":
                    self.send_bytes(404)
                    return
                if owner.kind == "ZIP_LIMIT_HEADER":
                    self.send_response(200)
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Type", "application/zip")
                    self.send_header("Content-Length", str(MAX_ARCHIVE + 1))
                    self.end_headers()
                    owner.requests.append({"stage": owner.stage, "route": self.path,
                                           "method": self.command, "status": 200,
                                           "declared_bytes": MAX_ARCHIVE + 1, "bytes_sent": 0,
                                           "body_sha256": hashlib.sha256(b"").hexdigest(),
                                           "time": datetime.now(timezone.utc).isoformat()})
                    return
                limit = owner.archive.stat().st_size // 2 if owner.kind == "TRUNCATED" else None
                sent = 0
                h = hashlib.sha256()
                self.send_response(200)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(limit if limit is not None else owner.archive.stat().st_size))
                self.end_headers()
                with owner.archive.open("rb") as stream:
                    while True:
                        chunk = stream.read(min(1024 * 1024, (limit - sent) if limit is not None else 1024 * 1024))
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                        except (BrokenPipeError, ConnectionResetError):
                            break
                        h.update(chunk)
                        sent += len(chunk)
                owner.requests.append({"stage": owner.stage, "route": self.path, "method": self.command,
                                       "status": 200, "bytes_sent": sent, "body_sha256": h.hexdigest(),
                                       "time": datetime.now(timezone.utc).isoformat()})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = False
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.control_url = self.url + "/control"
        self.metadata["url"] = self.url + "/update.zip"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        try:
            with build_opener(ProxyHandler({})).open(Request(self.url + "/health"), timeout=3) as response:
                if response.read().decode() != self.nonce:
                    raise ValueError("Owned validation source nonce mismatch")
            self.manifest_path = self.private / "negative-fixture-manifest.json"
            self.manifest_path.write_text(json.dumps({"schema_version": 1, "variant_id": variant_id,
                "archive_sha256": digest(self.archive), "archive_bytes": self.archive.stat().st_size,
                "metadata_version": self.metadata["version"], "metadata_build": self.metadata["build"],
                "metadata_sha256": self.metadata["sha256"], "metadata_bytes": self.metadata["bytes"],
                "ed25519_signature_present": True, "code_signature_verified": self.code_signature_verified,
                "candidate_requirement_rejected": self.candidate_requirement_rejected,
                "certificate_matches_candidate": self.certificate_matches_candidate,
                "sentinel_sha256": digest(self.sentinel),
                "source_nonce": self.nonce}, indent=2) + "\n", encoding="utf-8")
            os.chmod(self.manifest_path, 0o600)
        except Exception as error:
            try:
                closed = self.close()
            except Exception:
                closed = False
            if not closed:
                raise ValueError("Negative fixture setup failed and owned HTTP source did not close") from error
            raise

    def close(self) -> bool:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        return not self.thread.is_alive()


def main() -> int:
    """Fixed, non-GUI fixture check; never reports an App E2E result."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-manifest", type=Path, required=True)
    parser.add_argument("--update-zip", type=Path, required=True)
    parser.add_argument("--keys", type=Path, required=True)
    parser.add_argument("--variant", choices=sorted(IMPLEMENTED), required=True)
    parser.add_argument("--owned-output", type=Path, required=True)
    args = parser.parse_args()
    package = json.loads(args.package_manifest.read_text(encoding="utf-8"))
    fixture = ValidationFixture(args.update_zip, package, args.owned_output, args.variant, args.keys)
    try:
        result = {"schema_version": 1, "scope": "negative-update-fixture-non-gui",
                  "variant_id": args.variant, "state": "PASS",
                  "archive_sha256": digest(fixture.archive),
                  "source_nonce_matches": bool(fixture.nonce),
                  "code_signature_verified": fixture.code_signature_verified}
        target = fixture.private / "fixture-self-check.json"
        target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        os.chmod(target, 0o600)
        print(json.dumps({"state": "PASS", "variant_id": args.variant,
                          "evidence": str(target)}))
        return 0
    finally:
        if not fixture.close():
            raise ValueError("Owned validation source failed to close")


if __name__ == "__main__":
    raise SystemExit(main())
