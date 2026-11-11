# Light auxiliary helper tasks on claude-haiku-5-5: live procedure

Repository step: card `t_e7efc35f` (2026-11-11). This document is the input for
a later live card. Nothing in it has been run. Every step that writes under
`~/.hermes`, calls a model or restarts the gateway needs that later card's
separate human authorization.

## 1. Decision and scope

- Owner, Telegram 2026-11-11: "start the haiku as the main model for helper
  tasks card after the Jobcron & JSS cards are done". Owner answers on card
  `t_6996b4d0`: scope 21 profiles; model id `claude-haiku-5-5`; context window
  1,000,000 tokens
  (<https://platform.claude.com/docs/en/models/haiku-5-5/overview>). Decision:
  provider `claude-subscription`, model `claude-haiku-5-5`, as the primary
  model of the six light tasks.
- Light tasks (`LIGHT_HELPER_TASKS` in `scripts/verify-state`):
  `title_generation`, `memory_query_rewrite`, `tts_audio_tags`,
  `profile_describer`, `skills_hub`, `vision`.
- Other tasks: the remaining ten entries of `HELPER_TASKS` in
  `scripts/verify-state` (`compression`, `approval`, `review`, `mcp`,
  `triage_specifier`, `kanban_decomposer`, `goal_judge`, `curator`, `monitor`,
  `background_review`). They stay on `claude-subscription` / `claude-opus-5-5`.
- Profiles (21) and the switch target of each:
  - `--to claude-fable` (main model `claude-fable-5-2`): `advisor`,
    `anki-reviewer`, `chapt-reviewer`, `harness-reviewer`, `jobcron-reviewer`,
    `jss-reviewer`.
  - `--to claude-opus` (main model `claude-opus-5-5`): `anki-orchestrator`,
    `anki-worker`, `anki-worker-2`, `chapt-orchestrator`, `chapt-worker`,
    `chapt-worker-2`, `harness-orchestrator`, `harness-worker`,
    `harness-worker-2`, `jobcron-orchestrator`, `jobcron-worker`,
    `jobcron-worker-2`, `jss-orchestrator`, `jss-worker`, `jss-worker-2`.
- Out of scope, unchanged: the default profile (`~/.hermes`), the GLM (zai)
  profiles and the retired profiles.
- `fallback_providers` and `auxiliary.<task>.fallback_chain` stay as declared
  in `roster.yaml` (the Anthropic API fallback, `procedures/anthropic-api-fallback.md`).

## 2. Repository mechanism (card t_e7efc35f)

- `plugins/model-providers/claude-subscription/compat.py`: `MODELS` contains
  `"claude-haiku-5-5": {"context_length": 1000000}`.
- `roster.yaml`: each of the 21 entries declares
  `"auxiliary_models": {"light_tasks": "claude-haiku-5-5", "other_tasks": "claude-opus-5-5"}`.
  The schema is documented above `AUXILIARY_MODEL_GROUPS` in `scripts/verify-state`.
- `scripts/switch-profile-model --to claude-opus` and `--to claude-fable` write
  `auxiliary.<task>.provider` `claude-subscription` for all 16 tasks,
  `auxiliary.<task>.model` `claude-haiku-5-5` for the light tasks and
  `claude-opus-5-5` for the other tasks (`helper_models` and `settings`).
- `scripts/verify-state` compares `auxiliary.<task>.provider` and
  `auxiliary.<task>.model` of every profile that declares `auxiliary_models`
  with that declaration (`check_auxiliary_models`) and prints
  `FAIL: auxiliary model drift <profile> auxiliary.<task>.<provider|model>: expected <value>, actual <value>`.
- Consequence: once this repository change is on `main`, a live
  `scripts/verify-state` reports six `auxiliary model drift` lines (the
  `.model` of the six light tasks) for every one of the 21 profiles until step
  d of section 4 has switched that profile.

## 3. Before any live change

Run from a clean checkout of `main` that contains card `t_e7efc35f`. Set the
shell variables once:

```sh
REPO=/Users/chanbla11mit/hermes-local-harness
BASE=35f5e27c72d2be115c5040d83fd53adb8f76d8d4   # baseline of card t_e7efc35f
TS=$(date +%Y%m%d-%H%M%S)
B=~/.hermes/backups/haiku55-$TS
cd "$REPO" && git status --porcelain              # must print nothing
```

Record the live state of every profile before step d, for the comparison in
step e:

```sh
python3 scripts/verify-state > "$B-verify-before.txt" 2>&1; echo "exit $?"
```

Expected: the six `auxiliary model drift` lines per profile described in
section 2, and no other new drift line compared with the last recorded live run.

## 4. Steps

### a. Smoke test of claude-haiku-5-5 (before any live change)

Same method as the Fable 5.2 step 3 record (plugin README, "Claude Fable 5.2
allowlist entry", "Live smoke test, run once at 12:14 KST"): one run of the
repository `smoke.py` with the dedicated CLI that the profiles use (the path in
`HERMES_CLAUDE_SUBSCRIPTION_CLI`, CLI 2.1.302), under its own throwaway
`HERMES_HOME`. The smoke test includes an image check on one shared client,
which exercises the `vision` path.

```sh
python3 plugins/model-providers/claude-subscription/smoke.py --cli <dedicated claude CLI path> --model claude-haiku-5-5
```

Run it once. Expected: `SMOKE PASS cli=2.1.302 model=claude-haiku-5-5`. On
`SMOKE FAIL: <reason>`, stop: record the reason and change nothing else.
`smoke.py` does not print a context window, so the context length 1000000
stays the documented value, not a value the CLI reported.

### b. Copy the changed plugin files into the 22 installed plugin copies (with backups)

Same form as the Fable 5.2 step 3 record ("All 22 installed plugin copies
(`~/.hermes` and the 21 profile homes) received `compat.py` and `README.md`
from the repository"; backups in `~/.hermes/backups/fable52-20261111-121515/plugins/<home>/`).
Card `t_e7efc35f` changed only `compat.py` and `README.md` in the plugin
directory, so only those two files are copied.

1. Check every copy before the copy. `compat.py` must equal the baseline file;
   a `README.md` difference is recorded and does not stop the copy, because
   Hermes does not load `README.md`.

   ```sh
   n=0
   for home in ~/.hermes ~/.hermes/profiles/*; do
     d="$home/plugins/model-providers/claude-subscription"; [ -d "$d" ] || continue
     n=$((n+1)); name=$(basename "$home"); [ "$home" = ~/.hermes ] && name=default
     git -C "$REPO" show "$BASE:plugins/model-providers/claude-subscription/compat.py" | cmp -s - "$d/compat.py" \
       || echo "STOP compat.py differs from the baseline: $name"
     git -C "$REPO" show "$BASE:plugins/model-providers/claude-subscription/README.md" | cmp -s - "$d/README.md" \
       || echo "NOTE README.md differs from the baseline: $name"
   done; echo "copies: $n"
   ```

   Expected: `copies: 22` and no `STOP` line. On a `STOP` line or another
   count, stop and record the finding.
2. Back up and copy:

   ```sh
   for home in ~/.hermes ~/.hermes/profiles/*; do
     d="$home/plugins/model-providers/claude-subscription"; [ -d "$d" ] || continue
     name=$(basename "$home"); [ "$home" = ~/.hermes ] && name=default
     mkdir -p "$B/plugins/$name" && cp -p "$d/compat.py" "$d/README.md" "$B/plugins/$name/" \
       && cp "$REPO/plugins/model-providers/claude-subscription/compat.py" \
             "$REPO/plugins/model-providers/claude-subscription/README.md" "$d/"
   done
   ```

3. Read back: for every copy, `cmp` of both files against the repository files
   prints nothing, and `ls "$B/plugins" | wc -l` prints 22.

### c. Gateway restart by the owner (after step b, before any profile switch)

The running gateway keeps the allowlist it imported before step b. The Fable
5.2 advisor record in the plugin README (section "Claude Fable 5.2 allowlist
entry", the `advisor` items) shows why: the gateway imports a profile's
provider plugin once and never reloads it (`providers/__init__.py`
`_import_plugin_dir`, line 393, returns when the module name is already in
`sys.modules`, Hermes `9cf7960f`), so that gateway's `compat.MODELS` still
rejects a model id added after its start. After a profile switch, a helper task
of a gateway-served session would ask for `claude-haiku-5-5` and the old
allowlist would reject it until the gateway restarts. Kanban workers start as
separate processes and import the new `compat.py` from disk.

The owner restarts the gateway. The live card records the new gateway process
ID and its start time (`ps -o pid,lstart -p <pid>`) and confirms that the start
time is after step b. No profile is switched before this confirmation.

### d. Switch each profile

For each of the 21 profiles, with `t` the target from section 1:

```sh
p=harness-worker; t=claude-opus
for k in fallback_providers auth.adopt_external_logins model.default; do
  printf '%s ' "$k"; hermes -p "$p" config get --json "$k"; done > "$B/$p-before.txt"
cp -p ~/.hermes/profiles/$p/config.yaml ~/.hermes/profiles/$p/config.yaml.pre-haiku55-$TS
scripts/switch-profile-model --profile "$p" --to "$t" --dry-run
scripts/switch-profile-model --profile "$p" --to "$t"
```

- The dry run must list `auxiliary.<task>.model claude-haiku-5-5` for the six
  light tasks, `claude-opus-5-5` for the ten other tasks,
  `auxiliary.<task>.provider claude-subscription` for all 16 tasks, the
  unchanged `model.provider`, `model.default` and `model.base_url`, and the
  roster note `model <m> -> <m>, provider claude-subscription -> claude-subscription`.
  It must not print an `auxiliary_models` roster note. If it does, stop.
- The apply prints
  `<p>: <t> (<main model>); helpers on claude-haiku-5-5 for the light tasks (...) and on claude-opus-5-5 for the other tasks; backup config.yaml.pre-switch-<timestamp>`.
  The script also writes its own backup `config.yaml.pre-switch-<timestamp>`
  before the first write. It rewrites `roster.yaml` of the checkout with the
  same model and provider, so `git status --porcelain roster.yaml` must still
  print nothing.
- Read back:

  ```sh
  hermes -p "$p" config get --json auxiliary | python3 -c 'import json,sys
  a=json.load(sys.stdin)
  for t in ("vision","compression","skills_hub","approval","review","mcp","title_generation","memory_query_rewrite",
            "tts_audio_tags","triage_specifier","kanban_decomposer","profile_describer","goal_judge","curator",
            "monitor","background_review"):
      print(t, a.get(t,{}).get("provider"), a.get(t,{}).get("model"))'
  for k in fallback_providers auth.adopt_external_logins model.default; do
    printf '%s ' "$k"; hermes -p "$p" config get --json "$k"; done | diff "$B/$p-before.txt" -
  ```

  Expected: 16 lines, each `claude-subscription`, with `claude-haiku-5-5` on
  the six light tasks and `claude-opus-5-5` on the other ten; the `diff`
  prints nothing (`fallback_providers`, `auth.adopt_external_logins` and
  `model.default` unchanged).

Whether a switch rewrites `fallback_providers` or the fallback chains, from the
script source (`scripts/switch-profile-model` at card `t_e7efc35f`): a `--to`
switch writes only the pairs of `settings()` (lines 75 to 83): `model.provider`,
`model.default`, `model.base_url`, and `auxiliary.<task>.provider` and
`auxiliary.<task>.model` for the 16 tasks. `fallback_settings()` (line 101) is
added to the writes only with `--apply-fallbacks` (line 188) or
`--clear-fallbacks` (line 191), and this procedure uses neither. Result: the
switch does not rewrite `fallback_providers` or any
`auxiliary.<task>.fallback_chain`. Each write is one `hermes config set` of one
key; the Fable 5.2 step 3 record (plugin README) observed that a
`--to claude-fable` switch of `jobcron-reviewer` left `fallback_providers` and
every `auxiliary.<task>.fallback_chain` unchanged. The read-back above checks
`fallback_providers` again for every profile.

### e. Live scripts/verify-state

```sh
python3 scripts/verify-state > "$B-verify-after.txt" 2>&1; echo "exit $?"
grep 'auxiliary model drift' "$B-verify-after.txt"
diff <(grep '^FAIL' "$B-verify-before.txt" | grep -v 'auxiliary model drift') \
     <(grep '^FAIL' "$B-verify-after.txt")
```

Expected: no `auxiliary model drift` line, and no `FAIL` line in the second
run that was not in the first run.

### f. Acceptance evidence: one light task served on claude-haiku-5-5 per profile

Hermes records two kinds of evidence (installed Hermes source, read only,
commit `9cf7960f`):

1. Log line, written before the request is sent (it shows the route, not a
   completed response). `agent/auxiliary_client.py`, function
   `_prepare_aux_request` (line 7490), lines 7536 to 7538: for a synchronous
   call with a task name it logs at INFO
   `Auxiliary %s: using %s (%s)%s` with the task, the provider and the model.
   The logger is `agent.auxiliary_client` (line 133). Asynchronous calls
   (`async_mode`) do not write this line. The file is the profile's
   `agent.log` (`hermes_logging.py` line 344 creates `<HERMES_HOME>/logs`,
   line 372 names `agent.log`), here `~/.hermes/profiles/<p>/logs/agent.log`, with
   the format `%(asctime)s %(levelname)s%(session_tag)s %(name)s: %(message)s`
   (`hermes_logging.py` line 107). Pattern:

   ```sh
   grep -E 'INFO.* agent\.auxiliary_client: Auxiliary (title_generation|memory_query_rewrite|tts_audio_tags|profile_describer|skills_hub|vision): using claude-subscription \(claude-haiku-5-5\)' \
     ~/.hermes/profiles/<p>/logs/agent.log | tail -1
   ```

2. Session record of a completed response. `agent/auxiliary_client.py`
   `_validate_llm_response` (line 6863) calls `record_aux_usage` (line 6879), which
   (`agent/aux_accounting.py` line 84) calls `record_auxiliary_usage`
   (`hermes_state_usage.py` line 367). That writes one row per session, model,
   provider and task into the table `session_model_usage` of the profile's
   `state.db` (table definition `hermes_state_common.py` line 482). The model
   column is the model of the response (`aux_accounting.py`, docstring of
   `record_aux_usage`). A row is written only inside an agent turn (an
   accounting context exists) and only when the response reports token usage.
   Read only:

   ```sh
   sqlite3 -readonly ~/.hermes/profiles/<p>/state.db "SELECT session_id, task, model, billing_provider, api_call_count,
     datetime(last_seen, 'unixepoch', 'localtime') FROM session_model_usage
     WHERE model = 'claude-haiku-5-5' AND task IN ('title_generation', 'memory_query_rewrite', 'tts_audio_tags',
     'profile_describer', 'skills_hub', 'vision') ORDER BY last_seen DESC LIMIT 3;"
   ```

Trigger: `title_generation` runs at the start of a new session's first turn
(`agent/title_generator.py` `maybe_auto_title`, line 736; the model call is the
`call_llm(task="title_generation")` at line 514). A Kanban-dispatched worker
does not call the title model: `maybe_auto_title` uses the card title instead
(line 764, `_kanban_task_title` at line 713). Kanban runs therefore give title
evidence for no profile; they can give evidence for another light task (for
example `vision` or `skills_hub`) when the run uses it. For each profile, the
live card starts one new non-Kanban session with a message that asks for no
tool, for example `hermes -p <p> -z "Reply with exactly OK."`, and then reads
both kinds of evidence. The title model call runs in a background thread
(`spawn_context_thread`, `agent/title_generator.py` line 791). This card did not verify whether
that thread finishes before a one-shot process exits. If neither the log line
nor the row appears, the live card records that, and takes the evidence from
the next ordinary session of that profile (a gateway or interactive session)
instead of repeating calls.

Acceptance per profile: one `agent.log` line or one `session_model_usage` row
from the patterns above, dated after that profile's switch in step d. Record
the profile, the evidence kind, the task and the time.

### g. Revert

1. Restore each switched profile:

   ```sh
   cp -p ~/.hermes/profiles/$p/config.yaml.pre-haiku55-$TS ~/.hermes/profiles/$p/config.yaml
   ```

   Then read back `auxiliary` as in step d; every task must show
   `claude-subscription` / `claude-opus-5-5` again.
2. Restore the plugin copies from the step b backups:

   ```sh
   for home in ~/.hermes ~/.hermes/profiles/*; do
     d="$home/plugins/model-providers/claude-subscription"; [ -d "$d" ] || continue
     name=$(basename "$home"); [ "$home" = ~/.hermes ] && name=default
     cp -p "$B/plugins/$name/compat.py" "$B/plugins/$name/README.md" "$d/"
   done
   ```

   Restore the profile `config.yaml` files (item 1) before the plugin copies,
   so that no profile asks for `claude-haiku-5-5` after the allowlist loses it.
   The owner then restarts the gateway, for the reason in step c.
3. The repository stays as it is; while the live profiles are reverted, a live
   `scripts/verify-state` reports the six `auxiliary model drift` lines per
   profile from section 2. A full repository revert is a separate reviewed
   card that reverts card `t_e7efc35f`.

## 5. Not changed by card t_e7efc35f

`procedures/switching-hermes-models.md` still says that `--to claude-fable`
keeps the helpers on Opus. That file was outside the files card `t_e7efc35f`
was allowed to change; after this change the light tasks go to
`claude-haiku-5-5` under both Claude targets.
