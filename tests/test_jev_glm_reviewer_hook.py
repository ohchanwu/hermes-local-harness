"""Tests for the pre_tool_call shell hook guard for a GLM reviewer (card t_85d4fbda).

Standard library unittest only; run with python3 from the repository root:

    python3 tests/test_jev_glm_reviewer_hook.py
"""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "jev-glm-reviewer-hook"
OBSERVER = ROOT / "tests" / "observe_glm_reviewer_hook.py"
sys.path.insert(0, str(ROOT / "tests"))
from hermes_isolated_home import installed_hermes_python  # noqa: E402
HERMES_PYTHON = installed_hermes_python()

MESSAGE_START = "A GLM reviewer may not call kanban_complete or kanban_request_review."


class ScriptTests(unittest.TestCase):
    """The shell script itself: exit status 2, the message on stderr, no stdout."""

    def run_script(self, stdin_bytes):
        return subprocess.run([str(SCRIPT)], input=stdin_bytes, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=30)

    def test_file_is_executable_and_starts_with_posix_shell_shebang(self):
        self.assertTrue(SCRIPT.is_file(), f"missing script: {SCRIPT}")
        mode = SCRIPT.stat().st_mode
        self.assertTrue(mode & 0o111, f"script is not executable: {SCRIPT}")
        first = SCRIPT.read_bytes().split(b"\n", 1)[0]
        self.assertEqual(first, b"#!/bin/sh")

    def test_exits_2_with_message_on_stderr_and_no_stdout_with_json_stdin(self):
        result = self.run_script(b'{"hook_event_name": "pre_tool_call", "tool_name": "kanban_complete"}\n')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        stderr = result.stderr.decode("utf-8")
        self.assertIn(MESSAGE_START, stderr)

    def test_exits_2_with_message_on_stderr_and_no_stdout_with_empty_stdin(self):
        result = self.run_script(b"")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertIn(MESSAGE_START, result.stderr.decode("utf-8"))

    def test_exits_2_with_message_on_stderr_and_no_stdout_with_binary_stdin(self):
        result = self.run_script(b"\x00\xff not json \x00" * 100)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertIn(MESSAGE_START, result.stderr.decode("utf-8"))


class ObservationTests(unittest.TestCase):
    """The observation program against the installed Hermes in a temporary home."""

    def test_observation_program_exits_0_with_the_installed_hermes_venv(self):
        if HERMES_PYTHON is None:
            self.skipTest(
                "no interpreter of the installed Hermes is recorded in its per-install facts.json; "
                "the observation program needs the installed Hermes modules")
        result = subprocess.run([str(HERMES_PYTHON), "-I", str(OBSERVER)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=600, cwd=str(ROOT))
        self.assertEqual(result.returncode, 0,
                         f"observation program failed:\n{result.stdout[-4000:]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
