#!/usr/bin/env python3
"""Reversal of the edits of card t_be416943 in the five Opus reviewer SOUL sources.

Specification: docs/specs/261114-claude-worker-compression-hard-route-and-glm-reviewer.md
(Part 6 step 6, last sentence) and docs/decisions/261114-glm-reviewer-pass-to-opus-reviewer.md
(section 7, and item 11 of "What the plugin cards must implement"). Card t_be416943 added
sentences to the paragraph of each Opus reviewer SOUL source that verifies the implementing
profile (for `jobcron-reviewer`, the first paragraph, which states the accepted implementers):
the implementing profile is the implementer of the card's latest `review_requested` event; an
earlier run of the board's GLM reviewer `<prefix>-reviewer-glm` on the card (a run with outcome
`blocked` whose block reason starts with `jev-glm-review-pass`, and `changes_requested` events
whose `reviewer` is the GLM reviewer) is not a mismatch; the GLM reviewer cannot approve a card;
the other boundary checks are unchanged.

OPUS_REVIEWER_GLM_REVIEW_EDITS lists the exact (new text, old text) pair of each file.
reverse_opus_reviewer_glm_review_edits() reverses it byte for byte.
hard_route_policy_edits.reverse_hard_route_policy_edits calls it first, so every test that
recovers the bytes of an earlier commit reverses this card's edits before the edits of the
earlier cards. This module imports no other test module, so any test module can import it
without a circular import.
"""

BASELINE = "125624fc72a900aa50496c70d144f5554aacff83"
PASS_REASON = "jev-glm-review-pass"
PREFIXES = ("harness", "chapt", "jss", "anki", "jobcron")


def soul(profile):
    return f"policies/profile-souls/{profile}/SOUL.md"


def implementing_profile_sentence(prefix):
    """Item 1.a of the card."""
    if prefix == "jobcron":
        return ("For an implementation review, the implementing profile is the profile that the card's latest "
                "`review_requested` event names as implementer; it must be one of the five Jobcron implementation "
                "profiles that this paragraph names.")
    return ("The implementing profile is the profile that the card's latest `review_requested` event names as "
            "implementer; it must be one of the five implementation profiles of this board that the first "
            "paragraph names.")


def glm_review_run_sentences(prefix):
    """Item 1.b of the card."""
    glm_reviewer = f"`{prefix}-reviewer-glm`"
    return (f"An earlier run of this board's GLM reviewer {glm_reviewer} on the card is not a mismatch. This includes "
            f"a run with outcome `blocked` whose block reason starts with `{PASS_REASON}` (the GLM review had no "
            "findings, and the script `jev-peak-hold` of the `jev` plugin then assigned the card to this reviewer "
            f"and unblocked it), and `changes_requested` events whose `reviewer` is {glm_reviewer}.")


# Item 1.c of the card.
APPROVAL_SENTENCE = ("The GLM reviewer cannot approve a card: only this reviewer approves a card, with "
                     "`kanban_complete`, and a GLM review without findings does not change the review standard of "
                     "this file.")
# Item 1.d of the card.
UNCHANGED_CHECKS_SENTENCE = ("The other boundary checks of this file are unchanged, and a card whose implementer in "
                             "the latest `review_requested` event is a reviewer profile is still a mismatch.")


def added_text(prefix):
    """The sentences that the card added, with the leading space that joins them to the paragraph."""
    return " " + " ".join((implementing_profile_sentence(prefix), glm_review_run_sentences(prefix),
                           APPROVAL_SENTENCE, UNCHANGED_CHECKS_SENTENCE))


# Profile prefix -> the last sentence of the paragraph at BASELINE, after which the card added
# its sentences. Each occurs exactly once in its file and is followed by a blank line.
PARAGRAPH_END = {
    "harness": "Reject and block any boundary mismatch.\n\nReview the governing specification",
    "chapt": "Existing cards retain their original scope.\n\n",
    "jss": "Reject and block any boundary mismatch.\n\nNever edit implementation code or the reviewed drafts.",
    "anki": "Reject and block any boundary mismatch.\n\nReview the governing source",
    "jobcron": "Reject and block any project, workspace, or authorship boundary mismatch.\n\n",
}


def _edit(prefix):
    end = PARAGRAPH_END[prefix]
    head, separator, tail = end.partition("\n\n")
    return (head + added_text(prefix) + separator + tail, end)


# File -> ((new text, old text),). Each new text occurs exactly once in the file after this
# card and not at all at BASELINE.
OPUS_REVIEWER_GLM_REVIEW_EDITS = {soul(f"{prefix}-reviewer"): (_edit(prefix),) for prefix in PREFIXES}

# SHA-256 of each file at BASELINE (git show BASELINE:<path>).
BASELINE_SHA256 = {
    soul("harness-reviewer"): "84f61ec8568f5a5c9d63900cf23f1a4a3d5cf75e15983909a8777ff503f26c7d",
    soul("chapt-reviewer"): "85f4b5413615fbb61ccc0af1f54c16336af0b66c3601d42e620290d54cd90df8",
    soul("jss-reviewer"): "eedf5506b802d3d3af1053063a9d1e37f6a82e9f5ac2fdc32b0efcd3afbcb9f4",
    soul("anki-reviewer"): "3ed1997e5a6de048cb96a503a081af7442c8309ccd081ecc20ef05ec96534a8a",
    soul("jobcron-reviewer"): "1198892a743aad46a35054a95df6d18ba88f387f7840215c76ef67f622fbd824",
}


def reverse_opus_reviewer_glm_review_edits(relative_path, text):
    """Return text with the t_be416943 edits reversed; text may be str or bytes. A path that
    the card did not change, and a text that contains none of the new texts, is returned as
    the same object, so a caller may apply it to a text that another caller already reversed.
    A text that contains a new text more than once raises AssertionError."""
    edits = OPUS_REVIEWER_GLM_REVIEW_EDITS.get(relative_path)
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


def apply_opus_reviewer_glm_review_edits(relative_path, text):
    """Return text (str, the file at BASELINE) with the t_be416943 edits applied."""
    for new, old in OPUS_REVIEWER_GLM_REVIEW_EDITS.get(relative_path, ()):
        if text.count(old) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {old[:60]!r}")
        text = text.replace(old, new, 1)
    return text
