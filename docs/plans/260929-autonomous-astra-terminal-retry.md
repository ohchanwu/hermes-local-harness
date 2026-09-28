# Autonomous Astra terminal-retry harness plan

Status: proposed; implementation not started.

Baseline: `82113968519ae678726798373ce22c46b14a5a35` on `hermes-local-harness/main`.

## Objective

For an explicitly authorized fully autonomous campaign, a remediable semantic failure found by the independent reviewer at the final Astra rung must not stop the campaign. The same card stays at Astra, is reassigned to `worker-astra`, receives a new bounded implementation run, and returns to independent `reviewer-sol` review. This loop continues until the exact candidate is approved.

Side-by-side and ordinary bounded campaigns retain the existing terminal behavior: exhausted Astra revisions become `HUMAN_BLOCK`.

## Non-goals and retained human gates

This change does not make every Astra failure retryable. `HUMAN_BLOCK` remains mandatory for:

- user stop, pause, or authorization revocation;
- missing or contradictory product requirements that require an actual decision;
- credentials, MFA, attended authentication, or prohibited external writes;
- unsafe or unrecoverable repository/worktree state;
- a demonstrated capability boundary that another Astra attempt cannot resolve;
- policy, legal, or security decisions reserved for a human.

Provider, quota, crash, timeout, and context-exhaustion failures remain infrastructure outcomes. They do not enter the semantic review loop. Keep the current bounded infrastructure retry policy and human-block at Astra; broadening infrastructure retries is a separate decision.

The change does not modify Hermes core, patch the Kanban SQLite database, add a daemon, or create a second campaign store.

## Policy model

### 1. Version the ladder and make the behavior opt-in

Introduce `glm-review-v2` while preserving `glm-review-v1` semantics for existing cards.

A card may use terminal retries only when its durable metadata contains all three fields:

```yaml
ladder_version: glm-review-v2
authorization_mode: autonomous
terminal_retry_policy: astra-until-approve-v1
```

The default for missing, malformed, side-by-side, or v1 metadata is bounded Astra behavior and `HUMAN_BLOCK`. Never infer the mode from repository, assignee, model, tenant, or another card. Do not silently migrate in-flight cards; an existing campaign may opt in only through an explicit user authorization recorded on that exact card/root campaign.

Every retry record must also identify the root task, campaign generation, repository, protected baseline, worktree/branch, rejected candidate SHA, reviewer run ID, attribution, findings, and retry strategy. Event history is authoritative for the terminal-cycle count; a displayed ordinal is informational only.

### 2. Add one terminal retry verdict

Extend the reviewer contract with:

```yaml
verdict: RETRY_TERMINAL
strategy: continue | restart
rung: astra
```

`RETRY_TERMINAL` is valid only when:

- the three opt-in metadata fields match exactly;
- the current rung is Astra;
- `reviewer-sol` found a concrete, remediable semantic defect;
- the verdict is fenced to the current review run and exact candidate SHA;
- the outcome would otherwise exhaust Astra or require advancement beyond it.

Do not overload `ESCALATE_CONTINUE`: Astra does not advance a rung. Do not erase or reset ordinary same-rung revision history. The first one or two localized Astra corrections may still use `REVISE_SAME_RUNG`; after its allowance is exhausted, semantic correction uses `RETRY_TERMINAL`.

### 3. Define retry mechanics

For `strategy: continue`:

1. Preserve the branch, commit, test evidence, and reviewer findings.
2. Use the native review-return transition (`kanban_request_changes`) with the structured `RETRY_TERMINAL` verdict.
3. Confirm the card returns to `worker-astra`, remains on the same root/generation and worktree, and becomes eligible.
4. Verify a new run ID is claimed within two normal dispatcher ticks.
5. Require a new local commit or an explicit reviewer-guidance invalidation before another review; do not review an identical SHA repeatedly.
6. Require another independent `reviewer-sol` review.

For `strategy: restart`:

1. Durably block with the structured verdict before changing ownership.
2. Preserve the rejected branch, commit, findings, and evidence.
3. Create a fresh worktree from the recorded protected baseline.
4. Keep the same card, root identity, generation lineage, and Astra rung.
5. Reassign to `worker-astra`, explicitly promote to `ready`, and verify the new claim/run receipt.
6. Require another independent `reviewer-sol` review.

Duplicate/stale reviewer callbacks must be idempotent and must not create two Astra runs. A verdict for an older run, generation, candidate, worktree, or root task must be rejected.

### 4. Keep retries bounded per run, not per campaign

The semantic correction loop has no campaign-level retry count: it continues until approval or a retained human gate occurs. Each individual Astra run still has:

- an explicit runtime cap sized from prior evidence;
- one-run-per-profile concurrency;
- normal test and review requirements;
- preserved attribution and artifacts;
- dispatch-receipt verification.

Prevent a hot no-progress loop: an unchanged candidate, duplicate verdict, or no-edit completion is a protocol/infrastructure condition to diagnose, not another semantic review cycle. Use bounded dispatch backoff; never weaken acceptance criteria, tests, reviewer independence, or security policy to terminate the loop.

## Repository changes

### Canonical orchestration policy

1. `skills/multi-agent-coding-orchestrator/SKILL.md`
   - bump the skill version;
   - add `glm-review-v2`, exact opt-in metadata, `RETRY_TERMINAL`, continue/restart transitions, fencing, and dispatch receipt;
   - qualify the current unconditional Astra `HUMAN_BLOCK` rule by authorization mode;
   - retain the human-gate and infrastructure exclusions;
   - add GOOD/BAD examples for fully autonomous and side-by-side campaigns.

2. `policies/escalation-ladder.md`
   - document v1 compatibility and v2 mode-dependent final-rung behavior;
   - keep Astra as the final implementation rung rather than inventing a new rung.

3. `policies/authority-and-review.md`
   - define who may authorize `astra-until-approve-v1` and its exact card/root scope;
   - state that autonomous semantic retry does not authorize external writes or erase human gates.

4. `roster.yaml`
   - bump the schema and ladder versions;
   - replace the scalar `revision_limits.final_tier` declaration with explicit defaults and supported opt-in terminal policy;
   - keep bounded behavior as the default and `worker-astra` as the sole terminal implementation assignee.

### Notification correctness

The current notification classifier treats blocked reasons containing `review` as human-relevant. A restart-style automatic retry can therefore emit a false blocker notification.

5. `plugins/hermes-terminal-outcome-notification/core.py`
   - recognize the exact structured `RETRY_TERMINAL` marker before heuristic blocker matching;
   - classify it as non-human while it belongs to the current run and opted-in campaign;
   - continue delivering explicit `HUMAN_BLOCK`, `needs_input`, `capability`, and exhausted non-retryable outcomes;
   - preserve generation/run fencing so a retry cancels stale pending blocker notifications.

6. `tests/test_terminal_outcome_notifications.py`
   - cover automatic retry suppression, stale-generation cancellation, and continued delivery of genuine human blocks.

7. Update the notifier's version/pin surfaces after its reviewed commit exists:
   - `plugins/hermes-terminal-outcome-notification/plugin.yaml`;
   - `plugins/hermes-terminal-outcome-notification/README.md`;
   - `docs/specs/260921-hermes-terminal-outcome-notification.md`;
   - `procedures/hermes-terminal-outcome-notifications.md`;
   - `deployment/hermes-terminal-outcome-notification.example.yaml`.

### Desired-state verification

8. `scripts/verify-state`
   - validate the new roster schema and exact mode contract;
   - fail if autonomous terminal retry becomes the fleet default;
   - fail if required human-gate or infrastructure exclusions disappear;
   - continue checking tracked/deployed skill hashes and plugin pins.

9. `tests/test_verify_state.py`
   - assert the new skill/ladder version and required contract markers;
   - add negative cases for default-autonomous drift, missing card scope, and erased blocker exclusions.

10. `tests/gen_fixtures.py` and generated fixtures
    - update the clean v2 desired state;
    - add fixtures for default-mode drift, missing autonomous scope, and missing human-block exclusions;
    - retain all existing plugin, skill, profile, and adapter drift failures.

11. `snapshots/sanitized-current-state.yaml`
    - refresh reviewed orchestrator-skill hashes/version;
    - refresh notifier version/pin after publication;
    - record the bounded default and supported opt-in terminal mode.

12. `procedures/manual-apply.md`
    - document deployment of the reviewed skill and notifier copies/pin;
    - do not add an apply script or patch Hermes source.

Do not edit the archived tracking plan.

## Test matrix

The implementation is acceptable only when all of these pass:

1. A v1 or side-by-side Astra exhaustion still produces `HUMAN_BLOCK`.
2. An opted-in v2 semantic rejection produces `RETRY_TERMINAL`, remains at Astra, and creates a new `worker-astra` run ID.
3. Continue preserves the branch and rejected evidence.
4. Restart preserves rejected evidence and begins from the protected baseline.
5. A gateway restart reconstructs the policy and retry count from card metadata/events alone.
6. A stale run/generation/candidate verdict cannot requeue the card.
7. Duplicate callbacks do not create duplicate Astra runs.
8. An identical candidate SHA is not repeatedly reviewed unless the prior review is explicitly invalidated.
9. Concurrent cards, even in the same repository, cannot consume each other's authorization or verdict.
10. Credentials, prohibited actions, product decisions, unsafe state, capability limits, and user stop never auto-requeue.
11. Provider/timeout/context failures remain on the infrastructure path.
12. An automatic retry emits no terminal human-block notification.
13. A genuine Astra `HUMAN_BLOCK` emits exactly one notification per destination.
14. Approval names the exact candidate SHA and follows the existing local-integration contract.
15. `python3 tests/test_verify_state.py` passes.
16. `python3 tests/test_terminal_outcome_notifications.py` passes.
17. `./scripts/verify-state` passes after tracked state is deployed.

## Implementation and review sequence

1. Create an isolated harness worktree from the baseline.
2. Implement policy/roster/verifier changes and their fail-closed fixtures with tests first.
3. Implement notifier classification and tests.
4. Run both test suites, `git diff --check`, secret scanning, and fixture/live verification appropriate to the pre-deployment state.
5. Commit locally and obtain independent `reviewer-sol` approval of the exact commit.
6. Fast-forward the reviewed harness branch into local `main`.
7. Publish/pin the notifier only with separate external-write authorization.
8. Manually copy the reviewed orchestration skill to the default profile and deploy the reviewed notifier pin to producer profiles; reload the notification worker.
9. Run live `./scripts/verify-state`.
10. Canary with disposable local cards:
    - opted-in Astra fail → retry → approve;
    - simultaneous bounded Astra failure → human block;
    - explicit capability/human block → one notification.
11. Enable the policy only on individually authorized campaigns.

## Rollback

1. Stop issuing `astra-until-approve-v1` metadata and pause active loops without deleting history.
2. Convert affected cards to bounded mode or explicit `HUMAN_BLOCK`.
3. Restore the prior reviewed skill and notifier pins/copies using the manual procedure.
4. Reload the notification worker and run `./scripts/verify-state`.
5. Preserve all branches, worktrees, comments, rejected commits, and Kanban events.

## Completion criteria

The harness change is complete when the tracked policy, desired state, notification behavior, and deployed copies agree; all deterministic tests pass; the three-card canary demonstrates retry, bounded blocking, and genuine notification behavior; and no Hermes-core modification or hidden global autonomous default was introduced.
