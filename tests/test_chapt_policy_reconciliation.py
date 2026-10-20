#!/usr/bin/env python3
"""Offline tracked-byte preservation checks, not agent behavior or live rollout.

Frozen hashes bind the approved paragraph and e3aa92a source without private
controller inputs, installed profiles, Git history, network or model calls.
"""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
SOURCE = ROOT / "policies/profile-skills/chapt-orchestrator" / RELATIVE
BASELINE_SHA256 = "3fa1151192959b77e23921a813994517cb3cad8c655c901e425f0f958fb7674c"
PRE_PORT_SHA256 = "575419e386187a028b7c449bf6da7f298e88dfa3d4250619c06caa8d5a52e330"
RULE_SHA256 = "0b3349307eaaf7bc4de6716198dfdd5e72d3f99862ee335a0fdc4124ad5e1d5e"
UPGRADE_SHA256 = "0e9c5f1f07e50dd3653fc51ffba481427bb237d5805d3213aa209169ac64cd94"
PRE_RETIREMENT_SHA256 = "e60d361a5d41f0c864ce1796d107e38a995df76e9449037cb01ed44714b846d7"
PRE_LEGACY_LANE_SHA256 = "b6b80cef78fbcade77043e05de07a0382c0e1e94c705180c89869287f9696892"
PRE_SECOND_WORKER_SHA256 = "ff0a7f380f77ede2e429c497329fea3a4660889a5dc2801e4072cb62bb66a0c2"
PRE_SCRAPER_SHA256 = "c963e090ef2f19929b01a8cd3581f1b6e87501d6371439e27e3e7573469fdf62"
PRE_CARD_CREATION_SHA256 = "f95f1441f0c9c689d36b4756e465c9d088346f72d589b0ecfbf7281773020138"
MERGED_SHA256 = "5e3869b816966691f585d9ed6e3eb099e28bf4e7e8ff24d00636fa97a785095f"
# The card-creation change (t_b6d0e590, no version bump) replaces exactly Card
# Setup steps 1 and 4; reversing both recovers the reviewed scraper-scope bytes.
# tests/test_orchestrator_card_creation_policy.py checks the new wording.
CARD_CREATION_EDITS = (
    (b"1. Create it with the kanban_create tool: `kanban_create(..., board: cha-pt, initial_status: blocked)`. "
     b"The card is created blocked, so it cannot be dispatched before setup is complete, and its notification "
     b"subscription exists from creation. Create cards only with the kanban_create tool, never with "
     b"`hermes kanban --board cha-pt create`. The tool auto-subscribes this session to the card with delivery_mode "
     b"notify+wake, the owner's user ID, and this profile as notifier_profile, so completion, review-request, and "
     b"block events wake this orchestrator and ping the owner. The CLI create command does not subscribe, and a "
     b"manual notify-subscribe without flags defaults to notify with no user ID, which wakes nobody. This caused "
     b"the 2026-10-20 stalls of the JSS and Jobcron orchestrators.\n",
     b"1. Create it with `hermes kanban --board cha-pt create ... --initial-status blocked` before any notification "
     b"subscription exists.\n"),
    (b"4. Confirm the kanban_create result reports subscribed: true. Only if it does not, repair the subscription "
     b"with: hermes kanban --board cha-pt notify-subscribe <id> --platform telegram --chat-id <owner chat> "
     b"--user-id <owner user> --chat-type dm --notifier-profile chapt-orchestrator --delivery-mode notify+wake. "
     b"Re-running notify-subscribe updates an existing row, so this command also upgrades a wrongly subscribed card.\n",
     b"4. Subscribe the callback with `hermes kanban --board cha-pt notify-subscribe`.\n"),
)
# The scraper-repository scope (t_b04aef1d, no version bump) changes exactly
# these bytes and adds one paragraph; reversing both recovers the reviewed
# 0.6.7-chapt.4 bytes. tests/test_chapt_scraper_scope.py checks the new wording.
SCRAPER_EDITS = (
    (b"Repository allowlist (exactly three): `/Users/chanbla11mit/projects/cha-pt`, "
     b"`/Users/chanbla11mit/projects/cha-pt-frontend`, and `/Users/chanbla11mit/projects/cha-webpt-website-sync`; "
     b"primary board root `/Users/chanbla11mit/projects/cha-pt`; frontend Hermes project `cha-pt-frontend`; "
     b"scraper Hermes project `cha-webpt-website-sync`;",
     b"Repository allowlist: `/Users/chanbla11mit/projects/cha-pt` and `/Users/chanbla11mit/projects/cha-pt-frontend`; "
     b"primary board root `/Users/chanbla11mit/projects/cha-pt`; frontend Hermes project `cha-pt-frontend`;"),
    (b"### Cha PT multi-repository routing\n", b"### Cha PT dual-repository routing\n"),
    (b"in any of the three allowlisted Cha PT repositories,", b"in either allowlisted Cha PT repository,"),
    (b"(`/Users/chanbla11mit/projects/cha-pt`, a `cha-pt-frontend` project worktree, or a "
     b"`cha-webpt-website-sync` project worktree)",
     b"(`/Users/chanbla11mit/projects/cha-pt` or a `cha-pt-frontend` project worktree)"),
)
SCRAPER_PARAGRAPH_START = b"Scraper cards for `/Users/chanbla11mit/projects/cha-webpt-website-sync`"
# The 0.6.7-chapt.4 second-worker addition (t_b12ba0d9) changes exactly these
# bytes; reversing them recovers the reviewed 0.6.7-chapt.3 bytes.
SECOND_WORKER_EDITS = (
    (b"version: 0.6.7-chapt.4\n", b"version: 0.6.7-chapt.3\n"),
    (b"implementation workers `jobcron-worker` (`gpt-6.1-sol`) and `jobcron-worker-2` (`claude-opus-5-5`);",
     b"implementation worker `jobcron-worker` (`gpt-6.1-sol`);"),
    (b"implementation workers `chapt-worker` (`gpt-6.1-sol`) and `chapt-worker-2` (`claude-opus-5-5`);",
     b"implementation worker `chapt-worker` (`gpt-6.1-sol`);"),
    (b"A project orchestrator may assign only its matching workers and reviewer.",
     b"A project orchestrator may assign only its matching worker and reviewer."),
    (b"Each project has two implementation workers. Assign implementation only to them, never to a "
     b"foreign-project or legacy worker. Spread independent ready cards across the two workers; keep cards "
     b"that touch the same files serialized or dependency-linked. Review revision stays on the same assignee.",
     b"Each project has one implementation worker. Assign implementation only to it, never to a "
     b"foreign-project or legacy worker. Review revision stays on the same assignee."),
    (b"contains each project's workers and reviewer plus", b"contains each project's worker and reviewer plus"),
)
# The 0.6.7-chapt.3 legacy-lane note (t_56d81c3a) replaces exactly these
# bytes; reversing them recovers the reviewed 0.6.7-chapt.2 bytes.
LEGACY_LANE_EDITS = (
    (b"version: 0.6.7-chapt.3\n", b"version: 0.6.7-chapt.2\n"),
    (b"Legacy/default-board lanes are retired and inert: the GLM Flash and GLM-full workers were archived on "
     b"2026-10-18 and the GPT Luna, Terra, Sol and Astra workers and `reviewer-sol` were retired the same day. "
     b"Never assign, escalate, or route review to them. Archived copies are in `~/.hermes/profile-exports/`; "
     b"restore one only per `procedures/switching-hermes-models.md`.\n\n"
     b"- `advisor`: read/analyze advisor; not a Kanban implementation lane.\n",
     b"Legacy/default-board control profiles remain installed for rollback and existing history:\n\n"
     b"- `default`: legacy `gpt-5.6-sol` orchestrator and user-facing profile.\n"
     b"- `reviewer-sol`: legacy `gpt-5.6-sol` independent reviewer.\n"
     b"- `advisor`: read/analyze advisor; not a Kanban implementation lane.\n\n"
     b"Legacy/default-board implementation profiles, in escalation order:\n\n"
     b"1. `worker-flash-1`, `worker-flash-2`, `worker-flash-3`: Z.AI `glm-5.3-flash`.\n"
     b"2. `worker-luna-1`, `worker-luna-2`: OpenAI Codex `gpt-5.6-luna`.\n"
     b"3. `worker-terra-1`: OpenAI Codex `gpt-5.6-terra`.\n"
     b"4. `worker-glm-full`: Z.AI `glm-5.3`.\n"
     b"5. `worker-sol`: OpenAI Codex `gpt-5.6-sol`.\n"
     b"6. `worker-astra`: OpenAI Codex `gpt-6-astra`.\n\n"
     b"Keep `worker-terra-2` installed but dormant as a rollback/spare lane. It is outside the active legacy "
     b"roster unless the human changes the policy.\n"),
)
# The 0.6.7-chapt.2 GLM worker retirement (t_f953035b) changes exactly these
# lines; reversing them recovers the reviewed 0.6.7-chapt.1 bytes.
RETIREMENT_EDITS = (
    (b"version: 0.6.7-chapt.2\n", b"version: 0.6.7-chapt.1\n"),
    (b"implementation worker `jobcron-worker` (`gpt-6.1-sol`);",
     b"implementation pool `jobcron-worker` (`gpt-6.1-sol`), `jobcron-worker-glm-1` and `jobcron-worker-glm-2` (both `glm-5.3`);"),
    (b"implementation worker `chapt-worker` (`gpt-6.1-sol`);",
     b"implementation pool `chapt-worker` (`gpt-6.1-sol`), `chapt-worker-glm-1` and `chapt-worker-glm-2` (both `glm-5.3`);"),
    (b"A project orchestrator may assign only its matching worker and reviewer.",
     b"A project orchestrator may assign only its matching worker pool and reviewer."),
    (b"Each project has one implementation worker. Assign implementation only to it, never to a foreign-project "
     b"or legacy worker. Review revision stays on the same assignee.",
     b"Each project has one Sol worker and two GLM Full workers. Use Sol for routine bounded implementation; "
     b"prefer GLM Full for large-context, repo-wide, long-horizon, multimodal, visual, or broadly specified work, "
     b"and use either idle GLM worker for independent parallel slices. Capacity alone may select another matching "
     b"project worker, but never a foreign-project or legacy worker. Review revision stays on the same assignee "
     b"unless the reviewer identifies a concrete capability boundary; then the orchestrator may create a "
     b"continuation card for another worker in the same project pool with explicit lineage and preserved evidence."),
    (b"return `gpt-6.1-sol` for orchestrator/worker and `gpt-6-astra` for reviewer.",
     b"return `gpt-6.1-sol` for orchestrator/primary worker, `glm-5.3` for both GLM Full workers, and `gpt-6-astra` for reviewer."),
    (b"contains each project's worker and reviewer plus", b"contains each project's three-worker pool and reviewer plus"),
)
# The 0.6.7-chapt.1 port adds exactly these three sections before their
# successor headings; dropping them inverts the port byte-exactly.
PORTED_SECTIONS = (
    (b"## Card Setup\n", b"## Task Construction\n"),
    (b"## Autonomy\n", b"## Worker Contract\n"),
    (b"## Completion Gate\n", b"## Verification\n"),
)
HEADING = b"## Operator Effort and Evidence Lifecycle\n\n"
RULE_START = b"Distinguish worker-stop conditions from controller-disposition points and actual human authorization boundaries."


def digest(content):
    return hashlib.sha256(content).hexdigest()


class ChaptPolicyReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_bytes()
        self.skill = json.loads((ROOT / "snapshots/sanitized-current-state.yaml").read_bytes())["skill"]

    def retained_rule(self):
        self.assertEqual(self.source.count(RULE_START), 1)
        self.assertEqual(self.source.count(HEADING), 1)
        following = self.source.split(HEADING, 1)[1]
        self.assertTrue(following.startswith(RULE_START))
        # Preserve the installed paragraph's terminating LF and separating blank
        # line. Its frozen hash detects any wording/whitespace substitution.
        paragraph, rest = following.split(b"\n\n", 1)
        self.assertTrue(rest.startswith(b"Do not add unrelated collaborator-role or whole-governance audits"))
        rule = paragraph + b"\n"
        self.assertEqual(digest(rule), RULE_SHA256)
        self.assertEqual(self.source.count(rule), 1)
        return rule

    def test_exact_rule_once_at_existing_semantic_location(self):
        self.retained_rule()

    def test_entire_reviewed_source_is_preserved(self):
        self.assertEqual(self.source.count(b"version: 0.6.7-chapt.4\n"), 1)
        # Invert the 0.6.7-chapt.4 second worker, the 0.6.7-chapt.3 legacy-lane
        # note, then the 0.6.7-chapt.2 GLM worker retirement.
        original = self.source
        # Invert the card-creation change first: restore Card Setup steps 1 and 4.
        for new, old in CARD_CREATION_EDITS:
            self.assertEqual(original.count(new), 1, new)
            original = original.replace(new, old, 1)
        self.assertEqual(digest(original), PRE_CARD_CREATION_SHA256)
        # Then invert the scraper-repository scope: drop its one paragraph.
        self.assertEqual(original.count(SCRAPER_PARAGRAPH_START), 1)
        prefix, rest = original.split(SCRAPER_PARAGRAPH_START, 1)
        self.assertTrue(prefix.endswith(b"\n\n"))
        original = prefix + rest.split(b"\n\n", 1)[1]
        for new, old in SCRAPER_EDITS:
            self.assertEqual(original.count(new), 1, new)
            original = original.replace(new, old, 1)
        self.assertEqual(digest(original), PRE_SCRAPER_SHA256)
        for new, old in SECOND_WORKER_EDITS:
            self.assertEqual(original.count(new), 1, new)
            original = original.replace(new, old, 1)
        self.assertEqual(digest(original), PRE_SECOND_WORKER_SHA256)
        for new, old in LEGACY_LANE_EDITS:
            self.assertEqual(original.count(new), 1, new)
            original = original.replace(new, old, 1)
        self.assertEqual(digest(original), PRE_LEGACY_LANE_SHA256)
        for new, old in RETIREMENT_EDITS:
            self.assertEqual(original.count(new), 1, new)
            original = original.replace(new, old, 1)
        self.assertEqual(digest(original), PRE_RETIREMENT_SHA256)
        # Invert the 0.6.7-chapt.1 port: remove each added section exactly,
        # then restore the pre-port version line. Frozen full-source identity,
        # not a keyword-only preservation claim.
        for start, successor in PORTED_SECTIONS:
            self.assertEqual(original.count(start), 1, start)
            prefix, rest = original.split(start, 1)
            added, tail = rest.split(successor, 1)
            self.assertTrue(added.startswith(b"\nSet up a card without a setup-only hold")
                            or added.startswith(b"\nBookkeeping never gates")
                            or added.startswith(b"\nBefore reporting a cha-pt card complete"), added[:60])
            original = prefix + successor + tail
        original = original.replace(b"version: 0.6.7-chapt.1\n", b"version: 0.6.5-chapt.4\n", 1)
        self.assertEqual(digest(original), PRE_PORT_SHA256)
        # The pre-port reviewed state still contains the retained live-only rule;
        # removing it recovers the pre-rule-merge baseline, as before this port.
        rule = self.retained_rule()
        original = original.replace(rule + b"\n", b"", 1).replace(
            b"version: 0.6.5-chapt.4\n", b"version: 0.6.5-chapt.3\n", 1)
        self.assertEqual(digest(original), BASELINE_SHA256)
        self.assertEqual(digest(self.source), MERGED_SHA256)

    def test_upgrade_selection_is_byte_unchanged(self):
        section = self.source.split(b"## Routine upgrade selection", 1)[1].split(b"\n## ", 1)[0]
        self.assertEqual(digest(section), UPGRADE_SHA256)
        self.assertIn(b"independent review of the exact saved plan before apply", section)
        self.assertIn(b"separately from owner authorization", section)
        self.assertIn(b"not an extra gate for unchanged-platform app-only updates", section)

    def test_owner_caps_stop_and_authority_are_retained(self):
        rule = self.retained_rule()
        for clause in (
            b"preserve explicit owner caps and activated hard campaign budgets",
            b"Preserve counters, failed evidence and acceptance pins",
            b"never unlimited retries or a history reset",
            b"prohibited effect, unsafe/unowned state, capability limit or exhausted authorized recovery path",
            b"An explicit user stop always controls until a later resumption.",
        ):
            self.assertIn(clause, rule)
        for clause in (
            b"max_approaches: 3", b"max_attempts_per_approach: 3",
            b"max_infrastructure_retries_per_attempt: 1",
            b"Exhausting three approaches always human-blocks",
            b"credentials/MFA", b"policy/legal/security decisions still human-block immediately",
            b"It never covers pushes, PR creation, deployments, production mutations",
            b"When the user says stop, terminate every owned background worker",
            b"Never push, open a PR, deploy, mutate production, or bypass review.",
        ):
            self.assertIn(clause, self.source)

    def test_single_desired_override_pin_and_additive_provenance(self):
        overrides = self.skill["profile_local_skill_overrides"]["chapt-orchestrator"]
        # The declaration names the tracked source; its bytes are the merged result.
        self.assertEqual(overrides, {RELATIVE: "tracked-source"})
        self.assertEqual(digest(self.source), MERGED_SHA256)
        provenance = self.skill["source_pin_provenance"]
        self.assertEqual(provenance["baseline"], "84d91a7ba698d38bb31c5b80e04dea0dd002d15f")
        self.assertEqual(provenance["upgrade_proportionality"]["baseline"], "fdc59293262e15c0376cfaa9f25244e7c317fc58")
        self.assertEqual(provenance["chapt_policy_reconciliation"], {
            "baseline": "e3aa92a20227c780fde4c09d3b3a1402a7115db9",
            "protected_reference": "refs/harness/baselines/t_acb614c0",
            "installed_input_sha256": "e1e5d81f39353eabc49850354d4d76964587cd8b884de2276751b89018edb4f1",
            "retained_rule_sha256": RULE_SHA256,
            "status": "repository-only preservation merge and desired-source pin, not observed deployment; live rollout unperformed and live verification pending",
        })


if __name__ == "__main__":
    unittest.main(verbosity=2)
