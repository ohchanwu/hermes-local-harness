"""Isolated HERMES_HOME for import/help-level probes of the installed Hermes.

Why this exists
---------------
Starting Hermes components with a fresh ``HERMES_HOME`` used to trigger the
dependency bootstrap: ``hermes_bootstrap`` → ``hermes_cli.venv_sync.prepare_launch``
treats a fresh home as a *borrowing* root and syncs a dependency generation of
its own (``.install.lock``, active-generation ``.leases`` writes, a new
environment tree).  Run48 on card t_51cbb4e0 and four controller import-only
probes were stopped by exactly that.

Mechanism (installed Hermes v0.21.5+6751.g9cf7960, verified read-only)
-----------------------------------------------------------------------
1. ``HERMES_DISABLE_LAZY_INSTALLS=true`` makes ``prepare_launch`` return None
   (venv_sync.py:362-367, same test as the ``pm`` subcommand and the
   ``-h/--help/-V/--version`` metadata flags).  The variable is documented in
   the docs shipped with the installed Hermes
   (website/docs/reference/environment-variables.md:856: "Internal PM policy
   used by tests and install probes. ... It overrides the user-facing
   ``security.allow_lazy_installs`` setting.").
2. With no committed dependency state under the isolated home,
   ``pm.environments.activate_dependencies`` falls through to
   ``_require_own_dependencies``, which *returns early for a venv interpreter*
   (``sys.prefix != sys.base_prefix`` — pm/environments.py:374-375): the
   interpreter keeps the packages it booted with.  So the child runs on the
   install's committed venv interpreter (recorded in the install state's
   ``facts.json``) and imports the checkout read-only.
3. The installed ``hermes`` shim itself cannot serve a fresh home: it execs the
   store Python, for which ``_require_own_dependencies`` refuses ("no
   dependency environment is committed for this install; run ``hermes pm
   repair``", reproduced under a fresh home, exit 1).  Hence the committed venv
   interpreter, not the shim, is the entry point here.

Upgrade safety
--------------
The venv-interpreter carve-out and the per-home install-state scoping are
internal behaviours, not shipped documentation.  They are therefore covered by
an explicit version gate (``TESTED_HERMES_VERSIONS``, read passively from the
install stamp) plus a live install-state snapshot test in
``tests/test_hermes_isolated_home.py`` that proves a real exercise writes
nothing to the active install directory.  On any other version the helper
refuses with a clear message instead of guessing.

Boundaries: import/CLI-help-level actions only.  No model, auth, provider or
network calls (the child blocks every ``socket.socket`` construction), no
writes to the live install state, no modification of installed source
(``-B`` keeps even ``__pycache__` untouched).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, NamedTuple

#: Installed Hermes display versions this helper has been exercised against.
#: ``hermes_isolated_home`` refuses to run on anything else.
TESTED_HERMES_VERSIONS = ("0.21.5+6751.g9cf7960",)

#: Environment variable documented in the installed Hermes env-var reference
#: (website/docs/reference/environment-variables.md, "Internal PM policy used
#: by tests and install probes").  It makes prepare_launch skip the lazy
#: dependency bootstrap.
DISABLE_LAZY_INSTALLS = "HERMES_DISABLE_LAZY_INSTALLS"

_CHILD_GUARD = """\
import socket as _socket_module
_REAL_SOCKET = _socket_module.socket
_INET = _socket_module.AF_INET
_INET6 = _socket_module.AF_INET6
class _NoNetworkSocket(_REAL_SOCKET):
    def __init__(self, family=_INET, *args, **kwargs):
        raise AssertionError(
            "isolated-home exercise attempted network (family=%r)" % (family,))
_socket_module.socket = _NoNetworkSocket
"""

_IMPORT_ACTION = """\
import sys
sys.path.insert(0, {root!r})
import hermes_bootstrap
import hermes_cli.main
print({marker!r})
"""

_HELP_ACTION = """\
import sys
sys.path.insert(0, {root!r})
import hermes_bootstrap
import hermes_cli.main
print({marker!r})
sys.argv = ["hermes", "--help"]
try:
    rc = hermes_cli.main.main()
except SystemExit as exc:
    rc = exc.code
print({done_marker!r}, rc)
sys.exit(0 if rc in (0, None) else rc)
"""


class IsolatedHomeError(RuntimeError):
    """The isolated Hermes home cannot be provided safely on this install."""


def default_dependency_root() -> Path:
    """The data root dependency state lives under, as the launchers resolve it.

    Mirrors ``hermes_constants.get_default_hermes_root``: the platform default
    (``~/.hermes``) unless ``HERMES_HOME`` names a root outside it, in which
    case a ``<root>/profiles/<name>`` path folds to ``<root>`` and any other
    path is its own root.  Read-only; creates nothing.
    """
    native = Path.home() / ".hermes"
    env_home = os.environ.get("HERMES_HOME", "").strip()
    if not env_home:
        return native
    env_path = Path(os.path.expandvars(os.path.expanduser(env_home)))
    try:
        env_path.resolve().relative_to(native.resolve())
        return native  # normal or profile mode under ~/.hermes
    except (ValueError, OSError):
        return env_path.parent.parent if env_path.parent.name == "profiles" else env_path


def _shim_checkout_root() -> Path | None:
    """The installed checkout the ``hermes`` shim on PATH execs, or None."""
    shim = shutil.which("hermes")
    if not shim:
        return None
    try:
        text = Path(shim).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(
        # POSIX sh launchers quote the path as '"'"'<path>'"'"'; Windows and
        # plain launchers use a single-quoted literal. Handle both.
        r"sys\.path\.insert\(0,\s*(?:'\"'\"')?([^'\"\n]+)'", text)
    if not match:
        return None
    root = Path(match.group(1))
    return root if (root / "install-stamp.json").is_file() else None


def installed_hermes_version(checkout_root: Path) -> str | None:
    """Display version from the install stamp (passive read, no process)."""
    try:
        stamp = json.loads((checkout_root / "install-stamp.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    version = stamp.get("displayVersion")
    return version if isinstance(version, str) and version else None


def _install_key(checkout_root: Path) -> str:
    canonical = str(Path(checkout_root).resolve())
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def resolve_committed_venv_python(checkout_root: Path, dependency_root: Path) -> Path | None:
    """The venv interpreter the install state records, or None.

    Passive reads only: ``<dependency_root>/installs/<key>/facts.json`` →
    ``packages.venv.environment`` (pm/environments.py runtime facts), then the
    interpreter inside that venv.
    """
    facts_path = dependency_root / "installs" / _install_key(checkout_root) / "facts.json"
    try:
        facts = json.loads(facts_path.read_text(encoding="utf-8-sig"))
        environment = facts["packages"]["venv"]["environment"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    python = Path(environment) / ("python.exe" if os.name == "nt" else "bin/python3")
    return python if python.is_file() else None


def version_gate(version: str | None) -> str | None:
    """None when *version* is explicitly TESTED, else a refusal reason."""
    if version is None:
        return ("cannot read the installed Hermes version from its install stamp; "
                f"tested versions: {', '.join(TESTED_HERMES_VERSIONS)}")
    if version not in TESTED_HERMES_VERSIONS:
        return (f"installed Hermes {version} is not in the TESTED list "
                f"({', '.join(TESTED_HERMES_VERSIONS)}); re-verify the bootstrap "
                "mechanism (prepare_launch skip conditions, activate_dependencies "
                "venv carve-out, per-home install-state scoping) and the live "
                "install-state snapshot before adding it")
    return None


class IsolatedHome(NamedTuple):
    home: Path
    env: dict[str, str]
    python: Path
    checkout_root: Path

    def child_command(self, script: Path) -> list[str]:
        return [str(self.python), "-I", "-B", str(script)]

    def write_child(self, action: str, marker: str, *, done_marker: str | None = None,
                    directory: Path | None = None) -> Path:
        """Write a single-file guarded child exercising installed Hermes."""
        body = _IMPORT_ACTION if action == "import" else _HELP_ACTION
        code = _CHILD_GUARD + body.format(
            root=str(self.checkout_root), marker=marker,
            done_marker=done_marker or (marker + ":DONE"))
        directory = directory or self.home
        directory.mkdir(parents=True, exist_ok=True)
        script = directory / f"exercise-{action}.py"
        script.write_text(code, encoding="utf-8")
        return script

    def run(self, script: Path, *, timeout: float = 180.0) -> subprocess.CompletedProcess:
        return subprocess.run(self.child_command(script), env=self.env,
                              capture_output=True, text=True, timeout=timeout,
                              check=False)


@contextmanager
def isolated_hermes_home(*, extra_env: dict[str, str] | None = None) -> Iterator[IsolatedHome]:
    """Yield an isolated HERMES_HOME plus the launch recipe for a probe child.

    Creates a fresh home under the test process's TMPDIR (never the worktree),
    a minimal environment for the child, and resolves the committed venv
    interpreter.  Refuses (IsolatedHomeError) when the installed Hermes is not
    in the TESTED list or its committed interpreter cannot be resolved
    passively.  Everything the child writes stays inside *home*.
    """
    checkout_root = _shim_checkout_root()
    if checkout_root is None:
        raise IsolatedHomeError(
            "no installed `hermes` shim on PATH with a readable install stamp; "
            "the isolated Hermes home helper only probes an existing install")
    reason = version_gate(installed_hermes_version(checkout_root))
    if reason is not None:
        raise IsolatedHomeError(reason)
    dependency_root = default_dependency_root()
    python = resolve_committed_venv_python(checkout_root, dependency_root)
    if python is None:
        raise IsolatedHomeError(
            f"no committed dependency venv recorded under {dependency_root}/installs/ "
            f"for the checkout {checkout_root}; refusing to guess an interpreter")
    home = Path(tempfile.mkdtemp(prefix="hermes-isolated-home-",
                                dir=tempfile.gettempdir()))
    (home / "tmp").mkdir()
    env = {"HOME": str(home), "HERMES_HOME": str(home), "TMPDIR": str(home / "tmp"),
           "PATH": "/usr/bin:/bin", DISABLE_LAZY_INSTALLS: "true"}
    if extra_env:
        env.update(extra_env)
    try:
        yield IsolatedHome(home=home, env=env, python=python, checkout_root=checkout_root)
    finally:
        shutil.rmtree(home, ignore_errors=True)


def exercise_import_and_help(*, timeout: float = 180.0) -> dict[str, object]:
    """The canonical bounded real exercise: import + CLI-help under a fresh home.

    Returns a receipt dict.  Raises IsolatedHomeError on any gate refusal and
    AssertionError when the exercise does not demonstrably pass without
    dependency installation (no dependency generation under the isolated home)
    or without touching the network.
    """
    with isolated_hermes_home() as iso:
        import_marker = "ISO_HERMES_IMPORT_OK"
        help_marker = "ISO_HERMES_HELP_OK"
        script = iso.write_child("help", import_marker, done_marker=help_marker)
        result = iso.run(script, timeout=timeout)
        receipt = {
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-2000:],
            "stderr_tail": result.stderr[-2000:],
            "home": str(iso.home),
            "python": str(iso.python),
            "checkout_root": str(iso.checkout_root),
        }
        key = _install_key(iso.checkout_root)
        receipt["isolated_dependency_generations"] = sorted(
            p.name for p in (iso.home / "installs" / key / "environments").glob("*")
        ) if (iso.home / "installs" / key / "environments").is_dir() else []
    if result.returncode != 0:
        raise AssertionError(f"isolated-home exercise failed (rc={result.returncode}):\n"
                             f"stdout: {result.stdout[-2000:]}\nstderr: {result.stderr[-2000:]}")
    if import_marker not in result.stdout:
        raise AssertionError("isolated-home exercise did not import installed Hermes")
    if help_marker not in result.stdout or "usage:" not in result.stdout:
        raise AssertionError("isolated-home exercise did not render CLI help")
    if result.stderr.strip():
        raise AssertionError(f"isolated-home exercise wrote stderr: {result.stderr[-2000:]}")
    if receipt["isolated_dependency_generations"]:
        raise AssertionError("dependency generation built under the isolated home: "
                             f"{receipt['isolated_dependency_generations']}")
    receipt["ok"] = True
    return receipt


if __name__ == "__main__":  # pragma: no cover - manual bounded probe
    print(json.dumps(exercise_import_and_help(), indent=2))
