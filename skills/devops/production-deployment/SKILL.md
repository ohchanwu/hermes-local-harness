---
name: production-deployment
description: "Use when planning or executing production deployments."
version: 0.2.2
author: Hermes Agent
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [deployment, production, terraform, rollback, human-assisted]
---

# Production Deployment

Plan and execute production launches from observed runtime state. Prefer the smallest supported architecture that meets the near-term load, but never trade away data recovery, secret isolation, exact-artifact identity, or explicit public-cutover approval.

## Diagnostic Convergence

Choose the smallest decision-changing probe, not a reusable product. Record the decision, one falsifiable hypothesis, minimum probe, risk tier, positive/negative/INDETERMINATE outcome-to-action map, and complexity budget. Reject likely-INDETERMINATE probes that do not change the next action; state both positive and negative evidence utility and coverage limitations.

Prefer trusted direct bounded read-only commands when safer/simpler than custom controllers, then a local synthetic repro, then a one-off bounded script. A sealed reusable controller requires written justification of decision value, reuse, and concrete threat; do not build generalized automation during incident diagnosis. Accepted platform/system tools define a proportional trust boundary: check identity, target, arguments, permissions, and output handling, not recursive OS/toolchain attestation absent a concrete threat.

Limit each hypothesis to two design generations across cards/models. Reassess the approach after the first material review correction; after a second material failure or exhausted budget, pivot strategy or abandon rather than refine by default. Accept one-time probes with representative positive/negative/indeterminate checks, required risk-based verification, and evidence selecting the next action; synthetic success is not live proof.

All external-read/write, credential, mutation, deployment, and cutover HUMAN GATEs remain unchanged. Read-only payloads can still require provider writes and owner approval. Bound external work at the actual risk boundary: exact actor, target, operation, effect, permissions, output custody, and retry behavior. A proven local pre-provider failure consumes no external-call units; a completed provider request, including an error or ambiguous response, is not a free retry. Disable uncontrolled automatic retries, pagination, and polling when practical, and stop an ambiguous provider response for reconciliation.

Do not create campaign-wide protected-read or credential-acquisition ceilings, reserved-slot arithmetic, or owner amendments whose only purpose is increasing an aggregate count. Acquire each credential or secret bundle once per execution session when practical, securely reuse it, and reacquire normally after provider expiry under the same identity and scope. Permit at most one retry after a proven pre-provider/no-submission failure; a request that may have reached the provider stops for reconciliation. Keep value-blind acquisition audit events, but use a per-operation request or poll cap only when a concrete provider cost, rate, mutation, or ambiguity risk justifies it.

## Procedure

### 1. Establish the operating mode and authority

Classify the run as unattended, human-assisted, or advisory before planning commands. In a human-assisted run, divide work explicitly: the operator handles interactive authentication, console-only inspection, sensitive values, and approvals; the agent validates repository state, plans, value-blind evidence, and ordered gates.

Treat repository push, infrastructure apply, credential change, image publication, EIP association, DNS/proxy change, and public traffic as separate external effects. A deployment plan or specification is not authorization to perform them.

### 2. Reconcile live state before choosing an architecture

Inspect the current repository, deployment artifact, infrastructure state, and live provider inventory before relying on a historical plan. Ask the operator for value-blind confirmations such as correct account/region, resource status, encryption, backup freshness, and unexpected ingress; never request secret values or paste private identifiers into shared output.

Stage recovered controller inputs into an owner-only scratch directory before use; never execute or edit recovery copies in place. Pull remote state into a mode-`0600` file, then compare state-managed resources, live resources, extra plausible candidates, and public DNS without printing selectors. Treat a per-resource not-found response as drift and continue the remaining read-only inventory. If multiple plausible hosts or databases remain, stop before starting anything or generating a plan. Use the detailed [live-state reconciliation](references/live-state-reconciliation.md) recipe.

When the operator is present, use console inspection to resolve sensitive discovery quickly, but keep the same stop conditions and read back the effective state after every mutation. Human presence reduces latency, not safety requirements.

Before starting a reconciled host or database, obtain bounded approval that names the exact logical targets and explicitly excludes EIP association, ingress, DNS, image publication, migration, and plan/apply. After each start request, wait for effective readiness and read back status, public-address assignment, ingress, DNS-target agreement, database protection, and management-agent health; a start request succeeding is not evidence that the resource is ready or still private.

Choose among existing supported deployment paths only after reconciliation. Do not invent a PaaS, local-database stack, or new network topology merely to meet a deadline. If no supported path satisfies the gates, declare no-go.

### 3. Invalidate stale plans after drift

Treat any out-of-band create, delete, stop, replacement, or network change as drift until proved otherwise. Discard saved plans and regenerate them after a fresh provider refresh; a lifecycle guard such as Terraform `prevent_destroy` cannot protect against console-side deletion.

Re-check prior authorization assumptions after drift. If an approved contract required preserving a resource that no longer exists, suspend that authority and obtain a new bounded approval for the replacement action. Never reinterpret an old plan or approval to cover a new resource identity.

Treat fresh-plan generation as its own gate when the backend uses a remote lockfile. Stage inputs and plan artifacts owner-only, obtain approval for the temporary lock write, save the exact binary plan plus JSON and log, compute its digest, and independently review the complete action set. Verify automatic lock cleanup value-blind against the exact lock object; do not use force-unlock or infer cleanup from a successful plan command. A forced replacement is not safe merely because it is expected: if it deletes a retained host, volume, or other rollback asset, require a preservation step or an explicit runbook-grounded determination that the target is disposable before requesting apply approval.

Freeze the binary plan and its source evidence once generated. If validation exposes a checker/provider representation mismatch, revise only the checker and synthetic fixtures under independent code review; hash the plan, image evidence, live observations, and reconstructed inputs before and after integrating the checker commit. Keep production configuration and release inputs byte-identical, then validate the unchanged plan with the approved controller. For private drift evidence, pass owner-only regular non-symlink files by path, enforce exact schemas and single-resource selection, bind non-computed values to independent live/state/input evidence, and keep committed fixtures synthetic and value-blind. Never normalize plan JSON merely to satisfy a predicate.

Treat a fail-fast semantic validator as an approval gate, not as a discovery tool. If bounded corrections expose successive provider/state shapes one at a time, stop patching and first implement an independently reviewed, offline structural inventory that reports the complete shape in one pass. Keep it diagnostic only: emit no scalar values, identifiers, policy payloads, reversible encodings, or value-derived fingerprints; bind the owner-only immutable output to the exact binary-plan digest and reviewed tool/code contracts; represent only closed-schema addresses/actions, key/type/presence structure, unknown/sensitive path shapes, coverage, and explicit cross-resource relationships. Require independent semantic evidence and human disposition for every unsupported shape; the inventory must never generate allowlists, weaken predicates, or turn a rejected plan into an approval.

Publish structural inventories atomically under owner-only custody and keep lifecycle approval separate from the extractor. A read-only consumer may trust an attended operator-selected register as the current non-rolled-back file, but must state that a stateless reader cannot detect replay of an older otherwise valid register without an independent monotonic trust root. Verify ownership, mode, schema, exact generation tuple, manifest digest, sequence consistency, and latest status; treat missing, retired, invalidated, mismatched, or ambiguous status as fail-closed. Lifecycle status never replaces fresh state reconciliation, semantic validation, independent plan review, or separate apply approval. Follow the [live-state reconciliation](references/live-state-reconciliation.md) plan-packet recipe.

### 4. Compress scope, not safeguards

For a small launch, use one host, one supported managed database, one scheduler, one immutable application artifact, and manual operations where practical. Defer high availability, autoscaling, orchestration platforms, generalized automation, broad observability, exhaustive failure injection, and cleanup unless they are required for correctness.

Keep these release gates:

- exact clean source revision and immutable artifact digest;
- green release CI, including stages that an earlier failure may have skipped;
- HTTPS and least-exposure networking;
- secrets outside source, images, logs, shell history, and infrastructure state;
- lower-privilege runtime database credentials;
- a pre-change snapshot or equivalent point-in-time recovery whenever useful data or schema exists; for a verified empty, unused first-deployment database, record that there is nothing to preserve and establish backup/PITR plus the first recovery point after accepted schema/data exists;
- off-host backup plus a successful disposable restore before public writes create valuable state;
- private functional acceptance before public traffic;
- explicit cutover approval and a written rollback path.

Do not invent campaign deadlines, latest-start cutoffs, authorization expiry, full-path timing admission tests, or aggregate session/CI elapsed-time caps merely to make the deployment feel bounded. Approved scope remains valid until its effects complete, the owner revokes it, relevant state changes invalidate it, or a real external constraint requires renewal. A target date expresses priority unless the owner explicitly makes it a deadline.

Preserve technically meaningful timing controls: provider-issued credential expiry, externally imposed maintenance windows, network and subprocess timeouts, hung-process watchdogs, retry backoff, cleanup deadlines, and minimum stability-observation periods. State whether each duration is an external fact, a maximum local safety bound, or a minimum acceptance requirement. Do not promote those durations into campaign authority or require the entire worst-case serial path to fit a guessed wall-clock envelope before starting an otherwise safe operation.

### 5. Execute one concise attended runbook

Keep the active deployment specification concise and human-readable. Put only current assumptions, ownership, gates, ordered phases, approval boundaries, rollback, and deferred scope in it; archive superseded multi-stage ceremony rather than copying it forward.

When replacing a deployment documentation set:

- move superseded specifications, plans, and obsolete authorization decisions with history-preserving renames into one dated archive workstream;
- add one archive index explaining why the operating model changed and naming the new controlling specification;
- keep detailed runtime guides as technical references when code or tests depend on them, but add a prominent pointer stating that the concise active specification controls the attended run;
- repair inline links, reference-style link definitions, documentation indexes, and tests that hard-code old paths; and
- run both a Markdown destination check and the focused tests that consume the moved documentation before broader repository gates.

Run in this order:

1. Authenticate and reconcile live state.
2. Start or recover required resources and wait for effective readiness.
3. Fix and verify the exact release candidate.
4. Generate and independently review fresh plans.
5. Apply private infrastructure only after its bounded approval.
6. Run migrations or a bounded import only after a pre-change recovery point.
7. Complete private application and data acceptance.
8. Create, download, verify, and restore one recovery artifact.
9. Present the cutover packet and obtain explicit approval.
10. Change public routing, run public acceptance, observe, and freeze further changes.

When interactive cloud authentication is unavailable, continue only with deterministic local and hosted-CI release-readiness work that does not depend on live state. Do not infer provider state or generate a fresh plan until authentication and reconciliation are complete.

### 6. Preserve data-safe rollback

Before public writes, rollback may restore the pre-change database recovery point and previous routing. After the new database accepts writes, keep it authoritative: roll back to a schema-compatible application artifact, not to a stale writable database or file store.

Record the effective pre-cutover routing state and the new resource identities after drift. Do not claim that reassociation or DNS restoration is available until the exact target and command have been validated. Keep prior hosts, databases, images, keys, snapshots, and recovery material through the stabilization window; cleanup requires separate approval.

## Pitfalls

- Regenerate plans after console changes — saved plans encode an older world and can no longer prove the intended action set.
- Inspect workflow step ordering when CI fails early — downstream integration, race, or build gates may be skipped even when local smoke tests pass.
- Reproduce release-contract scripts with the hosted runner's exact command line and explicit shell, then match its OS and tool major versions before calling a local pass portable — an explicit `sh script` overrides a Bash shebang, while macOS and newer `awk`/`jq` behavior can accept syntax or mutation helpers that fail on Linux CI. Use the recipes in [release CI portability](references/release-ci-portability.md).
- Audit workflow authentication as executable code, not rendered logs — reference the scoped token variable in request headers and make mutation tests reject both the wrong token source and the wrong number of pre/post publication checks, because redaction placeholders can otherwise become literal credentials.
- Verify the origin path as one contract: container target, host bind, firewall/security-group port, proxy source restriction, and EIP/DNS attachment must agree. Distinguish an all-interface listener from external reachability, because a socket alone neither proves exposure nor satisfies an ingress rule on a different port.
- Verify backup restoration, not only backup creation — an unreadable dump provides no recovery boundary.
- Keep one scheduler active — parallel application instances can duplicate scheduled work even at low user count.
- Separate private deployment from public cutover — a healthy private runtime does not authorize routing users to it.
- Never use operator availability as implicit approval — ask at the named mutation boundary and record the decision.
- Keep approved remote diagnostics value-blind and tolerant of expected inactive states — `set -e`, unguarded `systemctl is-active`, or incorrectly quoted `awk` field references can turn a healthy diagnostic into a failed command before the remaining evidence is collected.
- Require plan gates to consume truthful current reconciliation evidence — combining a freshness limit with an obsolete phase invariant such as “zero secret versions” makes safe recovery impossible and pressures operators toward stale or false checkpoints.
- Add a distinct fail-closed validator mode when live drift creates a new legitimate action combination — weakening an existing mode or bypassing the checker hides extra creates, associations, imports, moves, or replacements.
- Treat `resource_drift` separately from planned actions, but never ignore it wholesale — admit only named resource/attribute shapes, bind addresses, identities, policy relationships, and timestamps to independent owner-only evidence, allow null-to-empty normalization only when semantically equivalent, and reject any coupled unapproved action.
- Scope preserved observations to the frozen plan they preceded — historical evidence may prove that plan’s review packet, but require attended freshness reconciliation before a later apply rather than silently treating old observations as current.
- Check reference-style Markdown definitions as well as inline links after archival moves — a file can render with a silently broken destination even when a simple inline-link scan passes.
- Do not leave a detailed legacy guide looking authoritative — retain it as a technical reference only when needed, and point its first screen to the concise controlling specification.
- Keep credential/private-metadata helpers owner-only at mode `0600`; execute reviewed shell helpers with an explicit trusted interpreter such as `/bin/bash path/to/helper.sh` rather than adding the executable bit or using `sudo`. Privilege escalation changes ownership and credential context, while mode `0600` intentionally prevents direct execution.

## Verification

Before reporting completion, verify the exact artifact, live runtime identity, database target and privilege level, effective ingress, HTTPS, core user journey, persistence across restart or recreation, backup restoration, public routing, and rollback readiness. Report any unexecuted gate or unverifiable live state as incomplete rather than inferring success from configuration.
