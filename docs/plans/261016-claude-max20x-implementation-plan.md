# Claude Max 20x inside Hermes — executable implementation plan

Date: 2026-10-16 KST.
Status: plan authored; execution unexecuted/unapproved.
Source: [approved native-first specification](../specs/261016-claude-max20x-model-portability.md), exact path `docs/specs/261016-claude-max20x-model-portability.md`.
Inspected baseline: `09a8355c6d6d68d46df26c685b73a4a4b810cf24`.
Provenance: `kanban://harness/t_83714ad6#body`; source approval `t_e7f80baf`, review run 26.
Source SHA256: `c0a5b7b752ac056e189c73149caec6d7b43e7c87245571c4e6db3c2d5ca9cf5a`.

## Scope, authority and inspected starting point

Goal: Claude inside Hermes, retaining its tools, roles and native task/review lifecycle, using only the included Max 20x pool. Purchase is USER-REPORTED PURCHASED; account entitlement, exact Claude Opus 5.5 availability/model slug and allowed route are UNVERIFIED. Never substitute an `opus` alias, self-report or another model for that exact requested label. No extra usage, overage, API-credit consumption, paid/cloud fallback or cancelled-provider spend. Preserve OpenAI and Zai contracts for explicit selection, never automatic Claude-only fallback.

The original October 18, 2026 KST target remains a target, not readiness, authorization or a new countdown. This card authorizes only this plan, one index line, offline doc checks, local commit, same-card independent review and exact approved local integration. It authorizes no account/credential access, inference, adapter/spike, config/policy deployment, runtime update, push or PR. No future cards or live task graph are created here.

Inspected tracked Harness surfaces (desired state, not live observations):

| Surface | Finding / future affected boundary |
| --- | --- |
| `roster.yaml`, Harness entries only | Orchestrator/primary worker select `openai-codex/gpt-6.1-sol`; GLM workers select `zai/glm-5.3`; reviewer selects `openai-codex/gpt-6-astra`. Selection changes must not rewrite role authority. |
| `policies/profile-souls/harness-{orchestrator,worker,worker-glm-1,reviewer}/SOUL.md`; Harness orchestrator `policies/profile-skills/harness-orchestrator/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` | Named implementation pool and sole `harness-reviewer`; protected worktrees, same-card review and history survive model changes. Model-branded prose is not an effective-selection oracle. |
| `scripts/run-harness-orchestrator` | Pins board `harness` and repository root before controller startup; retain pins. |
| `scripts/verify-state`, especially `check_harness_card_contract` and fixture `profile_models`/`profile_providers` comparisons | Existing verifier checks desired/observed selections and boundaries, not served model or subscription billing. Do not run it in this documentation task. |
| `README.md`, `procedures/manual-apply.md` §§2, 8b, `policies/authority-and-review.md` | Repository integration, manual per-target apply and independent review are distinct. Own active live policy is not autonomously deployable. |
| `plugins/hermes-terminal-outcome-notification/README.md` and tracked plugin inventory | Only terminal notification plugin source exists here; no existing Claude provider plugin. Notification/session evidence is not model delivery evidence. |

Upstream interface facts are dated claims from source spec S1–S5, not installed-source discoveries: native `claude-code` aliases Anthropic HTTP at pinned upstream revision; `ProviderProfile.create_client`/`external_process` and Copilot ACP are extension precedents. `create_client` exceptions may fall back to HTTP. Current supported interfaces, installed provenance, auth-resolution and helper overrides remain future authorized discovery. Do not browse network or installed Hermes source under this card.

## Execution slices and common evidence contract

Future sequential slices: M0/M1 native experiment under explicit bounded authority; native M4 if sufficient; otherwise justified M2 feasibility, then separately authorized M3 implementation; measured M4; attended M5. Keep each slice's billing/permission/tool acceptance together rather than split away its safeguards. Ordinary harmless fixture preparation, inspection and checks within an approved slice need no repeated approval. Authentication, account observation/inference, feasibility, implementation/integration and attended installation/external rollback are distinct authorization boundaries, not implied by planning or a previous gate.

When authorized, each future implementation card records one exact current protected baseline/ref, repository-owned isolated worktree/branch, assigned Harness worker, independent `harness-reviewer`, allowlist and executable focused/broader test contract. Reinspect drift; never inherit this document's baseline blindly. Controller routes and integrates; worker implements; reviewer does not author. Keep real same-card attempts, rejected candidates, review runs, infrastructure retries and applicable retry limits; changing model/card/branch does not reset them. This card has no bounded-convergence repair-history opt-in.

Use one sanitized gate record per stage, not another documentation campaign: candidate SHA/tree, applicable runtime versions/provenance, frozen fixture/oracle identities, verified interface/command and exit, timestamp/timezone, requested/effective/served selection, routes, tool audit, measured usage limitations, stop reason and review disposition. Mark each item observed, user-attested, documentation-derived, simulated, reused or unexecuted. Reused evidence names exact original candidate/version/fixture and why its assumptions remain unchanged. Store no credentials even in ignored evidence. Publish only conclusions/non-secret metadata after full staged review plus scanner; no account IDs, emails, raw logs/transcripts, billing screenshots, application data or unnecessary machine details.

## M0 — freeze permission, safeguards and experiment

Owners: controller + account owner for authority/attestations; assigned worker for scoped technical discovery; independent reviewer for gate completeness. Prerequisite: separate explicit authorization for the intended reads, attended authentication and bounded experiment; no inference yet.

1. Refresh applicable official Hermes provider/plugin docs and Anthropic account/terms contracts (spec S1–S8); record dated source/version provenance. Official docs are authoritative. Resolve personal/local intended-use eligibility independently of SDK availability. Unresolved/disallowed permission stops without inference.
2. Verify supported model-selection, route diagnostics, limits, usage observation and official attended auth interfaces before writing exact live commands. No invented auth/usage/dry-run/sandbox flags. Official unmodified Claude runtime owns sign-in; do not collect/replay subscription tokens or copy them into Hermes. Any native flow must itself be permitted.
3. In authorized isolated Harness scope, inspect actual auth resolution and non-secret route/presence facts: credential pools, Keychain access paths, ambient API/cloud credentials, inherited environment, aliases, fallback chains and helper overrides. No secret values/dumps. An empty shell environment is not isolation. Use supported isolation; if unavailable, stop the main experiment.
4. Account owner establishes and attests no enabled extra/overage route, no auto-top-up and no accessible purchased/API-credit/cloud fallback before inference. Do not autonomously change billing settings. Empty key variables, estimates and no observed charge do not establish safeguards. A known extra-usage-only native route can establish pre-inference NATIVE_FAILURE without making a request.
5. Freeze synthetic fixture bytes `HARNESS_READ_OK\n`, expected exact read result, representative system/task instructions and read-only tool allowlist in the owned test worktree. Freeze route/model oracles and supported time/output limits with exact values before any request. Exclude application/production data and all unrelated tools.
6. Budget: one tiny official Claude Code control; one stock Hermes workflow with one initial model request, one actual read-tool execution and one tool-result continuation. Verify suppression of automatic retries/hidden auxiliary calls and alternate routes; otherwise stop. No reruns, quota exhaustion, account rotation or budget resets. Additional M4 coverage needs its own frozen approved budget.

Artifact / proposed verification interface V0: preflight record with resolved eligibility, exact supported commands/interfaces and request/time/output caps, owner safeguard attestation, fixture/oracles and excluded routes. Success means safe to attempt the comparison, NOT proven native included-pool attribution. Stop on any missing prerequisite; record safe unrun status and dependency. Only complete V0 releases M1.

Concrete unknown-billing case: suppose refreshed authoritative contracts permit this native use, the owner has excluded every chargeable route, isolated routing is verified and exact-model selection/metadata interfaces are supported, but native included-pool consumption is unknown. That unknown is the experiment's question, not an extra prerequisite: permit the frozen control then Hermes comparison under V0. If current extra-usage-only constraint remains incompatible, or permission/safeguards cannot be established, stop before either request instead. Neither case licenses an adapter to evade the gate.

## M1 — native comparison and decision

Owners: account owner records usage windows; assigned worker runs only V0's approved commands; controller/reviewer classify evidence. Prerequisite: V0 passes, including permission and no-charge/fallback safeguards.

1. Pause other account activity across devices/sessions. Record sanitized before/after included and extra/balance observations for the control, timestamps/timezone, resolution, documented settling lag and concurrency limitations. Run the one small official unmodified Claude Code control with the verified requested model; require trustworthy runtime/provider served-model and route metadata. Observe settled results before continuing; if permitted subscription control cannot be established, stop.
2. Give the native Hermes workflow its own independent before/after billing window after control settling. Require structured read request, actual Hermes-authorized read, matched tool ID/arguments/result and continuation using the exact fixture bytes. Record tool execution/audit/exit, effective provider/auth route and served model for initial AND continuation. Textual tool mentions, canned transcripts and model self-description fail the oracle. Control success is not Hermes proof.
3. Compare included and extra observations only after verified settling interval; account for rounding, lag and concurrent activity separately per window. Unknown included consumption is not zero/free; no extra charge movement alone is insufficient. If attribution cannot distinguish this tiny trial, stop as inconclusive, not more probes. Never fabricate receipts or retain raw billing screenshots.

Artifact / proposed V1: bounded native comparison record and tool audit. Stop immediately on user request, quota refusal, unexpected route, disallowed-spend signal or scope breach; no retry or paid fallback. Record pre-inference failures honestly as unrun, not failed inference. Apply these outcomes:

| Classification | Evidence and next dependency |
| --- | --- |
| NATIVE_SUCCESS | Allowed included-pool billing, exact model, real tools and every required role/helper path verified. Stop adapter work; readiness review then M5. M1 main-path pass alone instead releases native M4, not this full classification. |
| NATIVE_FAILURE | Established permission/billing incompatibility, refusal, unavailable exact model or incompatible tools. Stop requests, preserve reason; M2 only for a specifically addressable unmet requirement within permitted terms/safeguards, never to invent missing model entitlement. |
| NATIVE_INCONCLUSIVE | Model/route/billing attribution unknown or required roles/helpers incomplete. No readiness. Complete native M4 for main-path-pass/missing-coverage case; resolve other uncertainty only within separately approved bounded scope or stop. Uncertainty alone cannot bypass eligibility/billing into M2. |

## M2 — conditional feasibility, not adapter commitment

Owners: controller states unmet requirement; account owner/authoritative contract source resolves eligibility; worker investigates documented extension; reviewer accepts/rejects feasibility. Prerequisites: M1 assessment, addressable requirement, resolved allowed intended use and separate feasibility authority. Native main-path success with missing helper coverage goes to native M4 first, not here.

1. Resolve terms for proposed personal/local use of unmodified official runtime. SDK installation is not consumer-login permission; reconcile spec S6/S7 against actual intended use. Stop for authoritative clarification if unresolved. No spoofing, token replay, modified binary, Hermes core/installed-source patch or monkey patch.
2. Discover exact supported provider registration/client/process interfaces from authoritative versions in authorized scope; record source locations and signatures versus proposals. Choose a distinct repository-owned plugin name (TBD here), never replace `anthropic` or hijack native `claude-code`. Do not assume Copilot ACP precedent establishes Claude compatibility.
3. Prove structured mediation can leave Hermes the sole tool executor/permission authority, while disabling independent subprocess filesystem/shell execution through supported controls. Preserve system/user/assistant semantics, call IDs/results, streaming/completion/error boundaries and continuation. A second wider-authority Claude agent or shell-wrapper transcript is not equivalent; reject if unavoidable.
4. Establish fail-closed client construction, startup/runtime/quota and auxiliary routes despite `create_client` exception-to-HTTP fallback. Raising an exception alone is unsafe. Use proposed route spies and a fake subprocess before any eligible separately budgeted live trial. Reject if supported extensions/configuration cannot prevent fallback without core changes.

Artifact / proposed V2: concise accepted/rejected feasibility record, exact interface/version findings, structured tool/lifecycle proof and source/test map. Expected outcome: all required controls feasible, or explicit rejection; no expansion to bypass controls. Only accepted V2 plus separate implementation authority releases M3. An infeasible result ends this architecture.

Proposed minimal surface map, NOT existing files or approved changes (plain code paths intentionally are not links):

| Proposed surface | Bounded responsibility |
| --- | --- |
| `plugins/<distinct-name-TBD>/plugin.yaml`, `__init__.py`, `client.py` | Supported registration/version metadata; client translation, owned process lifecycle and scoped state. Confirm layout in M2; no native alias takeover. |
| `tests/test_claude_subscription_provider.py` | Offline fake-runtime, route-spy, tool/protocol and lifecycle contract cases; no credentials/network. |
| `tests/test_model_selection_portability.py` | Harness-only explicit-selection, role/pin/history and OpenAI/Zai regression using fixtures. |
| `tests/fixtures/claude-subscription-protocol.json` | Synthetic message/tool/error/stream events, malformed cases and exact expected output/order. |
| `tests/test_claude_version_contract.py` | Supported-interface fixtures, exact tested version pairs and incompatible-version negative control. |

## M3 — conditional red/green implementation and reviewed local integration

Owners: assigned worker implements; `harness-reviewer` independently reviews exact candidate; controller integrates. Prerequisites: accepted V2, separate implementation authorization and a fresh exact card contract. No live account calls implied.

1. Author deterministic failing tests for the approved mechanisms first. Red must expose the missing behavior (not merely missing imports), including a deliberately unsafe constructor fallback that route spies catch. Assert zero alternate HTTP/OpenAI/Zai attempts in Claude-only mode, including `create_client` exception, startup failure, runtime failure and simulated quota refusal.
2. Cover system/messages, tool names/IDs/arguments and matched results, malformed/duplicate IDs, malformed arguments, supported parallel ordering, stream partial/final/error ordering and completion reasons. Invalid events never execute invented tools; actual Hermes executor continuation remains a separate live M4 requirement.
3. Cover cancel at startup/streaming, startup races, timeout/process death and idempotent cleanup: no orphan, duplicate request/tool, late callback or stale resume. Test profile/role/task/session/worktree separation and continuation; the same model must never share private reviewer state or attach old state to a new task.
4. Implement only enough supported plugin/translation/lifecycle code to make these mechanism oracles green. Run the portability/version checks below as the bounded broader contract, not unrelated campaigns. Reject unsafe interfaces rather than patch core. No retry-budget resets or provider switching on errors.

Proposed exact OFFLINE test commands V3–V5; unshipped/unexecuted, usable only AFTER M2 fixes layout/interfaces and M3 creates these stdlib-unittest-compatible tests. A future authorized card must freeze/confirm the commands and explicit network-denying fake transports before execution:

```sh
# V3 — provider mechanism red/green; depends on accepted V2 and synthetic fixtures
python3 -m unittest discover -s tests -p 'test_claude_subscription_provider.py'
# V4 — explicit-selection/identity regression; depends on Harness-only selection fixtures
python3 -m unittest discover -s tests -p 'test_model_selection_portability.py'
# V5 — supported-version contracts plus incompatibility negative control
python3 -m unittest discover -s tests -p 'test_claude_version_contract.py'
```

Artifacts: source/tests/fixtures, red and green outputs with mechanism-specific assertions, route attempts, cleanup evidence, candidate SHA/tree and publication-reviewed diff. Mocks establish mechanisms only, not billing/model readiness. Stop on failed oracle, unsafe fallback or scope expansion. Independent same-card approval of exact SHA/tree and no-drift checks precede controller local integration; repository presence is not installation. Reviewed candidate releases separately authorized M4, never an automatic deployment.

## M4 — actual roles, helpers, tool audit and readiness

Owners: controller inventories; account owner supplies authorized billing observations; named workers and independent reviewer execute their distinct roles. Prerequisites: native M1 main-path pass OR reviewed M3, plus separate bounded live-workflow authority, fresh V0 safeguards and per-path budgets. Do not read live configuration now to fill unknowns.

Required inventory artifact V6 below: expand each row per actual configured instance/override during authorized discovery. Columns record requested label/resolved selection, effective provider/model/auth scope, trustworthy served-model/route evidence, included/extra usage attribution, tool audit and required/optional disposition. All effective/live evidence is UNKNOWN here; desired current values are repository facts only. Intended target for all model paths is Claude Opus 5.5 with verified slug, never a hardcoded guessed ID.

| Role/helper and current desired selection | Requiredness / evidence to collect | Unsupported behavior |
| --- | --- | --- |
| `harness-orchestrator`: OpenAI Sol | Required; effective/served selection and route/billing for planning/dispatch, preserved board/root pins | Block full cutover |
| `harness-worker`: OpenAI Sol; `harness-worker-glm-1`, `harness-worker-glm-2`: Zai GLM | Primary worker required; each enabled lane required or explicitly excluded; measure actual tool read and continuation per lane | Disable explicitly excluded optional lanes; required lane failure blocks |
| `harness-reviewer`: OpenAI Astra | Required independent session, private state and exact evidence/candidate access; measured review and rework lifecycle | Block; never have worker approve itself |
| Delegated agents | Inventory actual delegates and overrides; required if workflow depends on them; measure effective/served route and isolation | Disable optional unsupported delegation; otherwise block |
| Compression | Discover configured model/route and trigger; required for advertised long-session workflow; measure continuation lineage and billing | Disable only if optional with disclosed limits; required path blocks |
| Vision | Discover configured model/route and actual usage; required only if advertised workflow requires it; verify real model/route, not label | Explicitly disable optional vision; required path blocks |
| Other configured model helpers | Enumerate every discovered model caller/override, including hidden automatic calls; assign requiredness before trials | Unknown required route blocks; optional unsupported route disabled, no silent fallback |

Run one frozen harmless synthetic task through real orchestrator → worker → independent `harness-reviewer`, including native request-changes/rework/approval on the same task, actual harmless tool audit and continuation. Use actual history and applicable retry bounds, not invented clean cards or canned lifecycle text. Same model never collapses role/session/worktree/authority boundaries. Reuse valid V1 evidence where unchanged; separately measure missing helper paths with their approved budgets/windows. No real OpenAI/Zai calls for regression: V4 proves explicit-selection contracts offline, not live service availability.

Expected V6 outcome: every required row has trustworthy exact-model, allowed included-pool route/billing and genuine workflow/tool evidence, optional exclusions are disabled and disclosed, independent readiness review agrees. For native route this completes NATIVE_SUCCESS; stop adapter work. Missing attribution/coverage is NATIVE_INCONCLUSIVE/partial, not ready. Refusal/disallowed routing stops requests. No mocks, estimated costs, file presence or current author session establish readiness. Only accepted V6 and separate attended authorization release M5.

## M5 — versioned rollout, consumption and rollback

Owners: controller integrates approved repository candidate; account owner/operator performs separately authorized attended per-target installation/selection; independent reviewer assesses readiness/evidence. Prerequisites: V6 acceptance, exact approved SHA/tree, enumerated targets, tested version bounds and safe rollback decision.

1. Publish only exact tested Hermes/Claude version pairs, not universal support. Spec's reported Hermes `v0.21.5+6751.g9cf7960 (2026.9.24)` / upstream `9cf7960f` and Claude `2.1.283` are dated observations, not inspected current installation or compatibility promises. V5 must reject an incompatible interface/version before inference; no guessing translation.
2. Before any update, rerun affected contracts: provider/translation changes V3; selection/helper changes V4/V6 affected rows; runtime/lifecycle changes V3/V5 and affected live audits; billing/terms changes V0/V1 and affected attribution. Reuse unchanged evidence with provenance rather than reflexively repeat entire campaign. Updates need separate scope and tested exact versions.
3. Keep reviewed repository integration separate from attended installation per authorized target and new target-session consumption. Verify candidate/version, effective selection, route/tool/helper behavior and allowed billing for each target; never infer deployment from Git or another session. No own active-policy deployment, push, PR, board/gateway change or live update is implicit.
4. Proposed V7 rollback rehearsal: offline selection fixture demonstrates prior approved selection or pause state, retained task attempts/audits/reviews and zero unauthorized provider calls. Before live promotion operator confirms supported rollback interface/target scope. In Claude-only/no-extra-spend mode rollback may mean pause/no inference; OpenAI/Zai/paid/cancelled-provider switch is never automatic or authorized by rollback wording. External rollback remains attended/explicitly authorized.

Artifact V7: tested-version matrix including negative control, per-target attended installation/consumption evidence, rollback rehearsal and independent final disposition. Stop on incompatibility, drift, missing target evidence, user stop or disallowed spend; preserve all failed-stage/recovery evidence. Final ready requires spec §6 acceptance matrix, not date pressure.

## Acceptance-to-evidence map and current documentation verification

| Requirement | Future evidence / final stop gate |
| --- | --- |
| P1 / goal and authority | Scope + V0; exact requested model, included pool only; unverified entitlement is not ready |
| P2 / ordered bounded slices | Common contract, M0–M5 artifacts/dependencies; fresh exact card bindings and separate side-effect authority |
| P3 / native-first | V0/V1 then native V6; pre-inference stop or measured classifications; no control-as-Hermes-proof |
| P4 / conditional architecture | Accepted V2 + V3 mechanism red/green; no independent Claude executor/core patch/HTTP fallback |
| P5 / workflow and portability | V4/V6 inventory, actual tools/review/rework; no silent OpenAI/Zai/helper fallback or retry reset |
| P6 / update and rollout | V5/V7 + affected V0/V1/V3/V4/V6 reruns; exact tested versions, per-target consumption, safe pause rollback |
| P7 / provenance and publication | Stage record distinguishes fact/proposal/simulation/unexecuted; full staged review and scans, same-card exact candidate approval |

For THIS doc card only, stage both allowed files, preserve frozen checker unchanged, and run these six existing offline checks (not V0–V7):

```sh
python3 private/controller-inputs/verify_impl_plan.py
git diff --check 09a8355c6d6d68d46df26c685b73a4a4b810cf24
gitleaks dir --redact --no-banner docs/plans/261016-claude-max20x-implementation-plan.md
gitleaks dir --redact --no-banner docs/README.md
git diff --cached --stat
git diff --cached -- docs/plans/261016-claude-max20x-implementation-plan.md docs/README.md
```

Record real outputs/exits and candidate SHA/tree on this card. Checker covers scope/hash/structure/links/syntax, not semantic completeness or capability; author and `harness-reviewer` independently inspect P1–P7 and full staged publication surface. No broad suites, `verify-state`, network, account inspection, inference or future test commands are documentation verification.

Known gaps: current eligibility, actual auth/route interfaces, exact model entitlement/slug, safe native billing behavior, supported mediation and lifecycle interfaces, helper overrides, served-model evidence and tested version pairs remain unknown. No proposed plugin/test exists or has passed. Final execution status: M0–M5 and V0–V7 unexecuted/unapproved; plan approval/local integration grants no execution, account-tested, deployed or Claude-ready claim.
