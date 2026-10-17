"""Offline tests for scripts/switch-profile-model; a fake hermes records its arguments."""
import importlib.machinery
import importlib.util
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("switch_profile_model", str(ROOT / "scripts/switch-profile-model"))
spec = importlib.util.spec_from_loader(loader.name, loader)
switch = importlib.util.module_from_spec(spec)
loader.exec_module(switch)


class SwitchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "profiles/worker-sol").mkdir(parents=True)
        (self.root / "profiles/worker-sol/config.yaml").write_text("model:\n  default: gpt-5.6-sol\n")
        (self.root / "config.yaml").write_text(
            "kanban:\n  dispatch_profiles:\n    - harness-worker\n  auto_decompose: false\n")
        self.calls = self.root / "calls.jsonl"
        self.fake = self.root / "hermes"
        self.fake.write_text(f"#!{sys.executable}\nimport json, sys\n"
                             f"open({str(self.calls)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n")
        self.fake.chmod(0o700)

    def run_switch(self, *args):
        with redirect_stdout(io.StringIO()) as out:
            code = switch.main(["--home-root", str(self.root), "--hermes", str(self.fake), *args])
        return code, out.getvalue()

    def calls_made(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def test_switch_to_gpt_sets_main_and_every_helper_and_backs_up(self):
        code, _ = self.run_switch("--profile", "worker-sol", "--to", "gpt", "--model", "gpt-5.6-luna")
        self.assertEqual(code, 0)
        calls = self.calls_made()
        self.assertEqual(calls[0], ["-p", "worker-sol", "config", "set", "model.provider", "openai-codex"])
        self.assertIn(["-p", "worker-sol", "config", "set", "model.default", "gpt-5.6-luna"], calls)
        helpers = [c for c in calls if c[4].startswith("auxiliary.") and c[4].endswith(".model")]
        self.assertEqual(len(helpers), 16)
        self.assertTrue(all(c[5] == "gpt-5.6-luna" for c in helpers))
        self.assertEqual(len(list((self.root / "profiles/worker-sol").glob("config.yaml.pre-switch-*"))), 1)

    def test_fable_keeps_helpers_on_opus_and_default_profile_has_no_flag(self):
        (self.root / "config.yaml").write_text((self.root / "config.yaml").read_text() + "model:\n  default: x\n")
        self.run_switch("--profile", "default", "--to", "claude-fable")
        calls = self.calls_made()
        self.assertTrue(all(c[0] == "config" for c in calls))
        self.assertIn(["config", "set", "model.default", "claude-fable-5-1"], calls)
        helpers = [c for c in calls if c[2].startswith("auxiliary.") and c[2].endswith(".model")]
        self.assertEqual(len(helpers), 16)
        self.assertTrue(all(c[3] == "claude-opus-5-5" for c in helpers))

    def test_dispatch_add_and_remove(self):
        self.run_switch("--profile", "worker-sol", "--to", "gpt", "--dispatch", "add")
        self.assertIn("    - worker-sol\n", (self.root / "config.yaml").read_text())
        self.run_switch("--profile", "worker-sol", "--to", "gpt", "--dispatch", "remove")
        text = (self.root / "config.yaml").read_text()
        self.assertNotIn("worker-sol", text)
        self.assertIn("  auto_decompose: false", text)

    def test_dry_run_changes_nothing(self):
        code, out = self.run_switch("--profile", "worker-sol", "--to", "glm", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("model.provider zai", out)
        self.assertFalse(self.calls.exists())
        self.assertEqual(list((self.root / "profiles/worker-sol").glob("config.yaml.pre-switch-*")), [])


if __name__ == "__main__":
    unittest.main()
