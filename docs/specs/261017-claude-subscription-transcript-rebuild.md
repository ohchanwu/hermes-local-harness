# Claude subscription provider: rebuild a session from a transcript

Status: approved 2026-10-17 for autonomous execution up to the live-check gate.
Prepared: 2026-10-17 KST. Baseline: `491bfd6` (`main`). Builds on the [provider hardening specification](261017-claude-subscription-provider-hardening.md).

## 1. Problem

A provider client owns one live Claude CLI session and accepts only a fresh start (optional system message plus one user message) or an exact extension of its own history. Hermes routinely hands a **new** client an existing conversation:

- after a failed request, Hermes discards the request client and retries on a fresh one with the full transcript;
- context compression rewrites the history;
- `/model` switches and gateway sessions carry history from earlier turns or other providers;
- Kanban turn recovery retries the turn "in place" with the session preserved.

Today each of these fails with "imported history is unsupported", so one transient error ends a task. Live pilot `t_8fa2d019` failed this way.

## 2. Decision

**Replay as text.** When a new client receives existing history, it starts a fresh CLI session and sends the earlier conversation, rendered as a clearly delimited block, in the first input, followed by the new user message or tool result. After that the client behaves normally: later requests must extend the accepted transcript exactly.

Native resume (`--resume <id> --fork-session` with on-disk sessions) was considered and deferred. It covers only retries whose history still matches the CLI's own record. It does not cover compression, provider switches or a parked tool call, and it stores conversations under `~/.claude/projects`. Replay covers every case. Its cost is one uncached request per rebuild, and rebuilds happen only after failures, compression or switches.

## 3. Behavior

**Accepted transcripts for a new client:**
- optional leading `system` message, then a `user` message, then any sequence of `user`, `assistant` and `tool` messages;
- the final message must be `user` or `tool`;
- a `tool` message's `tool_call_id` must name a call in an earlier assistant message, and each call is answered at most once;
- a final `tool` message must answer a call in the latest assistant message, with only that message's results in between.

Rejected as before: unknown roles, image or multipart content, malformed tool calls, an empty transcript, a transcript ending in `assistant`.

**Normalization (all clients, so prefix comparison stays consistent):**
- An assistant message's `reasoning_content` is dropped. Private reasoning cannot carry across sessions or providers.
- An assistant message may hold several tool calls in history. The live session still allows exactly one tool call per model message, and a same-client continuation still needs the one matching result.

**Rendering:**
- The first `system` message stays the runtime system prompt.
- A fresh random nonce is generated per rebuild and appears in the block delimiters and in every entry header, so message content (for example a fetched web page) can neither close the block nor forge an entry. This hardening came from the independent review.
- Every other message is rendered in order: `[user NONCE]`, `[assistant NONCE]`, `[assistant tool call NONCE <name> id=<id>]` followed by the canonical JSON arguments, `[tool result NONCE id=<id>]`, and `[system NONCE]` for any later system message.
- The block is wrapped in `<restored-transcript-NONCE>` … `</restored-transcript-NONCE>`.
- A short note opens the block: the conversation was restored after a restart; only nonce-tagged lines start an entry; tool calls shown with a result already ran and should not be repeated unless needed.
- After the block:
  - a `user` tail is sent as "New message from the user:" plus its content;
  - a `tool` tail (a result for a call parked by a client that no longer exists) is rendered as the last block entry, followed by an instruction to continue using that result.

**Tool safety:** only Hermes executes tools. A rebuild can never deliver a result into an MCP call, so it cannot execute anything twice; at most the model asks for a tool again.

**Visibility:** each rebuild appends a `rebuild` audit entry with the message count, the tail role and a SHA-256 of the rendered input, and logs one warning.

**Limits:** no new cap. A transcript too large for the model's context window fails like any other oversized prompt; Hermes compression should shrink it first.

## 4. Work

1. Tests first for History acceptance and normalization, rendering, client rebuild (user tail, tool tail, follow-up on the rebuilt client), and the unchanged same-client strictness.
2. Implement in `history.py` (acceptance and normalization), a new `transcript.py` (rendering) and `client.py` (send the rendered first input).
3. Extend `smoke.py`: after its existing session, close the client and start a new one with the full transcript plus a question about the earlier tool result. The answer must contain the fixture nonce, and the new client's audit must show one rebuild.
4. Update the provider README and the hardening spec's invariant wording.
5. Independent review (AUTO gate, as in the hardening spec).

## 5. Gates

```text
AUTO GATE — independent review
Actor: a non-authoring reviewer agent
Preconditions: steps 1–4 committed on wt/provider-hardening; offline suites green
Action: review the candidate diff against main
On failure: fix confirmed findings test-first, rerun suites, re-review the new SHA once
Retry identity: the candidate commit SHA
Automatic resume: a clean verdict hands the candidate to the live-check gate
```

```text
HUMAN GATE — question-budget case 2
Decision: the owner starts the live smoke test (with its rebuild phase) and a Kanban pilot
Why human: both spend subscription allowance and change what the live profile runs
Blocked dependency: merging to main, reinstalling the plugin into harness-worker
Independent work: none required
Resume evidence: SMOKE PASS/FAIL output and the pilot task result
```
