"""Deterministic data-program checks; these are not installed-App E2E results."""
import json
import os
from pathlib import Path
import plistlib
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request, ProxyHandler, build_opener
import zipfile

from scripts.granular_update_validation_fixture import (
    MAX_ARCHIVE, MAX_UNPACKED, ValidationFixture, _small_signed_zip, digest,
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


if __name__ == "__main__":
    unittest.main()
