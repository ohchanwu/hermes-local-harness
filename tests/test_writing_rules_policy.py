#!/usr/bin/env python3
"""Offline contracts for the fleet-wide writing rules (t_a1208da3).

policies/writing-rules.md is appended verbatim to every tracked profile SOUL, and
scripts/verify-state requires each SOUL to contain the whole policy as one exact
substring. Fixture-mode cases run the real verifier main() under the worktree-only
read guard; cases that change tracked content do so in a temporary repository copy.
"""
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from incident_recovery_verify_fixture import ROOT
from test_verify_state_derived_expectations import TempTree, TreeReads, load, redeployed, tree_verifier
from jss_download_install_edits import reverse_download_install_edits
from test_jobcron_app_only_deploy_authorization import reverse_app_only_deploy_edits
from test_jss_fleet_policy import reverse_read_only_exception_edits
from test_jev_policy_sources import reverse_jev_policy_edits
from test_stale_test_rule_policy import reverse_stale_test_rule_edits

BASELINE = "b7093717054754283c6f9ac671a227f695fec9b5"
POLICY = "policies/writing-rules.md"
POLICY_SHA256 = "36609ae76520b9eef3aa4d8cf795f7844aebc91fb8e0ee072b0843d232d2044c"
REVIEWERS = ("chapt-reviewer", "harness-reviewer", "jobcron-reviewer", "jss-reviewer")
LATER_SOULS = ("anki-orchestrator", "anki-worker", "anki-worker-2", "anki-reviewer",
               "anki-worker-glm-1", "anki-worker-glm-2")
# The SOULs of the third GLM workers (card t_f4ce916d) were written after card t_46b5e63e, with
# its stale test rule already appended after the block.
THIRD_GLM_SOULS = ("anki-worker-glm-3", "chapt-worker-glm-3", "harness-worker-glm-3", "jss-worker-glm-3")
REVIEWER_SENTENCE = (b"Reject a card, document, or commit that introduces a coined compound term or a "
                     b"'(project term)' that is not defined in the repository glossary.\n")
OK = "OK: desired state matches observed state"


def baseline_bytes(rel):
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{BASELINE}:{rel}"],
                          stdout=subprocess.PIPE, check=True).stdout


def run_main(root, fixture, extra=()):
    """(exit code, set of FAIL lines, full output) of fixture-mode main() over root."""
    verifier = tree_verifier(root)
    output = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="writing-rules-obs-") as directory:
        path = Path(directory) / "observation.yaml"
        path.write_text(json.dumps(fixture))
        with TreeReads(root, (path, *extra)), \
                patch.object(sys, "argv", ["TEST-ONLY", "--fixture", str(path)]), redirect_stdout(output):
            code = verifier.main()
    text = output.getvalue()
    return code, {line[len("FAIL: "):] for line in text.splitlines() if line.startswith("FAIL: ")}, text


class TrackedText(unittest.TestCase):
    def test_policy_file_is_the_exact_block(self):
        data = (ROOT / POLICY).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), POLICY_SHA256)
        self.assertEqual(len(data), 862)
        self.assertEqual(data.count(b"\n"), 6)
        self.assertTrue(data.isascii())

    def test_every_soul_is_its_baseline_bytes_plus_the_exact_append(self):
        block = (ROOT / POLICY).read_bytes()
        all_souls = sorted((ROOT / "policies/profile-souls").glob("*/SOUL.md"))
        # SOULs added after BASELINE (the anki fleet, t_06fc410a; the anki GLM workers,
        # t_71b4ef4a) have no baseline bytes; they were written with the block already at
        # their end.
        later = {path for path in all_souls if path.parent.name in (*LATER_SOULS, *THIRD_GLM_SOULS)}
        self.assertEqual({path.parent.name for path in later}, {*LATER_SOULS, *THIRD_GLM_SOULS})
        stale_rule = b"\n" + (ROOT / "policies/stale-test-rule.md").read_bytes()
        for path in sorted(later):
            with self.subTest(profile=path.parent.name):
                # The later append of card t_46b5e63e is reversed first.
                text = reverse_stale_test_rule_edits(path.relative_to(ROOT).as_posix(), path.read_bytes())
                if path.parent.name in THIRD_GLM_SOULS:
                    self.assertTrue(text.endswith(stale_rule))
                    text = text[:-len(stale_rule)]
                self.assertTrue(text.endswith(b"\n\n" + block))
                self.assertEqual(text.count(block), 1)
                self.assertEqual(text.count(REVIEWER_SENTENCE), 1 if path.parent.name == "anki-reviewer" else 0)
        souls = [path for path in all_souls if path not in later]
        self.assertEqual(len(souls), 20)
        self.assertEqual({path.parent.name for path in souls} & set(REVIEWERS), set(REVIEWERS))
        for path in souls:
            profile = path.parent.name
            with self.subTest(profile=profile):
                old = baseline_bytes(path.relative_to(ROOT).as_posix())
                self.assertNotIn(block, old)
                want = old if old.endswith(b"\n") else old + b"\n"
                if profile in REVIEWERS:
                    want += b"\n" + REVIEWER_SENTENCE
                want += b"\n" + block
                # The later owner-requested application-only production deploy exception
                # (t_b7455361) changed line 7 of the jobcron-orchestrator SOUL; reverse it first.
                # The jev plugin policy change (t_b722c617, and t_71b4ef4a for jss-genr) is the
                # latest change before the download and install change (t_89838618), which is
                # reversed first.
                relative = path.relative_to(ROOT).as_posix()
                text = reverse_download_install_edits(relative, path.read_bytes())
                text = reverse_jev_policy_edits(relative, text)
                text = reverse_app_only_deploy_edits(relative, reverse_read_only_exception_edits(relative, text))
                self.assertEqual(text, want)
                self.assertTrue(text.endswith(block))
                self.assertEqual(text.count(REVIEWER_SENTENCE), 1 if profile in REVIEWERS else 0)


class VerifierCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean = load(ROOT / "tests/fixtures/clean.yaml")
        cls.verifier = tree_verifier(ROOT)

    def test_clean_fixture_passes_with_the_check_active(self):
        self.assertTrue(callable(self.verifier.check_writing_rules))
        code, fails, output = run_main(ROOT, self.clean)
        self.assertEqual((code, fails), (0, set()), output)
        self.assertIn(OK, output)

    def tracked_change(self, profile, change):
        """Fixture run over a temporary tree whose tracked SOUL was changed and then
        redeployed (live hash equals the changed source), isolating the new check."""
        with TempTree() as root:
            soul = root / f"policies/profile-souls/{profile}/SOUL.md"
            soul.write_bytes(change(soul.read_bytes()))
            return run_main(root, redeployed(tree_verifier(root), self.clean))

    # (a)
    def test_soul_missing_the_block_fails(self):
        code, fails, output = self.tracked_change(
            "chapt-worker", lambda _: baseline_bytes("policies/profile-souls/chapt-worker/SOUL.md"))
        # The SOUL at BASELINE also lacks policies/stale-test-rule.md (card t_46b5e63e).
        self.assertEqual((code, fails), (1, {"writing rules missing from tracked SOUL chapt-worker",
                                             "policy block policies/stale-test-rule.md missing from tracked SOUL "
                                             "chapt-worker"}), output)

    # (b)
    def test_block_with_one_changed_word_fails(self):
        old, new = b"Prefer longer precise wording", b"Prefer shorter precise wording"

        def change(text):
            self.assertEqual(text.count(old), 1)
            return text.replace(old, new)
        code, fails, output = self.tracked_change("harness-reviewer", change)
        self.assertEqual((code, fails), (1, {"writing rules missing from tracked SOUL harness-reviewer"}), output)

    # (c) fixture mode observes the live SOUL by hash; a drifted live copy FAILs.
    def test_live_soul_drifted_from_tracked_source_fails_in_fixture_mode(self):
        fixture = copy.deepcopy(self.clean)
        fixture["profile_soul_hashes"]["jss-worker"] = hashlib.sha256(
            baseline_bytes("policies/profile-souls/jss-worker/SOUL.md")).hexdigest()
        code, fails, output = run_main(ROOT, fixture)
        self.assertEqual((code, fails), (1, {"profile SOUL drift jss-worker"}), output)

    # (c) live mode reads each live copy and compares the whole block.
    def test_live_mode_requires_the_block_in_each_live_copy(self):
        block = (ROOT / POLICY).read_bytes()
        tracked = {profile: (ROOT / entry["source"]).read_bytes()
                   for profile, entry in self.verifier.PROFILE_SOUL_PATHS.items()}
        with tempfile.TemporaryDirectory(prefix="writing-rules-live-") as directory:
            live = {profile: Path(directory) / profile / "SOUL.md" for profile in tracked}
            for profile, path in live.items():
                path.parent.mkdir()
                path.write_bytes(tracked[profile])
            live["jss-worker"].write_bytes(baseline_bytes("policies/profile-souls/jss-worker/SOUL.md"))
            live["chapt-worker"].write_bytes(tracked["chapt-worker"].replace(b"Boring", b"Plain"))
            live["harness-worker"].write_bytes(tracked["harness-worker"] + b"\nLocal note.\n")  # drift, block kept
            live["jss-reviewer"].unlink()
            paths = {profile: {**entry, "live": str(live[profile])}
                     for profile, entry in self.verifier.PROFILE_SOUL_PATHS.items()}
            errors = []
            with patch.dict(self.verifier.PROFILE_SOUL_PATHS, paths), redirect_stdout(io.StringIO()):
                self.verifier.check_writing_rules(errors, live=True)
        self.assertIn(block, tracked["harness-worker"])
        # jss-worker (bytes at BASELINE) and jss-reviewer (removed) also lack
        # policies/stale-test-rule.md (card t_46b5e63e).
        self.assertEqual(sorted(errors), [
            "policy block policies/stale-test-rule.md missing from live SOUL jss-reviewer",
            "policy block policies/stale-test-rule.md missing from live SOUL jss-worker",
            "writing rules missing from live SOUL chapt-worker",
            "writing rules missing from live SOUL jss-reviewer",
            "writing rules missing from live SOUL jss-worker",
        ])

    def test_missing_or_empty_policy_file_fails(self):
        for label, change in (("missing", Path.unlink), ("empty", lambda path: path.write_bytes(b""))):
            with self.subTest(policy=label), TempTree() as root:
                change(root / POLICY)
                code, fails, output = run_main(root, self.clean, extra=(root / POLICY,))
                self.assertEqual(code, 1, output)
                self.assertEqual(fails, {"writing rules policy missing or unreadable: policies/writing-rules.md"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
