"""Tests for plugins/jev/reasoning_effort.py and the kanban_create notice (card t_caf5dba0).

Standard library only. The `hermes` command is replaced by a test double
(`shutil.which` and `subprocess.run` of the module are patched); no test reads
a board, starts Hermes or writes outside a temporary directory.

    python3 tests/test_jev_reasoning_effort.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "jev"))

import reasoning_effort as re_mod  # noqa: E402
import routing  # noqa: E402

CONFIG = json.loads((ROOT / "plugins" / "jev" / "config.json").read_text(encoding="utf-8"))
FAKE_HERMES = "/synthetic/bin/hermes"
LEVELS = ("low", "medium", "high", "xhigh", "max")


def glm_request(thinking="enabled"):
    request = {"model": "glm-5.3", "messages": [{"role": "user", "content": "synthetic"}],
               "reasoning_effort": "medium"}
    if thinking is not None:
        request["extra_body"] = {"thinking": {"type": thinking}}
    return request


def claude_request():
    return {"model": "claude-opus-5-5", "messages": [], "extra_body": {"subscription_session_id": "s-1"}}


class FakeHermes:
    """Test double of `subprocess.run` for `hermes kanban --board <b> show <t> --json`."""

    def __init__(self, body="Reasoning effort EXACT high.\n", returncode=0, stdout=None, raises=None):
        self.calls = []
        self.body, self.returncode, self.stdout, self.raises = body, returncode, stdout, raises

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if self.raises is not None:
            raise self.raises
        stdout = self.stdout if self.stdout is not None else json.dumps({"task": {"id": argv[5], "body": self.body}})
        return subprocess.CompletedProcess(argv, self.returncode, stdout=stdout, stderr="")


class MiddlewareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log_dir = Path(self.tmp.name) / "logs"
        env = {"HERMES_KANBAN_TASK": "t_0a1b2c3d", "HERMES_KANBAN_BOARD": "harness",
               "HERMES_PROFILE": "harness-worker", "HERMES_JEV_LOG_DIR": str(self.log_dir)}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        re_mod._card_levels.clear()
        re_mod._logged.clear()
        self.config = json.loads(json.dumps(CONFIG))

    def call(self, fake, provider="zai", model="glm-5.3", request=None, which=FAKE_HERMES, config=None):
        request = request if request is not None else (glm_request() if provider == "zai" else claude_request())
        with mock.patch.object(re_mod.shutil, "which", return_value=which), \
                mock.patch.object(re_mod.subprocess, "run", fake):
            return re_mod.llm_request(config=config or self.config, request=request,
                                      original_request=dict(request), provider=provider, model=model,
                                      task_id="session-task", api_call_count=1)

    def records(self):
        path = self.log_dir / "reasoning_effort.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def reset(self):
        re_mod._card_levels.clear()
        re_mod._logged.clear()

    # --- applied --------------------------------------------------------------

    def test_each_level_for_glm_and_claude(self):
        glm_expected = {"low": "low", "medium": "medium", "high": "high", "xhigh": "max", "max": "max"}
        for level in LEVELS:
            self.reset()
            fake = FakeHermes(body=f"Repository x.\nReasoning effort EXACT {level}.\nMore text.")
            result = self.call(fake)
            self.assertEqual(result["request"]["reasoning_effort"], glm_expected[level], level)
            self.assertEqual(result["request"]["extra_body"], {"thinking": {"type": "enabled"}})
            self.assertEqual((result["source"], result["reason"]), ("jev", "card reasoning effort"))
            self.reset()
            result = self.call(FakeHermes(body=f"Reasoning effort EXACT {level}."), provider="claude-subscription",
                               model="claude-opus-5-5")
            self.assertEqual(result["request"]["extra_body"],
                             {"subscription_session_id": "s-1", "card_reasoning_effort": level}, level)
            self.assertNotIn("reasoning_effort", result["request"])

    def test_xhigh_maps_to_max_for_glm(self):
        result = self.call(FakeHermes(body="Reasoning effort EXACT xhigh."))
        self.assertEqual(result["request"]["reasoning_effort"], "max")

    def test_glm_5_2_and_flash_models(self):
        result = self.call(FakeHermes(body="Reasoning effort EXACT low."), model="glm-5.2")
        self.assertEqual(result["request"]["reasoning_effort"], "high")
        self.reset()
        result = self.call(FakeHermes(body="Reasoning effort EXACT low."), model="glm-5.3-flash")
        self.assertEqual(result["request"]["reasoning_effort"], "low")

    def test_glm_request_without_extra_body(self):
        result = self.call(FakeHermes(), request=glm_request(thinking=None))
        self.assertEqual(result["request"]["reasoning_effort"], "high")
        self.assertNotIn("extra_body", result["request"])

    def test_command_line_and_one_read_per_process(self):
        fake = FakeHermes()
        for _ in range(3):
            self.assertIsNotNone(self.call(fake))
        self.assertEqual(len(fake.calls), 1)
        argv, kwargs = fake.calls[0]
        self.assertEqual(argv, [FAKE_HERMES, "kanban", "--board", "harness", "show", "t_0a1b2c3d", "--json"])
        self.assertEqual(kwargs["timeout"], 15)
        self.assertFalse(kwargs.get("shell", False))
        applied = [r for r in self.records() if r["event"] == "applied"]
        self.assertEqual(len(applied), 1)
        self.assertEqual({k: applied[0][k] for k in ("task_id", "profile", "provider", "level", "board")},
                         {"task_id": "t_0a1b2c3d", "profile": "harness-worker", "provider": "zai",
                          "level": "high", "board": "harness"})

    def test_no_level_is_cached_too(self):
        fake = FakeHermes(body="Repository x.\nNo effort line.")
        self.assertIsNone(self.call(fake))
        self.assertIsNone(self.call(fake))
        self.assertEqual(len(fake.calls), 1)

    def test_other_worker_lists_apply(self):
        for profile in ("harness-worker-glm-medium-1", "harness-worker-glm-hard-2", "harness-worker-2"):
            self.reset()
            with mock.patch.dict(os.environ, {"HERMES_PROFILE": profile}):
                self.assertIsNotNone(self.call(FakeHermes()), profile)

    # --- no change ------------------------------------------------------------

    def test_line_absent(self):
        self.assertIsNone(self.call(FakeHermes(body="Repository x.\nAssigned worker EXACT harness-worker.")))
        self.assertIsNone(self.call(FakeHermes(body=None)))

    def test_two_lines_and_invalid_level_and_bad_format(self):
        for body in ("Reasoning effort EXACT high.\nReasoning effort EXACT low.",
                     "Reasoning effort EXACT ultra.",
                     "Reasoning effort EXACT high",
                     "Reasoning effort: high."):
            self.reset()
            self.assertIsNone(self.call(FakeHermes(body=body)), body)

    def test_enabled_false(self):
        self.config["reasoning_effort"]["enabled"] = False
        fake = FakeHermes()
        self.assertIsNone(self.call(fake))
        self.assertEqual(fake.calls, [])
        del self.config["reasoning_effort"]
        self.assertIsNone(self.call(fake))
        self.assertEqual(fake.calls, [])

    def test_profile_not_a_worker(self):
        for profile in ("harness-reviewer", "harness-reviewer-glm", "harness-orchestrator", "jobcron-worker"):
            with mock.patch.dict(os.environ, {"HERMES_PROFILE": profile}):
                fake = FakeHermes()
                self.assertIsNone(self.call(fake), profile)
                self.assertEqual(fake.calls, [])

    def test_variables_missing(self):
        for name in ("HERMES_KANBAN_TASK", "HERMES_KANBAN_BOARD"):
            with mock.patch.dict(os.environ, {name: ""}):
                fake = FakeHermes()
                self.assertIsNone(self.call(fake))
                self.assertEqual(fake.calls, [])

    def test_unknown_provider_and_model(self):
        fake = FakeHermes()
        self.assertIsNone(self.call(fake, provider="openrouter", model="glm-5.3"))
        self.assertIsNone(self.call(fake, provider="anthropic", model="claude-opus-5-5"))
        self.assertIsNone(self.call(fake, provider="zai", model="glm-4.6"))

    def test_thinking_disabled(self):
        self.assertIsNone(self.call(FakeHermes(), request=glm_request(thinking="disabled")))

    def test_failures_leave_the_request_unchanged_and_log_once(self):
        cases = (("command_not_found", FakeHermes(), None),
                 ("timeout", FakeHermes(raises=subprocess.TimeoutExpired(["hermes"], 15)), FAKE_HERMES),
                 ("nonzero_exit", FakeHermes(returncode=1), FAKE_HERMES),
                 ("json_error", FakeHermes(stdout="not json"), FAKE_HERMES),
                 ("missing_field", FakeHermes(stdout=json.dumps({"task": {"id": "t_0a1b2c3d"}})), FAKE_HERMES))
        for error_class, fake, which in cases:
            self.reset()
            before = len(self.records())
            self.assertIsNone(self.call(fake, which=which), error_class)
            self.assertIsNone(self.call(fake, which=which), error_class)
            self.assertLessEqual(len(fake.calls), 1, error_class)
            new = self.records()[before:]
            self.assertEqual(len(new), 1, error_class)
            self.assertEqual((new[0]["event"], new[0]["error_class"]), ("card_read_failed", error_class))
            self.assertNotIn("Reasoning effort", json.dumps(new[0]))

    def test_unexpected_request_shape(self):
        self.assertIsNone(self.call(FakeHermes(), request={"model": "glm-5.3", "extra_body": "text"}))
        self.assertIsNone(self.call(FakeHermes(), request={"model": "glm-5.3", "extra_body": ["x"]}))
        failed = [r for r in self.records() if r["event"] == "failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["error_class"], "UnexpectedRequestShape")

    def test_plugin_registers_the_llm_request_middleware(self):
        sys.path.insert(0, str(ROOT / "plugins"))
        import jev  # noqa: E402

        class Context:
            def __init__(self):
                self.middleware, self.hooks = [], []

            def register_middleware(self, kind, callback):
                self.middleware.append(kind)

            def register_hook(self, name, callback):
                self.hooks.append(name)

        ctx = Context()
        jev.register(ctx)
        self.assertEqual(ctx.middleware, ["tool_execution", "llm_request"])


class CreateNoticeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = {"HERMES_JEV_LOG_DIR": str(Path(self.tmp.name) / "logs"), "HERMES_KANBAN_BOARD": "",
               "HERMES_KANBAN_TASK": ""}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.config = {"routing": {"enabled": False}, "reasoning_effort": CONFIG["reasoning_effort"]}

    def create(self, body):
        calls = []

        def next_call(new_args=None):
            calls.append(new_args)
            return json.dumps({"task_id": "t_0a1b2c3d", "status": "running"})

        def ask(*_args, **_kwargs):
            raise AssertionError("routing is off; Jev must not be asked")

        args = {"title": "Synthetic", "body": body, "assignee": "harness-worker", "board": "harness"}
        result = routing.handle_create(args, next_call, config=self.config, ask=ask)
        self.assertEqual(calls, [None], "the card must be created with the arguments unchanged")
        return json.loads(result)

    def test_valid_line_or_no_line_gives_no_notice(self):
        for body in ("Repository x.\nReasoning effort EXACT max.\n", "Repository x.\n", None):
            self.assertNotIn("jev_note", self.create(body), body)

    def test_unusable_lines_give_a_notice(self):
        for body, text in (("Reasoning effort EXACT high.\nReasoning effort EXACT low.", "2 lines start with"),
                           ("Reasoning effort EXACT ultra.", "the level 'ultra' is not one of"),
                           ("Reasoning effort is high.", "does not have the form")):
            result = self.create(body)
            self.assertEqual(result["task_id"], "t_0a1b2c3d")
            self.assertIn(text, result["jev_note"], body)
            self.assertIn("created unchanged", result["jev_note"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
