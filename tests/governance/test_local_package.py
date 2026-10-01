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
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("local_package", ROOT / "scripts/local_package.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class LocalPackageTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "releases/v0.1.0-20260929T074814Z/local-release.json").read_text())

    def tm002_config(self):
        return dict(self.config, schema_version=2, release_id="v0.2.0-20261001T034118Z", version="0.2.0",
                    upgrade_version="0.2.1", build="200", upgrade_build="201",
                    upgrade_from_release_id="v0.1.0-20260929T074814Z",
                    upgrade_source_policy="sop018_pass_sop020_archived_original_dmg")

    def test_tm002_config_requires_approved_version_build_and_release(self):
        config = self.tm002_config()
        self.assertEqual(package.validate_config(config)["build"], "200")
        actual = json.loads((ROOT / "releases/v0.2.0-20261001T034118Z/local-release.json").read_text())
        self.assertEqual(actual, config)
        self.assertEqual(package.validate_config(actual)["schema_version"], 2)
        for change in (dict(version="0.1.0"), dict(build="100"), dict(upgrade_version="0.1.1"),
                       dict(upgrade_build="101"), dict(release_id="v0.1.0-20261001T034118Z"),
                       dict(release_id="v0.2.0-20260230T034118Z"), dict(schema_version=1),
                       dict(upgrade_from_release_id="v0.1.1-20260929T074814Z"),
                       dict(upgrade_source_policy="candidate_dmg")):
            with self.subTest(change=change), self.assertRaises(package.PackageError):
                package.validate_config(dict(config, **change))
        for missing in ("upgrade_from_release_id", "upgrade_source_policy"):
            with self.subTest(missing=missing), self.assertRaises(package.PackageError):
                reduced = dict(config); del reduced[missing]
                package.validate_config(reduced)
        for extra in ("upgrade_from_release_id", "upgrade_source_policy"):
            with self.subTest(extra=extra), self.assertRaises(package.PackageError):
                package.validate_config(dict(self.config, **{extra: config[extra]}))

    def test_tm002_builder_places_helper_in_contents_helpers(self):
        helper = Path("/owned/source-helper")
        config = package.builder_configuration(self.tm002_config(), "a" * 40, "0.2.0", "200",
                                               Path("/owned/output"), Path("/owned/config.json"), helper)
        self.assertEqual(config["extraFiles"], [{"from": str(helper), "to": "Helpers/source-helper"}])
        with self.assertRaisesRegex(package.PackageError, "helper"):
            package.builder_configuration(self.tm002_config(), "a" * 40, "0.2.0", "200",
                                          Path("/owned/output"), Path("/owned/config.json"), None)

    def test_tm002_helper_missing_symlink_or_tampered_digest_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve(); app = base / "TokenMeter.app"
            helper_dir = app / "Contents/Helpers"; helper_dir.mkdir(parents=True)
            expected = hashlib.sha256(b"signed helper").hexdigest()
            with self.assertRaisesRegex(package.PackageError, "helper"):
                package.verify_native_helper(app, self.tm002_config(), base / "verify", expected)
            outside = base / "outside"; outside.write_bytes(b"signed helper")
            helper = helper_dir / "source-helper"; helper.symlink_to(outside)
            with self.assertRaisesRegex(package.PackageError, "helper"):
                package.verify_native_helper(app, self.tm002_config(), base / "verify", expected)
            helper.unlink(); helper.write_bytes(b"modified helper"); helper.chmod(0o755)
            with self.assertRaisesRegex(package.PackageError, "helper"):
                package.verify_native_helper(app, self.tm002_config(), base / "verify", expected)
            self.assertEqual(outside.read_bytes(), b"signed helper")

    def test_tm002_helper_requires_executable_mode_arch_and_same_certificate(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve(); app = base / "TokenMeter.app"
            helper_dir = app / "Contents/Helpers"; helper_dir.mkdir(parents=True)
            helper = helper_dir / "source-helper"; helper.write_bytes(b"signed helper"); helper.chmod(0o644)
            with self.assertRaisesRegex(package.PackageError, "mode"):
                package.verify_native_helper(app, self.tm002_config(), base / "verify")
            helper.chmod(0o755)
            certificate = b"synthetic helper certificate"
            config = dict(self.tm002_config(), certificate_sha256=hashlib.sha256(certificate).hexdigest())

            def output(args, label, **kwargs):
                if args[0] == "lipo": return "arm64"
                if "--extract-certificates=" in " ".join(args):
                    prefix = next(arg.split("=", 1)[1] for arg in args if arg.startswith("--extract-certificates="))
                    Path(prefix + "0").write_bytes(certificate)
                return "CodeDirectory v=20500 flags=0x0\nAuthority=TokenMeter Internal Distribution"

            with mock.patch.object(package, "run", side_effect=output):
                with self.assertRaisesRegex(package.PackageError, "architecture"):
                    package.verify_native_helper(app, config, base / "verify")
            with mock.patch.object(package, "run", side_effect=lambda args, label, **kw:
                                   "x86_64" if args[0] == "lipo" else output(args, label, **kw)):
                observed = package.verify_native_helper(app, config, base / "verify")
            self.assertEqual(observed["sha256"], hashlib.sha256(b"signed helper").hexdigest())
            self.assertEqual(observed["certificate_sha256"], config["certificate_sha256"])
            with mock.patch.object(package, "run", side_effect=lambda args, label, **kw:
                                   "x86_64" if args[0] == "lipo" else output(args, label, **kw)):
                with self.assertRaisesRegex(package.PackageError, "certificate"):
                    package.verify_native_helper(app, self.tm002_config(), base / "verify")

    def test_tm002_builds_real_x86_helper_from_checked_source(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            expected_inputs = package.native_source_digests(self.tm002_config())
            self.assertEqual(set(expected_inputs), {"apps/desktop/native/source-helper.c",
                                                    "apps/desktop/native/build-source-helper.sh"})
            helper = package.build_native_helper(base, self.tm002_config())
            self.assertEqual(helper.name, "source-helper")
            self.assertEqual(helper.stat().st_mode & 0o777, 0o755)
            self.assertEqual(package.run(["lipo", "-archs", str(helper)], "Read compiled helper"), "x86_64")
            self.assertEqual(package.native_source_digests(self.tm002_config()), expected_inputs)

    def test_tm002_original_zip_readback_rejects_missing_changed_and_duplicate_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            config = self.tm002_config()
            info = {"native_helper": {"sha256": hashlib.sha256(b"signed helper").hexdigest()}}
            archive = base / "candidate.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("TokenMeter.app/Contents/Info.plist", b"info")
            with self.assertRaisesRegex(package.PackageError, "lacks native"):
                package.verify_zip_app(archive, base, config, "a" * 40, "0.2.0", "200", info, "candidate")
            archive.unlink()
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("TokenMeter.app/Contents/Info.plist", b"info")
                output.writestr("TokenMeter.app/Contents/Helpers/source-helper", b"modified helper")
            with self.assertRaisesRegex(package.PackageError, "digest changed"):
                package.verify_zip_app(archive, base, config, "a" * 40, "0.2.0", "200", info, "candidate")
            archive.unlink()
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("TokenMeter.app/Contents/Helpers/source-helper", b"signed helper")
                output.writestr("TokenMeter.app/Contents/Helpers/source-helper", b"signed helper")
            with self.assertRaisesRegex(package.PackageError, "duplicate"):
                package.verify_zip_app(archive, base, config, "a" * 40, "0.2.0", "200", info, "candidate")

    def test_tm002_ditto_zip_allows_only_the_macos_metadata_root_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            archive = base / "candidate.zip"
            config = self.tm002_config()
            info = {"native_helper": {"sha256": hashlib.sha256(b"signed helper").hexdigest()}}
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("__MACOSX/", b"")
                output.writestr("TokenMeter.app/Contents/Helpers/source-helper", b"signed helper")
            with mock.patch.object(package, "run", side_effect=package.PackageError("readback boundary")):
                with self.assertRaisesRegex(package.PackageError, "readback boundary"):
                    package.verify_zip_app(archive, base, config, "a" * 40, "0.2.0", "200", info, "candidate")
            for name in ("__MACOSX", "rogue.txt"):
                archive.unlink()
                with zipfile.ZipFile(archive, "w") as output:
                    output.writestr(name, b"not a directory")
                    output.writestr("TokenMeter.app/Contents/Helpers/source-helper", b"signed helper")
                with self.subTest(name=name), self.assertRaisesRegex(package.PackageError, "unexpected member"):
                    package.verify_zip_app(archive, base, config, "a" * 40, "0.2.0", "200", info, "candidate")

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
