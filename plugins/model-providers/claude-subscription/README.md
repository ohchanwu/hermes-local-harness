# Claude subscription — bounded serial Hermes provider

Repository source only. No live installation, profile/model change or rollout
has been performed. Provider name: `claude-subscription`; models: the exact ids
allowlisted in `compat.MODELS` (currently `claude-opus-5-5`). It does not
replace `anthropic` or the native `claude-code` alias. Independent review of the
local candidate is still required. Design: [hardening specification](../../../docs/specs/261017-claude-subscription-provider-hardening.md).

## Modules

| Module | Job |
| --- | --- |
| `compat.py` | Every model/CLI literal: allowlist, versions, CLI flags, child env |
| `history.py` | Transcript validation and canonicalization |
| `translate.py` | Tool schemas, chat-completion records, usage |
| `stream_events.py` | Parser for one streamed assistant message |
| `runtime.py` | Owned CLI process group, nonblocking I/O, cleanup |
| `bridge.py` | Owner end of the Unix-socket MCP bridge |
| `client.py` | `ClaudeSubscriptionClient` orchestration |
| `mcp_server.py` | Standalone MCP server and server end of the bridge |
| `smoke.py` | Owner-run live smoke test |

## Supported and tested surface

The official, unmodified Claude Code binary owns subscription authentication.
The plugin never reads/copies OAuth tokens, signs in, uses an Anthropic API key,
or constructs an HTTP model client. This is personal/local runtime mediation,
not a terms exemption or provider endorsement.

Hermes `v0.21.5+6751.g9cf7960` (public contracts at
`9cf7960f274ea2bdfe672d64d26389e9954dfeb6`). The provider runs only its own
dedicated Claude Code install, named by `HERMES_CLAUDE_SUBSCRIPTION_CLI`
(Hermes' `process_command_env_vars` route); it never falls back to the
interactive, self-updating `claude` on `PATH`, and its children run with
`DISABLE_AUTOUPDATER=1`. A CLI older than `compat.CLI_MINIMUM` or with
unparseable `--version` output fails before inference. A newer version not in
`compat.CLI_TESTED` runs and records one `untested_cli` audit entry and log
warning. The hard checks are behavioral: the init event's version must equal
`--version`, and served model, tool list, `apiKeySource` and `modelUsage`
provider are verified as before. No Hermes/Claude update or production
dependency was added.

Supported APIs are native provider discovery, `ProviderProfile.create_client`,
`external_process` resolution and synchronous `chat.completions.create`.
Construction is lazy, so startup failures occur in the owned request path rather
than throwing into Hermes' legacy HTTP-construction fallback. The transport and
async-wrapper opt-outs are deliberate; **async helpers are not supported**.
`close`, `is_closed`, context-manager use and streaming iterator `close` are
provided. Native Hermes' main streaming path was exercised end to end on the
original run49 candidate (see evidence limits below); both
stream/nonstream return shapes are exercised offline. Native nonstream main-loop
execution was not separately measured live.

A client owns one fresh, in-memory official CLI session. Its model, output
token cap (`max_tokens`/`max_completion_tokens`, otherwise the CLI default) and
effort (`HERMES_CLAUDE_SUBSCRIPTION_EFFORT`, default `medium`) are fixed by its
first request; changing any of them requires a separate client. Initial history must be
one user message, optionally preceded by one system message. The system is passed
as the runtime system prompt, user input through stream-json; assistant/tool
history remains in the same process. Subsequent requests must preserve the exact
canonical prefix and append either the one matching tool result or one new user
turn. Canonicalization accepts harmless native empty/null assistant content and
JSON argument key/whitespace differences, not changed semantics. Unknown imported
history, compaction, changed system/tools/session/profile/worktree/task identity,
unsupported roles, images and multipart content are rejected, not flattened or
silently forgotten. No session persistence/resume/token-file copying is used.
The accepted execution home and minimal child environment are bound at create;
home/profile/task/worktree identity is checked again before deferred startup,
input/result delivery and subsequent streamed chunks. A changed scope terminates
deferred execution, rather than moving the accepted transcript to another home.
The optional session ID must be nonempty text and is immutable for that client.

Function schemas become MCP declarations. A complete, single real model
`tool_use` is correlated by name/JSON arguments with the one parked MCP request;
model tool-use ID and MCP JSON-RPC ID remain distinct. Hermes gets a native
`tool_calls` response and alone authorizes/executes the tool. Its recorded tool
result on the next create call is returned exactly once to that invocation.
The MCP server reaches the client only over a Unix socket in a private
`/tmp/hcs-*` directory (0700). It authenticates with a per-session token passed
in the owner-only `mcp.json` env, the client accepts exactly one connection and
then removes the socket path, and messages are newline-delimited JSON with a
2 MB line bound. A parked call blocks on the socket; closing it cancels the
call. The server acknowledges each delivered result, and the client matches
every acknowledgement. The server never opens the requested tool path and
contains no filesystem/shell/tool implementation. Duplicate/replayed IDs,
missing/mismatched results and changed prefixes are errors. Multiple/parallel
model calls are rejected before any native tool call is exposed. Serial
multi-step tool use is supported without a step cap.

Streaming text comes from actual runtime deltas. Tool-call name/identity and
argument fragments are emitted only after the whole message and MCP invocation
match, so Hermes cannot act on a partial/parallel tool message. Terminal finish
reasons are `tool_calls`, `stop` or `length`, with available per-message usage.
Snapshot/stream mismatch, malformed protocol, quota/refusal, rejected rate limit,
process death and unsupported model/executor selection terminate the client.
An unmatched tool cannot become a text-success result. Unknown usage is absent,
not fabricated zero. Raw runtime usage/modelUsage is available on nonstream
response metadata and the client audit; runtime list-price cost is not a bill.

There is no session-level cap on user inputs, assistant messages, tool steps
or session duration; the subscription's own rate limits are the usage bound,
and a rejected rate limit still terminates the client. Hang protection remains:
the per-response timeout (default 300 s) is an idle timeout that resets on every
runtime event, and it also bounds startup and backpressured input writes; the
version check has a ten-second ceiling; cleanup stays within a five-second
budget (TERM, then KILL/reap); runtime JSON lines are bounded at 8 MB. Because
CLI compaction stays disabled, a very long session can fill the context window
and end the client with an error; start a new client. Closing before first
iteration creates no session files and launches no child; startup cancellation
owns and reaps the version child, not merely the model child. Sampling/options,
arbitrary CLI arguments and concurrent create calls are unsupported. CLI retries/nonstream fallback are disabled; the plugin never
relaunches a failed runtime. Use a separate client for a new role/task/session.
Cancellation is terminal, not resumable. Always close the client/agent, including
parked streams; partial output is not successful completion.

Claude built-in tools are disabled with `--tools ''`; strict owned MCP config,
restricted/empty setting sources, explicit settings, no hooks, no skills,
empty plugin cache, no memory/background tasks/cron/compaction/connectors/tool
search and minimal child environment preserve the serial transport boundary.
Only MCP tools advertised by Hermes are allowed. Runtime init verifies the exact
model, CLI version, auth-source indication and tool list. These controls do not
replace Hermes permissions or globally forbid Hermes' own permitted tools.

## Future manual setup and rollback — NOT executed here

Only after separate attended authorization and exact-candidate review:

1. Install the provider's dedicated CLI at an exact version, separate from the
   interactive one, for example
   `npm install --prefix "$HERMES_HOME/runtimes/claude-code/2.1.283" @anthropic-ai/claude-code@2.1.283`
   (confirm the currently supported pinned-install method first). Set
   `HERMES_CLAUDE_SUBSCRIPTION_CLI` in the Hermes environment to the absolute
   path of that install's `claude` binary (a bare name is rejected). Sign-in is the ordinary attended subscription login shared
   through the same `HOME`; never export tokens or configure an API-key
   substitute for this provider.
2. Copy this whole directory to
   `$HERMES_HOME/plugins/model-providers/claude-subscription/` for the explicitly
   authorized target. No edits to installed Hermes or Claude are needed.
3. Select provider `claude-subscription` and an allowlisted model through the
   native picker or supported `hermes config set model.provider` and
   `hermes config set model.default` interfaces. Start a new session, not imported
   history. Do not install/select it in an existing fleet as an automatic action.
4. For a bounded Claude-only workflow, explicitly configure its request-routing
   fallback chain empty and single-attempt/no-auto-recovery behavior. The actual
   validation used native `AIAgent(fallback_model=[])`, task-local
   `agent.api_max_retries=1`, `agent.auto_recovery_cycles=0`, compression disabled,
   memory/background review skipped and a runtime-only read-file toolset.
   This is not a change to global fallback functionality. The profile's
   `fallback_models` tuple is a **picker catalog**, not a routing fallback chain.
5. Inventory required helpers/roles before any broader use. Vision, async calls,
   arbitrary helper transcripts, compression/context compaction, imported history,
   persistent resume and full orchestrator/worker/reviewer operation are unproven
   or explicitly unsupported. Do not advertise full-fleet readiness or assume a
   helper selects this provider. A required missing path blocks that rollout.
6. Roll back by stopping/closing this client and explicitly selecting the prior
   approved provider/model in a new native session. `openai-codex`/`chatgpt`,
   the registry-only `openai-api` route, and `zai`/`z.ai` remain ordinary native
   selections; they need no plugin guard teardown. No real OpenAI/Zai request was
   made here. For an explicitly Claude-only task, pause on failure rather than
   silently substituting a provider. Removing this directory later is an
   attended installation action; preserve task history/evidence first.

## Upgrading the dedicated CLI

1. Install the new version beside the old one (step 1 above, new directory).
2. With owner approval, run one live smoke test against it:
   `python3 plugins/model-providers/claude-subscription/smoke.py --cli <new claude> --model claude-opus-5-5`.
   It runs one session (one tool round trip, one follow-up) under a throwaway
   `HERMES_HOME`, never retries, and prints `SMOKE PASS cli=<version> model=<model>`
   or `SMOKE FAIL: <reason>`.
3. On PASS, add the printed version to `compat.CLI_TESTED` and commit.
4. Point `HERMES_CLAUDE_SUBSCRIPTION_CLI` at the new install. Roll back by
   pointing it at the previous directory. Adding a model is the same: add it to
   `compat.MODELS`, then smoke-test it.

## Actual verification and retained recovery history

The live evidence below predates the hardening changes (modules, version
policy, model allowlist, dedicated CLI, removed session caps, socket bridge).
Those changes are verified offline only; no live run has attested them yet.

Card `kanban://harness/t_51cbb4e0`, run49, baseline
`92f0300eeb7f23d32dff38d9f7ecaef2c3caf698`. All new model slots are consumed:
**two official CLI sessions**, primary plus one corrective after actual
unmatched-tool/rate-limit error-path fixes. Reviewers must not launch more.
Each session had two explicit user inputs, three observed assistant messages,
reported runtime turns `[2, 1]`, one native `read_file`, one matched MCP return
and a same-client `FOLLOWUP_OK` response without a second tool call.

| Case | Native/model tool-use ID | MCP ID | Result |
| --- | --- | --- | --- |
| Primary | `toolu_01WcFyvBWJWiqWYAMNeGE5kC` | 2 | PASS, about 8.30s parent workflow |
| Corrective, run49 runtime source | `toolu_01DSp2G9ZumxJGWt2CqTzAgL` | 2 | PASS, about 11.93s parent workflow |

Fresh random nonce fixtures were frozen before each launch and excluded from
model inputs. The actual installed native `AIAgent.run_conversation` discovered
this user provider, streamed through the real native transport, invoked the
actual Hermes read-file executor and delivered its recorded JSON result to MCP.
Native tool-start/complete callbacks and transcript IDs agree with model and MCP
receipts; no outer-worker read/result-mailbox intervention, executor stub,
core monkeypatch or HTTP substitute stood in for the automatic loop. Exact
served `claude-opus-5-5` and `firstParty` appeared in runtime metadata. The native
summary's separate `served_model` field was null; the runtime metadata, not that
field or model self-report, establishes the observed model. Both leaders were
reaped and groups absent after repeated cleanup (intentional CLI exit143), with
native parent exit0. No exact internal wire-request count is claimed.

One pre-live official auth-status check retained only loggedIn=true,
authMethod=claude.ai, subscriptionType=max, apiProvider=firstParty and exit0.
The corrective run reused it, not another auth/account inspection. Supplied
Max20x/credits-OFF/$0 observations and owner attestations supplied the bounded
allowance basis. No account-side usage/billing measurement was performed;
unexposed auto-reload remains independently unverified. Estimated list costs
are not account receipts or proof of included-pool consumption. The requested
1024 cap is a supported control, not intercepted proof of its exact wire value.

Native validation used an owned test HERMES_HOME, not live profiles, with
ordinary installed-library bootstrap. Run48 unexpectedly prepared dependencies
before its audit guard and stopped; its failure and controller's four later
import-only failures remain intact. Owner-authorized run49 reused that existing
task-local dependency generation with documented lazy-install disable, without
another install/download or live runtime update. Per-process audit guards denied
parent network, live configuration/document access and nonallowlisted processes.
They prevented optional Bash login-shell snapshot/`true` initialization and an
entry-points metadata read; the genuine Python-backed native read still passed.
These validation-only guards are not plugin deployment features or a fake
bootstrap. No live profile/plugin/config/model selection was changed.

Offline tests currently cover 73 provider mechanisms (including both bridge
ends over a real socket and the smoke script against an inert runtime), five
registration/scope contracts and the original ten prototype regressions. Default test imports do
not load installed Hermes or contact providers. Inert Python children exercise
actual client/MCP/process code; registration tests label peripheral fake
provider dependencies. Separate `--native-api` mode exercised real isolated
native discovery/metadata/transport and ordinary OpenAI/Zai aliases without
inference; `openai-api` is a registry route, not a ProviderProfile in this version.
These offline tests are not model or billing evidence.

Run50 independent review rejected run49 candidate
`7d280803fa8e55873350fa4a17efda772fa1bc6c` for startup cancellation/deadline and
deferred scope defects. Run51 added regression assertions before repairs: actual
sleeping/stubborn Python version children, startup/response/session bounds,
closed-before-first-next, delayed scope changes and parked-result delivery.
The initial 37-case RED had 14 assertion failures including scope subtests; its
first green passed all 37. Additional backpressured-input cancellation/deadline
REDs exposed blocking-lock/write defects and retained cleanup errors; the final
39-case provider suite passes after bounded nonblocking writes. All failures,
intermediate diffs and original evidence remain private for independent review.

The two real integrations above are hash-bound to the rejected run49 candidate,
not to the changed run51 client. Unchanged registration, MCP transport, message
translation and official CLI controls retain those historical observations;
startup ownership, earlier deadlines, deferred scope checks and input-write
changes are reverified offline only. There is no new exact-candidate live
attestation. Both live slots remain consumed; no live script was rerun.

Fresh run51 isolated native inert controls also passed on the changed client:
actual provider discovery/construction rejected closed and changed-scope deferred
streams without starting a child, then the actual installed `AIAgent` main stream
automatically executed one native read, returned the exact recorded result via
MCP and completed a same-cached-client ordinary follow-up. The runtime was an
inert Python event producer, **not Claude/model delivery**. Its owned version and
runtime groups were reaped/absent; no auth/network/model call or dependency
download occurred. Two preliminary native-control failures are retained: a
driver cleanup assumed a not-yet-created request cache, then the explicit tool
allowlist caught Kanban tools auto-injected by the test's activation environment.
Neither reached a model child or tool execution. Corrected test-only setup
removed that activation input before the passing fresh control; no core patch,
live configuration change or evidence reset was used.

Run48 retained real schema/history/MCP/client-tool RED/green, including failed
test guards, but admitted some text-client code preceded its tests. Run49 retained
assertion RED/green for pre-effect timeouts/history, malformed argument errors,
stubborn-child cleanup, unmatched-tool false success and rejected rate limits.
**The historical text-path TDD-order gap is not erased or claimed as original
ordering compliance.** The owner explicitly accepted only this one historical
exception, `t_51cbb4e0-run48-text-order-1`, after disclosure;
`original_historical_TDD_order_compliant=false` remains recorded. New RED/green
does not retroactively repair it. All behavioral/hermeticity/safety requirements,
test-first repairs and independent same-card review remain mandatory. Native setup/import failures,
failed expectations about registry-only OpenAI metadata, both live runs and
exact source/output hashes remain in ignored `private/provider/` for review.
No secrets/raw account output or private thinking are retained or published.

Focused/broader offline commands, from the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_claude_subscription_provider.py' -v
python3 -m unittest discover -s tests -p 'test_model_selection_portability.py' -v
python3 -m unittest discover -s spikes/claude-runtime-capability -p 'test_*.py' -v
```

Native validation commands and frozen environments are retained privately:
`run_native49.py native-selection49-registryfix selection49.py`,
`prepare_live49.py` / `run_live49.py`, and
`prepare_corrective49.py` / `run_corrective49.py`. These are evidence, **not
reusable launch instructions**. They consume exclusive slots and must not be
replayed. Syntax/manifest/relative-link checks, per-surface secret scans and the
full staged diff are part of exact-candidate independent review. This artifact
is not M4 role/helper/billing readiness, attended installation, or cutover.
