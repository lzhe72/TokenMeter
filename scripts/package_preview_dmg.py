"""Build and verify a local-only DMG from an unchanged CI UITesting app.

This diagnostic package cannot be used as a signed/notarized release candidate.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
from urllib.parse import urlsplit


def run(*args, quiet=False):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL if quiet else None)


def tree_digest(directory):
    digest = hashlib.sha256()
    for entry in sorted(directory.rglob("*")):
        relative = entry.relative_to(directory).as_posix()
        digest.update(relative.encode() + b"\0")
        if entry.is_symlink():
            digest.update(b"link\0" + os.readlink(entry).encode() + b"\0")
        elif entry.is_file():
            digest.update(b"file\0")
            with entry.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
        elif entry.is_dir():
            digest.update(b"dir\0")
        else:
            raise ValueError(f"Unsupported app entry: {relative}")
    return digest.hexdigest()


def require_loopback(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.port is None or parsed.username or parsed.password or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment):
        raise ValueError("Preview service must be a plain loopback HTTP origin with an explicit port")
    return url.rstrip("/")


def package(app, output, service_url):
    app = app.resolve(strict=True)
    output = output.absolute()
    if app.name != "TokenMeter.app" or not app.is_dir():
        raise ValueError("Input must be a TokenMeter.app directory")
    if output.suffix.lower() != ".dmg" or output.exists() or not output.parent.is_dir():
        raise ValueError("Output must be a new .dmg in an existing directory")
    service_url = require_loopback(service_url)
    with (app / "Contents" / "Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    if info.get("CFBundleIdentifier") != "org.tokenmeter.TokenMeter.UITesting":
        raise ValueError("Only the isolated UITesting app may be packaged as a local preview")
    if info.get("TMTestAPIURL") != "":
        raise ValueError("Preview app must use its bundled local service default")
    if info.get("SUFeedURL"):
        raise ValueError("Preview app must not have a configured update feed")
    run("codesign", "--verify", "--deep", "--strict", str(app), quiet=True)
    source_digest = tree_digest(app)
    with tempfile.TemporaryDirectory(prefix="tokenmeter-preview-") as scratch:
        stage = Path(scratch) / "stage"
        mount = Path(scratch) / "mount"
        stage.mkdir()
        mount.mkdir()
        run("ditto", str(app), str(stage / "TokenMeter.app"), quiet=True)
        if tree_digest(stage / "TokenMeter.app") != source_digest:
            raise ValueError("Staged app differs from source app")
        (stage / "Applications").symlink_to("/Applications")
        (stage / "README-LOCAL-PREVIEW.txt").write_text(
            "TokenMeter 本机预览安装包\n\n"
            "将 TokenMeter.app 拖到 Applications。\n"
            "此包是临时签名的原生测试构建，未经 Developer ID 签名或公证，不能作为正式版发布。\n"
            "App 首次内置服务地址：http://127.0.0.1:49176\n"
            f"本机测试服务地址：{service_url}\n"
            "若测试服务使用其他地址，请在登录页更改；服务须在本机运行。\n"
            "更新源未配置；正式发布仍需完整 E2E、签名、公证及发布通行证。\n",
            encoding="utf-8",
        )
        run("hdiutil", "create", "-srcfolder", str(stage), "-volname",
            "TokenMeter Local Preview", "-format", "UDZO", str(output), quiet=True)
        try:
            run("hdiutil", "verify", str(output), quiet=True)
            run("hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint",
                str(mount), str(output), quiet=True)
            try:
                installed = mount / "TokenMeter.app"
                run("codesign", "--verify", "--deep", "--strict", str(installed), quiet=True)
                if tree_digest(installed) != source_digest:
                    raise ValueError("DMG app differs from source app")
            finally:
                run("hdiutil", "detach", str(mount), quiet=True)
        except Exception:
            output.unlink(missing_ok=True)
            raise
    return {"kind": "local-preview-only", "app_tree_sha256": source_digest,
            "dmg_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "dmg_bytes": output.stat().st_size, "dmg": str(output),
            "bundle_id": info["CFBundleIdentifier"], "service_url": service_url}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--service-url", required=True)
    args = parser.parse_args()
    print(json.dumps(package(args.app, args.output, args.service_url), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
