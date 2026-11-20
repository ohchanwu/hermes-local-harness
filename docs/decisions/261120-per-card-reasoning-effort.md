# Decision: reasoning effort of one Kanban card, set by the worker's `jev` plugin

Date: 2026-11-20

Card `t_caf5dba0` on board `harness` (this change). The provider side is card `t_db165633` on board `harness`: it changes `plugins/model-providers/claude-subscription` of this repository to accept the `extra_body` key `card_reasoning_effort`.

Hermes source read: `/Users/chanbla11mit/.hermes/hermes-agent` at commit `9cf7960f274ea2bdfe672d64d26389e9954dfeb6`. A file reference below without a leading directory of this repository (`plugins/jev/`, `scripts/`, `tests/`, `procedures/`, `docs/`) is relative to that Hermes directory. Nothing under that directory was changed.

## Decision

An orchestrator can give one card its own reasoning effort with one full body line:

```text
Reasoning effort EXACT <level>.
```

`<level>` is one of `low`, `medium`, `high`, `xhigh` and `max` (`reasoning_effort.allowed_levels` in `plugins/jev/config.json`). A card without the line runs at the reasoning effort of the profile of its worker, as before.

The `jev` plugin of the worker applies the level. `plugins/jev/reasoning_effort.py` is registered with `ctx.register_middleware("llm_request", ...)` (`plugins/jev/__init__.py`). Before every main model request of a dispatcher-started worker session, it:

1. does nothing unless `reasoning_effort.enabled` is `true`, `HERMES_KANBAN_TASK` and `HERMES_KANBAN_BOARD` are set, and the profile (`HERMES_PROFILE`, else the name of the profile directory of `HERMES_HOME`) is in `implementation_workers`, `glm_workers` or `glm_max_workers` of that board in `plugins/jev/config.json`. Reviewers, orchestrators and every other profile get no change;
2. reads the card once per process and task ID with the documented command `hermes kanban --board <board> show <task> --json` (timeout 15 seconds, no shell) and keeps the result, also the result "no level" and a failed read. It never opens a board database;
3. when the body has exactly one valid line:
   - provider `zai`, model name containing `glm-5.3`: sets the top-level `reasoning_effort` of the request to `low`, `medium`, `high` or `max` (`xhigh` becomes `max`);
   - provider `zai`, model name containing `glm-5.2`: `high` or `max` (`low` and `medium` become `high`, `xhigh` becomes `max`), the same mapping as `plugins/model-providers/zai/__init__.py` lines 31-42;
   - provider `zai` with `extra_body.thinking.type` equal to `disabled`: no change;
   - provider `claude-subscription`: sets `extra_body["card_reasoning_effort"]` to the level;
   - any other provider or model: no change.

`kanban_create` gets a notice in its result (JSON key `jev_note`) when the body has more than one line that starts with `Reasoning effort`, a level that is not allowed, or a line that starts with `Reasoning effort` and does not match the format. The card is created unchanged, and no database is written.

## Owner authority

- Owner, Telegram direct message to `harness-orchestrator`, 2026-11-20 (verbatim): "Both. Document this to harness docs, prominently, so we keep this in mind should anything break."
- Owner, 2026-11-20 (verbatim): "Yes, look harder for alt strats that're more upgrade-compat."
- Owner, 2026-11-20, choosing this design (design D: the worker's own `jev` sets the level of each model request from the card line, through the documented `llm_request` middleware, for GLM and Claude workers) (verbatim): "D"
- Owner, 2026-11-19 (verbatim): "GLM's weekly limit is spent anyway, so just route the cards to claude workers."

## Why the `kanban_create` tool cannot carry the value

Hermes stores a card field `reasoning_effort` (`hermes_cli/kanban_db.py` line 801; NULL means the setting of the profile), but the `kanban_create` tool does not pass one: `tools/kanban_tools.py` lines 1133-1149 call `kb.create_task(...)` with title, body, assignee, parents, tenant, priority, workspace, project, triage, idempotency key, runtime limit, skills, model and provider override, goal mode, completion contract, initial status, creator and session, and no `reasoning_effort`. `tools/kanban_tools_schemas.py` has no `reasoning_effort` property either. The body line is the one field that an orchestrator's Kanban tools can write and a worker can read.

## Rejected designs

- Store the level with the internal function `kanban_db.set_reasoning_effort` (`hermes_cli/kanban_db.py` line 1690) from the `jev` plugin at card creation (the earlier design of this card). Rejected: the function is not documented, it writes the board database directly, and the owner asked for a design that is more likely to keep working after a Hermes upgrade.
- Set the field through the dashboard REST API. Rejected: it needs the dashboard process to run, and the endpoint is not part of the documented plugin contract.
- Change the profile settings (`agent.reasoning_effort` in `config.yaml`) of the worker for each card. Rejected: it is a live profile change for every card, it applies to every card that the profile runs at the same time, and a failed reset leaves the profile at the wrong level.
- Add more worker profiles, each with a fixed level. Rejected: many more profiles to create, log in and keep in the roster, for a value that changes per card.

## Hermes behaviour this design depends on

| Behaviour | Source | Documented |
|---|---|---|
| A plugin registers request middleware with `ctx.register_middleware("llm_request", callback)`; the callback receives `request`, `original_request` and context keyword arguments and returns `{"request": {...}}` to replace the provider keyword arguments; a callback that raises is logged and skipped | `hermes_cli/plugins.py` lines 978-983; `hermes_cli/middleware.py` line 21 (`LLM_REQUEST_MIDDLEWARE = "llm_request"`) and lines 63-99; `hermes_cli/plugins_dispatch.py` lines 591-602 | Yes: `website/docs/developer-guide/plugins/index.md`, sections "Middleware: change what happens" (from line 1278, table row at line 1303, rules at lines 1307-1312) and "Native plugin compatibility contract" (line 112) |
| Hermes applies the `llm_request` middleware before every main provider request and passes `provider=` and `model=` | `agent/turn_api_request.py` lines 145-153 (`apply_llm_request_middleware(api_kwargs, task_id=..., model=agent.model, provider=agent.provider, ...)`) | The middleware kind is documented; the keyword arguments `provider` and `model` are not listed in the documentation (source reading only) |
| The dispatcher sets `HERMES_KANBAN_TASK` and `HERMES_KANBAN_BOARD` in the worker environment | `hermes_cli/kanban_db_dispatch.py` lines 2888 and 2929 | Yes: `website/docs/user-guide/features/kanban-worker-lanes.md` lines 37-39 |
| `hermes kanban --board <board> show <task> --json` prints `{"task": {..., "body": ...}, ...}` | `hermes_cli/kanban_parser.py` line 470 (`--board`); `hermes_cli/kanban.py` lines 493-495 | Yes: `website/docs/user-guide/features/kanban.md` line 957 (`hermes kanban show <id> [--json]`) and line 57 |
| The `zai` provider sends `reasoning_effort` at the top level of the request for GLM 5.2 and GLM 5.3; GLM 5.3 takes `low`, `medium`, `high`, `max`; Hermes maps `xhigh` to `max` | `plugins/model-providers/zai/__init__.py` lines 16-17, 31-42 and 63 (`top_level["reasoning_effort"] = effort`); merged by `agent/transports/chat_completions.py` line 574 (`api_kwargs.update(top_level_from_profile)`) | No (source reading only) |
| The `claude-subscription` provider of this repository takes its effort from `HERMES_CLAUDE_SUBSCRIPTION_EFFORT` and, after card `t_db165633`, from `extra_body["card_reasoning_effort"]` | `plugins/model-providers/claude-subscription/client.py` of this repository | Provider of this repository |

Limit found in the same reading: when more than one plugin registers `llm_request` middleware, `hermes_cli/plugins_dispatch.py` lines 591-602 call every callback with the same request, and `hermes_cli/middleware.py` lines 70-82 use the last returned request. Another plugin that returns a request after `jev` would replace the change of `jev`. On 2026-11-20 no bundled Hermes plugin and no other plugin of the profile `harness-worker` registers `llm_request` middleware.

## What happens when one of these breaks

- The request is sent unchanged, and the worker runs at the reasoning effort of its profile. Every failure (command missing, timeout, non-zero exit, JSON error, missing field, unexpected request shape) returns `None` from the callback; Hermes also skips a callback that raises.
- `jev` writes one record per process and task to `<jev log directory>/reasoning_effort.jsonl` with the failure type (`event` `card_read_failed` or `failed`, `error_class`). The record holds no card body and no request content. An applied level writes one record with `event` `applied`, the task ID, the profile, the board, the provider and the level.
- `scripts/verify-state`, check `check_hermes_reasoning_effort_sources`, reads the installed Hermes source as text and parses it with `ast` (no import of Hermes). It reports FAIL when `hermes_cli/middleware.py` no longer defines `LLM_REQUEST_MIDDLEWARE = "llm_request"`, `agent/turn_api_request.py` no longer calls `apply_llm_request_middleware` with `provider=` and `model=`, `hermes_cli/kanban_db_dispatch.py` no longer sets `HERMES_KANBAN_TASK` and `HERMES_KANBAN_BOARD`, or `plugins/model-providers/zai/__init__.py` no longer sets `top_level["reasoning_effort"]`. It reports WARN when `tools/kanban_tools_schemas.py` or `tools/kanban_tools.py` contains `reasoning_effort`: a supported per-card option then exists, and this design should be reviewed. Each message names this document.

## Visibility limit

The level is applied to the model requests only. Hermes's own card field `reasoning_effort` stays empty, so `hermes kanban show`, the dashboard and `kanban_show` do not show it. The body line and the `applied` record of the `jev` log are the places to look.

## Joint deployment

Until card `t_db165633` is deployed, the `claude-subscription` provider refuses a request with the `extra_body` key `card_reasoning_effort`. The live rollout installs this `jev` change and the provider change at the same time. A rollback of the provider change without a rollback of this change makes every Claude worker request on a card with the line fail; set `reasoning_effort.enabled` to `false` in the installed `plugins/jev/config.json` first.

## Upstream

Issue NousResearch/hermes-agent#105339 and open pull requests #79405, #87114 and #107957 add a supported per-card option; none is merged on 2026-11-20. This card made no upstream post.

## Moving to a supported option when Hermes adds one

1. `scripts/verify-state` reports the WARN of `check_hermes_reasoning_effort_sources`, or the Hermes release notes name a per-card reasoning effort.
2. Read the new option: the `kanban_create` argument, the dispatcher code that applies the card field to the worker, and the levels it accepts for `zai` and `claude-subscription`.
3. On a new card: make the orchestrator skills pass the level as the new `kanban_create` argument, set `reasoning_effort.enabled` to `false` in `plugins/jev/config.json`, and then remove `plugins/jev/reasoning_effort.py`, its registration, the `kanban_create` notice, the verify-state check and this dependency entry in `docs/README.md`.
4. Keep the provider key `card_reasoning_effort` until no card with the body line is open.
