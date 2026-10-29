# Cards made with the Hermes CLI command `hermes kanban create` had no notification subscription, so a card approval went unseen for 7 hours

Reported: 2026-10-30, by the Jobcron orchestrator (`jobcron-orchestrator`, filing session `20261004_175052_68e32b25`; board `jobcron`). Recorded from harness card `t_7701b44e`.

All times are KST (UTC+09:00). Source references are to the installed Hermes Agent (`/Users/chanbla11mit/.hermes/hermes-agent/`, commit `9cf7960f274e`), read without running, importing or changing it, and to this repository at commit `3bf9ec8`. The board database and the gateway log named below were not opened on this card; the evidence is the filing orchestrator's report.

## Summary
The Jobcron orchestrator runs only when a message arrives, either from the owner or from the gateway Kanban notifier. Six of its nine cards were made by an orchestrator script that called `hermes kanban --board jobcron create`. That command writes no `kanban_notify_subs` row and prints no warning, so the notifier never sent a notice for those six cards. The approval of card J8 at 2026-10-29 22:52:14 was not seen until the owner wrote at 2026-10-30 06:01, about 7 hours later. The immediate cause is that the orchestrator did not follow its own skill, which says to make cards only with the `kanban_create` tool. This repository now has a read-only check, `scripts/check-notify-subscriptions`, that lists the open cards of one board that have no `notify+wake` subscription.

## Observed
- Board `jobcron`. Cards: J1 `t_48915145`, J2 `t_5d345499`, J3 `t_7daed2a6`, J4 `t_3161d3db`, J5 `t_254404f4`, J6 `t_82a88a8c`, J7 `t_45cb20df`, J8 `t_decc4e63`, S1 `t_b14f705a`.
- J1 and J4 were made at 2026-10-28 23:32:41 with the `kanban_create` tool. J2, J3, J5, J6, J7 and J8 were made from 23:35:54 to 23:35:59 by an orchestrator script that called `hermes kanban --board jobcron create`.
- A read-only query of the board's `kanban_notify_subs` table by the filing orchestrator found rows for J1, J4 and S1, and no row for J2, J3, J5, J6, J7 or J8.
- On 2026-10-29, J6 review run 643 completed at 18:25:53, J8 implementation run 645 blocked at 20:54:38, and J8 reviewer run 647 approved the card at 22:52:14. No notice reached the orchestrator for any of these events, and nothing else started it, so the approved J8 was not merged until the owner wrote at 2026-10-30 06:01.
- The gateway log has `kanban notifier: woke agent for` lines to `jobcron-orchestrator` for the subscribed cards only, for example for `t_b14f705a` at 2026-10-29 16:56:28 (`review_requested`) and 17:14:59 (`completed`). It has no such line for `t_5d345499`, `t_7daed2a6`, `t_254404f4`, `t_82a88a8c`, `t_45cb20df` or `t_decc4e63`.
- The notifier itself worked that night: from 23:15 to 23:48 on 2026-10-29 it woke `anki-orchestrator` for the board `anki` cards `t_46246675`, `t_079b48b9`, `t_dad631b4` and `t_6023eb94`. Telegram reconnections occurred overnight but are not the cause, because the notifier attempted no delivery for J8.
- At 2026-10-29 20:41 the orchestrator recorded that the J6 approval "never reached" it, and did not check the subscription table at that time.
- Expected: a notice starts the orchestrator on `review_requested`, `blocked` and `completed` for every card it made and is waiting on.

## Impact
- An approved card waited about 7 hours for the next step. A blocked card and a completed review on the same board also produced no notice.
- Nothing in Hermes or in this repository reported that open cards had no subscription. The fault was found only after the owner asked.

## Cause
Each statement is marked "Established from source", "Reported" or "Not established".

### Orchestrator did not follow its skill
- Reported: the profile skill `multi-agent-coding-orchestrator`, section "Card Setup", steps 1 and 4, says to make cards only with the `kanban_create` tool and to confirm that the tool returned `subscribed: true`. The orchestrator did not follow it. The context compressor had removed that skill from the context (a `[SKILL_PRUNED]` marker), and the transcript shows no reload of the skill before the cards were made.

### The CLI create command writes no subscription and prints no warning
- Established from source: `_cmd_create` (`hermes_cli/kanban.py:334-391`) calls `kb.create_task` (`hermes_cli/kanban.py:362-379`), prints `Created <id>` (`hermes_cli/kanban.py:384`), and warns only when a ready, assigned card has no running dispatcher (`hermes_cli/kanban.py:385-390`). It does not call `add_notify_sub`. The `create` subcommand parser (`hermes_cli/kanban_parser.py:160-221`) has no subscription option.
- Established from source: `create_task` (`hermes_cli/kanban_db.py:1327`) writes subscription rows only by copying them from the card's parents (`_inherit_notify_subs`, `hermes_cli/kanban_db.py:1495`, `1534-1569`) and from the creator task when the caller is a dispatcher-owned worker (`inherit_creator_origin`, `hermes_cli/kanban_db.py:1494`; `hermes_cli/kanban_db_graph.py:8-22`; the creator task id is set only in that case, `hermes_cli/kanban.py:377-378`). A card made from an orchestrator's gateway session with the CLI command, without parents, therefore has no row.
- Established from source: the `kanban_create` tool handler (`tools/kanban_tools.py:1094-1154`) returns `subscribed` from `_maybe_auto_subscribe` (`tools/kanban_tools.py:1229-1258`). That function is enabled by `kanban.auto_subscribe_on_create`, default true (`hermes_cli/config_defaults.py:1897`), resolves the calling gateway session from the session context (`_resolve_notify_target`, `tools/kanban_tools.py:1183-1226`), and writes a row with delivery mode `notify+wake` for every platform except `tui` (`tools/kanban_tools.py:1225`) through `add_notify_sub` (`hermes_cli/kanban_db_notify.py:67-141`).
- Established from source: a row written without an explicit delivery mode gets `notify`, which sends a message but does not start the agent, except on platform `api_server` (`hermes_cli/kanban_db_notify.py:24-26`, `95-99`). The explicit command `hermes kanban notify-subscribe` (`hermes_cli/kanban.py:1154-1176`; parser `hermes_cli/kanban_parser.py:389`) can add the missing row afterwards.

### The notifier logs nothing for an event on a card with no subscription
- Established from source: the gateway notifier reads subscriptions, not events. `collect_board` (`gateway/kanban_watchers_notifier.py:325-354`) returns early when the board has no subscription owned by the profiles that the gateway serves (`gateway/kanban_watchers_notifier.py:277-290`, `327-328`), then lists the subscription rows (`gateway/kanban_watchers_notifier.py:341`) and claims unseen events of the kinds in `TERMINAL_KINDS` (`gateway/kanban_watchers_notifier.py:47`) for each row (`_claim_for_sub`, `gateway/kanban_watchers_notifier.py:302-323`). An event on a card that has no row is never read, so nothing is logged for it at any level. The only related messages are debug lines for a board with no subscriptions at all (`gateway/kanban_watchers_notifier.py:287-289`, `342-343`). The `woke agent for` line is written only after a wake (`gateway/kanban_watchers_notifier.py:605-607`).

### Not established
- Not established: whether other boards have open cards without a `notify+wake` subscription. No board database was read on this card.

## Repository change
- `scripts/check-notify-subscriptions --db PATH` opens one board's `kanban.db` in SQLite read-only mode (`mode=ro`) and makes no writes. It lists each open card (status other than `done` and `archived`; the full status set is `VALID_STATUSES`, `hermes_cli/kanban_db.py:106`) that has no `kanban_notify_subs` row with delivery mode `notify+wake`, a non-empty `notifier_profile` and a non-empty `user_id`. Output is one line `NO-WAKE-SUBSCRIPTION <id> <status> <assignee or -> <title>` per card, ordered by `created_at` and then id, with exit status 1; or `OK: <n> open cards, each with a notify+wake subscription` with exit status 0. A missing file, a missing table or an unreadable database gives one `ERROR:` line on standard error and exit status 2; the file is never made.
- `--db` has no default. The path must be given explicitly, because `HOME` can point at a Hermes profile directory instead of the user's home directory.
- How an orchestrator uses it on its own board: after making cards, and whenever it finds a card result without a notice, run `scripts/check-notify-subscriptions --db <absolute path of its own board's kanban.db>` from this repository, and for each listed card that it is waiting on, add the subscription with `hermes kanban notify-subscribe` (or report the gap to the owner). Adding this step to an orchestrator skill is not part of this card and needs a separate card.
- `tests/test_check_notify_subscriptions.py` covers the script with synthetic databases only.

## Requested
Changes requested from Hermes Agent (proposal parts 1 and 2; Hermes source is not changed from this repository):
1. Let `hermes kanban create` subscribe the calling session in the same way as the `kanban_create` tool when the command runs inside a gateway session (the same `_resolve_notify_target` lookup and `kanban.auto_subscribe_on_create` setting), or add an option to `create` that writes a `notify+wake` subscription for a given platform, chat and profile.
2. When `hermes kanban create` runs inside a gateway or agent session and writes no subscription, print a warning to standard error that names the card and the `hermes kanban notify-subscribe` command, in the same way as the existing warning for a missing dispatcher.

## Upstream status
Not checked: network access was not authorized on this card.
