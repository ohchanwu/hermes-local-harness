#!/usr/bin/env python3
"""The declared Fable model changes from claude-fable-5-1 to claude-fable-5-2 (t_a6bbe808).

Offline checks of tracked repository files only: no live ~/.hermes reads, board
access, network or model calls. roster.yaml, the claude-fable target of
scripts/switch-profile-model and the Fable roles of the scripts/verify-state
model policy declare the same Fable model, claude-fable-5-2.

FABLE_5_2_EDITS lists the exact (new, old) text this card changed in each
orchestrator skill copy, so tests that pin older bytes of these files can
reverse the change byte for byte with reverse_fable_5_2_edits(). This module
imports no other test module, so any test module can import it.
"""
import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
OLD_MODEL, NEW_MODEL = "claude-fable-5-1", "claude-fable-5-2"
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
SHARED = "skills/multi-agent-coding-orchestrator/SKILL.md"
JOBCRON = f"policies/profile-skills/jobcron-orchestrator/{RELATIVE}"
CHAPT = f"policies/profile-skills/chapt-orchestrator/{RELATIVE}"


def _reviewer(prefix, model):
    return f"independent `{prefix}-reviewer` (`{model}`)."


def _edit(text_of):
    return text_of(NEW_MODEL), text_of(OLD_MODEL)


_VERIFICATION = _edit(lambda model: f"and `{model}` for reviewer.")
# File -> ((new text, old text), ...). Each new text occurs exactly once.
FABLE_5_2_EDITS = {
    SHARED: (_edit(lambda m: _reviewer("jobcron", m)), _edit(lambda m: _reviewer("chapt", m)),
             _edit(lambda m: _reviewer("harness", m)), _VERIFICATION),
    JOBCRON: (_edit(lambda m: _reviewer("jobcron", m)), _edit(lambda m: _reviewer("chapt", m)), _VERIFICATION),
    CHAPT: (_edit(lambda m: _reviewer("jobcron", m)), _edit(lambda m: _reviewer("chapt", m)), _VERIFICATION),
}
# Bytes of each file at baseline bed49a9347ca14339f9eeadc27b08c1f962169be.
BASELINE_SHA256 = {
    SHARED: "7ed84549c2ad2cfdee04cee3825ae8a2b61b73d111f8a1a7e60d116daed8b23f",
    JOBCRON: "e999adc7145a8b71db7bda8b7191f170d8ab5c2d67c9962f0f330ed9a74bf09c",
    CHAPT: "eb8380a518d73756527026aaffcb9cac5a23b98924d4405b649df49245adc852",
}
FABLE_PROFILES = ("advisor", "anki-reviewer", "chapt-reviewer", "harness-reviewer", "jobcron-reviewer",
                  "jss-reviewer")
FABLE_ROLES = ("advisor", "independent reviewer", "project independent reviewer")


def reverse_fable_5_2_edits(relative_path, text):
    """Return text with this card's edits reversed; text may be str or bytes."""
    as_bytes = isinstance(text, bytes)
    if as_bytes:
        text = text.decode()
    for new, old in FABLE_5_2_EDITS.get(relative_path, ()):
        if text.count(new) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {new[:60]!r}")
        text = text.replace(new, old, 1)
    return text.encode() if as_bytes else text


def load_script(name, relative_path):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / relative_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class FableDeclaredModel(unittest.TestCase):
    def test_reversing_the_edits_recovers_the_baseline_bytes(self):
        for path, want in BASELINE_SHA256.items():
            with self.subTest(path=path):
                original = reverse_fable_5_2_edits(path, (ROOT / path).read_bytes())
                self.assertEqual(hashlib.sha256(original).hexdigest(), want)

    def test_skill_copies_name_only_the_new_model(self):
        for path, edits in FABLE_5_2_EDITS.items():
            text = (ROOT / path).read_text()
            with self.subTest(path=path):
                self.assertNotIn(OLD_MODEL, text)
                self.assertEqual(text.count(NEW_MODEL), len(edits))

    def test_roster_switch_target_and_model_policy_declare_the_same_model(self):
        roster = json.loads((ROOT / "roster.yaml").read_text())
        fable = sorted(p["name"] for p in roster["profiles"] if p.get("model", "").startswith("claude-fable"))
        self.assertEqual(fable, sorted(FABLE_PROFILES))
        for profile in roster["profiles"]:
            if profile["name"] in FABLE_PROFILES:
                with self.subTest(profile=profile["name"]):
                    self.assertEqual(profile["model"], NEW_MODEL)
                    self.assertEqual(profile["provider"], "claude-subscription")
        switch = load_script("switch_profile_model_fable_5_2", "scripts/switch-profile-model")
        provider, _, main_model, helper_model = switch.TARGETS["claude-fable"]
        self.assertEqual((provider, main_model, helper_model), ("claude-subscription", NEW_MODEL, "claude-opus-5-5"))
        policy = switch.VERIFIER.MODEL_POLICY_BY_ROLE
        self.assertEqual({role: policy[role] for role in FABLE_ROLES}, dict.fromkeys(FABLE_ROLES, NEW_MODEL))


if __name__ == "__main__":
    unittest.main()
