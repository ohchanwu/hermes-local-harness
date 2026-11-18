#!/usr/bin/env python3
"""Reversal of the orchestrator model edits of card t_d3bb0983 (2026-11-15).

On 2026-11-15 the owner set claude-opus-5-5 as the main model of the five project
orchestrators. Card t_f03857d4 changed roster.yaml and scripts/verify-state. Card
t_d3bb0983 changed three orchestrator skill sources: each orchestrator entry of the
Fixed Roster names `claude-opus-5-5` instead of `claude-fable-5-2`, the verification
sentence names `claude-opus-5-5` for orchestrator, worker and reviewer, and the version
line is raised by one step.

OPUS_5_5_ORCHESTRATOR_EDITS lists the exact (new text, old text) pairs of each file, in the
order in which the card applied them. reverse_opus_5_5_orchestrator_edits() reverses them
byte for byte. hard_route_policy_edits.reverse_hard_route_policy_edits and
test_fable_5_2_declared_model.reverse_role_model_edits call it first, so every test that
recovers the bytes of an earlier commit reverses this card's edits before the edits of the
earlier cards.

The new version line of a file occurs only after this card, while the text
"`<prefix>-orchestrator` (`claude-opus-5-5`);" also occurs before card t_0faca45d. For that
reason the function reverses the edits only when the new version line is present, and returns
any other text as the same object, so a caller may apply it to a text that another caller
already reversed. This module imports no other test module, so any test module can import it
without a circular import.
"""
from test_ponytail_policy_text import reverse_ponytail_policy_text_edits

BASELINE = "2d34fcdb1ff7a146f2d3b61e42be3bd95ed24248"
OLD_MODEL, NEW_MODEL = "claude-fable-5-2", "claude-opus-5-5"
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
SHARED = "skills/multi-agent-coding-orchestrator/SKILL.md"
JOBCRON = f"policies/profile-skills/jobcron-orchestrator/{RELATIVE}"
CHAPT = f"policies/profile-skills/chapt-orchestrator/{RELATIVE}"
# File -> (version at BASELINE, version after this card).
VERSIONS = {
    SHARED: ("0.6.14", "0.6.15"),
    JOBCRON: ("0.6.9-jobcron.14", "0.6.9-jobcron.15"),
    CHAPT: ("0.6.7-chapt.13", "0.6.7-chapt.14"),
}
# File -> board prefixes of the Fixed Roster entries that the file names.
PREFIXES = {
    SHARED: ("jobcron", "chapt", "harness"),
    JOBCRON: ("jobcron", "chapt"),
    CHAPT: ("jobcron", "chapt"),
}
VERIFICATION = (
    f"return `{NEW_MODEL}` for orchestrator, worker and reviewer.",
    f"return `{OLD_MODEL}` for orchestrator, `{NEW_MODEL}` for worker and `{NEW_MODEL}` for reviewer.",
)


def version_edit(relative_path):
    old, new = VERSIONS[relative_path]
    return (f"version: {new}\n", f"version: {old}\n")


def orchestrator_edit(prefix):
    return (f"`{prefix}-orchestrator` (`{NEW_MODEL}`);", f"`{prefix}-orchestrator` (`{OLD_MODEL}`);")


# File -> ((new text, old text), ...), in the order in which the card applied them. Each new
# text occurs exactly once in the file after this card.
OPUS_5_5_ORCHESTRATOR_EDITS = {
    path: (version_edit(path), *(orchestrator_edit(prefix) for prefix in PREFIXES[path]), VERIFICATION)
    for path in VERSIONS
}
# SHA-256 of each file at BASELINE (git show BASELINE:<path>).
BASELINE_SHA256 = {
    SHARED: "00263911436aa5c1e7d596234c18e19ac6476b192f2ffc52581b158cd9eec9c3",
    JOBCRON: "5e8cc959f1b153be28df728bb6f3629aea6ca48462abc4d75be200cab4be3e46",
    CHAPT: "6edcd7a7bb736fec6f5ba24bac7e17631a0d7ff844e1354be0b98ab66e25c332",
}


def reverse_opus_5_5_orchestrator_edits(relative_path, text):
    """Return text with the t_d3bb0983 edits reversed; text may be str or bytes. A path that
    the card did not change, and a text without the new version line, is returned as the same
    object. A text with the new version line but not each other new text exactly once raises
    AssertionError."""
    text = reverse_ponytail_policy_text_edits(relative_path, text)
    edits = OPUS_5_5_ORCHESTRATOR_EDITS.get(relative_path)
    if not edits:
        return text
    as_bytes = isinstance(text, bytes)
    value = text.decode() if as_bytes else text
    if edits[0][0] not in value:
        return text
    counts = [value.count(new) for new, _old in edits]
    if counts != [1] * len(edits):
        raise AssertionError(f"{relative_path}: expected one occurrence of each new text, found {counts}")
    for new, old in reversed(edits):
        value = value.replace(new, old, 1)
    return value.encode() if as_bytes else value
