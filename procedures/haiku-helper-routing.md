# Light auxiliary helper tasks on claude-haiku-5-5: live procedure

Repository step: card `t_e7efc35f` (2026-11-11). This document is the input for
a later live card. It was run on 2026-11-11 by the cards `t_cd353076` and
`t_216bb355`; the live record follows. Every step that writes under
`~/.hermes`, calls a model or restarts the gateway needs that later card's
separate human authorization.

## Live record (2026-11-11, KST)

Authority: owner, Telegram 2026-11-11 (section 1), and the owner's standing
instruction that approved live changes run without the owner present.

- Card `t_cd353076` (steps a and b, no commit):
  - Step a, one `smoke.py` run, 19:28:56 to 19:29:16:
    `SMOKE PASS cli=2.1.302 model=claude-haiku-5-5`.
  - Step b: check before the copy `copies: 22`, no `STOP` line. `compat.py` and
    `README.md` copied into all 22 installed plugin copies; backups in
    `/Users/chanbla11mit/.hermes/backups/haiku55-20261111-192936/plugins/<name>/`
    (22 directories). The copy finished at 19:29:37.
- Step c: the owner restarted the gateway. New gateway process 23372, started
  2026-11-11 19:49:01, after the step b copy. Other processes whose command
  line contains `hermes` and that started before 19:29:37 were only
  `browser_harness.daemon` processes and one `cua-driver serve` process (33100);
  no Hermes agent session and no dashboard process. None was stopped.
- Card `t_216bb355` (section 3 and steps d, e and f). Evidence directory
  `/Users/chanbla11mit/.hermes/backups/haiku55-switch-20261111-201312`
  (`TS` = `20261111-201312`); every Hermes command ran with a clean
  environment (`env -i` with `HOME`, `USER`, `LOGNAME`, `SHELL`, `LANG` and
  `PATH` only), so no variable of the Kanban worker session reached the
  profile commands.
  - Section 3, `verify-before.txt` (20:13 to 20:19): exit 1, 126 lines, all
    126 are `auxiliary model drift` lines (6 for each of the 21 profiles), no
    other `FAIL` line.
  - Step d, 20:20 to 20:36, in the order of section 1: all 21 profiles
    switched. Each has the backup `config.yaml.pre-haiku55-20261111-201312`
    and the backup that `scripts/switch-profile-model` wrote itself:

    | Profile | Target | `pre-switch` backup |
    |---|---|---|
    | `advisor` | `claude-fable` | `config.yaml.pre-switch-20261111-202023` |
    | `anki-reviewer` | `claude-fable` | `config.yaml.pre-switch-20261111-202128` |
    | `chapt-reviewer` | `claude-fable` | `config.yaml.pre-switch-20261111-202216` |
    | `harness-reviewer` | `claude-fable` | `config.yaml.pre-switch-20261111-202258` |
    | `jobcron-reviewer` | `claude-fable` | `config.yaml.pre-switch-20261111-202340` |
    | `jss-reviewer` | `claude-fable` | `config.yaml.pre-switch-20261111-202427` |
    | `anki-orchestrator` | `claude-opus` | `config.yaml.pre-switch-20261111-202509` |
    | `anki-worker` | `claude-opus` | `config.yaml.pre-switch-20261111-202551` |
    | `anki-worker-2` | `claude-opus` | `config.yaml.pre-switch-20261111-202634` |
    | `chapt-orchestrator` | `claude-opus` | `config.yaml.pre-switch-20261111-202716` |
    | `chapt-worker` | `claude-opus` | `config.yaml.pre-switch-20261111-202903` (also `config.yaml.pre-switch-20261111-202757`, see below) |
    | `chapt-worker-2` | `claude-opus` | `config.yaml.pre-switch-20261111-202943` |
    | `harness-orchestrator` | `claude-opus` | `config.yaml.pre-switch-20261111-203023` |
    | `harness-worker` | `claude-opus` | `config.yaml.pre-switch-20261111-203109` |
    | `harness-worker-2` | `claude-opus` | `config.yaml.pre-switch-20261111-203155` |
    | `jobcron-orchestrator` | `claude-opus` | `config.yaml.pre-switch-20261111-203238` |
    | `jobcron-worker` | `claude-opus` | `config.yaml.pre-switch-20261111-203323` |
    | `jobcron-worker-2` | `claude-opus` | `config.yaml.pre-switch-20261111-203406` |
    | `jss-orchestrator` | `claude-opus` | `config.yaml.pre-switch-20261111-203452` |
    | `jss-worker` | `claude-opus` | `config.yaml.pre-switch-20261111-203536` |
    | `jss-worker-2` | `claude-opus` | `config.yaml.pre-switch-20261111-203619` |

    For every profile the dry run matched the expected 35 `config set` lines
    and the roster note exactly (no `auxiliary_models` note); the read-back
    showed 16 tasks on `claude-subscription`, `claude-haiku-5-5` on the six
    light tasks and `claude-opus-5-5` on the other ten; the `diff` of
    `fallback_providers`, `auth.adopt_external_logins` and `model.default`
    printed nothing; `git status --porcelain roster.yaml` printed nothing.
    `chapt-worker`: the first apply was stopped at about 20:28 by the time
    limit of the terminal tool after a part of its `config set` writes
    (backup `config.yaml.pre-switch-20261111-202757`). The profile was
    restored from `config.yaml.pre-haiku55-20261111-201312` (`cmp` found the
    restored `config.yaml` equal to that backup, and the values of
    `fallback_providers`, `auth.adopt_external_logins` and `model.default`
    read back after the restore equal the values in `chapt-worker-before.txt`
    of the evidence directory), then dry run, apply and read-back ran again
    with the results above.
  - Step e, `verify-after.txt` (20:37 to 20:43): exit 0,
    `OK: desired state matches observed state`; no `auxiliary model drift`
    line and no `FAIL` line.
  - Step f, 20:43:21 to 20:43:43: one
    `hermes -p <p> -z "Reply with exactly OK."` per profile, no retry. All 21
    calls exited 0 and printed `OK`. Each created one session with source
    `oneshot` in the profile's `state.db`, with one `session_model_usage` row
    of the main model on `claude-subscription`. Each session except the
    `advisor` session received the instant title `Reply with exactly OK.`
    (`title_source` `derived`); the `advisor` session has no title. The
    one-shot runs wrote no line to the profiles' `agent.log`. Result for all
    21 profiles: no light-task call recorded. No profile has a
    `claude-haiku-5-5` route line of item 1, a fallback line of item 1 or a
    row of item 2 (with either `billing_provider`) dated after its switch, so
    no failed primary route was found. The evidence for each profile is the
    step d read-back and the step e result above.
- Revert, if needed: section 4, step g, with `TS` = `20261111-201312` and
  `B` = `/Users/chanbla11mit/.hermes/backups/haiku55-20261111-192936`.

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
separate processes and import the new `compat.py` from disk. Any other Hermes
process started before step b (an open interactive session, a dashboard
process) also keeps the old allowlist; after step d, the Anthropic API fallback
chain answers its light tasks until that process restarts. The live card closes
or restarts such processes before step d, or records them.

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

1. Log line, written before the request is sent. `agent/auxiliary_client.py`,
   function `_prepare_aux_request` (line 7490), lines 7536 to 7538: for a
   synchronous call with a task name it logs at INFO
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

   This line is evidence of the route only: it is written before the request
   is sent, so it does not show that `claude-subscription` answered. When the
   `claude-subscription` request fails, the same `agent.log` later shows one
   of these lines for the same task:
   - `agent/auxiliary_client.py` line 7889, INFO
     `Auxiliary %s%s: %s on %s (%s), trying fallback` (line 7884, WARNING
     `... timed out after %ss ... on %s, trying fallback`, for a timeout);
   - `agent/auxiliary_client.py` line 4460, INFO
     `Auxiliary %s: %s on %s — configured fallback to %s (%s)`, which names
     the fallback chain entry that answers instead, for example
     `configured fallback to fallback_chain[0](anthropic) (claude-haiku-5-5)`.

   Pattern for these lines (`<task>` is the task of the route line):

   ```sh
   grep -E 'agent\.auxiliary_client: Auxiliary <task>.*(trying fallback|configured fallback to)' \
     ~/.hermes/profiles/<p>/logs/agent.log | tail -3
   ```

   A route line followed by such a line for the same task is a failed primary
   route, not acceptance evidence. Because the model id of the fallback chain
   of the six light tasks is also `claude-haiku-5-5`
   (`auxiliary_fallback_chain` in `roster.yaml`, provider `anthropic`), the
   model id alone never shows which provider answered.

2. Session record of a completed response. `agent/auxiliary_client.py`
   `_validate_llm_response` (line 6863) calls `record_aux_usage` (line 6879), which
   (`agent/aux_accounting.py` line 84) calls `record_auxiliary_usage`
   (`hermes_state_usage.py` line 367). That writes one row per session, model,
   provider and task into the table `session_model_usage` of the profile's
   `state.db` (table definition `hermes_state_common.py` line 482). The model
   column is the model of the response (`aux_accounting.py`, docstring of
   `record_aux_usage`). A row is written only inside an agent turn (an
   accounting context exists) and only when the response reports token usage.
   The `billing_provider` column is the provider hint that the caller passed
   to `_validate_llm_response`. For a synchronous call, only the first primary
   request passes it (`agent/auxiliary_client.py` line 8230,
   `_primary(provider=request_provider, base_url=req.base_info)`). The other
   synchronous paths pass the task only: a fallback chain entry
   (`_call_fallback_candidate_sync`, line 4169), a same-provider retry of the
   recovery steps (`_retry_same_provider_sync`, line 3832), a retry after a
   transient transport error (line 8243, `_primary()`) and the recovery call
   step (line 8253). Their responses give a row with an empty
   `billing_provider`; a row of an auxiliary task does not inherit the
   provider of the session (`hermes_state_usage.py` line 357, docstring of
   `_record_model_usage` at line 337, and the docstring of
   `_validate_llm_response`, lines 6866 to 6875). Read only:

   ```sh
   sqlite3 -readonly ~/.hermes/profiles/<p>/state.db "SELECT session_id, task, model, billing_provider, api_call_count,
     datetime(last_seen, 'unixepoch', 'localtime') FROM session_model_usage
     WHERE model = 'claude-haiku-5-5' AND billing_provider = 'claude-subscription'
     AND task IN ('title_generation', 'memory_query_rewrite', 'tts_audio_tags',
     'profile_describer', 'skills_hub', 'vision') ORDER BY last_seen DESC LIMIT 3;"
   ```

   A `claude-haiku-5-5` row of a light task with an empty or different
   `billing_provider` is a fallback row: the first `claude-subscription`
   request failed, and a path from the list above answered. It is not
   acceptance evidence, and the live card records it as a failed primary route
   for that profile and task (the `agent.log` lines of item 1 show whether the
   fallback chain or a same-provider retry answered). Example from the live state of 2026-11-11,
   before any switch (review round 1 of card `t_e7efc35f`, read only): `jss-worker-2` has the row
   `vision|claude-haiku-5-5||2026-11-11 16:44:09`, after the `agent.log` line
   `Auxiliary vision: request timed out on claude-subscription — configured fallback to fallback_chain[0](anthropic) (claude-haiku-5-5)`.

Trigger: `title_generation` runs at the start of a new session's first turn
(`agent/title_generator.py` `maybe_auto_title`, line 736; the model call is the
`call_llm(task="title_generation")` at line 514). A Kanban-dispatched worker
does not call the title model: `maybe_auto_title` uses the card title instead
(line 764, `_kanban_task_title` at line 713). Kanban runs therefore give title
evidence for no profile; they can give evidence for another light task (for
example `vision` or `skills_hub`) when the run uses it. For each profile, the
live card starts one new non-Kanban session with a message that asks for no
tool, for example `hermes -p <p> -z "Reply with exactly OK."`, and then reads
both kinds of evidence once. The title model call runs in a background thread
(`spawn_context_thread`, `agent/title_generator.py` line 791). The repository
already records that title generation in a one-shot run can be cut off when
the process exits ("client closed or cancelled";
`docs/bugs/261017-claude-subscription-cli-retries-and-title-helper-rejected.md`,
section "Remaining limits"), so the one call may leave no evidence.

Acceptance per profile, dated after that profile's switch in step d, one of:

- Completed response on the primary route: one `session_model_usage` row from
  the query of item 2 (`billing_provider = 'claude-subscription'`). Record the
  profile, the evidence kind, the task and the time.
- Route only: one `agent.log` route line from item 1 with no `trying fallback`
  or `configured fallback to` line for the same task after it. Record it as
  "route line only, no completed-response row", with the profile, the task and
  the time.

End state for a profile with no evidence: if, after the one call, the profile
has neither a row from item 2 nor a route line from item 1, the live card
records "no light-task call recorded" for that profile, names the evidence that
does exist for it (the step d read-back of the 16 `auxiliary.<task>.provider`
and `.model` values, and the step e result with no `auxiliary model drift`
line for that profile), and treats that profile as complete. It does not
repeat the call and does not wait for a later gateway or interactive session.
The step a smoke test and the step b read-back of the plugin copies cover the
allowlist for every profile.

Failed primary route: a fallback row from item 2, or a route line followed by a
fallback line from item 1, dated after the switch, is a finding. The live card
records it with the profile, the task, the time and the fallback line, checks
the step c condition for the process that wrote it (a process started before
step b), and does not count it as acceptance.

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
   The revert needs no gateway restart: after item 1 no profile requests
   `claude-haiku-5-5` on `claude-subscription`, and the allowlist that the
   running gateway loaded in step c contains every model id of the restored
   `compat.py`, so it rejects no request.
3. The repository stays as it is; while the live profiles are reverted, a live
   `scripts/verify-state` reports the six `auxiliary model drift` lines per
   profile from section 2. A full repository revert is a separate reviewed
   card that reverts card `t_e7efc35f`.

## 5. Not changed by card t_e7efc35f

Card `t_e7efc35f` left in place the statement in
`procedures/switching-hermes-models.md` that `--to claude-fable` keeps the
helpers on Opus, because that file was outside the files card `t_e7efc35f` was
allowed to change. Card `t_216bb355` corrected that statement on 2026-11-11:
the six light tasks go to `claude-haiku-5-5` under both Claude targets.
