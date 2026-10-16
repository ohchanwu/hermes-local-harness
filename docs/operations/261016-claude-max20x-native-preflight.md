# Claude Max 20x native pre-inference gate

Recorded 2026-10-16, 04:23 UTC / 13:23 KST. Execution authority and exact verification contract: `kanban://harness/t_ef3a8463#body`, run 33; user instruction “Start autonomous implementation.” This is the first diagnostic artifact generation, not a new campaign. Setup run 32 was a controller hold/materialization only; no diagnostic candidate was rejected or live trial run. See the [specification](../specs/261016-claude-max20x-model-portability.md), [implementation plan](../plans/261016-claude-max20x-implementation-plan.md) and [index](../README.md).

## Disposition

**NATIVE_FAILURE — documented incompatibility at the pre-inference gate. M1 comparison UNRUN.** This is not an observed inference failure, measured account billing result, account-specific confirmation of the documentation, or full M0/V0 pass. Stock Hermes' documented extra-usage route cannot meet the included-Max-20x-only requirement. Stop native calls rather than enable extra usage or send a request to confirm a known incompatible contract. No owner attestation is needed just to record this documentation-based stop.

Current official provider wording, reused from the frozen controller observations:

> The base Max plan allowance (the usage included in Claude Code by default) is not consumed by Hermes — only the extra/overage credits you've added on top are.

Source: https://hermes-agent.nousresearch.com/docs/integrations/providers (controller retrieval on 2026-10-16 KST). It is a current documentation claim, not a receipt. The pinned native source independently establishes that `claude-code` is an alias for the Anthropic HTTP provider, not a Claude CLI backend; source alone does not establish included-pool billing behavior.

## Boundaries and evidence types

- **Observed here:** Git root is the assigned repository-owned `.worktrees/t_ef3a8463`, common directory is its repository's `.git`, branch `wt/t_ef3a8463`; initial HEAD and protected ref `refs/harness/baselines/t_ef3a8463` both equal `60850828e75bad23ed846c974440ce40edbfff07`. Initial tracked status was clean. Board `harness`, profile/assignee `harness-worker`, tenant unset/null match the assigned card. Sole reviewer is `harness-reviewer`; no child review lane exists. No installed-source/configuration inspection was performed.
- **Observed here:** approved spec SHA256 remains `c0a5b7b752ac056e189c73149caec6d7b43e7c87245571c4e6db3c2d5ca9cf5a`. Full spec, plan, docs index, repository instructions and relevant Harness authority/adoption surfaces were read; no bug report was treated as implementation authority.
- **Reused executable observations:** controller reports `hermes --version`, exit 0: `Hermes Agent v0.21.5+6751.g9cf7960 (2026.9.24)`, upstream `9cf7960f`; `claude --version`, exit 0: `2.1.283 (Claude Code)`. These commands were not repeated here. They establish reported availability/version, not installed-source integrity, supported version range, login or entitlement. Original full stdout/stderr and second-resolution retrieval times are not supplied; do not reconstruct them.
- **User-reported only:** Max 20x purchased. **Desired only:** Claude Opus 5.5 for all required roles/model paths. Exact model slug, public availability and this account's entitlement remain unverified; no model discovery or alias substitution occurred.
- **Unknown/unobserved:** owner no-paid-route attestations; account login; extra/overage, auto-top-up, purchased/API-credit/cloud routes; effective credential resolution/pools/Keychain/ambient credentials; route/helper overrides; served model; usage reporting lag/concurrency and included/extra balances. No account attestation or billing evidence was obtained or simulated.
- **Synthetic only:** the frozen fixture below. No model/tool transcript or claimed live tool execution was generated.

Frozen controller input: ignored `private/controller-inputs/claude-m0-controller-observations.json`, SHA256 `cce444d2ac511879a96e8c5d86992ed9def0abbb3a86c0f6599765fc0cb4d917`, verified unchanged. It contains non-secret observation notes, not full raw page receipts. Its dated quotes are reused with that limitation; there is no original response-body hash or exact UTC retrieval time to assert for those pages.

## Bounded pinned-source observations

Three additional anonymous HTTPS GET attempts, all HTTP 200; no retries, redirects, pagination, authentication or downloaded-code execution. Each used a 30-second timeout. All paths below are at revision `9cf7960f274ea2bdfe672d64d26389e9954dfeb6` under `https://raw.githubusercontent.com/NousResearch/hermes-agent/` (exact URLs in the table). Public response data and timestamp/hash manifest are preserved ignored under this task's `private/native-preflight/`; no account/private runtime values are stored there.

| URL | Retrieval UTC / KST (2026-10-16) | Response SHA256 |
| --- | --- | --- |
| https://raw.githubusercontent.com/NousResearch/hermes-agent/9cf7960f274ea2bdfe672d64d26389e9954dfeb6/providers/base.py | 04:22:54.704686+00:00 / 13:22:54.704686+09:00 | `53c48f8c6a10e0085dea8ac6622ece055218db0a03a4d575d5eaaf4a1b84ebf0` |
| https://raw.githubusercontent.com/NousResearch/hermes-agent/9cf7960f274ea2bdfe672d64d26389e9954dfeb6/plugins/model-providers/anthropic/__init__.py | 04:22:55.074954+00:00 / 13:22:55.074954+09:00 | `5923df831261359801b822e348ace93325f05a46219e006b4eb7b7339dfc7167` |
| https://raw.githubusercontent.com/NousResearch/hermes-agent/9cf7960f274ea2bdfe672d64d26389e9954dfeb6/plugins/model-providers/copilot-acp/__init__.py | 04:22:55.393712+00:00 / 13:22:55.393712+09:00 | `41dce1b92802eda076fe9d0181dc39d9dbcbf26535b03c5648492e8c828ef4fe` |

Decision-changing findings, from data-only reads (no imports):

- Native profile lines 49–53 register `name="anthropic"`, aliases including `claude-code`, `api_mode="anthropic_messages"`, `base_url="https://api.anthropic.com"` and `auth_type="api_key"`. The profile declares a separate default auxiliary model. This is declaration evidence, not observed effective routing or an account auth-resolution audit.
- `providers/base.py` lines 105–114 expose `external_process` launch fields; lines 308–331 define `create_client(self, **client_kwargs: Any) -> Any | None`. A returned client can provide an out-of-tree transport; `None` returns to standard construction. Source comments call this “safe” in the generic construction sense, not a no-spend guarantee. Lines 333–341 expose setup/model-discovery hooks; they were not called.
- Copilot precedent lines 18–22 returns a `CopilotACPClient`; lines 50–62 register `external_process` and launch metadata. Its model discovery can create a signed-in subprocess session (lines 24–47), so “discovery” is not assumed account-free. No discovery/status/help process was invoked. This precedent establishes an extension shape, not Claude protocol compatibility, eligibility, tool isolation or fallback suppression.

## M0 fixture and withheld live interfaces

Frozen [read fixture](../../tests/fixtures/claude-max20x-read.txt): exactly `HARNESS_READ_OK` followed by LF, SHA256 `2bc8a5abe08affb835048c45c7ecffd957d739f57a28c2a0d259e31ac2815575`. Expected future harmless read result is those exact bytes. A future task must restrict tools to an authorized read of that fixture and require a real Hermes tool ID/arguments/result plus continuation; this file alone proves none of that.

No runnable auth, selection, usage, isolation, route-diagnostic, time/output-limit or retry-disable interface was established. Their exact commands/flags and enforceable caps remain UNKNOWN. `hermes chat --help` and `claude --help` were deliberately not invoked: the native contract already stops this route, and help startup account-side effects were not established safe. Known successful version observations were reused instead. No invented dry-run/auth/usage flags are proposed.

Proposed future M1 budget remains one tiny official control plus one native workflow (initial request, actual read, continuation), but is **not released or fully frozen at executable-interface level**. Current authorized Claude experiment budget is zero. Unknown included attribution alone would be the question for a permitted safe trial, not an added prerequisite; here the documented route is incompatible first.

## Conditional M2 read-only assessment and next smallest boundary

**Eligibility UNRESOLVED; transparent-provider feasibility NOT ESTABLISHED. No adapter/spike is authorized or implemented.** The addressable unmet requirement is access to the included pool while Hermes remains the agent, not merely selecting a different native alias. Neither a wrapper nor API credits establish that requirement or supply an unavailable requested model.

Reused official SDK overview, https://code.claude.com/docs/en/agent-sdk/overview:

> Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents

The controller's legal/compliance observation at https://code.claude.com/docs/en/legal-and-compliance describes published unmodified binary/end-user-owned sign-in conditions for commercial contexts and consumer terms for Free/Pro/Max use. Neither statement resolves this intended personal/local Hermes provider use; SDK existence is not permission and the binary condition is not blanket wrapper approval. No legal-policy decision was made.

Supported Hermes plugin documentation at https://hermes-agent.nousresearch.com/docs/developer-guide/model-provider-plugin says:

> A raise is logged and falls back to the standard client.

The supplied documentation also says auxiliary clients key on `auth_type="external_process"` and describes `HERMES_SKIP_TRANSPORT_WRAP` / `HERMES_SKIP_ASYNC_WRAP` for complete async-safe clients. These are extension/transport statements, not proof that all startup, runtime, quota and helper failures cannot reach native HTTP or another provider. An exception by itself cannot be treated as fail-closed. The inspected declarative interfaces and Copilot registration do not establish Claude-specific structured tool roundtrips, supported disabling of all independent Claude filesystem/shell execution, cancellation/continuation isolation, or fail-closed construction. No assertion that these controls are impossible is justified by these limited reads either.

Next smallest useful boundary is an authoritative intended-use eligibility determination for a personal/local provider using the unmodified official runtime with end-user-owned sign-in. Controller should supply/obtain that determination without secrets, not repeat unchanged public probes or launch a paid test. Only if allowed, a separately scoped supported-interface assessment must identify actual controls for sole-Hermes tool execution, role/session/task isolation, structured request/result continuation, and constructor/startup/runtime/quota/helper no-fallback behavior. No adapter coding or live proof before eligibility and those extension capabilities are established. If supported controls cannot establish them without core/binary modification, reject this transparent-provider architecture rather than weaken safeguards.

A future native trial would require materially changed authoritative contract evidence first, then separately authorized attended sign-in, owner no-extra/overage/top-up/API/cloud-fallback attestations, verified effective routing/isolation/model entitlement, supported exact commands/caps and sanitized usage windows per the plan. Attestations alone cannot cure today's documented extra-only incompatibility. No immediate sign-in or billing-setting action is requested here.

## Execution accounting, checks and remaining stages

- Worker: **3 additional public GET attempts out of at most 6**, 3 completed 200 responses; zero retries/redirects. No further requests are needed for this disposition. Controller separately used extraction for four URLs (backend transport/retry counts unknown) plus two explicit HTML GETs; do not invent a combined exact transport count.
- **Zero Claude control/native experiment/inference calls**, zero account/billing/credential reads or writes, zero runtime/config/profile/policy changes. The worker did not run Hermes/Claude commands; version commands above are explicitly reused controller evidence. No OpenAI/Zai compatibility surface was changed or probed; current author/reviewer sessions are not Claude experiments or readiness measurements.
- Local commands executed for binding/provenance: `pwd`; selected non-secret boundary environment reads; `git rev-parse --show-toplevel --git-common-dir`; `git branch --show-current`; `git status --short`; `git rev-parse HEAD refs/harness/baselines/t_ef3a8463`; `git worktree list --porcelain`; stdlib instruction-location/hash/time checks; `git check-ignore`; `git ls-files`; Git author-identity availability checks. Their shell batches exited 0. `python3 private/native-preflight/fetch_pinned.py` exited 0; its exact public responses/hashes/times are above. No installed-source code was executed.
- Local verification is exactly this card's fixture/hash, gate UTF-8/fences/relative links/one index entry, baseline diff whitespace, three scoped gitleaks scans, staged stat/full four-path diff, binding/allowlist/spec/input hashes and manual E1–E5/publication review. Exact executable commands, real stdout/stderr/exits and candidate SHA/tree are preserved in the same-card review handoff and ignored verification receipts. They prove local artifact integrity only, not semantic approval or billing.
- M0 is assessed and stopped, **not safe-to-infer V0 acceptance**. M1 control/comparison remains **UNRUN** due to documented incompatibility. M2 live feasibility/proof and all M3 adapter work, M4 measured roles/helpers/readiness and M5 rollout/rollback remain **UNRUN**, with eligibility/mediation/fallback gates unresolved and no applicable live authority. Future V3–V7 tests, broad suites and `verify-state` were not run.
- Local commit is a candidate only. Same-card independent `harness-reviewer` must review E1–E5 and the exact candidate; controller local integration is distinct from installation. No supported version range, account-tested result, model readiness, deployment or cutover is claimed. All original role, task, model, spend and authority boundaries remain in force.

## 2026-10-16 current scope clarification — offline M2

The preceding record is retained historical evidence, including its then-current
clarification-first stop, GET accounting, NATIVE_FAILURE and M1 UNRUN. Current
`kanban://harness/t_a409287e#body` supersedes that generic external-clarification
prerequisite for bounded private/local non-inference technical work only. Separate
Anthropic Support approval is not required for public interface/source tracing
or an inert offline spike. This does not declare terms waived, invent provider
approval, or settle account-use applicability. No-token/no-paid/core-patch rules,
account-test prerequisites, independent review and attended rollout remain.

The [offline feasibility record](../../spikes/claude-subscription-feasibility/README.md)
reports PARTIAL: actual pinned main constructor fallback and distinct auxiliary
behavior were exercised with route spies, plus a source-shaped MCP exchange and
owned-child cleanup. Five passing offline tests are not an official Claude/Hermes
roundtrip, sole-executor proof or all-path fail-closed result. No account/credential
access, Claude/SDK process or model experiment was performed; native findings and
zero-call evidence above are unchanged. Further production implementation/live
testing is not released by this clarification.
