#!/usr/bin/env python3
"""Model names and wording in the five orchestrator skill copies (t_c836d2a4).

Offline checks of tracked bytes only: no live ~/.hermes reads, board access,
network or model calls. The retired GPT model names and the coined term
"value-blind" must not appear in any copy, and every model named in a Fixed
Roster or Verification line must equal that profile's model in roster.yaml.

TERMINOLOGY_EDITS lists the exact (new, old) text this card changed, so tests
that pin older bytes of these files can reverse the change byte for byte.
"""
import hashlib
import json
import re
from pathlib import Path
import unittest

from test_card_contract_line_start_policy import reverse_owner_path_edits
from test_orchestrator_skill_changes_policy import reverse_skill_changes_edits
from test_repair_history_candidate_rules_policy import reverse_candidate_rule_edits
from test_repair_history_format_policy import reverse_repair_format_edits

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
SHARED = "skills/multi-agent-coding-orchestrator/SKILL.md"
JOBCRON = f"policies/profile-skills/jobcron-orchestrator/{RELATIVE}"
CHAPT = f"policies/profile-skills/chapt-orchestrator/{RELATIVE}"
HARNESS = f"policies/profile-skills/harness-orchestrator/{RELATIVE}"
JSS = f"policies/profile-skills/jss-orchestrator/{RELATIVE}"
ALL_COPIES = (SHARED, JOBCRON, CHAPT, HARNESS, JSS)
# File -> boards that its Fixed Roster names, in order.
ROSTER_BOARDS = {
    SHARED: ("jobcron", "cha-pt", "harness"),
    JOBCRON: ("jobcron", "cha-pt"),
    CHAPT: ("jobcron", "cha-pt"),
}
FORBIDDEN = re.compile(r"gpt-6\.1-sol|gpt-6-astra|[Vv]alue-blind")
MODEL_PAIR = re.compile(r"`([a-z0-9-]+)` \(`([a-z0-9.-]+)`\)")
VERIFICATION = re.compile(r"return `([^`]+)` for orchestrator/worker and `([^`]+)` for reviewer\.")

# Bytes of each file at baseline 44320e4a3226bfa057cb532af7fe00b97095cfe8,
# recovered by reversing TERMINOLOGY_EDITS.
PRE_TERMINOLOGY_SHA256 = {
    SHARED: "ee8adf5fb1d92be6e72fa1b2615e5c9cf688df288c2c761161cb8e583052db7f",
    JOBCRON: "ff3e828ac4a5c0efd078f158b674c38776ec8868f76394e3568a0bc87eda155a",
    CHAPT: "5e3869b816966691f585d9ed6e3eb099e28bf4e7e8ff24d00636fa97a785095f",
}


def _roster_line(prefix):
    old = (f"`{prefix}-orchestrator` (`gpt-6.1-sol`); implementation workers `{prefix}-worker` (`gpt-6.1-sol`) "
           f"and `{prefix}-worker-2` (`claude-opus-5-5`); independent `{prefix}-reviewer` (`gpt-6-astra`).")
    new = (f"`{prefix}-orchestrator` (`claude-opus-5-5`); implementation workers `{prefix}-worker` "
           f"(`claude-opus-5-5`) and `{prefix}-worker-2` (`claude-opus-5-5`); independent `{prefix}-reviewer` "
           f"(`claude-fable-5-1`).")
    return new, old


def _review_sentence(reviewers):
    return (f"Project boards use their board's designated reviewer ({reviewers}); "
            "the legacy reviewer `reviewer-sol` was retired on 2026-10-18.",
            "Project boards use Astra reviewers; the legacy board uses `reviewer-sol`.")


_VERIFICATION_EDIT = (
    "return `claude-opus-5-5` for orchestrator/worker and `claude-fable-5-1` for reviewer.",
    "return `gpt-6.1-sol` for orchestrator/worker and `gpt-6-astra` for reviewer.",
)
_AUDIT_EDIT = (
    "Keep audit events that record no secret or identifying values and narrowly justified "
    "per-operation request/poll caps",
    "Keep value-blind audit events and narrowly justified per-operation request/poll caps",
)
_SEQUENCE_EDIT = (
    "Identify the whole dependent credential/capability sequence, recording names and order only, never values, "
    "before an execution window",
    "Identify the whole dependent credential/capability sequence value-blind before an execution window",
)
_OPT_IN_EDIT = (
    "Record whether each opt-in input is set (yes or no) in the effective launch environment, never its value, "
    "before launch.",
    "Record effective opt-in presence value-blindly before launch.",
)
_PANE_EDIT = (
    "inspect the exact pane and phase without recording any input values before any retry",
    "inspect the exact pane and phase value-blindly before any retry",
)
# The retirement paragraph and advisor line, copied verbatim from the Jobcron copy.
LEGACY_RETIREMENT = (
    "Legacy/default-board lanes are retired and inert: the GLM Flash and GLM-full workers were archived on "
    "2026-10-18 and the GPT Luna, Terra, Sol and Astra workers and `reviewer-sol` were retired the same day. "
    "Never assign, escalate, or route review to them. Archived copies are in `~/.hermes/profile-exports/`; "
    "restore one only per `procedures/switching-hermes-models.md`.\n\n"
    "- `advisor`: read/analyze advisor; not a Kanban implementation lane.\n"
)
_SHARED_LEGACY_EDIT = (
    LEGACY_RETIREMENT,
    "Legacy/default-board control profiles remain installed for rollback and existing history:\n\n"
    "- `default`: legacy `gpt-5.6-sol` orchestrator and user-facing profile.\n"
    "- `reviewer-sol`: legacy `gpt-5.6-sol` independent reviewer.\n"
    "- `advisor`: read/analyze advisor; not a Kanban implementation lane.\n\n"
    "Legacy/default-board implementation profiles, in escalation order:\n\n"
    "1. `worker-flash-1`, `worker-flash-2`, `worker-flash-3`: Z.AI `glm-5.3-flash`.\n"
    "2. `worker-luna-1`, `worker-luna-2`: OpenAI Codex `gpt-5.6-luna`.\n"
    "3. `worker-terra-1`: OpenAI Codex `gpt-5.6-terra`.\n"
    "4. `worker-glm-full`: Z.AI `glm-5.3`.\n"
    "5. `worker-sol`: OpenAI Codex `gpt-5.6-sol`.\n"
    "6. `worker-astra`: OpenAI Codex `gpt-6-astra`.\n",
)
# File -> ((new text, old text), ...). Each new text occurs exactly once.
TERMINOLOGY_EDITS = {
    SHARED: (_roster_line("jobcron"), _roster_line("chapt"), _roster_line("harness"), _SHARED_LEGACY_EDIT,
             _AUDIT_EDIT, _SEQUENCE_EDIT,
             _review_sentence("`jobcron-reviewer`, `chapt-reviewer`, `harness-reviewer`"), _VERIFICATION_EDIT),
    JOBCRON: (_roster_line("jobcron"), _roster_line("chapt"), _AUDIT_EDIT, _SEQUENCE_EDIT,
              _review_sentence("`jobcron-reviewer`, `chapt-reviewer`"), _OPT_IN_EDIT, _PANE_EDIT,
              _VERIFICATION_EDIT),
    CHAPT: (_roster_line("jobcron"), _roster_line("chapt"), _AUDIT_EDIT, _SEQUENCE_EDIT,
            _review_sentence("`jobcron-reviewer`, `chapt-reviewer`"), _VERIFICATION_EDIT),
}


def reverse_terminology_edits(relative_path, text):
    """Return text with this card's edits reversed; text may be str or bytes."""
    as_bytes = isinstance(text, bytes)
    for new, old in TERMINOLOGY_EDITS[relative_path]:
        if as_bytes:
            new, old = new.encode(), old.encode()
        if text.count(new) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {new[:80]!r}")
        text = text.replace(new, old, 1)
    return text


def fixed_roster(text):
    match = re.search(r"^## Fixed Roster\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match is not None, "Fixed Roster"
    return match.group(1)


class OrchestratorSkillTerminologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        roster = json.loads((ROOT / "roster.yaml").read_text())
        cls.models = {profile["name"]: profile["model"] for profile in roster["profiles"]}
        cls.fleets = {fleet["board"]: fleet for fleet in roster["project_fleets"].values()}
        cls.text = {path: (ROOT / path).read_text() for path in ALL_COPIES}

    def test_no_retired_model_name_or_coined_term(self):
        for path, text in self.text.items():
            with self.subTest(path=path):
                hits = [(number, line[:120]) for number, line in enumerate(text.splitlines(), 1)
                        if FORBIDDEN.search(line)]
                self.assertEqual(hits, [])

    def test_fixed_roster_models_equal_roster(self):
        for path, boards in ROSTER_BOARDS.items():
            section = fixed_roster(self.text[path])
            for board in boards:
                fleet = self.fleets[board]
                lines = [line for line in section.splitlines() if f" board `{board}`: " in line]
                with self.subTest(path=path, board=board):
                    self.assertEqual(len(lines), 1)
                    pairs = dict(MODEL_PAIR.findall(lines[0]))
                    names = [fleet["orchestrator"], *fleet["workers"], fleet["reviewer"]]
                    self.assertEqual(sorted(pairs), sorted(names))
                    for name in names:
                        self.assertEqual(pairs[name], self.models[name], name)
            with self.subTest(path=path, check="no other board"):
                other = [line for line in section.splitlines() if " board `" in line
                         and not any(f" board `{board}`: " in line for board in boards)]
                self.assertEqual(other, [])

    def test_every_named_model_equals_roster(self):
        # Covers model pairs outside the Fixed Roster and the two copies without one.
        for path, text in self.text.items():
            pairs = MODEL_PAIR.findall(text)
            with self.subTest(path=path):
                if path not in ROSTER_BOARDS:
                    self.assertEqual(pairs, [])
                for name, model in pairs:
                    self.assertIn(name, self.models)
                    self.assertEqual(model, self.models[name], name)

    def test_verification_models_equal_roster(self):
        for path, boards in ROSTER_BOARDS.items():
            matches = VERIFICATION.findall(self.text[path])
            with self.subTest(path=path):
                self.assertEqual(len(matches), 1)
                controller_or_worker, reviewer = matches[0]
                for board in boards:
                    fleet = self.fleets[board]
                    for name in (fleet["orchestrator"], *fleet["workers"]):
                        self.assertEqual(self.models[name], controller_or_worker, name)
                    self.assertEqual(self.models[fleet["reviewer"]], reviewer, fleet["reviewer"])
        for path in (HARNESS, JSS):
            with self.subTest(path=path):
                self.assertEqual(VERIFICATION.findall(self.text[path]), [])

    def test_review_contract_names_each_designated_reviewer(self):
        for path, boards in ROSTER_BOARDS.items():
            reviewers = ", ".join(f"`{self.fleets[board]['reviewer']}`" for board in boards)
            with self.subTest(path=path):
                self.assertEqual(self.text[path].count(_review_sentence(reviewers)[0]), 1)
                self.assertNotIn("Astra reviewers", self.text[path])

    def test_shared_copy_uses_the_jobcron_retirement_paragraph(self):
        self.assertEqual(self.text[JOBCRON].count(LEGACY_RETIREMENT), 1)
        self.assertEqual(self.text[SHARED].count(LEGACY_RETIREMENT), 1)
        self.assertNotIn("remain installed", self.text[SHARED])
        self.assertIn("\n\n" + LEGACY_RETIREMENT + "\nKeep `worker-terra-2` installed but dormant", self.text[SHARED])

    def test_reversing_the_edits_recovers_the_baseline_bytes(self):
        for path, want in PRE_TERMINOLOGY_SHA256.items():
            with self.subTest(path=path):
                # Reverse the later Skill Changes section (t_0a8674fe), the repair_history
                # candidate rule change (t_6436ac1c), the owner shell command path change
                # (t_bd860536) and the repair_history format change (t_a4dccec1) first.
                current = reverse_skill_changes_edits(path, (ROOT / path).read_bytes())
                current = reverse_candidate_rule_edits(path, current)
                current = reverse_owner_path_edits(path, current)
                current = reverse_repair_format_edits(path, current)
                original = reverse_terminology_edits(path, current)
                self.assertEqual(hashlib.sha256(original).hexdigest(), want)

    def test_harness_and_jss_copies_are_unchanged(self):
        # Unchanged by this card; the later Skill Changes section (t_0a8674fe), repair_history
        # candidate rule change (t_6436ac1c), owner shell command path change (t_bd860536) and
        # repair_history format change (t_a4dccec1) are reversed first.
        for path, want in ((HARNESS, "c1e78607948f4d0c890ef86afb2fe63f3898efe35d8c413ec225147c99d8f17c"),
                           (JSS, "589ca4a53186e13726d4f77a6a647a36559fa8795dbc7682000007114211b5e6")):
            with self.subTest(path=path):
                current = reverse_skill_changes_edits(path, (ROOT / path).read_bytes())
                current = reverse_candidate_rule_edits(path, current)
                current = reverse_owner_path_edits(path, current)
                original = reverse_repair_format_edits(path, current)
                self.assertEqual(hashlib.sha256(original).hexdigest(), want)


if __name__ == "__main__":
    unittest.main(verbosity=2)
