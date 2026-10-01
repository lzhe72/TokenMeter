"""Fixed owner-fixture checks. A mounted fixture is not a product E2E result."""

import hashlib
import os
from pathlib import Path
import shutil
import stat
import struct
import sys
import tempfile
import unittest

from scripts.granular_credential_owner_fixture import (
    IMAGE_BYTES, FixtureError, _image_attachment, detach, patch_catalog_owner, prepare,
)


NAME = "a" * 64 + ".token"


def synthetic_image(path: Path, *, uid: int = 501, inode: int = 19, mode: int = 0o100600,
                    journaled: bool = False, invalid_offsets: bool = False) -> int:
    image = bytearray(IMAGE_BYTES)
    header = 1024
    image[header:header + 2] = b"H+"
    struct.pack_into(">H", image, header + 2, 4)
    struct.pack_into(">I", image, header + 4, (1 << 13) if journaled else 0)
    struct.pack_into(">I", image, header + 40, 4096)
    catalog = header + 272
    struct.pack_into(">Q", image, catalog, 8192)
    struct.pack_into(">I", image, catalog + 12, 2)
    struct.pack_into(">II", image, catalog + 16, 2, 2)
    base = 2 * 4096
    image[base + 8] = 1
    struct.pack_into(">I", image, base + 14 + 10, 1)
    struct.pack_into(">H", image, base + 14 + 18, 4096)
    struct.pack_into(">I", image, base + 14 + 22, 2)
    leaf = base + 4096
    image[leaf + 8] = 255
    struct.pack_into(">H", image, leaf + 10, 1)
    record = leaf + 14
    key_length = 6 + len(NAME) * 2
    struct.pack_into(">H", image, record, key_length)
    struct.pack_into(">I", image, record + 2, 2)
    struct.pack_into(">H", image, record + 6, len(NAME))
    image[record + 8:record + 8 + len(NAME) * 2] = NAME.encode("utf-16-be")
    data = record + 2 + key_length
    struct.pack_into(">H", image, data, 2)
    struct.pack_into(">I", image, data + 8, inode)
    struct.pack_into(">I", image, data + 32, uid)
    struct.pack_into(">H", image, data + 42, mode)
    struct.pack_into(">H", image, leaf + 4096 - 2, 15 if invalid_offsets else 14)
    struct.pack_into(">H", image, leaf + 4096 - 4, data + 248 - leaf)
    path.write_bytes(image)
    os.chmod(path, 0o600)
    return data + 32


class CatalogOwnerPatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="tm-owner-format-")
        self.addCleanup(self.temporary.cleanup)
        self.image = Path(self.temporary.name) / "owned.dmg"

    def test_only_target_uid_field_changes(self):
        offset = synthetic_image(self.image, uid=os.getuid())
        before = self.image.read_bytes()
        record = patch_catalog_owner(self.image, NAME, 19, os.getuid())
        after = self.image.read_bytes()
        self.assertEqual(record["catalog_owner_offset"], offset)
        self.assertEqual(record["patch_span_bytes"], 4)
        self.assertEqual(after[:offset], before[:offset])
        self.assertEqual(after[offset + 4:], before[offset + 4:])
        self.assertEqual(after[offset:offset + 4], b"\0\0\0\0")
        self.assertEqual(record["image_sha256_before"], hashlib.sha256(before).hexdigest())
        self.assertEqual(record["image_sha256_after"], hashlib.sha256(after).hexdigest())

    def test_wrong_inode_owner_mode_and_name_fail_without_modifying_image(self):
        for variant in ("inode", "owner", "mode", "name"):
            with self.subTest(variant=variant):
                synthetic_image(self.image, uid=os.getuid(), mode=0o100644 if variant == "mode" else 0o100600)
                before = self.image.read_bytes()
                with self.assertRaises(FixtureError):
                    patch_catalog_owner(self.image, "b" * 64 + ".token" if variant == "name" else NAME,
                                        20 if variant == "inode" else 19,
                                        os.getuid() + 1 if variant == "owner" else os.getuid())
                self.assertEqual(self.image.read_bytes(), before)

    def test_journal_and_btree_bounds_fail_closed(self):
        for variant in ("journal", "offset", "extent"):
            with self.subTest(variant=variant):
                synthetic_image(self.image, uid=os.getuid(), journaled=variant == "journal",
                                invalid_offsets=variant == "offset")
                if variant == "extent":
                    with self.image.open("r+b") as stream:
                        stream.seek(1024 + 272 + 20)
                        stream.write(struct.pack(">I", 1))
                before = self.image.read_bytes()
                with self.assertRaises(FixtureError):
                    patch_catalog_owner(self.image, NAME, 19, os.getuid())
                self.assertEqual(self.image.read_bytes(), before)


@unittest.skipUnless(sys.platform == "darwin" and shutil.which("hdiutil"), "macOS hdiutil is required")
class RealOwnedImageFixtureTests(unittest.TestCase):
    def test_prepare_mount_verify_and_detach_owned_other_uid_file(self):
        with tempfile.TemporaryDirectory(prefix="tm-owner-mount-", dir="/private/tmp") as directory:
            root = Path(directory)
            profile = root / "profile"; profile.mkdir(mode=0o700)
            credentials = profile / "credentials"; credentials.mkdir(mode=0o700)
            source = profile / "synthetic-token.txt"
            source.write_text("A" * 43, encoding="ascii"); os.chmod(source, 0o600)
            output = root / "evidence"; output.mkdir(mode=0o700)
            image = output / "fixture.dmg"; record = output / "fixture.json"
            try:
                result = prepare(profile, "http://127.0.0.1:54321", source, image, record)
                target = credentials / result["credential_name"]
                self.assertEqual(result["phase"], "mounted")
                self.assertEqual(result["observed_owner_uid"], 0)
                self.assertEqual(target.lstat().st_uid, 0)
                self.assertEqual(stat.S_IMODE(target.lstat().st_mode), 0o600)
                self.assertEqual(credentials.lstat().st_uid, os.getuid())
                self.assertEqual(source.read_text(encoding="ascii"), "A" * 43)
                self.assertEqual(_image_attachment(image), (result["device"], str(credentials)))
            finally:
                if image.exists() and record.exists():
                    detached = detach(record)
                    self.assertEqual(detached["phase"], "detached")
                    self.assertIsNone(_image_attachment(image))


if __name__ == "__main__":
    unittest.main()
