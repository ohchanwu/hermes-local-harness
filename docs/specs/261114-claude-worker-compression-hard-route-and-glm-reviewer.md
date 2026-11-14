# Request to harness-orchestrator: Claude worker compression threshold, `very_hard` route, GLM first for `hard` cards, GLM reviewer before the Opus reviewer

Written 2026-11-14 22:35 KST by the `advisor` profile (advisor session `20261113_053932_e5a3aee6`). Extended 2026-11-14 23:00 KST with Part 6, the section "How to carry this out" and facts re-read at the new `main`. Changed later the same night on the owner's instruction: the peak-hours hold window rule in Part 6 step 2.
Harness repository `/Users/chanbla11mit/hermes-local-harness`, `main` at `c9e91312f2583d960b21fe2ef8787d1da6fb048d`, working tree clean when read. Hermes checkout `/Users/chanbla11mit/.hermes/hermes-agent` at `9cf7960f27`.
The advisor changed nothing. harness-orchestrator creates its own cards from this file and may rewrite any proposed wording.

## Owner approval and status

- Source: the request file that the `advisor` profile wrote for `harness-orchestrator` on 2026-11-14, SHA-256 `2bc8c3dda0d03e42169a8cfe7f39d9e40bfc35d2d96943856cdc42f17b988ac5`. Card `t_1041f143` on board `harness` copied it into this repository with two changes: this section was added, and the three mentions of the Hermes checkout directory were changed to the full path.
- Owner, Telegram direct message to `harness-orchestrator` on 2026-11-14, about that file: "carry it out. I approve it, including clause B."
- Clause B of the `very_hard` criterion in Part 2 is therefore approved.
- The owner's message changes none of the advisor's choices inside Part 6 that the section "Authority" lists, so those choices apply.
- Where the section "Authority" says "the owner's message that delivers this file", it means the message quoted above.
- Status: approved. The work is done by separate cards on board `harness`. Each live deployment is a separate card.

## How to carry this out: one objective, many cards

Owner, 2026-11-14: "it should be kind of like a campaign. It should be made clear to the Harness orchestrator that this is a campaign that's meant to be split up into many cards."

Here the owner's word "campaign" means: one objective (fewer Claude tokens at the same review standard), carried out as many small cards over several days, with separate deployments and a measurement report after each.

Do not create one card per Part. The splitting paragraph at line 61 of the harness-orchestrator skill `multi-agent-coding-orchestrator` applies: one card for each part that has its own acceptance check, a design decision on its own card, links only where one card needs another's result or both change the same files. Small cards that name their files and check command can themselves run on GLM workers.

Proposed cards. harness-orchestrator decides the final split and order.

- Group A, no dependencies:
  - A1: Part 1, repository change.
  - A2: read-only report on the "Not verified" items for Parts 2 to 4 (reasoning effort key, behaviour at the Z.ai usage limit, four criteria, readers of `glm_workers`). No commit.
  - A3: design decision for Part 6: how the first reviewer passes a card to the second (Part 6 step 4). Report with a proposal; read the Hermes source first and use `procedures/isolated-hermes-test-home.md` only where reading does not settle a point.
- Group B, `hard` route, after A2:
  - B1: Part 2, `config.json` routes and criterion texts, with tests.
  - B2: Part 3, the GLM workers at `max` and every reader of the worker lists.
  - B3: Part 4, a limit per route in `handle_request_changes`.
  - B4: Part 5 for B1 to B3: procedure, policy sentences, report script.
- Group C, GLM reviewer, after A3; C3 and C4 after B3 because they change the same functions:
  - C1: roster, verifier, snapshot and fixtures for five GLM reviewer profiles.
  - C2: policy sources: the five GLM reviewer `SOUL.md` files and the changed sentences in the Opus reviewer `SOUL.md` files and orchestrator skills.
  - C3: plugin: reviewer chosen at the review request; a GLM reviewer cannot mark a card done; GLM review runs wait during the peak-hours hold window.
  - C4: plugin: which change requests count, and the return of the card to its worker.
  - C5: procedure text and report script for Part 6.
- Group D, live deployment, each on its own card with owner approval:
  - D1: Part 1 on the ten live configs.
  - D2: `hard` route: plugin copy, reasoning effort of the `max` workers, policy files.
  - D3: GLM reviewer: profiles, the owner's Z.ai logins, plugin copy, policy files, then the switch of Part 6 step 7.
- Group E: the two reports named under Acceptance.

Deploy D2 and D3 separately so that each report can say which change a card ran under. D3 does not have to wait for the report on `hard` cards.

## Authority

All quotes are the owner's Telegram messages to the advisor on 2026-11-14.

- Part 1: "create a new handoff file for the harness worker that sets compression threshold tokens to 300,000 on the 10 Claude worker profiles, leaving the rest unchanged."
- Parts 2 to 5: "let's also implement the very hard category idea that I had earlier, and let's actually make it 3 attempts for the GLM worker for hard cards."
- The earlier idea, same day: "starting a hard card by first attempting it with GLM full set on max effort. If it fails consecutively twice, then route it to a Claude worker (but with the option of the Claude worker being able to reference or even just continue from the GLM worker's previous state, so that the Claude worker can just not start from scratch)." and "perhaps we can make a separate, very, very hard category that is exclusively routed to Claude." The later message replaces "twice" with 3 attempts.
- Definition of very hard: "I think that \"very hard\" would be these sensitive areas, plus if there's ambiguity or if it's a very complex problem." The sensitive areas named in that message are authentication, secrets, payment, migration and production work.
- Examples that must not be very hard: "Let's say that it's authentication, but it's simply implementing a session cookie or something. Then that shouldn't be very hard. That should be medium, even, or just hard." and "Let's say that it's payment, but it's simply making a request to a Stripe API endpoint, and that's not very hard. It's just maybe at most hard."
- Owner's reason: "we have the Claude Opus 5.5 reviewer, by the way, to review this stuff."
- Part 6: "Implement a reviewer pipeline where you pass worker output first to a GLM reviewer (GLM full). If the GLM full reviewer catches stuff, then you don't pass the result to the Claude reviewer. You just send it back to the worker model to fix those. If the GLM full reviewer doesn't catch anything, then you pass that to the Claude reviewer. The Claude reviewer tries to find something. If it doesn't find anything, good, work done. If it does find something, you pass that back to the workers for them to fix."
- Part 6, limits: "This would necessitate giving the GLM workers a bit more leeway on the escalation pipeline because now they're going through a harder gauntlet."
- Part 6, scope: "I agree on starting it on GLM work cards only."
- Part 6 joined to this request: "I'd like to add this to the hard route request".
- Not authorized by the quotes above: clause B of the `very_hard` criterion in Part 2. It is the advisor's addition. The owner's message that delivers this file approves it or removes it. If that message says nothing about clause B, leave clause B out.
- The advisor's choices inside Part 6, reported to the owner in chat on 2026-11-14. They apply unless the owner's delivery message changes them:
  - the form of the extra allowance: only change requests of the Opus reviewer count towards the limits 3 and 5, and the GLM reviewer may return a card at most 2 times;
  - once the Opus reviewer has reviewed a card, later reviews of that card go to the Opus reviewer directly;
  - reasoning effort `max` for the GLM reviewer.
- Part 6, peak-hours hold window (this replaces the advisor's earlier choice that such cards go to the Opus reviewer): "Yes, no GLM review at those times, but those cards don't go straight to Opus. Work is just blocked: no work on cards that normally depend on GLM agents." and "It's basically just a rest period for the easy, medium, and hard cards."

## Goal

1. Claude worker sessions compress at 300,000 tokens instead of 500,000.
2. A card that Jev classifies as `hard` is worked first by a GLM worker on `glm-5.3` at reasoning effort `max`. After the third change request of the Opus reviewer the card goes to a Claude worker, which continues in the same worktree.
3. Only a card classified as `very_hard` goes directly to a Claude worker.
4. A card implemented by a GLM worker is reviewed first by a GLM reviewer on `glm-5.3`. Only a candidate that the GLM reviewer has no findings on reaches the Opus reviewer.
5. Every card is still approved by the Opus reviewer (`claude-opus-5-5`). The review standard is unchanged.

## Constraints

- Use Hermes configuration and the existing `jev` plugin extension points. Do not modify files under `/Users/chanbla11mit/.hermes/hermes-agent`.
- Every new plugin path fails open: when it raises or a command fails, the card keeps the state the earlier steps left, as the existing code does. One exception, Part 6 step 5: a plugin failure must never let a card be marked done without a review run of the Opus reviewer.
- No new secret values in files. Part 6 needs one Z.ai login per new profile; the owner performs it (`procedures/jev-plugin.md` lines 76 to 78).
- Log records keep the present rule: identifiers, counts and probabilities only, no card text.

## Facts verified (read-only, 2026-11-14 22:25 to 22:55 KST)

Compression:
- The ten Claude worker profiles are `anki-worker`, `anki-worker-2`, `chapt-worker`, `chapt-worker-2`, `harness-worker`, `harness-worker-2`, `jobcron-worker`, `jobcron-worker-2`, `jss-worker`, `jss-worker-2`. Each live `config.yaml` has `model.default: claude-opus-5-5` and no `compression:` section.
- Their trigger is 500,000 tokens: `procedures/anthropic-api-fallback.md` lines 103, 104 and 108 (1,000,000 × `compression.threshold` 0.5), and `agent.log` lines `threshold=500,000` of `jobcron-worker`, `jobcron-worker-2` and `jss-worker` on 2026-11-13 and 2026-11-14. The other seven profiles have no such log line; the advisor assumes the same value because the model is the same.
- Hermes uses the lower of the ratio trigger and `compression.threshold_tokens` (`hermes_cli/config.py`, `_show_compression_section`, text "takes lower of ratio vs absolute").
- Commit `c9e9131` (card `t_b906fda1`) changed `roster.yaml` `managed_profile_settings`: seven profiles (`advisor`, `default` and the five project orchestrators) with `compression.threshold_tokens: 200000` and `compression.min_tail_user_messages: 1`. The live configs of those seven profiles show both values. No Claude worker is in that group.
- `scripts/verify-state` `check_managed_setting_groups` (line 2167) checks two named groups, `managed_profile_settings` and `orchestrator_profile_settings`, and fails when two groups declare the same profile and key. `tests/test_managed_compression_settings.py` asserts the profiles and settings of the first group. `snapshots/sanitized-current-state.yaml` mirrors the roster.
- Since 2026-11-08 the Claude workers logged 4 compressions, all near 500,000 tokens. 19 of 173 Claude worker sessions averaged more than 200,000 prompt tokens per call; they hold 47% of the Claude worker prompt tokens (Hermes local counts, session averages).
- The value 300,000 is the advisor's judgement. No published source gives a number.

Router, `plugins/jev/routing.py` (unchanged between `5fc198c` and `c9e9131`):
- A route with `assignee_from` or `model` is treated as a route that sends the card to a GLM worker (`_glm_sum`, lines 286 to 298). Lines 369 to 382: when the sum of the probabilities of those routes is at least `routing.threshold` (0.6), the applied route is the one of them with the highest probability; on a tie, the one listed last. Otherwise a chosen route without `assignee_from` and `model` at 0.6 or more leaves the card unchanged; everything else is `below_threshold`, also unchanged.
- Consequence: adding `assignee_from`, `model` and `provider` to the `hard` route in `plugins/jev/config.json` sends `hard` cards to a GLM worker with no change to that decision code.
- Lines 399 to 404: the control group (project term: every n-th card of a board and applied route that would go to a GLM worker stays with the Claude worker). `routing.control_group_every` is 10.
- `handle_request_changes` (line 683) calls the tool first (line 711). Afterwards, when the assignee is in the board's `glm_workers` and the card has at least `routing.max_glm_change_requests` (5, one value for all routes) `changes_requested` events, the plugin runs `set-model <id> none`, then `reassign <id> <Claude worker> --reclaim`, then rewrites the `Assigned worker EXACT` body line. The count is `SELECT COUNT(*) FROM task_events WHERE task_id = ? AND kind = 'changes_requested'` (line 614): every reviewer's change requests count. The Claude worker is the `original_assignee` of the card's `route` record (`routed_claude_worker`, line 619).
- `handle_request_review` (line 569) runs in a GLM worker session and clears the model override before review.
- A middleware can pass changed arguments to the tool: `next_call(new_args)` at line 478 (`handle_create`); `hermes_cli/middleware.py` line 143 onward, `next_call(next_payload)`.
- The plugin's middleware handles four tools: `kanban_create`, `kanban_unblock`, `kanban_request_review`, `kanban_request_changes` (`plugins/jev/__init__.py` line 60).
- The routes are identical on the five boards (`jobcron`, `cha-pt`, `harness`, `jss-genr`, `anki`). Current `hard` criterion: "Everything else: a design decision, a fault with an unknown cause, logic for authentication, secrets or payment, writing a database migration, or commands that will be run against production, including deployment guides."

Continuing from the GLM worker's state:
- A reassigned card keeps `workspace_kind`, `workspace_path` and `branch_name` (columns of `tasks`). Four Jobcron cards (`t_942f06ba`, `t_bca57a36`, `t_c37eae11`, `t_e1594a3b`) have GLM worker runs and Claude worker runs on one `workspace_path`.
- Hermes gives a worker the section "## Prior attempts on this task" (`hermes_cli/kanban_db.py` line 4171).

Reasoning effort:
- The fifteen board GLM worker profiles have `reasoning_effort: high` in the `model:` section of `config.yaml`.
- `glm-5.3` accepts `low`, `high` and `max` (https://docs.z.ai/guides/llm/glm-5.3). Hermes maps to `low`, `medium`, `high`, `max` for it (`agent/reasoning_effort.py` line 78).
- Hermes has a per-card value: column `tasks.reasoning_effort` (`hermes_cli/kanban_db.py` lines 1007 to 1011), setter `set_reasoning_effort` (line 1690), and the dispatcher adds `--reasoning <level>` to the run command (`hermes_cli/kanban_db_dispatch.py` lines 2769 to 2770). The code at those lines does not check which profile the run is for.
- The `kanban_create` tool takes `model` and `provider` but no reasoning effort (`tools/kanban_tools_schemas.py` lines 516 and 522). `hermes_cli/kanban.py` and `hermes_cli/kanban_parser.py` contain no match for "reasoning". Only the dashboard plugin calls the setter (`plugins/kanban/dashboard/plugin_api.py` line 616).

Review mechanics in Hermes (`hermes_cli/kanban_db.py` unless another file is named):
- `request_review` (line 3426) accepts a card in status `running` or `ready` (lines 3516 to 3520), sets status `review` and, when `reviewer` is given, makes that profile the assignee. It records `implementer` as the profile of the card's current run (lines 3489 to 3505) and `reviewer` on the `review_requested` event.
- The tool `kanban_request_review` checks only that the named reviewer is an installed profile (`tools/kanban_tools.py` lines 873 to 904).
- The dispatcher starts the review run on the card's assignee (`hermes_cli/kanban_db_dispatch.py` line 2427, lane `review`).
- `request_changes` (line 3575) requires a run that was claimed from `review`, gives the card back to the `implementer` of the latest `review_requested` event, and writes a `changes_requested` event whose payload has `reviewer`, the profile that requested the changes.
- When a review request names no reviewer after a change request, Hermes uses the reviewer of the latest `changes_requested` event (`_prior_reviewer`, line 3555). The harness cards name the reviewer: `Reviewer EXACT harness-reviewer.` (harness-orchestrator skill line 53) and `kanban_request_review(..., reviewer: harness-reviewer, board: harness)` (line 212).
- `reclaim_task` (line 2638) returns a run that was claimed from `review` to status `review` (`_retry_status_for_run`, line 2406 onward); `assign_task` (line 1625) then accepts a new assignee. `hermes kanban reassign <id> <profile> --reclaim` does both (`hermes_cli/kanban_parser.py` line 261).
- Consequence: when a GLM reviewer run itself calls `kanban_request_review` with the Opus reviewer, Hermes records the GLM reviewer as `implementer`, and a later change request of the Opus reviewer returns the card to the GLM reviewer profile, not to the worker.

Reviewer profiles:
- The reviewer profiles are `harness-reviewer`, `jobcron-reviewer`, `chapt-reviewer`, `jss-reviewer`, `anki-reviewer`, all `claude-opus-5-5` on `claude-subscription`. No GLM reviewer profile exists.
- `roster.yaml` `project_fleets.<board>.reviewer` holds one profile. `scripts/verify-state` pins the role `project independent reviewer` to `claude-opus-5-5` (lines 378 and 379) and lists the allowed assignees of each board (lines 1064 to 1067).
- The reviewer `SOUL.md` files name the implementation profiles whose cards the reviewer accepts and the sentence about the fifth change request (`policies/profile-souls/harness-reviewer/SOUL.md` lines 1 to 5).
- Precedent for five new GLM profiles: card `t_f4ce916d` (commit `d337def`) and card `t_55432326`; `procedures/jev-plugin.md` lines 69 to 87. A cloned profile has no `auth.json`; the owner runs `hermes -p <profile> auth add zai` for each.

Size and limits (Hermes local counts):
- `hard` route records from 2026-11-12 23:01 to 2026-11-14 21:28 KST: 25, of which 22 have Claude worker runs. Those runs used 550M tokens. Their reviews used 163M tokens over 38 review runs (median 2.5M per run, mean 4.5M). Of these, the 14 review runs that requested changes used about 102M (the advisor's sum of per-card figures rounded to 0.1M).
- First review of that Claude work: 12 change requests, 9 approvals, 1 blocked.
- All Opus review runs from 2026-11-12 23:01 to 2026-11-14 22:42 KST: 71 runs on 50 cards, 212M tokens. 21 requested changes (121M, median 5.0M per run). 50 approved (91M, median 1.3M per run).
- Of these, on cards whose first worker run was a GLM worker: 26 runs, 35M tokens. 6 requested changes (14M, median 1.8M). 20 approved (21M, median 0.9M).
- A Claude worker run after a change request: 15 runs, 72M tokens, median 4.2M.
- GLM tokens per day: 56M on 2026-11-13, 46M on 2026-11-14 up to 21:28. The plan's usage limit was reported in the GLM worker error logs on 2026-11-13 in the hours 09, 10 and 20.
- `peak_hold` holds cards of GLM workers on Monday to Friday from 15:00 to 19:00 Asia/Seoul. It selects cards in status `ready` or `todo` (`plugins/jev/peak_hold.py` line 244), so it does not hold a card in status `review`.
- Other files that name the routes or the limit: `scripts/jev-report` line 104 (`SAVINGS_ROUTES = ("easy", "medium")`); the sentence about the fifth change request in the five orchestrator skills, the five reviewer `SOUL.md` files and `procedures/jev-plugin.md` (lines 5, 6, 226, 231, 254, 284 to 288); tests `test_jev_routing.py`, `test_jev_client.py`, `test_jev_peak_hold.py`, `test_jev_report.py`, `test_jev_route_notice.py`, `test_jev_routing_policy_text.py`.

## Not verified (the worker checks these first and reports)

Parts 1 to 4:
- The command or harness step that writes one key into a live profile `config.yaml` (Part 1 deployment).
- Which key gives a dispatcher-started worker its reasoning effort: the GLM profiles set it under `model:`, and the comment at `kanban_db.py` line 1010 names `agent.reasoning_effort`. Confirm from a request log that a run sends `max`.
- How many more GLM tokens a card uses at `max` than at `high`.
- What Hermes does with a card when a GLM run stops on the plan's usage limit: retry, block, or count towards `consecutive_failures`. Report the observed behaviour for a worker run and for a review run; no card may stay unworked or unreviewed without a visible state.
- Whether Jev answers with four criteria as it does with three (`route_question`, line 195, sets no limit).
- Every reader of `glm_workers`: `routing.py` line 723, `peak_hold.all_glm_workers`, `scripts/jev-peak-hold`, `scripts/jev-report`, `scripts/jev-route-notice`.
- Whether the Z.ai plan can carry the added load of `hard` cards at `max` plus the GLM review runs. The advisor has no figure for the plan's limit.

Part 6:
- Whether Hermes accepts `kanban_request_review` from a run that was claimed from `review`. The source lines read check only the card status and the run ID; `_worker_guard` and `_goal_gate` in `tools/kanban_tools.py` were not read in full.
- Whether `hermes kanban reassign <id> <profile> --reclaim`, started from inside the review run that holds the claim, finishes: `reclaim_task` terminates the process recorded as the card's worker before it updates the card.
- How many of the Opus reviewer's findings a `glm-5.3` reviewer also finds, and how often it requests a change that the Opus reviewer would not. No data exists.
- How to hold a card in status `review` during the peak-hours window and return it to `review` with the same assignee afterwards. `hermes_cli/kanban_db.py` lines 3741 to 3742 and 3776 mention a resume status `review`; the advisor did not read that code.
- Whether a profile on provider `zai` works with the `review` toolset and the reviewer policy files as the GLM worker profiles work with theirs.

## Part 1: compression threshold of the ten Claude workers

1. Add a third managed settings group to `roster.yaml`, for example `claude_worker_profile_settings`, with the ten profiles named above and the single setting `compression.threshold_tokens: 300000`. Do not add the other three compression settings of the first group; the owner asked for this one value only.
2. Add the group to `check_managed_setting_groups` in `scripts/verify-state`, mirror it in `snapshots/sanitized-current-state.yaml`, regenerate the fixtures and extend the tests.
3. Correct `procedures/anthropic-api-fallback.md` lines 103, 104 and 108 where they state 500,000 as the present trigger of the workers.
4. No other profile changes: the reviewers, the GLM workers and the GPT profiles keep the Hermes default, and the seven profiles at 200,000 keep that value.

## Part 2: routes `hard` and `very_hard`

1. In `plugins/jev/config.json`, on every board, give `hard` the fields `assignee_from`, `model` `glm-5.3` and `provider` `zai`, and add a fourth route `very_hard` after it with no `assignee_from` and no `model`.
2. Proposed criterion texts. `easy` and `medium` stay as they are.
   - `hard`: "Everything that is not easy, medium or very hard: a design decision, a fault with an unknown cause, or logic for authentication, secrets, payment, a database migration or deployment when the card states the required behaviour. The topic alone does not make a card very hard."
   - `very_hard`, clause A (owner's definition): "Work on authentication, secrets, payment, a database migration or production systems, and in addition either the card leaves the required behaviour or the approach undecided, or the problem is very complex: many parts that depend on each other and must be worked out together."
   - `very_hard`, clause B (advisor's addition, see Authority): "Also any card whose worker itself runs commands against production or against the live Hermes installation." Reason: the reviewer sees such commands only after they have taken effect, so the review cannot prevent a wrong command. The `harness` board has such cards, for example `t_ac898be6` (install the plugin on all 36 profiles).
3. Consequences to state in `procedures/jev-plugin.md`:
   - The sum that is compared with 0.6 now includes `hard`. A card goes to a GLM worker when `easy` + `medium` + `hard` is at least 0.6, even when `very_hard` is the single most probable route, for example 0.25 / 0.36 / 0.39 for `medium` / `hard` / `very_hard`.
   - On a tie between `medium` and `hard` the applied route is `hard`, because it is listed later.
   - Every tenth `hard` card of a board stays with the Claude worker as the control group.
   - `hard` cards are held from 15:00 to 19:00 on Monday to Friday like other GLM cards.
4. The two conditions for applying a route are unchanged: the orchestrator left `model` empty, and the assignee is one of the board's `implementation_workers`.
5. Cards that exist when the change is deployed are not rerouted.

## Part 3: reasoning effort `max` for `hard` cards on a GLM worker

Requirement: the GLM run of a `hard` card uses `max`. Reviewer runs and the Claude worker after reassignment keep their own effort. `easy` and `medium` cards stay at `high`.

Two ways were found. The advisor recommends B. If harness-orchestrator prefers A or a third way, propose it to the owner before implementing.

- **A, per-card value.** Set `tasks.reasoning_effort` to `max` after creation. No tool argument and no `hermes kanban` subcommand does this, so the plugin would import `hermes_cli.kanban_db` or call the dashboard API. The dispatcher applies the value to every run of the card, so by inference the reviewers and the Claude worker after reassignment would also run at `max` unless the plugin clears the value at review and at reassignment and sets it again after a change request.
- **B, profile value.** On each board, take `<board>-worker-glm-3` out of `glm_workers`, put it in a new list, for example `glm_max_workers`, set that profile's reasoning effort to `max`, and give `hard` `assignee_from: glm_max_workers`. No per-card state and no Hermes internals. Costs: `easy` and `medium` cards alternate over two GLM workers instead of three, and one `hard` card per board runs on GLM at a time. Every reader of `glm_workers` listed under "Not verified" must also read the new list, so that reassignment after change requests, the peak-hours hold and the clearing of the model override at review apply to these workers.

## Part 4: three GLM attempts for `hard` cards

1. Allow a route to carry its own `max_glm_change_requests`. Set `3` on `hard`. `easy` and `medium` keep the general value 5.
2. In `handle_request_changes`, use the limit of the card's applied route, read from the card's `route` record in `decisions.jsonl` as `routed_claude_worker` reads it; with option B the worker list of the assignee gives the same answer. When neither is found, use the general value.
3. Meaning of the value 3, the same as today's 5: the third counted change request sends the card to the Claude worker. A crash, a timeout or a usage-limit stop is not a change request and does not count; say so in the documentation. Part 6 step 3 changes which change requests are counted.
4. The reassignment steps are unchanged. Check in a test that the Claude worker gets the same `workspace_path` and branch, and add `applied_route` and the limit used to the `escalate` record.

## Part 5: documentation, policy text, report

1. `procedures/jev-plugin.md`: the four routes, the criterion texts, the two limits, the consequences listed in Part 2 step 3, and the review order of Part 6.
2. The five orchestrator skills and the five reviewer `SOUL.md` files: change the existing sentences that name three routes and the fifth change request. Do not add new rules beside them. Owner preference of 2026-11-14: "We need to also find stuff to remove."
3. `scripts/jev-report`: include `hard` in the routes whose Claude tokens saved are reported, with its control group.
4. Update the tests listed under "Facts verified".

## Part 6: GLM reviewer before the Opus reviewer

Scope: cards whose current implementer is a GLM worker, on all five boards, including `hard` cards on the `max` worker. A card implemented by a Claude worker, also a control-group card and a card after reassignment to a Claude worker, goes to the Opus reviewer as today.

1. **Profiles.** One GLM reviewer per board, for example `<board prefix>-reviewer-glm`: model `glm-5.3`, provider `zai`, reasoning effort `max` in the profile's own config, the `review` toolset, the `jev` plugin. Add them to the roster with a role name of their own (the role `project independent reviewer` is pinned to `claude-opus-5-5`), to the verifier's allowed assignees, and to a new list per board in `plugins/jev/config.json`, for example `glm_reviewers`.
2. **Which reviewer gets a review request.** In `handle_request_review`, in a GLM worker session only, pass the board's GLM reviewer as `reviewer` to the tool when all of these hold; otherwise leave the argument unchanged, so the Opus reviewer named on the card reviews:
   - the card has no `changes_requested` event whose payload `reviewer` is the board's Opus reviewer;
   - the card has fewer than `max_glm_review_change_requests` (new setting, value 2) `changes_requested` events whose payload `reviewer` is a GLM reviewer.
   Reason for the second condition: without it a GLM reviewer could return a card any number of times and the Opus reviewer would never see it.
   **Peak-hours hold window (owner decision, see Authority).** The window does not change which reviewer is chosen. While the hold is active (Monday to Friday, 15:00 to 19:00 Asia/Seoul, and the hold switch is on), no GLM review run starts: a card whose review request went to a GLM reviewer waits in a visible held state and is reviewed by the GLM reviewer after the window ends. It is not passed to the Opus reviewer instead. `peak_hold` selects only cards in status `ready` or `todo` today, so this needs an addition for cards in status `review` whose assignee is in `glm_reviewers`. A GLM review run that is already running when the window starts is handled the same way as a GLM worker run that is already running; report which that is. The advisor's reading, not stated by the owner: a review run of the Opus reviewer on a GLM-worked card (after the GLM reviewer had no findings, or after its 2 returns) is not held, as today.
3. **Which change requests count.** In `handle_request_changes`, count towards the limits of Part 4 only `changes_requested` events whose payload `reviewer` is not one of the board's `glm_reviewers`. Result in the worst case: a `hard` card gets 5 GLM worker attempts (2 returned by the GLM reviewer, 3 by the Opus reviewer) and at most 3 Opus review runs before it goes to the Claude worker; an `easy` or `medium` card gets 7 and 5.
4. **Passing a card from the GLM reviewer to the Opus reviewer** when the GLM reviewer has no findings. This is the design decision of card A3. Requirements:
   - after the GLM reviewer has no findings, the card's next run is a review run of the Opus reviewer;
   - a change request of either reviewer returns the card to the worker that implemented it, never to a reviewer profile;
   - no change under `/Users/chanbla11mit/.hermes/hermes-agent`.
   Two candidates were read in the source; neither is tested:
   - **a.** The GLM reviewer calls `kanban_request_review` with the Opus reviewer. Hermes then records the GLM reviewer as `implementer` (see "Review mechanics"), so after a change request of the Opus reviewer the plugin must reassign the card to the GLM worker named as `implementer` in the last `review_requested` event that a worker wrote, as it already reassigns after the limit. If that reassignment fails, the card is `ready` on a reviewer profile; the GLM reviewer's `SOUL.md` must then tell it to block a card it did not claim from `review`.
   - **b.** The plugin runs `hermes kanban reassign <id> <Opus reviewer> --reclaim` for the GLM reviewer. By the source the card returns to `review` with the Opus reviewer as assignee and the `implementer` record stays the worker. Not verified: whether the command finishes when it terminates the run that started it.
5. **A GLM reviewer cannot mark a card done.** Add `kanban_complete` to the plugin's middleware: in a GLM reviewer session it returns an error and does not call the tool. This path fails closed (see Constraints). State the same in the GLM reviewer's `SOUL.md`.
6. **Policy text.** The GLM reviewer's `SOUL.md` starts from the board's reviewer `SOUL.md`, with: the card's `Reviewer EXACT` line names the Opus reviewer and that is not a mismatch; findings go back with `kanban_request_changes`; no findings means the step chosen in step 4; never `kanban_complete`. In the Opus reviewer `SOUL.md` files and the orchestrator skills, change the existing sentences so that an earlier GLM review run on a card is not treated as a mismatch.
7. **Switch.** One setting, for example `routing.glm_review.enabled`, default false in the repository. When false, step 2 never changes the reviewer and the behaviour is today's.
8. **Report.** `scripts/jev-report`: per board, cards that had a GLM review, change requests by the GLM reviewer, and the Opus reviewer's first outcome on candidates that the GLM reviewer had no findings on.

## Deployment

Out of scope for the implementation cards; it follows the harness rules for a separate deployment card and owner approval.
- Part 1: write `compression.threshold_tokens: 300000` to the ten live configs, then run `scripts/verify-state`. A worker run started afterwards uses the value.
- Parts 2 to 5: install the plugin copy on all profiles (`config.json` is read on every call), write the reasoning effort of the five `glm-3` profiles if option B is used, and update the ten policy files.
- Part 6: create the five GLM reviewer profiles by the procedure of `procedures/jev-plugin.md` lines 69 to 87; the owner runs `hermes -p <profile> auth add zai` for each of the five; install the plugin copy and the policy files; set `routing.glm_review.enabled` to true last.

## Rollback

Revert the commits. Live:
- Part 1: remove the `compression` key from the ten Claude worker configs (the trigger returns to 500,000).
- Parts 2 to 5: restore the earlier `config.json` and `routing.py`; restore `high` and the `glm_workers` membership of the five `glm-3` profiles; restore the earlier policy sentences. A `hard` card that is with a GLM worker at rollback is reassigned to its `original_assignee` by hand.
- Part 6: set `routing.glm_review.enabled` to false. A card that is in `review` with a GLM reviewer at that time is reassigned to the board's Opus reviewer by hand. The five profiles can stay installed and unused.

## Out of scope

- A compression threshold for reviewers, GLM workers or GPT profiles: the owner said "leaving the rest unchanged".
- GLM review of cards implemented by a Claude worker: the owner said "I agree on starting it on GLM work cards only." Reason: a wrong change request on such a card starts a Claude worker run (median 4.2M tokens).
- Approval of any card by a GLM reviewer alone: the owner's pipeline passes every candidate without GLM findings to the Claude reviewer.
- Changing `routing.threshold` or `routing.control_group_every`: not asked.
- An automatic move to a Claude worker or to the Opus reviewer when the GLM plan's limit is reached: not asked; report the observed behaviour first (see "Not verified").

## Acceptance

- The harness test suite passes with the commands that the harness cards normally name.
- After deployment of Part 1, a Claude worker `agent.log` shows `threshold=300,000`.
- Report 1, after the first 10 cards with applied route `hard`, per board: cards approved within three counted change requests, cards reassigned to a Claude worker, reviewer tokens and Claude worker tokens on those cards, GLM usage-limit errors, the number of `very_hard` cards with their Claude worker tokens, and for each card whether Part 6 was switched on.
- Report 2, after the first 20 cards with a GLM review, per board: change requests by the GLM reviewer; the Opus reviewer's first outcome on candidates without GLM findings, compared with the present figure (6 change requests in 26 Opus review runs on cards first worked by a GLM worker); Opus reviewer tokens per card, compared with the present 35M over those 26 runs; GLM review tokens; cards that stayed in `review` longer than one dispatcher interval because of a GLM error.
