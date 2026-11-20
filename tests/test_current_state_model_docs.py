#!/usr/bin/env python3
"""Documents that state the current main model name claude-opus-5-5 for the seven profiles (t_4422a67f).

Owner change of 2026-11-15: claude-opus-5-5 is the main model of default, advisor,
jobcron-orchestrator, chapt-orchestrator, harness-orchestrator, jss-orchestrator
and anki-orchestrator; roster.yaml and MODEL_POLICY_BY_ROLE follow from card
t_f03857d4. Offline checks of tracked repository files only: no live reads under
/Users/chanbla11mit/.hermes, board access, network or model calls. Every document
that states the current main model names claude-opus-5-5 for the seven profiles
and no longer
states that an orchestrator, the default home or the advisor currently runs
claude-fable-5-2; a manual switch of a project orchestrator to claude-fable-5-2
gives the manual model switch warning, and the way back is /model opus --global.
Text that names claude-fable-5-2 as an available model, a switch target, an
alias, a fallback or a dated record is out of scope here.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
OPUS = "claude-opus-5-5"
FABLE = "claude-fable-5-2"
README = ROOT / "README.md"
ADOPTION = {name: ROOT / f"adoption/{name}.md" for name in
            ("anki", "cha-pt", "harness", "jobcron", "jss-genr")}
PROVIDER_README = ROOT / "plugins/model-providers/claude-subscription/README.md"
PROCEDURE = ROOT / "procedures/switching-hermes-models.md"
CURRENT_SENTENCE = ("The orchestrator uses `claude-opus-5-5`; `{worker}`, `{worker2}` and the reviewer "
                    "use `claude-opus-5-5` (workers and reviewer since 2026-11-13, card `t_0faca45d`; "
                    "orchestrator since 2026-11-15, owner change; `roster.yaml` follows from card "
                    "`t_f03857d4`).")
FLEET_WORKERS = {
    "anki": ("anki-worker", "anki-worker-2"),
    "cha-pt": ("chapt-worker", "chapt-worker-2"),
    "harness": ("harness-worker", "harness-worker-2"),
    "jobcron": ("jobcron-worker", "jobcron-worker-2"),
    "jss-genr": ("jss-worker", "jss-worker-2"),
}


class CurrentStateSentences(unittest.TestCase):
    """The eight documents state claude-opus-5-5 as the current main model."""

    def test_readme_states_opus_for_every_role(self):
        # Card t_caf5dba0 put a section above this paragraph; the line is found by its start.
        line = next(text for text in README.read_text().splitlines()
                    if text.startswith("Every active profile currently runs"))
        self.assertIn("Since 2026-11-15 (owner change; `roster.yaml` follows from card `t_f03857d4`), "
                      "Opus 5.5 serves the orchestrators, the default home, the Advisor, the workers "
                      "and the reviewers", line)
        self.assertNotIn("Fable 5.2 serves", line)

    def test_adoption_records_state_opus_orchestrators(self):
        for name, path in ADOPTION.items():
            with self.subTest(record=f"adoption/{name}.md"):
                text = path.read_text()
                worker, worker2 = FLEET_WORKERS[name]
                self.assertIn(CURRENT_SENTENCE.format(worker=worker, worker2=worker2), text)
                self.assertNotIn("The orchestrator uses `claude-fable-5-2`", text)

    def test_provider_readme_table_rows_state_opus(self):
        rows = [line for line in PROVIDER_README.read_text().splitlines() if line.startswith("|")]
        current = [line for line in rows
                   if ("default (`/Users/chanbla11mit/.hermes`" in line
                       or "`orchestrator` |" in line or "| `advisor` |" in line)]
        self.assertEqual(len(current), 3, current)
        for line in current:
            with self.subTest(row=line[:60]):
                self.assertIn(f"`{OPUS}` (since 2026-11-15, owner change; roster and policy from card "
                              f"`t_f03857d4`; `{FABLE}` from", line)
                self.assertNotIn(f"| `{FABLE}` (", line)

    def test_procedure_table_and_owner_paragraph_state_opus(self):
        text = PROCEDURE.read_text()
        table = text.split("## Role models and reasoning effort", 1)[1].split("\n## ", 1)[0]
        for role in ("Orchestrator", "Advisor"):
            row = next(line for line in table.splitlines() if line.startswith(f"| {role} |"))
            with self.subTest(role=role):
                self.assertIn(f"| `{OPUS}` (since 2026-11-15, owner change; `roster.yaml` and "
                              "`MODEL_POLICY_BY_ROLE` from card `t_f03857d4`;", row)
                self.assertNotIn(f"| `{FABLE}` |", row)
        self.assertIn("`roster.yaml` and `MODEL_POLICY_BY_ROLE` follow it from card `t_f03857d4`, so the "
                      "`Main model` column of the Orchestrator and Advisor rows below names "
                      f"`{OPUS}`", text)

    def test_procedure_policy_paragraph_names_opus_for_the_seven_profiles(self):
        paragraph = next(p for p in PROCEDURE.read_text().split("## Switching one profile", 1)[1]
                         .split("\n## ", 1)[0].split("\n\n") if "outside the owner model policy" in p)
        self.assertIn(f"(provider `claude-subscription`; `{OPUS}` for the orchestrators, `default` and "
                      "the advisor, since 2026-11-15;", paragraph)
        self.assertNotIn(f"`{FABLE}` for the orchestrators", paragraph)


class ManualSwitchStatements(unittest.TestCase):
    """The section of the procedure about switching a project orchestrator by
    hand matches the behavior of scripts/verify-state."""

    @classmethod
    def setUpClass(cls):
        text = PROCEDURE.read_text()
        cls.section = text.split("## Switching a project orchestrator between Fable and Opus by hand",
                                 1)[1].split("\n## ", 1)[0]

    def test_way_back_is_opus_global(self):
        self.assertIn("Since 2026-11-15 the `config.yaml` of each project orchestrator (owner change) "
                      "and `roster.yaml` (card `t_f03857d4`) declare `claude-opus-5-5`; after a manual "
                      "switch to Fable, the way back is `/model opus --global`",
                      self.section)

    def test_fable_switch_gives_the_manual_model_switch_warning(self):
        paragraph = next(p for p in self.section.split("\n\n")
                         if p.startswith("What `scripts/verify-state` reports"))
        self.assertIn("while a project orchestrator is on `claude-fable-5-2`", paragraph)
        self.assertIn("WARN: manual model switch <name>: model.default is <observed model>, "
                      "roster declares <roster model>", paragraph)
        self.assertIn(f"`roster.yaml` keeps `{OPUS}` for the role (card `t_f03857d4`)", paragraph)
        self.assertNotIn(f"`roster.yaml` keeps `{FABLE}`", paragraph)

    def test_verify_state_warns_for_each_fable_orchestrator(self):
        from test_orchestrator_model_switch_policy import ORCHESTRATORS, fixture_main
        clean = json.loads((ROOT / "tests/fixtures/clean.yaml").read_text())
        self.assertTrue(all(clean["profile_models"][name] == OPUS for name in ORCHESTRATORS))
        fixture = json.loads(json.dumps(clean))
        fixture["profile_models"].update({name: FABLE for name in ORCHESTRATORS})
        code, output = fixture_main(fixture)
        self.assertEqual(code, 0, output)
        self.assertEqual(output.count("WARN: manual model switch"), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
