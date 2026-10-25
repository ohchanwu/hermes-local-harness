# Claude subscription — bounded Hermes provider

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
The plugin never signs in, stores or logs credentials, uses an Anthropic API
key, or constructs an HTTP model client. The CLI runs with the OS account's
real `HOME`, `USER` and `LOGNAME`, so it finds the ordinary Keychain login.

Background Hermes processes cannot read a locked Keychain. For them the owner
can create the CLI's official headless login with `claude setup-token`, save it
in an owner-only file (mode 0600), and set `HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE`
to that file's absolute path. The client checks the file is an owner-only
regular file, opens it, checks the opened file again, and hands the open
descriptor to the CLI process only (`CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR`);
the MCP server closes any descriptors it inherits from the CLI. The plugin never reads the token,
and the token is never put in any environment variable. Do **not** put the
token in a profile `.env` as `CLAUDE_CODE_OAUTH_TOKEN`: Hermes deliberately
passes that variable to every tool subprocess, where commands the model runs
could read it. A `CLAUDE_CODE_OAUTH_TOKEN` variable is never forwarded by this
plugin. Remaining exposure: Hermes tools run as the same OS user and can read
the file if they look for it, comparable to the user's other credentials; use
the provider in profiles whose tools you trust, and revoke and regenerate the
token if it may have leaked. This is personal/local runtime mediation,
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
first request; changing any of them requires a separate client. A new client
normally starts from one user message, optionally preceded by one system message.
The system is passed as the runtime system prompt, user input through
stream-json; assistant/tool history remains in the same process. Subsequent
requests must preserve the exact canonical prefix and append either the one
matching tool result or one new user turn. Canonicalization accepts harmless
native empty/null assistant content and JSON argument key/whitespace
differences, not changed semantics, and drops assistant reasoning fields.

When a **new** client is handed an existing transcript, as Hermes does after a
failed request, after compression, on a `/model` switch or in gateway sessions,
it rebuilds the session: it starts a fresh CLI session and sends the earlier
conversation as a nonce-delimited block in the first input, followed by the new
user message or tool result
([rebuild specification](../../../docs/specs/261017-claude-subscription-transcript-rebuild.md)).
The transcript must start with a user message (after an optional system
message), end with a user or tool message, and every tool result must name an
earlier call. Hermes' context compaction can leave complete tool-call groups
(an assistant message with calls, then exactly one result per call) ahead of
the user message carrying its summary; those leading groups are accepted and
left out of the replay, while the client still tracks the full transcript.
Each rebuild records a `rebuild` audit entry (with the count of leading rows
left out, `skipped_leading`) and logs a warning.
A rebuild never delivers a result into an MCP call, so it cannot run a tool
twice. Changed system/tools/session/profile/worktree/task identity on the same
client, unsupported roles, images and multipart content are still rejected. No
session persistence/resume/token-file copying is used.
The accepted execution home and minimal child environment are bound at create;
home/profile/task/worktree identity is checked again before deferred startup,
input/result delivery and subsequent streamed chunks. A changed scope terminates
deferred execution, rather than moving the accepted transcript to another home.
The optional session ID must be nonempty text and is immutable for that client.

Function schemas become MCP declarations. A complete real model message may
hold several `tool_use` blocks (parallel tool calls). The CLI requests them over
MCP one at a time. Its first request must match one of the message's calls by
name/JSON arguments; Hermes then gets every call as one native `tool_calls`
response and alone authorizes/executes them. Model tool-use IDs and MCP
JSON-RPC IDs remain distinct. The next create call must carry exactly one result
per call. The parked request gets its result first; each later MCP request is
matched to a remaining call (in any order; identical calls are answered in
message order) and gets that call's result, exactly once. If the model continues
before the CLI has requested every call, the request fails.
Hermes may remove calls from a batch before running it: a duplicate (same name
and arguments) or `delegate_task` calls over its concurrency limit. Its recorded
assistant message then holds only the kept calls, and the provider accepts that.
When the CLI requests a removed call, a duplicate gets its twin's result and any
other gets an error result saying Hermes did not run it. Only the first call of
a batch is confirmed by an MCP request before Hermes runs them all; if the CLI
then skips one, Hermes has already run it and the request fails.
The MCP server reaches the client only over a Unix socket in a private
`/tmp/hcs-*` directory (0700). It authenticates with a per-session token passed
in the owner-only `mcp.json` env, the client accepts exactly one connection and
then removes the socket path, and messages are newline-delimited JSON with a
2 MB line bound. A parked call blocks on the socket; closing it cancels the
call. The server acknowledges each delivered result, and the client matches
every acknowledgement. The server never opens the requested tool path and
contains no filesystem/shell/tool implementation. Duplicate/replayed IDs,
missing/mismatched results and changed prefixes are errors. Multi-step tool use
is supported without a step cap.

Streaming text is the runtime's own deltas, but each message is held whole: its
text reaches Hermes only once the message is final (parked for its tool calls, or
ended by the turn's result). Tool-call name/identity and argument fragments are
emitted only after the whole message and MCP invocation match, so Hermes cannot
act on a partial tool message. Terminal finish reasons are `tool_calls`, `stop`
or `length`, with available per-message usage.
When an API call fails mid-reply (a stream `error` event, such as overload),
the CLI retries it and streams the reply again from `message_start`. Nothing of
the unfinished message has reached Hermes, so the provider drops it and
continues (audit stage `runtime_retry`).
When a second message streams after one has completed, `second_message.py`
decides deterministically (audit stage `second_message`, with its outcome and
row): keep the first when the second is an exact replay; append when the first
was cut off (`max_tokens`) and the second continues it; keep the last when the
first stopped for `tool_use` and the CLI answered exactly those calls itself
(`user` tool_result events) without asking Hermes over MCP, so the second is the
real reply (the first's text is kept, its unrun calls are dropped and can never
be parked later). Each of those answers must be a rejection (`is_error` exactly
true; built-in tools are off), else row `internal_step_non_error_result` fails,
since something may have run outside Hermes. Anything else, or more than four
such messages in one request, fails as `duplicate streamed message` with a
stream audit.
When the stream itself fails (an undecidable second message, event outside a
message, invalid block, snapshot mismatch, malformed or
unknown runtime event), the client first reads the rest of the current message
briefly into memory only (never to Hermes), then writes one owner-only (0600)
file `$HERMES_HOME/sessions/stream_audit_<session>_<YYYYMMDD_HHMMSS_ffffff>.json`
(`stream_audit.py`), and raises the original error unchanged. The file holds an
allowlist only: error class/message, session id, model, CLI version, the client
audit without tool arguments, and per message its id, model, stop reason, event
types (bounded), blocks, restarts, whether text reached Hermes, text length and
sha256, and its relation to the previous message's text. It never holds text,
thinking, tool arguments/results, prompts, environment, paths or credentials. A
write failure is one log warning; an existing file is never replaced.
One bounded exception: when a runtime stdout line is not JSON, the request fails
as before (`runtime startup, I/O or malformed protocol: JSONDecodeError`), and
the audit's `rejected_line` holds the line's length (`bytes`), `sha256`, and at
most its first 200 bytes (`prefix_bytes`, `prefix`) after Hermes's secret
redaction (`agent.redact.redact_sensitive_text` with `force=True`). A token that
the 200-byte boundary cuts is left out whole, so redaction never sees a
shortened secret. If redaction cannot be imported or fails, `prefix` is null
and `prefix_omitted` is `redaction unavailable`; no part of the line is stored.
A `tool_progress` event (the CLI reports a running tool call, every 30 s while
Hermes runs a parked call) is recorded in the audit's event types, counts as
activity for the idle timeout, and is never forwarded. A non-null
`parent_tool_use_id` (a subagent's message) is rejected on `assistant`, `user`
and `stream_event` events only, as `malformed runtime event or unexpected
subagent`; `tool_progress` is accepted with any value of it.
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
search and minimal child environment preserve the owned transport boundary.
Only MCP tools advertised by Hermes are allowed. Runtime init verifies the exact
model, CLI version, auth-source indication and tool list. These controls do not
replace Hermes permissions or globally forbid Hermes' own permitted tools.

## Hermes helper jobs

Hermes helper jobs (compression summaries, titles, approval checks, image
analysis and the rest) can run on this provider
([helper support specification](../../../docs/specs/261017-claude-subscription-helper-support.md)):

- **Async callers:** when `create` is called on a running event loop it returns
  an awaitable served from a worker thread.
- **Concurrent callers:** callers sharing one client queue for it. An open
  stream plus a second call from the same thread is an immediate error.
- **New conversations on the same client:** a request that does not continue
  the client's own conversation, or changes its tool list or output cap, ends
  the CLI session (cancelling any parked tool call) and starts a new one, fresh
  or rebuilt.
- **Options:** `extra_body.response_format` and `extra_body.reasoning` (title
  generation turns thinking off) are ignored, and output caps below
  4096 tokens are raised to 4096 because thinking counts toward the cap.
- **Images:** base64 `data:` images (PNG, JPEG, GIF, WebP) in user messages are
  sent as image blocks. Remote image URLs and images in tool results are
  rejected. When a conversation is rebuilt, earlier images become a note.

## Rollout status (2026-10-17 KST)

Owner-approved and live; GPT is retired from 2026-10-18.

| Home | Main model | Effort |
| --- | --- | --- |
| default (`~/.hermes`, main orchestrator) | `claude-opus-5-5` | high |
| `harness-`, `chapt-`, `jobcron-` `worker` and `orchestrator` | `claude-opus-5-5` | high |
| `harness-`, `chapt-`, `jobcron-` `reviewer`, `advisor` | `claude-fable-5-1` | high |

In all eleven homes, the sixteen `auxiliary.<task>` helpers run on this
provider with `claude-opus-5-5`. Pinning Opus keeps Fable homes off Fable's
weekly cap. All run CLI 2.1.302 with the headless login token file.

Remaining OpenAI profiles (`reviewer-sol`, `worker-*` GPT variants) are out of
every `kanban.dispatch_profiles` list; the project orchestrators' own lists are
`[]` (claim nothing).

Verification:
- live smoke passes for Opus 5.5 and Fable 5.1, including the rebuild and helper
  checks;
- Kanban pilots completed for a worker and a reviewer;
- one-shot chats completed for an orchestrator, the Advisor and the default
  profile;
- Hermes' own `call_llm` (sync) and `async_call_llm` helper paths returned
  through this provider.

Rollback copies: `config.yaml.pre-claude-261017` (before any Claude change) and
`config.yaml.pre-helpers-261017` (before helpers moved off GPT) in each home.

## Manual setup and rollback reference

Only after separate attended authorization and exact-candidate review:

1. Install the provider's dedicated CLI at an exact version, separate from the
   interactive one, for example
   `npm install --prefix "$HERMES_HOME/runtimes/claude-code/2.1.283" @anthropic-ai/claude-code@2.1.283`
   (confirm the currently supported pinned-install method first). Set
   `HERMES_CLAUDE_SUBSCRIPTION_CLI` in the Hermes environment to the absolute
   path of that install's `claude` binary (a bare name is rejected). Sign-in is
   the ordinary attended subscription login. For Kanban workers or other
   background processes, run `claude setup-token` yourself in a separate
   terminal, save the printed token in an owner-only file (for example
   `$HERMES_HOME/runtimes/claude-code/oauth-token`, mode 0600), and set
   `HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE` to its absolute path in the profile's
   `.env`. Never paste the token into a chat, a `.env` or a commit, and never
   configure an API-key substitute for this provider.
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
3. On PASS, add the printed version to `compat.CLI_TESTED` and commit. Tested so far: 2.1.283 and 2.1.302 (both SMOKE PASS, 2026-10-17).
4. Point `HERMES_CLAUDE_SUBSCRIPTION_CLI` at the new install. Roll back by
   pointing it at the previous directory. Adding a model is the same: add it to
   `compat.MODELS`, then smoke-test it.

## Actual verification and retained recovery history

The live evidence below predates the hardening changes (modules, version
policy, model allowlist, dedicated CLI, removed session caps, socket bridge).
Those changes passed the offline suites, an independent review and one
owner-approved live smoke test on 2026-10-17 KST:
`SMOKE PASS cli=2.1.283 model=claude-opus-5-5`.

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
