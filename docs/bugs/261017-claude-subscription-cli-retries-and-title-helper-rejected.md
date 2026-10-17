# Claude subscription provider rejected CLI retries and title-helper requests

- Incident date: 2026-10-17 (KST).
- Severity: two failures, both in the provider plugin `plugins/model-providers/claude-subscription/`.
  - A user-visible turn failure in one orchestrator's Telegram chat.
  - Session-title generation failing silently on every profile.
  - No data loss and no tool execution from a partial message.
- Status: fixed, deployed to all 11 Claude homes, gateway restarted. Commits `4a5d856`, `d0664df` and `e69274e`.

## 1. Mid-reply API retries by the Claude CLI

### Symptom

At 19:52–19:55, one turn in the Harness orchestrator's Telegram chat failed three times. Telegram showed:

> Claude subscription (serial CLI) didn't answer after 3 attempts … Provider said: unexpected/duplicate streamed message or model

| Attempt | Time before failing | Provider error |
|---|---|---|
| 1 | ~100 s | `unknown assistant stream event` |
| 2 | ~150 s | `unknown assistant stream event` |
| 3 | ~47 s | `unexpected/duplicate streamed message or model` |

No other profile logged these errors. Each attempt also rebuilt the 118-message session transcript, so the three failures cost three full, uncached replays.

### Cause (inferred)

`stream_events.Message` accepted exactly one `message_start` … `message_stop` sequence per request and rejected any other event type. When an Anthropic API call fails mid-stream (for example, overload), the CLI does two things that sequence doesn't allow:

- it passes a stream `error` event through;
- it retries the API call itself, starting a second `message_start` in the same stream.

The provider passes `--no-session-persistence`, so the CLI kept no record of the events. The inference rests on the two error messages and the long waits before each failure.

### Fix

- **`ping` events are ignored.**
- **An `error` event marks the message interrupted.** After it, only a new `message_start` is accepted.
- **A second `message_start` before `message_stop`:**
  - *If no visible text has yet gone to Hermes,* the partial message is discarded and the stream continues. Whitespace and thinking don't count as visible text. The client records the audit stage `runtime_retry` and logs a warning.
  - *If visible text has already gone to Hermes,* the request fails with `runtime retried a reply after part of it had streamed`. Hermes builds the assistant message from the streamed text and keeps that partial reply; it does not retry (`agent/chat_completion_helpers.py`, "Streaming failed after partial delivery, not retrying"). The user can send `/retry`.
- **Chunks keep the first message id** across restarts.
- **An unknown event's error message names its type,** capped at 40 characters and never with content.

Tool calls are still emitted only after `message_stop` passes every snapshot check. A discarded message's partial tool call never reaches Hermes, and a late snapshot from the aborted message is rejected.

### Verification

- **New tests** replay these cases:
  - a restart before any text, both streamed and non-streamed;
  - two restarts, one without an `error` event;
  - a restart after text has streamed;
  - a discarded partial tool call;
  - a late snapshot from the aborted message;
  - an unknown event name;
  - an `error` event with no restart after it.

  The first three new tests failed against the old parser.
- **Independent review:** approved, and its four follow-ups were applied in `d0664df`.
- **Live check:** a one-shot chat on `harness-worker` succeeded after the deploy.

## 2. Title generation rejected by the provider

### Symptom

After the helper rollout, Hermes logged `Title generation failed: unsupported extra_body configuration`.

### Cause

`agent/title_generator.py` calls `call_llm` with `reasoning_config={"enabled": False}`. The provider profile doesn't handle reasoning, so `agent/auxiliary_client.py` falls back to adding `extra_body.reasoning`. The client accepted only `subscription_session_id` and `response_format`. Other helpers that pass a reasoning config, such as the curator, would hit the same rejection.

### Fix

`extra_body.reasoning` is accepted when it is an object, and ignored. `HERMES_CLAUDE_SUBSCRIPTION_EFFORT` governs effort, and the Claude CLI has no per-call way to turn thinking off.

### Verification

- **Unit test:** the exact title-generator shape, an effort shape, and a non-object `reasoning` value, which is still rejected.
- **Live check:** a direct `generate_title` call in the `harness-worker` home returned a title.
- **Not independently reviewed** (small change).

## Remaining limits

- **A retry after visible text has streamed** still fails the turn, by design.
- **Telegram messages sent during a gateway restart are dropped.** Each restart took about 20 seconds, and `drop_pending_on_cold_boot` is on.
- **Title generation in a one-shot `hermes chat -q` can be cut off** when the process exits ("client closed or cancelled"). That is expected for one-shot runs, not a provider fault.

See the [provider README](../../plugins/model-providers/claude-subscription/README.md) and the [helper-support spec](../specs/261017-claude-subscription-helper-support.md).
