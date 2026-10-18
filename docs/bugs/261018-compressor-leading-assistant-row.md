# Hermes compactor placed an assistant/tool group ahead of the summary

- Incident date: 2026-10-18 (KST).
- Severity: the session was wedged for good. After a context compaction, every request in the session failed the same way, so retries could not help.
- Affected path: Hermes context compaction in session `20261014_143605_3cfae369` (harness-orchestrator, Telegram), served by the repository's `claude-subscription` provider plugin.
- Status: upstream report for the owner to file against hermes-agent. This document changes no code. Provider-side tolerance is tracked separately on the provider's rebuild card.

## Summary

At about 19:55 KST, a context compaction cut the session transcript from 132 to 81 messages (owner-reported). Every request from 19:57 on failed with:

> ProviderError: a transcript must start with a user message and end with a user or tool message

The compacted transcript does not start with a user turn. After the system row, it starts with an assistant message holding one tool call, then that call's tool result, and only then the user row with the `[CONTEXT COMPACTION` summary. The provider rejects any transcript whose first non-system row is not a user message, so every later request in the session failed the same way.

## Environment

- Hermes Agent v0.21.5+6751.g9cf7960 (2026.9.24), upstream commit `9cf7960f`.
- Provider: `claude-subscription`, the model-provider plugin in this repository (`plugins/model-providers/claude-subscription/`).
- Session: `20261014_143605_3cfae369`, profile harness-orchestrator, Telegram gateway.

## Observed shape

The controller read two request dumps from the session on 2026-10-18. Only the message roles and the summary marker are recorded here; no transcript content is.

Dump `request_dump_20261014_143605_3cfae369_20261018_195713_189121.json`, 82 messages:

| Row | Role | Note |
|---|---|---|
| 0 | system | |
| 1 | assistant | 1 tool call |
| 2 | tool | |
| 3 | user | contains the `[CONTEXT COMPACTION` summary marker |
| 4 | assistant | |
| 5 | user | |
| 6 | assistant | 2 tool calls |
| 7 | tool | |
| … | … | |
| last 3 | tool, assistant, tool | |

Error: `ProviderError` "a transcript must start with a user message and end with a user or tool message".

Dump `request_dump_20261014_143605_3cfae369_20261018_200415_533607.json`, 83 messages: the same leading rows 0–7; the last three are assistant, tool, user. Same error.

Both transcripts end with a tool or user message, which the end condition allows. Only the start condition can have failed: row 1, the first non-system row, is an assistant message.

## Interpretation

This is the controller's reading of the role sequence. It was not confirmed in Hermes's compaction source.

The compactor appears to have kept one assistant (tool call) + tool result pair from before the cut and placed it ahead of the summary user row. The summary row is the user turn a compacted transcript would normally start with. With the pair in front of it, the compacted transcript no longer begins with a user turn.

The pair is a complete call and its result, so it is consistent on its own, and tool-call/result pairing is not the failure here. The defect is where the pair sits: ahead of the summary instead of after it, or dropped and folded into the summary.

## Expected shape

After compaction, the first non-system row should be a user turn. Either of these would do:

- **Summary first.** The summary user row (the `[CONTEXT COMPACTION` marker) comes right after the system row, and any kept assistant/tool group follows it.
- **Leading group removed.** An assistant/tool group that would otherwise come before the summary is dropped and its content folded into the summary, so the transcript starts at the summary row.

Either way, every kept tool result should still follow the assistant message whose call it answers.

## Impact

- **The session stays wedged.** The compacted history is saved and replayed on every later request, so each one is rejected the same way. Neither retries nor new user messages recover it: the bad rows are at the start, and new messages are only added at the end. This session was wedged until a fresh controller session replaced it.
- **Any strict provider breaks the same way.** Many chat-completion style backends require the conversation after the system prompt to start with a user turn, as the Anthropic Messages API does. The `claude-subscription` check is one instance; any provider that enforces that ordering would reject this transcript too.
- **It happens when context is already full.** Compaction runs in long sessions, which hold the most work.

## Reproduction notes

This was not reproduced for this report. The steps below come from the observed shape; they were not run.

1. Run a long session on a provider that requires the first non-system message to be a user message, such as `claude-subscription`.
2. Let the context grow until Hermes compacts it, with the cut point right after an assistant tool call and its result, so that a complete assistant(tool call)+tool group sits at the boundary.
3. Inspect the compacted transcript (for example, the next request dump). The bug is present if rows 1–2 are assistant (tool call) and tool, and the summary user row comes after them.
4. Send any message. The provider rejects the request, and every later request is rejected too.

A provider-independent check: after compaction, assert that the first non-system message has role `user`.

## Evidence files

- `request_dump_20261014_143605_3cfae369_20261018_195713_189121.json` (82 messages).
- `request_dump_20261014_143605_3cfae369_20261018_200415_533607.json` (83 messages).

The controller read these dumps on 2026-10-18. They are not in this repository and were not opened for this report. They hold real transcript content, so share them upstream only after redaction, with the role sequence alone.

## Suggested upstream fix

In Hermes's context compactor:

- **Keep a user turn first.** After building the compacted list, ensure the first non-system message is a user message. If the boundary leaves assistant/tool rows ahead of the summary, place the summary user row first and the kept rows after it, or fold the leading rows into the summary and drop them.
- **Move whole groups.** Never split an assistant tool-call message from its results while moving or dropping rows.
- **Add a regression test.** Compact a history whose cut falls right after a complete assistant(tool call)+tool group, then assert that the result starts with a user turn after the system prompt and that every tool result follows its call.
- **Optionally validate.** Check the compacted list before saving it, so a bad shape fails at compaction time rather than wedging every later request.

## Local mitigation reference

The rejecting check is `History.rebuild` in `plugins/model-providers/claude-subscription/history.py` (baseline lines 82–86, added in commit `48ef2074`, "Rebuild a Claude subscription session from an existing transcript"). It removes an optional leading system message, then requires the first remaining message to be from the user and the last to be from the user or a tool. See the [transcript-rebuild spec](../specs/261017-claude-subscription-transcript-rebuild.md) and the [provider README](../../plugins/model-providers/claude-subscription/README.md).

Making the provider tolerate this shape is tracked separately on the provider's rebuild card. That work would let `claude-subscription` recover from this shape; it does not fix the compactor, and other strict providers would still fail.

Files under `docs/bugs/` are evidence and triage input, not implementation authorization. This report changes no source, provider, or live configuration.
