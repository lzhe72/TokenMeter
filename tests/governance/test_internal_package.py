"""Internal release packaging boundaries. These are tool tests, not App E2E."""
import base64
import copy
import json
from pathlib import Path
import plistlib
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import internal_package as package


def valid_config():
    return {"release_id": "v0.1.0-20260929T074814Z", "version": "0.1.0",
            "bundle_id": "org.tokenmeter.TokenMeter", "minimum_macos": "15.0",
            "architectures": ["arm64", "x86_64"],
            "platform_matrix": [{"runner":"macos-15", "macos_major": "15", "architecture": "arm64"}, {"runner":"macos-15-intel", "macos_major": "15", "architecture": "x86_64"}],
            "build": 100, "upgrade_build": 101,
            "update_feed_url": "http://127.0.0.1:49177/appcast.xml",
            "update_public_key": base64.b64encode(b"p" * 32).decode(),
            "certificate_sha256": "a" * 64}


def valid_environment():
    return {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS",
            "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/master",
            "GITHUB_REF_PROTECTED": "true", "GITHUB_SHA": "a" * 40,
            "GITHUB_REPOSITORY": "lzhe72/TokenMeter", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_WORKFLOW": "TokenMeter internal release", "GITHUB_WORKFLOW_REF":"lzhe72/TokenMeter/.github/workflows/internal-release.yml@refs/heads/master", "RUNNER_TEMP": "/private/tmp/test-runner"}


class InternalPackageTests(unittest.TestCase):
    def test_config_accepts_exact_internal_scope(self):
        self.assertEqual(package.validate_config(valid_config())["minimum_macos"], "15.0")

    def test_config_rejects_changed_scope_or_missing_bindings(self):
        changes = {"bundle_id": "org.tokenmeter.TokenMeter.UITesting", "minimum_macos": "14.0",
                   "architectures": ["arm64"], "upgrade_build": 100,
                   "update_feed_url": "http://192.0.2.1/appcast.xml", "certificate_sha256": "no",
                   "update_public_key": base64.b64encode(b"p" * 31).decode(), "build": True}
        for key, value in changes.items():
            with self.subTest(key=key):
                config = valid_config(); config[key] = value
                with self.assertRaises(package.PackageError): package.validate_config(config)
        for key in valid_config():
            with self.subTest(missing=key):
                config = valid_config(); del config[key]
                with self.assertRaises(package.PackageError): package.validate_config(config)

    def test_config_rejects_malformed_or_mismatched_release(self):
        for rid in ("v0.1.0", "v0.2.0-20260929T074814Z", "v0.1.0-20261399T990099Z"):
            config=valid_config();config["release_id"]=rid
            with self.assertRaises(package.PackageError): package.validate_config(config)

    def test_matrix_rejects_duplicate_or_wrong_platform(self):
        for matrix in ([{"macos":"15","arch":"arm64"}]*2,
                       [{"macos":"14","arch":"arm64"},{"macos":"15","arch":"x86_64"}], []):
            config=valid_config();config["platform_matrix"]=matrix
            with self.assertRaises(package.PackageError): package.validate_config(config)

    def test_ci_requires_protected_master_exact_candidate(self):
        self.assertEqual(package.validate_ci("a"*40,valid_environment())["run_id"],"123")
        for key, value in {"GITHUB_REF":"refs/heads/feature", "GITHUB_REF_PROTECTED":"false",
                           "GITHUB_SHA":"b"*40, "GITHUB_EVENT_NAME":"pull_request", "RUNNER_ENVIRONMENT":"self-hosted",
                           "GITHUB_ACTIONS":"false", "GITHUB_REPOSITORY":"other/TokenMeter", "RUNNER_OS":"Linux"}.items():
            with self.subTest(key=key):
                env=valid_environment();env[key]=value
                with self.assertRaises(package.PackageError): package.validate_ci("a"*40,env)

    def test_secret_decoding_never_echoes_secret(self):
        for text in ("do-not-print-secret",base64.b64encode(b"short").decode()):
            with self.assertRaises(package.PackageError) as error: package.decode_secret(text,32,"Ed25519 seed")
            self.assertNotIn(text,str(error.exception))

    def test_child_environment_drops_secrets_and_test_variables(self):
        env=valid_environment();env.update(TM_INTERNAL_P12_BASE64="secret",TM_INTERNAL_P12_PASSWORD="secret2",
                                        TM_INTERNAL_ED25519_SEED="secret3",TM_TEST_API_URL="test",TOKENMETER_DATABASE_URL="prod")
        child=package.child_environment(env)
        self.assertEqual(child["GITHUB_SHA"],"a"*40)
        self.assertFalse(any(k.startswith(("TM_INTERNAL_","TM_TEST_","TOKENMETER_")) for k in child))

    def test_new_output_rejects_existing_or_symlink_ancestors(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp).resolve(); existing=base/"exists";existing.mkdir()
            with self.assertRaises(package.PackageError): package.prepare_output(existing)
            link=base/"link";link.symlink_to(existing,target_is_directory=True)
            with self.assertRaises(package.PackageError): package.prepare_output(link/"new")
            path=package.prepare_output(base/"new")
            self.assertTrue(path.is_dir())
            self.assertEqual(path.stat().st_mode & 0o777,0o700)

    def make_app(self, root):
        app=root/"TokenMeter.app";(app/"Contents/MacOS").mkdir(parents=True)
        info={"CFBundleIdentifier":"org.tokenmeter.TokenMeter", "CFBundlePackageType":"APPL", "CFBundleExecutable":"TokenMeter",
              "CFBundleVersion":"100", "CFBundleShortVersionString":"0.1.0", "LSMinimumSystemVersion":"15.0",
              "SUFeedURL":"", "SUPublicEDKey":valid_config()["update_public_key"], "SUVerifyUpdateBeforeExtraction":True,
              "NSAppTransportSecurity":{"NSExceptionDomains":{h:{"NSExceptionAllowsInsecureHTTPLoads":True} for h in ("127.0.0.1","localhost","::1")}}}
        (app/"Contents/Info.plist").write_bytes(plistlib.dumps(info));(app/"Contents/MacOS/TokenMeter").write_bytes(b"binary")
        return app,info

    def test_production_app_info_and_no_test_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            app,info=self.make_app(Path(tmp).resolve())
            self.assertEqual(package.validate_app_info(app,valid_config(),100)["build"],"100")
            for key,value in (("TMTestRunID","x"),("TMTestCredentialsDirectory","/tmp/x"),("CFBundleIdentifier","org.tokenmeter.TokenMeter.UITesting"),
                              ("SUFeedURL","http://localhost:1/appcast.xml"),("SUVerifyUpdateBeforeExtraction",False),("LSMinimumSystemVersion","14.0")):
                mutated=dict(info);mutated[key]=value;(app/"Contents/Info.plist").write_bytes(plistlib.dumps(mutated))
                with self.subTest(key=key),self.assertRaises(package.PackageError):package.validate_app_info(app,valid_config(),100)

    def test_app_rejects_broad_http_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            app,info=self.make_app(Path(tmp).resolve())
            info["NSAppTransportSecurity"]["NSAllowsArbitraryLoads"]=True
            (app/"Contents/Info.plist").write_bytes(plistlib.dumps(info))
            with self.assertRaises(package.PackageError):package.validate_app_info(app,valid_config(),100)

    def test_signature_requires_stable_requirement_and_bound_certificate(self):
        details="Identifier=org.tokenmeter.TokenMeter\nCodeDirectory v=20500 size=123 flags=0x0(none)\nAuthority=TokenMeter Internal\n"
        requirement='designated => identifier "org.tokenmeter.TokenMeter" and certificate leaf = H"' + "a"*40 + '"'
        self.assertEqual(package.validate_signature(details,requirement,"a"*64,valid_config())["signature_kind"],"internal_self_signed")
        for d,r,c in ((details.replace("flags=0x0(none)","flags=0x2(adhoc)"),requirement,"a"*64),
                      (details,requirement+" and cdhash H\"123\"","a"*64),(details,requirement,"b"*64)):
            with self.assertRaises(package.PackageError):package.validate_signature(d,r,c,valid_config())

    def test_internal_signature_without_runtime_accepts_pinned_identity(self):
        details="Identifier=org.tokenmeter.TokenMeter\nCodeDirectory v=20500 flags=0x0(none)\nAuthority=TokenMeter Internal\n"
        requirement='designated => identifier "org.tokenmeter.TokenMeter" and certificate leaf = H"' + "a"*40 + '"'
        self.assertEqual(package.validate_signature(details,requirement,"a"*64,valid_config())["signature_kind"],"internal_self_signed")

    def test_internal_signature_rejects_team_based_library_validation_flags(self):
        requirement='designated => identifier "org.tokenmeter.TokenMeter" and certificate leaf = H"' + "a"*40 + '"'
        for flags in ("0x10000(runtime)","0x2000(library-validation)","0x12000(library-validation,runtime)"):
            details="Identifier=org.tokenmeter.TokenMeter\nCodeDirectory v=20500 flags="+flags+"\n"
            with self.subTest(flags=flags),self.assertRaises(package.PackageError):
                package.validate_signature(details,requirement,"a"*64,valid_config())

    def test_internal_build_explicitly_overrides_public_runtime_without_test_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp).resolve()
            signing=SimpleNamespace(identity="A"*40,keychain=base/"private keychain")
            with patch.object(package,"run") as command,patch.object(package,"verify_app",return_value={"code_sign_identity":"A"*40}):
                package.build_app(base,base,base,valid_config(),100,signing)
            arguments=command.call_args.args[0]
            self.assertIn("ENABLE_HARDENED_RUNTIME=NO",arguments)
            self.assertNotIn("ENABLE_HARDENED_RUNTIME=YES",arguments)
            self.assertIn("SWIFT_ACTIVE_COMPILATION_CONDITIONS=",arguments)
            self.assertIn("Release",arguments)
            self.assertIn("CODE_SIGN_IDENTITY="+signing.identity,arguments)

    def test_artifact_requires_regular_nonempty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp).resolve();file=base/"candidate.zip";file.write_bytes(b"zip")
            self.assertEqual(package.artifact(file,base)["bytes"],3)
            link=base/"link";link.symlink_to(file)
            with self.assertRaises(package.PackageError):package.artifact(link,base)
            file.write_bytes(b"")
            with self.assertRaises(package.PackageError):package.artifact(file,base)

    def test_dmg_layout_accepts_only_expected_installation_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp).resolve();mount=base/"mounted";mount.mkdir()
            installation=base/"source.md";installation.write_text("Install this internal build")
            (mount/"TokenMeter.app").mkdir()
            (mount/"Applications").symlink_to("/Applications")
            (mount/"INSTALLATION.txt").write_bytes(installation.read_bytes())
            package.validate_dmg_layout(mount,installation)
            extra=mount/"private.p12";extra.write_bytes(b"synthetic secret sentinel")
            with self.assertRaises(package.PackageError):package.validate_dmg_layout(mount,installation)
            extra.unlink()
            (mount/"INSTALLATION.txt").unlink();(mount/"INSTALLATION.txt").symlink_to(installation)
            with self.assertRaises(package.PackageError):package.validate_dmg_layout(mount,installation)

    def test_dmg_layout_rejects_wrong_app_destination_or_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp).resolve();mount=base/"mounted";mount.mkdir()
            installation=base/"source.md";installation.write_text("Install this internal build")
            (mount/"TokenMeter.app").mkdir();(mount/"Applications").symlink_to("/Applications")
            (mount/"INSTALLATION.txt").write_text("different instructions")
            with self.assertRaises(package.PackageError):package.validate_dmg_layout(mount,installation)
            (mount/"INSTALLATION.txt").write_bytes(installation.read_bytes())
            (mount/"Applications").unlink();(mount/"Applications").symlink_to("/tmp")
            with self.assertRaises(package.PackageError):package.validate_dmg_layout(mount,installation)
            (mount/"Applications").unlink();(mount/"Applications").symlink_to("/Applications")
            (mount/"TokenMeter.app").rmdir();(mount/"TokenMeter.app").symlink_to(base)
            with self.assertRaises(package.PackageError):package.validate_dmg_layout(mount,installation)

    def test_packaging_rejects_an_extra_file_in_mounted_dmg(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp).resolve();installation=base/"source.md";installation.write_text("Install this internal build")
            info={"tree_sha256":"a"*64}
            def run_tool(arguments,*args,**kwargs):
                if arguments[0:2]==["hdiutil","attach"]:
                    mount=Path(arguments[arguments.index("-mountpoint")+1])
                    (mount/"TokenMeter.app").mkdir()
                    (mount/"Applications").symlink_to("/Applications")
                    (mount/"INSTALLATION.txt").write_bytes(installation.read_bytes())
                    (mount/"private.p12").write_bytes(b"synthetic secret sentinel")
                return ""
            with patch.object(package,"run",side_effect=run_tool),patch.object(package,"tree_sha256",return_value="a"*64),patch.object(package,"verify_app",return_value=info):
                with self.assertRaises(package.PackageError):
                    package.make_dmg(base/"TokenMeter.app",base/"package.dmg",base,valid_config(),info,installation)

    def test_tree_hash_includes_symlink_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/"file").write_bytes(b"data");link=root/"link";link.symlink_to("file")
            before=package.tree_sha256(root);link.unlink();link.symlink_to("elsewhere")
            self.assertNotEqual(before,package.tree_sha256(root))


if __name__ == "__main__":unittest.main()
