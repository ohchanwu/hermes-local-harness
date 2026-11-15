#!/usr/bin/env python3
"""The five Opus reviewer SOUL sources accept an earlier GLM review run on a card (card t_be416943).

Offline checks of tracked repository files only: no live profile, board, network or model
observation, and no write under /Users/chanbla11mit/.hermes. Each source of
`<prefix>-reviewer` states, in the paragraph that verifies the implementing profile (for
`jobcron-reviewer`, the first paragraph, which states the accepted implementers), that the
implementing profile is the implementer of the card's latest `review_requested` event, that
an earlier run of `<prefix>-reviewer-glm` on the card is not a mismatch (a run with outcome
`blocked` whose block reason starts with `jev-glm-review-pass`, and `changes_requested`
events whose `reviewer` is the GLM reviewer), that the GLM reviewer cannot approve a card,
and that the other boundary checks are unchanged. The approval with `kanban_complete` and
the existing mismatch rule of each source are kept, and reversing the card's edits gives the
bytes of each source at the card's baseline.
"""
import hashlib
import unittest
from pathlib import Path

from opus_reviewer_glm_review_edits import (
    APPROVAL_SENTENCE, BASELINE_SHA256, PASS_REASON, PREFIXES, UNCHANGED_CHECKS_SENTENCE, added_text,
    glm_review_run_sentences, implementing_profile_sentence, reverse_opus_reviewer_glm_review_edits, soul)

ROOT = Path(__file__).resolve().parents[1]

# Profile prefix -> the approval sentence and the mismatch rule that the source had at the
# card's baseline and still has.
KEPT = {
    "harness": ("Use `kanban_complete` for approval", "Reject and block any boundary mismatch."),
    "chapt": ("Use `kanban_complete` for approval",
              "Reject and block any boundary mismatch or in-place repository switch."),
    "jss": ("Use `kanban_complete` for approval", "Reject and block any boundary mismatch."),
    "anki": ("Use `kanban_complete` for approval", "Reject and block any boundary mismatch."),
    "jobcron": ("Use `kanban_complete` for scoped approval",
                "Reject and block any project, workspace, or authorship boundary mismatch."),
}


def source_bytes(prefix):
    return (ROOT / soul(f"{prefix}-reviewer")).read_bytes()


def paragraphs(text):
    return [part for part in text.split("\n\n") if part.strip()]


class OpusReviewerGlmReviewText(unittest.TestCase):
    def text(self, prefix):
        return source_bytes(prefix).decode("utf-8")

    def test_names_the_glm_reviewer_and_the_pass_reason(self):
        for prefix in PREFIXES:
            text = self.text(prefix)
            with self.subTest(prefix=prefix):
                self.assertIn(f"`{prefix}-reviewer-glm`", text)
                self.assertEqual(text.count(PASS_REASON), 1)
                self.assertIn(f"block reason starts with `{PASS_REASON}`", text)

    def test_an_earlier_glm_review_run_is_not_a_mismatch(self):
        for prefix in PREFIXES:
            text = self.text(prefix)
            with self.subTest(prefix=prefix):
                self.assertIn(f"An earlier run of this board's GLM reviewer `{prefix}-reviewer-glm` on the card "
                              "is not a mismatch.", text)
                self.assertIn(glm_review_run_sentences(prefix), text)
                self.assertIn(f"`changes_requested` events whose `reviewer` is `{prefix}-reviewer-glm`", text)

    def test_implementing_profile_is_the_latest_review_request_implementer(self):
        for prefix in PREFIXES:
            text = self.text(prefix)
            with self.subTest(prefix=prefix):
                self.assertIn(implementing_profile_sentence(prefix), text)
                self.assertIn("the card's latest `review_requested` event names as implementer", text)

    def test_the_glm_reviewer_cannot_approve_and_the_standard_is_unchanged(self):
        for prefix in PREFIXES:
            text = self.text(prefix)
            with self.subTest(prefix=prefix):
                self.assertIn(APPROVAL_SENTENCE, text)
                self.assertIn(UNCHANGED_CHECKS_SENTENCE, text)
                self.assertIn("a reviewer profile is still a mismatch", text)

    def test_own_approval_and_existing_mismatch_rule_are_kept(self):
        for prefix in PREFIXES:
            text = self.text(prefix)
            approval, mismatch_rule = KEPT[prefix]
            with self.subTest(prefix=prefix):
                self.assertIn(approval, text)
                self.assertIn("`kanban_complete`", text)
                self.assertEqual(text.count(mismatch_rule), 1)

    def test_added_sentences_are_in_the_paragraph_with_the_mismatch_rule(self):
        for prefix in PREFIXES:
            text = self.text(prefix)
            _approval, mismatch_rule = KEPT[prefix]
            added = added_text(prefix).strip()
            with self.subTest(prefix=prefix):
                holding = [part for part in paragraphs(text) if added in part]
                self.assertEqual(len(holding), 1)
                self.assertIn(mismatch_rule, holding[0])
                self.assertTrue(holding[0].endswith(added))

    def test_reversal_gives_the_baseline_bytes(self):
        for prefix in PREFIXES:
            relative = soul(f"{prefix}-reviewer")
            data = source_bytes(prefix)
            with self.subTest(prefix=prefix):
                original = reverse_opus_reviewer_glm_review_edits(relative, data)
                self.assertNotEqual(original, data)
                self.assertEqual(hashlib.sha256(original).hexdigest(), BASELINE_SHA256[relative])
                self.assertEqual(reverse_opus_reviewer_glm_review_edits(relative, data.decode()),
                                 original.decode())
                self.assertIs(reverse_opus_reviewer_glm_review_edits(relative, original), original)

    def test_reversal_returns_other_paths_unchanged(self):
        relative = soul("harness-reviewer-glm")
        data = (ROOT / relative).read_bytes()
        self.assertIs(reverse_opus_reviewer_glm_review_edits(relative, data), data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
