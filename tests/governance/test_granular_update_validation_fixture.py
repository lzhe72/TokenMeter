"""Deterministic data-program checks; these are not installed-App E2E results."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import plistlib
import stat
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request, ProxyHandler, build_opener
import zipfile

from scripts.granular_update_validation_fixture import (
    MAX_ARCHIVE, MAX_UNPACKED, SigningInputsUnavailable, ValidationFixture,
    _check_key_dir, _small_signed_zip, digest, validate_signing_inputs,
)
import scripts.granular_update_validation_fixture as fixture_module

ROOT = Path(__file__).resolve().parents[2]


class NegativeUpdateFixtureTests(unittest.TestCase):
    def setUp(self):
        self.holder = tempfile.TemporaryDirectory(prefix="tm-update-validation-")
        self.addCleanup(self.holder.cleanup)
        self.root = Path(self.holder.name)
        release_id = "v0.1.0-20260929T074814Z"
        config = json.loads((ROOT / "releases" / release_id / "local-release.json").read_text())
        self.assertEqual(config["release_id"], release_id)
        self.archive = self.root / "update.zip"
        self.info = plistlib.dumps({"CFBundleIdentifier": config["bundle_id"],
                                     "CFBundleShortVersionString": "0.1.1", "CFBundleVersion": "101"})
        with zipfile.ZipFile(self.archive, "x") as stream:
            stream.writestr("TokenMeter.app/Contents/Info.plist", self.info)
        app_info = self.root / "update/mac/TokenMeter.app/Contents/Info.plist"
        app_info.parent.mkdir(parents=True)
        app_info.write_bytes(self.info)
        self.keys = self.root / "keys"
        self.keys.mkdir(mode=0o700)
        for name in ("seed", "codesign.p12", "password"):
            value = self.keys / name
            value.write_bytes(b"dummy-test-only")
            os.chmod(value, 0o600)
        self.package = {"release_id": release_id,
                        "artifacts": {"update_zip": {"bytes": self.archive.stat().st_size,
                                                     "sha256": digest(self.archive)}},
                        "app": {"certificate_sha256": config["certificate_sha256"]},
                        "update_app": {"relative_path": "update/mac/TokenMeter.app",
                                       "version": "0.1.1", "build": "101"},
                        "signatures": {"update_ed_signature": "A" * 86 + "=="}}
        self.opener = build_opener(ProxyHandler({}))

    def fixture(self, suffix):
        result = ValidationFixture(self.archive, self.package, self.root / suffix,
                                   "TC-TM001-UPDATE-05#" + suffix, self.keys)
        self.addCleanup(result.close)
        return result

    def activate(self, fixture):
        request = Request(fixture.control_url + "/activate", method="POST",
                          headers={"Authorization": "Bearer " + fixture.token})
        with self.opener.open(request, timeout=3) as response:
            self.assertEqual(json.load(response)["nonce"], fixture.nonce)

    def test_size_digest_and_truncation_metadata_are_independent(self):
        for kind in ("BYTES", "SHA", "TRUNCATED", "ZIP_LIMIT_METADATA", "ZIP_LIMIT_HEADER"):
            with self.subTest(kind=kind):
                fixture = self.fixture(kind)
                with self.opener.open(fixture.url + "/version.json", timeout=3) as response:
                    self.assertEqual(response.status, 204)
                self.activate(fixture)
                with self.opener.open(fixture.url + "/version.json", timeout=3) as response:
                    metadata = json.load(response)
                self.assertEqual(metadata["url"], fixture.url + "/update.zip")
                if kind == "BYTES":
                    self.assertEqual(metadata["bytes"], self.archive.stat().st_size + 1)
                if kind == "SHA":
                    self.assertNotEqual(metadata["sha256"], digest(self.archive))
                if kind == "ZIP_LIMIT_METADATA":
                    self.assertEqual(metadata["bytes"], MAX_ARCHIVE + 1)
                if kind == "ZIP_LIMIT_HEADER":
                    with self.opener.open(fixture.url + "/update.zip", timeout=3) as response:
                        self.assertEqual(response.headers["Content-Length"], str(MAX_ARCHIVE + 1))
                if kind == "TRUNCATED":
                    with self.opener.open(fixture.url + "/update.zip", timeout=3) as response:
                        self.assertEqual(len(response.read()), self.archive.stat().st_size // 2)
                self.assertEqual(digest(fixture.sentinel),
                                 json.loads(fixture.manifest_path.read_text())["sentinel_sha256"])

    def test_info_metadata_mismatches_follow_both_approved_release_pairs(self):
        release_id = "v0.2.0-20261001T034118Z"
        config = json.loads((ROOT / "releases" / release_id / "local-release.json").read_text())
        self.assertEqual(config["release_id"], release_id)
        archive = self.root / "update-02.zip"
        info = plistlib.dumps({"CFBundleIdentifier": config["bundle_id"],
                               "CFBundleShortVersionString": "0.2.1", "CFBundleVersion": "201"})
        with zipfile.ZipFile(archive, "x") as stream:
            stream.writestr("TokenMeter.app/Contents/Info.plist", info)
        app_info = self.root / "update-02/mac/TokenMeter.app/Contents/Info.plist"
        app_info.parent.mkdir(parents=True)
        app_info.write_bytes(info)
        package = copy.deepcopy(self.package)
        package["release_id"] = release_id
        package["app"]["certificate_sha256"] = config["certificate_sha256"]
        package["artifacts"]["update_zip"] = {"bytes": archive.stat().st_size,
                                                "sha256": digest(archive)}
        package["update_app"] = {"relative_path": "update-02/mac/TokenMeter.app",
                                 "version": "0.2.1", "build": "201"}
        releases = (("v0.1.0-20260929T074814Z", self.archive, self.package,
                     {"INFO_VERSION": ("0.1.2", "101"), "INFO_BUILD": ("0.1.1", "102")}),
                    (release_id, archive, package,
                     {"INFO_VERSION": ("0.2.2", "201"), "INFO_BUILD": ("0.2.1", "202")}))
        for approved_id, source, manifest, cases in releases:
            for kind, expected in cases.items():
                with self.subTest(release_id=approved_id, kind=kind):
                    fixture = ValidationFixture(source, manifest,
                        self.root / (approved_id + "-" + kind),
                        "TC-TM001-UPDATE-05#" + kind, self.keys)
                    try:
                        self.assertEqual(fixture.config["release_id"], approved_id)
                        self.assertEqual((fixture.metadata["version"], fixture.metadata["build"]), expected)
                        recorded = json.loads(fixture.manifest_path.read_text())
                        self.assertEqual((recorded["metadata_version"], recorded["metadata_build"]), expected)
                        self.activate(fixture)
                        with self.opener.open(fixture.url + "/version.json", timeout=3) as response:
                            served = json.load(response)
                        self.assertEqual((served["version"], served["build"]), expected)
                        self.assertNotEqual(expected, (manifest["update_app"]["version"],
                                                       manifest["update_app"]["build"]))
                    finally:
                        self.assertTrue(fixture.close())

    def test_unpack_limit_central_directory_is_over_threshold(self):
        archive = self.root / "oversize.zip"
        _small_signed_zip(archive, "UNPACK_LIMIT", self.info)
        with zipfile.ZipFile(archive) as stream:
            entries = stream.infolist()
        payload = next(item for item in entries if item.filename.endswith("oversize.bin"))
        self.assertEqual(payload.file_size, MAX_UNPACKED + 1)
        self.assertLess(archive.stat().st_size, MAX_ARCHIVE)

    def test_path_escape_and_symlink_parent_are_distinct(self):
        escape, link = self.root / "escape.zip", self.root / "link.zip"
        _small_signed_zip(escape, "PATH_ESCAPE", self.info)
        _small_signed_zip(link, "SYMLINK_PARENT", self.info)
        with zipfile.ZipFile(escape) as archive:
            self.assertTrue(any("../" in item.filename for item in archive.infolist()))
        with zipfile.ZipFile(link) as archive:
            entries = archive.infolist()
        parent = next(item for item in entries if item.filename.endswith("/link"))
        self.assertEqual((parent.external_attr >> 16) & stat.S_IFMT(0o170000), stat.S_IFLNK)
        self.assertTrue(any(item.filename.endswith("/link/child") for item in entries))

    def test_manifest_failure_closes_owned_http_source(self):
        servers = []
        original_server = fixture_module.ThreadingHTTPServer
        original_write = Path.write_text

        def tracked_server(*args, **kwargs):
            server = original_server(*args, **kwargs)
            servers.append(server)
            return server

        def failed_manifest(path, *args, **kwargs):
            if path.name == "negative-fixture-manifest.json":
                raise OSError("synthetic fixture manifest write failure")
            return original_write(path, *args, **kwargs)

        with patch.object(fixture_module, "ThreadingHTTPServer", side_effect=tracked_server), \
             patch.object(Path, "write_text", failed_manifest):
            with self.assertRaisesRegex(OSError, "synthetic fixture manifest write failure"):
                ValidationFixture(self.archive, self.package, self.root / "BYTES",
                                  "TC-TM001-UPDATE-05#BYTES", self.keys)
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].fileno(), -1)


class SigningInputPreflightTests(unittest.TestCase):
    """Use generated private material; never inspect a developer's signing keys."""

    def setUp(self):
        self.holder = tempfile.TemporaryDirectory(prefix="tm-signing-preflight-")
        self.addCleanup(self.holder.cleanup)
        self.root = Path(self.holder.name)
        self.archive = self.root / "original-update.zip"
        self.archive.write_bytes(b"synthetic original update bytes")
        self.keys = self.root / "keys"
        self.keys.mkdir(mode=0o700)
        self.seed = self.keys / "seed"
        self.seed.write_text(base64.b64encode(hashlib.sha256(b"tm-test-seed").digest()).decode() + "\n")
        os.chmod(self.seed, 0o600)
        script = ("const fs=require('node:fs'),c=require('node:crypto');"
                  "const raw=Buffer.from(fs.readFileSync(process.argv[1],'utf8').trim(),'base64');"
                  "const key=c.createPrivateKey({key:Buffer.concat([Buffer.from('302e020100300506032b657004220420','hex'),raw]),format:'der',type:'pkcs8'});"
                  "console.log(c.createPublicKey(key).export({type:'spki',format:'der'}).subarray(-32).toString('base64'))")
        public = subprocess.run(["node", "-e", script, str(self.seed)], capture_output=True,
                                text=True, check=True).stdout.strip()
        self.password = self.keys / "password"
        self.password.write_text("test-only-password\n")
        os.chmod(self.password, 0o600)
        certificate = self._make_certificate(self.keys, "primary")
        self.config = {"release_id": "v0.1.0-20260929T074814Z", "update_public_key": public,
                       "certificate_sha256": digest(certificate)}
        scratch = self.root / "scratch"
        scratch.mkdir(mode=0o700)
        signature = fixture_module.sign_archive(self.archive, self.keys, self.config, scratch)
        self.package = {"release_id": self.config["release_id"],
                        "artifacts": {"update_zip": {"sha256": digest(self.archive),
                                                      "bytes": self.archive.stat().st_size}},
                        "app": {"certificate_sha256": self.config["certificate_sha256"]},
                        "signatures": {"update_ed_signature": signature}}

    def _make_certificate(self, location: Path, name: str) -> Path:
        key, certificate, der = (location / (name + suffix)
                                 for suffix in (".key", ".pem", ".der"))
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-keyout", str(key), "-out", str(certificate), "-days", "1",
                        "-subj", "/CN=TokenMeter synthetic " + name],
                       capture_output=True, check=True, timeout=30)
        subprocess.run(["openssl", "pkcs12", "-export", "-inkey", str(key), "-in", str(certificate),
                        "-out", str(self.keys / "codesign.p12"), "-passout", "file:" + str(self.password)],
                       capture_output=True, check=True, timeout=30)
        os.chmod(self.keys / "codesign.p12", 0o600)
        subprocess.run(["openssl", "x509", "-in", str(certificate), "-outform", "DER", "-out", str(der)],
                       capture_output=True, check=True, timeout=30)
        return der

    def preflight(self, *, package=None, key_dir=None, archive=None):
        with patch.object(fixture_module, "_read_config", return_value=self.config):
            return validate_signing_inputs(key_dir or self.keys, package or self.package,
                                           archive or self.archive)

    def test_original_zip_and_public_certificate_are_bound_to_private_inputs(self):
        result = self.preflight()
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["update_zip_sha256"], digest(self.archive))
        self.assertEqual(result["certificate_sha256"], self.config["certificate_sha256"])
        self.assertNotIn(str(self.keys), json.dumps(result))

    def test_missing_or_relative_key_dir_is_blocked_before_app_launch(self):
        for value in (Path("relative-keys"), self.root / "missing", self.root / "keys" / ".." / "keys"):
            with self.subTest(value=value), self.assertRaises(SigningInputsUnavailable):
                self.preflight(key_dir=value)

    def test_directory_and_private_file_permissions_are_strict(self):
        for mode in (0o755, 0o770):
            with self.subTest(directory_mode=oct(mode)):
                os.chmod(self.keys, mode)
                with self.assertRaises(SigningInputsUnavailable):
                    self.preflight()
                os.chmod(self.keys, 0o700)
        for name in ("seed", "codesign.p12", "password"):
            item = self.keys / name
            with self.subTest(file=name):
                os.chmod(item, 0o644)
                with self.assertRaises(SigningInputsUnavailable):
                    self.preflight()
                os.chmod(item, 0o600)
        original = self.seed.read_bytes()
        self.seed.unlink()
        fallback = self.root / "seed-outside"
        fallback.write_bytes(original)
        os.chmod(fallback, 0o600)
        self.seed.symlink_to(fallback)
        with self.assertRaises(SigningInputsUnavailable):
            self.preflight()

    def test_replaceable_ancestor_and_user_symlink_are_blocked(self):
        unsafe = self.root / "unsafe"
        unsafe.mkdir(mode=0o777)
        os.chmod(unsafe, 0o777)
        nested = unsafe / "keys"
        nested.mkdir(mode=0o700)
        for name in ("seed", "codesign.p12", "password"):
            (nested / name).write_bytes((self.keys / name).read_bytes())
            os.chmod(nested / name, 0o600)
        with self.assertRaises(SigningInputsUnavailable):
            _check_key_dir(nested)
        link = self.root / "user-link"
        link.symlink_to(self.keys, target_is_directory=True)
        with self.assertRaises(SigningInputsUnavailable):
            _check_key_dir(link)
        path_through_link = self.root / "linked-parent"
        path_through_link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(SigningInputsUnavailable):
            _check_key_dir(path_through_link / "keys")

    def test_wrong_seed_or_p12_identity_is_blocked(self):
        self.seed.write_text(base64.b64encode(hashlib.sha256(b"other-seed").digest()).decode() + "\n")
        with self.assertRaises(SigningInputsUnavailable):
            self.preflight()
        self.seed.write_text(base64.b64encode(hashlib.sha256(b"tm-test-seed").digest()).decode() + "\n")
        self._make_certificate(self.keys, "other")
        with self.assertRaises(SigningInputsUnavailable):
            self.preflight()

    def test_public_zip_or_manifest_conflict_is_candidate_failure(self):
        altered = copy.deepcopy(self.package)
        altered["artifacts"]["update_zip"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            validate_signing_inputs(self.keys, altered, self.archive)
        altered = copy.deepcopy(self.package)
        altered["signatures"]["update_ed_signature"] = base64.b64encode(b"X" * 64).decode()
        with self.assertRaises(ValueError) as caught:
            self.preflight(package=altered)
        self.assertNotIsInstance(caught.exception, SigningInputsUnavailable)

    def test_public_trust_anchor_conflict_is_candidate_failure(self):
        with self.assertRaises(ValueError) as caught:
            fixture_module._read_config(self.package, self.archive)
        self.assertNotIsInstance(caught.exception, SigningInputsUnavailable)


if __name__ == "__main__":
    unittest.main()
