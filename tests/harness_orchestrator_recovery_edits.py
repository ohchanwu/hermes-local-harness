#!/usr/bin/env python3
"""Reversal of the edits of card t_40028345 in the harness-orchestrator skill source.

Card t_40028345 raised the version of the source from 0.6.7-harness.15 to 0.6.7-harness.16 and added
three texts: a list item in `## Operational Discipline` (recovery of a review card that the respawn
guard holds with the reason `blocker_auth`), a paragraph in `## Card Setup` (no planned hand-back
block of a card) and a paragraph in `## Role Separation` (the steps on other boards that the owner
authorized).

HARNESS_RECOVERY_EDITS lists the exact (new text, old text) pairs, in the order in which the card
applied them. reverse_harness_recovery_edits() reverses them byte for byte.
test_glm_claude_fallback.reverse_glm_claude_fallback_edits calls it first, so every test that
recovers the bytes of an earlier commit reverses this card's edits before the edits of the earlier
cards. This module imports only the standard library, so any test module can import it without a
circular import.
"""
from test_ponytail_policy_text import reverse_ponytail_policy_text_edits

SKILL = ("policies/profile-skills/harness-orchestrator/"
         "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md")
KANBAN_DB = "/Users/chanbla11mit/.hermes/hermes-agent/hermes_cli/kanban_db.py"
OWNER_QUOTATION = ("You (harness-orchestrator) run the card reads, moves and comments on the five boards "
                   "from your session. The worker does the renames, policy texts, .env lines and copies. "
                   "No Hermes limit is removed.")

VERSION_EDIT = ("version: 0.6.7-harness.16\n", "version: 0.6.7-harness.15\n")

ROLE_SEPARATION_PARAGRAPH = (
    "A worker that the dispatcher starts can read and change cards of its own board only. When a card "
    "that the owner authorized has steps that read or change cards of other boards, harness-orchestrator "
    "runs only those authorized steps from its own session and records each in a comment on the card, and "
    "the worker does every other step. Owner decision, Telegram direct message to `harness-orchestrator` "
    f"on 2026-11-16 (verbatim): \"{OWNER_QUOTATION}\" This gives no access to another board beyond the "
    "steps that the owner authorized for that card.\n\n")

CARD_SETUP_PARAGRAPH = (
    "Do not plan a stop at which the worker blocks the card to hand it back to harness-orchestrator. "
    "Hermes counts every block of a card, including the kind `needs_input`: `BLOCK_RECURRENCE_LIMIT` is 2 "
    f"(`{KANBAN_DB}`, line 114), and the function `_route_block` (lines 3397 to 3407 of the same file) "
    "moves the card to `triage`, with the event `block_loop_detected`, at the second block of the same "
    "kind after an unblock. When a step must wait for harness-orchestrator, split the work into two cards "
    "and link them.\n\n")

OPERATIONAL_DISCIPLINE_ITEM = (
    "- A `ready` or `review` card that the dispatcher skips with events `respawn_guarded` and reason "
    "`blocker_auth` still stores the failure text of an earlier run, which `kanban_request_review` does "
    "not clear. This is the step of the finding RESPAWN-GUARDED of the board check "
    "(`/Users/chanbla11mit/hermes-local-harness/deployment/orchestrator-board-check/cron-prompt.md`, "
    "line 13), which `harness-orchestrator` does not run. If no run of the card is running, the status is "
    "`review`, and the newest ended run has the outcome `review_requested`, run "
    "`hermes kanban --board harness assign <card id> none`, then "
    "`hermes kanban --board harness assign <card id> <the previous assignee>`, and confirm with "
    "`kanban_show(..., board: harness)` that the assignee is that profile again; a change of assignee "
    "sets `last_failure_error` to NULL and `consecutive_failures` to 0 (function `assign_task`, lines "
    f"1639 to 1644 of `{KANBAN_DB}`). In every other case report the card to the owner and change "
    "nothing.\n")

# (new text, old text) pairs; each new text occurs exactly once in the source after this card.
HARNESS_RECOVERY_EDITS = (
    VERSION_EDIT,
    (ROLE_SEPARATION_PARAGRAPH, ""),
    (CARD_SETUP_PARAGRAPH, ""),
    (OPERATIONAL_DISCIPLINE_ITEM, ""),
)


def reverse_harness_recovery_edits(relative_path, text):
    """Return text with the t_40028345 edits reversed; text may be str or bytes. A path that the card
    did not change, and a text that contains none of the new texts, is returned as the same object, so
    a caller may apply it to a text that another caller already reversed. A text that contains some of
    the new texts but not each of them exactly once raises AssertionError."""
    text = reverse_ponytail_policy_text_edits(relative_path, text)
    if relative_path != SKILL:
        return text
    as_bytes = isinstance(text, bytes)
    value = text.decode() if as_bytes else text
    counts = [value.count(new) for new, _old in HARNESS_RECOVERY_EDITS]
    if not any(counts):
        return text
    if counts != [1] * len(HARNESS_RECOVERY_EDITS):
        raise AssertionError(f"{relative_path}: expected one occurrence of each new text, found {counts}")
    for new, old in reversed(HARNESS_RECOVERY_EDITS):
        value = value.replace(new, old, 1)
    return value.encode() if as_bytes else value
