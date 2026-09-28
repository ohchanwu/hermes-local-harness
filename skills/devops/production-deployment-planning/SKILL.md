---
name: production-deployment-planning
description: "Use when planning first or replacement production launches."
version: 0.1.7
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [deployment, production, terraform, rollback, planning]
    related_skills: [autonomous-workflow-gates, multi-agent-coding-orchestrator]
---

# Production Deployment Planning

Plan production changes from the deployment's actual lifecycle state. Distinguish an initial launch from an upgrade, replacement, or recovery before creating selectors, provenance requirements, rollback hosts, migration gates, or implementation tasks.

## Procedure

1. **Classify the lifecycle before writing the plan.** Ask, in one short decision round:
   - Has this application ever served production traffic?
   - Does any current host run a working application version?
   - Does any current database or host contain production data that must survive?
   - Is an existing resource a real rollback target or merely disposable bootstrap infrastructure?
   - If validation fails, should rollback restore a working prior service or simply stop before public cutover?

   Do this before dispatching workers or building evidence helpers. A resource's existence does not prove it is a prior production deployment.

2. **Derive evidence from those facts.** Require legacy-host provenance, previous-image lineage, import/migration evidence, pre-change snapshots, and old-service preservation only when a corresponding real asset exists. Never fabricate, infer, or ask the operator to hand-author provenance to satisfy a checker whose premise is false.

   Treat duplicate provenance signals proportionally. When an exact reviewed commit, green CI, publication workflow input and head SHA, immutable tag, and registry digest form a verified chain, do not force another release solely to add an embedded revision label. Never claim a missing label exists; require it only when the runtime or an explicit non-duplicative contract consumes it.

3. **Use a lean initial-deployment path when there is no prior service or production data.** Keep these gates:
   - exact clean release, green CI, and immutable private image;
   - owner-only evidence, secret hygiene, remote-state/live-resource reconciliation, and a locked encrypted backend;
   - a fresh saved binary plan, machine-readable plan/cost evidence, exact digest, and independent review;
   - explicit apply approval;
   - private functional, persistence, networking, and single-scheduler acceptance;
   - one verified off-host database backup and disposable restore after accepted schema/data exists and before public writes;
   - a separate attended public-cutover approval.

   Mark prior-production import, prior-image migration equality, old-host retention, snapshots of an empty unused database, and generalized recovery-object/log matrices as N/A or deferred. If private validation fails, stop before cutover; do not pretend there is an old service to restore.

4. **Make the plan validator express the truthful mode.** Add an explicit initial-deployment mode rather than bypassing a replacement checker. Permit only the exact intended bootstrap disposition and reconciled prerequisites. Reject unrelated drift, unexplained destruction or replacement, database replacement, broad/public ingress, EIP/DNS/Cloudflare/public routing changes, and secret-bearing outputs or shared evidence.

5. **Keep replacement and recovery paths separate.** When a working prior service or valuable data exists, preserve it until successor acceptance, bind targets from authoritative state, validate rollback mechanics, and require provenance for destructive transitions. Do not weaken those paths merely because the initial-deployment path is leaner.

6. **Audit for over-conservative inherited gates before execution.** Search the active spec and runbook for assumptions about `legacy`, `previous`, `replacement`, `recovery`, `snapshot`, `migration`, `import`, and `rollback`. Present disproportionate gates to the user early, with the risk retained by removing each one. Prefer one grouped decision over serial interruptions.

7. **Separate task acceptance from downstream release operations.** A code-change card should end at committed implementation, local verification, and independent review. Put integration, remote push, image publication, authenticated evidence generation, saved-plan production, apply, and cutover in downstream gates or cards. Do not make a goal-mode worker's completion depend on actions that the same card prohibits or assigns to the orchestrator; that creates a circular review/completion gate.

   Use goal mode only when one lifecycle can satisfy the whole card without interim helper review, attended authentication, or human approval. For a multi-gate controller workflow, use phase dependencies or a non-goal long-lived card so a helper-only review can close without pretending the plan is complete. For an explicitly authorized unattended preparation run, commit the approved plan first, then create the independent preflight review and its execution card as a parent-gated pair: the execution card may auto-promote only after exact-candidate approval, and its acceptance criteria must stop before every external-write gate. Read both cards back, require a real reviewer claim before reporting the run active, and never mistake the queued child for started work. After any automated specification pass, read the body back and reconcile pinned SHA/worktree/mode fields before dispatch; comments do not reliably neutralize stale identifiers that remain in the primary body.

   When a goal judge converts an otherwise successful review into `HUMAN_BLOCK` solely because prohibited downstream work remains, inspect the exact reviewer run rather than trusting the lane label. Accept it only when the reviewer explicitly records substantive approval, no actionable findings, the exact candidate/baseline, and passing required gates; write an orchestrator disposition, integrate that exact candidate locally, and continue on the existing downstream card. Do not rerun the review or create a duplicate task to escape the transition. If the reviewer names any substantive finding or leaves the verdict ambiguous, preserve the block and seek the required disposition.

8. **Roll release-bound private evidence forward without mixing generations.** Preserve the prior controller tree in an owner-only archive, verify its path/type/hash inventory without printing private values, and start the active root without stale image, selector, checkpoint, or plan artifacts. Move the checkout to the exact new release only after the archive comparison passes. Keep helper deltas minimal, rerun fail-closed fixtures and stale-release rejection, and obtain fresh independent review before the first authenticated execution against the new release.

9. **Assign remote-lock planning to an actor allowed to write the lock.** Detect `use_lockfile=true` before dispatch and classify the transient backend lock `PutObject`/`DeleteObject` as an external write. A card comment cannot override a profile-wide no-external-writes contract. Route only the locked `terraform plan` invocation to the already authorized operator/control-plane actor, capture stdout/stderr and the saved binary owner-only, verify the exact lock object is absent afterward, and return the unchanged plan to workers for read-only JSON, cost, secret, action, digest, and review gates. Never retry the prohibited worker action, disable locking, substitute a copied/local state, or broaden this authority to apply/state/resource mutations.

10. **Freeze the binary plan while repairing validators.** When a real saved plan exposes a provider-version representation mismatch, preserve and hash the binary plan and private inputs before changing code. Reproduce the rejection with a value-blind predicate, correct only the checker/interface and synthetic mutation fixtures, require independent review of that exact correction, then advance the private planning checkout to the reviewed checker commit. Recompute the private artifact hashes and require equality before rerunning `terraform show -json`, cost, secret, action, and digest gates. Regenerating derived JSON is read-only; regenerating the binary plan is a new planning event and invalidates the prior digest review.

   Exercise each reviewed checker candidate against the exact frozen real plan and its complete preserved evidence bundle before treating the correction as converged or consuming the final ordinary revision allowance. Synthetic fixtures are necessary for fail-closed mutation coverage but cannot establish compatibility with every provider-emitted unknown mask, omitted field, collection shape, refresh-only record, or sensitivity annotation. Keep this integration run value-blind: report predicates, counts, digests, and pass/fail stages, never private values.

   Treat Terraform sensitivity paths as provenance metadata, not automatic proof that a known-public value is secret. Never strip or rewrite state to make a validator pass. When a provider marks a public lookup sensitive, admit only the exact canonical path after independently binding the source identity, public parameter contract, type, syntax, and value to the reviewed input; reject empty, missing, wildcard, indexed, additional, or differently targeted paths and retain the normal secret scan.

   Stop predicate-by-predicate patching when the same frozen plan exposes multiple sequential provider/state shapes that synthetic fixtures missed. Preserve the plan and evidence, then design a one-pass owner-only structural manifest before authorizing more checker code. Bind the manifest to the exact binary-plan digest and reviewed checker commit; include only resource addresses/actions, key/type/presence structure, unknown/sensitive path shapes, and explicit cross-resource relationship descriptors. Exclude values, identifiers, policy payloads, credentials, reversible encodings, and value hashes. Generate it deterministically and atomically under owner-only permissions, produce a human-readable value-blind structural diff, and require independent review of the complete shape plus separate authoritative evidence for semantic values. A plan-derived manifest inventories compatibility; it must never approve its own semantics. Invalidate it when the binary plan, checker contract, provider schema, or accepted evidence generation changes.

   Separate immutable structural generations from mutable lifecycle status. The extractor must never activate, approve, retire, or invalidate its own output. Use a closed owner-only register whose events bind the exact plan/manifest digests and reviewed code/tool tuple; an independently reviewed operator writer records lifecycle decisions, while consumers only read and require the latest exact matching status. Treat the attended operator-selected register as the current non-rolled-back custody input unless an independent monotonic trust root is explicitly designed. A stateless reader can reject substitution and retired manifests against the current register, but it must label historical register rollback as outside its guarantee rather than claiming anti-replay it cannot prove.

   Stage this redesign in separate gates: independently review the value-blind design; implement and test only with synthetic saved binaries and leakage canaries; independently review the implementation; only then obtain explicit private-read authorization for one owner-only run against the frozen plan. The structural inventory remains diagnostic throughout and cannot weaken the canonical semantic checker or replace freshness, plan review, apply approval, or cutover approval.

   For that private run, create a closed binding file and a new no-clobber generation beneath a `0700` controller directory; require regular non-symlink `0600` inputs/outputs and safe parents. Decode only with the reviewed offline Terraform/provider tuple, a cleared child environment, and network denial. Verify deterministic disposable regeneration, exact source/evidence pre/post hashes, closed-schema and prohibited-content scans, traversal conservation, and the complete accumulated unsupported-shape set. Report only fixed status tokens and value-blind counts; never print the manifest, plan JSON, digests, identifiers, policies, user-data, or provider output. Generation must end as `inventory_complete_unreviewed` and must not create or update lifecycle status.

   Route a separate private diagnostic review bound to the exact manifest and plan digests. The reviewer may inspect only the authorized generation/binding/verification material needed to verify integrity, privacy, determinism, and completeness; classify the whole unsupported set before proposing semantic changes. Approval at this gate approves only the diagnostic artifact, not the plan. Keep the canonical failure intact, and do not invoke the lifecycle writer until the diagnostic review and a separate human disposition authorize it.

11. **Validate refresh drift independently from planned actions.** Inventory `resource_changes` and `resource_drift` separately: provider refresh metadata is not an apply action, but it must not receive a generic waiver. Admit only named resource/attribute shapes, prove they introduce no extra planned action, and bind non-computed values to owner-only reconciliation evidence rather than comparing the plan to itself. If the checker lacks that evidence, extend its interface with required regular, non-symlink, owner-only file inputs; validate exact cardinality, types, identities, and value matches without printing them. Use synthetic values in committed fixtures and test missing, ambiguous, malformed, mismatched, extra-attribute, secret-bearing, and action-coupled cases. Record whether preserved observations are accepted only for the frozen plan and require attended freshness revalidation before a later apply.

   Treat absence as a scoped claim, not as a self-explanatory empty array. For API-derived absence evidence, preserve or durably record the successful operation, account and region context, exact selector or collection scope, observation time, and the response field that binds the state identity. Distinguish an empty successful collection from `NotFound`, denied, malformed, partial, or unscoped output; fail closed when query provenance is missing. The checker should compare the state-bound identifier against the authoritative response collection, reject duplicate or conflicting matches, and accept absence only when the recorded query scope proves that the missing match is meaningful.

12. **Treat public frontend extraction as a trust-boundary migration, not a hosting switch.** Before separating a static frontend from an application server, inventory every request-time behavior the server currently applies to page requests: routing and method semantics, redirects and errors, cookies and analytics, bot filtering, security headers, cache rewriting, forms, and rollback. Use a separate repository when source access must be separated; a monorepo build root limits deployment scope but not collaborator access. Preserve the public contract with a method-aware route fixture, keep complete reserved namespaces on the backend, make previews and direct hosting origins inert, and define one cache/rollback rule. See [frontend origin separation](references/frontend-origin-separation.md) for the reusable design and verification recipe.

13. **Separate authentication availability from evidence validity.** If authentication expires or an attended login is unavailable, preserve the last verified result with its scope. Authentication expiry blocks fresh observation; it does not invalidate prior evidence or create an immediate operator task. Mark any freshness refresh as deferred, then reobserve only the affected surface after a relevant observed mutation or immediately before the next authorized mutation that materially depends on it. If completed, blocked, and still-valid checks leave no useful action, say so directly instead of manufacturing precautionary work. Reauthentication authorizes observation, not mutation.

   Treat CLI tokens, cloud-console sessions, and provider web sessions as independent authentication channels. Before declaring a gate blocked, identify which channel the exact operation requires and whether the operator already has an authenticated session there; an expired CLI token does not prove that a repository-app installation or console-only gate is unavailable. Conversely, an authenticated browser session neither refreshes CLI evidence nor authorizes a mutation—retain the gate and read back the exact external target after any separately approved write.

14. **Design temporary bootstrap IAM from the exact attended operations.** Start with a read-only inventory identity, then draft a separate temporary write grant for the smallest provisioning phase. Verify each action's supported resource type and condition keys against the current provider authorization reference, split statements whenever action resource support differs, and map every retained write action to one named operator step. Approval of the document is not approval to attach it, and attachment is not approval to provision. Define cleanup for the actual policy form (inline versus customer-managed) before the gate opens. See [temporary cloud bootstrap IAM](references/temporary-cloud-bootstrap-iam.md) for the statement-partitioning and gate recipe.

15. **Verify Amplify GitHub App installation independently from the AWS callback.** A regional Amplify GitHub App can remain successfully installed after its return to AWS fails because the AWS console session requires reauthentication or MFA. Read the organization’s installed-app configuration directly and require the exact region-specific app, organization, `Only select repositories` mode, and intended repository set. Record the installation as operator-attested until API or console readback is available; do not retry installation, broaden repository access, or claim that an Amplify app was created merely from the callback result.

## Documentation Gate

Before implementing a durable operational record, read the nearest documentation instructions plus both the documentation index and root agent instructions, then inventory every required discovery pointer. Schedule protected root-instruction edits before final review: a substantively correct implementation can still be blocked when its durable record is indexed in `docs/README.md` but the repository also requires a root `AGENTS.md` pointer. Never waive or bypass a protected-file gate implicitly. When the runtime requires an interactive approval, preserve the reviewed candidate, resume the exact foreground session for the narrow edit, rerun documentation/diff/secret checks, and return the same card to its reviewer.

## Reporting

Report milestones, not routine heartbeats. State which lifecycle model controls, which inherited gates were removed or retained, the exact current blocker, and the furthest safe unattended point. Never describe a routed task as active until a real claim/run exists.

## Pitfalls

- Establish whether a legacy deployment exists before designing a legacy selector, because a conservative helper cannot repair a false premise.
- Treat a bootstrap host with no application or production data as infrastructure, not as a rollback service.
- Preserve safety boundaries while removing ceremony: plan review, secret handling, apply approval, private acceptance, backup restore, and cutover approval are not schedule optimizations.
- Keep review acceptance local to the artifact under review, because bundling remote publication and production evidence into the same goal makes independent review impossible to close cleanly.
