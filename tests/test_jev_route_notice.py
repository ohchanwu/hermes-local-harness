"""Offline tests for scripts/jev-route-notice (Part 8.6 of the GLM routing request).

Every log file, database and settings file is made under a temporary directory
with the fixture builder of tests/test_jev_report.py. Card ids, profiles, paths
and token numbers are synthetic. No test sends a message: run() receives a
sender that records the text, and the command-line runs only write to a pipe.
"""
import contextlib
import importlib.machinery
import io
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_jev_report as base  # noqa: E402  (fixture builder and constants)

NOTICE = ROOT / "scripts/jev-route-notice"
REPORT = ROOT / "scripts/jev-report"


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    module_spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(module_spec)
    loader.exec_module(module)
    return module


notice = load("jev_route_notice_under_test", NOTICE)


def board_settings(easy=True, medium=True, hard=True, glm_workers=("worker-glm-1",)):
    """One board entry in the format of plugins/jev/config.json."""
    return {"implementation_workers": ["worker"], "glm_workers": list(glm_workers),
            "routes": [
                {"name": "easy", "enabled": easy, "assignee_from": "glm_workers",
                 "model": "glm-5.3-flash", "provider": "zai", "criterion": "synthetic"},
                {"name": "medium", "enabled": medium, "assignee_from": "glm_workers",
                 "model": "glm-5.3", "provider": "zai", "criterion": "synthetic"},
                {"name": "hard", "enabled": hard, "criterion": "synthetic"}]}


def make_settings(tmp, boards=None, routing_enabled=True, raw=None):
    """A synthetic settings path: plugin config.json and routing-state.json.

    boards maps a board name to board_settings(...); default: harness, jobcron
    and anki with every route on. raw, when given, is written as the file
    content instead. Returns the path of config.json.
    """
    settings = os.path.join(tmp, "settings", "plugins", "jev")
    os.makedirs(settings)
    if boards is None:
        boards = {name: board_settings() for name in ("harness", "jobcron", "anki")}
    config = os.path.join(settings, "config.json")
    with open(config, "w", encoding="utf-8") as handle:
        if raw is not None:
            handle.write(raw)
        else:
            json.dump({"routing": {"enabled": routing_enabled, "threshold": 0.6,
                                   "control_group_every": 5, "boards": boards}}, handle)
    with open(os.path.join(tmp, "logs", "routing-state.json"), "w", encoding="utf-8") as handle:
        json.dump({"counters": {"harness": 3}, "control_group_counters": {"harness": {"easy": 4}}},
                  handle)
    return config


def rule_cards(glm_claude=1200, control_claude=1000, glm_count=10, control_count=3):
    return (base.specs("g", glm_count, "harness", "easy", "glm", 0, 0, glm_claude)
            + base.specs("c", control_count, "jobcron", "easy", "control", 0, 0, control_claude))


class Recorder:
    def __init__(self):
        self.texts = []

    def __call__(self, text):
        self.texts.append(text)


def notice_args(fixture, config):
    return ["--config", config, "--log-dir", fixture.logs, "--since", "100000", "--kanban-db", fixture.kanban_db,
            "--state-db", fixture.worker_db, "--state-db", fixture.reviewer_db]


class NoticeTests(unittest.TestCase):
    def run_notice(self, cards, extra_args=(), **settings):
        """(exit status, sent texts, standard error) of one in-process run."""
        with tempfile.TemporaryDirectory() as tmp:
            fixture = base.SavingsFixture(tmp, cards)
            config = make_settings(tmp, **settings)
            before = base.tree_state(tmp)
            recorder = Recorder()
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                status = notice.run(notice_args(fixture, config) + list(extra_args),
                                    sender=recorder, now=base.NOW)
            self.assertEqual(base.tree_state(tmp), before, "a file under the temporary tree changed")
            return status, recorder.texts, errors.getvalue()

    def test_rule_line_gives_exactly_one_message_and_changes_no_file(self):
        status, texts, _errors = self.run_notice(rule_cards())
        self.assertEqual(status, 0)
        self.assertEqual(len(texts), 1)
        text = texts[0]
        self.assertIn("route easy", text)
        self.assertIn("saved -2000 Claude tokens", text)
        self.assertIn("mean Claude tokens per control card 1000 (3 control cards)", text)
        self.assertIn("mean Claude tokens per GLM-routed card 1200 (10 GLM-routed cards)", text)
        self.assertIn('"disable this route: owner permission required"', text)
        self.assertIn("Do you give permission to turn off route easy?", text)
        self.assertIn("The route stays on until you answer. Nothing has been changed.", text)
        self.assertNotIn(base.SENTINEL, text)
        self.assertNotIn("medium", text)

    def test_two_routes_with_a_rule_line_give_one_message(self):
        cards = rule_cards() + (
            base.specs("m", 10, "anki", "medium", "glm", 0, 0, 3000)
            + base.specs("n", 3, "anki", "medium", "control", 0, 0, 2500))
        status, texts, _errors = self.run_notice(cards)
        self.assertEqual(status, 0)
        self.assertEqual(len(texts), 1)
        self.assertIn("routes easy, medium, over all boards", texts[0])
        self.assertIn("- route medium: saved -5000 Claude tokens", texts[0])
        self.assertIn("The routes stay on until you answer.", texts[0])

    def test_no_rule_line_sends_nothing(self):
        for cards in (rule_cards(glm_claude=900),        # saved is positive
                      rule_cards(glm_count=9),           # below the GLM-routed minimum
                      rule_cards(control_count=2),       # below the control minimum
                      []):                               # no card at all
            status, texts, _errors = self.run_notice(cards)
            self.assertEqual(status, 0)
            self.assertEqual(texts, [])

    def test_after_option_is_passed_to_the_report(self):
        status, texts, _errors = self.run_notice(rule_cards(), ["--after", "2099-01-01T00:00:00+09:00"])
        self.assertEqual(status, 0)
        self.assertEqual(texts, [])
        status, texts, _errors = self.run_notice(rule_cards(), ["--after", "2020-01-01T00:00:00+09:00"])
        self.assertEqual(len(texts), 1)
        self.assertIn("records after 2019-12-31T15:00:00+00:00", texts[0])

    def test_message_matches_the_report_rule_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = base.SavingsFixture(tmp, rule_cards())
            text = fixture.text()
            self.assertIn("  route easy: " + base.report.RULE_TEXT + "\n", text)
            self.assertEqual(notice.RULE_TEXT, base.report.RULE_TEXT)


def every_board(**route_settings):
    return {name: board_settings(**route_settings) for name in ("harness", "jobcron", "anki")}


def two_rule_routes():
    """rule_cards() for route easy plus a rule line for route medium on board anki."""
    return rule_cards() + (base.specs("m", 10, "anki", "medium", "glm", 0, 0, 3000)
                           + base.specs("n", 3, "anki", "medium", "control", 0, 0, 2500))


class RouteSettingTests(unittest.TestCase):
    """A route with a rule line that is off on every board gets no message."""

    run_notice = NoticeTests.run_notice

    def test_route_off_on_every_board_sends_nothing(self):
        status, texts, errors = self.run_notice(rule_cards(), boards=every_board(easy=False))
        self.assertEqual(status, 0)
        self.assertEqual(texts, [])
        self.assertIn("jev-route-notice: route easy has a rule line and is off on every board in ",
                      errors)
        self.assertEqual(errors.count("\n"), 1)

    def test_route_off_on_some_boards_only_gives_one_message(self):
        boards = every_board(easy=False)
        boards["anki"] = board_settings()
        status, texts, errors = self.run_notice(rule_cards(), boards=boards)
        self.assertEqual(status, 0)
        self.assertEqual(len(texts), 1)
        self.assertIn("Do you give permission to turn off route easy?", texts[0])
        self.assertEqual(errors, "")

    def test_two_routes_with_one_off_name_only_the_route_that_is_on(self):
        status, texts, errors = self.run_notice(two_rule_routes(), boards=every_board(easy=False))
        self.assertEqual(status, 0)
        self.assertEqual(len(texts), 1)
        text = texts[0]
        self.assertIn("for route medium, over all boards:", text)
        self.assertIn("- route medium: saved -5000 Claude tokens", text)
        self.assertNotIn("easy", text)
        self.assertIn("Do you give permission to turn off route medium?", text)
        self.assertIn("The route stays on until you answer.", text)
        self.assertIn("route easy has a rule line and is off on every board", errors)

    def test_unreadable_settings_file_gives_the_message(self):
        for settings, error_class in (({"raw": "{not json"}, "JSONDecodeError"),
                                      ({"raw": "[1, 2]"}, "UnexpectedStructure"),
                                      ({"raw": '{"routing": {"boards": []}}'}, "UnexpectedStructure")):
            status, texts, errors = self.run_notice(rule_cards(), **settings)
            self.assertEqual(status, 0)
            self.assertEqual(len(texts), 1, settings)
            self.assertIn(f": {error_class}; every route counts as on\n", errors)
        with tempfile.TemporaryDirectory() as tmp:
            fixture = base.SavingsFixture(tmp, rule_cards())
            recorder, errors = Recorder(), io.StringIO()
            absent = os.path.join(tmp, "absent", "config.json")
            with contextlib.redirect_stderr(errors):
                status = notice.run(notice_args(fixture, absent), sender=recorder, now=base.NOW)
            self.assertEqual(status, 0)
            self.assertEqual(len(recorder.texts), 1)
            self.assertIn(": FileNotFoundError; every route counts as on\n", errors.getvalue())

    def test_settings_file_with_invalid_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = base.SavingsFixture(tmp, rule_cards())
            config = make_settings(tmp)
            with open(config, "wb") as handle:
                handle.write(b'{"routing": "\xff"}')
            recorder, errors = Recorder(), io.StringIO()
            with contextlib.redirect_stderr(errors):
                status = notice.run(notice_args(fixture, config), sender=recorder, now=base.NOW)
            self.assertEqual(status, 0)
            self.assertEqual(len(recorder.texts), 1)
            self.assertIn(": UnicodeDecodeError; every route counts as on\n", errors.getvalue())

    def test_no_rule_line_does_not_need_the_settings_file(self):
        status, texts, errors = self.run_notice(rule_cards(glm_claude=900), raw="{not json")
        self.assertEqual((status, texts, errors), (0, [], ""))

    def test_route_is_on_follows_the_plugin_conditions(self):
        def config(boards, enabled=True):
            return {"routing": {"enabled": enabled, "boards": boards}}

        self.assertTrue(notice.route_is_on(config(every_board()), "easy"))
        self.assertFalse(notice.route_is_on(config(every_board(), enabled=False), "easy"))
        self.assertFalse(notice.route_is_on({"routing": {"boards": every_board()}}, "easy"))
        self.assertFalse(notice.route_is_on(config(every_board(easy=False)), "easy"))
        self.assertTrue(notice.route_is_on(config(every_board(easy=False)), "medium"))
        # Only one enabled route left on a board: the plugin asks no route question there.
        self.assertFalse(notice.route_is_on(config(every_board(medium=False, hard=False)), "easy"))
        self.assertFalse(notice.route_is_on(config(every_board(glm_workers=())), "easy"))
        absent = {"harness": {"glm_workers": ["worker-glm-1"], "routes": [
            {"name": "medium", "enabled": True, "assignee_from": "glm_workers"},
            {"name": "hard", "enabled": True}]}}
        self.assertFalse(notice.route_is_on(config(absent), "easy"))
        self.assertFalse(notice.route_is_on(config({}), "easy"))
        mixed = every_board(easy=False)
        mixed["anki"] = board_settings()
        self.assertTrue(notice.route_is_on(config(mixed), "easy"))


def fixture_config(fixture):
    """The settings file of a fixture, made with every route on at the first call."""
    if not hasattr(fixture, "config"):
        fixture.config = make_settings(fixture.tmp)
    return fixture.config


class CommandLineTests(unittest.TestCase):
    def command(self, fixture, *extra):
        env = dict(os.environ)
        env.pop("HERMES_JEV_LOG_DIR", None)
        args = notice_args(fixture, fixture_config(fixture))
        return subprocess.run([sys.executable, str(NOTICE)] + args + list(extra),
                              capture_output=True, text=True, encoding="utf-8", env=env,
                              check=False)

    def test_rule_line_prints_the_message_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = base.SavingsFixture(tmp, rule_cards())
            fixture_config(fixture)
            before = base.tree_state(tmp)
            proc = self.command(fixture)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stderr, "")
            self.assertEqual(proc.stdout.count("jev routing: owner permission requested"), 1)
            self.assertTrue(proc.stdout.endswith("Nothing has been changed.\n"))
            self.assertNotIn(base.SENTINEL, proc.stdout)
            self.assertEqual(base.tree_state(tmp), before)

    def test_no_rule_line_prints_nothing(self):
        # Empty standard output is what makes a `--no-agent` scheduled job a silent run.
        with tempfile.TemporaryDirectory() as tmp:
            fixture = base.SavingsFixture(tmp, rule_cards(glm_claude=900))
            proc = self.command(fixture)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, "")
            self.assertEqual(proc.stderr, "")

    def test_report_script_option_and_symbolic_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = base.SavingsFixture(tmp, rule_cards())
            proc = self.command(fixture, "--report-script", str(REPORT))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.count("jev routing: owner permission requested"), 1)
            link_dir = os.path.join(tmp, "bin")
            os.makedirs(link_dir)
            os.symlink(str(NOTICE), os.path.join(link_dir, "jev-route-notice"))
            proc = subprocess.run(
                [sys.executable, os.path.join(link_dir, "jev-route-notice")]
                + notice_args(fixture, fixture_config(fixture)),
                capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.count("jev routing: owner permission requested"), 1)

    def test_default_settings_file_and_no_bytecode_file(self):
        # A copy of the two scripts in a synthetic checkout: the default --config is
        # plugins/jev/config.json of that checkout, and no run writes a file (no __pycache__).
        with tempfile.TemporaryDirectory() as tmp:
            fixture = base.SavingsFixture(tmp, rule_cards())
            checkout = os.path.join(tmp, "checkout")
            os.makedirs(os.path.join(checkout, "scripts"))
            os.makedirs(os.path.join(checkout, "plugins", "jev"))
            for script in (NOTICE, REPORT):
                shutil.copy(str(script), os.path.join(checkout, "scripts", script.name))
            config = os.path.join(checkout, "plugins", "jev", "config.json")
            args = [sys.executable, os.path.join(checkout, "scripts", "jev-route-notice"),
                    "--log-dir", fixture.logs, "--since", "100000", "--kanban-db", fixture.kanban_db,
                    "--state-db", fixture.worker_db, "--state-db", fixture.reviewer_db]
            for easy, expected in ((True, 1), (False, 0)):
                with open(config, "w", encoding="utf-8") as handle:
                    json.dump({"routing": {"enabled": True, "boards": every_board(easy=easy)}},
                              handle)
                before = base.tree_state(tmp)
                proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                                      check=False)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(proc.stdout.count("jev routing: owner permission requested"),
                                 expected)
                self.assertEqual(base.tree_state(tmp), before, "a file under the temporary tree changed")
                self.assertFalse(os.path.exists(os.path.join(checkout, "scripts", "__pycache__")))
            self.assertIn("route easy has a rule line and is off on every board in "
                          + os.path.realpath(config),
                          proc.stderr)

    def test_failure_exits_nonzero_without_a_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = base.SavingsFixture(tmp, rule_cards())
            proc = self.command(fixture, "--report-script", os.path.join(tmp, "absent"))
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(proc.stdout, "")
            self.assertIn("cannot load", proc.stderr)
            broken = os.path.join(tmp, "broken-report")
            shutil.copy(str(REPORT), broken)
            with open(broken, "a", encoding="utf-8") as handle:
                handle.write("\n\ndef route_savings(*args, **kwargs):\n"
                             "    raise RuntimeError('synthetic failure')\n")
            proc = self.command(fixture, "--report-script", broken)
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(proc.stdout, "")
            self.assertEqual(proc.stderr, "jev-route-notice: report calculation failed: RuntimeError\n")

    def test_argument_error_and_help(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = base.SavingsFixture(tmp, rule_cards())
            proc = self.command(fixture, "--after", "not a time")
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stdout, "")
        proc = subprocess.run([sys.executable, str(NOTICE), "--help"], capture_output=True,
                              text=True, encoding="utf-8", check=False)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--after DATETIME", proc.stdout)
        self.assertIn("--report-script PATH", proc.stdout)


if __name__ == "__main__":
    unittest.main()
