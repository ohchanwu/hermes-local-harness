# Local Hermes Harness Tracking Plan

## Purpose

Create a small, private, version-controlled source of truth for the local Hermes orchestration harness without modifying or forking the installed Hermes source. Preserve upgrade safety, make configuration drift visible, and make the harness reproducible without committing credentials or runtime databases.

## Current state

The current setup already has several useful tracking layers:

- The installed Hermes source checkout is clean and matches `origin/main`; the harness does not depend on local source patches.
- Shared orchestration policy is stored in the local Hermes skill `multi-agent-coding-orchestrator`, currently version `0.2.0`.
- The Flash → Luna → Terra → GLM-full → Sol → Astra → human ladder is installed, authenticated, applied, and dry-run tested.
- The installed topology contains the Sol orchestrator, independent Sol reviewer, advisor, nine implementation lanes, and one dormant Terra spare.
- The initial dispatch pool contains three Flash lanes, two Luna lanes, and `reviewer-sol`.
- `kanban.max_in_progress` is unset, `kanban.max_in_progress_per_profile` is `1`, and a five-lane helper safely changes the active implementation pool without consuming reviewer capacity.
- Cha PT and Jobcron each contain a Git-tracked Hermes orchestration adapter specification. Their repositories remain authoritative even though their current paths reside beneath the retired legacy GT directory.
- Kanban preserves task, review, escalation, and handoff history.
- Private pre-update and pre-ladder Hermes state snapshots exist outside Git.

The gaps are:

- `~/.hermes` is not itself version-controlled.
- The shared orchestration skill and profile configurations have no normal Git change history.
- There is no single desired-state inventory of profiles, models, providers, plugins, dispatch eligibility, active-pool membership, concurrency, or ladder policy.
- The already-applied ladder and its revision rules are durable in live policy but are not yet tracked in a private control repository.
- Point-in-time state snapshots are rollback material, not readable configuration ledgers.

## Proposed source-of-truth model

Use four distinct layers, each authoritative for a different concern:

1. A private harness-control Git repository holds desired state, shared policy, decisions, and verification procedures.
2. `~/.hermes` holds live applied configuration and runtime state.
3. Kanban holds active execution, attempts, reviews, escalations, and handoffs.
4. Project repositories hold repository-specific constraints and adoption status.

Hermes state snapshots remain private rollback and disaster-recovery artifacts, not configuration documentation.

## Control repository

Create a private Git repository outside both the Hermes source checkout and `~/.hermes`, for example:

    ~/hermes-local-harness/
      README.md
      roster.yaml
      policies/
        escalation-ladder.md
        authority-and-review.md
        concurrency.md
      skills/
        multi-agent-coding-orchestrator/
          SKILL.md
      scripts/
        verify-state
      procedures/
        manual-apply.md
      snapshots/
        sanitized-current-state.yaml
      decisions/
        YYMMDD-<decision>.md

The exact location may change, but it must not be nested inside the installed Hermes source checkout.

## Desired-state inventory

`roster.yaml` should record, without secrets:

- profile name and role;
- model and provider;
- whether the profile is installed;
- whether the profile is eligible for Kanban dispatch;
- whether it is currently in the dispatch pool;
- lifecycle state: active, dormant-spare, or rollback-only;
- per-profile concurrency limit;
- required plugins and modes, including Ponytail requirements;
- enabled toolsets relevant to the role;
- review and orchestration relationships;
- whether a credential is required and whether one is present, using booleans or symbolic names only;
- repository scope, if any.

It should also record global settings such as:

- `ladder_version`;
- ordered escalation rungs;
- permitted direct-entry rungs;
- maximum concurrent implementation runs;
- the expected native settings `kanban.max_in_progress: null` and `kanban.max_in_progress_per_profile: 1`;
- the active implementation-profile allowlist and the requirement that `reviewer-sol` remain outside its five-slot budget;
- lane-switch helper version and policy;
- review and escalation priority;
- whether automatic decomposition is enabled;
- revision and infrastructure-failure limits;
- final-tier human-intervention behavior.

## Escalation and revision policy

Record the applied ladder explicitly and give it a version:

    Flash → Luna → Terra → GLM-full → Sol → Astra → human

Every task governed by the ladder should record:

- ladder version;
- entry rung;
- current rung;
- baseline commit;
- attempt and revision counts;
- escalation cause and attribution;
- whether escalation continues the existing work or restarts from baseline.

Same-rung revision policy:

- Allow one same-rung REVISE cycle by default.
- Permit one additional and final same-rung revision only when either:
  1. prior substantive feedback was substantially resolved and the remaining work is localized, mechanical, and unambiguous; or
  2. the failed retry is attributable primarily to incorrect, contradictory, incomplete, or materially ambiguous reviewer guidance.
- Every same-rung revision counts against the rung's allowance, including reviewer-error retries.
- No rung may receive more than two same-rung REVISE cycles.
- Reviewer error changes attribution but does not reset or extend the retry allowance.
- After the second revision, the reviewer must choose APPROVE, ESCALATE_CONTINUE, ESCALATE_RESTART, or HUMAN_BLOCK.
- At Astra, exhausted revisions or any condition that would require further escalation must produce HUMAN_BLOCK and notify the human.

When reviewer error is cited, preserve:

- what the reviewer got wrong;
- how that error caused or materially contributed to failure;
- corrected actionable guidance;
- whether an independent worker error also occurred.

## Concurrency policy

Initial policy:

- Maximum concurrent implementation runs: 5.
- Reviewer and orchestrator/control-plane activity must not consume implementation slots or be starved by them.
- Reviews and escalation continuations take precedence over starting new low-rung work.
- Installed profiles and lanes represent available capacity; idle profiles do not consume implementation slots or model usage.
- Retain all planned lanes even when the concurrency cap is below total lane count.

Raise the implementation cap from 5 to 7, and later from 7 to 9, only after observing:

- sustained slot saturation;
- meaningful ready-task wait time caused specifically by the cap;
- acceptable reviewer latency;
- no problematic test, worktree, CPU, memory, or repository contention;
- no material provider rate-limit increase;
- acceptable cost and branch pressure.

## Repository adapters

Keep the existing tracked repository adapters in Cha PT and Jobcron. They should:

- point to the shared orchestration policy instead of duplicating the fleet roster;
- record only repository-specific constraints;
- identify local verification requirements;
- state external-action and production boundaries;
- define repository-specific rollback or pause behavior.

The control repository should contain links or identifiers for adopted repositories, not duplicate their detailed specifications.

Cha PT and Jobcron remain active project-adoption records. Treat only their Git repositories, Hermes adapters, and repository-specific constraints as authoritative. Gas Town services, agents, boards, control-plane state, and workflows are retired: do not inventory, invoke, verify, or maintain them. During baseline capture, flag any adapter instruction that still depends operationally on GT instead of silently preserving that dependency.

## Secrets and sensitive state

Never commit:

- `.env`;
- `auth.json`;
- API keys, OAuth grants, or credential exports;
- `state.db`;
- `kanban.db`;
- raw session transcripts;
- private Telegram or account identifiers;
- secret-bearing state snapshots;
- raw private logs.

The desired-state inventory may record that a credential is required or configured, but never its value. Prefer booleans or symbolic credential names.

## Canonical source and deployment direction

The control repository copy of `multi-agent-coding-orchestrator` is the canonical tracked source. The copy under `~/.hermes/skills/` is deployed live state.

- `verify-state` compares the tracked and deployed skill version and content hash.
- Deployment is a documented manual copy or supported install operation.
- Do not use symlinks that make Hermes upgrades or profile isolation depend on the control repository path.

## Application and verification

Use documented Hermes CLI/configuration interfaces to apply desired state. Do not hand-maintain a fork or patch the Hermes source.

The executable `scripts/verify-state` must be read-only. It should compare live state with desired state and report, at minimum:

- missing or unexpected profiles;
- profile model/provider drift;
- plugin drift;
- dispatch-profile drift;
- concurrency-setting drift;
- missing shared skills or version mismatches;
- ladder-policy version mismatches;
- unexpected Hermes source modifications;
- repository-adapter adoption status.

Verification must not print secrets.

Generate sanitized inventory from an explicit field allowlist. Do not dump and redact complete configuration files. The collector must never read or serialize `.env`, `auth.json`, runtime databases, transcripts, private identifiers, or raw logs.

Verification exit behavior:

- Exit `0` when required desired state matches; non-blocking warnings may still be present.
- Exit nonzero for missing required profiles/plugins/skills, model or provider drift, dispatch or concurrency drift, behavior-changing unexpected state, malformed desired state, ladder-policy mismatch, or unexpected Hermes source modifications.
- Print only field names and expected/actual non-secret values.

Drift severity:

- Fail for unexpected profiles or plugins that are active, dispatchable, role-affecting, or otherwise behavior-changing.
- Warn for unrelated dormant extras.
- Never remove profiles, plugins, credentials, or configuration automatically.
- A failed check does not authorize deletion. Exact removal remains a separately reviewed manual action unless an approved execution specification explicitly names it and verifies recovery.

There is no executable apply script. `procedures/manual-apply.md` should provide exact supported Hermes CLI commands and checks. The manual procedure should be idempotent where practical and should:

1. capture or verify a recovery point;
2. display the proposed non-secret changes;
3. use supported Hermes commands and extension points;
4. verify the resulting live state;
5. leave an auditable Git commit in the control repository;
6. avoid changing credentials unless separately and explicitly authorized.

## Backup and rollback

Before significant harness changes:

- create a private Hermes state snapshot;
- record the current Hermes source commit/version;
- record a sanitized live-state inventory;
- commit the desired-state change separately from applying it;
- define the rollback target and procedure.

State snapshots must remain outside Git because they may contain credentials and private runtime data.

## Implementation sequence

1. Create the private control repository outside `~/.hermes` and the Hermes source checkout.
2. Initialize it locally at `~/hermes-local-harness`; do not create or push a remote. Structure it so a private remote can be added later through a separately approved external action.
3. Capture an allowlisted sanitized inventory of the current working harness.
4. Import the deployed shared orchestration skill as canonical controlled source and record its live version/hash.
5. Record the complete current live harness as the baseline desired state; do not replay the historical Terra/Luna-to-ladder migration.
6. Add decision records for the already-applied escalation ladder, revision policy, five-lane concurrency design, canonical-source direction, drift severity, and manual-apply boundary.
7. Add the read-only drift-verification script and tests or deterministic fixtures for its parsing and exit behavior.
8. Add the manual apply and rollback procedure using supported Hermes CLI/configuration interfaces.
9. Record Cha PT and Jobcron as active repository-adoption records while excluding retired GT control-plane state. Flag operational GT dependencies in the adapters.
10. Verify that the baseline manifest matches the current live setup and that no secret-bearing path was read into an artifact.
11. Run the verifier against a temporary altered fixture to prove it detects behavior-changing drift without mutating live state.
12. Commit the complete local control repository. Do not apply ladder changes because the tracked baseline is already live.

## Acceptance criteria

The tracking system is complete when:

- the harness's desired non-secret state can be understood from one private Git repository;
- live configuration can be checked for drift without exposing secrets;
- the shared policy has version history;
- every active profile has a declared role, model/provider, plugin set, and dispatch status;
- installed, dispatch-eligible, dispatch-pool, and lifecycle states are distinct;
- ladder and revision behavior have an explicit version;
- repository-specific requirements remain in their repositories;
- runtime task history remains in Kanban;
- rollback material exists outside Git;
- the Hermes source checkout remains clean and updateable;
- the read-only verifier returns success against the current live harness and fails against a deterministic behavior-changing drift fixture;
- the manual apply procedure can reconstruct the non-secret harness configuration using supported Hermes commands;
- a new machine or repaired installation could reconstruct the non-secret harness configuration from the control repository plus separately restored or freshly authorized credentials.

## Instruction to the orchestrator

Establish a private, version-controlled local harness control repository at `~/hermes-local-harness`, outside the Hermes source checkout. Import the already-working live ladder as baseline desired state rather than reapplying it. Record the complete profile roster, model/provider assignments, plugin requirements, dispatch eligibility and pool membership, five-lane concurrency design, versioned escalation and revision policy, canonical shared orchestration skill source, and repository-adoption pointers. Implement a read-only drift verifier and a manual apply procedure; do not create a mutating apply script or automatically remove unexpected state. Exclude credentials and runtime databases. Treat this repository as desired state, `~/.hermes` as live applied state, Kanban as execution history, and adopted project repositories as the source of repository-specific constraints. Treat GT control-plane operation as retired while preserving Cha PT and Jobcron repository adapters as active adoption records. Do not create or push a remote during this execution.
