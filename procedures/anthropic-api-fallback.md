# Anthropic API fallback for the claude-subscription profiles

Procedure owner: harness board. Card `t_54fc49fb` added the repository mechanism and this procedure. The live configuration, the model identifiers and the live test are done on later cards, after the owner has added the API key. Sections 1 to 7 describe the four Jobcron profiles. Section 8 extends the fallback to the 18 other claude-subscription profiles.

Hermes facts below were read from the installed Hermes source at commit `9cf7960f` (`~/.hermes/hermes-agent`). Re-read them after a Hermes upgrade.

## 1. Owner decision and scope

- **Decision.** Owner, Telegram, 2026-11-09: "Harness change request: Anthropic API fallback behind the Claude subscription for the Jobcron fleet."
- **Scope.** `jobcron-orchestrator`, `jobcron-worker`, `jobcron-worker-2` and `jobcron-reviewer`, and since the owner decision of 2026-11-11 also the 18 profiles listed in section 8. These profiles keep `claude-subscription` as the primary provider. They gain a fallback provider: the native Hermes `anthropic` provider.
- **Payment.** The fallback is paid from Anthropic API credits. USD 200 of Anthropic Console promotional credits expire on 2026-11-19. For what happens after that date, see section 8, "Credit behaviour and owner decision".
- **Recorded override.** `plugins/model-providers/claude-subscription/README.md` says "never configure an API-key substitute for this provider". It also says "pause on failure rather than silently substituting a provider". For the four Jobcron profiles and the 18 profiles in section 8 only, and only until a revert under section 7, the owner's decision overrides both statements. The README is unchanged. Every other profile keeps both rules.

## 2. Hermes configuration keys

- **Main fallback.** The top-level key `fallback_providers` holds a list of entries. Each entry has `provider` and `model` (`website/docs/user-guide/features/fallback-providers.md`; default `[]` at `hermes_cli/config_defaults.py:36`). Do not use `fallback_model`, the legacy single-entry key. `hermes_cli/fallback_config.py:103-120` (`get_fallback_chain`) still appends a `fallback_model` entry after the `fallback_providers` entries. On 2026-11-09 no non-retired profile had `fallback_model` set.
- **Auxiliary fallback.** `auxiliary.<task>.fallback_chain` is a list of entries, one list per auxiliary task. Each entry has `provider` and `model`, and may have a positive `timeout` in seconds (`website/docs/user-guide/configuration.md:1570` and `:1640`; read at `agent/auxiliary_client.py:4426`; the per-entry timeout at `:3971-3981`). The key has no default in `DEFAULT_CONFIG`. `hermes config set` therefore prints "not a recognized config key", but it still saves the value with exit status 0, and the auxiliary client reads it.

## 3. Harness mechanism

- **roster.yaml.** A profile entry may declare:
  - `fallback_providers`: a list of objects with exactly `provider` and `model`.
  - `auxiliary_fallback_chain`: an object whose keys are auxiliary task names from `HELPER_TASKS` (`scripts/verify-state`). Each value is a list of objects with `provider`, `model` and an optional positive numeric `timeout`.

  Any other entry field is a verify-state error, for example `api_key`, `key_env` or `base_url`. A field whose name contains `key`, `token` or `secret` is reported as a credential-like field, and the error message never contains the field's value. An absent field means that the profile must have no fallback (an empty list or no value).
- **scripts/switch-profile-model.**
  - `--apply-fallbacks` writes the roster-declared value of `fallback_providers` and of `auxiliary.<task>.fallback_chain` for every one of the sixteen helper tasks; an undeclared task gets `[]`.
  - `--clear-fallbacks` sets all seventeen keys to `[]`.
  - Either option works alone or with `--to`. Each run first backs up `config.yaml` as `config.yaml.pre-switch-<timestamp>`, and `--dry-run` prints the commands and writes nothing.
  - The script writes with `hermes config set <key> '<JSON list>'`: a value that starts with `[` is parsed as YAML/JSON and stored as a list (`hermes_cli/config.py:3330-3409`, `_looks_structured_value` and `_coerce_config_set_value`). An empty list is the cleared state. The script does not use `hermes config unset`, because it exits non-zero for a key that was never set (`hermes_cli/config.py`, `unset_config_value`).
  - Neither option changes `roster.yaml`, and neither writes a credential.
- **scripts/verify-state.** In live mode it reads `hermes -p <profile> config get --json fallback_providers` and `hermes -p <profile> config get --json auxiliary` for every non-retired roster profile. In fixture mode it reads the fixture section `profile_fallback_settings`. A difference from the roster is reported as `fallback drift <profile> <key>: expected [...], actual [...]`. The whole `auxiliary` mapping is read because `config get` exits non-zero for a `fallback_chain` that was never set. An auxiliary task outside `HELPER_TASKS` that has a non-empty `fallback_chain` is also drift. In a drift message, the value of any field other than `provider`, `model` and `timeout` is replaced by `<not shown>`.

## 4. Credential (the owner does this; the harness never reads or prints the key)

1. In the Anthropic Console, create one API key for this purpose.
2. **Add the key to the `.env` file of each of the four profiles.** Run the three commands below in zsh, once, in one terminal. `read -rs` asks for the key with a prompt that does not show the typed text, and keeps the key only in the shell variable `K`. The typed command lines and the shell history contain `$K`, not the key. While each `hermes` process runs, the key is one of its process arguments.

   ```zsh
   read -rs "K?Anthropic API key: "; echo
   for p in jobcron-orchestrator jobcron-worker jobcron-worker-2 jobcron-reviewer; do hermes -p "$p" config set ANTHROPIC_API_KEY "$K"; done
   unset K
   ```

   - Each `config set` prints only `✓ Set ANTHROPIC_API_KEY in <path of the profile .env>`. A key name that ends in `_API_KEY` is written to the active profile's `.env`, not to `config.yaml` (`_is_env_config_key`, `hermes_cli/config.py:869-879`; `set_config_value`, `hermes_cli/config.py:3629-3638`; `save_provider_env_credential`, `hermes_cli/credential_lifecycle.py:163-199`).
3. **Do not use `hermes auth add anthropic --type api-key` in these four profiles until the Hermes defect is fixed** ([bug report](../docs/bugs/261109-anthropic-api-key-auth-add-dropped-in-named-profile.md)): in a named profile it prints `Added anthropic credential` but stores nothing.
4. **How Hermes uses the key.** At every credential pool load, Hermes adds an in-memory `anthropic` entry with label `ANTHROPIC_API_KEY` and source `env:ANTHROPIC_API_KEY` (`_seed_from_env`, `agent/credential_pool.py:2951-2991`; `_env_payload`, `agent/credential_pool.py:2899-2905`). `resolve_anthropic_token` reads `ANTHROPIC_API_KEY` (`agent/anthropic_credentials.py:702`), but `ANTHROPIC_TOKEN` or `CLAUDE_CODE_OAUTH_TOKEN` in the same environment takes precedence (line 697). On 2026-11-09 none of the four profile `.env` files defined either name (checked by name only); do not add them.
5. **Places the key must never be written:** `~/.hermes/.env`, `roster.yaml`, any Kanban card or comment, any log, or any commit. Only the four profile `.env` files receive the key, through step 2.
6. **Check without printing the key.** For each of the four profiles, run `hermes -p <profile> auth list anthropic`. The expected output is one entry, with label `ANTHROPIC_API_KEY` and source `env:ANTHROPIC_API_KEY`. The command prints the label, credential type, id, priority and source of each entry, but not the key (`hermes_cli/auth_commands.py:537-541`). If an entry with another source is listed, for example `claude_code` or `hermes_pkce`, do not continue with section 6 and report it to the owner.
7. **Billing boundary: `auth.adopt_external_logins` is `false` on the four profiles.** Owner decision, 2026-11-09. The reason: the Claude Code login uses the same Max plan allowance as the primary provider `claude-subscription`, and Hermes must not use that login directly.
   - With the default value `true` (`hermes_cli/config_defaults.py:1763`), Hermes can seed the Claude Code login (`~/.claude/.credentials.json`) into the `anthropic` credential pool as a `claude_code` entry (`agent/credential_pool.py:2621-2625`), and credential rotation after an authentication or rate-limit error could move the fallback onto it.
   - While `ANTHROPIC_API_KEY` is set and neither `ANTHROPIC_TOKEN` nor `CLAUDE_CODE_OAUTH_TOKEN` is set, Hermes already removes and does not seed the `claude_code` and `hermes_pkce` entries (`agent/credential_pool.py:2598-2615`). The setting `false` additionally stops Hermes from reading or refreshing the Claude Code login files at all (`adopt_external_logins_enabled`, `agent/credential_sources.py:32-38`), and removes a `claude_code` entry that an earlier process stored (`agent/credential_pool.py:2626-2629`).
   - The command for each of the four profiles is `hermes -p <profile> config set auth.adopt_external_logins false`. The earlier value was `true`; section 7 restores it.

## 5. Model identifiers

- **Source and date.** Card `t_731d4476` requested the live Anthropic model list once, on 2026-11-11 at 10:40 KST, for `jobcron-worker`. The identifiers in this procedure come only from that list, not from documentation or memory.
- **Why the picker was not used.** The earlier plan was to run `hermes -p jobcron-worker model --refresh` and close the picker without choosing anything. `hermes model` is an interactive picker (`hermes_cli/subcommands/model.py:8-15`), and a wrong key press changes the profile's default model. The card therefore called the function that the picker uses to fetch the Anthropic list, `_fetch_anthropic_models` (`hermes_cli/models.py:2138`), directly. The picker reaches it through `provider_model_ids` and `_anthropic_catalog` (`hermes_cli/models.py:1442-1448`, registered at `:1554`). `_anthropic_catalog` passes `base_url=None` and `api_key=None` when `model.provider` is not `anthropic`; on `jobcron-worker` it is `claude-subscription`. The direct call used the same arguments. The card did not use `provider_model_ids`, because that function returns a built-in catalog when the live request fails (`hermes_cli/models.py:1747-1775`).
- **How the call ran.** Installed Hermes Python (`~/.hermes/hermes-agent/venv/bin/python`, Hermes commit `9cf7960f`), under `env -i` with only `HOME`, `PATH` and `HERMES_HOME=/Users/chanbla11mit/.hermes/profiles/jobcron-worker`, so no token from the calling environment could be used. The profile environment was loaded only with `load_hermes_dotenv(project_env=<hermes-agent>/.env)` (`hermes_cli/env_loader.py:455`), the same call that the CLI makes at start (`hermes_cli/main.py:713`). The script opened no `.env` or `auth.json` file itself and printed only the returned model identifiers.
- **Which credential listed the models.** Before the request, the script checked with the Hermes functions, without printing any value:
  - `_first_env("ANTHROPIC_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN")` is empty, and `ANTHROPIC_API_KEY` is set.
  - `resolve_anthropic_token()` returns the `ANTHROPIC_API_KEY` value (`agent/anthropic_credentials.py:691-709`, the API key branch at line 702).
  - `_is_oauth_token` is False for that value (`agent/anthropic_credentials.py:63-67`), so it has the shape of an Anthropic Console API key.

  `_fetch_anthropic_models` therefore sent the value in the `x-api-key` header (`hermes_cli/models.py:2165`), not as an OAuth Bearer token. The list came from the `ANTHROPIC_API_KEY` value in the `jobcron-worker` profile `.env`. The first attempt, on 2026-11-09, stopped at the `_is_oauth_token` check and made no request, because the value then had the shape of an OAuth or setup token; the owner replaced the value on 2026-11-11.
- **Returned list.** 15 identifiers, in the order Hermes sorts them (Opus, then Sonnet, then Haiku, then others; `hermes_cli/models.py:2196`): `claude-opus-4-5-20251101`, `claude-opus-4-6`, `claude-opus-4-7`, `claude-opus-4-8`, `claude-opus-5`, `claude-opus-5-5`, `claude-sonnet-4-5-20250929`, `claude-sonnet-4-6`, `claude-sonnet-5`, `claude-sonnet-5-5`, `claude-haiku-4-5-20251001`, `claude-haiku-5-5`, `claude-fable-5`, `claude-fable-5-1`, `claude-fable-5-2`.
- **Chosen identifiers.**
  - Opus: `claude-opus-5-5`, the only Claude Opus 5.5 identifier in the list.
  - Fable: `claude-fable-5-2`, the only Claude Fable 5.2 identifier in the list. Owner decision, 2026-11-11: the Fable profiles, including `jobcron-reviewer`, move from Fable 5.1 to Fable 5.2 on a separate card. Until that card, the primary model of `jobcron-reviewer` stays `claude-fable-5-1`.
  - Haiku: `claude-haiku-5-5`, the newest Haiku identifier in the list. The other one is `claude-haiku-4-5-20251001`, which is also the Hermes built-in default.
- **Where the list is cached.** `_fetch_anthropic_models` itself writes no cache file; the call above therefore wrote none. The picker's disk cache is written by the `provider_model_ids` cache layer to `~/.hermes/profiles/<profile>/provider_models_cache.json` (`_provider_models_cache_path`, `hermes_cli/models.py:1869`). Each entry is keyed by provider and a credential fingerprint, which is a short hash, not the key (`_credential_fingerprint`, `hermes_cli/models.py:1874`). `hermes_cli/models_profile_cache.py` keeps only in-memory values per profile.
- **Proof of use.** The list shows which identifiers the key can see. The live test in section 6 is what proves that each identifier works with the API key.

## 6. Intended values, apply steps and live test plan

### Intended values (identifiers from section 5; declared in `roster.yaml` by card `t_731d4476`)

| Profile | `fallback_providers` |
|---|---|
| `jobcron-orchestrator`, `jobcron-worker`, `jobcron-worker-2` | `[{"provider": "anthropic", "model": "claude-opus-5-5"}]` |
| `jobcron-reviewer` | `[{"provider": "anthropic", "model": "claude-fable-5-2"}]` |

| Auxiliary task | `auxiliary_fallback_chain.<task>` (all four profiles) |
|---|---|
| `title_generation`, `memory_query_rewrite`, `tts_audio_tags`, `profile_describer`, `skills_hub`, `vision` | `[{"provider": "anthropic", "model": "claude-haiku-5-5"}]` |
| `compression`, `goal_judge`, `review`, `background_review`, `kanban_decomposer`, `triage_specifier`, `curator`, `monitor`, `approval`, `mcp` | `[{"provider": "anthropic", "model": "claude-opus-5-5"}]` |

On 2026-11-11 the four profiles had exactly these sixteen auxiliary tasks with a `provider` and `model` (all `claude-subscription` / `claude-opus-5-5`), read by name with `hermes -p <profile> config get --json auxiliary`. The `auxiliary` section also has `moa_reference` and `moa_aggregator`. These are Hermes default entries (`hermes_cli/config_defaults.py:817-818`, provider `auto`, no model) and are not in `HELPER_TASKS`, so they get no fallback chain.

### Compression fallback model check

1. `check_compression_model_feasibility` (`agent/conversation_compression.py:2085`) runs at session start. It uses the `compression` fallback chain only when the primary compression route cannot build a client (lines 2105-2112).
2. When the check does run, two rules apply:
   - A context window below `MINIMUM_CONTEXT_LENGTH` = 64,000 tokens (`agent/model_metadata.py:272`) raises an error, and the session does not start.
   - A context window below the profile's `compression.threshold_tokens` lowers that threshold for the session.
3. When the chain is used later, after a compression call fails, an entry whose context window is below 64,000 tokens is skipped (`_task_minimum_context_length` and `_context_too_small`, `agent/auxiliary_client.py:4380-4382` and `:4397`).
4. The check also runs again after the main runtime changes, for example when a fallback activates (`revalidate_compression_feasibility`, `agent/conversation_compression.py:2177`), and it can be deferred until a request first reaches 64,000 tokens (`ensure_compression_feasibility_checked`, line 2193).
5. **Result (card `t_731d4476`, 2026-11-11; no model call and no network request).** `claude-opus-5-5` as the `compression` fallback chain model on provider `anthropic` passes the check for all four profiles.

   | Profile | Main model (provider `claude-subscription`) | Main context window | Compression trigger (`threshold_tokens`) | Fallback model context window | Result |
   |---|---|---|---|---|---|
   | `jobcron-orchestrator` | `claude-opus-5-5` | 1,000,000 | 150,000 (configured cap) | 1,000,000 | pass |
   | `jobcron-worker` | `claude-opus-5-5` | 1,000,000 | 500,000 | 1,000,000 | pass |
   | `jobcron-worker-2` | `claude-opus-5-5` | 1,000,000 | 500,000 | 1,000,000 | pass |
   | `jobcron-reviewer` | `claude-fable-5-1` | 1,000,000 | 500,000 | 1,000,000 | pass |

   - **How the numbers were obtained.** `get_model_context_length` (`agent/model_metadata.py:2245`) was run with the installed Hermes Python for each profile home, with network connections blocked, no `.env` loaded and no API key. For `claude-opus-5-5` on `anthropic` at `https://api.anthropic.com` it returned 1,000,000: no persistent cache entry (step 1, line 2303); the live `/v1/models` step is skipped without a key (step 4, lines 2325-2329; `_query_anthropic_context_length` at line 1670 returns nothing for an empty key); the models.dev lookup without network (`lookup_models_dev_context`, step 5, line 2330) gives 1,000,000; the built-in table entry `claude-opus-5` also gives 1,000,000 (line 293, used in step 8, line 2353). Each main model on `claude-subscription` also resolves to 1,000,000, which matches `MODELS` in `plugins/model-providers/claude-subscription/compat.py`.
   - **Trigger.** Each profile has `compression.threshold` 0.5 and no `model.max_tokens`. `_compute_threshold_tokens` (`agent/context_compressor.py:2863`) gives 1,000,000 × 0.5 = 500,000. `jobcron-orchestrator` has `compression.threshold_tokens` 150,000, which caps its trigger (`_effective_threshold_cap`, line 2759); the other three profiles have no value.
   - **Comparison.** 1,000,000 is at least `MINIMUM_CONTEXT_LENGTH` 64,000 (`agent/model_metadata.py:272`), so no error is raised (`agent/conversation_compression.py:2149`). 1,000,000 is at least each trigger, so the trigger is not lowered (line 2160). When the main runtime itself is on the fallback (`claude-opus-5-5`, or `claude-fable-5-2` for `jobcron-reviewer`, both 1,000,000 by the same offline lookup), the triggers stay 150,000 and 500,000, and the result is the same.
   - **Limit.** At run time, with the Console key, Hermes first asks Anthropic's `/v1/models` for `max_input_tokens` (step 4). This card did not read that value: the single allowed request returned identifiers only. If Anthropic reports a value below the trigger but at least 64,000, Hermes lowers the trigger for that session (lines 2160-2164); the session still starts.

### Apply steps (a later card, with separate human authorization for the live writes)

1. The owner completes section 4 for all four profiles. On 2026-11-11 the owner wrote the replacement key to the four profile `.env` files (controller check by variable name and `auth list` source only). Confirm step 7 of section 4 (`auth.adopt_external_logins` is `false`) before step 4 below. Done by card `t_b399f9f3` on 2026-11-11 (see "Live rollout record" below). In the order that card specified, `auth.adopt_external_logins` was set to `false` directly after step 4 below, in the same run (the last step 4 apply started at 11:14:02 KST).
2. Read the identifiers (section 5) and complete the compression check above. Done by card `t_731d4476`.
3. In the repository, add `fallback_providers` and `auxiliary_fallback_chain` to the four roster entries. Update `test_repository_roster_declarations` in `tests/test_fallback_provider_settings.py`, run `python3 tests/gen_fixtures.py` and the test contract, and get the change reviewed and committed. Done by card `t_731d4476`. From that commit until step 4 is done, `scripts/verify-state` in live mode reports `fallback drift` for the four profiles.
4. For each profile, preview the change, then apply it:

   ```sh
   scripts/switch-profile-model --profile <profile> --apply-fallbacks --dry-run
   scripts/switch-profile-model --profile <profile> --apply-fallbacks
   ```

   Done by card `t_b399f9f3` on 2026-11-11 for all four profiles.
5. Run `scripts/verify-state`. The expected result is no `fallback drift` line. Done by card `t_b399f9f3` on 2026-11-11: no `fallback drift` line.

### Live test plan: make the primary provider fail for one run

1. **Method (read from source, not run yet).** Run one one-shot command with a per-invocation model override that the claude-subscription plugin rejects:

   ```sh
   hermes -p jobcron-worker -z "Reply with the single word OK." \
     -m not-an-allowlisted-model --provider claude-subscription --usage-file <path outside the repository>
   ```

2. **Why it is expected to work:**
   - `-m/--model` and `--provider` apply to this invocation only and change no `config.yaml` (`hermes_cli/_parser.py:161-167`).
   - The plugin's `_validate` rejects a model id outside its allowlist with `ProviderError` before it starts the Claude CLI (`plugins/model-providers/claude-subscription/client.py:192-196`), so the main model makes no subscription request.
   - Hermes classifies an exception with no HTTP status as `unknown` (`agent/error_classifier.py:66`). It retries up to the retry budget; each retry fails locally in the same way. Hermes then activates the next `fallback_providers` entry (`agent/turn_api_error.py:357-373`).
   - One-shot mode passes `get_fallback_chain(cfg)` to the agent (`hermes_cli/oneshot.py:585`).
3. **Known limits:**
   - The automatic session title runs in one-shot mode (`hermes_cli/oneshot.py:57-66`). Its auxiliary route is still `claude-subscription` with a valid model, so it can make one small subscription request. The `auxiliary.by_task` section of the usage file shows whether it ran.
   - Whether Hermes rejects the unknown model before the agent starts is not verified. In that case the run ends with no request and no fallback, and no safe forced-failure method is confirmed.
   - An environment override of `HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE` for one run does not work: the profile `.env` is loaded with `override=True` (`hermes_cli/env_loader.py:507`) and replaces the shell value.
   - The plugin's own failure paths at `client.py:634-641` (rate-limit rejection, runtime and protocol errors) occur only after the Claude CLI has started. They cannot be produced without a subscription request.
4. **Expected evidence.** The usage file names the `anthropic` provider and the fallback model. The response is "OK". `hermes -p jobcron-worker config get model.default` is unchanged.

### Live rollout record (card `t_b399f9f3`, 2026-11-11)

Authority: owner, Telegram 2026-11-09 (apply to the four profiles after a backup of each `config.yaml`, then a smoke test that does not spend the subscription); owner, Telegram 2026-11-11 (live changes approved to run without the owner present; "Leave the Jobcron board check paused.").

1. **Backups** (`cp -p`, each confirmed identical with `cmp`), one per profile, in `/Users/chanbla11mit/.hermes/profiles/<profile>/`:
   - `jobcron-orchestrator`: `config.yaml.pre-anthropic-fallback-20261111-111306`
   - `jobcron-worker`: `config.yaml.pre-anthropic-fallback-20261111-111306`
   - `jobcron-worker-2`: `config.yaml.pre-anthropic-fallback-20261111-111306`
   - `jobcron-reviewer`: `config.yaml.pre-anthropic-fallback-20261111-111306`

   `scripts/switch-profile-model` also wrote its own backups: `config.yaml.pre-switch-20261111-111316` (`jobcron-orchestrator`), `-111332` (`jobcron-worker`), `-111347` (`jobcron-worker-2`) and `-111402` (`jobcron-reviewer`).
2. **Applied values.** The `--dry-run` preview for each profile listed 17 `hermes config set` commands with exactly the values in "Intended values" above: `fallback_providers` and the `fallback_chain` of all 16 helper tasks. The apply run then wrote them (exit status 0 for each profile). Read back with `hermes -p <profile> config get --json fallback_providers`:
   - `jobcron-orchestrator`, `jobcron-worker`, `jobcron-worker-2`: `[{"provider": "anthropic", "model": "claude-opus-5-5"}]`
   - `jobcron-reviewer`: `[{"provider": "anthropic", "model": "claude-fable-5-2"}]`

   A comparison of each `config.yaml` with its `pre-anthropic-fallback` backup, by key path only, found exactly 18 changed key paths per profile: `fallback_providers`, the 16 `auxiliary.<task>.fallback_chain` keys and `auth.adopt_external_logins`.
3. **Primary model unchanged.** `model.provider` is `claude-subscription` on all four profiles. `model.default` is `claude-opus-5-5` on the first three profiles and `claude-fable-5-1` on `jobcron-reviewer`.
4. **Billing boundary.** `hermes -p <profile> config set auth.adopt_external_logins false` for each of the four profiles; `config get auth.adopt_external_logins` reads `false` on each. `hermes -p <profile> auth list anthropic` lists exactly one entry on each profile: label `ANTHROPIC_API_KEY`, type `api_key`, source `env:ANTHROPIC_API_KEY`. No `claude_code` or `hermes_pkce` entry is listed, and the command reports that external CLI logins are not adopted.
5. **verify-state (live mode).** No `fallback drift` line and no FAIL line that names one of the four profiles. The run printed 7 FAIL lines, all about board or gateway state, which the card classified as present before this card: one line "multi-board gateway is still pinned to one database via HERMES_KANBAN_DB", one line "unable to read open Cha PT card list", and five lines "unable to read open project card list" (for the boards `jobcron`, `cha-pt`, `harness`, `jss-genr` and `anki`).
6. **Board check deployment (`jobcron-orchestrator` only).**
   - Backups in `/Users/chanbla11mit/.hermes/profiles/jobcron-orchestrator/scripts/`: `orchestrator_board_check.py.pre-20261111-112056` and `orchestrator_board_check.json.pre-20261111-112056` (`cp -p`, confirmed with `cmp`).
   - `scripts/orchestrator-board-check` was copied to `scripts/orchestrator_board_check.py` and `deployment/orchestrator-board-check/jobcron-orchestrator.json` to `scripts/orchestrator_board_check.json` in the profile; both copies were confirmed with `cmp`.
   - `hermes -p jobcron-orchestrator cron edit 5afc6729a9c4 --prompt "$(cat deployment/orchestrator-board-check/cron-prompt.md)"`. The stored prompt equals `cron-prompt.md` without its final newline (the shell command substitution removes it). A comparison of every other field of the job in `cron/jobs.json` before and after the edit found no change.
   - Job `5afc6729a9c4` stays paused (`enabled` false, `state` `paused`), by owner decision of 2026-11-11. `cron resume`, `cron run` and `cron tick` were not run.
   - `python3 <home>/scripts/orchestrator_board_check.py --status` printed `primary claude-subscription` for each of `jobcron-orchestrator`, `jobcron-worker`, `jobcron-worker-2` and `jobcron-reviewer`.
7. **Live test result: observed.** One run, at 11:21:27 to 11:21:49 KST, of the command in "Live test plan" step 1 on `jobcron-worker`, with the usage file `/Users/chanbla11mit/.hermes/profiles/harness-orchestrator/cache/scratch/t_b399f9f3-jobcron-worker-fallback-usage.json`. Exit status 0.
   - Reply: "OK".
   - Usage file: provider `anthropic`, model `claude-opus-5-5`, 1 main API call; input 4, output 4, cache read 0, cache write 30,006, total 30,014 tokens.
   - Usage file, auxiliary: task `title_generation`, 1 API call; input 2, output 38, cache write 920, total 40 tokens. The usage file does not record which provider that call used. Its configured route is `claude-subscription` with `claude-opus-5-5`, so it was probably the one small subscription request that "Known limits" above describes.
   - Session row in the profile `state.db` (read-only query of the model and billing columns): model `claude-opus-5-5`, billing provider `anthropic`, billing base URL `https://api.anthropic.com`.
   - `agent.log` has no `Fallback activated` line from this run, and no line at all from this run. One-shot mode calls `logging.disable(logging.CRITICAL)` (`hermes_cli/oneshot.py:257`), which drops every log record, including records for file handlers. The comment above that call (lines 255-256) says file handlers keep working; that statement does not match the behavior of `logging.disable`.
   - During the run Hermes ran its own Python dependency sync: stderr printed "Installing Python dependencies", and `logs/update_receipts/latest.json` in the `jobcron-worker` profile records `kind` `sync`, outcome `ok`, from 02:21:39 to 02:21:45 UTC. This card did not start an install; the sync was started by Hermes.
   - After the run, `hermes -p jobcron-worker config get model.default` is still `claude-opus-5-5`, and `model.provider` is still `claude-subscription`.

## 7. Revert

Owner decision, 2026-11-11: the fallback stays configured after 2026-11-19 (section 8, "Credit behaviour and owner decision"). Run this section only after a new owner decision to remove the fallback.

1. For each of the four profiles, preview and then clear the fallback values:

   ```sh
   scripts/switch-profile-model --profile <profile> --clear-fallbacks --dry-run
   scripts/switch-profile-model --profile <profile> --clear-fallbacks
   ```

2. In the repository, remove `fallback_providers` and `auxiliary_fallback_chain` from the four roster entries. Restore the assertion in `test_repository_roster_declarations`, run `python3 tests/gen_fixtures.py` and the test contract, and get the change reviewed and committed.
3. The owner removes the key from the four profile `.env` files and restores `auth.adopt_external_logins` to its earlier value `true`:

   ```zsh
   for p in jobcron-orchestrator jobcron-worker jobcron-worker-2 jobcron-reviewer; do hermes -p "$p" config unset ANTHROPIC_API_KEY; done
   for p in jobcron-orchestrator jobcron-worker jobcron-worker-2 jobcron-reviewer; do hermes -p "$p" config set auth.adopt_external_logins true; done
   ```

   - `config unset ANTHROPIC_API_KEY` removes the `ANTHROPIC_API_KEY` line from the profile `.env`, removes the variable from the process environment and removes the credential pool entries seeded from it (`unset_config_value`, `hermes_cli/config.py:3800-3819`; `remove_provider_env_credential`, `hermes_cli/credential_lifecycle.py:202-221`; `remove_env_value`, `hermes_cli/config.py:2808-2826`). It prints `✓ Unset ANTHROPIC_API_KEY from <path of the profile .env>`, or exits with a non-zero status and `Config key not set: ANTHROPIC_API_KEY` when the profile has no such line.
   - This replaces the earlier `auth remove` step: no `auth.json` entry exists to remove.
   - Then `hermes -p <profile> auth list anthropic` must list no entry with source `env:ANTHROPIC_API_KEY`.
4. The owner deletes (revokes) the key in the Anthropic Console, under API keys.
5. Run `scripts/verify-state`. The expected result is no `fallback drift` line, and `hermes -p <profile> config get --json fallback_providers` prints `[]` for each profile.

## 8. The 18 other claude-subscription profiles

Card `t_875f53f3` (repository step, no live change). A later card applies the values to the live profiles.

- **Owner decision.** Owner, Telegram, 2026-11-11: "Fallback all plus main. I want to keep it as a backup, but I'm not going to fill it up myself. I want to keep it just in case Claude adds more credits or I get credits somehow."
- **Profiles.** `default`, `advisor`; `chapt-orchestrator`, `chapt-worker`, `chapt-worker-2`, `chapt-reviewer`; `harness-orchestrator`, `harness-worker`, `harness-worker-2`, `harness-reviewer`; `jss-orchestrator`, `jss-worker`, `jss-worker-2`, `jss-reviewer`; `anki-orchestrator`, `anki-worker`, `anki-worker-2`, `anki-reviewer`. The GLM (`zai`) profiles and the retired entries get no fallback declaration.

### Declared values

| Profile | `fallback_providers` |
|---|---|
| `advisor`, `chapt-reviewer`, `harness-reviewer`, `jss-reviewer`, `anki-reviewer` | `[{"provider": "anthropic", "model": "claude-fable-5-2"}]` |
| the other 13 profiles | `[{"provider": "anthropic", "model": "claude-opus-5-5"}]` |

`auxiliary_fallback_chain` is the same for all 18 profiles as for the four Jobcron profiles (the auxiliary task table in section 6): `claude-haiku-5-5` for the six tasks `title_generation`, `memory_query_rewrite`, `tts_audio_tags`, `profile_describer`, `skills_hub` and `vision`, and `claude-opus-5-5` for the other ten tasks, all with provider `anthropic` and no `timeout`.

On 2026-11-11 each of the 18 profiles had exactly the sixteen auxiliary tasks of `HELPER_TASKS`, each with provider `claude-subscription` and model `claude-opus-5-5`. None had `fallback_providers`, `fallback_model` or a non-empty `fallback_chain`, and none had `auth.adopt_external_logins` set (the default `true` applies). These values were read by key name from each `config.yaml` (`~/.hermes/config.yaml` for `default`), without running Hermes. The auxiliary task list therefore does not differ from the Jobcron list.

### Credential: the 17 named profiles (the owner does this)

Run the three commands below in zsh, once, in one terminal. They work in the same way as section 4 step 2: `read -rs` keeps the key only in the shell variable `K`, and each `config set` writes it to the `.env` file of that profile.

```zsh
read -rs "K?Anthropic API key: "; echo
for p in advisor chapt-orchestrator chapt-worker chapt-worker-2 chapt-reviewer harness-orchestrator harness-worker harness-worker-2 harness-reviewer jss-orchestrator jss-worker jss-worker-2 jss-reviewer anki-orchestrator anki-worker anki-worker-2 anki-reviewer; do hermes -p "$p" config set ANTHROPIC_API_KEY "$K"; done
unset K
```

Section 4 steps 3 to 5 apply unchanged to these 17 profiles. Then, for each of the 17 profiles, run `hermes -p <profile> auth list anthropic`. The expected output is one entry, with label `ANTHROPIC_API_KEY` and source `env:ANTHROPIC_API_KEY`. If an entry with another source is listed, do not continue with the live apply steps below for that profile, and report it to the owner (section 4 step 6).

### Credential: the default profile

**Result: default profile: no supported key location without the root .env; owner decision needed.**

The owner decided on 2026-11-11: the default profile gets the fallback values and no key (item 4).

1. **The root `.env` stays forbidden.** The `.env` file of the default profile is `~/.hermes/.env`. Section 4 step 5 forbids writing the key there, because the gateway process of the default profile loads that file into the environment that it shares with every profile it serves. That prohibition stays.
2. **What `hermes auth add anthropic --type api-key` does in the default profile (read from source, not run).**
   - Which profile a `hermes` command without `-p` uses depends on its environment (`_apply_profile_override`, `hermes_cli/main.py:594-626`). If the environment variable `HERMES_HOME` names a directory whose parent directory is named `profiles`, the command uses that profile (lines 607-609). Every terminal of a dispatched worker or reviewer has `HERMES_HOME` set in this way, for example `~/.hermes/profiles/harness-worker`. Otherwise the command uses the default profile, unless the file `~/.hermes/active_profile` names another profile (lines 611-624); that file is not read when `HERMES_SUPERVISED_CHILD` is set, which is the case in a dispatched session (`_under_gateway_supervisor`, line 557). On 2026-11-11 that file did not exist. With `-p default` a command uses the root `~/.hermes` in every one of these cases (`resolve_profile_env`, `hermes_cli/profiles.py:2573-2575`; `profile_root_for_env_home`, lines 2551-2559). Every command for the default profile in this section therefore has the form `hermes -p default ...`.
   - Without `--api-key`, the command asks for the key with a prompt that does not show the typed text (`masked_secret_prompt`, `hermes_cli/auth_commands.py:360-362`), and stores it as a pool entry with source `manual` (lines 368-373).
   - In the default profile the profile home is the root, so `_global_auth_file_path()` returns `None` (`hermes_cli/auth.py:509-518`). `load_pool` therefore records no borrowed rows (`agent/credential_pool.py:3136-3143`), `add_entry` calls `_persist` (`agent/credential_pool_admin.py:131-132`), `_profile_owns_pool_provider` returns `True` (`agent/credential_pool.py:845-848`), and `persist_pool_entries` calls `write_credential_pool` (`agent/credential_pool.py:930` and `:948`). That function writes `credential_pool.anthropic` in the active `auth.json` (`hermes_cli/auth.py:1099-1117`), which is `~/.hermes/auth.json` (`_auth_file_path`, lines 496-497). The merge that only updates existing rows and drops the new row (`_update_root_pool_rows`, `agent/credential_pool.py:868-908`; [bug report](../docs/bugs/261109-anthropic-api-key-auth-add-dropped-in-named-profile.md)) is reached only in a named profile. **The key is stored correctly in the default profile.**
   - **The fallback uses the stored entry.** On fallback activation, `try_activate_fallback` calls `resolve_provider_client` for the entry's provider (`agent/chat_completion_helpers.py:2074` and `:2110`). For `anthropic`, `_resolve_registry_branch` calls `_resolve_api_key_branch` (`agent/auxiliary_client.py:5417`), which calls `_try_anthropic` (lines 5299-5302). `_try_anthropic` uses the selected entry of the `anthropic` credential pool first (lines 3069-3071). `_rebind_fallback_credential_pool` also attaches `load_pool("anthropic")` to the agent (`agent/chat_completion_helpers.py:1896-1913`).
3. **Why this is still not a supported location.** `~/.hermes/auth.json` is also the root store that every named profile reads. A named profile with no `credential_pool.anthropic` rows of its own reads the rows of the root store (`read_credential_pool`, `hermes_cli/auth.py:952-976`; `load_pool`, `agent/credential_pool.py:3076`). The entry that Hermes adds from the profile `.env` key (section 4 step 4) does not give a named profile its own rows: `persist_pool_entries` sends it to the merge into the root store that only updates existing rows, which adds no row (`agent/credential_pool.py:930-934` and `:868-908`). An `anthropic` row in `~/.hermes/auth.json` therefore has these effects:
   - The key reaches every named profile that has no `anthropic` rows of its own, including the GLM (`zai`) profiles and the retired profiles. This is the same sharing for which section 4 step 5 forbids `~/.hermes/.env`.
   - In each of those profiles the row counts as an explicit `anthropic` configuration (`_explicit_pool_entry_present`, `hermes_cli/auth.py:1262-1265`; `_pool_entry_is_explicit`, lines 1310-1321). In a profile whose auxiliary route is automatic provider selection, this allows the auxiliary client to select `anthropic` (`agent/auxiliary_client.py:2187-2193`).
   - `hermes -p <profile> auth list anthropic` lists the borrowed row, with source `manual`, next to the `env:ANTHROPIC_API_KEY` row (`auth_list_command` loads the pool at `hermes_cli/auth_commands.py:520`). Section 4 step 6 and the check above treat an entry with another source as a reason to stop. This applies also to the four Jobcron profiles, which are live.
4. **Owner decision (option A).** Owner, Telegram, 2026-11-11, relayed by `harness-orchestrator` on card `t_875f53f3`: the default profile receives the fallback values and `auth.adopt_external_logins` `false` (with `hermes -p default`), and it receives no API key: none in `~/.hermes/.env` and none in `~/.hermes/auth.json`. Its fallback stays inactive until a key exists. Without a key, the fallback of the default profile can still obtain an OAuth token:
   - While `auth.adopt_external_logins` is `true` (the current value, by default), the fallback can run on the Claude Code login in the macOS Keychain or in `~/.claude/.credentials.json`. With no `anthropic` pool entry, `_try_anthropic` calls `resolve_anthropic_token` (`agent/auxiliary_client.py:3069-3075`). With none of `ANTHROPIC_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_API_KEY` in the environment, that function reads the Claude Code login directly (`agent/anthropic_credentials.py:691-709`; `_resolve_claude_code_token_from_credentials`, lines 611-627; `read_claude_code_credentials`, lines 351-368). The fallback would then run on the Claude Code login, which uses the same Max plan allowance as `claude-subscription`. Section 4 step 7 exists to prevent this.
   - `load_pool` adds a `claude_code` pool entry only when `anthropic` counts as explicitly configured in the profile (`_seed_anthropic_singletons`, `agent/credential_pool.py:2587-2594` and 2617-2625; `is_provider_explicitly_configured`, `hermes_cli/auth.py:1344-1364`). The fallback values do not count: `_config_selects_provider` checks `model.provider`, the `provider` of each auxiliary task and the MoA slots, and does not check `fallback_providers` or `fallback_chain` (`hermes_cli/auth.py:1232-1259`). In `~/.hermes/config.yaml` on 2026-11-11 (read by key name), `model.provider` and the `provider` of all 16 auxiliary tasks were `claude-subscription`, and there was no `moa` section, so the default MoA presets apply; they name `openai-codex` and `openrouter` (`hermes_cli/config_defaults.py:1437-1443`). Without a key, the default profile therefore gets no `claude_code` pool entry, and nothing is written to `~/.hermes/auth.json`.
   - With `false`, Hermes does not read the Claude Code login (`agent/anthropic_credentials.py:358-360`) and removes a stored `claude_code` entry (`agent/credential_pool.py:2626-2629`). A `hermes_pkce` entry is added only from `~/.hermes/.anthropic_oauth.json` (`read_hermes_oauth_credentials`, `agent/anthropic_credentials.py:809-812`); on 2026-11-11 that file did not exist (checked by file name only). With no pool entry and none of `ANTHROPIC_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_API_KEY` in the environment, `_try_anthropic` builds no client (`agent/auxiliary_client.py:3072-3077`; `resolve_anthropic_token`, `agent/anthropic_credentials.py:691-709`), and the fallback entry is skipped with the log line "Fallback to anthropic failed: provider not configured" (`agent/chat_completion_helpers.py:2112-2115`).
   - For this reason the live apply steps below set `auth.adopt_external_logins` to `false` on the default profile before they apply its fallback values.

### Live apply steps (a later card, with separate human authorization for the live writes)

1. The owner completes the credential step for the 17 named profiles, and the `auth list anthropic` check passes for each of them. The default profile gets no key ("Credential: the default profile", item 4, owner decision option A).
2. **Backups.** For each of the 18 profiles, copy `config.yaml` with `cp -p` to `config.yaml.pre-anthropic-fallback-<timestamp>` in the same directory, and confirm the copy with `cmp`, as in section 6, "Live rollout record", step 1. For `default` the file is `~/.hermes/config.yaml`; for a named profile it is `~/.hermes/profiles/<profile>/config.yaml`.
3. **Apply.** For each profile, run section 6, "Apply steps", step 4: `scripts/switch-profile-model --profile <profile> --apply-fallbacks --dry-run`, compare the 17 planned `hermes config set` commands with "Declared values" above, then run `scripts/switch-profile-model --profile <profile> --apply-fallbacks`. For `default` the script runs `hermes` without `-p` (`scripts/switch-profile-model`, `prefix` at line 167) and passes its own environment to that command (`subprocess.run` without an `env` argument, line 179). A `hermes` command without `-p` follows an exported `HERMES_HOME` that names a profile directory (`hermes_cli/main.py:607-609`; "Credential: the default profile", item 2), so in a terminal of a dispatched worker the script would back up `~/.hermes/config.yaml` but write the 17 values to the worker's own `config.yaml`. For `default`, therefore run both commands with `HERMES_HOME` removed from the environment:

   ```sh
   env -u HERMES_HOME scripts/switch-profile-model --profile default --apply-fallbacks --dry-run
   env -u HERMES_HOME scripts/switch-profile-model --profile default --apply-fallbacks
   ```

   Without `HERMES_HOME` and without `HERMES_DATA_DIR_SUFFIX`, Hermes uses `~/.hermes` (`get_hermes_home`, `hermes_constants.py:111-118`; `get_process_hermes_home`, lines 160-169; `_get_platform_default_hermes_home`, lines 51-58). Outside a dispatched session the command then follows `~/.hermes/active_profile` if that file exists (`hermes_cli/main.py:611-624`), so confirm first that it does not exist. The script finds and backs up `~/.hermes/config.yaml` through its `--home-root` option, which does not depend on `HERMES_HOME` (`scripts/switch-profile-model`, lines 57-58 and 119).
4. **Billing boundary.** For each profile, set `auth.adopt_external_logins` to `false` as in section 4 step 7: `hermes -p <profile> config set auth.adopt_external_logins false`, and `hermes -p default config set auth.adopt_external_logins false` for `default`. Do not use the form without `-p` for `default`: in a terminal of a dispatched worker it writes to the worker's own profile ("Credential: the default profile", item 2). For `default`, do this step before step 3, because the default profile has no API key (see "Credential: the default profile", item 4).
5. **Read-back**, as in section 6, "Live rollout record", steps 2 to 4: `hermes -p <profile> config get --json fallback_providers`, `hermes -p <profile> config get auth.adopt_external_logins` and `hermes -p <profile> auth list anthropic` for each profile, with `-p default` for `default`, so that the read-back for `default` reads `~/.hermes/config.yaml` and not the configuration of the terminal's own profile; a comparison of each `config.yaml` with its backup from step 2 by key path only, which is expected to find exactly 18 changed key paths (`fallback_providers`, the 16 `auxiliary.<task>.fallback_chain` keys and `auth.adopt_external_logins`); and `model.provider` and `model.default` unchanged. If the comparison for `default` finds no changed key path, the values were written to another profile: stop and report it to the owner. The expected `auth list anthropic` result is one entry with source `env:ANTHROPIC_API_KEY` for each of the 17 named profiles, and no entry for `default`, which has no key.
6. **verify-state.** Run `scripts/verify-state` in live mode. The expected result is no `fallback drift` line. From the commit of card `t_875f53f3` until step 3 is done for all 18 profiles, live `scripts/verify-state` reports `fallback drift` for these profiles.

Revert: section 7 applies to these 18 profiles in the same way. For `default`, run the commands of its step 1 with `env -u HERMES_HOME`, as in step 3 above, and use `hermes -p default` for every direct `hermes` command. Its step 3 applies to the 17 named profiles, and not to the default profile, which has no key (owner decision option A); `auth.adopt_external_logins` of `default` is restored with `hermes -p default config set auth.adopt_external_logins true`.

### Credit behaviour and owner decision

Anthropic documentation (cited, not fetched on card `t_875f53f3`):

- https://support.anthropic.com/en/articles/8977456-how-do-i-pay-for-my-claude-api-usage: API usage is paid from prepaid credits. Failed requests are not charged. When the credits run out, requests stop, unless auto-reload buys more credits.
- https://platform.claude.com/docs/en/about-claude/api-credits-for-subscribers: Max, Ultra and Team plans receive monthly API credits, which expire at the end of each billing cycle. When these credits are used up, requests stop until the next monthly credits arrive, and the API returns "Your credit balance is too low to access the Anthropic API".

Owner decision, 2026-11-11: the fallback stays configured after 2026-11-19, when the USD 200 of Console promotional credits expire, and the owner does not buy new credits. With no credits, a fallback request fails with the error "Your credit balance is too low to access the Anthropic API", and nothing is charged while auto-reload is off. Owner, Telegram, 2026-11-11: Console auto-reload is off. When credits are added again (monthly plan credits or other credits), the configured fallback uses them without a configuration change.
