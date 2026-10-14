# Implementation plan: incident recovery without invented gates

Date: 2026-10-14
Status: Authorized local implementation on Harness card `t_acef09b6`; same-card review and local integration pending. Live rollout remains unauthorized.
Provenance: original proposed/authoring-only standalone attachment SHA256 `a2aa7b1a74c68c0ad29f8358ee00c3b61985cf0dc31a69dc4020d885b4b3207b`. The subsequent human instruction “Ok, start autonomous impl then.” authorizes the exact bounded local slice, configured synthetic inference, same-card review and orchestrator local integration, not live or foreign-project effects.
Recommended tracked destination: `docs/plans/261014-incident-recovery-implementation-plan.md`
Specification: `docs/specs/261014-incident-recovery-without-over-gating.md` (adopted companion specification).
Repository: `/Users/chanbla11mit/hermes-local-harness` only.
Inspected baseline: `84d91a7ba698d38bb31c5b80e04dea0dd002d15f` on `main`; working tree clean at plan authoring.

## 1. Delivery shape

Use one Harness implementation card and one repository-owned isolated worktree. Execute the steps below sequentially within that card, not as a new campaign graph. The exact assigned profile is `harness-worker`; this card does not authorize substitution. Independent review is always `harness-reviewer` on the same card.

The deliverable is a concise tracked policy correction plus honest regression evidence. Do not build a permission engine, generalized replay platform, production test wrapper, incident ledger, new deployment machinery, or auto-cleanup facility.

The implementation stops at reviewed local integration. Live policy deployment is separate.

## 2. Findings that affect the plan

### Existing behavior guidance is too remote from the decision

The repository-owned Jobcron skill already discusses fixture routing and incident/code-correctness separation in Pitfalls. Put the operative recovery rule where controllers construct, recover, and route tasks; retain or shorten the existing pitfall without creating contradictory duplicates.

### A listed broad test is not hermetic

Inspection of `tests/test_verify_state.py` found real home-directory backup/profile checks and a forced-skill check referencing the installed Hermes source. Do not run that entire script under this scope. Pre-dispatch inspection additionally discovered the production verifier reads a foreign repository instruction file BEFORE its fixture branch. Direct invocation, even with a fixture, is fenced. Earlier authoring-time runs missed this escape. The adopted test-only driver uses declared-binding/fixture substitution and fences other resource access. This is scoped mocked coverage, not real foreign-source validation. Preserve the discovery and do not repeat or recheck that foreign read.

This is a corrected test contract, not a claim that the full suite passed. Do not solve it by reading additional profiles or installed source, or by expanding this task into a rewrite of unrelated rollback tests.

### Policy files are hash-pinned

`scripts/verify-state` verifies canonical shared-skill hashes and tracked project override hashes against `snapshots/sanitized-current-state.yaml`. Policy edits therefore require narrow source-pin updates and matching synthetic fixture changes. The companion specification now includes that necessary metadata surface.

An updated expected source hash is not evidence of live deployment. Preserve the original observation via the protected baseline and annotate repository-only source-pin advancement and pending live rollout. Do not relabel a synthetic fixture as an observed installation.

## 3. Preconditions and card contract

Before dispatch, the orchestrator must:

1. Confirm board `harness`, repository root, current `main`, clean integration target, exact worker profile, and reviewer roster. Use only explicit `board: harness` / `--board harness` operations.
2. Revalidate the baseline. If `main` has advanced, inspect only the relevant delta, update the specification/card baseline explicitly, and rerun affected checks; do not silently retain a stale baseline.
3. Make this plan and the corrected specification available to the worker as exact artifacts. Their later repository adoption is part of the authorized implementation slice, not an assumption that they already exist there.
4. Create and verify a card with one exact baseline, one exact `.worktrees/<task-id>` workspace, executable tests, the bounded file allowlist below, and same-card reviewer. No dispatch until the stored card and actual workspace match. If the supported creation flow requires an ID before an exact path can be stored, keep the card non-dispatchable until the path and contract are finalized; do not race the dispatcher or edit the board database directly.
5. Verify the worktree belongs to the Harness common Git directory, starts at the protected baseline, and is not a shared checkout. Protect the baseline with a local reference or the established repository baseline mechanism; no history rewrite.

Suggested card fields, to be resolved and validated rather than pasted with placeholders:

- `Repository /Users/chanbla11mit/hermes-local-harness ONLY.`
- Board: `harness`.
- Workspace kind: `worktree`.
- Workspace: `/Users/chanbla11mit/hermes-local-harness/.worktrees/<actual-task-id>`.
- `Baseline EXACT <validated-40-hex-commit>.`
- Specification and plan: exact staged artifact paths, then their tracked destinations.
- Slice: policy recovery rule, compact regression coverage, necessary source pins, documentation adoption.
- `Reviewer EXACT harness-reviewer.`
- Runtime cap: propose `max_runtime_seconds: 7200` as a per-run hung-worker watchdog covering discovery, tests, and handoff; it is not campaign authorization expiry. Reassess using actual runtime evidence if needed.
- `minimal_implementation: disabled`; reason: authority/trust-boundary change. Verification and safety outrank simplification.
- Completion contract: `local-only`; local commit and structured handoff required.
- Explicitly forbid pushes, PRs, live skill/profile rollout, board/gateway configuration changes, credentials, other-board/repository operations, shared cleanup, and production/cloud/external mutations.

The exact card explicitly authorizes bounded-convergence-v1 and records initial history before dispatch. Logical pending attempt `t_acef09b6-a1-attempt1` maps to native implementation run 2; staging run 1 was not implementation. Preserve complete append-only successor snapshots, pending attempt and infrastructure spend. Never reset repair history by changing cards or workers.

## 4. Bounded file allowlist

Primary edits:

- `policies/authority-and-review.md`
- `skills/multi-agent-coding-orchestrator/SKILL.md`
- `policies/profile-skills/jobcron-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md`
- `policies/profile-skills/harness-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md`, only for necessary Harness-specific alignment
- `tests/test_incident_recovery.py` (new focused stdlib suite)
- `tests/fixtures/incident-recovery-cases.json` (synthetic inputs, no expected answers)
- `tests/fixtures/incident-recovery-expectations.json` (reviewer/test oracle, never replay input)
- `tests/incident_recovery_replay.py` (small offline prompt/response helper, only if existing tooling is insufficient)
- `tests/incident_recovery_verify_fixture.py` (test-only contained fixture driver, never a production runner)
- `tests/test_diagnostic_convergence.py`, only if needed to retain/add the relevant policy/link contract
- `docs/README.md`
- The specification and plan at their recommended tracked destinations

Necessary hash dependency only:

- `snapshots/sanitized-current-state.yaml`: only affected source hashes/versions and an explicit repository-only/pending-live provenance note.
- Existing `tests/fixtures/*.yaml`: only affected skill hash/version fields and their directly corresponding negative controls. Enumerate the exact affected fixture filenames on the card after read-only dependency discovery, before editing them.

Do not change roster/profile/model/dispatch settings, plugin code, actual project sources, other fleets' policy content, deployed files, or the production verifier implementation to make a fixture pass. If the existing schema cannot represent source-pin advancement honestly, report that exact incompatibility rather than silently recording a deployment that did not happen.

## 5. Ordered implementation steps

### Step A — Capture relevant baseline and define the replay boundary

- Read the card, specification, this plan, repository instructions, relevant policy sections, and hash consumers.
- Save baseline copies of the affected policy files from the exact protected commit in task-local ignored evidence. Use repository-relative policy paths so temporary worktree names do not affect policy-bundle identity.
- Inspect the supported replay options available within authorized Harness execution. No source patch, guessed dry-run flag, credential read, profile reconfiguration, or active live-policy replacement.
- Select one of these evidence modes:
  - Safely intercepted action replay, if a supported mechanism actually prevents real effects.
  - Explicitly labeled action-selection-only replay, with synthetic state and actual model responses, if authorized and supported.
  - An exact behavioral-verification blocker if neither can be performed safely/within authority.
- Record the actual supported invocation only after verification. Do not create a framework to compensate for a missing execution boundary.

Exit: the baseline, file surface, and evidence mode are known. A replay limitation need not prevent safe static implementation, but it remains a blocker to claiming the full behavioral correction complete.

### Step B — Write regression fixtures and tests before changing policy

Create R1–R10 plus the authority-precedence case from the specification. Fixtures must distinguish input facts from expected outcomes. R6 includes a user stop followed by a delayed completion callback; R7 includes an already-spent infrastructure retry and a pending semantic attempt; R9 includes current metadata with explicitly unknown historical impact.

For R3, cover both out-of-project read-only access and a protected-credential requirement. For R5, require no false containment claim while the offending actor is still active. Do not teach that "independent" overrides a global stop or higher-priority prohibition.

Focused suite requirements:

- Validate scenario IDs, required fields, oracle separation, no real targets/secrets, and source-policy manifest completeness.
- Assert the candidate policy contains the operative rule at the decision point and preserves genuine gates, same-card continuity, and global user stop.
- Add a real inert child-process test for R10. Give the child a deliberately minimal synthetic environment, not a copy of the host's real secret-bearing environment. Test explicit broad-command removal of the synthetic integration inputs and separately scoped targeted inclusion. Use `sys.executable`, an absolute executable path, captured output, and a subprocess timeout.
- Capture which inputs the child actually sees. Do not print real environment values, access a database, or run a project preview script.
- Test absent optional inputs, a contaminated synthetic parent, and targeted-only activation. This proves a command-construction pattern, not repaired enforcement in actual Jobcron code.
- Ensure the suite runs when invoked directly with `python3 tests/test_incident_recovery.py`, reports what ran, and returns nonzero on failure.

Run the relevant baseline policy assertion and capture any observed failure before editing. If the baseline already passes, report that fact; do not invent a RED result. The inert child mechanism may pass from its first implementation and is not proof of prior controller failure.

### Step C — Implement the concise policy correction

Add one clearly headed incident-recovery section near task recovery/routing in the shared and relevant tracked project policies:

1. Contain the offending actor/path and preserve evidence.
2. Classify diagnosis, remediation, and independent implementation separately using actor, target, effects, access, authority, and dependencies.
3. Perform the smallest useful observation when already authorized.
4. Continue isolated authorized work whose safety is independent of unresolved cleanup, preserving the same card/artifact/history.
5. Withhold unauthorized effects and pause genuinely dependent work.
6. Require a concrete dependency explanation before a campaign-wide block.

Explicitly retain the limitations that local/read-only is not blanket permission, profile prohibitions outrank permissive card prose, unknown cleanup remains unknown, and user stop remains global. Add the exact-invocation environment-clearing requirement without inventing a universal variable blacklist or new production wrapper.

Use brief existing card comments/handoffs, not a mandatory new recovery form. Reconcile existing related text instead of growing an append-only checklist. Avoid mass-editing unrelated fleets.

### Step D — Update source pins and documentation atomically

- Bump changed tracked skill versions according to their existing convention.
- Compute hashes from actual changed bytes using tooling; never copy plausible hashes.
- Update only those expected source hash/version bindings and synthetic fixture fields that consume them. Preserve intentional negative fixture mismatches; do not normalize every fixture to green.
- Add a bounded provenance note identifying the protected baseline and stating that source pins advanced locally while live rollout and live verification were not performed. Do not update collection timestamps as if a live observation occurred.
- Adopt the corrected specification and this plan into `docs/specs/` and `docs/plans/`; index both in `docs/README.md`. Keep links repository-relative and valid.

### Step E — Exercise baseline/candidate behavior and repository checks

Behavioral replay:

- Use the same authorized model/settings and frozen scenario inputs for baseline and candidate, with fresh sessions to avoid earlier answers contaminating later trials.
- Present the exact relevant policy bundle plus scenario facts, not expected answers or a list of correct decisions.
- Capture actual responses/action traces. An offline helper may prepare prompts and validate/import response files, but must never generate model answers itself or execute actions described in them.
- For structured action-selection output, record proposed actions and targets, authorization basis, dependencies, whether a fresh approval is requested and why, continuity fields, evidence limitations, and stop handling. Ask for decisions and concise reasons, not hidden reasoning.
- Record actual model identity/settings, scenario ID, baseline/candidate policy digest, evidence mode, response path, and observed outcome. Missing settings are unknown, not invented.
- A mechanical parser can check required fields and prohibited action declarations; same-card reviewer judgment must assess the semantic decision. Keyword matching is not behavioral acceptance.
- Baseline results are comparative evidence, not a required fabricated failure. Candidate cases must pass in two consecutive runs as specified; failures stay visible and repairs retain existing history.

Run the scoped commands in section 6. No cross-project or live incident operation is part of this exercise. A synthetic action trace never proves actual shared cleanup or real-world agent reliability.

### Step F — Commit, same-card review, integrate

- Inspect the complete diff, file allowlist, test results, and publication surface. Commit successful work locally in the isolated worktree.
- Submit the exact commit and evidence using same-card review with `harness-reviewer`. Reviewer reads the spec/plan, actual diff, baseline/candidate results, remaining limits, and retained gates; no separate approval layer or reviewer card.
- Material defects return to the implementer through the normal same-card mechanism. Retain rejected candidates and evidence.
- Full approval requires all specification acceptance criteria, not just static tests. If behavioral verification is unavailable, report the exact outstanding AC2 limitation instead of declaring the complete correction done. Do not create a duplicate card merely to clear the blocker.
- After approval, orchestrator verifies the exact reviewed commit/diff, baseline ancestry, clean target, and scoped integration checks. Integrate locally, preferably fast-forward. If conflicts would materially change the reviewed tree, route that change for same-card review rather than silently resolving and claiming unchanged approval.
- Read back the exact Harness card and Git state before reporting integrated completion.

## 6. Executable verification contract

All commands run with explicit cwd set to the validated task worktree. Use the profile-managed scratch area for temporary state; preserve `TMPDIR` and make test-created temporary files stay there. Do not run a live verifier or the full live-sensitive `tests/test_verify_state.py`.

Required scoped checks after complete resource/subprocess preflight:

```sh
python3 tests/test_incident_recovery.py
python3 tests/test_diagnostic_convergence.py
python3 tests/test_terminal_outcome_notifications.py
python3 tests/incident_recovery_verify_fixture.py tests/fixtures/clean.yaml
python3 tests/incident_recovery_verify_fixture.py tests/fixtures/incomplete-empty.yaml
python3 tests/incident_recovery_verify_fixture.py tests/fixtures/deployed-skill-divergence.yaml
git diff --check
```

The driver substitutes the foreign-source assertion with declared-binding/fixture comparison and fences other resources to existing read-only task-worktree paths; commands/network are forbidden during verifier execution. Never invoke production `scripts/verify-state` directly, even in fixture mode. Each wrapper succeeds ONLY on its expected embedded result: clean exit 0; incomplete exit 1 with `incomplete fixture`; divergent exit 1 with `deployed skill hash mismatch`. Report embedded exit separately and test wrapper fail-closed controls. No blanket `|| true`.

Original plan authoring recorded clean exit 0 and both negative exits 1. These are retained historical observations, not safe execution evidence: the foreign read escaped those runs. Do not repeat/recheck it. The full live-sensitive suite remains unrun.
Publication checks:

```sh
gitleaks dir --redact --no-banner docs/specs/261014-incident-recovery-without-over-gating.md
gitleaks dir --redact --no-banner docs/plans/261014-incident-recovery-implementation-plan.md
```

Also scan each exact changed policy, metadata, test, and fixture file with redaction enabled; enumerate paths from the actual diff. Manually inspect for sensitive details regardless of scanner output.

The behavioral invocation must be added to the final card after a supported mode is established. Proposed new helper interfaces are not existing Hermes capabilities. If a new offline helper is needed, keep it stdlib-only and limited to prompt preparation, digest binding, response ingestion, and report validation; no provider transport, credential loading, tool execution, auto-retry, or live-state access.

## 7. Acceptance-to-evidence mapping

- AC1: policy diff and focused placement/retained-boundary tests.
- AC2: actual baseline/candidate replay receipts and same-card semantic review, with evidence mode explicitly stated; no static-only substitution.
- AC3: captured inert child-process output for R10 and targeted-only activation controls.
- AC4: R7/R9 behavior plus evidence/history readback; no false cleanup claim.
- AC5: focused tests, safe broader fixture/policy/notification checks, negative controls, link checks, redacted scans, and manual publication review. Disclose that the live-sensitive full suite was not run.
- AC6: same-card reviewer approval tied to exact candidate commit, followed by verified local integration.
- AC7: scope/diff review and observed execution record showing no prohibited effect or live rollout.

A completed preparation step, a local commit, successful worker launch, or partial test pass is not full completion.

## 8. Handoff, rollback, and later rollout

Worker handoff: exact board/card/worktree/baseline/commit, changed files, executed commands with exit status, scenario results, actual model/evidence mode, private evidence locations, source-pin provenance, and unresolved acceptance items. Keep raw transcripts and mutable replay outputs in task-local ignored evidence; tracked docs contain only sanitized summaries and fixtures. Never treat gitignore as permission to retain secrets.

Rollback of a locally integrated defect is a reviewed local revert, preserving the original commit and evidence. Do not reset shared history or delete worktrees/failed attempts to hide a defect. With no live rollout, no live rollback is necessary.

If live rollout is later explicitly authorized, use existing attended manual-apply practices and exact reviewed source bindings; no automatic deployment. Move useful completed planning material to the repository's established archive lifecycle and repair its links only after completion, not while this plan is still pending.

## 9. Current completion boundary

The originals were proposed authoring artifacts, not execution authority. They are now adopted under the exact authorized Harness card with the foreign-read correction. Actual checks, behavioral limitations and commit evidence belong to that card; adoption itself proves none of them. Full completion requires actual baseline/candidate behavioral evidence, independent same-card review and orchestrator integration. Live rollout remains unauthorized.
