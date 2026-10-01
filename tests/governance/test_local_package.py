"""Local package contract checks; these do not certify the desktop product."""
import copy
import importlib.util
import json
import hashlib
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("local_package", ROOT / "scripts/local_package.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class LocalPackageTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "releases/v0.1.0-20260929T074814Z/local-release.json").read_text())

    def test_local_contract_accepts_current_host_only(self):
        self.assertEqual(package.validate_config(self.config)["architectures"], ["x86_64"])

    def test_public_ci_and_unverified_platforms_rejected(self):
        for field, value in [("distribution_profile", "public"), ("architectures", ["arm64", "x86_64"]),
                             ("minimum_macos", "14.0"), ("update_feed_url", "http://example.com/version.json"),
                             ("upgrade_version", "0.1.0"), ("upgrade_build", "100")]:
            with self.subTest(field=field):
                config = copy.deepcopy(self.config); config[field] = value
                with self.assertRaises(package.PackageError): package.validate_config(config)

    def test_key_material_and_unknown_fields_rejected(self):
        for key in ("private_key", "seed", "password", "unexpected"):
            config = dict(self.config, **{key: "not-public"})
            with self.assertRaises(package.PackageError): package.validate_config(config)

    def test_bad_public_key_and_certificate_rejected(self):
        for key in ("update_public_key", "certificate_sha256"):
            config = dict(self.config, **{key: "bad"})
            with self.assertRaises(package.PackageError): package.validate_config(config)

    def test_artifact_refuses_symlinks_and_empty_files(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve(); empty = base / "empty"; empty.touch()
            with self.assertRaises(package.PackageError): package.artifact(empty, base)
            original = base / "source"; original.write_text("original")
            link = base / "link"; link.symlink_to(original)
            with self.assertRaises(package.PackageError): package.artifact(link, base)
            observed = package.artifact(original, base)
            self.assertEqual(observed["path"], "source")
            self.assertEqual(observed["bytes"], 8)

    def test_local_dmg_copy_is_findable_and_does_not_change_original(self):
        release_id = self.config["release_id"]
        candidate = "a" * 40
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            output = base / "candidate"; output.mkdir()
            original = output / f"TokenMeter-{release_id}-internal.dmg"
            original.write_bytes(b"original package bytes")
            descriptor = package.artifact(original, output)
            for development, label in ((True, "DEVELOPMENT-NOT-RELEASED"),
                                       (False, "CANDIDATE-NOT-RELEASED")):
                with self.subTest(development=development):
                    exposed = package.expose_local_dmg(original, descriptor, release_id, candidate,
                                                        development=development, dmg_root=base / "dmg")
                    self.assertEqual(exposed, base / "dmg" / release_id / f"TokenMeter-{release_id}-{label}.dmg")
                    self.assertEqual(package.file_sha256(exposed), descriptor["sha256"])
                    self.assertEqual(exposed.read_bytes(), original.read_bytes())
                    self.assertEqual(original.name, descriptor["path"])
                    self.assertEqual(package.expose_local_dmg(original, descriptor, release_id, candidate,
                                                              development=development, dmg_root=base / "dmg"), exposed)

    def test_existing_local_dmg_is_never_overwritten(self):
        release_id = self.config["release_id"]
        candidate = "b" * 40
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            first_output = base / "first"; first_output.mkdir()
            second_output = base / "second"; second_output.mkdir()
            name = f"TokenMeter-{release_id}-internal.dmg"
            original = first_output / name; original.write_bytes(b"first candidate")
            revised = second_output / name; revised.write_bytes(b"different candidate")
            first_descriptor = package.artifact(original, first_output)
            revised_descriptor = package.artifact(revised, second_output)
            first = package.expose_local_dmg(original, first_descriptor, release_id, candidate,
                                             development=True, dmg_root=base / "dmg")
            alternate = package.expose_local_dmg(revised, revised_descriptor, release_id, candidate,
                                                 development=True, dmg_root=base / "dmg")
            self.assertEqual(first.read_bytes(), b"first candidate")
            self.assertNotEqual(first, alternate)
            self.assertIn(revised_descriptor["sha256"][:12], alternate.name)
            self.assertEqual(alternate.read_bytes(), b"different candidate")
            self.assertEqual(package.expose_local_dmg(revised, revised_descriptor, release_id, candidate,
                                                      development=True, dmg_root=base / "dmg"), alternate)

    def test_local_dmg_copy_rejects_changed_original_and_symlink_destination(self):
        release_id = self.config["release_id"]
        candidate = "c" * 40
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            output = base / "candidate"; output.mkdir()
            original = output / f"TokenMeter-{release_id}-internal.dmg"
            original.write_bytes(b"valid original")
            descriptor = package.artifact(original, output)
            with self.assertRaisesRegex(package.PackageError, "differs"):
                package.expose_local_dmg(original, dict(descriptor, sha256="0" * 64), release_id, candidate,
                                         development=True, dmg_root=base / "dmg")
            version_dir = base / "dmg" / release_id; version_dir.mkdir(parents=True)
            victim = base / "untouched"; victim.write_bytes(b"outside")
            (version_dir / f"TokenMeter-{release_id}-DEVELOPMENT-NOT-RELEASED.dmg").symlink_to(victim)
            with self.assertRaisesRegex(package.PackageError, "unsafe"):
                package.expose_local_dmg(original, descriptor, release_id, candidate,
                                         development=True, dmg_root=base / "dmg")
            self.assertEqual(victim.read_bytes(), b"outside")

    def test_local_dmg_copy_rejects_symlink_directory(self):
        release_id = self.config["release_id"]
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            output = base / "candidate"; output.mkdir()
            original = output / f"TokenMeter-{release_id}-internal.dmg"
            original.write_bytes(b"valid original")
            descriptor = package.artifact(original, output)
            target_dir = base / "external"; target_dir.mkdir()
            (base / "dmg").symlink_to(target_dir, target_is_directory=True)
            with self.assertRaisesRegex(package.PackageError, "symlink"):
                package.expose_local_dmg(original, descriptor, release_id, "d" * 40,
                                         development=True, dmg_root=base / "dmg")
            self.assertEqual(list(target_dir.iterdir()), [])

    def test_builder_really_builds_dir_without_publishing(self):
        config = package.builder_configuration(self.config, "a" * 40, "0.1.0", "100", Path("/tmp/output"), Path("/tmp/resources.json"))
        self.assertEqual(config["mac"]["identity"], None)
        self.assertEqual(config["mac"]["target"], ["dir"])
        self.assertEqual(config["mac"]["icon"], str(ROOT / "apps/desktop/resources/TokenMeter.icns"))
        self.assertEqual(config["extraMetadata"]["version"], "0.1.0")
        self.assertTrue(config["mac"]["extendInfo"]["ElectronSquirrelPreventDowngrades"])
        self.assertNotIn("NSAllowsArbitraryLoads", config["mac"]["extendInfo"]["NSAppTransportSecurity"])
        self.assertEqual(set(config["mac"]["extendInfo"]["NSAppTransportSecurity"]["NSExceptionDomains"]), {"127.0.0.1"})

    def test_safe_archive_names_reject_escape(self):
        for name in ("../secret", "/secret", "server/../../secret", "server\\secret"):
            with self.subTest(name=name), self.assertRaises(package.PackageError): package.archive_name(name)
        self.assertEqual(package.archive_name("server/main.py"), "server/main.py")

    def test_actual_runtime_flag_is_rejected_despite_requested_signing_options(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve(); app = base / "TokenMeter.app"
            resources = app / "Contents/Resources"; resources.mkdir(parents=True)
            (resources / "TokenMeter.icns").write_bytes((ROOT / "apps/desktop/resources/TokenMeter.icns").read_bytes())
            certificate = b"synthetic certificate for verifier unit fixture"
            config = dict(self.config, certificate_sha256=hashlib.sha256(certificate).hexdigest())
            info = {"CFBundleIdentifier": config["bundle_id"], "CFBundleShortVersionString": "0.1.0",
                    "CFBundleVersion": "100", "ElectronSquirrelPreventDowngrades": True,
                    "LSMinimumSystemVersion": "15.0", "CFBundleIconFile": "TokenMeter.icns",
                    "NSAppTransportSecurity": {"NSExceptionDomains": {"127.0.0.1": {"NSExceptionAllowsInsecureHTTPLoads": True}}}}
            (app / "Contents/Info.plist").write_bytes(plistlib.dumps(info))
            (resources / "release-config.json").write_text(json.dumps(package.resource_config(config, "a" * 40, "0.1.0", "100")))

            def output(args, label, **kwargs):
                if args[0] == "lipo": return "x86_64"
                if "--extract-certificates=" in " ".join(args):
                    prefix = next(arg.split("=", 1)[1] for arg in args if arg.startswith("--extract-certificates="))
                    Path(prefix + "0").write_bytes(certificate)
                if "-r-" in args: return 'designated => identifier "org.tokenmeter.TokenMeter" and certificate leaf = H"abcd"'
                if "--verbose=4" in args: return "CodeDirectory v=20500 size=474 flags=0x10000(runtime)\nAuthority=TokenMeter Internal Distribution\nTeamIdentifier=not set"
                return ""

            with mock.patch.object(package, "run", side_effect=output):
                with self.assertRaisesRegex(package.PackageError, "runtime|validation"):
                    package.verify_app(app, config, "a" * 40, "0.1.0", "100", base / "verification")


if __name__ == "__main__": unittest.main()
