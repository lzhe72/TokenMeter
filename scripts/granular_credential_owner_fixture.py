"""Create one owned HFS+ image whose synthetic credential has a different UID.

The image is private to one TM-001 test case. No privilege escalation, user
profile, production credential, or system file is used. The four-byte UID
change is made only while the newly created image is detached.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import stat
import struct
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


FIXTURE_ID = "tokenmeter-credential-other-uid-v1"
IMAGE_BYTES = 16 * 1024 * 1024
MAX_CATALOG_NODES = 4096
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{43}\Z")


class FixtureError(RuntimeError):
    pass


def _u16(data: bytes | bytearray, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise FixtureError("HFS+ record is truncated")
    return struct.unpack_from(">H", data, offset)[0]


def _u32(data: bytes | bytearray, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise FixtureError("HFS+ record is truncated")
    return struct.unpack_from(">I", data, offset)[0]


def _safe_file(path: Path, mode: int = 0o600) -> os.stat_result:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != mode:
        raise FixtureError("Fixture file ownership, links, or mode are unsafe")
    return info


def _safe_directory(path: Path) -> None:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise FixtureError("Fixture directory ownership or mode is unsafe")
    if str(path) != os.path.realpath(path):
        raise FixtureError("Fixture directory must use its canonical path")


def _run(*command: str) -> str:
    process = subprocess.run(command, text=True, capture_output=True, check=False, timeout=60)
    if process.returncode:
        raise FixtureError(f"{Path(command[0]).name} {command[1]} exited {process.returncode}: {process.stderr.strip()[:400]}")
    return process.stdout


def _image_attachment(image: Path) -> tuple[str, str] | None:
    data = plistlib.loads(subprocess.check_output(["hdiutil", "info", "-plist"], timeout=15))
    matching: list[tuple[str, str]] = []
    for item in data.get("images", []):
        if item.get("image-path") != str(image):
            continue
        if item.get("owner-uid") != os.getuid():
            raise FixtureError("Owned image is attached by another UID")
        for entity in item.get("system-entities", []):
            mountpoint = entity.get("mount-point")
            device = entity.get("dev-entry")
            if mountpoint and isinstance(device, str) and re.fullmatch(r"/dev/disk\d+(?:s\d+)?", device):
                matching.append((device, mountpoint))
    if len(matching) > 1:
        raise FixtureError("Owned image has multiple mounted volumes")
    return matching[0] if matching else None


def _write_record(path: Path, item: dict[str, Any], *, initial: bool = False) -> None:
    text = json.dumps(item, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if initial:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return
    _safe_file(path)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_record(path: Path) -> dict[str, Any]:
    _safe_directory(path.parent)
    _safe_file(path)
    item = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(item, dict) or item.get("fixture_id") != FIXTURE_ID:
        raise FixtureError("Owner fixture record is invalid")
    return item


def patch_catalog_owner(image: Path, name: str, inode: int, owner_uid: int) -> dict[str, Any]:
    """Patch exactly the on-disk UID field for one known regular HFS+ file."""
    _safe_file(image)
    if not re.fullmatch(r"[a-f0-9]{64}\.token", name) or inode < 16 or owner_uid <= 0:
        raise FixtureError("Credential identity is not a synthetic catalog target")
    before = image.read_bytes()
    if len(before) != IMAGE_BYTES or before[1024:1026] != b"H+" or _u16(before, 1026) != 4:
        raise FixtureError("Expected raw 16 MiB HFS+ image is missing")
    header = 1024
    attributes = _u32(before, header + 4)
    if attributes & (1 << 13):
        raise FixtureError("Journaled HFS+ cannot be patched offline")
    block_size = _u32(before, header + 40)
    if block_size < 512 or block_size > 65536 or block_size & (block_size - 1):
        raise FixtureError("HFS+ block size is invalid")
    catalog = header + 272
    logical_size = struct.unpack_from(">Q", before, catalog)[0]
    total_blocks = _u32(before, catalog + 12)
    start_block = _u32(before, catalog + 16)
    extent_blocks = _u32(before, catalog + 20)
    if not start_block or not extent_blocks or total_blocks > extent_blocks or logical_size > extent_blocks * block_size:
        raise FixtureError("Catalog is not contained in one validated extent")
    catalog_start = start_block * block_size
    if catalog_start + logical_size > len(before) or logical_size < 8192:
        raise FixtureError("Catalog extent is outside the owned image")
    if before[catalog_start + 8] != 1:
        raise FixtureError("Catalog B-tree header is missing")
    node_size = _u16(before, catalog_start + 14 + 18)
    first_leaf = _u32(before, catalog_start + 14 + 10)
    total_nodes = _u32(before, catalog_start + 14 + 22)
    if node_size < 4096 or node_size > 32768 or node_size & (node_size - 1):
        raise FixtureError("Catalog B-tree node size is invalid")
    if not first_leaf or total_nodes > MAX_CATALOG_NODES or total_nodes * node_size > logical_size:
        raise FixtureError("Catalog B-tree bounds are invalid")
    matches: list[int] = []
    seen_nodes: set[int] = set()
    leaf = first_leaf
    while leaf:
        if leaf in seen_nodes or leaf >= total_nodes:
            raise FixtureError("Catalog leaf chain loops or exceeds bounds")
        seen_nodes.add(leaf)
        node = catalog_start + leaf * node_size
        if node + node_size > catalog_start + logical_size or struct.unpack_from(">b", before, node + 8)[0] != -1:
            raise FixtureError("Catalog leaf node is malformed")
        count = _u16(before, node + 10)
        if not count or count > (node_size - 16) // 4:
            raise FixtureError("Catalog leaf record count is invalid")
        offsets = [_u16(before, node + node_size - 2 * (index + 1)) for index in range(count + 1)]
        if offsets[0] != 14 or offsets != sorted(offsets) or offsets[-1] > node_size - 2 * (count + 1):
            raise FixtureError("Catalog leaf record offsets are invalid")
        for index in range(count):
            start = node + offsets[index]
            end = node + offsets[index + 1]
            if end - start < 10:
                raise FixtureError("Catalog leaf record is truncated")
            key_length = _u16(before, start)
            name_length = _u16(before, start + 6)
            if key_length != 6 + 2 * name_length or name_length > 255 or start + 2 + key_length + 2 > end:
                raise FixtureError("Catalog key is malformed")
            try:
                entry_name = before[start + 8:start + 8 + 2 * name_length].decode("utf-16-be")
            except UnicodeDecodeError as error:
                raise FixtureError("Catalog name encoding is invalid") from error
            if entry_name != name or _u32(before, start + 2) != 2:
                continue
            data_start = start + 2 + key_length
            if _u16(before, data_start) != 2 or data_start + 248 > end:
                raise FixtureError("Target catalog entry is not a file")
            if _u32(before, data_start + 8) != inode:
                raise FixtureError("Target catalog CNID differs from mounted inode")
            owner_offset = data_start + 32
            if _u32(before, owner_offset) != owner_uid:
                raise FixtureError("Target catalog owner differs from mounted UID")
            file_mode = _u16(before, owner_offset + 10)
            if stat.S_IFMT(file_mode) != stat.S_IFREG or stat.S_IMODE(file_mode) != 0o600:
                raise FixtureError("Target catalog file mode is not private regular 0600")
            matches.append(owner_offset)
        leaf = _u32(before, node)
    if len(matches) != 1:
        raise FixtureError("Expected exactly one credential catalog record")
    offset = matches[0]
    with image.open("r+b") as stream:
        stream.seek(offset)
        stream.write(struct.pack(">I", 0))
        stream.flush()
        os.fsync(stream.fileno())
    after = image.read_bytes()
    if after[:offset] != before[:offset] or after[offset + 4:] != before[offset + 4:] or after[offset:offset + 4] != b"\0\0\0\0":
        raise FixtureError("Offline patch changed data outside the four-byte UID field")
    return {"catalog_owner_offset": offset, "patch_span_bytes": 4,
            "image_sha256_before": hashlib.sha256(before).hexdigest(),
            "image_sha256_after": hashlib.sha256(after).hexdigest(),
            "changed_byte_offsets": [index for index in range(offset, offset + 4) if before[index] != after[index]]}


def _attach(image: Path, mountpoint: Path) -> str:
    _run("hdiutil", "attach", "-nobrowse", "-owners", "on", "-mountpoint", str(mountpoint), str(image))
    attachment = _image_attachment(image)
    if not attachment or attachment[1] != str(mountpoint):
        raise FixtureError("Owned HFS+ image did not mount at the expected path")
    return attachment[0]


def _detach(image: Path, mountpoint: Path, device: str | None = None) -> None:
    attachment = _image_attachment(image)
    if attachment is None:
        return
    if attachment[1] != str(mountpoint) or (device is not None and attachment[0] != device):
        raise FixtureError("Refusing to detach an unrecognized disk image mount")
    _run("hdiutil", "detach", attachment[0])
    if _image_attachment(image) is not None:
        raise FixtureError("Owned disk image remained mounted after detach")


def prepare(profile: Path, origin: str, token_source: Path, image: Path, record: Path) -> dict[str, Any]:
    profile = profile.absolute(); token_source = token_source.absolute(); image = image.absolute(); record = record.absolute()
    mountpoint = profile / "credentials"
    _safe_directory(profile); _safe_directory(mountpoint); _safe_directory(image.parent)
    if record.parent != image.parent or token_source.parent != profile or list(mountpoint.iterdir()):
        raise FixtureError("Owner fixture paths must be isolated and credential mountpoint empty")
    _safe_file(token_source)
    token = token_source.read_text(encoding="ascii")
    if not TOKEN_RE.fullmatch(token):
        raise FixtureError("Owned synthetic token is malformed")
    if not re.fullmatch(r"https?://[^\s/]+", origin):
        raise FixtureError("Origin must be one configured service origin")
    credential_name = hashlib.sha256(origin.encode("utf-8")).hexdigest() + ".token"
    if image.exists() or record.exists() or image.suffix != ".dmg":
        raise FixtureError("Owned image and record paths must be unused")
    item: dict[str, Any] = {"fixture_id": FIXTURE_ID, "phase": "starting", "image_path": str(image),
                            "record_path": str(record), "mountpoint": str(mountpoint), "device": None,
                            "credential_name": credential_name, "expected_owner_uid": 0,
                            "created_by_uid": os.getuid()}
    _write_record(record, item, initial=True)
    device: str | None = None
    try:
        _run("hdiutil", "create", "-size", "16m", "-fs", "HFS+", "-volname", "TMOwnedCredential",
             "-layout", "NONE", "-uid", str(os.getuid()), "-gid", str(os.getgid()), "-mode", "0700", str(image))
        os.chmod(image, 0o600)
        _safe_file(image)
        item["phase"] = "attaching"; _write_record(record, item)
        device = _attach(image, mountpoint)
        item.update(phase="mounted-before-patch", device=device); _write_record(record, item)
        _safe_directory(mountpoint)
        credential = mountpoint / credential_name
        fd = os.open(credential, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(token)
            stream.flush()
            os.fsync(stream.fileno())
        file_info = _safe_file(credential)
        inode = file_info.st_ino
        _detach(image, mountpoint, device)
        device = None
        item.update(phase="detached-for-patch", device=None, credential_file_id=inode); _write_record(record, item)
        item.update(patch_catalog_owner(image, credential_name, inode, os.getuid()))
        item["phase"] = "attaching-patched"; _write_record(record, item)
        device = _attach(image, mountpoint)
        item.update(phase="mounted", device=device); _write_record(record, item)
        _safe_directory(mountpoint)
        changed = (mountpoint / credential_name).lstat()
        if not stat.S_ISREG(changed.st_mode) or changed.st_uid != 0 or changed.st_nlink != 1 or stat.S_IMODE(changed.st_mode) != 0o600 or changed.st_ino != inode:
            raise FixtureError("Mounted synthetic credential does not have the expected other UID")
        item["observed_owner_uid"] = changed.st_uid
        _write_record(record, item)
        return item
    except Exception as error:
        cleanup_error = None
        try:
            if image.exists():
                _detach(image, mountpoint, device)
        except Exception as failure:
            cleanup_error = str(failure)
        remaining = None
        try:
            if image.exists():
                remaining = _image_attachment(image)
        except Exception as failure:
            cleanup_error = f"{cleanup_error or ''}; attachment check: {failure}"
        item.update(phase="failed", device=remaining[0] if remaining else None,
                    error=str(error), cleanup_error=cleanup_error)
        _write_record(record, item)
        raise


def detach(record: Path) -> dict[str, Any]:
    item = _read_record(record.absolute())
    image = Path(item["image_path"]); mountpoint = Path(item["mountpoint"])
    if item["record_path"] != str(record.absolute()) or image.parent != record.absolute().parent:
        raise FixtureError("Owner fixture record paths do not match")
    _safe_file(image)
    attachment = _image_attachment(image)
    if attachment:
        if attachment[1] != str(mountpoint) or (item.get("device") is not None and attachment[0] != item["device"]):
            raise FixtureError("Mounted device does not match this fixture record")
        _detach(image, mountpoint, attachment[0])
    item.update(phase="detached", device=None)
    _write_record(record, item)
    return item


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    creation = commands.add_parser("prepare")
    creation.add_argument("--profile", type=Path, required=True)
    creation.add_argument("--origin", required=True)
    creation.add_argument("--token-source", type=Path, required=True)
    creation.add_argument("--image", type=Path, required=True)
    creation.add_argument("--record", type=Path, required=True)
    closing = commands.add_parser("detach")
    closing.add_argument("--record", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.profile, args.origin, args.token_source, args.image, args.record) if args.command == "prepare" else detach(args.record)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (FixtureError, OSError, subprocess.SubprocessError, ValueError, UnicodeError) as error:
        print(f"Owner fixture failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
