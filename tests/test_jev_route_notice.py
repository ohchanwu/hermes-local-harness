"""Offline tests for scripts/jev-route-notice (Part 8.6 of the GLM routing request).

Every log file, database and settings file is made under a temporary directory
with the fixture builder of tests/test_jev_report.py. Card ids, profiles, paths
and token numbers are synthetic. No test sends a message: run() receives a
sender that records the text, and the command-line runs only write to a pipe.
"""
import importlib.machinery
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


def make_settings(tmp):
    """A synthetic settings path: plugin config.json and routing-state.json."""
    settings = os.path.join(tmp, "settings", "plugins", "jev")
    os.makedirs(settings)
    with open(os.path.join(settings, "config.json"), "w", encoding="utf-8") as handle:
        json.dump({"routing": {"threshold": 0.6, "control_group_every": 5, "boards": {
            "harness": {"routes": {"easy": {"enabled": True}, "medium": {"enabled": True}}}}}},
            handle)
    with open(os.path.join(tmp, "logs", "routing-state.json"), "w", encoding="utf-8") as handle:
        json.dump({"counters": {"harness": 3}, "control_group_counters": {"harness": {"easy": 4}}},
                  handle)
    return settings


def rule_cards(glm_claude=1200, control_claude=1000, glm_count=10, control_count=3):
    return (base.specs("g", glm_count, "harness", "easy", "glm", 0, 0, glm_claude)
            + base.specs("c", control_count, "jobcron", "easy", "control", 0, 0, control_claude))


class Recorder:
    def __init__(self):
        self.texts = []

    def __call__(self, text):
        self.texts.append(text)


def notice_args(fixture):
    return ["--log-dir", fixture.logs, "--since", "100000", "--kanban-db", fixture.kanban_db,
            "--state-db", fixture.worker_db, "--state-db", fixture.reviewer_db]


class NoticeTests(unittest.TestCase):
    def run_notice(self, cards, extra_args=()):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = base.SavingsFixture(tmp, cards)
            make_settings(tmp)
            before = base.tree_state(tmp)
            recorder = Recorder()
            status = notice.run(notice_args(fixture) + list(extra_args), sender=recorder,
                                now=base.NOW)
            self.assertEqual(base.tree_state(tmp), before, "a file under the temporary tree changed")
            return status, recorder.texts

    def test_rule_line_gives_exactly_one_message_and_changes_no_file(self):
        status, texts = self.run_notice(rule_cards())
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
        status, texts = self.run_notice(cards)
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
            status, texts = self.run_notice(cards)
            self.assertEqual(status, 0)
            self.assertEqual(texts, [])

    def test_after_option_is_passed_to_the_report(self):
        status, texts = self.run_notice(rule_cards(), ["--after", "2099-01-01T00:00:00+09:00"])
        self.assertEqual(status, 0)
        self.assertEqual(texts, [])
        status, texts = self.run_notice(rule_cards(), ["--after", "2020-01-01T00:00:00+09:00"])
        self.assertEqual(len(texts), 1)
        self.assertIn("records after 2019-12-31T15:00:00+00:00", texts[0])

    def test_message_matches_the_report_rule_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = base.SavingsFixture(tmp, rule_cards())
            text = fixture.text()
            self.assertIn("  route easy: " + base.report.RULE_TEXT + "\n", text)
            self.assertEqual(notice.RULE_TEXT, base.report.RULE_TEXT)


class CommandLineTests(unittest.TestCase):
    def command(self, fixture, *extra):
        env = dict(os.environ)
        env.pop("HERMES_JEV_LOG_DIR", None)
        return subprocess.run([sys.executable, str(NOTICE)] + notice_args(fixture) + list(extra),
                              capture_output=True, text=True, encoding="utf-8", env=env,
                              check=False)

    def test_rule_line_prints_the_message_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = base.SavingsFixture(tmp, rule_cards())
            make_settings(tmp)
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
                [sys.executable, os.path.join(link_dir, "jev-route-notice")] + notice_args(fixture),
                capture_output=True, text=True, encoding="utf-8", check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.count("jev routing: owner permission requested"), 1)

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
