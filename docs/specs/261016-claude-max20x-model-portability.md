# Claude Max 20x inside Hermes: native-first verification and model portability

Status: execution specification; awaiting separately authorized execution. No adapter, account test, deployment or model-readiness claim.

Prepared: 2026-10-16 KST. Documentation authority: `kanban://harness/t_e7f80baf#body`; repository baseline `53d9c46f2f58eb976cabbd57fcdfcfa34e57e6b9`. This specification is desired future work, not applied configuration. See the [documentation index](../README.md) and [repository state distinction](../../README.md).

## 1. Requirements, provenance and present authority

The user reports having purchased Max 20x: **USER-REPORTED PURCHASED**. Login, actual account entitlement, permitted provider billing path and availability of the exact requested model **Claude Opus 5.5** are **UNVERIFIED**. We have not observed the account. The earlier discovery brief's prospective purchase wording is superseded by that user statement, not by an account check.

The goal is Claude models **inside Hermes**, retaining its roles, tools, task lifecycle and independent review, not migration to the Claude Code UI. Use only the included Max 20x Claude/Claude Code usage pool. Do not buy/enable extra usage, top up API credits, drain purchased credits, or fall back to any paid or cancelled provider. Anthropic separately documents monthly API credits for eligible plans [S8]; those credits are not the 20x pool and must not be silently substituted. The purchase authorizes neither additional spend nor account experimentation.

Preserve OpenAI and Zai compatibility for explicit future selections, without invoking them automatically in Claude-only mode. The requested `Claude Opus 5.5` target covers the orchestrator, workers and reviewer, with every other model-using path covered or explicitly disclosed. Preserve that exact label; verify its actual provider model slug, availability and account entitlement before selecting it. An `opus` alias, model self-description or another Claude version is not proof. If unavailable or uncertain, report that result; do not invent a slug or silently replace the requested model.

The original target is **October 18, 2026 KST**, three days from October 15. It is a requested target, not a reset three-day countdown, readiness assertion or automatic cutover date. Missing a safety/readiness gate means stop or report partial progress, not weaken the gate to meet the date.

### Evidence and limits

This specification uses the supplied read-only feasibility brief and its public references, as dated observations available on 2026-10-16. No external discovery or account inspection was performed for this documentation task. The brief reported:

- `hermes --version`: Hermes Agent `v0.21.5+6751.g9cf7960 (2026.9.24)`, reporting upstream `9cf7960f`; `claude --version`: `2.1.283 (Claude Code)`. Executable availability/version is not login, entitlement, installed-source integrity or future compatibility. No update was performed.
- Hermes provider documentation [S1] states native Anthropic OAuth uses extra-usage credits rather than the included Max allowance. This is a documented constraint, not measured billing on this user's account.
- Public source at `9cf7960f274ea2bdfe672d64d26389e9954dfeb6` has `ProviderProfile.create_client` and `external_process` fields [S3]. Its Copilot ACP plugin is an extension precedent [S5], not a Claude implementation. At that commit, `claude-code` aliases the native `anthropic` HTTP provider [S4]; it is not evidence of a shipped Claude CLI backend.
- Upstream reports [R1–R4] corroborate the concern or request support, but include older releases and different plans. They do not prove current behavior, this account's billing or current permission.

Official Hermes docs are authoritative for supported interfaces; official Anthropic docs govern the runtime/account contract. Revalidate the relevant current contracts during an authorized future stage; do not extrapolate compatibility from this dated source match.

### Authority boundaries

Current authorization covers only this specification, one index entry, offline documentation verification, local commit, same-card independent `harness-reviewer` review and exact approved local integration. It does **not** authorize sign-in, credential reads, account/billing observation or changes, inference, adapter/spike implementation, config/profile/model/provider/skill deployment, Hermes/Claude updates, application actions, board/gateway settings changes, push or PR. Merging this document does not authorize executing it.

Future bounded stages need explicit scope for their distinct side effects: attended authentication; account observation/live inference; feasibility; implementation/local integration; attended installation/rollout and any external rollback. Once a bounded stage is approved, ordinary harmless steps within its scope do not need a fresh permission prompt each time. Approval of one stage does not silently authorize the next. All future Harness work stays in its authorized repository-owned worktree and board `harness`; no other fleet is accessed or rewritten under this specification.

## 2. Ordered milestones and decision gates

Execute in this order, recording each gate's result rather than assuming it passed:

1. **M0 — freeze the experiment and permission boundary.** In a separately authorized execution stage, refresh relevant official contracts and runtime provenance, resolve the account-use eligibility question, freeze the synthetic fixtures, expected tool results, attribution oracles, supported interfaces and bounded call budget before any behavioral trial. Establish attended sign-in and no-paid-route safeguards as detailed below. Do not perform inference if those prerequisites fail.
2. **M1 — native route first.** Compare official Claude Code subscription control with stock Hermes using the same bounded synthetic task. Follow the exact native protocol below. Adapter coding may not precede this assessment.
3. **M2 — conditional bounded feasibility.** Only if the native result leaves a justified unmet requirement, and separately authorized, test whether a documented provider extension can preserve all necessary controls using the unmodified official Claude runtime. Resolve terms eligibility first. A native inconclusive result is not permission to bypass unresolved billing/eligibility. Reject infeasible designs; do not expand into core patches.
4. **M3 — conditional implementation and local integration.** Only after an accepted feasibility result and separate implementation authorization, build repository-owned source/tests/non-secret metadata, verify fail-closed routing, translation and portability, then obtain same-card independent review of the exact candidate before local integration.
5. **M4 — measured role workflow and readiness.** Under separately authorized live scope, measure the actual orchestrator/worker/reviewer and helper paths, model and billing attribution. Integrate the evidence, not just a demo transcript. If M1's bounded native main-path comparison passes, proceed directly to native M4 coverage without M2/M3 adapter work. Missing role/helper measurements alone do not justify an adapter; complete that native coverage first to resolve NATIVE_SUCCESS versus partial/inconclusive status.
6. **M5 — attended target rollout and rollback readiness.** Install/select only for explicitly authorized targets after review and readiness approval. Verify consumption by new target sessions; repository file presence or a successful authoring session is not deployment. Updates and later rollout remain separately scoped.

Native outcomes have explicit consequences:

- **NATIVE_SUCCESS:** allowed included-pool billing, exact requested model, representative Hermes tool execution and all required role/helper paths are verified. Stop adapter work. Use native mechanisms and complete independent readiness review/attended rollout only; no adapter is justified.
- **NATIVE_FAILURE:** refusal, incompatible tool behavior, unavailable requested model or established disallowed billing/permission prevents the requirement. Stop live requests; preserve the reason. A documented extra-usage-only route that cannot meet safeguards can fail at the pre-inference gate without risking a charge. Consider M2 only if it can address the unmet requirement within the allowed contract; model unavailability is not cured by pretending a wrapper supplies it.
- **NATIVE_INCONCLUSIVE:** unknown included consumption, reporting lag, concurrent activity, uncertain model/auth attribution or incomplete helper coverage prevents a conclusion. Do not claim readiness. Resolve the uncertainty within an approved bounded scope or stop. A main-path success with incomplete roles/helpers is partial, not NATIVE_SUCCESS.

## 3. Proposed native experiment protocol — not executed

The following is the protocol to authorize, not a claim of working live commands. Sign-in, account controls, usage interfaces, model selection and diagnostic command syntax must be checked against the actual supported versions before execution. Do not invent helper commands or treat this prose as a runnable harness. Record the exact verified commands/interfaces and exit codes in the future evidence record.

### 3.1 Pre-inference prerequisites

1. Use an isolated Harness-owned test environment/profile and worktree with synthetic data only. Freeze one small read-only fixture, its exact expected bytes and a harmless Hermes read-tool task; exclude patient/application data, production access and unrelated tool authority. Freeze expected pass/fail conditions and the role/helper routing inventory before trials.
2. With explicit authorization, inspect the actual supported auth-resolution implementation and non-secret effective route, including credential pools, macOS Keychain access, ambient API/cloud credentials, inherited environment, aliases, fallback chains and auxiliary overrides. An empty shell environment alone is not isolation. Record only source locations and route/presence facts, never values, tokens, account identifiers or credential-store dumps. Do not copy/replay subscription tokens into Hermes. Official attended sign-in must remain owned by the unmodified Claude runtime; any native auth flow must also be officially allowed for the intended use.
3. Separately verify permission/terms eligibility for the intended use; **STOP without inference** if unresolved or disallowed. Technical success does not establish allowed use. Current extra-usage-only documentation can establish a pre-inference NATIVE_FAILURE where that constraint prevents the requirement or exclusion of chargeable routes. Do not execute a knowingly disallowed request to prove that it is disallowed. Native Hermes included-pool attribution is the bounded comparison's measured success/failure/inconclusive result, not a prerequisite that must already be proven.
4. The account owner must establish and attest account-side no-paid-route safeguards **before inference**: no enabled extra-usage/overage route, no auto-top-up, and no accessible purchased/API-credit or cloud billing fallback for the test. Do not autonomously change billing settings. If available controls cannot exclude paid routing, **STOP without inference**. An SDK cost estimate, empty local key variable or absence of a charge is not such a safeguard. Verified permitted use and exclusion of all chargeable/fallback routes are prerequisites; unknown native included-pool consumption alone does not block the safe bounded comparison.
5. Establish isolated request routing with no paid/native-HTTP or cross-provider fallback, including startup failure and helper paths. If a path cannot be isolated using supported controls, exclude it explicitly and refuse complete readiness; if the main experiment cannot be safely isolated, stop it. Do not enable extra usage to make the test work.
6. Freeze a bounded request budget before the trial: one tiny official Claude Code control and one native Hermes synthetic workflow containing a real read-tool round trip (initial request and tool-result continuation). Set supported output/time limits after interface verification; record their exact values before the first request. No automatic reruns, quota-exhaustion experiment, account rotation or retry-budget reset. Stop on any disallowed spend signal, quota refusal, unexpected route, user request or boundary breach.

### 3.2 Control, comparison and attribution

7. Immediately before the control, the account owner records sanitized included-usage and extra-usage/balance observations, timestamps/timezone, measurement resolution and known reporting lag. Pause other account activity for the bounded window, including other devices/sessions. If concurrent activity cannot be excluded, record it as an attribution limitation, not zero consumption.
8. Run the small official, unmodified Claude Code control after attended sign-in, explicitly selecting the verified requested model. Attribute its provider/auth route and served model from trustworthy runtime/provider metadata, not model-generated text. Keep it synthetic and within the frozen budget. Observe included and extra usage after the documented settling interval before proceeding; stop if the control cannot establish a permitted subscription route. This separately attributed control is a prerequisite to the Hermes comparison, not proof of native Hermes included-pool billing.
9. Run stock Hermes using representative system/task instructions and the frozen harmless fixture-read task. Require a structured tool request, an actual Hermes-authorized read, the recorded tool result and a model continuation that uses that result. Capture sanitized tool IDs, arguments, result match and exit status sufficient to prove execution. Merely mentioning a tool, returning a canned transcript or producing a plain-text answer does not pass.
10. Verify actual effective provider, auth path and served model for both initial and continuation requests. Inspect non-secret request/runtime provenance and effective selections; do not rely on an alias string, displayed role label, model self-report or estimated dollar counter. Missing trustworthy model metadata makes that assertion unverified, not implicitly correct.
11. After reporting settles, record the same included/extra measurements and timestamps. Correlate control and Hermes windows separately, allowing for rounding/lag and paused concurrent activity. If needed observations cannot distinguish usage, conclude inconclusive rather than send additional probes outside the budget. No charge movement alone is insufficient if included consumption is unknown; unknown is neither zero usage nor a guarantee of no charges. Do not fabricate billing receipts or retain raw billing screenshots.
12. Assign NATIVE_SUCCESS/FAILURE/INCONCLUSIVE using the complete requirement. The bounded main-path comparison is only a component: M4 must cover required role/helper paths before full native success/cutover. Log the safe pre-inference stop if no authorized comparison was possible; do not call an unrun test an inference failure.

## 4. Conditional provider feasibility and architecture

M2 is a small, separately authorized feasibility stage, not an adapter commitment. Prefer a repository-owned, uniquely named provider plugin through documented `create_client` / `external_process` hooks [S2–S5]. Determine the unique name in that approved stage; do not hijack `claude-code`, replace `anthropic` or assume the proposed provider already exists. Hermes remains the agent and the official unmodified Claude runtime owns sign-in. An official SDK may be evaluated only if eligible and capable, not assumed to be a transparent raw-model API.

Anthropic's SDK overview restricts third-party offerings of consumer Claude login/rate limits [S6]. Its legal/compliance documentation separately allows end users to sign in to the unmodified Claude Code binary themselves, including hosted-binary contexts [S7]. Confirm the actual intended personal/local provider use against the applicable contract before choosing a design. These statements neither authorize arbitrary wrappers nor prohibit every personal local use. If unresolved, stop for authoritative clarification. Never collect credentials, copy/replay subscription tokens, spoof client identity, modify the Claude binary or bypass billing controls.

Feasibility must establish all of the following before promising implementation:

- **One authoritative tool executor.** Hermes owns tool permissions, approval decisions, board/repository/worktree/task pins and actual tool audit records. The Claude subprocess must not independently run filesystem/shell tools or silently start a second agent with wider authority. Use only supported controls to prevent that execution while carrying structured tool requests back to Hermes. If the runtime cannot do this, reject this transparent-provider architecture; a shell wrapper is not an equivalent integration.
- **Protocol translation.** Preserve system/user/assistant semantics; structured tool-call IDs, names, arguments and matched results; parallel-call ordering as supported; errors and completion reasons; streaming boundaries and partial output. Validate malformed/duplicate IDs and arguments without executing invented tools. Exercise the real Hermes executor and continuation, not a transcript stub.
- **Lifecycle.** Handle cancellation during startup and streaming, startup races, process death, timeouts, cleanup and quota errors without duplicate requests/tools or orphan processes. Resume/continuation is scoped to the correct profile, session, task, role and worktree; stale processes/sessions cannot attach to a new task.
- **Independent state.** Isolate orchestrator, worker and reviewer sessions, mutable runtime state and private deliberation. Preserve exact reviewer assignment and evidence access. Using Opus for every role does not merge their authority or remove independent same-card review.
- **Every model-using path.** Inventory delegated agents and auxiliary calls, including compression, vision and other configured helpers. Prove their allowed route or disable an optional unsupported path with explicit limitation. A required missing path blocks full-cutover readiness. Never quietly use an OpenAI/Zai/API fallback for a helper while advertising Claude-only operation.
- **Honest attribution.** Report verified effective provider/model and available usage metadata. Unknown usage stays unknown, not zero or free. Account-side evidence remains necessary for included-pool billing; a plugin's reported cost is not a receipt.
- **Fail-closed routing.** Hermes documents that `create_client` exceptions can fall back to a standard HTTP client [S2]. Raising an exception is therefore not a safety mechanism by itself. Prove through supported configuration/extension behavior that client construction, subprocess startup, runtime and quota failures cannot send another paid/native-HTTP request. Instrument attempted routes in offline tests, including a simulated quota failure. If safe construction cannot be achieved without a core patch, reject the design.

No Hermes fork, installed-source edit, monkey patch, modified runtime, hidden fallback or core-patch dependency is in scope. An infeasible result is useful evidence; it is not permission to silently enlarge the architecture or implement a billing bypass.

## 5. Role identity and model portability

Use native Hermes provider/model selection, aliases and role/profile mechanisms first. Provider/model choice is separate from role identity and authority. Existing role/profile names, exact reviewers, board pins, repository/worktree/task scope, retry accounting and recovery evidence remain stable. Switching to a different model never grants more tools or resets task attempts/retry budgets.

A future authorized selection records requested label, resolved provider/model, profile/role/session scope, effective settings and provenance. Verify resolution rather than replacing old model-name heuristics with equally fixed Claude assumptions. Native aliases can vary by provider/version; do not assume `opus` permanently means the requested model. Select changes explicitly, fail clearly on unavailable models and do not auto-switch provider on quota/error.

Retain OpenAI and Zai configurations/contracts for explicit future selection, with tests of their unchanged selection semantics. In Claude-only mode they must remain uncalled, including helpers and error paths. Mechanism tests may use route spies/fixtures without credentials; real non-regression inference needs its own allowed-provider/spend authorization and cannot borrow this specification's no-extra-spend scope. A cancelled provider is not a fallback resource. No work on another fleet is authorized here.

## 6. Evidence and acceptance matrix

Freeze fixtures, expected tool outputs, routing/error oracles and budgets before behavioral trials. Keep tests proportional to changed surfaces: reuse valid unchanged evidence with exact provenance; do not demand a repeated full model campaign for unchanged behavior. Re-run affected contracts when runtime, provider, selection, tool mediation or billing assumptions change. Mocks prove mechanisms, not actual model delivery or account billing.

| Gate / surface | Required check and evidence | Acceptance / stop condition |
| --- | --- | --- |
| M0/M1 native comparison | Frozen synthetic fixture; permitted auth-resolution facts; no-paid-route attestation; official control and real Hermes read/continuation; exact model/provider attribution; separate before/after included and extra observations with lag/concurrency notes | Complete requirement met: NATIVE_SUCCESS, stop adapter work. Disallowed/refused route: NATIVE_FAILURE and stop requests. Unknown attribution or missing required coverage: NATIVE_INCONCLUSIVE; no readiness claim. |
| M2 conditional feasibility | Contract eligibility for intended use; supported extension proof; structured tool mediation; no independent Claude tool executor; lifecycle isolation; fail-closed construction/startup/quota proof | Proceed only with separately authorized implementation if every necessary control is feasible. Reject core patches, token replay, unresolved eligibility or unavoidable HTTP/paid fallback. |
| M3 pure mechanism tests | Deterministic message/tool ID/argument/result translation, streaming, startup/cancel race, process death, continuation scoping, malformed input and simulated quota failure; route spies prove no alternate request | Exact expected outputs and no duplicated tools/orphans/cross-session state or paid/native fallback. Offline passing tests are not provider/billing proof. |
| M4 genuine role workflow | Bounded synthetic task actually handled by orchestrator, worker and independent `harness-reviewer`, with real harmless tool execution/audits and native review/rework lifecycle; requested/served model and allowed route for each required helper/delegated call | All required paths genuinely measured. Shared private state, text-only demos, unverified helpers/model/billing or bypassed independent review block full cutover; disclose partial results. |
| Portability / OpenAI and Zai | Offline explicit-selection/alias and unchanged-provider regression checks; no fallback/retry-reset in Claude-only mode; any real calls separately authorized and labelled | Existing contracts preserved and no automatic requests to retained/cancelled providers. Fixture evidence must not be called live non-regression proof. |
| Update and rollback | Supported-version contract suite covering tools/cancellation/quota/auxiliary routing/billing isolation/profile separation/review lifecycle; incompatible-version negative test; safe selection rollback rehearsal with preserved task history | Publish only the tested version range. Reject incompatible versions; rollback does not silently invoke another provider or erase evidence. No universal upgrade-proof claim. |

Future execution records must include exact Harness source/candidate SHA and tree, Hermes/Claude versions and verified runtime provenance, tested version bounds, frozen fixture/oracle identities, non-secret effective selections/settings, requested and served model identifiers, commands/interfaces, timestamps, exits, route audit results, measurement limitations and review disposition. Record the provenance of reused evidence and distinguish observed facts, user attestations, documentation claims, simulations and unexecuted steps. Preserve relevant recovery evidence and failed-stage reasons; never reset history to manufacture a clean pass.

Only sanitized conclusions/non-secret metadata belong in tracked docs or handoffs. Do not publish account IDs, emails, tokens, billing screenshots, raw transcripts/logs, credential values, patient/application data or unnecessary machine-specific details. Store no secret values even in ignored evidence. Publication review covers the full staged diff as well as scanning.

## 7. Update, rollout and rollback contract

Canonical future source, tests and non-secret deployment metadata stay in the Harness repository. Use documented profile-local extensions and an isolated protected-baseline task worktree, with same-card `harness-reviewer` approval of the exact candidate. Any policy change, including active Harness policy, needs same-card independent review; this specification changes no policy.

Declare the exact tested Hermes and Claude runtime version range only after testing; the discovery versions above are observations, not a supported range. Run small contract/regression checks across the supported versions and before adopting an update, using the matrix's affected surfaces. Fail explicitly on incompatible interfaces rather than guessing a translation. Supported extensions are upgrade-friendly, not universally upgrade-proof. No runtime upgrade is authorized now.

Separate repository integration, installation per authorized target and actual target-session consumption. Before attended promotion, verify the allowed billing path, exact model, every required role/helper route, lifecycle/tool audits, independent review and rollback selection. A file in Git or the current session's model choice proves none of the other targets were updated. Active live rollout remains separately attended even after local review/integration.

Prefer rollback by reverting/selecting the prior approved provider/model configuration, not editing installed Hermes code. In Claude-only/no-extra-spend mode rollback may mean pause with no inference: selecting OpenAI/Zai or any paid route requires explicit authorization for that selection and use. Preserve task attempts, audits, evidence and review history. External rollback/configuration changes require the applicable attended authorization; stop immediately on user request or disallowed spend. Do not delete evidence or reset budgets to make recovery appear successful.

## 8. Current documentation verification and execution status

For this two-file documentation task only, stage the new spec and index in the exact assigned worktree, then run the frozen offline contract without modifying its checker:

```sh
python3 private/controller-inputs/verify_spec_doc.py
git diff --check 53d9c46f2f58eb976cabbd57fcdfcfa34e57e6b9
gitleaks dir --redact --no-banner docs/specs/261016-claude-max20x-model-portability.md
gitleaks dir --redact --no-banner docs/README.md
git diff --cached --stat
git diff --cached -- docs/specs/261016-claude-max20x-model-portability.md docs/README.md
```

The checker covers repository/task/baseline/branch, exactly two changed tracked paths, UTF-8/fences, one index entry and scoped relative links. It does not assess the entire design. Author and independent reviewer must additionally inspect the full staged candidate for all A1–A9 requirements and publication safety, record actual check exits and candidate SHA/tree, and review on the same card. Controller integration is restricted to the exact approved local candidate after no-drift checks; no push or PR.

Do not run live-sensitive suites, `verify-state`, inference, the future protocol or an adapter experiment as documentation checks. Current execution status is **unexecuted** for M0 account/runtime revalidation, M1 native comparison, M2 feasibility, M3 implementation, M4 measured role workflow and M5 rollout/rollback. No account-tested, implemented, deployed or model-ready status is implied by documentation approval. Full Claude-only cutover requires verified allowed included-pool billing, exact model availability, all required roles/helpers and independent review; otherwise report an explicit partial/inconclusive or stopped result.

## 9. Public references and confidence

These are the official references and pinned source supplied in the discovery brief, not newly fetched findings. Future execution must verify applicable current documentation; pinned source records only that revision.

- **S1 — Hermes native Anthropic provider:** https://hermes-agent.nousresearch.com/docs/integrations/providers#anthropic-native — documented extra-usage constraint, not this account's bill.
- **S2 — Hermes provider plugin / external process:** https://hermes-agent.nousresearch.com/docs/developer-guide/model-provider-plugin#external-process-acp-providers — supported extension contract and client-construction fallback concern.
- **S3 — Pinned provider interface:** https://github.com/NousResearch/hermes-agent/blob/9cf7960f274ea2bdfe672d64d26389e9954dfeb6/providers/base.py
- **S4 — Pinned native Anthropic provider and alias:** https://github.com/NousResearch/hermes-agent/blob/9cf7960f274ea2bdfe672d64d26389e9954dfeb6/plugins/model-providers/anthropic/__init__.py
- **S5 — Pinned external-process precedent:** https://github.com/NousResearch/hermes-agent/blob/9cf7960f274ea2bdfe672d64d26389e9954dfeb6/plugins/model-providers/copilot-acp/__init__.py
- **S6 — Anthropic Agent SDK overview:** https://code.claude.com/docs/en/agent-sdk/overview — third-party consumer-login restrictions; confirm applicability, do not infer blanket wrapper permission.
- **S7 — Anthropic legal/compliance:** https://code.claude.com/docs/en/legal-and-compliance — end-user sign-in to unmodified Claude Code; evaluate intended personal/local use separately from token collection/replay.
- **S8 — Separate monthly API credits:** https://support.claude.com/en/articles/17154008-monthly-api-credits-for-max-and-team-plans — not the requested included 20x usage pool.

Dated upstream self-reports/status observations from the supplied brief, not independently verified account behavior or current permission:

- **R1:** https://github.com/NousResearch/hermes-agent/issues/47260 — reported open; reporter describes native OAuth extra usage/charge.
- **R2:** https://github.com/NousResearch/hermes-agent/issues/65564 — reported open; older-release Pro report of small prompts succeeding but representative tool-bearing requests failing for extra usage despite subscription headroom. Not current Max 20x proof.
- **R3:** https://github.com/NousResearch/hermes-agent/issues/25267 — reported open subscription-provider proposal; historical credit-policy wording is not current terms or shipped implementation.
- **R4:** https://github.com/NousResearch/hermes-agent/issues/48320 — reported closed as duplicate; closure does not establish that a CLI backend shipped.
