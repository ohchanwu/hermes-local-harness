#!/usr/bin/env python3
"""A third GLM worker for every board (card t_f4ce916d, owner request of 2026-11-14).

Offline checks of tracked repository files only: no live /Users/chanbla11mit/.hermes
reads, board access, network or model calls.

The card adds `<prefix>-worker-glm-3` for the prefixes harness, chapt, jobcron, jss and
anki wherever the baseline names `<prefix>-worker-glm-2` as a GLM worker in service:
plugins/jev/config.json, roster.yaml, scripts/verify-state, the snapshot, four new GLM
worker SOUL sources, the reviewer and orchestrator SOULs, the orchestrator skills (each
version raised by one) and the procedures.

THIRD_GLM_WORKER_EDITS lists the exact (new, old, count) text that the card changed in
each existing policy source. reverse_third_glm_worker_edits() reverses the change; it
leaves a text that has none of the new texts unchanged, so a caller may apply it to a text
that another caller already reversed. jss_download_install_edits.py and
test_stale_test_rule_policy.py call it first, so the reversal functions of the earlier
cards receive the bytes from before this card. This module imports no other test module,
so any test module can import it.
"""
import copy
import hashlib
import json
import re
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "aec198aad4abba35209eaf95f715c2622105d471"
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
PREFIXES = ("harness", "chapt", "jobcron", "jss", "anki")
BOARD_OF = {"harness": "harness", "chapt": "cha-pt", "jobcron": "jobcron", "jss": "jss-genr", "anki": "anki"}
# The prefixes whose GLM workers have a SOUL source in this repository.
GLM_SOUL_PREFIXES = ("harness", "chapt", "jss", "anki")
# Text before the list of implementation profiles in the first paragraph of each reviewer SOUL.
REVIEWER_LIST_LEAD = {
    "harness": "one of the {} Harness implementation profiles ",
    "chapt": "one of the {} Cha PT implementation profiles ",
    "jobcron": "one of the {} authorized Jobcron implementation profiles: ",
    "jss": "one of the {} jss-genr implementation profiles ",
    "anki": "one of the {} anki implementation profiles ",
}
VERSIONS = {"harness": ("0.6.7-harness.9", "0.6.7-harness.10"), "chapt": ("0.6.7-chapt.10", "0.6.7-chapt.11"),
            "jobcron": ("0.6.9-jobcron.11", "0.6.9-jobcron.12"), "jss": ("0.6.7-jss.12", "0.6.7-jss.13"),
            "anki": ("0.6.10-anki.7", "0.6.10-anki.8")}


def soul(profile):
    return f"policies/profile-souls/{profile}/SOUL.md"


def skill(prefix):
    return f"policies/profile-skills/{prefix}-orchestrator/{RELATIVE}"


def glm(prefix, number):
    return f"`{prefix}-worker-glm-{number}`"


def three_or(prefix):
    return f"{glm(prefix, 1)}, {glm(prefix, 2)} or {glm(prefix, 3)}"


def two_or(prefix):
    return f"{glm(prefix, 1)} or {glm(prefix, 2)}"


def three_and(prefix):
    return f"{glm(prefix, 1)}, {glm(prefix, 2)} and {glm(prefix, 3)}"


def two_and(prefix):
    return f"{glm(prefix, 1)} and {glm(prefix, 2)}"


def reviewer_list(prefix, count):
    lead = REVIEWER_LIST_LEAD[prefix].format(count)
    names = f"`{prefix}-worker`, `{prefix}-worker-2`, "
    if count == "five":
        return lead + names + three_or(prefix)
    return lead + names + two_or(prefix)


def _edits():
    edits = {}
    for prefix in PREFIXES:
        edits[soul(f"{prefix}-reviewer")] = (
            (reviewer_list(prefix, "five"), reviewer_list(prefix, "four"), 1),
            (three_or(prefix), two_or(prefix), 2),
        )
        edits[soul(f"{prefix}-orchestrator")] = ((three_or(prefix), two_or(prefix), 1),)
        old_version, new_version = VERSIONS[prefix]
        skill_edits = [
            (f"version: {new_version}\n", f"version: {old_version}\n", 1),
            (f"{three_or(prefix)}, taking the three in turn,", f"{two_or(prefix)}, alternating between the two,", 1),
            (three_or(prefix), two_or(prefix), 2),
        ]
        if prefix in ("harness", "jss", "anki"):
            skill_edits.append((three_and(prefix), two_and(prefix), 1))
        edits[skill(prefix)] = tuple(skill_edits)
    return edits


# File -> ((new text, old text, number of occurrences), ...), applied in this order in both directions.
THIRD_GLM_WORKER_EDITS = _edits()
# SHA-256 of each file at the baseline of card t_f4ce916d.
BASELINE_SHA256 = {
    soul("harness-reviewer"): "080e9cc0f45bbbdad3e7513d3c5e6ec13d8f0302d542d67c20909f623920d413",
    soul("harness-orchestrator"): "4c7e92808f33b81191f48e138deedd3b8b6706574cf9563ac39be178bde6b68b",
    skill("harness"): "497401eb5e37f34179d42858a6a92e48033c87ba470c67905465792bea226762",
    soul("chapt-reviewer"): "5ba39e2ddc32f858a4e4827537327ad0372cecdcb4736eea2c0fa181e2c3a967",
    soul("chapt-orchestrator"): "08f9ebaff70d91c9979348119faa4342e08cf43c9d8de836d30a001d7006c6db",
    skill("chapt"): "47ceec5013ca612d58056c803cd77dc4cceff601d9939beefd9c5d56bbf12f7c",
    soul("jobcron-reviewer"): "075fb2d07a753cf53109b8c4a80ef095b660feb943ee87ba92a115f098c59dfd",
    soul("jobcron-orchestrator"): "bc3f7e7642abd48b9dc70c86649dc977fcc497dc96f9641fb2833538fcff62b2",
    skill("jobcron"): "0d91fcacc10be222f774ca19c9e0a0cae9f02714e54538e352e66689ea5f0f4e",
    soul("jss-reviewer"): "0cdc81e4f3382611819fa5d8cc64b2982cea1589e2985e6a3ec5ccc58d07521f",
    soul("jss-orchestrator"): "c63c26fe8f5c2731c06d9d36413d955e9c3019ada2014e2fea4c19717f9e785d",
    skill("jss"): "60f09de57e8fde5dc2783bb149d3ba7b550df45f76166fb6ec11b6af726ee416",
    soul("anki-reviewer"): "5560226d767caa0e58de349f696881e8b6dced45729cd1d8fed657239657f61f",
    soul("anki-orchestrator"): "b388ff66e6936631c7bad14bbba773ab6746950245819a611525781d823a992b",
    skill("anki"): "c4902aa7eca9f195c70c751820ba22d98dd97a3db48c97279b33829d7cea23b5",
}


def reverse_third_glm_worker_edits(relative_path, text):
    """Return text with the t_f4ce916d edits reversed; text may be str or bytes. A path that
    the card did not change, and a text that contains none of the new texts, is returned as
    the same object."""
    edits = THIRD_GLM_WORKER_EDITS.get(relative_path)
    if not edits:
        return text
    as_bytes = isinstance(text, bytes)
    current = text.decode() if as_bytes else text
    changed = False
    for new, old, count in edits:
        found = current.count(new)
        if found == 0:
            continue
        if found != count:
            raise AssertionError(f"{relative_path}: expected {count} occurrences of {new[:60]!r}, found {found}")
        current = current.replace(new, old)
        changed = True
    if not changed:
        return text
    return current.encode() if as_bytes else current


def apply_third_glm_worker_edits(relative_path, text):
    """Return the baseline text of relative_path with the t_f4ce916d edits applied (str)."""
    # The same order as the reversal: a longer text that contains a shorter one comes first.
    for new, old, count in THIRD_GLM_WORKER_EDITS.get(relative_path, ()):
        if text.count(old) != count:
            raise AssertionError(f"{relative_path}: expected {count} occurrences of {old[:60]!r}")
        text = text.replace(old, new)
    return text


def with_third_glm_worker(text):
    """A sentence of an earlier card with the GLM worker names of this card, for every prefix."""
    for prefix in PREFIXES:
        text = text.replace(f"{two_or(prefix)}, alternating between the two,",
                            f"{three_or(prefix)}, taking the three in turn,")
        text = text.replace(two_or(prefix), three_or(prefix)).replace(two_and(prefix), three_and(prefix))
    return text


def baseline_bytes(relative_path):
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{BASELINE}:{relative_path}"],
                          stdout=subprocess.PIPE, check=True).stdout


def implementation_profiles(text, prefix):
    return set(re.findall(rf"`({prefix}-worker(?:-[a-z0-9]+)*)`", text))


class PolicySources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = {path: (ROOT / path).read_text() for path in THIRD_GLM_WORKER_EDITS}

    def test_reversing_the_edits_recovers_the_baseline_bytes(self):
        self.assertEqual(set(BASELINE_SHA256), set(THIRD_GLM_WORKER_EDITS))
        for path, want in BASELINE_SHA256.items():
            with self.subTest(path=path):
                data = (ROOT / path).read_bytes()
                original = reverse_third_glm_worker_edits(path, data)
                self.assertEqual(hashlib.sha256(original).hexdigest(), want)
                self.assertEqual(reverse_third_glm_worker_edits(path, data.decode()), original.decode())
                # A second reversal changes nothing.
                self.assertIs(reverse_third_glm_worker_edits(path, original), original)
                self.assertEqual(apply_third_glm_worker_edits(path, original.decode()), data.decode())

    def test_other_paths_are_returned_unchanged(self):
        for path in (soul("harness-worker"), soul("anki-worker-glm-1"), "procedures/jev-plugin.md"):
            data = (ROOT / path).read_bytes()
            with self.subTest(path=path):
                self.assertIs(reverse_third_glm_worker_edits(path, data), data)

    def test_each_reviewer_names_exactly_the_five_implementation_profiles_of_its_board(self):
        for prefix in PREFIXES:
            text = self.text[soul(f"{prefix}-reviewer")]
            want = {f"{prefix}-worker", f"{prefix}-worker-2", *(f"{prefix}-worker-glm-{n}" for n in (1, 2, 3))}
            with self.subTest(prefix=prefix):
                self.assertEqual(text.count(reviewer_list(prefix, "five")), 1)
                self.assertEqual(implementation_profiles(text, prefix), want)
                self.assertEqual(implementation_profiles(text.split("\n\n", 1)[0], prefix), want)
                self.assertNotIn(" four ", text.split("\n\n", 1)[0])
                self.assertNotIn(two_or(prefix), text)
                self.assertEqual(text.count(three_or(prefix)), 3)

    def test_orchestrator_souls_and_skills_name_the_three_glm_workers(self):
        for prefix in PREFIXES:
            orchestrator = self.text[soul(f"{prefix}-orchestrator")]
            text = self.text[skill(prefix)]
            with self.subTest(prefix=prefix):
                self.assertEqual(orchestrator.count(
                    f"The `jev` plugin can change the assignee of a new card from `{prefix}-worker` or "
                    f"`{prefix}-worker-2` to {three_or(prefix)}, and set the card's model and provider, inside "
                    "`kanban_create`;"), 1)
                self.assertNotIn(two_or(prefix), orchestrator)
                self.assertRegex(text, rf"(?m)^version: {re.escape(VERSIONS[prefix][1])}$")
                self.assertEqual(text.count(f"`{prefix}-worker-2` to {three_or(prefix)}, taking the three in turn,"), 1)
                self.assertNotIn("alternating between the two", text)
                self.assertEqual(text.count(f"the `jev` plugin moves a card that is assigned to {three_or(prefix)} "
                                            "to `scheduled`"), 1)
                self.assertEqual(text.count(f"After the fifth change request on a card that {three_or(prefix)} "
                                            "implements"), 1)
                # The two Claude workers still alternate after the fifth change request.
                self.assertEqual(text.count("otherwise the two alternate"), 1)
                self.assertNotIn(two_or(prefix), text)
                self.assertNotIn(two_and(prefix), text)
                if prefix in ("harness", "jss", "anki"):
                    self.assertEqual(text.count(f"move a new card to the GLM workers {three_and(prefix)} "
                                                "(see Worker Selection)"), 1)

    def test_third_glm_worker_souls_follow_the_first(self):
        for prefix in GLM_SOUL_PREFIXES:
            first = (ROOT / soul(f"{prefix}-worker-glm-1")).read_text()
            want = first.replace(f"{prefix}-worker-glm-1", f"{prefix}-worker-glm-3")
            lines = want.split("\n", 1)
            lines[0] = lines[0].replace("GLM implementation worker 1", "GLM implementation worker 3")
            want = "\n".join(lines)
            third = (ROOT / soul(f"{prefix}-worker-glm-3")).read_text()
            with self.subTest(prefix=prefix):
                self.assertEqual(third, want)
                self.assertNotIn(f"{prefix}-worker-glm-1", third)
                self.assertIn(f"/Users/chanbla11mit/.hermes/profiles/{prefix}-worker-glm-3/cache/scratch", third)
                self.assertIn(f"board: {BOARD_OF[prefix]})`", third)
        # The Jobcron GLM worker SOULs stay untracked.
        for number in (1, 2, 3):
            self.assertFalse((ROOT / soul(f"jobcron-worker-glm-{number}")).exists())

    def test_existing_glm_and_claude_worker_souls_are_unchanged(self):
        for prefix in GLM_SOUL_PREFIXES:
            for profile in (f"{prefix}-worker", f"{prefix}-worker-2", f"{prefix}-worker-glm-1", f"{prefix}-worker-glm-2"):
                with self.subTest(profile=profile):
                    self.assertEqual((ROOT / soul(profile)).read_bytes(), baseline_bytes(soul(profile)))


class DesiredState(unittest.TestCase):
    def test_jev_config_has_three_glm_workers_on_every_board_and_no_other_change(self):
        config = json.loads((ROOT / "plugins/jev/config.json").read_text())
        before = json.loads(baseline_bytes("plugins/jev/config.json"))
        boards = config["routing"]["boards"]
        self.assertEqual(set(boards), set(BOARD_OF.values()))
        for prefix, board in BOARD_OF.items():
            with self.subTest(board=board):
                self.assertEqual(boards[board]["glm_workers"],
                                 [f"{prefix}-worker-glm-1", f"{prefix}-worker-glm-2", f"{prefix}-worker-glm-3"])
                self.assertEqual(before["routing"]["boards"][board]["glm_workers"],
                                 [f"{prefix}-worker-glm-1", f"{prefix}-worker-glm-2"])
        expected = copy.deepcopy(before)
        for prefix, board in BOARD_OF.items():
            expected["routing"]["boards"][board]["glm_workers"].append(f"{prefix}-worker-glm-3")
        self.assertEqual(config, expected)

    def test_roster_entries_of_the_third_glm_workers_equal_the_second(self):
        roster = json.loads((ROOT / "roster.yaml").read_text())
        profiles = {p["name"]: p for p in roster["profiles"]}
        for prefix in PREFIXES:
            second, third = f"{prefix}-worker-glm-2", f"{prefix}-worker-glm-3"
            with self.subTest(prefix=prefix):
                self.assertEqual(dict(profiles[third], name=second), profiles[second])
                entry = profiles[third]
                self.assertEqual((entry["model"], entry["provider"], entry["lifecycle"]),
                                 ("glm-5.3", "zai", "project-active"))
                self.assertTrue(entry["dispatch_eligible"] and entry["in_dispatch_pool"])
                self.assertEqual(entry["required_plugins"], ["jev"])
                for key in ("profiles",):
                    self.assertIn(third, roster["approval_policy"][key])
                self.assertIn(third, roster["project_dispatch_allowlist"])
        # No GLM worker SOUL is listed in profile_souls, as at the baseline.
        self.assertFalse([name for name in roster["profile_souls"] if "-glm-" in name])

    def test_every_list_that_names_a_second_glm_worker_names_the_third(self):
        for path in ("roster.yaml", "snapshots/sanitized-current-state.yaml"):
            data = json.loads((ROOT / path).read_text())
            stack = [(data, path)]
            while stack:
                node, where = stack.pop()
                if isinstance(node, dict):
                    stack.extend((value, f"{where}/{key}") for key, value in node.items())
                elif isinstance(node, list):
                    names = [item for item in node if isinstance(item, str)]
                    for prefix in PREFIXES:
                        if f"{prefix}-worker-glm-2" in names:
                            with self.subTest(where=where, prefix=prefix):
                                index = names.index(f"{prefix}-worker-glm-2")
                                self.assertEqual(names[index + 1], f"{prefix}-worker-glm-3")
                    stack.extend((item, f"{where}[]") for item in node if not isinstance(item, str))

    def test_verifier_pools_have_three_glm_workers_per_board(self):
        text = (ROOT / "scripts/verify-state").read_text()
        for prefix, board in BOARD_OF.items():
            names = ", ".join(f"\"{prefix}-worker-glm-{n}\"" for n in (1, 2, 3))
            self.assertIn(f"    \"{board}\": [{names}],\n", text)


class Procedures(unittest.TestCase):
    HEADING = "## Creating the third GLM worker profile of each board\n"

    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / "procedures/jev-plugin.md").read_text()
        cls.section = cls.text.split(cls.HEADING, 1)[1].split("\n## ", 1)[0]

    def test_install_list_and_board_table(self):
        install = self.text.split("## Install on a profile\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn("Profiles (36 in total;", install)
        self.assertIn("The fifteen GLM worker profiles that the routes use, three for each board:", install)
        for prefix in PREFIXES:
            for number in (1, 2, 3):
                self.assertIn(f"`{prefix}-worker-glm-{number}`", install)
        for prefix, board in BOARD_OF.items():
            row = (f"| `{board}` | `{prefix}-worker`, `{prefix}-worker-2` | `{prefix}-worker-glm-1`, "
                   f"`{prefix}-worker-glm-2`, `{prefix}-worker-glm-3` | `easy`, `medium`, `hard` |")
            self.assertEqual(self.text.count(row), 1)
        self.assertIn("(the three take turns;", self.text)
        self.assertNotIn("(the two alternate;", self.text)
        # Statements about earlier cards stay as history.
        self.assertIn("on the same 31 profiles on 2026-11-13", self.text)

    def test_tracked_soul_sources_paragraph_names_twelve_sources(self):
        paragraph = next(p for p in self.text.split("\n\n") if p.startswith("The tracked SOUL sources of the"))
        self.assertTrue(paragraph.startswith("The tracked SOUL sources of the twelve GLM workers"))
        sources = re.findall(r"`/Users/chanbla11mit/hermes-local-harness/policies/profile-souls/([a-z0-9-]+)/SOUL.md`",
                             paragraph)
        self.assertEqual(sorted(sources), sorted(f"{p}-worker-glm-{n}" for p in GLM_SOUL_PREFIXES for n in (1, 2, 3)))

    def test_creation_section(self):
        self.assertEqual(self.text.count(self.HEADING), 1)
        for prefix in PREFIXES:
            self.assertIn(f"| `{prefix}-worker-glm-3` | `{prefix}-worker-glm-1` |", self.section)
        for marker in (
                "hermes profile create <profile> --clone-from <source>",
                "`_bootstrap_profile_dir`", "`_CLONE_CONFIG_FILES`", "`_CLONE_SUBDIR_FILES`", "`_clone_plugins`",
                "`model.default` is `glm-5.3`, `model.provider` is `zai`",
                "copied as a whole file with mode 0600", "Nobody opens, prints or changes the copied `.env`.",
                "The copy contains no `auth.json`",
                "rm -f /Users/chanbla11mit/.hermes/profiles/<profile>/memories/MEMORY.md "
                "/Users/chanbla11mit/.hermes/profiles/<profile>/memories/USER.md",
                "cp /Users/chanbla11mit/hermes-local-harness/policies/profile-souls/<profile>/SOUL.md "
                "/Users/chanbla11mit/.hermes/profiles/<profile>/SOUL.md",
                "sed -e 's/jobcron-worker-glm-1/jobcron-worker-glm-3/g' -e 's/implementation worker 1/implementation "
                "worker 3/g' /Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-1/SOUL.md > "
                "/Users/chanbla11mit/.hermes/profiles/jobcron-worker-glm-3/SOUL.md",
                "hermes -p <profile> plugins list --plain --no-bundled",
                "python3 /Users/chanbla11mit/hermes-local-harness/scripts/switch-profile-model --profile <profile> "
                "--to glm --dispatch add --clear-fallbacks",
                "hermes -p <profile> auth add zai", "Nobody else runs this command or handles the key.",
                "on the five orchestrator profiles only after all five new profiles have their login",
                "a GLM worker without a Z.ai login fails its run",
                # The live labels of scripts/verify-state (fixture mode prints `dispatch_profiles` instead).
                "`FAIL: missing profile: <profile>`", "`FAIL: provider drift <profile>: expected zai`",
                "`FAIL: unable to read plugin list <profile>`",
                "`FAIL: GLM worker missing from kanban.dispatch_profiles: <profile>`",
                "`FAIL: concurrency/dispatch drift kanban.dispatch_profiles: expected [...], actual [...]`",
                "`FAIL: deployed skill copy missing: <skill> <profile>/<file>`",
                "`FAIL: plugin drift <profile>: required jev not enabled (actual ...)`",
                "`FAIL: profile SOUL drift <profile>`"):
            with self.subTest(marker=marker[:50]):
                self.assertIn(marker, self.section)
        # The owner's login comes after the dispatch entry, and the orchestrator install after the login.
        self.assertLess(self.section.index("--dispatch add"), self.section.index("auth add zai"))
        for text in (self.section,):
            self.assertNotIn("~/", text)
            self.assertNotIn("$HOME", text)

    def test_switching_procedure_counts_fifteen_glm_workers(self):
        text = (ROOT / "procedures/switching-hermes-models.md").read_text()
        self.assertIn("Card `t_f4ce916d` added a third GLM worker to every board on 2026-11-14", text)
        self.assertIn("a later deployment card creates these five profiles", text)
        self.assertIn("declares each of the fifteen with", text)
        self.assertIn("for the fifteen GLM workers in service", text)
        self.assertNotIn("each of the ten", text)
        self.assertNotIn("the ten GLM workers in service", text)


if __name__ == "__main__":
    unittest.main()
