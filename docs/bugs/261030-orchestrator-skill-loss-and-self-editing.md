# Orchestrators lost their skill text in context compression and edited their own skills with skill_manage

Reported: 2026-10-30, by the owner and the harness orchestrator (`harness-orchestrator`, board `harness`). Recorded from harness card `t_0a8674fe`.

All times are KST (UTC+09:00). Source references are to the installed Hermes Agent (`/Users/chanbla11mit/.hermes/hermes-agent/`, commit `9cf7960f274e`), read without running, importing or changing it, and to this repository at commit `a391e38`. No live profile, skill, ledger, board database or log was opened on this card; the evidence below is the card's report.

## Summary
The five project orchestrators (`harness-orchestrator`, `jobcron-orchestrator`, `chapt-orchestrator`, `jss-orchestrator`, `anki-orchestrator`) load their rules from the skill `multi-agent-coding-orchestrator` with `skill_view`. Context compression replaces a large `skill_view` result with a `[SKILL_PRUNED: ...]` marker, and an orchestrator then often continues without the rules. Separately, the orchestrators changed their own live skill copies with `skill_manage`, so the live copies drifted from the reviewed repository copies. This repository now requires four Hermes settings on each of the five orchestrators: `skills.auto_load: ["multi-agent-coding-orchestrator"]` puts the skill text into the system prompt, `skills.write_approval: true` stores every `skill_manage` mutation as a pending record instead of writing it, and `security.protected_instruction_files: true` with `security.protected_instruction_extra_patterns: ["SKILL.md"]` adds `SKILL.md` to the file names that `write_file` and `patch` treat as protected. `scripts/verify-state` fails when any of the four settings differs on any of the five orchestrators. Each orchestrator skill has a new section `## Skill Changes` that states these rules.

## Observed
- On 2026-10-28 `jobcron-orchestrator` made 6 cards with `hermes kanban --board jobcron create` while its skill, which forbids that command, had been replaced by a `[SKILL_PRUNED]` marker. The approval of card J8 then went unseen for about 7 hours. Details: [`261030-kanban-cli-create-no-notify-subscription.md`](261030-kanban-cli-create-no-notify-subscription.md).
- A `skill_view` result longer than 5,000 characters is replaced by the `[SKILL_PRUNED: ...]` marker during compression. The orchestrator skill copies in this repository are 20,503 to 69,247 bytes long.
- All five orchestrators had `skills.auto_load: []`.
- The skills ledger of `jobcron-orchestrator` (actor `agent`) records more than 30 `skill_manage` mutations of its `multi-agent-coding-orchestrator` skill from 2026-10-09 to 2026-10-30. The last one, at 2026-10-30 06:26, added one paragraph that no review had approved. On 2026-10-30, at the owner's instruction, the controller removed it and restored the live copy byte for byte to the repository copy, keeping a backup under that profile's `skill-backups/` directory. The ledger was not opened on this card.
- `security.protected_instruction_files` was already true on all five orchestrators. The Hermes built-in system prompt tells every agent to fix a skill with `skill_manage`, so a rule in the skill alone does not stop the agent from editing the skill.

## Cause
Each statement is marked "Established from source", "Reported" or "Not established".

- Reported: context compression removed the skill text, and the orchestrator did not reload it before acting.
- Established from source: `skills.auto_load` renders the named skills into the system prompt once per agent and keeps the same text when the system prompt is rebuilt after compression (`agent/system_prompt.py:317-341`, placed in the stable part of the prompt at `agent/system_prompt.py:760`; `agent/skill_commands.py:730-758`). The setting defaults to an empty list (`hermes_cli/config_defaults.py:1463-1466`).
- Established from source: `skill_manage` writes directly unless `skills.write_approval` is true (`tools/skill_manager_tool.py:618-634`; default false at `hermes_cli/config_defaults.py:1485`).
- Established from source: `security.protected_instruction_files` covers only the file names `AGENTS.md`, `CLAUDE.md`, `SOUL.md` and `.cursorrules` (`tools/file_tools_write_guards.py:188-189`) plus any `security.protected_instruction_extra_patterns`, and only `write_file` and `patch` consult it (`tools/file_tools.py:786`, `tools/file_tools.py:873`). It does not apply to `skill_manage`.
- Established from source: `skill_manage`, `skill_view` and `skills_list` are in the same `skills` toolset, so `agent.disabled_toolsets: [skills]` would also remove `skill_view`, and `skills.auto_load` renders nothing for an agent without a skills tool (`agent/system_prompt.py:325-327`). The repository does not use `disabled_toolsets` for this reason.

## Source findings for the four settings
These findings were confirmed before the settings were added to `roster.yaml`.

### (a) Value type that verify-state reads for a list setting
- Established from source: `hermes config get --json <key>` prints `json.dumps(value)` of the stored value (`hermes_cli/config.py:882-885`, called from `hermes_cli/config.py:3747-3780`). A list is printed as a JSON array and a boolean as `true` or `false`. A key that is not set exits with status 1 (`hermes_cli/config.py:3769-3770`, `hermes_cli/config.py:3573-3575`). Masking changes only values under credential-shaped keys (`hermes_cli/config.py:2947-2963`).
- `json_config` in `scripts/verify-state` parses that output with `json.loads` (`scripts/verify-state:49-56`), so it returns a Python `list` for `skills.auto_load` and `security.protected_instruction_extra_patterns` and a `bool` for the two boolean settings.
- Python treats `1 == True` as true, but Hermes reads a `write_approval` value of `1` as off (`tools/write_approval.py:55-60`). The comparison in `scripts/verify-state` (`same_setting_value`) therefore requires equal types at every level as well as equal values.
- `hermes config set` parses a list literal such as `'["SKILL.md"]'` into a list (`hermes_cli/config.py:3379-3409`) and refuses a non-list value for a key whose default is a list (`hermes_cli/config.py:3447-3466`).

### (b) `skills.write_approval: true`
- Established from source: with the setting true, every skill write is staged, from a foreground turn and from the background review fork alike (`tools/write_approval.py:201-210`). The staged write is stored as one JSON file per write at `<HERMES_HOME>/pending/skills/<id>.json` (`tools/write_approval.py:65-89`), where `<HERMES_HOME>` is the profile's home directory. The tool result reports `staged: true` and a message to the model (`tools/skill_manager_tool.py:632-634`, `tools/write_approval.py:190-198`).
- Established from source: staging sends no message to the owner. No gateway, cron or notifier code reacts to a staged skill write. The `/skills` command lists, shows, approves or rejects pending records only when someone runs it (`gateway/slash_commands.py:899-919`). The background review summary skips a staged skill write (`agent/background_review.py:687-692`).
- Result: the setting is included. The staged message names the `/skills pending` command in an interactive or gateway session (`tools/write_approval.py:166-198`); the skill section therefore tells the orchestrator not to ask the owner to approve a staged skill edit.

### (c) `security.protected_instruction_extra_patterns: ["SKILL.md"]`
- Established from source: the pattern is matched with `fnmatch`, without regard to letter case, against the base name of the target path and of its resolved path (`tools/file_tools_write_guards.py:192-207`, `tools/file_tools_write_guards.py:240-245`). Only `write_file` and `patch` call this check (`tools/file_tools.py:786`, `tools/file_tools.py:873`). `skill_manage`, `skill_view` and `skills.auto_load` do not call it, so the pattern does not block `skill_view` or `skills.auto_load`.
- Established from source: the check exempts every path inside the active Hermes home and, for a named profile, inside the Hermes root directory (`tools/file_tools_write_guards.py:114-135`, `tools/file_tools_write_guards.py:231-238`). Every live skill copy is under `~/.hermes`, so the pattern does not protect any live skill copy. It applies only to a `SKILL.md` outside `~/.hermes`, for example in a checkout of this repository.
- Established from source: a matching write needs approval for each operation. In a gateway session the approval request is sent to the owner (`tools/file_tools_write_guards.py:288-310`); with no human channel, for example in cron, the write is blocked (`tools/file_tools_write_guards.py:318-321`).
- Result: the setting is included, because it does not block `skill_view` or `skills.auto_load`. Its effect is limited to `SKILL.md` files outside `~/.hermes`.

### (d) `skills.auto_load` in gateway and cron sessions
- Established from source: the pinned skills are rendered for every agent that has a skills tool and does not skip context files (`agent/system_prompt.py:325-327`).
- Gateway sessions: context files are skipped only when `gateway.platforms.<platform>.skip_context_files` is true (`gateway/run_turn_runner.py:1004-1012`), so gateway sessions render the pinned skill when the platform's toolsets include a skills tool.
- Cron sessions: a cron job skips context files unless it has a working directory (`cron/scheduler.py:2528-2529`, `skip_context_files=not bool(workdir)`), so a cron job without a working directory does not render the pinned skill. A later scheduled board check for an orchestrator needs a working directory and a skills tool to see the skill.

## Repository change
- `roster.yaml` has a second settings group, `orchestrator_profile_settings`, for exactly the five orchestrators with the four settings above. The existing group `managed_profile_settings` (compression settings for `advisor`, three orchestrators and `default`) is unchanged; `advisor` and `default` do not get the new settings. `snapshots/sanitized-current-state.yaml` is unchanged, because verify-state does not compare it for the new group.
- `scripts/verify-state`: `check_managed_setting_groups` checks both groups with the same reader in fixture mode and in live mode (`hermes -p <profile> config get --json <key>`). A wrong, missing or unreadable value fails with a message that names the profile and the key. A malformed group fails, a key declared by both groups for one profile fails, and `orchestrator_profile_settings` must name exactly the orchestrators of `project_isolation`.
- Each of the five files `policies/profile-skills/<orchestrator>/autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md` has a new section `## Skill Changes` after `## Skills`. The version lines are unchanged.
- `tests/gen_fixtures.py` writes the new values into `profile_managed_settings` of every fixture and writes the drift fixture `tests/fixtures/orchestrator-skill-settings-drift.yaml`. Tests: `tests/test_orchestrator_profile_settings.py`, `tests/test_orchestrator_skill_changes_policy.py`, and `anki-orchestrator` added to `tests/test_orchestrator_card_creation_policy.py`. The tests that rebuild older bytes of the skill files reverse the new section first.

## Rollout
Not part of this card. A separate deployment card, after integration:
1. For `jobcron-orchestrator`, `chapt-orchestrator`, `jss-orchestrator` and `anki-orchestrator`: `hermes -p <profile> config set skills.auto_load '["multi-agent-coding-orchestrator"]'`, `hermes -p <profile> config set skills.write_approval true`, `hermes -p <profile> config set security.protected_instruction_extra_patterns '["SKILL.md"]'` (`security.protected_instruction_files` is already true), and install the reviewed skill copy into each profile's skills directory.
2. `harness-orchestrator`: its own config and skill copy are installed by the owner.
3. The owner restarts the gateway from a separate shell. The pinned skill is resolved once per agent, so a running agent keeps its earlier system prompt until it is created again.

## Remaining gaps
- The terminal can still write a `SKILL.md`. The orchestrator command-line toolsets that verify-state checks (`clarify`, `kanban`, `memory`, `session_search`, `skills`, `todo`) include no terminal or file toolset; the toolsets of other platforms were not checked on this card. verify-state in live mode reports a live skill copy whose bytes differ from the repository copy.
- Staged skill writes stay under each profile's `pending/skills/` directory until someone approves or rejects them with `/skills`.
- The pinned skill text is part of every orchestrator system prompt; the longest copy (`jobcron-orchestrator`) is 69,247 bytes.

## Upstream status
Not checked: network access was not authorized on this card.
