#!/usr/bin/env python3
"""Card split rule of card t_c7cc3830 (advisor's request of 2026-11-14, Part 3).

Offline checks of tracked repository files only: no live /Users/chanbla11mit/.hermes
reads, board access, network or model calls.

The card replaces, in the five orchestrator skills, the rule that split off the
parts of a card that needs a design decision with a rule that creates one card for
each part that has its own acceptance check, shortens the two passages of the
Jobcron and Cha PT skills that restated that rule, and raises each skill version by
one. The section that holds the rule in the Jobcron and Cha PT skills is named
"Task Construction", so the second passage of item 2 names Task Construction.

CARD_SPLIT_RULE_EDITS lists the exact (new, old) text the card changed in each of
the five skills. reverse_card_split_rule_edits() reverses the change byte for byte:
for a file that this card changed, when the given bytes are the bytes of that file
after this card, it returns the bytes of the file at this card's baseline commit.
test_third_glm_worker_policy.reverse_third_glm_worker_edits calls it first, so every
test that recovers the bytes of an earlier commit reverses this card's edits before
the earlier edits. This module imports no other test module, so any test module can
import it.
"""
import hashlib
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "43f9e2c2d51fd3ce8df11db341ed76e04a832fee"
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
PREFIXES = ("harness", "anki", "jss", "chapt", "jobcron")
VERSIONS = {"harness": "0.6.7-harness.11", "anki": "0.6.10-anki.9", "jss": "0.6.7-jss.14",
            "chapt": "0.6.7-chapt.12", "jobcron": "0.6.9-jobcron.13"}

NEW_RULE = (
    "By default, when the work for a card has several parts that each have their own acceptance check, "
    "create one card for each part, and link two cards only where one part needs the result of the other "
    "or both change the same files. A part that needs a design decision gets its own card, and the parts "
    "that wait for that decision depend on that card. A part that has no acceptance check of its own "
    "stays in the card of the part it belongs to. Name the exact files and the exact check command in "
    "each card. Reason: a card that names its files and its check command can run on a GLM worker, and a "
    "card that covers several parts usually stays with a Claude worker."
)
OLD_RULE = (
    "When a card needs a design decision, split off every part that has its own acceptance check and "
    "needs no design decision into a separate card that depends on the design card. Name the exact files "
    "and the exact check command in that card."
)
# Item 2, the two passages of the Jobcron and Cha PT skills: (new, old).
PASSAGE_EDITS = (
    ("- Prefer a larger bounded cap over splitting work solely to evade the timer.\n",
     "- Prefer a larger bounded cap over splitting work solely to evade the timer. Split into dependent "
     "cards when the stages have their own acceptance criteria or handoffs, including the parts that "
     "Task Construction requires to be split off a card that needs a design decision.\n"),
    ("- Do not enable automatic decomposition until observed use shows manual decomposition is the "
     "bottleneck. This does not limit the manual split that Task Construction describes.\n",
     "- Do not enable automatic decomposition until observed use shows manual decomposition is the "
     "bottleneck. This does not limit the manual split that Task Construction requires for a card that "
     "needs a design decision.\n"),
)


def skill(prefix):
    return f"policies/profile-skills/{prefix}-orchestrator/{RELATIVE}"


def _edits():
    edits = {}
    for prefix in PREFIXES:
        old_version = VERSIONS[prefix].rsplit(".", 1)[0] + "." + str(int(VERSIONS[prefix].rsplit(".", 1)[1]) - 1)
        rules = [(NEW_RULE, OLD_RULE)]
        if prefix in ("chapt", "jobcron"):
            rules = [("Use parent-child links for real dependencies. Keep independent slices parallel. "
                      + NEW_RULE + " Do not split a card only to keep every lane busy.",
                      "Use parent-child links for real dependencies. Keep independent slices parallel. "
                      + OLD_RULE + " Do not split a card only to keep every lane busy.")]
            rules.extend(PASSAGE_EDITS)
        edits[skill(prefix)] = tuple([(f"version: {VERSIONS[prefix]}\n", f"version: {old_version}\n")] + rules)
    return edits


# File -> ((new text, old text), ...), applied in this order in both directions.
CARD_SPLIT_RULE_EDITS = _edits()
# SHA-256 of each file after card t_c7cc3830.
AFTER_SHA256 = {
    skill("harness"): "623f596d8fa9df94790f40ae0029caf78cd552a4d071ac48721f03cf1d493bda",
    skill("anki"): "1a0ad2da331956dd4a195b3b5085c35d6bbd133a28765a0b17b53cc43f32ad82",
    skill("jss"): "33259158416885045d4aece8213bb7dbfe2aa1dd783c540fe2153627f5482038",
    skill("chapt"): "9b7e16c17ab179e6374fc773fd504c40a124cf76b07e56a39dd5c43645e5d138",
    skill("jobcron"): "e8734eecad69db2cba1da5568ab09457a8d1186a15c1d57917cbccb2052e5256",
}


def baseline_bytes(relative_path):
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{BASELINE}:{relative_path}"],
                          stdout=subprocess.PIPE, check=True).stdout


def reverse_card_split_rule_edits(relative_path, text):
    """Return the bytes of relative_path at BASELINE when text is that file after card
    t_c7cc3830, else text unchanged; text may be str or bytes."""
    want = AFTER_SHA256.get(relative_path)
    if want is None:
        return text
    data = text if isinstance(text, bytes) else text.encode()
    if hashlib.sha256(data).hexdigest() != want:
        return text
    old = baseline_bytes(relative_path)
    return old if isinstance(text, bytes) else old.decode()


def apply_card_split_rule_edits(relative_path, text):
    """Return the baseline text of relative_path with this card's edits applied (str)."""
    for new, old in CARD_SPLIT_RULE_EDITS.get(relative_path, ()):
        if text.count(old) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {old[:60]!r}")
        text = text.replace(old, new, 1)
    return text


class Helper(unittest.TestCase):
    def test_helper_returns_baseline_bytes_only_for_the_bytes_after_this_card(self):
        self.assertTrue(AFTER_SHA256)
        for relative_path, want in AFTER_SHA256.items():
            with self.subTest(path=relative_path):
                current = (ROOT / relative_path).read_bytes()
                self.assertEqual(hashlib.sha256(current).hexdigest(), want)
                self.assertEqual(reverse_card_split_rule_edits(relative_path, current),
                                 baseline_bytes(relative_path))
                self.assertEqual(reverse_card_split_rule_edits(relative_path, current.decode()),
                                 baseline_bytes(relative_path).decode())
                self.assertEqual(apply_card_split_rule_edits(relative_path,
                                                             baseline_bytes(relative_path).decode()),
                                 current.decode())
                other = current + b"\n"
                self.assertIs(reverse_card_split_rule_edits(relative_path, other), other)

    def test_other_paths_are_returned_unchanged(self):
        for relative_path in ("policies/profile-souls/harness-orchestrator/SOUL.md",
                              "procedures/jev-plugin.md"):
            data = (ROOT / relative_path).read_bytes()
            with self.subTest(path=relative_path):
                self.assertIs(reverse_card_split_rule_edits(relative_path, data), data)


class PolicySources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = {path: (ROOT / path).read_text() for path in CARD_SPLIT_RULE_EDITS}

    def test_every_source_states_the_new_rule_once_and_not_the_old_rule(self):
        for prefix in PREFIXES:
            text = self.text[skill(prefix)]
            with self.subTest(prefix=prefix):
                self.assertEqual(text.count(NEW_RULE), 1)
                self.assertNotIn("When a card needs a design decision", text)
                self.assertNotIn(OLD_RULE, text)
                self.assertNotIn("split off every part", text)

    def test_every_source_has_the_new_version(self):
        import re
        for prefix in PREFIXES:
            text = self.text[skill(prefix)]
            with self.subTest(prefix=prefix):
                self.assertRegex(text, rf"(?m)^version: {re.escape(VERSIONS[prefix])}$")

    def test_the_lane_sentence_is_only_in_the_jobcron_and_chapt_skills(self):
        sentence = "Do not split a card only to keep every lane busy."
        for prefix in PREFIXES:
            text = self.text[skill(prefix)]
            with self.subTest(prefix=prefix):
                if prefix in ("chapt", "jobcron"):
                    self.assertEqual(text.count(sentence), 1)
                else:
                    self.assertNotIn(sentence, text)
                    for word in ("decompos", "lane busy", "evade the timer"):
                        self.assertNotIn(word, text)

    def test_the_two_passages_have_their_new_text_in_jobcron_and_chapt(self):
        for prefix in ("chapt", "jobcron"):
            text = self.text[skill(prefix)]
            with self.subTest(prefix=prefix):
                for new, old in PASSAGE_EDITS:
                    self.assertEqual(text.count(new), 1)
                    self.assertNotIn(old, text)
                self.assertNotIn("including the parts that Task Construction requires", text)
                self.assertNotIn("requires for a card that needs a design decision", text)

    def test_the_sentences_around_the_rule_stay(self):
        for prefix in ("chapt", "jobcron"):
            text = self.text[skill(prefix)]
            with self.subTest(prefix=prefix):
                self.assertEqual(text.count("Use parent-child links for real dependencies. "
                                            "Keep independent slices parallel."), 1)
        for prefix in ("harness", "anki", "jss"):
            text = self.text[skill(prefix)]
            with self.subTest(prefix=prefix):
                self.assertEqual(text.count("\n" + NEW_RULE + "\n"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
