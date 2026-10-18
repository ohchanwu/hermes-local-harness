# Telegram DM text with formatting entities reported dropped after admission

- Report date: 2026-10-18 (KST). Card `t_6f475561` (diagnosis and test only; the fix goes in a follow-up card).
- Status: **root cause not established.** The reported drop does not reproduce in the installed adapter for a well-formed `message.text` update. One silent receipt-without-delivery path is proven, and an expected-failure test covers it.
- Severity: silent loss of user input. The update is acknowledged and receipted, but no turn runs and nothing is logged.

## Environment

- Hermes Agent v0.21.5+6751.g9cf7960 (upstream `9cf7960f`), installed checkout `~/.hermes/hermes-agent`, used read-only.
- python-telegram-bot 22.8, from the install's committed venv.
- Telegram adapter: `plugins/platforms/telegram/` (`adapter.py`, `update_admission.py`, `telegram_entities.py`, `telegram_context.py`).
- Affected profile: `harness-orchestrator` (Telegram gateway, private chat).

## Observed

Owner report: DM text carrying formatting entities (for example `pre` from a copied code block, about 1k–4k characters) gets its update acknowledged and its receipt written, but produces no text batch, no turn and no log line. The same text sent plain works.

Metadata I checked (update ids and timestamps only, no content):
- I matched every receipt in `telegram_update_receipts_<bot>.json` against `gateway.log`, `agent.log` and `errors.log` within ±3 s.
- Receipts with no log line at all: `541220319` (20:56:49), `541220321` (20:57:20), `541220322` (20:57:30), `541220324` (21:16:24), `541220326` (22:34:53), `541220327` (22:45:42).
- None of these ids has a `Flushing text batch` line, an `inbound message` line, a WARNING/ERROR, or an exception.
- `541220320` and `541220323` coincide with slash-confirm and `session_reset` lines; those are commands and buttons, not losses.
- `541220328` (22:52:08) was delivered normally: a 3954-character batch was flushed and a turn ran. It fits "the plain retry works", but the logs cannot show whether the unlogged ids were formatted pastes.

## What the code and the synthetic test show

Path for a private-chat text update:
1. `TelegramApplication.process_update` claims the update (`update_admission.py:278-302`).
2. PTB's group 0 sends it to `filters.TEXT & ~filters.COMMAND` → `_handle_text_message` (`adapter.py:2990`, `6569-6581`), or to `filters.COMMAND` → `_handle_command` (`adapter.py:2991`, `6583-6600`) when the first entity is a `bot_command` at offset 0.
3. Text is batched by `_enqueue_text_event` (`adapter.py:6642-6648`), which also accepts the update. `_flush_buffered` then logs `Flushing text batch` and calls `handle_message` (`adapter.py:6650-6701`).
4. In parallel, group 99's `TypeHandler` → `_on_platform_update` (`adapter.py:3001`, `2846-2876`).

Where entities could matter, and why they don't for a DM:
- **`expand_link_entities`** (`telegram_entities.py:24-68`) acts only on `text_link`. It skips every other entity type before touching any offset. Its UTF-16 → code-point mapping returns `None` instead of raising.
- **Mention and command detection** (`_entity_sources` / `_entity_span` / `_message_mentions_bot`, `adapter.py:6062-6212`) runs only for group chats. `_should_process_message` returns True for any non-group chat (`adapter.py:6495-6496`), and `group_trigger_text` only strips the bot's own handle.
- **Batching** (`gateway/platforms/base.py:2574-2593`) is length-based and ignores entities. Texts at ~4k UTF-16 units take the longer split delay and still flush.
- **No broad `except`** on this path swallows an error after the receipt. A caught preparation error sets `claim.failed`, and that suppresses the receipt (`update_admission.py:260-276`).

Synthetic result through real PTB dispatch on the installed adapter, under an isolated home:
- Inputs: DM text of 1000 and 3900 code points (4024 UTF-16 units), with two non-BMP emoji before every entity.
- Entity variants: plain, `pre`, `code`, `bold`, a `bold`+`code`+`pre` mix, and `expandable_blockquote`.
- Result: every variant reaches the message handler exactly once, with text identical to the plain delivery (both trailing-whitespace-stripped). Each gets one receipt, nothing is held and no batch is left pending.
- An earlier scratch probe gave the same result at 4090 code points (over Telegram's limit) and for text starting with a `/path`-shaped `bot_command` entity.

### Proven silent receipt-without-delivery path

A claim counts as completed when *any* admitted callback returns without failing, including the group-99 observer:
- `admitted_callback` sets `claim.completed = True` (`update_admission.py:226`).
- `_release_claim` then writes the receipt (`:267-268`).
- The observer returns early when there is no `gateway_platform_event` hook (`adapter.py:2859`).

So an admitted `message` update that no group-0 core handler matches is receipted with no batch, no turn and no log line. That is exactly the reported symptom. The test demonstrates this with an unserved message shape (a dice message).

Two other silent returns exist:
- `_handle_text_message` / `_handle_command` return silently when `msg.text` is empty (`adapter.py:6572`, `6586`). PTB's `filters.TEXT` normally prevents that.
- Base `handle_message` may queue silently behind an active session; this is outside the adapter slice and not exercised here.

## Root cause: what remains unknown

The adapter does not drop a formatted `message.text` DM. The unlogged receipts are consistent with the update reaching admission **in a shape no core handler serves** (it took the observer-only completion path above). The other explanation is a loss after `handle_message`, which would have logged `Flushing text batch` first for the text path. Which shape the owner's client actually sent is not recorded anywhere I may read.

**The single observation that would decide it:** the update's top-level field and its message's field names, with no values, for one unlogged receipt id such as `541220326` or `541220327`. Examples: `message` with or without `text`, `caption`, `document`, `quote`/`external_reply`, or another update type. The next repro could capture this with a metadata-only DEBUG line at admission.

## Test

`tests/test_telegram_formatted_dm_drop.py`. It is hermetic:
- temporary `HERMES_HOME` via `tests/hermes_isolated_home.py`;
- the committed venv interpreter with `-I -B`;
- a stub Bot API request that answers only `getMe`;
- INET sockets blocked;
- synthetic text only.

Run from the worktree root:

```
python3 tests/test_telegram_formatted_dm_drop.py
```

Result: `Ran 4 tests ... OK (expected failures=1)`.
- (a) **Plain control.** Plain 1k/4k DM text is delivered once.
- (b) **Formatted variants.** Every formatted variant is delivered once, equal to plain. These are plain assertions, not expected failures, because the drop does not reproduce.
- (c) **Proven path.** The unserved update is receipted with no delivery and no INFO+ log. `test_unserved_update_is_not_silently_receipted` is the `expectedFailure` for the no-silent-loss invariant; it flips to an unexpected success once such an update is logged or no longer receipted.

If the installed Hermes cannot be provided in an isolated home, the tests skip with the helper's reason; they never pass.

## Impact

- Any admitted update that no core handler serves is lost silently and marked done. Because a receipt is written, a Telegram redelivery is also suppressed.
- Operators get no log line to correlate with a user's "my message vanished".

## Fix options for the follow-up card

The installed Hermes source must not be modified locally.

1. **First, observe (recommended prerequisite).** Capture the decisive observation above, either from a gateway DEBUG line that already exists, or with the owner repeating the repro while a metadata-only update-shape log is enabled. Only then choose the fix for the formatted-paste symptom.
2. **Upstream patch (recommended fix for the proven path).** In `update_admission.py`, do not let the group-99 observer alone mark a claim completed. Alternatively, log at INFO (update id plus field names, no content) when an update is receipted without any core handler having served it.
3. **Harness-owned mitigation.** A Harness plugin registering a `gateway_platform_event`-independent observer cannot see group-0 matching without patching the adapter, so only a log/alert can be owned locally. Prefer option 2.

## Proposed fix

Card `t_a9b14c3c` implements option 2 as an upstream-ready patch. It has not been applied to the installed checkout or filed upstream.

- Patch: `docs/bugs/261018-telegram-unserved-update-receipt.patch`. It is a `git diff` against upstream `9cf7960f` and touches only `plugins/platforms/telegram/update_admission.py`.
- Behaviour:
  - Only a group-0 (core) callback completes a claim. The group-99 observer returning no longer does.
  - An update that nothing served or failed is therefore not receipted, so a Telegram redelivery is not suppressed.
  - Instead it logs one INFO line: `[Telegram] Update <id> matched no core handler; not receipted (fields: ...)`. The line carries the field names of the update and of its message (for example `message(chat,date,dice,from,message_id), update_id`). It never logs values, text, or chat/user ids.
  - Served updates, commands, callbacks, native plugin handlers and the failed-preparation path are unchanged.
- Test: `python3 tests/test_telegram_unserved_update_patch.py`. Inside the isolated home it copies the installed telegram package, applies the patch to the copy with `git apply`, and runs the same real-PTB dispatch against it. The test checks three things:
  - the unserved update is not receipted and logs exactly one names-only line;
  - plain and formatted DM text are each delivered once with one receipt;
  - the dispatch imported the patched copy.

  It skips with a reason if the copy cannot be prepared, and fails if the patch does not apply to its base blob. The `expectedFailure` in `tests/test_telegram_formatted_dm_drop.py` still targets the unpatched installed adapter. Once the patch is applied there, that test becomes an unexpected success and the current-behaviour mechanism test fails, so both need updating.
- Applying or filing it is a separate, attended owner step:
  - To file upstream: attach the patch file. Its header is the commit message.
  - To apply locally: run `git apply --check <patch>` and then `git apply <patch>` in the Hermes checkout, then restart the gateway.
- Next repro: the INFO line names the shape of every unserved update. That is the decisive observation above: for example, whether the formatted paste arrived as `message(...,text,...)`, with `caption`/`document`, or as another update type. It lands in `gateway.log` next to the update id.
