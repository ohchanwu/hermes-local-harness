#!/usr/bin/env python3
"""The declared Fable model changes from claude-fable-5-1 to claude-fable-5-2 (t_a6bbe808).

Offline checks of tracked repository files only: no live ~/.hermes reads, board
access, network or model calls. roster.yaml, the claude-fable target of
scripts/switch-profile-model and the Fable roles of the scripts/verify-state
model policy declare the same Fable model, claude-fable-5-2.

FABLE_5_2_EDITS lists the exact (new, old) text this card changed in each
orchestrator skill copy, so tests that pin older bytes of these files can
reverse the change byte for byte with reverse_fable_5_2_edits().

ROLE_MODEL_EDITS lists the exact (new, old) text that card t_0faca45d
(2026-11-13: orchestrators to claude-fable-5-2, reviewers to claude-opus-5-5)
changed later in the same lines. reverse_role_model_edits() reverses it, and
reverse_fable_5_2_edits() reverses it first, so every caller that recovers the
bytes from before this card also recovers them from before t_0faca45d.

Card t_d3bb0983 (2026-11-15: orchestrators to claude-opus-5-5) changed the
orchestrator lines and the verification sentence again; its edits are recorded in
orchestrator_opus_5_5_edits, and reverse_role_model_edits() reverses them first.
This module imports only test_jev_policy_sources and orchestrator_opus_5_5_edits.
"""
import hashlib
import importlib.machinery
import importlib.util
import json
import re
from pathlib import Path
import unittest

from orchestrator_glm_review_edits import (VERSIONS as GLM_REVIEW_VERSIONS, reverse_orchestrator_glm_review_edits,
                                           skill as glm_review_skill)
from orchestrator_opus_5_5_edits import (BASELINE_SHA256 as OPUS_5_5_BASELINE_SHA256, VERSIONS as OPUS_5_5_VERSIONS,
                                          reverse_opus_5_5_orchestrator_edits)
from glm_route_worker_names_edits import VERSIONS as ROUTE_NAMES_VERSIONS
from test_jev_easy_medium_worker_split import VERSIONS as SPLIT_VERSIONS
from test_jev_policy_sources import reverse_jev_policy_edits

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
OPUS = "claude-opus-5-5"


def _role_model_edits(prefixes):
    """(new, old) text of the t_0faca45d edits in a copy whose Fixed Roster names these board prefixes."""
    edits = []
    for prefix in prefixes:
        edits.append((f"`{prefix}-orchestrator` (`{NEW_MODEL}`);", f"`{prefix}-orchestrator` (`{OPUS}`);"))
        edits.append((_reviewer(prefix, OPUS), _reviewer(prefix, NEW_MODEL)))
    edits.append((f"return `{NEW_MODEL}` for orchestrator, `{OPUS}` for worker and `{OPUS}` for reviewer.",
                  f"return `{OPUS}` for orchestrator/worker and `{NEW_MODEL}` for reviewer."))
    return tuple(edits)

# File -> ((new text, old text), ...). Each new text occurs exactly once.
FABLE_5_2_EDITS = {
    SHARED: (_edit(lambda m: _reviewer("jobcron", m)), _edit(lambda m: _reviewer("chapt", m)),
             _edit(lambda m: _reviewer("harness", m)), _VERIFICATION),
    JOBCRON: (_edit(lambda m: _reviewer("jobcron", m)), _edit(lambda m: _reviewer("chapt", m)), _VERIFICATION),
    CHAPT: (_edit(lambda m: _reviewer("jobcron", m)), _edit(lambda m: _reviewer("chapt", m)), _VERIFICATION),
}
# File -> ((new text, old text), ...) of card t_0faca45d. Each new text occurs exactly once.
ROLE_MODEL_EDITS = {
    SHARED: _role_model_edits(("jobcron", "chapt", "harness")),
    JOBCRON: _role_model_edits(("jobcron", "chapt")),
    CHAPT: _role_model_edits(("jobcron", "chapt")),
}
# Bytes of each file at baseline bed49a9347ca14339f9eeadc27b08c1f962169be.
BASELINE_SHA256 = {
    SHARED: "7ed84549c2ad2cfdee04cee3825ae8a2b61b73d111f8a1a7e60d116daed8b23f",
    JOBCRON: "e999adc7145a8b71db7bda8b7191f170d8ab5c2d67c9962f0f330ed9a74bf09c",
    CHAPT: "eb8380a518d73756527026aaffcb9cac5a23b98924d4405b649df49245adc852",
}
# Since card t_0faca45d (2026-11-13) the advisor and the orchestrators (default included) ran Fable;
# the reviewers moved to Opus. On 2026-11-15 the owner set claude-opus-5-5 as the main model of
# these seven profiles, and card t_f03857d4 changed roster.yaml and MODEL_POLICY_BY_ROLE to
# follow it; the claude-fable target of scripts/switch-profile-model is unchanged.
OPUS_PROFILES = ("advisor", "default", "anki-orchestrator", "chapt-orchestrator", "harness-orchestrator",
                 "jobcron-orchestrator", "jss-orchestrator")
FABLE_ROLES = ("advisor", "orchestrator", "project orchestrator")


def _reverse(edits, relative_path, text):
    as_bytes = isinstance(text, bytes)
    if as_bytes:
        text = text.decode()
    for new, old in edits.get(relative_path, ()):
        if text.count(new) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {new[:60]!r}")
        text = text.replace(new, old, 1)
    return text.encode() if as_bytes else text


def reverse_role_model_edits(relative_path, text):
    """Return text with the t_35874d04 edits, the t_d3bb0983 edits and then the t_0faca45d edits reversed;
    text may be str or bytes."""
    text = reverse_orchestrator_glm_review_edits(relative_path, text)
    return _reverse(ROLE_MODEL_EDITS, relative_path, reverse_opus_5_5_orchestrator_edits(relative_path, text))


def reverse_fable_5_2_edits(relative_path, text):
    """Return text with the t_0faca45d edits and then this card's edits reversed; text may be str or bytes."""
    return _reverse(FABLE_5_2_EDITS, relative_path, reverse_role_model_edits(relative_path, text))


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
                # The later jev plugin policy change (t_b722c617) is reversed first.
                original = reverse_fable_5_2_edits(path, reverse_jev_policy_edits(path, (ROOT / path).read_bytes()))
                self.assertEqual(hashlib.sha256(original).hexdigest(), want)

    def test_skill_copies_name_only_the_new_model(self):
        for path, edits in FABLE_5_2_EDITS.items():
            text = reverse_role_model_edits(path, (ROOT / path).read_text())
            with self.subTest(path=path):
                self.assertNotIn(OLD_MODEL, text)
                self.assertEqual(text.count(NEW_MODEL), len(edits))

    def test_reversing_the_opus_5_5_orchestrator_edits_recovers_the_baseline_bytes(self):
        for path, want in OPUS_5_5_BASELINE_SHA256.items():
            with self.subTest(path=path):
                # The later edits of card t_35874d04 are reversed first.
                original = reverse_opus_5_5_orchestrator_edits(
                    path, reverse_orchestrator_glm_review_edits(path, (ROOT / path).read_bytes()))
                self.assertEqual(hashlib.sha256(original).hexdigest(), want)
                # A second call on the reversed bytes returns them unchanged.
                self.assertIs(reverse_opus_5_5_orchestrator_edits(path, original), original)

    def test_skill_copies_name_no_fable_model_and_have_the_raised_versions(self):
        # Card t_35874d04 raised the versions of the Jobcron and Cha PT copies by one more step,
        # card t_cf518fd0 by one more, and card t_18a2dc93 by one more.
        current = {glm_review_skill(prefix): new for prefix, (_old, new) in ROUTE_NAMES_VERSIONS.items()}
        self.assertEqual({prefix: old for prefix, (old, _new) in ROUTE_NAMES_VERSIONS.items()},
                         {prefix: new for prefix, (_old, new) in SPLIT_VERSIONS.items()})
        self.assertEqual({prefix: old for prefix, (old, _new) in SPLIT_VERSIONS.items()},
                         {prefix: new for prefix, (_old, new) in GLM_REVIEW_VERSIONS.items()})
        for path, (_old, new) in OPUS_5_5_VERSIONS.items():
            new = current.get(path, new)
            text = (ROOT / path).read_text()
            with self.subTest(path=path):
                self.assertNotIn("claude-fable", text)
                self.assertEqual(re.findall(r"(?m)^version: (.+)$", text), [new])
                self.assertIn(f"return `{OPUS}` for orchestrator, worker and reviewer.", text)

    def test_roster_switch_target_and_model_policy_declare_the_same_model(self):
        roster = json.loads((ROOT / "roster.yaml").read_text())
        fable = sorted(p["name"] for p in roster["profiles"] if p.get("model", "").startswith("claude-fable"))
        self.assertEqual(fable, [])
        for profile in roster["profiles"]:
            if profile["name"] in OPUS_PROFILES:
                with self.subTest(profile=profile["name"]):
                    self.assertEqual(profile["model"], OPUS)
                    self.assertEqual(profile["provider"], "claude-subscription")
        switch = load_script("switch_profile_model_fable_5_2", "scripts/switch-profile-model")
        provider, _, main_model, helper_model = switch.TARGETS["claude-fable"]
        self.assertEqual((provider, main_model, helper_model), ("claude-subscription", NEW_MODEL, "claude-opus-5-5"))
        policy = switch.VERIFIER.MODEL_POLICY_BY_ROLE
        self.assertEqual({role: policy[role] for role in FABLE_ROLES}, dict.fromkeys(FABLE_ROLES, OPUS))


if __name__ == "__main__":
    unittest.main()
