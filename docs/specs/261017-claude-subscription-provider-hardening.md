# Claude subscription provider: upgrade-tolerant compatibility, unbounded sessions, socket bridge and modular client

Status: approved 2026-10-17 for autonomous execution up to the smoke-test gate. Steps 1–8 implemented locally on branch `wt/provider-hardening` and verified offline; see §14. No installation, configuration change or live call has been made.
Prepared: 2026-10-17 KST. Baseline: `f031b4e` (`main`), carrying the run51 provider candidate from `7127e61`.
Subject: [`plugins/model-providers/claude-subscription/`](../../plugins/model-providers/claude-subscription/README.md). Parent specification: [Claude Max 20x inside Hermes](261016-claude-max20x-model-portability.md).

## 1. Why

The provider's core design is sound and is kept. Hermes starts the official Claude Code CLI; the CLI owns subscription sign-in; Hermes tools are offered to the model as MCP tools; a "parked" MCP call is handed back to Hermes as a native `tool_calls` response; Hermes alone authorizes and runs the tool; its result releases the parked call.

Four parts of the current candidate are too rigid for ordinary use:

1. **Exact pins in five places.** The CLI version `2.1.283` is compared byte-for-byte at `client.py:584` and again at `client.py:685`. The model `claude-opus-5-5` is a module constant (`client.py:20`) and is repeated in `__init__.py` (`fallback_models`, `model_capabilities`). Claude Code updates itself by default, so one routine update disables the provider until code is edited. The version pin also adds little safety: the init-event and `modelUsage` checks already verify what actually ran.
2. **Proof-of-concept session limits.** Two user inputs, four assistant messages, `--max-turns 3` per input, a 150-second session ceiling and a 1024-token output cap. Any normal multi-step Hermes task exceeds them.
3. **File-mailbox bridge.** `client.py` and `mcp_server.py` exchange `call-N`, `result-N`, `returned-N` and `cancel` files; both sides poll every 10 ms.
4. **One 672-line module** mixing history validation, stream parsing, process ownership, IPC and response construction.

## 2. Goals and non-goals

Goals:

- A Claude Code update for interactive use never breaks the provider; upgrading the provider's own CLI is a deliberate, one-command, verifiable step.
- Model selection by request from an allowlist, keeping the served-model check.
- Sessions bounded only by Hermes, the subscription's own rate limits and hang protection.
- Event-driven bridge with no polling files.
- Smaller modules with one job each; behavior unchanged except where this spec says otherwise.

Non-goals (unchanged from the current candidate): async helpers, vision/multipart content, parallel tool calls, imported or compacted history, session resume, Agent SDK adoption, Hermes core patches, installation or rollout. Each remains separately authorized work.

Invariants that must survive every change: the plugin never reads, copies or exports subscription credentials and never uses an API key; Claude built-in tools stay disabled; only Hermes-advertised tools are allowed; Hermes alone executes tools; a mismatched, replayed or partial tool call never reaches Hermes; any protocol failure terminates the client rather than becoming a success; cancellation reaps the whole process group.

## 3. Fix 1 — the provider gets its own Claude Code install

Decision: the provider runs a dedicated, version-locked CLI binary, separate from the interactive `claude` on `PATH`.

- Location: `$HERMES_HOME/runtimes/claude-code/<version>/`. The install mechanism (npm package at an exact version, or the official installer's pinned-version option) is confirmed against current Anthropic installation docs at implementation time; do not guess.
- The child environment sets `DISABLE_AUTOUPDATER=1` so the dedicated binary never updates itself.
- The CLI path comes from the provider configuration (§4), not from `PATH`. If it is unset, the provider fails before inference with a message naming the missing setting. There is no fallback to the interactive `claude`, because that binary can change underneath Hermes.
- Sign-in is unchanged. Both binaries run with the same `HOME`, so the dedicated binary uses the ordinary attended subscription login. The plugin still never touches credentials.
- Rollback is pointing the configuration back at the previous version's directory.

The install script is a documented owner action, not something the provider does at runtime.

## 4. Fix 2 — one source of truth for compatibility

Add `compat.py` holding every compatibility literal, and nothing else:

```python
CLI_MINIMUM = (2, 1, 283)            # oldest version with every flag/event this client needs
CLI_TESTED = {(2, 1, 283)}           # versions that passed the smoke test (§7)
MODELS = {"claude-opus-5-5": {"context_length": 1000000}}   # allowlist + capabilities
CLI_FLAGS = [...]                    # the fixed argv currently at client.py:592
CHILD_ENV = {...}                    # the fixed env currently at client.py:556
```

`__init__.py` derives `fallback_models` and `model_capabilities` from `MODELS`. No other file contains a version or model literal; a test enforces this by grepping the plugin source.

Configuration that differs per machine (the CLI path, default effort) is read from Hermes' supported plugin/provider configuration. If Hermes offers no per-provider setting, use the existing `command` constructor argument and one documented environment variable, `HERMES_CLAUDE_SUBSCRIPTION_CLI`. Confirm the supported route against Hermes `v0.21.5` before choosing.

## 5. Fix 3 — fail on behavior, warn on version

Version handling:

- Parse `--version` output as `major.minor.patch`. Unparseable output fails.
- Below `CLI_MINIMUM` fails before inference.
- At or above minimum but not in `CLI_TESTED` starts normally and records one warning in `client.audit` and the Hermes log: `untested Claude CLI <version>; run the smoke test`.
- The init event's `claude_code_version` must equal the `--version` result (consistency check), not a literal.

Behavior checks stay hard failures, unchanged: exact served model, exact tool list, `apiKeySource == "none"`, `modelUsage` provider `firstParty`, stream/snapshot agreement, stop-reason validity. An unknown CLI flag already fails safely because the CLI refuses to start; the error message must say so and point to the smoke test.

## 6. Fix 4 — model chosen per request from the allowlist

- `_validate` accepts any `model` in `compat.MODELS` and rejects others before any effect.
- The first request fixes the client's model. A different model on a later request on the same client is rejected ("use a new client"), like a changed tool schema today.
- Every place that compares to `MODEL` (`Message.feed`, the init check, the `modelUsage` check, response/chunk construction) compares to the client's requested model.
- The served model must equal the requested model exactly. If a real run ever returns a variant string (for example a dated suffix), record it as an explicit `served_aliases` entry for that model in `compat.MODELS`; never relax to prefix matching.
- Adding a model is a `compat.py` edit plus a smoke-test pass for it.

## 7. Fix 5 — upgrade smoke test

Add `plugins/model-providers/claude-subscription/smoke.py`, an owner-run command:

```sh
python3 plugins/model-providers/claude-subscription/smoke.py --cli <path> --model claude-opus-5-5
```

It makes **one** live session through the real client: one synthetic read-only tool with a fresh random fixture, one tool round trip, one follow-up turn. It checks the served model, the tool correlation, the delivered result, cleanup (process group absent) and the CLI version, then prints a single PASS/FAIL line and the exact version and model. On PASS it prints the `CLI_TESTED` line to add; it does not edit source itself.

Each run is a live model call on the subscription, so it runs only when the owner starts it. It never retries. Its offline test uses an inert fake runtime.

Upgrade procedure, documented in the provider README: install the new version (§3), run the smoke test against it, add the version to `CLI_TESTED`, switch the configured CLI path. Rollback: switch the path back.

## 8. Remove the session limits

| Current limit | New behavior |
| --- | --- |
| 2 user inputs per client | Removed |
| 4 assistant messages per client | Removed |
| `--max-turns 3` per input; `num_turns > 3` check | Flag omitted; `num_turns` validated as a non-negative int only |
| 150 s session ceiling and its timer | Removed |
| Fixed 1024 output cap, `low` effort | Use the request's `max_tokens`/`max_completion_tokens` (or Hermes' default); effort from configuration, default `medium` |
| 4 MB total runtime output | Replaced by a per-line bound (8 MB per JSON line) |

Kept, because they protect against hangs and leaks rather than limiting work:

- Per-response timeout. It becomes an **idle** timeout: it resets on each runtime event, so a long but active response is never cut off. Default 300 s, overridable per request.
- Version-check ceiling (10 s), the 5-second cleanup budget, cancellation and process-group reaping.
- Serial `create` and the one-pending-tool rule.
- Quota/rate-limit refusals terminate the client as today. Subscription rate limits are the real usage bound.

The fixed CLI flags remain otherwise unchanged: no session persistence, no compaction, no built-in tools, strict MCP config, no hooks/skills/plugins/memory.

Because the CLI's own compaction stays disabled, a very long session can eventually fill the context window. That ends the client with a clear error; Hermes then starts a new client. Context compaction stays out of scope.

## 9. Replace the file mailbox with a Unix domain socket

Decision: **Unix domain socket**, not a pipe.

- An inherited anonymous pipe is impossible: the Claude CLI, not the client, starts `mcp_server.py`, and its stdio is the CLI's MCP channel.
- A named pipe (FIFO) carries data one way only. Two would be needed, `open` blocks until both ends exist, and there is no clean connection-closed signal.
- A socket is two-way, gives an immediate end-of-file when either side dies (this replaces both the `cancel` file and deadline polling), and needs only the standard library on both sides.

Design:

- At session start the client creates a short private directory with `tempfile.mkdtemp(dir="/tmp", prefix="hcs-")` (mode 0700) and listens on `bridge.sock` inside it. macOS limits socket paths to 104 bytes, so the socket cannot live under the long `$HERMES_HOME` cache path; the client checks the length before binding. Other session files (`settings.json`, `mcp.json`) stay where they are.
- The client also writes a random 32-byte token into `mcp.json`'s server `env` (file mode 0600; not on the command line, where `ps` would show it).
- `mcp_server.py` connects, sends `{"hello": token}`, and receives the advertised tool list (replacing `bridge.json`). The client accepts exactly one connection, rejects a wrong token and closes the listener after the handshake.
- Messages are newline-delimited JSON with a 2 MB line bound, matching today's MCP input bound:
  - server → client: `{"call": seq, "rpc_id", "name", "arguments"}`
  - client → server: `{"result": seq, "rpc_id", "tool_use_id", "text"}`
  - server → client: `{"returned": seq, "rpc_id", "tool_use_id"}`
- The client checks the socket without blocking on every pass of its existing runtime-read loop, so a call is seen as soon as it arrives rather than by polling for a file. The server side blocks on the socket, so it has no polling loop at all.
- Cancellation: the client closes the socket; the server sees end-of-file, exits without answering the parked call, and the CLI is then reaped as today. If the server dies, the client sees end-of-file and terminates the client.
- All existing correlation checks are kept unchanged: name and arguments must match the model's `tool_use`; RPC IDs and tool-use IDs are never reused; a result must match the parked call; `returned` must echo both IDs.
- `mcp_server.py` remains a stdlib-only script run with `python -I -S` (isolated mode, so it cannot import package modules). It keeps its own small copy of the framing code; a test drives both sides through a real socket to keep the two copies compatible.

## 10. Modularize `client.py`

| Module | Contents (from current `client.py`) |
| --- | --- |
| `compat.py` | Versions, model allowlist, CLI flags, child environment (§4) |
| `history.py` | `History`, message canonicalization |
| `translate.py` | `convert_tools`, `Record`/`record`, `usage`, chunk/response builders |
| `stream_events.py` | `Message` (stream-json assistant-message parser) |
| `runtime.py` | `Runtime`: process group, nonblocking I/O, version check, cleanup |
| `bridge.py` | Client side of the socket bridge (§9) |
| `client.py` | `ClaudeSubscriptionClient` and `Stream`: orchestration only |
| `mcp_server.py` | Standalone MCP server plus server side of the bridge |

`__init__.py` keeps importing `ClaudeSubscriptionClient` from `client.py`, so Hermes registration is unchanged. Plugin manifest and install instructions change from "copy these five files" to "copy this directory".

## 11. Order of work

Each step is a separate local commit with the offline suites green. Steps 3–7 change behavior; for those, write or change tests first and record the failing run, as the repository's test-first rule requires.

1. **Pure refactor** into the modules of §10. No behavior change; the 39 provider and 4 portability tests pass unmodified apart from import paths.
2. **`compat.py`** and removal of all scattered literals, with the source-scan test.
3. **Version policy** (§5): tests for below-minimum fail, untested-version warning, unparseable output, init/`--version` mismatch.
4. **Model allowlist** (§6): tests for an allowed second model, an unlisted model, a model change on the same client, a served model that differs from the requested one.
5. **Dedicated CLI path** (§3): tests for a missing setting, no `PATH` fallback, `DISABLE_AUTOUPDATER` in the child environment.
6. **Limits** (§8): invert `test_same_client_scope_change_and_third_user_input_rejected_before_send` so a third input is accepted while the scope-change rejection stays; replace `test_session_timer_is_armed_before_real_version_startup` with idle-timeout tests (an active slow stream survives, a silent one times out); multi-turn tool loops beyond four messages.
7. **Socket bridge** (§9): port the existing MCP tests (`test_actual_mcp_returns_only_matching_owner_result_and_never_reads_tool_path`, `test_cancelled_or_expired_mcp_cannot_return_result`) to the socket, and add a wrong token, a second connection, server death mid-park, a path-length guard and an oversized line.
8. **Smoke test** script with its offline inert test (§7). Update the provider README: upgrade/rollback procedure, the new limits, the directory install.

Then submit the combined candidate (run51 plus these changes) for independent review. The run51 candidate has not yet been reviewed independently; this review covers both.

## 12. Acceptance

- All offline suites pass: provider, portability and `spikes/claude-runtime-capability`.
- No version or model literal outside `compat.py`.
- No `call-*`, `result-*`, `returned-*`, `cancel` or `bridge.json` files are created; no `time.sleep` polling loop remains in the bridge path.
- No session-level cap remains. Hang protection is the idle timeout, cleanup budget and line bounds.
- Every invariant in §2 is covered by at least one passing test.
- One owner-started smoke-test PASS on the final candidate, recorded with version, model and date. This is the only live call in scope, and it needs explicit owner approval when it is run.

## 13. Authority

Approving this specification authorizes steps 1–8 as local repository changes, offline tests, local commits and independent review. It does not authorize installing a CLI under `$HERMES_HOME`, changing live Hermes configuration or provider selection, running the smoke test or any other live model call, pushing, or rollout. Each of those needs explicit owner approval when it comes up.

Gates for this work:

```text
AUTO GATE — independent review
Actor: a non-authoring reviewer agent
Preconditions: steps 1–8 committed on wt/provider-hardening; offline suites green
Action: review the exact candidate diff against main for correctness and the §2 invariants
On failure: fix each confirmed finding test-first, rerun the suites, re-review the new SHA once
Retry identity: the candidate commit SHA
Automatic resume: a clean verdict hands the candidate to the smoke-test gate
```

```text
HUMAN GATE — question-budget case 2
Decision: the owner starts one live smoke test (and approves installing the dedicated CLI it runs against)
Why human: it spends the owner's subscription allowance and is a deliberate live action this spec reserves to the owner
Blocked dependency: adding the version to CLI_TESTED, merging to main, attended installation
Independent work: none required; offline work is complete
Resume evidence: a SMOKE PASS or SMOKE FAIL line from smoke.py
```

## 14. Implementation notes

- **Hermes setting.** Hermes `v0.21.5` already resolves an external-process binary from `process_command_env_vars`, so the profile sets `process_command=""` and `process_command_env_vars=("HERMES_CLAUDE_SUBSCRIPTION_CLI",)`. With the variable unset, Hermes itself reports the missing setting, and the client raises before any effect. Effort comes from `HERMES_CLAUDE_SUBSCRIPTION_EFFORT`.
- **Output cap.** The profile's `default_max_tokens` is now unset, so Hermes sends no cap unless configured and the CLI default applies. A requested cap is applied to the session through `CLAUDE_CODE_MAX_OUTPUT_TOKENS`. Because the cap is fixed per process, a different cap on a later request is rejected ("use a separate client").
- **Pinned install.** `@anthropic-ai/claude-code` is published on npm at exact versions (verified for `2.1.283`); the native installer's `claude install <version>` is the alternative. On 2026-10-17 the interactive CLI had already self-updated to `2.1.302`, so the provider as previously written could not have started there.
- **Extra module.** `errors.py` holds `ProviderError` so the other modules do not import each other just for the error type.
- **Server end-of-file.** End-of-file from the MCP server is an error only while the client still expects a call or an acknowledgement; a server that exits after its work is done is not.
- **Test order.** Steps 3–7 and the review fixes recorded a failing run before each implementation. The smoke script (step 8) was written just before its offline tests.
- **Review fixes.** The independent review requested changes: `selectors` instead of `select.select` (which fails on descriptors ≥ 1024), absolute-path-only CLI setting, oversized tool results rejected before delivery, a finalizer for the socket directory, the smoke-test hint when the CLI exits before reading input, and stronger tests. The new early-exit test also exposed an existing cleanup bug on `main`: an exited but unreaped CLI made `Runtime.close` raise `PermissionError`. It now reaps the process first.
- **Pre-existing failure.** `spikes/claude-subscription-feasibility` tests fail identically on `main` (they read ignored `private/feasibility/` evidence files absent from fresh worktrees). They are not in this spec's acceptance set.
