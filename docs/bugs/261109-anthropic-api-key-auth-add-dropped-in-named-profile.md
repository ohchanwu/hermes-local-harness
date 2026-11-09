# `hermes -p <profile> auth add anthropic --type api-key` reports success but stores no credential in a named profile

Reported: 2026-11-09, by the harness controller (session `20261018_211610_98474e8e`; board `harness`). Recorded from harness card `t_11314ed2`.

All times are KST (UTC+09:00). Source references are to the installed Hermes Agent (`/Users/chanbla11mit/.hermes/hermes-agent/`, commit `9cf7960f27`), read without running, importing or changing it. No `auth.json` or `.env` file was opened on this card. The live observations below are the controller's report from 2026-11-09 14:2x to 14:5x; the harness did not run any `hermes auth` or `hermes config` command. This report contains no key value.

## Summary
The owner added an Anthropic Console API key to the named profile `jobcron-worker` with `hermes -p jobcron-worker auth add anthropic --type api-key --label anthropic-console-2611`. Hermes printed a success message, but no `auth.json` file received the credential, and `hermes -p jobcron-worker auth list` does not show it. The cause is in Hermes: for a provider whose OAuth refresh tokens are single-use, a named profile that has no rows of its own for that provider writes pool changes back to the root `auth.json` in an update-only merge, and that merge drops a new row. The workaround is to put the key in the profile `.env` as `ANTHROPIC_API_KEY` with `hermes -p <profile> config set ANTHROPIC_API_KEY ...`. The procedure `procedures/anthropic-api-fallback.md` is corrected to use the workaround.

## Observed
- The owner ran `hermes -p jobcron-worker auth add anthropic --type api-key --label anthropic-console-2611` on this Mac. It printed `Added anthropic credential #1: "anthropic-console-2611"`.
- Afterwards, `hermes -p jobcron-worker auth list` shows only the `copilot` and `openai-codex` providers.
- `hermes -p jobcron-worker config path` prints the `jobcron-worker` profile's `config.yaml` (`~/.hermes/profiles/jobcron-worker/config.yaml`), and `HOME` is the user's home directory, so the command ran in the correct profile.
- No `auth.json` file was changed by the command: the modification times of the `auth.json` files of `jobcron-worker`, `jobcron-worker-2` and `jobcron-reviewer` stay at 13:58 on 2026-11-09, and the modification time of the root `~/.hermes/auth.json` stays on 2026-10-25.

## Expected
One of the following:
- The new row is stored in the `credential_pool.anthropic` list of the profile's own `auth.json`, and `auth list` shows it; or
- The command fails with an error that says the credential was not stored, and exits with a non-zero status.

## Cause (established from source)
1. `anthropic` is in `SINGLE_USE_REFRESH_POOL_PROVIDERS` (`hermes_cli/auth_oauth_grants.py:27`).
2. `_add_api_key_credential` (`hermes_cli/auth_commands.py:360-375`) builds a `PooledCredential` with source `manual`, calls `pool.add_entry(entry)` (line 373) and then prints the success message (line 374) without checking whether anything was written.
3. `add_entry` (`agent/credential_pool_admin.py:110-133`) appends the entry in memory. The profile writes its own rows directly only when the pool holds rows borrowed from the root store (`_borrowed_root_ids`, lines 117-130). In a named profile that has no `anthropic` rows of its own and with no `anthropic` rows in the root store, nothing is borrowed, so `add_entry` calls `self._persist()` (line 132).
4. `_persist` (`agent/credential_pool.py:1145`) calls `persist_pool_entries` at line 1154 (`persist_pool_entries` is defined at `agent/credential_pool.py:912-950`). Because `anthropic` is a single-use refresh provider and the profile does not own `anthropic` rows (`_profile_owns_pool_provider`, line 839), and because the root `auth.json` path is available (`_borrowed_single_use_pool_root`, line 856), it calls `_update_root_pool_rows` instead of `write_credential_pool`.
5. `_update_root_pool_rows` (`agent/credential_pool.py:868-908`) is documented as an "UPDATE-ONLY merge": a borrower "may refresh the root's rows ... but never add or delete them". It only updates root rows whose `id` matches an incoming row. The new row has a new `id`, so it is dropped, and the root file is not saved because nothing changed. `persist_pool_entries` returns normally, and `_persist` does not report the dropped row.

The update-only routing exists to prevent a copy of a single-use OAuth refresh token in two `auth.json` files (comment in `persist_pool_entries`, issue `#100339`). An API key has no refresh token, but the routing is decided by provider name only.

## Impact
- The owner is told that the key was added when it was not. The Anthropic API fallback for the four Jobcron profiles (`procedures/anthropic-api-fallback.md`) would have no credential, and the defect would show only when the fallback is first used.
- The same path applies to the other providers in `SINGLE_USE_REFRESH_POOL_PROVIDERS` (`openai-codex`, `xai-oauth`, `nous`) when `--type api-key` is used in a named profile. This is read from source and was not observed.

## Workaround
Put the key in the profile `.env` as `ANTHROPIC_API_KEY`:
- `hermes -p <profile> config set ANTHROPIC_API_KEY <value>` routes a credential-shaped key name to the profile `.env` (`_is_env_config_key`, `hermes_cli/config.py:869-879`; `set_config_value`, `hermes_cli/config.py:3629-3638`; `save_provider_env_credential`, `hermes_cli/credential_lifecycle.py:163-199`). It prints only `✓ Set ANTHROPIC_API_KEY in <path of the profile .env>`.
- At every pool load, `_seed_from_env` (`agent/credential_pool.py:2951-2991`) adds an in-memory `anthropic` row with source `env:ANTHROPIC_API_KEY` and label `ANTHROPIC_API_KEY` (`_env_payload`, `agent/credential_pool.py:2899-2905`). `resolve_anthropic_token` (`agent/anthropic_credentials.py:691-709`) reads `ANTHROPIC_API_KEY` (line 702), but `ANTHROPIC_TOKEN` or `CLAUDE_CODE_OAUTH_TOKEN` in the same environment takes precedence (line 697). On 2026-11-09 the controller checked by variable name only that none of the four Jobcron profile `.env` files defines either name.
- `hermes -p <profile> config unset ANTHROPIC_API_KEY` removes the `.env` line (`unset_config_value`, `hermes_cli/config.py:3800-3819`; `remove_provider_env_credential`, `hermes_cli/credential_lifecycle.py:202-221`; `remove_env_value`, `hermes_cli/config.py:2808-2826`), and also prunes the rows seeded from that variable.
- Not yet observed live: that `auth list anthropic` shows the `env:ANTHROPIC_API_KEY` row after the `config set` command.
- Do not use `hermes auth add anthropic --type api-key` in a named profile until this defect is fixed.

## Repository change
- `procedures/anthropic-api-fallback.md`: the credential, verification and revert steps use `config set ANTHROPIC_API_KEY` and `config unset ANTHROPIC_API_KEY` instead of `auth add` and `auth remove`, and record the owner's decision on `auth.adopt_external_logins`.
- `tests/test_fallback_provider_settings.py`: one test checks those procedure steps.
- No Hermes source is changed from this repository.

## Upstream status
Upstream report: not filed (needs owner approval).
