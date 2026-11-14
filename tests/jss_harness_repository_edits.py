#!/usr/bin/env python3
"""Reversal of the source edits of card t_a8884510 (owner decision, 2026-11-15).

The owner added the Harness repository `/Users/chanbla11mit/hermes-local-harness` as the
fifth repository of the read-only repository exception of `jss-orchestrator` and
`jss-reviewer` (card t_3af6293c, owner decision 2026-11-11). The card changed the one
exception line of three sources and the version line of the jss-orchestrator skill.

HARNESS_REPOSITORY_EDITS lists the exact (new text, old text) pairs of each source, in the
order in which the card applied them. reverse_harness_repository_edits() reverses them byte
for byte. test_card_split_rule_policy.reverse_card_split_rule_edits calls it first, so every
test that recovers the bytes of an earlier commit reverses this card's edits before the
edits of the earlier cards. This module imports no other test module, so any test module
can import it without a circular import.
"""

HARNESS = "/Users/chanbla11mit/hermes-local-harness"
ORCH_SOUL = "policies/profile-souls/jss-orchestrator/SOUL.md"
REVIEWER_SOUL = "policies/profile-souls/jss-reviewer/SOUL.md"
SKILL = ("policies/profile-skills/jss-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/"
         "SKILL.md")
BASELINE = "13854da8098d92dde6fccc1843c421d7c4b269f0"
# SHA-256 of the three sources at BASELINE, in the order of the card.
BASELINE_SHA256 = {
    ORCH_SOUL: "79ac395679cca0fda1a95bd3372bdeaba100eec87bc72cbc8a7142c5f98f0544",
    REVIEWER_SOUL: "699d0c0b108bd5554980f0ff84cd98255979499ea2cb2e1f58420eaf45455d3b",
    SKILL: "33259158416885045d4aece8213bb7dbfe2aa1dd783c540fe2153627f5482038",
}
OLD_VERSION = "0.6.7-jss.14"
NEW_VERSION = "0.6.7-jss.15"

# The sentences that the card added, as they appear in the exception line.
ADDED = (f"The owner added the Harness repository `{HARNESS}` to this list on 2026-11-15 (card t_a8884510); "
         "the refs, the permitted Git commands, and the prohibited Git commands below apply to it as they "
         "apply to the other repositories of this list.")
NO_HARNESS_BOARD = "This exception adds no access to board `harness`"
NO_HARNESS_BOARD_ORCH = (f"{NO_HARNESS_BOARD}: filing a card on that board under the `harness-bug-report` skill "
                         "stays as that skill states.")
NO_HARNESS_BOARD_REVIEWER = f"{NO_HARNESS_BOARD}."
BUG_REPORT_COMMAND = f"`git -C {HARNESS} rev-parse main`"
NAMED_FILES = f"`{HARNESS}/scripts/jev-peak-hold`, `{HARNESS}/scripts/check-forced-skills`"
ADDS_AND_REMOVES_NOTHING = "this exception adds the reads above and removes nothing."
NAMED_ORCH = (f"The files and the command of the Harness repository that your skills already name stay "
              f"permitted as they are: {NAMED_FILES}, and the command {BUG_REPORT_COMMAND} of the "
              f"`harness-bug-report` skill; {ADDS_AND_REMOVES_NOTHING}")
NAMED_SKILL = (f"The files and the command of the Harness repository that this skill and the "
               f"`harness-bug-report` skill already name stay permitted as they are: {NAMED_FILES}, and the "
               f"command {BUG_REPORT_COMMAND} of the `harness-bug-report` skill; {ADDS_AND_REMOVES_NOTHING}")
ONLY_COMMAND = ("The sentence of the `harness-bug-report` skill that calls that command \"the only command that "
                "you run in that repository\" describes filing a report and does not prohibit the reads of this "
                "exception.")
NAMED_REVIEWER = ("The overgating checklist of the Harness repository that the paragraph above names stays "
                  f"permitted as that paragraph states; {ADDS_AND_REMOVES_NOTHING}")
MERGED_NOT_INSTALLED = ("For the Harness repository, a commit on `main` shows what is merged, not what is "
                        "installed on a live profile; a statement that a change is installed still needs an owner "
                        "statement or a deployment record.")

_LIST_TAIL_OLD = ("`/Users/chanbla11mit/projects/cha-pt-frontend`, and "
                  "`/Users/chanbla11mit/projects/cha-webpt-website-sync`. Read from")
_LIST_TAIL_NEW = ("`/Users/chanbla11mit/projects/cha-pt-frontend`, "
                  f"`/Users/chanbla11mit/projects/cha-webpt-website-sync`, and `{HARNESS}`. {ADDED} Read from")
_PROFILES = ("the Jobcron or Cha PT profiles or their sessions,",
             "the Jobcron, Cha PT, or Harness profiles or their sessions,")
_MERGED = ("These repositories show what is merged, not what is deployed: a deploy date or a statement that a "
           "feature is live still needs an owner statement or a deployment record.")
_PRIVACY_OLD = ("carries an all-rights-reserved notice, and the Cha PT repositories, including the WebPT "
                "exporter, contain clinic operations documents.")
_PRIVACY_NEW = ("carries an all-rights-reserved notice, the Cha PT repositories, including the WebPT exporter, "
                "contain clinic operations documents, and the Harness repository contains the policy and "
                "operations documents of the owner's Hermes profiles.")
_CARD_SENTENCE = "and never create a card on board `jss-genr` pinned to any of those repositories."
_COMMON = (
    ("these five repositories:", "these four repositories:"),
    (_LIST_TAIL_NEW, _LIST_TAIL_OLD),
    (_PROFILES[1], _PROFILES[0]),
    (f"{_MERGED} {MERGED_NOT_INSTALLED}", _MERGED),
    (_PRIVACY_NEW, _PRIVACY_OLD),
)

# File -> ((new text, old text), ...), in the order in which the card applied them. Each new
# text occurs exactly once in the file after this card.
HARNESS_REPOSITORY_EDITS = {
    ORCH_SOUL: _COMMON + (
        (f"{_CARD_SENTENCE} {NO_HARNESS_BOARD_ORCH} {NAMED_ORCH} {ONLY_COMMAND}", _CARD_SENTENCE),
    ),
    REVIEWER_SOUL: _COMMON + (
        (f"{_CARD_SENTENCE} {NO_HARNESS_BOARD_REVIEWER} {NAMED_REVIEWER}", _CARD_SENTENCE),
        ("no review authority over those five repositories:", "no review authority over those four repositories:"),
    ),
    SKILL: (
        (f"version: {NEW_VERSION}\n", f"version: {OLD_VERSION}\n"),
    ) + _COMMON + (
        (f"{_CARD_SENTENCE} {NO_HARNESS_BOARD_ORCH} {NAMED_SKILL} {ONLY_COMMAND}", _CARD_SENTENCE),
    ),
}


def reverse_harness_repository_edits(relative_path, text):
    """Return text with the t_a8884510 edits reversed; text may be str or bytes. A path that
    the card did not change, and a text that contains none of the new texts, is returned as
    the same object, so a caller may apply it to a text that another caller already reversed.
    A text that contains only some of the new texts raises AssertionError."""
    edits = HARNESS_REPOSITORY_EDITS.get(relative_path)
    if not edits:
        return text
    as_bytes = isinstance(text, bytes)
    value = text.decode() if as_bytes else text
    counts = [value.count(new) for new, _old in edits]
    if not any(counts):
        return text
    if counts != [1] * len(edits):
        raise AssertionError(f"{relative_path}: expected one occurrence of each new text, found {counts}")
    for new, old in reversed(edits):
        value = value.replace(new, old, 1)
    return value.encode() if as_bytes else value


def apply_harness_repository_edits(relative_path, text):
    """Return text (str, the file at BASELINE) with the t_a8884510 edits applied."""
    for new, old in HARNESS_REPOSITORY_EDITS.get(relative_path, ()):
        if text.count(old) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {old[:60]!r}")
        text = text.replace(old, new, 1)
    return text
