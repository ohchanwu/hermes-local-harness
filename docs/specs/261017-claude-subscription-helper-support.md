# Claude subscription provider: serve Hermes helper jobs

Status: approved 2026-10-17 by the owner, who chose "Claude provider" for helper jobs after deciding to stop using GPT from 2026-10-18. Autonomous execution up to the live-check gate.
Builds on the [hardening](261017-claude-subscription-provider-hardening.md) and [transcript rebuild](261017-claude-subscription-transcript-rebuild.md) specifications.

## 1. Problem

Hermes runs side jobs ("auxiliary tasks") besides the main conversation: compression summaries, title generation, command-approval checks, image analysis, memory query rewriting and others. With `auxiliary.<task>.provider: auto` they inherit the main model; today every Claude profile pins them to OpenAI Codex, which goes away on 2026-10-18. On this provider they fail for four reasons found in Hermes `v0.21.5`:

1. **Async callers.** `async_call_llm` (image analysis, plugin `ctx.llm`, some pipelines) awaits `client.chat.completions.create(...)` on the event-loop thread. The client rejects running loops, and the `HERMES_SKIP_ASYNC_WRAP` flag, which prevents Hermes from rebuilding a plain HTTP client, also stops Hermes from moving the call to a thread.
2. **One shared client.** Hermes caches one helper client per profile and task and shares it across concurrent callers. The client rejects a second concurrent `create`.
3. **Unrelated conversations on one client.** Each helper call is its own conversation, but the cached client accepts only exact extensions of its own history.
4. **Options and content.** `extra_body.response_format` (title generation) is rejected; very small output caps (approval: 16 tokens) cannot fit the model's always-on thinking; images (`image_url` parts) are rejected.

Hermes already drops `temperature` for this model family, and async callers accept a complete response when they asked for a stream (`agent/auxiliary_client.py` `_build_call_kwargs`, `_acreate_with_progress`).

## 2. Behavior

1. **Async.** Called inside a running event loop, `create` returns an awaitable that runs the same request, non-streaming, in a worker thread. Sync callers are unchanged. `HERMES_SKIP_ASYNC_WRAP` stays, so Hermes never builds an HTTP client.
2. **Queueing.** A `create` that arrives while another request on the same client is in progress waits for it, up to that request's timeout, instead of failing. A caller that holds an unfinished stream and calls `create` again on the same thread gets an immediate error rather than a deadlock.
3. **New conversation on the same client.** When a request is not an exact continuation of the client's own conversation, or changes the tool list or output cap, the client ends its current CLI session (reaping the process group and cancelling any parked tool call, which then never returns a result) and starts a new session from the request: a fresh start, or a rebuild as in the rebuild specification. Each reset records a `session_reset` audit entry. A change of model or execution scope (working directory, profile, Hermes home, Kanban task, session id) is still rejected.
4. **Options.** `extra_body.response_format` is accepted and ignored; the prompt already asks for the format. Any requested output cap below 4096 tokens is raised to 4096 for the CLI, because thinking counts toward the cap.
5. **Images.** A user message may be a list of `text` parts and `image_url` parts whose URL is a base64 `data:` URL of PNG, JPEG, GIF or WebP. These are sent to the CLI as image blocks. Remote image URLs, images in tool results, and other part types are rejected. When a conversation with images is rebuilt, each earlier image is replaced by an `[image not carried over]` note. The profile declares `supports_vision=True`.

## 3. Rollout

Pin all sixteen `auxiliary.<task>` blocks in every Claude profile to `provider: claude-subscription`, `model: claude-opus-5-5`. Pinning Opus explicitly keeps the helpers of Fable profiles (reviewers, Advisor) off Fable's weekly cap. Helpers run at the profile's effort setting.

## 4. Gates

```text
AUTO GATE — independent review
Actor: a non-authoring reviewer agent
Preconditions: implementation committed on wt/provider-hardening; offline suites green
Action: review the candidate diff against main
On failure: fix confirmed findings test-first, rerun suites, re-review the new SHA once
Retry identity: the candidate commit SHA
Automatic resume: a clean verdict hands the candidate to the live check
```

```text
AUTO GATE — live check (pre-authorized by the owner's choice of this option)
Actor: executor
Preconditions: clean review
Action: one smoke run with the existing phases plus an async call, two concurrent calls on one client, an unrelated conversation on the same client and one small image; then the rollout of §3 and one Kanban pilot
On failure: diagnose and fix test-first; no retry of the same SHA
Retry identity: the candidate commit SHA
Automatic resume: a pass completes the work
```
