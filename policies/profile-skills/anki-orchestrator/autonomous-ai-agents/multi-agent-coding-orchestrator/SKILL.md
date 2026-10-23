---
name: multi-agent-coding-orchestrator
description: "Use when orchestrating anki add-on, tooling, and deck change work."
version: 0.6.10-anki.1
author: chanbla11mit, Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [orchestration, kanban, coding, review, worktrees, anki]
    related_skills: [hermes-agent]
---

# anki Orchestrator

Coordinate work for board `anki` only, across exactly two local repositories: the primary repository `/Users/chanbla11mit/projects/anki` (deck tooling, writing standards, deck change sets) and the add-on repository `/Users/chanbla11mit/projects/anki-addons` (Anki add-on code). This is a project-local control-plane policy, not a generic fleet guide. The primary repository's `README.md` and each repository's own instructions govern content and tooling; this skill governs routing.

## Hard Scope

- Pass `board: anki` on every Kanban tool call.
- Pass `--board anki` on every Kanban CLI command.
- Use only `/Users/chanbla11mit/projects/anki`, `/Users/chanbla11mit/projects/anki-addons`, and repository-owned worktrees under `<repository>/.worktrees/<task-id>` of the card's one repository.
- The board default workdir and every fleet profile's `terminal.cwd` stay at `/Users/chanbla11mit/projects/anki`. The add-on repository is reached only through the Hermes project `anki-addons`, which exists only in the `anki-orchestrator` profile.
- Never access or route to another project, board, repository, profile fleet, or worktree. Never access Jobcron, Cha PT, jss-genr, or Harness work. The only harness files this fleet reads are the read-only references this skill names: `/Users/chanbla11mit/hermes-local-harness/scripts/check-forced-skills` and `/Users/chanbla11mit/hermes-local-harness/policies/overgating-review.md`.
- The orchestrator is interactive and non-dispatchable. Launch it with `scripts/run-anki-orchestrator` from the harness repository.
- The implementation workers are `anki-worker` and `anki-worker-2`.
- The sole independent reviewer is `anki-reviewer`.
- Both repositories stay local with no remote. Never add a remote, run `git push` or `gh`, open a PR, or deploy.
- Never sync with AnkiWeb (the owner syncs), never publish to AnkiWeb, and never change other installed add-ons or their configuration (AnkiConnect, Syntax Highlighting NG, FSRS Helper).
- Never edit the safety rules or adapter text of `/Users/chanbla11mit/projects/anki/README.md` outside an owner-scoped card.
- Credentials stay excluded: an AnkiConnect `apiKey`, AnkiWeb login data, and any token are never read, printed, committed, or put on cards.
- Installs or downloads (including the add-on test environment below), credentials, live profile, skill, board, or gateway changes, and other external writes require separate explicit owner authorization.

If any board, repository, add-on project, profile, worktree, baseline, test-contract, or reviewer boundary is absent or inconsistent, stop before file access or mutation.

## Collection Access

The Anki collection is changed only through AnkiConnect (installed add-on ID 2055492159, which accepts requests on http://127.0.0.1:8765 while Anki is running).

- No fleet profile opens the collection files (`*.anki2`, `*.anki21`, `*.anki21b`, `collection.media`) directly, including through a repository script that opens them (for example `scripts/export_swe_notes.py`). Writing them while Anki is open can corrupt the collection or conflict with AnkiWeb sync.
- Workers and the reviewer may read the collection only through these AnkiConnect actions: `version`, `requestPermission`, `deckNames`, `deckNamesAndIds`, `modelNames`, `modelFieldNames`, `findNotes`, `notesInfo`, `findCards`, `cardsInfo`, `getTags`. Any other action is forbidden to them, including `sync`, `exportPackage`, `importPackage`, and every action that changes notes, cards, decks, tags, note types, media, or configuration.
- Only `anki-orchestrator` writes to the collection, only through AnkiConnect, only after a backup, and only for the exact change set the owner approves (see Applying a Change Set).
- There is no privacy rule for note content (owner decision, 2026-10-23). Note text, deck names, change sets, exports, and reports may appear in tracked files, commits, card bodies, comments, handoffs, memory, and Telegram replies. The credential exclusion in Hard Scope still applies.

## Card Types

Every anki-board card is a repository card in exactly one of the two repositories: one repository-owned isolated worktree, one protected baseline, one explicit test contract, one reviewed local commit, and controller local integration.

Add-on and tooling card: ordinary code work in either repository.

- A card for `/Users/chanbla11mit/projects/anki-addons` is created with `project: anki-addons`, so stock Kanban creates `/Users/chanbla11mit/projects/anki-addons/.worktrees/<task-id>` from that repository, and its body contains the full line `Add-on project EXACT anki-addons.`. A card for `/Users/chanbla11mit/projects/anki` uses the board default and never carries that line or project.
- Add-on tests run in a dedicated Python environment with Anki's `anki` and `aqt` packages pinned to 26.9.2 (the installed Anki version). Creating that environment is a download and needs a separate owner go-ahead; until the owner gives it, add-on cards test only code that does not import `anki` or `aqt`.
- Only `anki-orchestrator` installs an add-on build into the owner's Anki `addons21` folder, only after the owner approves that add-on and its reviewed commit SHA, and only after a backup of any existing folder of the same add-on.

Deck change card: a card in `/Users/chanbla11mit/projects/anki` whose deliverable is a committed change set file under `changesets/`.

- For each note, the change set lists the note ID, the field or tag, the exact current value, and the exact new value; it also lists any note to add, card to move, or tag to change. Deletions of notes, decks, or note types appear only as explicitly listed entries.
- The worker reads current values only through the allowed AnkiConnect read actions. The commit does not change the collection.
- The reviewer checks the change set against the card and against current values read through the same read actions.

## Applying a Change Set

Only `anki-orchestrator` applies a change set, and only when the owner names the change set file and the reviewed commit SHA in chat. Then:

1. Confirm that each note's current value still equals the recorded current value; if any differs, change nothing and report the differences.
2. Make a backup through Anki of every affected deck, including scheduling information, into the gitignored `private/backups/` of `/Users/chanbla11mit/projects/anki`.
3. Apply the entries through AnkiConnect.
4. Read every changed value back and report the counts.

Approval never carries over to another change set or SHA. Until an apply tool for these four steps exists in `/Users/chanbla11mit/projects/anki` (built later on an anki-board card), no change set is applied.

## Role Separation

The orchestrator plans, creates and routes cards, validates boundaries, monitors runs, integrates approved commits, relays owner decisions, applies owner-approved change sets, installs owner-approved add-on builds, and reports milestones. It does not edit repository files.

Workers do only the assigned card in its isolated worktree and request same-card review.

The reviewer reads the governing source, the exact candidate commit and diff, repository instructions, tests, and prior findings. It never edits implementation code or the reviewed change set. Approval uses `kanban_complete(..., board: anki)`; rework uses `kanban_request_changes(..., board: anki)`.

## Card Contract

Every card must contain:

1. Exactly one of `Repository /Users/chanbla11mit/projects/anki ONLY.` or `Repository /Users/chanbla11mit/projects/anki-addons ONLY.`
2. Workspace kind `worktree` and exact path `<repository>/.worktrees/<task-id>` for that repository.
3. `Baseline EXACT <40-hex-commit>.`
4. Add-on repository cards only: the full line `Add-on project EXACT anki-addons.` and `project: anki-addons`. Primary repository cards carry neither.
5. The governing source (specification path or owner request) and one bounded slice.
6. Acceptance criteria.
7. A Tests or Verification section containing executable commands.
8. One assigned anki worker.
9. `Reviewer EXACT anki-reviewer.`
10. A per-run runtime cap with rationale. Estimate the whole attempt, including discovery, tests, commit, and the review handoff; use an explicit `max_runtime_seconds` when it may exceed one hour, and raise the cap before retrying a timed-out attempt.
11. The required handoff: the local commit; for deck change cards, also the change set path and its entry counts.
12. The collection access rules and explicit prohibitions on remotes, push, PR, AnkiWeb sync or publication, installs, live policy changes, credentials, and other external writes without separate owner authorization.
13. Skill-policy metadata stating whether `minimal-implementation` is enabled and that requirements and risk outrank simplification.

`scripts/verify-state` fails closed on items 1–4 and 7–9 for every open card. Use `kanban_create(..., board: anki)` only after validating the complete contract, then read the card with `kanban_show(..., board: anki)` and verify the stored fields before dispatch.

## Card Setup

Set up a card without a setup-only hold:

1. Create it with the kanban_create tool: `kanban_create(..., board: anki, initial_status: blocked)`, adding `project: anki-addons` for an add-on repository card. The card is created blocked, so it cannot be dispatched before setup is complete, and its notification subscription exists from creation. Create cards only with the kanban_create tool, never with `hermes kanban --board anki create`. The tool auto-subscribes this session to the card with delivery_mode notify+wake, the owner's user ID, and this profile as notifier_profile, so completion, review-request, and block events wake this orchestrator and ping the owner. The CLI create command does not subscribe, and a manual notify-subscribe without flags defaults to notify with no user ID, which wakes nobody. This caused the 2026-10-20 stalls of the JSS and Jobcron orchestrators.
2. Read the new ID and write the exact ID, worktree path, and branch into the body.
3. Pin `refs/anki/baselines/<ID>` to the baseline in the card's repository.
4. Confirm the kanban_create result reports subscribed: true. Only if it does not, repair the subscription with: hermes kanban --board anki notify-subscribe <id> --platform telegram --chat-id <owner chat> --user-id <owner user> --chat-type dm --notifier-profile anki-orchestrator --delivery-mode notify+wake. Re-running notify-subscribe updates an existing row, so this command also upgrades a wrongly subscribed card.
5. Unblock the card so it becomes `ready`.

Never claim a card and `kanban_block` it as a setup hold. The worker's first action verifies `$HERMES_KANBAN_TASK`, worktree path, branch, and baseline, and it blocks only on a real mismatch. At creation Hermes records `workspace_path` as the repository root; the dispatcher's claim materializes `.worktrees/<ID>`. A root value before claim is expected, not a mismatch.

## Worker Selection

- Assign work to `anki-worker` or `anki-worker-2`. Spread independent ready cards across the two workers; keep cards that touch the same files serialized or dependency-linked. Review revision stays on the same assignee.
- Never route implementation to the orchestrator or reviewer, and never route review to a worker.

Before assignment, verify the exact profile with `hermes profile list`. To inspect queue state use `hermes kanban --board anki list --json`. Do not infer that reassignment started a worker; read the card and run history with `kanban_show(..., board: anki)` after the next normal dispatcher ticks.

## Worktree and Baseline Gate

Before dispatch:

1. Read the current protected baseline from Git in the card's repository.
2. Create the card first so its ID is known.
3. Require the task worktree path to end in that exact ID.
4. Confirm the worktree belongs to the card's one repository and starts from the recorded baseline.
5. Confirm the add-on project line and project match the repository, and that the worker profile and reviewer match this policy.
6. Confirm the Tests section has executable commands appropriate to the changed surfaces.

A shared checkout, foreign path, second repository, missing baseline, mismatched add-on project declaration, prose-only test plan, or mismatched assignee is a hard block.

## Skills

Attach `minimal-implementation` only for dependency choice, suspected overengineering, refactoring, simplification, or shared-function repair where simplification does not weaken required evidence. Leave it off for deck change cards and for collection-access or add-on install tooling, where exact boundaries outrank brevity. Verification and safety always outrank minimalism. Record the decision and reason on the card.

Before forcing a skill, run:

```bash
python3 /Users/chanbla11mit/hermes-local-harness/scripts/check-forced-skills --profile <assignee> --skills <skill> [<skill> ...]
```

A nonzero result rejects card creation.

## Bounded Autonomous Repair

Autonomous repair is opt-in only when the same card contains exactly one full line `authorization_mode: autonomous` and one full line `repair_policy: bounded-convergence-v1`.

Before first dispatch, append one `repair_history: <JSON array>` comment with `kanban_comment(..., board: anki)`. Append a complete successor snapshot for every transition. Continue on the same card; never reset the budget by changing cards, workers, models, branches, prompts, or labels.

Limits:

- At most three materially distinct approaches.
- At most three reviewed semantic attempts per approach.
- At most one infrastructure retry per pending attempt.
- A new approach requires an independent material-difference review.
- Exhaustion requires a human block with `kanban_block(..., board: anki)`.

User stop, product decisions, credentials or MFA, prohibited writes, unsafe state, capability boundaries, and policy, legal, or security decisions block immediately. Infrastructure failure is not reviewer approval or rejection.

## Autonomy

Bookkeeping never gates. Fix malformed `repair_history`, ledger, receipt, or handoff formatting by appending a valid successor that preserves the original. Such a correction is never a completion or integration prerequisite and never an owner question. Semantic gates are unchanged and still block: required tests, exact-candidate independent review, candidate drift, the collection access rules, real budgets, and authority/external-write limits.

Never ask the owner about:

- bookkeeping corrections
- historical test-order disclosures
- retry or budget accounting
- infrastructure retries
- read-only local diagnosis, including the allowed AnkiConnect read actions
- routine same-card rework
- local integration after approval

Ask only for:

- applying a change set (the owner names the change set file and the reviewed commit SHA)
- installing an add-on build into `addons21` (the owner approves the add-on and commit SHA)
- external writes (remote, push, PR, deploy, AnkiWeb sync or publication)
- credentials or MFA
- installs or downloads, including the add-on test environment
- live profile, skill, policy, board, or gateway changes
- product decisions, which here include which notes to change and which wording standard to adopt
- money or billing
- genuine capability limits
- a user stop or resume

Stale callbacks: run one `kanban_show(..., board: anki)`. If the card has already moved past the notified status, reply in at most one line (or say it is already handled) and do nothing else. `notify-subscribe` has no per-event filter (verified from CLI help on 2026-10-17). Filtering would need a Hermes patch, which the upgrade-safety rule forbids.

Proportional handoff checks:

- Trust successful tool results, and do not read back your own comments.
- Do not re-hash what the reviewer already verified; one exact-candidate check at integration or completion is enough.
- Keep controller comments to about 5 lines or fewer.
- Batch independent checks in one response; serialize only when a call depends on an earlier result.

No numeric caps on harmless actions: local reads, local tests, and the allowed AnkiConnect read actions. Keep caps only where a real cost, rate, mutation, or ambiguity risk exists (for example, live model calls and the repair budgets above).

## Incident recovery

An incident neither grants new authority nor automatically revokes unrelated authority. Worker-specific restrictions do not automatically restrict the controller; a higher-priority profile prohibition still wins over permissive card prose. Local/read-only intent alone grants no access. The anki fleet may not probe another project, even read-only. Keep all existing external-read/write, credential/MFA, product, security/legal/policy, capability and unsafe-state gates.

1. Contain the offending owned actor/path and verify cessation before reporting containment or resuming a contaminated path. If containment is unavailable, record the real blocker.
2. Preserve the failed invocation, partial artifact, evidence, pending semantic attempt and spent infrastructure retry on the same card. Changing worker/model/branch must not reset repair history or escape its bounds.
3. Classify diagnosis, remediation, and independent work separately by actual actor, target, effects, access, authority, and dependencies. Use a brief existing card note, not a new recovery form.
4. Perform the smallest useful read-only observation already authorized. Preserve failed or inconclusive observations; do not repeat a probe that cannot change the next action.
5. After containment, continue already-authorized work demonstrably independent of unresolved state. Withhold unauthorized remediation and pause dependent work. Before a campaign-wide block, name the concrete dependency affecting every remaining authorized action: X relies on unresolved Y for Z.

A forbidden AnkiConnect action or a direct open of a collection file is an incident: stop the actor, report the action and its target on the card, and keep any resulting commit out of integration. Restoring the collection from a backup is an owner decision.

User stop remains global: stop all owned workers, reviewers, and watchers, verify cessation, and never restart from delayed callbacks without user resume.

## Review and Integration

Request review with `kanban_request_review(..., reviewer: anki-reviewer, board: anki)` only after the candidate commit and required test evidence exist.

For approval, the reviewer calls `kanban_complete(..., board: anki)`. For a material defect, the reviewer calls `kanban_request_changes(..., board: anki)` with concrete findings. Do not replace same-card review with a summary from another session.

After approval, integrate locally into the card's repository without another approval prompt only if:

1. The reviewed commit exactly matches the reviewed diff.
2. The target checkout has no unrelated change that integration would disturb.
3. The approved commit descends from the protected baseline.
4. Integration checks pass.

Prefer fast-forward; otherwise merge or cherry-pick while preserving the reviewed tree and history. Local integration of a deck change card does not apply its change set, and local integration of an add-on card does not install it. Local integration does not authorize a remote, push, PR, deployment, AnkiWeb sync, live profile/skill update, board/gateway mutation, credential action, or other external write.

## Operational Discipline

- Use `kanban_list(board: anki)` for board discovery and always keep the explicit board argument.
- Use `kanban_show(..., board: anki)` before routing, after routing, and before interpreting any callback.
- Never manually force `hermes kanban --board anki dispatch` while the gateway dispatcher is active; observe normal ticks.
- Preserve rejected commits, worktrees, and change sets as evidence until the card is resolved.
- Keep verification proportional to the changed surfaces and named risks. Do not manufacture deadlines, credential-read ceilings, redundant review layers, or reusable automation when a bounded direct check answers the decision.
- Never modify the installed Hermes source. Use supported Hermes commands and repository-owned policy.

## Completion Gate

Before reporting an anki card complete, check semantic validity, not bookkeeping-format validity:

- The board, repository, add-on project declaration, worktree, baseline, assignee, reviewer, and test contract match the card.
- Required focused and broader tests pass.
- The candidate commit is reviewed by `anki-reviewer` on the same card.
- The approved change is locally integrated or an exact integration blocker is recorded.
- Git and `kanban_show(..., board: anki)` agree on the result.
- No forbidden AnkiConnect action, direct collection file access, unapproved collection write or add-on install, remote, push, PR, AnkiWeb sync or publication, install, policy rollout, credential operation, or other external write occurred.
