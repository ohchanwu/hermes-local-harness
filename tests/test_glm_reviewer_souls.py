#!/usr/bin/env python3
"""The SOUL.md sources of the five <board>-reviewer-glm profiles (card t_92a5f02e, repository only).

Offline checks of tracked repository files only: no live profile, board, network or
model observation, and no write under /Users/chanbla11mit/.hermes. Each source states
that the GLM reviewer is the first reviewer of a card that a GLM worker of its board
implemented, returns findings with `kanban_request_changes`, ends a review without
findings with `kanban_block` and a reason that starts with `jev-glm-review-pass`, and
never calls `kanban_complete` or `kanban_request_review`. Four of the five sources have
a `profile_souls` entry; `jobcron-reviewer-glm` has none, as `jobcron-reviewer` has none.
"""
import importlib.machinery
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROSTER = ROOT / "roster.yaml"
SNAPSHOT = ROOT / "snapshots/sanitized-current-state.yaml"
VERIFY = ROOT / "scripts/verify-state"

# Profile prefix -> Kanban board name.
BOARDS = {"harness": "harness", "chapt": "cha-pt", "jss": "jss-genr", "anki": "anki", "jobcron": "jobcron"}
# The GLM reviewers whose board's Opus reviewer has a profile_souls entry.
SOUL_ENTRY_PREFIXES = ("chapt", "harness", "jss", "anki")
PASS_REASON = "jev-glm-review-pass"
FORBIDDEN_CALLS = ("kanban_complete", "kanban_request_review")
# A sentence forbids a call when it contains "never" or "do not".
FORBIDDING_WORDS = re.compile(r"\b(never|do not)\b", re.IGNORECASE)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_verifier():
    spec = importlib.util.spec_from_loader(
        "verify_state", importlib.machinery.SourceFileLoader("verify_state", str(VERIFY)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_path(prefix):
    return ROOT / f"policies/profile-souls/{prefix}-reviewer-glm/SOUL.md"


def sentences(text):
    return [part.strip() for part in SENTENCE_END.split(text) if part.strip()]


def soul_entry(prefix):
    name = f"{prefix}-reviewer-glm"
    return {"source": f"policies/profile-souls/{name}/SOUL.md",
            "live": f"/Users/chanbla11mit/.hermes/profiles/{name}/SOUL.md"}


class GlmReviewerSoulSources(unittest.TestCase):
    def text(self, prefix):
        return source_path(prefix).read_text(encoding="utf-8")

    def test_each_source_exists(self):
        for prefix in BOARDS:
            with self.subTest(prefix=prefix):
                self.assertTrue(source_path(prefix).is_file())

    def test_names_board_glm_workers_and_opus_reviewer(self):
        for prefix, board in BOARDS.items():
            text = self.text(prefix)
            with self.subTest(prefix=prefix):
                self.assertTrue(text.startswith(f"You are the independent GLM reviewer of board `{board}`"))
                self.assertIn("model `glm-5.3` with provider `zai`", text)
                for number in (1, 2, 3):
                    self.assertIn(f"`{prefix}-worker-glm-{number}`", text)
                self.assertIn(f"Only the board's Opus reviewer `{prefix}-reviewer` approves a card.", text)
                self.assertIn(f"The card's `Reviewer EXACT` line names the Opus reviewer `{prefix}-reviewer`; "
                              "that is not a mismatch.", text)

    def test_names_the_review_end_calls(self):
        for prefix in BOARDS:
            text = self.text(prefix)
            with self.subTest(prefix=prefix):
                self.assertIn("`kanban_request_changes`", text)
                self.assertIn("`kanban_block`", text)
                self.assertIn(PASS_REASON, text)
                self.assertIn(f"end the review with one `kanban_block` call whose `reason` starts with "
                              f"`{PASS_REASON}`", text)
                self.assertIn("When the review has any finding, end the review with `kanban_request_changes`",
                              text)
                self.assertIn("Do not call any other Kanban tool after that call, and do not run "
                              "`hermes kanban` commands.", text)

    def test_a_mismatch_block_reason_does_not_start_with_the_pass_reason(self):
        for prefix in BOARDS:
            text = self.text(prefix)
            with self.subTest(prefix=prefix):
                self.assertIn("Accept a card only when this profile claimed it from status `review`", text)
                self.assertIn(f"a `reason` that names the mismatch and does not start with `{PASS_REASON}`", text)

    def test_every_sentence_that_names_a_refused_call_forbids_it(self):
        for prefix in BOARDS:
            named = [s for s in sentences(self.text(prefix)) if any(call in s for call in FORBIDDEN_CALLS)]
            with self.subTest(prefix=prefix):
                self.assertTrue(named)
                for sentence in named:
                    self.assertRegex(sentence, FORBIDDING_WORDS, sentence)
                self.assertIn("Never call `kanban_complete` or `kanban_request_review`.", named)

    def test_no_approval_sentence_of_the_opus_reviewer(self):
        for prefix in BOARDS:
            text = self.text(prefix)
            with self.subTest(prefix=prefix):
                self.assertNotIn("Use `kanban_complete` for approval", text)
                self.assertNotIn("Use `kanban_complete` for scoped approval", text)
                self.assertNotIn("in the approval.", text)

    def test_not_described_as_an_implementation_worker(self):
        for prefix in BOARDS:
            text = self.text(prefix)
            with self.subTest(prefix=prefix):
                self.assertNotRegex(text, re.compile(r"implementation worker", re.IGNORECASE))
                self.assertNotIn("You are a ", text)

    def test_wording_and_test_rule_blocks_are_kept(self):
        blocks = [(ROOT / "policies/writing-rules.md").read_text(encoding="utf-8"),
                  (ROOT / "policies/stale-test-rule.md").read_text(encoding="utf-8")]
        for prefix in BOARDS:
            text = self.text(prefix)
            for block in blocks:
                with self.subTest(prefix=prefix, block=block[:30]):
                    self.assertIn(block, text)


class ProfileSoulEntries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = load(ROSTER)["profile_souls"]
        cls.snapshot = load(SNAPSHOT)["profile_souls"]

    def test_four_entries_after_the_opus_reviewer(self):
        for label, souls in (("roster", self.roster), ("snapshot", self.snapshot)):
            names = list(souls)
            for prefix in SOUL_ENTRY_PREFIXES:
                name = f"{prefix}-reviewer-glm"
                with self.subTest(file=label, profile=name):
                    self.assertEqual(souls.get(name), soul_entry(prefix))
                    self.assertEqual(names[names.index(f"{prefix}-reviewer") + 1], name)

    def test_no_entry_for_the_jobcron_glm_reviewer(self):
        for souls in (self.roster, self.snapshot):
            self.assertNotIn("jobcron-reviewer-glm", souls)
            self.assertNotIn("jobcron-reviewer", souls)

    def test_roster_and_snapshot_are_equal(self):
        self.assertEqual(self.roster, self.snapshot)

    def test_verifier_profile_names(self):
        verifier = load_verifier()
        self.assertEqual(list(verifier.PROFILE_SOUL_PATHS), list(self.roster))
        for prefix in SOUL_ENTRY_PREFIXES:
            self.assertEqual(verifier.PROFILE_SOUL_PATHS[f"{prefix}-reviewer-glm"], soul_entry(prefix))
        self.assertNotIn("jobcron-reviewer-glm", verifier.PROFILE_SOUL_PATHS)
        errors = []
        verifier.check_profile_souls(errors, self.roster)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
