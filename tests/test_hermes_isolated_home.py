"""Tests for tests/hermes_isolated_home.py — offline contract + real exercise.

Layout:
- Mechanism/contract tests (no Hermes launch): version gate, passive venv
  resolution, child guard blocks network, tmp placement, TESTED-list refusal.
- One real bounded exercise (only when an installed Hermes with a readable
  install stamp is present and in the TESTED list): the helper runs an
  import + CLI-help child under a fresh isolated home, and the LIVE install
  state directory's snapshot (file list, sizes, mtimes) is byte-identical
  before and after — the mandatory proof that no live install state was
  written by the exercise.

No network, no model/auth/provider calls, no writes to the live home.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hermes_isolated_home as hih  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class VersionGateTests(unittest.TestCase):
    def test_tested_version_passes(self):
        self.assertIsNone(hih.version_gate("0.21.5+6751.g9cf7960"))

    def test_untested_version_refuses_with_clear_message(self):
        reason = hih.version_gate("9.9.9")
        assert reason is not None
        self.assertIn("9.9.9", reason)
        self.assertIn("TESTED", reason)
        self.assertIn("0.21.5+6751.g9cf7960", reason)

    def test_missing_version_refuses(self):
        reason = hih.version_gate(None)
        assert reason is not None
        self.assertIn("install stamp", reason)


class PassiveResolutionTests(unittest.TestCase):
    def test_default_dependency_root_profiles_path_folds_to_root(self):
        with patch.dict(os.environ, {"HERMES_HOME": "/tmp/altroot/profiles/worker"}):
            self.assertEqual(hih.default_dependency_root(), Path("/tmp/altroot"))

    def test_default_dependency_root_outside_home_is_itself(self):
        with patch.dict(os.environ, {"HERMES_HOME": "/tmp/altroot2"}):
            self.assertEqual(hih.default_dependency_root(), Path("/tmp/altroot2"))

    def test_default_dependency_root_unset_uses_platform_default(self):
        env = {k: v for k, v in os.environ.items() if k != "HERMES_HOME"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(hih.default_dependency_root(), Path.home() / ".hermes")

    def test_committed_venv_python_resolved_passively(self):
        # Uses the real machine state (passive reads only) — the exact path
        # the real exercise will use.
        checkout = hih._shim_checkout_root()
        if checkout is None:
            self.skipTest("no installed hermes shim with install stamp on PATH")
        python = hih.resolve_committed_venv_python(checkout, hih.default_dependency_root())
        assert python is not None, "expected a committed venv for the installed checkout"
        self.assertTrue(python.is_file())
        self.assertIn("environments", str(python))

    def test_committed_venv_python_none_on_missing_state(self):
        self.assertIsNone(hih.resolve_committed_venv_python(
            Path("/nonexistent/checkout"), Path("/nonexistent/root")))


class ChildGuardTests(unittest.TestCase):
    def test_child_guard_blocks_network_socket(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "probe.py"
            script.write_text(
                hih._CHILD_GUARD + "\nimport socket\nsocket.socket()\n",
                encoding="utf-8")
            result = subprocess.run([sys.executable, "-I", "-B", str(script)],
                                    capture_output=True, text=True, timeout=60, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("attempted network", result.stderr)


class RefusalTests(unittest.TestCase):
    def test_isolated_home_refuses_untested_version(self):
        with patch.object(hih, "_shim_checkout_root", return_value=ROOT), \
                patch.object(hih, "installed_hermes_version", return_value="1.2.3"):
            with self.assertRaises(hih.IsolatedHomeError) as ctx:
                with hih.isolated_hermes_home():
                    pass
            self.assertIn("not in the TESTED list", str(ctx.exception))

    def test_isolated_home_refuses_when_venv_unresolvable(self):
        with patch.object(hih, "_shim_checkout_root", return_value=ROOT), \
                patch.object(hih, "installed_hermes_version", return_value=None), \
                patch.object(hih, "resolve_committed_venv_python", return_value=None):
            with self.assertRaises(hih.IsolatedHomeError):
                with hih.isolated_hermes_home():
                    pass


class IsolatedHomeContractTests(unittest.TestCase):
    def test_isolated_home_env_shape(self):
        with patch.object(hih, "_shim_checkout_root", return_value=ROOT), \
                patch.object(hih, "installed_hermes_version", return_value=hih.TESTED_HERMES_VERSIONS[0]), \
                patch.object(hih, "resolve_committed_venv_python", return_value=Path("/synthetic/python3")):
            with hih.isolated_hermes_home() as iso:
                self.assertEqual(iso.env["HERMES_HOME"], str(iso.home))
                self.assertEqual(iso.env["HOME"], str(iso.home))
                self.assertTrue(iso.env["TMPDIR"].startswith(str(iso.home)))
                self.assertEqual(iso.env[hih.DISABLE_LAZY_INSTALLS], "true")
                self.assertNotIn("HERMES_PROFILE", iso.env)
                self.assertNotIn("HERMES_KANBAN_TASK", iso.env)
                self.assertNotIn("PYTEST_CURRENT_TEST", iso.env)
                # The isolated home lives under the process TMPDIR, never the worktree.
                self.assertNotIn(str(ROOT), str(iso.home))
                self.assertNotIn("/worktrees/", str(iso.home))
                # The child command runs the committed venv interpreter isolated, no bytecode.
                self.assertEqual(iso.child_command(Path("/x/y.py")),
                                 ["/synthetic/python3", "-I", "-B", "/x/y.py"])
                self.assertTrue(iso.home.exists())


class RealExerciseTests(unittest.TestCase):
    """The mandatory real exercise — skipped only without a TESTED install."""

    def test_import_and_help_without_bootstrap_and_live_state_unchanged(self):
        checkout = hih._shim_checkout_root()
        if checkout is None:
            self.skipTest("no installed hermes shim with install stamp on PATH")
        if hih.version_gate(hih.installed_hermes_version(checkout)) is not None:
            self.skipTest("installed Hermes is not in the TESTED list")
        state_dir = hih.default_dependency_root() / "installs" / hih._install_key(checkout)

        def snapshot() -> dict[str, tuple[int, int, int]]:
            snap: dict[str, tuple[int, int, int]] = {}
            for path in sorted(state_dir.rglob("*")):
                if ".leases" in path.relative_to(state_dir).parts or path.name == ".leases":
                    continue  # leases churn with live processes by design
                if path.is_dir():
                    continue
                st = path.stat()
                snap[str(path.relative_to(state_dir))] = (st.st_size, int(st.st_mtime), st.st_ino)
            return snap

        before = snapshot()
        receipt = hih.exercise_import_and_help()
        after = snapshot()
        self.assertTrue(receipt["ok"])
        self.assertEqual(receipt["returncode"], 0)
        self.assertEqual(before, after,
                         "live install state changed during the isolated-home exercise")
        # The isolated home is gone after the context manager exits.
        self.assertFalse(Path(str(receipt["home"])).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
