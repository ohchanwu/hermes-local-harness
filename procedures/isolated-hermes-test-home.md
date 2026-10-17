# Isolated Hermes test home without dependency bootstrap (upgrade-safe)

Procedure owner: harness board. Evidence base: run48 on card `t_51cbb4e0`
(fresh `HERMES_HOME` triggered the dependency bootstrap and stopped the run)
and the four controller import-only probes stopped at scratch preparation,
the existing `.install.lock` and active-generation `.leases` writes.

Helper: `tests/hermes_isolated_home.py` (context manager `isolated_hermes_home()`
+ canonical exercise `exercise_import_and_help()`).
Tests: `tests/test_hermes_isolated_home.py` (focused: `python3 tests/test_hermes_isolated_home.py`).

## Read-only investigation summary

Installed Hermes under test: `v0.21.5+6751.g9cf7960` (stamp `9cf7960f`,
`updateMechanism: self`, source git), resolved via the `hermes` shim on `PATH`
(`/Users/chanbla11mit/.hermes/hermes-agent/.hermes/bin/hermes`).

How a fresh home bootstraps today (all verified by reading the installed
source, never modifying it):

1. The shim execs the **store Python** in isolated mode and imports
   `hermes_bootstrap`.
2. `hermes_bootstrap` → `hermes_cli.venv_sync.prepare_launch`
   (`hermes_cli/venv_sync.py:338`). Unless the command is `pm`, a metadata
   flag (`-h/--help/-V/--version`) is present, or
   `HERMES_DISABLE_LAZY_INSTALLS` is truthy, it resolves the *owning* root of
   the checkout. A temporary `HERMES_HOME` is a **borrowing** root
   (`pm/environments.py:41` `owning_home_root`), so
   `_prepare_borrowed_launch` syncs a dependency generation **of its own**
   under the borrowing root — the `.install.lock`, leases and environment
   writes that stopped the earlier probes.
3. `hermes_bootstrap` → `hermes_cli._early_recovery.recover_if_needed` — no
   `.repair-incomplete`/`.update-incomplete` marker exists on this install, so
   this is inert.
4. `hermes_bootstrap` → `pm.environments.activate_dependencies`
   (`pm/environments.py:380`). With no committed dependency state under the
   fresh home it calls `_require_own_dependencies`, which **returns early for
   a venv interpreter** (`sys.prefix != sys.base_prefix`,
   `pm/environments.py:374-375`): a venv interpreter keeps the packages it
   booted with. The store Python has none, so for it the function refuses
   ("no dependency environment is committed for this install; run `hermes pm
   repair`" — reproduced read-only under a fresh home, exit 1).

## Mechanism chosen and why it is safe

**Entry point:** the **committed venv interpreter** recorded in the install
state (`<dependency root>/installs/<install key>/facts.json` →
`packages.venv.environment`), launched as
`<venv python> -I -B <child script>` under a minimal environment:
`HOME`, `HERMES_HOME` and `TMPDIR` pointing at a fresh temp home,
`PATH=/usr/bin:/bin`, and `HERMES_DISABLE_LAZY_INSTALLS=true`.

- `HERMES_DISABLE_LAZY_INSTALLS` is **documented in the docs shipped with the
  installed Hermes** (`website/docs/reference/environment-variables.md:856`):
  "Internal PM policy used by tests and install probes. Truthy values refuse
  on-demand installation. It overrides the user-facing
  `security.allow_lazy_installs` setting." It makes `prepare_launch` return
  `None` (same code path the `pm` subcommand and `--help/--version` use), so
  no borrowed-launch dependency sync runs and no install lock/lease is taken.
- The venv-interpreter carve-out in `_require_own_dependencies`, the per-home
  scoping of `install_state_dir` and `get_default_hermes_root`'s
  profile-folding are **internal behaviours, not shipped documentation**. The
  card's constraint that an undocumented mechanism must be version-gated and
  snapshot-proven therefore applies, and both are implemented:
  - **Version gate:** the helper reads `displayVersion` passively from the
    install stamp and refuses on anything outside
    `TESTED_HERMES_VERSIONS = ("0.21.5+6751.g9cf7960",)` with a message that
    names what must be re-verified. Refusal is tested.
  - **Live install-state snapshot:** the test snapshots the *live* install
    directory (`~/.hermes/installs/<key>/`, excluding `.leases`, which churn
    with live processes by design) before and after the real exercise and
    asserts file list, sizes, mtimes and inodes are identical.
- `-B` keeps bytecode out of the checkout/venv; `-I` isolates the interpreter
  (no user site, no `PYTHON*` vars); the child blocks **all** `socket.socket`
  construction (no network; `socketpair` used by asyncio wakeup pipes is
  avoided by not running an event loop — import/help only).
- The isolated home itself is created under the test process's `TMPDIR`
  (never inside the worktree — fixture guards reject symlinks under the repo
  root) and is removed on context exit.

## What was actually exercised

`exercise_import_and_help()` (tests/test_hermes_isolated_home.py::RealExerciseTests):
under the fresh home the child imports `hermes_bootstrap` + `hermes_cli.main`
(import-only probe — exactly what previously bootstrapped) and then runs the
CLI-help-level action `hermes --help` through `hermes_cli.main.main()`.
Result on this machine (2026-10-17): rc=0, `usage: hermes ...` rendered, zero
stderr, **no dependency generation created under the isolated home**, and the
live install-state snapshot identical before/after. The installed `hermes`
shim under a fresh home is retained as the documented negative control: it
refuses with `hermes: no dependency environment is committed for this
install; run `hermes pm repair`` and exit 1 — the reason the committed venv
interpreter is the entry point instead.

## Manual use

```python
import sys; sys.path.insert(0, "tests")
from hermes_isolated_home import isolated_hermes_home
with isolated_hermes_home() as iso:
    script = iso.write_child("import", "MY_MARKER")
    result = iso.run(script)   # bounded, guarded, offline
```

or run the canonical exercise:

```sh
python3 tests/hermes_isolated_home.py   # prints a JSON receipt
python3 tests/test_hermes_isolated_home.py
```

## Limits

- Import/CLI-help-level actions only. The helper is not a harness for running
  agents, model calls, gateways or anything needing auth; those have their own
  authorization paths.
- The helper depends on the current bootstrap chain; after any Hermes upgrade,
  add the new version to `TESTED_HERMES_VERSIONS` only after re-verifying the
  three behaviours above (skip conditions of `prepare_launch`, venv carve-out
  of `_require_own_dependencies`, per-home install-state scoping) and re-running
  the snapshot test.
- `HERMES_DISABLE_LAZY_INSTALLS=true` disables lazy installs for the child
  process; it never changes live config, and the child writes only under its
  isolated home.
- The hermetic client tests in `tests/test_claude_subscription_provider.py`
  (their `ClientTests` isolated directory) never launch installed Hermes, so
  they keep their lighter existing isolation; adopting this helper there is
  not applicable (no installed-Hermes native/isolated-home test path exists
  in that file to convert).
