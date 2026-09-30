"""Test builds tied to an isolated runner must not become local installer previews."""
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "preview", Path(__file__).resolve().parents[2] / "scripts/package_preview_dmg.py")
preview = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preview)


class PreviewCredentialsTests(unittest.TestCase):
    def test_runner_bound_app_is_rejected_before_packaging(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "TokenMeter.app"
            (app / "Contents").mkdir(parents=True)
            with (app / "Contents/Info.plist").open("wb") as stream:
                plistlib.dump({"CFBundleIdentifier": "org.tokenmeter.TokenMeter.UITesting",
                              "TMTestAPIURL": "", "TMTestCredentialsDirectory": "/private/test/credentials"}, stream)
            with patch.object(preview, "run") as run:
                with self.assertRaisesRegex(ValueError, "Runner-bound credentials"):
                    preview.package(app, root / "preview.dmg", "http://127.0.0.1:49176")
                run.assert_not_called()
            self.assertFalse((root / "preview.dmg").exists())


if __name__ == "__main__":
    unittest.main()
