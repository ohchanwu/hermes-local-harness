#!/usr/bin/env python3
"""Claude subscription fallback of the 30 GLM workers and the five GLM reviewers (card t_50fd66f2).

Owner decisions of 2026-11-16 (section 1 and open question Q1 of
docs/specs/261116-glm-worker-profiles-by-route-and-claude-fallback.md): when the Z.ai quota
is used up, the workers of the route `easy` fall back to claude-haiku-5-5, the workers of
the routes `medium` and `hard` and the GLM reviewers to claude-sonnet-5-5, on provider
claude-subscription; the provider anthropic (a paid Console key) is never used. The
fallback_chain of each helper task names claude-subscription too: the light helper tasks
claude-haiku-5-5, the other helper tasks the profile's own fallback model.

Offline checks of tracked repository files and fixture-mode verification only: no live
profile, board, network or model call, and no write under /Users/chanbla11mit/.hermes.
"""
from contextlib import redirect_stdout
import copy
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

from harness_orchestrator_recovery_edits import reverse_harness_recovery_edits

ROOT = Path(__file__).resolve().parents[1]
ROSTER = ROOT / "roster.yaml"
VERIFY = ROOT / "scripts/verify-state"
FIXTURES = ROOT / "tests/fixtures"
SOULS = ROOT / "policies/profile-souls"

PROVIDER = "claude-subscription"
HAIKU, SONNET = "claude-haiku-5-5", "claude-sonnet-5-5"
PREFIXES = ("jobcron", "chapt", "harness", "jss", "anki")
# The owner's table, written out here and not read from scripts/verify-state.
OWNER_FALLBACK_MODEL = {
    **{f"{prefix}-worker-glm-{route}-{number}": HAIKU if route == "easy" else SONNET
       for prefix in PREFIXES for route in ("easy", "medium", "hard") for number in (1, 2)},
    **{f"{prefix}-reviewer-glm": SONNET for prefix in PREFIXES},
}
HELPER_TASKS = ("vision", "compression", "skills_hub", "approval", "review", "mcp", "title_generation",
                "memory_query_rewrite", "tts_audio_tags", "triage_specifier", "kanban_decomposer",
                "profile_describer", "goal_judge", "curator", "monitor", "background_review")
LIGHT_HELPER_TASKS = ("title_generation", "memory_query_rewrite", "tts_audio_tags", "profile_describer",
                      "skills_hub", "vision")
COMPAT = "plugins/model-providers/claude-subscription/compat.py"
ANTHROPIC_FIXTURE = "glm-fallback-anthropic.yaml"
ANTHROPIC_FIXTURE_LINE = (
    'fallback drift harness-worker-glm-medium-1 fallback_providers: expected '
    '[{"provider": "claude-subscription", "model": "claude-sonnet-5-5"}], actual '
    '[{"provider": "anthropic", "model": "claude-sonnet-5-5"}]')


def soul_sentence(profile):
    """The sentence that this card inserts after the first sentence of the SOUL source of profile."""
    if profile.endswith("-reviewer-glm"):
        model, done = SONNET, "the review is then carried out in the same way"
    else:
        model = OWNER_FALLBACK_MODEL[profile]
        done = "the card is then completed in the same way"
    return (f"When the Z.ai quota is used up, Hermes can switch the run to provider `claude-subscription` "
            f"with model `{model}`; {done}, and the `jev` rules are unchanged.")


# Path of each GLM SOUL source that this card changed -> the inserted text (a space and the
# sentence), at the end of the first sentence. The six jobcron GLM workers have no tracked SOUL
# source (section 3 of the specification).
GLM_CLAUDE_FALLBACK_SOUL_EDITS = {
    f"policies/profile-souls/{name}/SOUL.md": " " + soul_sentence(name)
    for name in OWNER_FALLBACK_MODEL if not name.startswith("jobcron-worker-glm-")}


def reverse_glm_claude_fallback_edits(relative_path, text):
    """Return text with this card's SOUL sentence removed; text may be str or bytes.

    glm_route_worker_names_edits.reverse_glm_route_worker_name_edits calls it first, so every test
    that recovers the bytes of an earlier commit reverses this card's edit before the edits of the
    earlier cards. A path that the card did not change, and a text without the sentence, is
    returned as the same object. A text that contains the sentence more than once raises
    AssertionError. This function uses only the standard library."""
    # The later edits of card t_40028345 in the harness-orchestrator skill are reversed first.
    text = reverse_harness_recovery_edits(relative_path, text)
    inserted = GLM_CLAUDE_FALLBACK_SOUL_EDITS.get(relative_path)
    if inserted is None:
        return text
    as_bytes = isinstance(text, bytes)
    value = text.decode() if as_bytes else text
    found = value.count(inserted)
    if found == 0:
        return text
    if found != 1:
        raise AssertionError(f"{relative_path}: expected 1 occurrence of the fallback sentence, found {found}")
    value = value.replace(inserted, "")
    return value.encode() if as_bytes else value


def load(path):
    return json.loads(Path(path).read_text())


def load_verifier():
    spec = importlib.util.spec_from_loader(
        "verify_state_glm_fallback", importlib.machinery.SourceFileLoader("verify_state_glm_fallback", str(VERIFY)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def quiet(function, *args, **kwargs):
    errors = []
    with redirect_stdout(io.StringIO()):
        function(errors, *args, **kwargs)
    return errors


def run_fixture(path):
    result = subprocess.run([sys.executable, str(VERIFY), "--fixture", str(path)],
                            text=True, capture_output=True)
    return result.returncode, result.stdout + result.stderr


def fail_lines(output):
    return [line[len("FAIL: "):] for line in output.splitlines() if line.startswith("FAIL: ")]


def entry(roster, name):
    return next(p for p in roster["profiles"] if p["name"] == name)


def shown(entries):
    return json.dumps(entries)


class Roster(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roster = load(ROSTER)
        cls.profiles = {p["name"]: p for p in cls.roster["profiles"]}

    def test_the_owner_table_has_35_profiles(self):
        self.assertEqual(len(OWNER_FALLBACK_MODEL), 35)
        self.assertEqual(sum(1 for model in OWNER_FALLBACK_MODEL.values() if model == HAIKU), 10)

    def test_each_glm_profile_declares_the_owner_fallback(self):
        for name, model in OWNER_FALLBACK_MODEL.items():
            with self.subTest(profile=name):
                profile = self.profiles[name]
                self.assertEqual((profile["model"], profile["provider"]), ("glm-5.3", "zai"))
                self.assertEqual(profile["fallback_providers"], [{"provider": PROVIDER, "model": model}])
                self.assertEqual(list(profile["auxiliary_fallback_chain"]), list(HELPER_TASKS))
                for task, chain in profile["auxiliary_fallback_chain"].items():
                    want = HAIKU if task in LIGHT_HELPER_TASKS else model
                    self.assertEqual(chain, [{"provider": PROVIDER, "model": want}], task)
                self.assertNotIn("auxiliary_models", profile)
                self.assertNotIn("anthropic", json.dumps(profile))

    def test_the_task_lists_match_the_verifier(self):
        verifier = load_verifier()
        self.assertEqual(verifier.HELPER_TASKS, HELPER_TASKS)
        self.assertEqual(verifier.LIGHT_HELPER_TASKS, LIGHT_HELPER_TASKS)

    def test_both_fallback_models_are_in_compat_models(self):
        models = load_verifier().claude_subscription_models()
        self.assertIn(HAIKU, models)
        self.assertIn(SONNET, models)


class Verifier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verifier = load_verifier()
        cls.roster = load(ROSTER)

    def check(self, roster, **kwargs):
        return (quiet(self.verifier.check_glm_worker_profiles, roster, **kwargs)
                + quiet(self.verifier.check_glm_reviewer_profiles, roster, **kwargs))

    def changed(self, name, change):
        roster = copy.deepcopy(self.roster)
        change(entry(roster, name))
        return roster

    def test_the_repository_roster_passes(self):
        self.assertEqual(self.check(self.roster), [])

    def test_the_expected_fallback_follows_the_owner_table(self):
        for name, model in OWNER_FALLBACK_MODEL.items():
            with self.subTest(profile=name):
                self.assertEqual(self.verifier.glm_fallback_model(name), model)
        self.assertIsNone(self.verifier.glm_fallback_model("harness-worker"))

    def test_anthropic_in_fallback_providers_is_rejected(self):
        roster = self.changed("harness-worker-glm-medium-1", lambda p: p.update(
            fallback_providers=[{"provider": "anthropic", "model": SONNET}]))
        self.assertEqual(self.check(roster), [
            "GLM fallback drift harness-worker-glm-medium-1 fallback_providers: expected "
            f"{shown([{'provider': PROVIDER, 'model': SONNET}])}, declared "
            f"{shown([{'provider': 'anthropic', 'model': SONNET}])}",
            "GLM fallback names anthropic harness-worker-glm-medium-1 fallback_providers[0]: the anthropic "
            "provider is a paid Console key and is never a fallback of a GLM worker or GLM reviewer"])

    def test_anthropic_in_a_helper_chain_of_a_reviewer_is_rejected(self):
        roster = self.changed("anki-reviewer-glm", lambda p: p["auxiliary_fallback_chain"].update(
            compression=[{"provider": "anthropic", "model": SONNET}]))
        self.assertEqual(self.check(roster), [
            "GLM fallback drift anki-reviewer-glm auxiliary_fallback_chain.compression: expected "
            f"{shown([{'provider': PROVIDER, 'model': SONNET}])}, declared "
            f"{shown([{'provider': 'anthropic', 'model': SONNET}])}",
            "GLM fallback names anthropic anki-reviewer-glm auxiliary_fallback_chain.compression[0]: the "
            "anthropic provider is a paid Console key and is never a fallback of a GLM worker or GLM reviewer"])

    def test_another_provider_is_rejected(self):
        roster = self.changed("jss-worker-glm-hard-2", lambda p: p.update(
            fallback_providers=[{"provider": "zai", "model": SONNET}]))
        errors = self.check(roster)
        self.assertEqual(len(errors), 2, errors)
        self.assertEqual(errors[1], "GLM fallback provider not allowed jss-worker-glm-hard-2 fallback_providers[0]: "
                                    "provider zai, expected claude-subscription")

    def test_a_missing_fallback_entry_is_rejected(self):
        roster = self.changed("chapt-worker-glm-easy-2", lambda p: p.pop("fallback_providers"))
        self.assertEqual(self.check(roster), [
            "GLM fallback drift chapt-worker-glm-easy-2 fallback_providers: expected "
            f"{shown([{'provider': PROVIDER, 'model': HAIKU}])}, declared unset"])
        roster = self.changed("chapt-worker-glm-easy-2", lambda p: p.update(fallback_providers=[]))
        self.assertEqual(self.check(roster), [
            "GLM fallback drift chapt-worker-glm-easy-2 fallback_providers: expected "
            f"{shown([{'provider': PROVIDER, 'model': HAIKU}])}, declared []"])
        roster = self.changed("jobcron-reviewer-glm", lambda p: p["auxiliary_fallback_chain"].pop("vision"))
        self.assertEqual(self.check(roster), [
            "GLM fallback drift jobcron-reviewer-glm auxiliary_fallback_chain.vision: expected "
            f"{shown([{'provider': PROVIDER, 'model': HAIKU}])}, declared unset"])
        roster = self.changed("harness-worker-glm-hard-1", lambda p: p.pop("auxiliary_fallback_chain"))
        errors = self.check(roster)
        self.assertEqual(len(errors), len(HELPER_TASKS), errors)
        self.assertTrue(all(line.startswith("GLM fallback drift harness-worker-glm-hard-1 auxiliary_fallback_chain.")
                            for line in errors))

    def test_a_wrong_route_model_is_rejected(self):
        # An easy worker on the Sonnet fallback of the other routes.
        roster = self.changed("anki-worker-glm-easy-1", lambda p: p.update(
            fallback_providers=[{"provider": PROVIDER, "model": SONNET}]))
        self.assertEqual(self.check(roster), [
            "GLM fallback drift anki-worker-glm-easy-1 fallback_providers: expected "
            f"{shown([{'provider': PROVIDER, 'model': HAIKU}])}, declared "
            f"{shown([{'provider': PROVIDER, 'model': SONNET}])}"])

    def test_a_model_outside_compat_models_is_rejected(self):
        roster = self.changed("harness-reviewer-glm", lambda p: p.update(
            fallback_providers=[{"provider": PROVIDER, "model": "claude-not-in-models"}]))
        errors = self.check(roster)
        self.assertEqual(len(errors), 2, errors)
        self.assertEqual(errors[1], "GLM fallback model not allowed harness-reviewer-glm fallback_providers[0]: "
                                    f"model claude-not-in-models is not in MODELS of {COMPAT}")
        # The allowlist is MODELS of compat.py: without claude-sonnet-5-5 every Sonnet entry fails.
        errors = self.check(self.roster, allowed_models=frozenset({HAIKU}))
        sonnet_entries = sum(1 + len(HELPER_TASKS) - len(LIGHT_HELPER_TASKS)
                             for model in OWNER_FALLBACK_MODEL.values() if model == SONNET)
        self.assertEqual(len(errors), sonnet_entries)
        self.assertTrue(all(line.startswith("GLM fallback model not allowed ") and "claude-sonnet-5-5" in line
                            for line in errors))

    def test_an_unreadable_allowlist_is_an_error(self):
        verifier = load_verifier()
        verifier.claude_subscription_models = lambda: None
        errors = quiet(verifier.check_glm_reviewer_profiles, self.roster)
        self.assertEqual(len(errors), 5)
        self.assertTrue(all(line.startswith("GLM fallback check impossible ") and line.endswith(
            f"the claude-subscription allowlist (MODELS in {COMPAT}) is unreadable") for line in errors))

    def test_auxiliary_models_stays_forbidden_on_a_glm_reviewer(self):
        roster = self.changed("jss-reviewer-glm", lambda p: p.update(
            auxiliary_models={"light_tasks": HAIKU, "other_tasks": SONNET}))
        self.assertEqual(quiet(self.verifier.check_glm_reviewer_profiles, roster), [
            "GLM reviewer declares auxiliary_models: jss-reviewer-glm must declare none, as the GLM workers"])

    def test_a_credential_field_value_is_not_shown(self):
        secret = "synthetic-credential-value"
        roster = self.changed("harness-worker-glm-easy-1", lambda p: p.update(
            fallback_providers=[{"provider": "anthropic", "model": HAIKU, "api_key": secret}]))
        errors = self.check(roster)
        self.assertTrue(errors)
        self.assertNotIn(secret, "\n".join(errors))


class Fixtures(unittest.TestCase):
    def test_the_clean_fixture_passes(self):
        code, output = run_fixture(FIXTURES / "clean.yaml")
        self.assertEqual(code, 0, output)
        self.assertIn("OK: desired state matches observed state", output)

    def test_the_clean_fixture_observes_the_owner_fallback(self):
        settings = load(FIXTURES / "clean.yaml")["profile_fallback_settings"]
        for name, model in OWNER_FALLBACK_MODEL.items():
            with self.subTest(profile=name):
                self.assertEqual(settings[name]["fallback_providers"], [{"provider": PROVIDER, "model": model}])
                self.assertEqual(settings[name]["auxiliary"]["compression"]["fallback_chain"],
                                 [{"provider": PROVIDER, "model": model}])
                self.assertEqual(settings[name]["auxiliary"]["vision"]["fallback_chain"],
                                 [{"provider": PROVIDER, "model": HAIKU}])

    def test_the_anthropic_fixture_fails_with_its_expected_line(self):
        code, output = run_fixture(FIXTURES / ANTHROPIC_FIXTURE)
        self.assertEqual(code, 1, output)
        self.assertNotIn("OK: desired state matches observed state", output)
        self.assertEqual(fail_lines(output), [ANTHROPIC_FIXTURE_LINE])


class Souls(unittest.TestCase):
    def test_each_tracked_glm_soul_names_its_fallback_after_the_first_sentence(self):
        names = sorted(path.parent.name for path in SOULS.glob("*/SOUL.md")
                       if "-worker-glm-" in path.parent.name or path.parent.name.endswith("-reviewer-glm"))
        # The six jobcron GLM workers have no tracked SOUL source (section 3 of the specification).
        self.assertEqual(names, sorted(name for name in OWNER_FALLBACK_MODEL
                                       if not name.startswith("jobcron-worker-glm-")))
        self.assertEqual(sorted(path.split("/")[-2] for path in GLM_CLAUDE_FALLBACK_SOUL_EDITS), names)
        for name in names:
            with self.subTest(profile=name):
                text = (SOULS / name / "SOUL.md").read_text()
                first = text[:text.index(". ") + 1]
                self.assertTrue(text.startswith(f"{first} {soul_sentence(name)} "), text[:400])
                self.assertEqual(text.count("Z.ai quota"), 1)

    def test_the_sentence_is_the_only_change_of_each_soul_source(self):
        baseline = "c91e172f9a19adb6a5964852ec10c2397d231f8a"
        for relative, inserted in GLM_CLAUDE_FALLBACK_SOUL_EDITS.items():
            with self.subTest(path=relative):
                data = (ROOT / relative).read_bytes()
                before = subprocess.run(["git", "show", f"{baseline}:{relative}"], cwd=ROOT,
                                        capture_output=True, check=True).stdout
                original = reverse_glm_claude_fallback_edits(relative, data)
                self.assertEqual(original, before)
                self.assertEqual(reverse_glm_claude_fallback_edits(relative, data.decode()), before.decode())
                self.assertIs(reverse_glm_claude_fallback_edits(relative, original), original)
                end = before.decode().index(". ") + 1
                self.assertEqual(data.decode(), before.decode()[:end] + inserted + before.decode()[end:])
                with self.assertRaises(AssertionError):
                    reverse_glm_claude_fallback_edits(relative, data.decode() + inserted)
        data = (ROOT / "policies/profile-souls/harness-worker/SOUL.md").read_bytes()
        self.assertIs(reverse_glm_claude_fallback_edits("policies/profile-souls/harness-worker/SOUL.md", data), data)


if __name__ == "__main__":
    unittest.main()
