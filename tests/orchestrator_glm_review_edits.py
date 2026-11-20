#!/usr/bin/env python3
"""Reversal of the edits of card t_35874d04 in the five project orchestrator skill sources.

Specification: docs/specs/261114-claude-worker-compression-hard-route-and-glm-reviewer.md
(Part 6 step 6, last sentence) and docs/decisions/261114-glm-reviewer-pass-to-opus-reviewer.md
(section 7, and items 5 and 11 of "What the plugin cards must implement"). Card t_35874d04
added one paragraph to the review section of each project orchestrator skill source ("## Review
and Integration" in the harness, jss and anki sources; "## Review Contract" in the chapt and
jobcron sources) and raised the version line by one step. The paragraph states: on a card that a
GLM worker of the board implements, the first review run or runs can be made by the board's GLM
reviewer `<prefix>-reviewer-glm`, which is not an assignee or reviewer mismatch, and the card's
`Reviewer EXACT` line still names `<prefix>-reviewer`; a change request from the GLM reviewer is
routine same-card rework; a `blocked` notification whose reason starts with `jev-glm-review-pass`
needs no action and is not an owner question; a card that is still `blocked` with that reason at
the orchestrator's next check is passed by hand with two `hermes kanban` commands; the GLM
reviewer cannot approve a card.

ORCHESTRATOR_GLM_REVIEW_EDITS lists the exact (new text, old text) pairs of each file, in the
order in which the card applied them. reverse_orchestrator_glm_review_edits() reverses them byte
for byte. hard_route_policy_edits.reverse_hard_route_policy_edits calls it first, so every test
that recovers the bytes of an earlier commit reverses this card's edits before the edits of the
earlier cards. The later edits of card t_cf518fd0 (test_jev_easy_medium_worker_split) are
reversed first. This module imports only test_jev_easy_medium_worker_split, which imports no
other test module at module level, so any test module can import it without a circular import.
"""

from test_jev_easy_medium_worker_split import reverse_easy_medium_split_edits
from test_ponytail_policy_text import reverse_ponytail_policy_text_edits
from test_reasoning_effort_skill_text import reverse_reasoning_effort_skill_text_edits

BASELINE = "e18997b7e2d27c69ed1e7af2ce4fc6e73ba88875"
PASS_REASON = "jev-glm-review-pass"
HOLD_SCRIPT = "/Users/chanbla11mit/hermes-local-harness/scripts/jev-peak-hold"
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
PREFIXES = ("harness", "jss", "anki", "chapt", "jobcron")
# Profile prefix -> Kanban board name.
BOARDS = {"harness": "harness", "jss": "jss-genr", "anki": "anki", "chapt": "cha-pt", "jobcron": "jobcron"}
# Profile prefix -> (version at BASELINE, version after this card).
VERSIONS = {
    "harness": ("0.6.7-harness.12", "0.6.7-harness.13"),
    "jss": ("0.6.7-jss.16", "0.6.7-jss.17"),
    "anki": ("0.6.10-anki.10", "0.6.10-anki.11"),
    "chapt": ("0.6.7-chapt.14", "0.6.7-chapt.15"),
    "jobcron": ("0.6.9-jobcron.15", "0.6.9-jobcron.16"),
}
# Profile prefix -> (end of the paragraph after which the card added its paragraph, start of the
# text that follows). Each joined text occurs exactly once in its file at BASELINE.
ANCHORS = {
    "harness": ("Do not replace same-card review with a summary from another session.", "After approval"),
    "jss": ("Do not replace same-card review with a summary from another session.", "After approval"),
    "anki": ("Do not replace same-card review with a summary from another session.", "After approval"),
    "chapt": ("whether continuation or a clean restart is safer.", "## Integration"),
    "jobcron": ("whether continuation or a clean restart is safer.", "## Integration"),
}


def skill(prefix):
    return f"policies/profile-skills/{prefix}-orchestrator/{RELATIVE}"


def assign_command(prefix):
    """Item 1.d of the card: the first hand command."""
    return f"hermes kanban --board {BOARDS[prefix]} assign <task id> {prefix}-reviewer"


def unblock_command(prefix):
    """Item 1.d of the card: the second hand command."""
    return f"hermes kanban --board {BOARDS[prefix]} unblock <task id>"


def approval_sentence(prefix):
    """Item 1.e of the card."""
    return (f"The GLM reviewer cannot approve a card: only `kanban_complete` by `{prefix}-reviewer` is the approval, "
            "and local integration starts only after it.")


def added_paragraph(prefix):
    """The paragraph that the card added (items 1.a to 1.e), without the surrounding blank lines."""
    glm_workers = f"`{prefix}-worker-glm-1`, `{prefix}-worker-glm-2` or `{prefix}-worker-glm-3`"
    glm_reviewer = f"`{prefix}-reviewer-glm`"
    reviewer = f"`{prefix}-reviewer`"
    return " ".join((
        # Item 1.a.
        f"On a card that {glm_workers} implements, the first review run or runs can be made by the GLM reviewer "
        f"of board `{BOARDS[prefix]}`, {glm_reviewer}.",
        "Such a run is not an assignee or reviewer mismatch.",
        f"The card's `Reviewer EXACT` line still names the Opus reviewer {reviewer}, and that is correct.",
        # Item 1.b.
        f"A change request from {glm_reviewer} is routine same-card rework, in the same way as a change request "
        f"from {reviewer}.",
        # Item 1.c.
        f"A `blocked` notification whose reason starts with `{PASS_REASON}` means that the GLM review had no "
        "findings.",
        f"It needs no action and is not an owner question: the script `{HOLD_SCRIPT}` assigns the card to "
        f"{reviewer} and unblocks it within about a minute.",
        # Item 1.d.
        "If the card is still `blocked` with that reason at the orchestrator's next check, the orchestrator passes "
        f"it by hand with `{assign_command(prefix)}` and then `{unblock_command(prefix)}`.",
        # Item 1.e.
        approval_sentence(prefix),
    ))


def version_edit(prefix):
    old, new = VERSIONS[prefix]
    return (f"version: {new}\n", f"version: {old}\n")


def paragraph_edit(prefix):
    end, following = ANCHORS[prefix]
    return (f"{end}\n\n{added_paragraph(prefix)}\n\n{following}", f"{end}\n\n{following}")


# File -> ((new text, old text), ...), in the order in which the card applied them. Each new
# text occurs exactly once in the file after this card and not at all at BASELINE.
ORCHESTRATOR_GLM_REVIEW_EDITS = {skill(prefix): (version_edit(prefix), paragraph_edit(prefix)) for prefix in PREFIXES}

# SHA-256 of each file at BASELINE (git show BASELINE:<path>).
BASELINE_SHA256 = {
    skill("harness"): "a02ff532122f52a20727edaab6ec0d6f84dcdd63e3c7fa658823bd9e140260d8",
    skill("jss"): "395556d00440f55e8dabcad2aaebdc4b27bef198ed8d6828c69f303a8c6f2ddd",
    skill("anki"): "acdd9dbf97460e6816bb2a5692beb9716af89dc7954bce0cda3a0e7b9e20dda3",
    skill("chapt"): "fa7da850d19611c1dfdfd4dc91dd6766834c2b01d6f8a411db2b8952d444db24",
    skill("jobcron"): "660417026c9190aef505bd3b3d09be40c3634f1f08d72269b95548ea2cb8c499",
}


def reverse_orchestrator_glm_review_edits(relative_path, text):
    """Return text with the t_35874d04 edits reversed; text may be str or bytes. A path that
    the card did not change, and a text that contains none of the new texts, is returned as
    the same object, so a caller may apply it to a text that another caller already reversed.
    A text that contains some of the new texts but not each of them exactly once raises
    AssertionError. The later edits of card t_cf518fd0 are reversed first."""
    text = reverse_reasoning_effort_skill_text_edits(relative_path, text)
    text = reverse_ponytail_policy_text_edits(relative_path, text)
    text = reverse_easy_medium_split_edits(relative_path, text)
    edits = ORCHESTRATOR_GLM_REVIEW_EDITS.get(relative_path)
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


def apply_orchestrator_glm_review_edits(relative_path, text):
    """Return text (str, the file at BASELINE) with the t_35874d04 edits applied."""
    for new, old in ORCHESTRATOR_GLM_REVIEW_EDITS.get(relative_path, ()):
        if text.count(old) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {old[:60]!r}")
        text = text.replace(old, new, 1)
    return text
