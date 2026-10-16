# Private-local Claude runtime feasibility (offline)

2026-10-16 KST. Authority: `kanban://harness/t_a409287e#body`, run 36.
Verdict: **PARTIAL**. Supported pieces exist, but this is not an accepted V2,
transparent provider, official-runtime roundtrip, or safe-to-infer result.

Hypothesis: documented Hermes provider extensions plus an unmodified official
Claude runtime can leave Hermes the sole tool/permission executor and exclude
alternate routes at construction, startup, runtime, quota and helper boundaries.
The evidence rejects a permission-callback-as-tool-result design and a
raise-to-stop factory. It does **not** establish that every MCP bridge is impossible.
Do not proceed to production implementation or account testing on this evidence.

## Findings that change the decision

Hermes paths below refer only to public revision
`9cf7960f274ea2bdfe672d64d26389e9954dfeb6`, not inspected installed source.

- `providers/base.py:308–331` defines `create_client(**client_kwargs)` returning
  a custom client or `None`. The native Anthropic registration at
  `plugins/model-providers/anthropic/__init__.py:49–53` aliases `claude-code` to
  Anthropic HTTP, not a CLI backend. Reused snapshots/hashes are unchanged.
- Main construction: `run_agent.py:137,242,306–312` delegates lifecycle and init
  to mixins; `agent/agent_runtime_helpers.py:1928–1957` catches profile lookup/
  factory exceptions and returns `None`. `create_openai_client:2015–2125` checks
  the supplied client at 2061–2067, then reaches `process_bootstrap.OpenAI` at
  2120. There is no external-process fail-stop in that function. A deliberately
  raising synthetic profile exercises these **actual AST-extracted bodies**:
  `profile → FORBIDDEN_HTTP_CONSTRUCTOR`. This is an intercepted constructor
  attempt, NOT an HTTP request, demonstrated charge, or proof that a non-HTTP
  URL would send successfully. Successful profile construction avoids that path.
  Public lifecycle/init fetches returned 429, so their complete caller wiring
  and the main runtime/quota recovery machinery remain unexercised.
- Auxiliary construction: `agent/auxiliary_client.py:5399–5419` dispatches on
  `auth_type`; `5359–5396` catches an external-process factory error and returns
  `(None, None)`, unlike main construction. Both success and failure run the
  extracted branch and `_route_client:4998–5002`. This local branch's unavailability
  is NOT an end-to-end no-fallback guarantee. API-key profile exceptions separately
  fall through to `_create_openai_client` at 5272–5293,5331–5342.
- Auxiliary callers matter: `resolve_provider_client:5451–5537` selects branches;
  `get_text_auxiliary_client:5542–5548` resolves task overrides. `_resolve_auto_route:
  4693–4720` tries main, task/main fallback policy, then permitted discovery.
  `_resolve_call_client:7422–7479` may rescue unavailable vision with auto vision
  and unavailable text with a task fallback. `_ladder_provider_fallback:7850–7914`
  permits capacity/payment/quota recovery even for explicit provider selections;
  an empty task chain alone is not an all-helper proof. These paths were read,
  not executed. No real configuration or credential resolver was read/called.
- Wrapping: `_maybe_wrap_anthropic:1941–1948` recognizes
  `HERMES_SKIP_TRANSPORT_WRAP`; `_to_async_client:4735–4780` recognizes
  `HERMES_SKIP_ASYNC_WRAP` before rebuilding `AsyncOpenAI`. The provider docs
  explicitly document both opt-outs for complete async-safe external-process
  clients. Neither flag suppresses every caller's fallback policy.
- Official Claude CLI reference documents `-p`, `--input-format stream-json`,
  `--output-format stream-json`, `--tools ""` (built-ins off, not MCP),
  `--strict-mcp-config` and permission controls. `--allowedTools` auto-approves;
  it is not the tool-availability boundary. None was invoked. `--bare` is not
  an included-subscription solution; the prior auth caveat remains unchanged.
- Public official Python SDK `types.py:259–280` and
  `_internal/query.py:586–638` show `can_use_tool` returns allow/deny and updated
  input/permissions, **not a replacement tool result**. Allowing a tool still
  leaves execution to the runtime. Denial text is not successful tool execution.
  Post-tool output replacement (`types.py:521–535`) occurs after execution and
  therefore cannot establish sole-Hermes execution either.
- A different, supported structured channel exists: SDK
  `_internal/query.py:656–688,753–781` routes MCP JSON-RPC through a named SDK
  server and returns `mcp_response` in a correlated `control_response`.
  `types.py:2330–2378` supplies built-in disabling and strict MCP configuration;
  transport `subprocess_cli.py:591–617,701,730` translates these options.
  This makes an MCP-only Hermes rendezvous a **proposal worth distinguishing**
  from an invented textual tool transcript, not a validated transparent API.
  Tool-use IDs, Hermes's actual executor/permissions and continuation across its
  model-call boundary are still unproven. The fixture freezes only control ID
  `control-1`, MCP RPC ID `7`, tool `fixture_read` and its exact synthetic result;
  these are not claimed to be real Claude/Hermes tool-use IDs.
- SDK transport `subprocess_cli.py:819–825` merges the parent's environment with
  `options.env`; passing a small options dictionary does not remove ambient auth.
  Our direct inert child has an explicit minimal environment instead. No SDK was
  imported, run, installed, modified or monkey-patched.

## Executed bounded mechanisms

From the assigned worktree:

```sh
python3 -m unittest discover -s spikes/claude-subscription-feasibility -p 'test_probe.py' -v
```

Five collected cases: successful profile; throwing profile/main HTTP attempt;
structured inert exchange; owned-child timeout/reaping; network/file-access guard.
Mechanism RED exited 1: five cases, four assertion failures and one guard pass,
not missing imports. GREEN exited 0: `Ran 5 tests`, `OK` (2.174s on the first
complete green run). Exact stdout/stderr/exits are ignored task-private receipts.
The frozen result bytes are `HARNESS_READ_OK` plus LF. `fixtures.json` SHA256:
`e568c52d6b16b7c678b0d1861bad6e74d02093b98a9dba5356391bd8fbb50965`.

Actual inert stdout contained the MCP-shaped request and an acknowledgment with
`accepted_result.content[0].text = "HARNESS_READ_OK\n"`, plus exactly the four
allowed environment keys. Success: returncode 0, reaped true, group absent true.
Timeout: returncode -9, timed_out true, reaped true, group absent true. Cleanup is
called twice in both cases. Absolute Python, `-I -S`, synthetic owned HOME/cwd,
`start_new_session=True`, bounded waits and owned-group-only termination are used.
Parent audit denies network and non-allowlisted file access during mechanisms;
child denies all file opens/network/child creation after its inspected stdlib
imports. No auth/cloud environment is inherited. macOS injected the locale hint
`__CF_USER_TEXT_ENCODING`; the child removes it before checking the four-key set.

The source exercise runs four selected function bodies with imports/annotations
removed and explicit fake dependencies, including an HTTP constructor that records
and raises before creating any client. Validators, headers, SSL, configuration,
credential lookup and actual transport are NOT exercised. The inert child merely
exchanges source-shaped envelopes and a frozen synthetic authorization/result;
it is NOT Hermes execution or an official model continuation. Thus passing tests
expose the unsafe constructor route and establish local process mechanisms only.
Runtime/quota/helper no-fallback proof, malformed/duplicate tool-use handling,
real role/session isolation and official billing remain UNRUN, not silently passed.

Development evidence is retained, including the initial RED reporter blocked by
its own file guard and first green-attempt failure (macOS locale injection and
owned-directory cleanup guard). The guard was narrowed to permit owned directory
cleanup and stdlib traceback source, without allowing credentials. This is one
probe artifact generation, not a discarded/replaced diagnostic candidate.

## Public evidence receipts

Ten additional anonymous GET attempts: eight HTTP 200, two HTTP 429, 30-second
per-attempt timeout, no redirects/retries/pagination. The last GET used GitHub's
contents endpoint for a different pinned source path after the raw-host 429s;
there was no refetch of unchanged inputs or account endpoint. Raw snapshots,
complete exact URL/UTC/hash manifest and verification receipts remain ignored at
`private/feasibility/`. SDK `main` and live docs are retrieval snapshots with
unknown commit identity, not a pinned SDK release or compatibility range.

| File | Exact URL | Retrieval UTC, 2026-10-16 | SHA256 of response body |
| --- | --- | --- | --- |
| get-1.txt | https://raw.githubusercontent.com/NousResearch/hermes-agent/9cf7960f274ea2bdfe672d64d26389e9954dfeb6/run_agent.py | 09:35:08.553717 | `2dda8e9bb530d8da54cfb1625f624a5b9533300f1be828b689cfd5e73bbae373` |
| get-2.txt | https://raw.githubusercontent.com/NousResearch/hermes-agent/9cf7960f274ea2bdfe672d64d26389e9954dfeb6/agent/auxiliary_client.py | 09:35:10.042465 | `41d019d18574e69f64c95b8711132f08170db7c2b061e8a56578cdbd41f33cf9` |
| get-3.txt | https://hermes-agent.nousresearch.com/docs/developer-guide/model-provider-plugin | 09:35:11.228790 | `60e4df679016b4e09ac06cffceed0920147a0d325d929c512b3af1149181dc40` |
| get-4.txt | https://raw.githubusercontent.com/anthropics/claude-agent-sdk-python/main/src/claude_agent_sdk/types.py | 09:35:12.321000 | `c06ccef3487b2f5ad81000a72a772b823760db1c32e85693eea57c8b16a93aa2` |
| get-5.txt | https://raw.githubusercontent.com/anthropics/claude-agent-sdk-python/main/src/claude_agent_sdk/_internal/transport/subprocess_cli.py | 09:35:14.014253 | `23c0b35acfcff5426255f1f17433e66fc7f8f6d5b8f339e93e085233c569e11c` |
| get-6.txt (429) | https://raw.githubusercontent.com/NousResearch/hermes-agent/9cf7960f274ea2bdfe672d64d26389e9954dfeb6/agent/client_lifecycle.py | 09:35:48.515169 | `6850b0e5d07bed32b3613d4c7da50e0fc36542239a5ff5188b524494e9edda75` |
| get-7.txt (429) | https://raw.githubusercontent.com/NousResearch/hermes-agent/9cf7960f274ea2bdfe672d64d26389e9954dfeb6/agent/agent_init.py | 09:35:49.453755 | `6850b0e5d07bed32b3613d4c7da50e0fc36542239a5ff5188b524494e9edda75` |
| get-8.txt | https://raw.githubusercontent.com/anthropics/claude-agent-sdk-python/main/src/claude_agent_sdk/_internal/query.py | 09:35:51.144484 | `0562517de949f4431177f204fe84cda3265f495d0eb0a949b9ced96cc5bd8276` |
| get-9.txt | https://code.claude.com/docs/en/cli-reference.md | 09:35:51.973552 | `0acf910e96c4a9f4488d9f40befecc1077fdd58598276a8436e8ef54408ecace` |
| get-10.txt | https://api.github.com/repos/NousResearch/hermes-agent/contents/agent/agent_runtime_helpers.py?ref=9cf7960f274ea2bdfe672d64d26389e9954dfeb6 | 09:36:36.291840 | `33688718eb20033273fd27b8bceb97735dd475bc6b50befeaef76c9b36c47700` |

Decoded get-10 source: `main-helpers.py.txt`, SHA256
`735612c07ffb2d28e5d1ab555578c961e34e7e70fd53404fec574e61954e805a`,
Git blob `6fce8cf786a9c9ac39122d3bec214485662b245d`. The previous three accepted
source inputs and their original exact receipts are preserved in
`private/controller-inputs/source-manifest.json` (SHA256
`a6af6d7cfc863e512aba35a1693ba7743815f7275160e7a7c7157979ce2a8969`);
see [native history](../../docs/operations/261016-claude-max20x-native-preflight.md).
The probe requires the two named copied source files with exact hashes; absent or
drifted evidence fails rather than downloading, importing installed code or
passing zero tests. Independent review uses these preserved task-private copies.

## Boundary and next smallest step

Board/root/worktree/branch/protected baseline/assigned profile/tenant and Harness
roster pins matched the card before editing. No other tracked paths, OpenAI/Zai
contracts or role/retry policies changed. Zero Claude/SDK processes, account or
credential accesses, model/control/native experiments, paid routes, installs,
core patches, live configuration changes, external writes, pushes or PRs.
Public document/source reads are not account calls. Native NATIVE_FAILURE and
M1 UNRUN remain unchanged; Claude Opus 5.5 slug/availability/entitlement, billing,
auth and helpers remain unknown. Private/local authority is not terms exemption
or provider approval; a generic Support-letter gate did not block this work.

Next smallest technical step, if separately assigned: resolve a supported
MCP-only rendezvous across the real Hermes model-call/tool-result boundary and
prove no alternate construction/helper route, starting with the remaining pinned
caller/recovery sources and concrete supported isolation controls. A non-HTTP URL,
lazy always-returned client, guarded transport or disabled helper is only a
proposal until its failure paths are established; do not call this proof that a
core patch is necessary, or run account tests to paper over it. If those controls
cannot be established, reject the transparent-provider architecture. Do not build
a broad provider framework or repeat unchanged billing/terms discovery.

Local candidate commit/review is separate from integration, installation and
rollout. Full focused output, scoped scans, staged publication review, UTF-8/
fence/link/embedded-command syntax and exact allowlist results accompany the
same-card `harness-reviewer` handoff. No broad runtime suite or `verify-state` is
appropriate for these changed surfaces.

## Generation2 — final bounded diagnostic, not V2 acceptance

2026-10-16 KST; `kanban://harness/t_2812605d#body`, run39. Baseline
`562c77a304df9d3e89da583c016db34228a2d88c`. Generation2/2 continues the
accepted generation1 PARTIAL result (t_a409287e/run36, review37); setup run38
was not a semantic attempt. Material review corrections consumed: zero at handoff.
Everything above remains generation1 evidence, not newly claimed compatibility.

Final OFFLINE verdict: **PARTIAL**. The Hermes-side seam is mechanically usable
in this constrained simulation; official-runtime rendezvous and all-path routing
are NOT established. **V2 is not accepted; M3/account trials remain unreleased.**
Stop this diagnostic line here: retain the artifacts, do not create generation3,
build a production adapter, broaden the architecture or reset the attempt budget.

### What actually ran, and what was faked

`rendezvous.py` executes only hash-checked, named, inspected Hermes AST bodies
at the same pinned revision as generation1. It removes imports, decorators and
function annotations, supplies restricted builtins with imports denied, and
injects explicit fake peripheral dependencies. It never executes a downloaded
module wholesale or imports installed Hermes/Claude/SDK code.

- `chat_completion_helpers.py:761–794` is the actual nonstreaming client dispatch;
  `1622–1663,1666–1761` serialize the assistant/tool-call ID. Actual
  `turn_tool_round.py:46–230,233–308` stages that row, checks persistence, invokes
  the owning-side executor and returns `continue` after its result. The full
  conversation loop, request assembler, transport wrappers and error caller are
  not executed. `conversation_loop.py:41–58` identifies those separate phases.
- Across two actual dispatch-body calls, the inert child emits an independently
  generated synthetic assistant `tool_use` event and MCP request, then waits.
  The facade exposes one structured Hermes-style tool call without answering MCP;
  the owning-side fake executor supplies the result through the actual tool-round
  body. The second dispatch validates assistant/result lineage and replies to the
  parked MCP request. The child computes a SHA256 receipt of the received text;
  it does not return an answer-key/model-text success. IDs stay distinct:
  `toolu-synthetic-1` (model-shaped), `control-1` (control), `7` (JSON-RPC).
- These are **synthetic IDs, not observed official model tool-use IDs**. Only the
  owning test side performs `fake_permission`/`fake_execution` once. The actual
  Hermes permission implementation, tool executor, registry, durability store and
  post-tool compression are explicitly fake. A failed persistence dependency
  makes the actual round stop before that fake executor. Missing/duplicate/
  mismatched results, duplicate/missing model events, argument mismatch, replay,
  cancellation and changes to each profile/role/task/session/worktree tuple field
  terminate the facade without another tool dispatch or stale child attachment.
  The scope argument is synthetic harness scaffolding, not proof that stock
  Hermes passes all those identities through its client interface.
- Owned inert children use absolute Python, `-I -S`, synthetic HOME/cwd, exactly
  four environment keys and isolated process groups; per-read monotonic deadlines,
  bounded output/wait, group kill, reap and repeated cleanup are exercised on
  success, startup/continuation timeout, process death and cancellation. No secret
  environment is inherited. Scoped Python audit guards deny network, unexpected
  file access and other child commands; these are test protections, not an OS
  sandbox or a production security claim.

The reused SDK retrieval snapshots clarify the remaining capability gap:
`types.py:1209–1223` separates ToolUseBlock.id from ToolResultBlock.tool_use_id;
`2837–2840` exposes no model ID in SDKControlMcpMessageRequest. Query
`412–425,505–506` dispatches control requests separately from regular assistant
messages; `656–688` awaits MCP then writes the correlated control response.
This does not specify the official CLI's emission order or uniquely correlate
parallel identical MCP calls to model IDs. The prototype assumes one assistant
tool-use event is available before one MCP request; it rejects ambiguity instead
of inventing a model ID from the control/RPC ID. No SDK was fetched again or run.

### Routing controls: narrow proofs, not a universal stop switch

| Actual pinned path exercised | Result and boundary |
| --- | --- |
| `agent_init.py:815–843,986–1022` → main factory → `client_lifecycle.py:288–311` | A nonthrowing lazy factory is used at explicit initialization and replacement; both return the custom client, with zero HTTP constructor attempts. Header/TLS/profile lookup peripherals are fake. Replacement is called directly with a synthetic failure reason, not by the full error handler. |
| Main `create_openai_client:2015–2125` with actual aux validators `2880–2913` | `acp://synthetic` passes the real validator. A throwing factory still attempts the intercepted HTTP constructor. Non-HTTP URL alone does NOT prohibit HTTP client construction; no request is sent. Generation1's no-op validator is not reused as proof. |
| `try_activate_fallback:2074–2199`, `_fallback_chain_exhausted:1935–1943`, `recover_with_credential_pool:1005–1016` | Explicit empty main chain and absent pool return false/no recovery with zero route attempts in these bodies. Cooldown helpers are fake. This does not exercise quota classification, retries, `turn_api_error` or every main recovery caller. |
| Aux `_resolve_call_client:7422–7479` → `_resolve_external_process_branch:5359–5396` and actual empty-chain bodies `4417–4477` | External factory startup failure returns unavailable; explicit text task plus empty task chain raises without auto rescue. Cache lookup/config/profile are injected, not live reads. |
| Aux `_try_payment_fallback:4262–4273` → `_discovery_chain_allowed:4654–4666` | An explicit main provider blocks built-in discovery before the discovery-chain spy is called. This is a supported narrow control, not a helper-disable switch or all-helper proof. |
| Aux `_ladder_provider_fallback:7850–7941` → `_try_main_agent_model_fallback:4321–4362` | After an injected quota classification and empty task chain, the actual bodies read the disk main-provider dependency and attempt `resolve_provider_client(provider="openai")` despite `route.main_runtime.provider="synthetic"`. Spy catches the attempt before credentials/client/request. Classification, health and backend-identity peripherals are fake; the foreign-provider fixture is deliberately not skipped. A session pin/empty task chain alone is insufficient. |

No fallback/validation function body was rewritten to obtain these results.
No guard transport or optional-helper disable is claimed as implemented. Aligning
disk and session settings may avoid the demonstrated mismatch, but is not proven
all-path isolation. Async callers, vision auto rescue, discovery/auto construction,
init without explicit route, refresh/restore, main error classification/retry,
streaming, helper inventory and live effective selection remain unproven. The
selected extracted gates are not a complete safe-to-infer runtime.

### Evidence, receipts and final capability decision

Focused command (includes all five unchanged generation1 tests):

```sh
python3 -m unittest discover -s spikes/claude-subscription-feasibility -p 'test_*.py' -v
```

Initial mechanism RED: exit1, 18 tests, 16 assertion failures including subtests;
no import errors. First GREEN: exit0, 18 tests. A subsequent deadline/death oracle
first failed with three assertions (19 tests, exit1), then GREEN passed all
**19 tests: five retained plus fourteen new** (exit0, 7.715s). Both REDs and green
outputs remain ignored in `private/feasibility/generation2-*.txt`. The final
syntax/scope/scanner/staged-diff receipts accompany the same-card review.
Generation1 `probe.py`, `test_probe.py`, `fixtures.json`, source snapshots and
original receipts are unchanged. Only a new explicit rendezvous branch and a
stdlib hash import were added to its inert child; original modes/oracles remain.

Six new anonymous GETs, all HTTP200, timeout30s each, zero retries/redirects/
pagination; the envelope is exhausted. Diagnostic accounting is **16 attempts**:
generation1 ten (8×200,2×429) plus generation2 six (6×200), not a reset. The three
earlier native inputs remain separately retained. No unchanged source/docs/terms
were refetched. Exact response hashes, decoded hashes, Git blob checks and UTC
timestamps are in ignored `generation2-manifest.json`. All six URLs use the exact
Hermes revision `9cf7960f274ea2bdfe672d64d26389e9954dfeb6`:

| Source URL (GitHub contents, exact ref) | UTC on 2026-10-16 | Decoded source SHA256 |
| --- | --- | --- |
| https://api.github.com/repos/NousResearch/hermes-agent/contents/agent/client_lifecycle.py?ref=9cf7960f274ea2bdfe672d64d26389e9954dfeb6 | 09:58:14.891830 | `5333b2dd5c96427996f060e9c01f6ca86d882cb89a59f60482e2281de8b66d5f` |
| https://api.github.com/repos/NousResearch/hermes-agent/contents/agent/agent_init.py?ref=9cf7960f274ea2bdfe672d64d26389e9954dfeb6 | 09:58:15.768899 | `5befa4177caab596804f185379cbd86e3c91507693f12e20057aae122907cf0d` |
| https://api.github.com/repos/NousResearch/hermes-agent/contents/agent/chat_completion_helpers.py?ref=9cf7960f274ea2bdfe672d64d26389e9954dfeb6 | 09:58:29.884151 | `15c2aa0e7863495546ad1bbaf8ad9c67de12fdbc65f10b91c7f51a210d0a5214` |
| https://api.github.com/repos/NousResearch/hermes-agent/contents/agent/tool_executor.py?ref=9cf7960f274ea2bdfe672d64d26389e9954dfeb6 | 09:58:30.871485 | `c2c65ba2d5d0847f968321e0438f2dd3c87973cb2680acb5cd52192f48b602ab` |
| https://api.github.com/repos/NousResearch/hermes-agent/contents/agent/conversation_loop.py?ref=9cf7960f274ea2bdfe672d64d26389e9954dfeb6 | 09:59:04.452417 | `8b8768c965579121d836d736134661433b1e672f352971fe72b950986d9baca7` |
| https://api.github.com/repos/NousResearch/hermes-agent/contents/agent/turn_tool_round.py?ref=9cf7960f274ea2bdfe672d64d26389e9954dfeb6 | 09:59:32.276092 | `8afef412460a4a6a0d3df0ec219919a736ba376f4add81864fd49c0e758c531f` |

Tool-executor/conversation snapshots were inspected for caller context, not
executed wholesale or counted as exercised executor/loop behavior. SDK snapshots
remain unversioned retrieval observations, never a tested release/range.

Decision: **do not accept the transparent-provider architecture for M3 now**.
Reconsideration needs concrete official-runtime evidence that a real structured
tool-use ID is available and uniquely matchable while MCP is parked, that the
same pending invocation accepts Hermes's result on continuation with built-ins
off, and that cancellation/parallel ambiguity do not invoke another executor.
It also needs actual supported all-caller fail-closed configuration, including
disk/session helper recovery and factory failure. Another echo or synthetic
generation cannot supply either missing capability; do not schedule one. This is
a technical capability stop, not a generic provider-permission/Support-letter
gate or proof that every possible MCP design is impossible. Any future official
process/account trial remains separately scoped and subject to the existing
attended-auth, applicable-use and no-paid-route prerequisites.

Zero official Claude/SDK processes, account/auth/model/billing calls, credential
reads, paid/cloud/provider requests, core patches, installs, live settings/policy
changes, pushes or PRs. Native pre-inference NATIVE_FAILURE and M1 UNRUN remain;
Claude Opus 5.5, actual billing, permissions and version readiness remain UNRUN.
