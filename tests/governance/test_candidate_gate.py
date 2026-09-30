"""Candidate identity checks use real isolated Git repositories, never product evidence."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("candidate_gate", REPO / "scripts/candidate_gate.py")
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)


class CandidateGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Governance test")
        (self.root / "releases").mkdir()
        self.release_id = "v0.1.0-20260929T040000Z"
        (self.root / "releases/current.json").write_text(json.dumps({"release_id": self.release_id}))
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.sha = self.git("rev-parse", "HEAD")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

    def check(self, **changes):
        args = dict(root=self.root, candidate_sha=self.sha, event="workflow_dispatch",
                    workflow_ref="refs/heads/main", default_branch="main", dispatch_sha=self.sha)
        args.update(changes)
        return candidate.validate_context(**args)

    def test_unpublished_candidate_needs_no_tag(self):
        self.assertEqual([], self.check())
        self.assertEqual("", self.git("tag", "--list"))

    def test_rejects_short_or_injected_sha(self):
        for sha in (self.sha[:8], "main", self.sha + "\n", "$(touch injected)"):
            with self.subTest(sha=sha):
                self.assertTrue(self.check(candidate_sha=sha))
        self.assertFalse((self.root / "injected").exists())

    def test_rejects_different_checkout(self):
        self.assertTrue(self.check(candidate_sha="0" * 40))

    def test_rejects_commit_outside_default_branch_dispatch(self):
        errors = self.check(dispatch_sha="0" * 40)
        self.assertTrue(any("default-branch dispatch SHA" in error for error in errors), errors)
        self.assertTrue(self.check(dispatch_sha="invalid"))

    def test_rejects_untrusted_trigger(self):
        self.assertTrue(self.check(event="push"))
        self.assertTrue(self.check(workflow_ref="refs/tags/" + self.release_id))
        self.assertTrue(self.check(workflow_ref="refs/heads/feature"))
        self.assertTrue(self.check(default_branch=""))

    def test_rejects_dirty_candidate(self):
        (self.root / "untracked").write_text("uncommitted")
        self.assertTrue(self.check())

    def test_rejects_tag_already_created(self):
        self.git("tag", self.release_id)
        self.assertTrue(self.check())

    def test_rejects_invalid_release_index(self):
        (self.root / "releases/current.json").write_text(json.dumps({"release_id": "--all"}))
        self.git("add", ".")
        self.git("commit", "-qm", "invalid fixture")
        next_sha = self.git("rev-parse", "HEAD")
        self.assertTrue(self.check(candidate_sha=next_sha, dispatch_sha=next_sha))

    def test_cli_pass_is_context_only(self):
        process = subprocess.run(["python3", str(REPO / "scripts/candidate_gate.py"),
                                  "--root", str(self.root), "--candidate-sha", self.sha,
                                  "--event", "workflow_dispatch", "--workflow-ref", "refs/heads/main",
                                  "--default-branch", "main", "--dispatch-sha", self.sha],
                                 text=True, capture_output=True)
        self.assertEqual(0, process.returncode, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual("candidate_context_only", result["scope"])
        self.assertFalse(result["release_eligible"])

    def test_workflows_validate_before_tag(self):
        regular = (REPO / ".github/workflows/quality.yml").read_text()
        self.assertNotIn("tags:", regular)
        self.assertIn("python3 scripts/quality_gate.py iteration", regular)
        dispatch = (REPO / ".github/workflows/release-candidate.yml").read_text()
        self.assertIn("workflow_dispatch:", dispatch)
        self.assertIn("environment: release-validation", dispatch)
        self.assertIn("ref: ${{ inputs.candidate_sha }}", dispatch)
        self.assertIn('test "$TM_CANDIDATE_SHA" = "$GITHUB_SHA"', dispatch)
        self.assertLess(dispatch.index('test "$TM_CANDIDATE_SHA" = "$GITHUB_SHA"'),
                        dispatch.index("actions/checkout@v4"))
        self.assertIn('--dispatch-sha "$GITHUB_SHA"', dispatch)
        self.assertIn("python3 scripts/quality_gate.py release", dispatch)
        self.assertLess(dispatch.index("scripts/candidate_gate.py"), dispatch.index("scripts/quality_gate.py release"))
        self.assertNotIn("contents: write", dispatch)
        self.assertNotIn("continue-on-error:", dispatch)

    def test_environment_diagnostic_cannot_replace_pr_gate_or_package(self):
        workflow = (REPO / ".github/workflows/quality.yml").read_text()
        self.assertIn("environment_probe_only:", workflow)
        self.assertIn("type: boolean\n        required: false\n        default: false", workflow)
        product_condition = "github.event_name != 'workflow_dispatch' || inputs.environment_probe_only != true"
        diagnostic_condition = "github.event_name == 'workflow_dispatch' && inputs.environment_probe_only == true"
        steps = workflow.split("      - name: ")
        product = next(step for step in steps if step.startswith("Execute product gate\n"))
        diagnostic = next(step for step in steps if step.startswith("Diagnose isolated environment only\n"))
        self.assertIn("if: ${{ " + product_condition + " }}", product)
        self.assertIn("python3 scripts/quality_gate.py iteration", product)
        self.assertIn("if: ${{ " + diagnostic_condition + " }}", diagnostic)
        self.assertIn("python3 scripts/native_environment.py", diagnostic)
        self.assertNotIn("quality_gate.py", diagnostic)
        for name in ("Package local-only preview DMG", "Retain local-only preview DMG"):
            step = next(step for step in steps if step.startswith(name))
            self.assertIn("(" + product_condition + ")", step)
        # Distinct check and artifact identities prevent READY being mistaken for product PASS.
        distinct_name = diagnostic_condition + " && 'environment-diagnostic' || 'product-e2e'"
        self.assertEqual(2, workflow.count(distinct_name))
        self.assertIn("runner: [macos-15, macos-15-intel]", workflow)
        self.assertNotIn("continue-on-error:", workflow)


if __name__ == "__main__":
    unittest.main()
