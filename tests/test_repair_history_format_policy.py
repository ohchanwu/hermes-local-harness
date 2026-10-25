#!/usr/bin/env python3
"""repair_history formats and the repository line in orchestrator instructions (t_a4dccec1).

Offline checks of tracked bytes and of the scripts/verify-state validator only:
no live ~/.hermes reads, board access, network or model calls. All histories are
synthetic.

The verifier accepts `implementation_run_id: null` only on the final pending
attempt of the final approach before its dispatch, and permits one new
transition: that null run ID becomes a string and nothing else changes. Every
other repair rule is unchanged.

REPAIR_FORMAT_EDITS lists the exact (new, old) text this card changed in each
instruction file, so tests that pin older bytes of these files can reverse the
change byte for byte with reverse_repair_format_edits().
"""
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

from test_card_contract_line_start_policy import reverse_owner_path_edits
from test_repair_history_candidate_rules_policy import reverse_candidate_rule_edits

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
SHARED = "skills/multi-agent-coding-orchestrator/SKILL.md"
HARNESS = f"policies/profile-skills/harness-orchestrator/{RELATIVE}"
JOBCRON = f"policies/profile-skills/jobcron-orchestrator/{RELATIVE}"
CHAPT = f"policies/profile-skills/chapt-orchestrator/{RELATIVE}"
JSS = f"policies/profile-skills/jss-orchestrator/{RELATIVE}"
ANKI = f"policies/profile-skills/anki-orchestrator/{RELATIVE}"
AUTHORITY = "policies/authority-and-review.md"
LADDER = "policies/escalation-ladder.md"
SKILL_FILES = (SHARED, HARNESS, JOBCRON, CHAPT, JSS, ANKI)
POLICY_FILES = (AUTHORITY, LADDER)
TOLERANCE_TEST = "tests/test_repair_history_tolerance.py"

# Boards whose repositories each skill file must name with the exact line.
SKILL_BOARDS = {
    SHARED: ("jobcron", "cha-pt", "harness"),
    HARNESS: ("harness",),
    JOBCRON: ("jobcron",),
    CHAPT: ("cha-pt",),
    JSS: ("jss-genr",),
    ANKI: ("anki",),
}

# Bytes of each file at baseline 1363567ca7c0e9650e706092e6cdc49e7202f3c2,
# recovered by reversing REPAIR_FORMAT_EDITS.
PRE_REPAIR_FORMAT_SHA256 = {
    SHARED: "691aff3063a098cd4c8e46c63c278d35b5f49ddd0950f2b8b2069e0ea41fc290",
    HARNESS: "c1e78607948f4d0c890ef86afb2fe63f3898efe35d8c413ec225147c99d8f17c",
    JOBCRON: "ab6bf55437ce581440602faf163f545824a5cb1f4f89c03e6e6c209ee53fd6a5",
    CHAPT: "432fe0e129378fc4620820a0aa17327e1ac88d9e57df84f10c8f303b42e46d44",
    JSS: "589ca4a53186e13726d4f77a6a647a36559fa8795dbc7682000007114211b5e6",
    ANKI: "1087d0f89c2e577e8f27f3b955abe3ed65fbcfb40147c571a2e5bb3d45024e13",
    AUTHORITY: "a9d7627d3255f6f75b399d7e4e9ccdd2bc70077ecdbe2682c0ea4a2bf53f159a",
    LADDER: "6c45d4619c72785c7ed3470d3bbf45a1d3bcf52a78c8dac533f8d361d7ebac51",
}
# Bytes of the tolerance test at the same baseline; this card does not edit it.
TOLERANCE_TEST_SHA256 = "0f7df8844546fc8a6bf66c5bea77d33f2e6bd7545e916e910467d693c3113697"

EXAMPLE_STRATEGY = "Add a bounded retry limit to the export job and cover the limit with one unit test"
EXAMPLE_STRATEGY_SHA256 = "95a031c63f8d9676ebce8a6628f6c9681318ef99b653ca6619e1ff9a941aa934"
EXAMPLE_LINE = (
    'repair_history: [{"approach_id":"a1","strategy":"' + EXAMPLE_STRATEGY + '",'
    '"strategy_sha256":"' + EXAMPLE_STRATEGY_SHA256 + '",'
    '"material_difference_review_run_id":null,"attempts":[{"candidate_commit":null,'
    '"implementation_run_id":null,"review_run_id":null,"infrastructure_retries":0,'
    '"outcome":"pending"}]}]'
)
HASH_COMMAND = ("python3 -I -c 'import hashlib,sys; print(hashlib.sha256(\" \".join(sys.argv[1].split())"
                ".encode()).hexdigest())' \"<strategy text>\"")

FORMAT_RULES = (
    "Exact `repair_history` formats. `scripts/verify-state` rejects a snapshot that does not follow them:\n"
    "\n"
    "- `approach_id` uses only lowercase letters, digits and hyphens, starts with a letter or digit, and has "
    "at most 64 characters, for example `a1` or `a2`. An ID with uppercase letters, such as `A1`, is rejected.\n"
    "- `strategy_sha256` is the lowercase hexadecimal SHA-256 of the UTF-8 bytes of the `strategy` text after "
    "every run of whitespace is replaced with one space and leading and trailing whitespace is removed. Copy the "
    "strategy text byte-for-byte into the snapshot, and compute the hash from that same text with this exact "
    "command: `" + HASH_COMMAND + "`.\n"
    "- The snapshot appended before the first dispatch has `implementation_run_id: null`, because no run exists "
    "before dispatch. After the dispatcher starts the run, append a successor snapshot that sets "
    "`implementation_run_id` to that run ID and changes nothing else. Follow the same two steps when an appended "
    "attempt or approach is recorded before its dispatch. Only the final attempt of the final approach may have a "
    "null run ID, and only while that attempt has `outcome: \"pending\"`, `infrastructure_retries: 0`, "
    "`candidate_commit: null` and `review_run_id: null`. A pending attempt with a null run ID never changes "
    "directly to another outcome.\n"
    "\n"
    "Complete example of a valid snapshot line before the first dispatch:\n"
    "\n"
    "```text\n"
    + EXAMPLE_LINE + "\n"
    "```\n"
)

REPOSITORY_RULE = (
    "Write the repository line on the card body in exactly the form `Repository <exact repository path> ONLY.` "
    "`scripts/verify-state` accepts no other repository wording; a repository line that uses `EXACT` instead of "
    "`ONLY` fails the card contract check."
)


def repository_line(path):
    return f"`Repository {path} ONLY.`"


JOBCRON_LINES = "- Jobcron: " + repository_line("/Users/chanbla11mit/projects/jobcron") + "\n"
CHAPT_LINES = (
    "- Cha PT, exactly one per card: " + repository_line("/Users/chanbla11mit/projects/cha-pt") + ", "
    + repository_line("/Users/chanbla11mit/projects/cha-pt-frontend") + ", or "
    + repository_line("/Users/chanbla11mit/projects/cha-webpt-website-sync") + "\n"
)
HARNESS_LINES = "- Harness: " + repository_line("/Users/chanbla11mit/hermes-local-harness") + "\n"


def _fleet_repository_rule(lines):
    return REPOSITORY_RULE + " The exact repository lines are:\n\n" + lines + "\n"


_PROHIBITIONS = "- Explicit prohibitions on push, PR creation, deployment, and production mutation.\n\n"
_PARENT_CHILD = "Use parent-child links for real dependencies."
_ALLOWLIST_ITEM = (
    "- One exact repository from the fleet allowlist, declared with the exact repository line below, "
    "and the tenant.\n",
    "- One exact repository from the fleet allowlist and the tenant.\n",
)
_IMMUTABLE = "all prior snapshot content remains immutable.\n\n"
_NO_RESET = "never reset the budget by changing cards, workers, models, branches, prompts, or labels.\n\n"
_SKILL_POLICY_ITEM = ("Skill-policy metadata stating whether `minimal-implementation` is enabled and that "
                      "requirements and risk outrank simplification.\n\n")
_ITEM_ONE_RULE = REPOSITORY_RULE.replace("Write the repository line on the card body",
                                         "Item 1 writes the repository line") + "\n\n"


def _version(new, old):
    return (f"version: {new}\n", f"version: {old}\n")


def _fleet_edits(version, item, lines):
    return (
        version,
        (_IMMUTABLE + FORMAT_RULES + "\n", _IMMUTABLE),
        item,
        (_PROHIBITIONS + _fleet_repository_rule(lines) + _PARENT_CHILD, _PROHIBITIONS + _PARENT_CHILD),
    )


def _single_edits(version, item_number, following):
    item = f"{item_number}. {_SKILL_POLICY_ITEM}"
    return (
        version,
        (_NO_RESET + FORMAT_RULES + "\nLimits:", _NO_RESET + "Limits:"),
        (item + _ITEM_ONE_RULE + following, item + following),
    )


# File -> ((new text, old text), ...). Each new text occurs exactly once.
REPAIR_FORMAT_EDITS = {
    SHARED: _fleet_edits(_version("0.6.11", "0.6.10"), _ALLOWLIST_ITEM,
                         JOBCRON_LINES + CHAPT_LINES + HARNESS_LINES),
    JOBCRON: _fleet_edits(_version("0.6.9-jobcron.5", "0.6.9-jobcron.4"),
                          ("- The exact repository line below and the tenant.\n", "- Repository and tenant.\n"),
                          JOBCRON_LINES),
    CHAPT: _fleet_edits(_version("0.6.7-chapt.5", "0.6.7-chapt.4"), _ALLOWLIST_ITEM, CHAPT_LINES),
    HARNESS: _single_edits(_version("0.6.7-harness.4", "0.6.7-harness.3"), 12,
                           "Use `kanban_create(..., board: harness)` only after validating"),
    JSS: _single_edits(_version("0.6.7-jss.6", "0.6.7-jss.5"), 14,
                       "`scripts/verify-state` fails closed on items 1–5"),
    ANKI: _single_edits(_version("0.6.10-anki.2", "0.6.10-anki.1"), 13,
                        "`scripts/verify-state` fails closed on items 1–4"),
    AUTHORITY: (("Human gates and external-write restrictions remain unchanged.\n\n" + FORMAT_RULES,
                 "Human gates and external-write restrictions remain unchanged.\n"),),
    LADDER: (("never resets history.\n\n" + FORMAT_RULES, "never resets history.\n"),),
}


def reverse_repair_format_edits(relative_path, text):
    """Return text with this card's edits reversed; text may be str or bytes."""
    as_bytes = isinstance(text, bytes)
    if as_bytes:
        text = text.decode()
    for new, old in REPAIR_FORMAT_EDITS.get(relative_path, ()):
        if text.count(new) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {new[:60]!r}")
        text = text.replace(new, old, 1)
    return text.encode() if as_bytes else text


def load_validator():
    source = ROOT / "scripts/verify-state"
    loader = SourceFileLoader("verify_state_repair_format", str(source))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def strategy_digest(text):
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()


def attempt(run="run-worker-1", outcome="pending", retries=0, candidate=None, review=None):
    return {"candidate_commit": candidate, "implementation_run_id": run, "review_run_id": review,
            "infrastructure_retries": retries, "outcome": outcome}


def approach(approach_id, strategy, attempts, material_review=None):
    return {"approach_id": approach_id, "strategy": strategy, "strategy_sha256": strategy_digest(strategy),
            "material_difference_review_run_id": material_review, "attempts": attempts}


def copy(history):
    return json.loads(json.dumps(history))


FIRST_STRATEGY = "Use transaction fencing around the retry clock"
SECOND_STRATEGY = "Replace the retry clock with a persisted attempt counter"


def before_dispatch():
    return [approach("a1", FIRST_STRATEGY, [attempt(run=None)])]


def history_line(history):
    return "repair_history: " + json.dumps(history, separators=(",", ":"))


class NullRunIdValidityTests(unittest.TestCase):
    def setUp(self):
        self.verifier = load_validator()

    def valid(self, history):
        return self.verifier.valid_project_repair_history(history)

    def test_first_snapshot_before_dispatch_with_null_run_id_is_valid(self):
        self.assertTrue(self.valid(before_dispatch()))
        card = {"id": "t_synthetic_null_run", "board": "jobcron",
                "body": "authorization_mode: autonomous\nrepair_policy: bounded-convergence-v1",
                "comments": [{"body": history_line(before_dispatch())}]}
        errors, warnings = [], []
        self.verifier.check_project_repair_cards(errors, [card], warnings)
        self.assertEqual((errors, warnings), ([], []))

    def test_appended_attempt_and_approach_before_dispatch_are_valid(self):
        revised = [approach("a1", FIRST_STRATEGY, [
            attempt(outcome="revise", candidate="1" * 40, review="run-review-1"), attempt(run=None)])]
        self.assertTrue(self.valid(revised))
        pivoted = [approach("a1", FIRST_STRATEGY, [
                       attempt(outcome="pivot", candidate="1" * 40, review="run-review-1")]),
                   approach("a2", SECOND_STRATEGY, [attempt(run=None)], material_review="run-review-2")]
        self.assertTrue(self.valid(pivoted))

    def test_null_run_id_on_a_non_final_attempt_is_rejected(self):
        history = [approach("a1", FIRST_STRATEGY, [
            attempt(run=None, outcome="revise", candidate="1" * 40, review="run-review-1"), attempt()])]
        self.assertFalse(self.valid(history))
        history = [approach("a1", FIRST_STRATEGY, [attempt(run=None), attempt()])]
        self.assertFalse(self.valid(history))

    def test_null_run_id_on_a_non_final_approach_is_rejected(self):
        history = [approach("a1", FIRST_STRATEGY, [
                       attempt(run=None, outcome="pivot", candidate="1" * 40, review="run-review-1")]),
                   approach("a2", SECOND_STRATEGY, [attempt()], material_review="run-review-2")]
        self.assertFalse(self.valid(history))

    def test_null_run_id_with_a_non_pending_outcome_is_rejected(self):
        for outcome, candidate, review, retries in (
                ("blocked", None, None, 0), ("blocked", "1" * 40, "run-review-1", 0),
                ("approve", "1" * 40, "run-review-1", 0), ("revise", "1" * 40, "run-review-1", 0),
                ("infrastructure_failed", None, None, 1), ("approved", "1" * 40, "run-review-1", 0)):
            with self.subTest(outcome=outcome, candidate=candidate):
                history = [approach("a1", FIRST_STRATEGY, [
                    attempt(run=None, outcome=outcome, candidate=candidate, review=review, retries=retries)])]
                self.assertFalse(self.valid(history))
                # The same attempt with a run ID is valid, so the null run ID is the cause.
                history[0]["attempts"][0]["implementation_run_id"] = "run-worker-1"
                self.assertTrue(self.valid(history))

    def test_null_run_id_with_retries_or_candidate_or_review_is_rejected(self):
        for changes in ({"retries": 1}, {"retries": False}, {"candidate": "1" * 40},
                        {"review": "run-review-1"}, {"candidate": "1" * 40, "review": "run-review-1"}):
            with self.subTest(changes=changes):
                history = [approach("a1", FIRST_STRATEGY, [attempt(run=None, **changes)])]
                self.assertFalse(self.valid(history))

    def test_blank_or_padded_or_reused_run_ids_are_still_rejected(self):
        for run in ("", "   ", " run-worker-1", 7):
            with self.subTest(run=run):
                self.assertFalse(self.valid([approach("a1", FIRST_STRATEGY, [attempt(run=run)])]))
        reused = [approach("a1", FIRST_STRATEGY, [
            attempt(outcome="revise", candidate="1" * 40, review="run-review-1"), attempt()])]
        self.assertFalse(self.valid(reused))

    def test_uppercase_approach_id_and_wrong_hash_are_still_rejected(self):
        history = before_dispatch()
        history[0]["approach_id"] = "A1"
        self.assertFalse(self.valid(history))
        for wrong in (hashlib.sha256(b"another strategy").hexdigest(),
                      hashlib.sha256(("  " + FIRST_STRATEGY + "\n").encode()).hexdigest(),
                      strategy_digest(FIRST_STRATEGY).upper()):
            with self.subTest(wrong=wrong):
                history = before_dispatch()
                history[0]["strategy"] = "  " + FIRST_STRATEGY + "\n"
                history[0]["strategy_sha256"] = wrong
                self.assertFalse(self.valid(history))
        history = before_dispatch()
        history[0]["strategy"] = "  " + FIRST_STRATEGY.replace(" ", "\n  ") + "\n"
        self.assertTrue(self.valid(history))


class NullRunIdTransitionTests(unittest.TestCase):
    def setUp(self):
        self.verifier = load_validator()

    def transition(self, previous, current):
        return self.verifier.project_repair_transition_valid(previous, current)

    def started(self, history, run="run-worker-1"):
        current = copy(history)
        current[-1]["attempts"][-1]["implementation_run_id"] = run
        return current

    def test_null_to_string_run_id_is_a_valid_transition(self):
        self.assertTrue(self.transition(before_dispatch(), self.started(before_dispatch())))
        card = {"id": "t_synthetic_null_run", "board": "cha-pt",
                "body": "authorization_mode: autonomous\nrepair_policy: bounded-convergence-v1",
                "comments": [{"body": history_line(before_dispatch())},
                             {"body": history_line(self.started(before_dispatch()))}]}
        errors, warnings = [], []
        self.verifier.check_project_repair_cards(errors, [card], warnings)
        self.assertEqual((errors, warnings), ([], []))

    def test_null_to_string_run_id_on_appended_attempt_and_approach(self):
        revised = [approach("a1", FIRST_STRATEGY, [
            attempt(outcome="revise", candidate="1" * 40, review="run-review-1"), attempt(run=None)])]
        self.assertTrue(self.transition(revised, self.started(revised, "run-worker-2")))
        self.assertFalse(self.transition(revised, self.started(revised, "run-worker-1")))
        pivoted = [approach("a1", FIRST_STRATEGY, [
                       attempt(outcome="pivot", candidate="1" * 40, review="run-review-1")]),
                   approach("a2", SECOND_STRATEGY, [attempt(run=None)], material_review="run-review-2")]
        self.assertTrue(self.transition(pivoted, self.started(pivoted, "run-worker-2")))

    def test_any_other_field_change_in_the_same_step_is_rejected(self):
        base = [approach("a1", FIRST_STRATEGY, [
                    attempt(outcome="pivot", candidate="1" * 40, review="run-review-1")]),
                approach("a2", SECOND_STRATEGY, [attempt(run=None)], material_review="run-review-2")]
        self.assertTrue(self.transition(base, self.started(base, "run-worker-2")))

        def changed(mutate):
            current = self.started(base, "run-worker-2")
            mutate(current)
            return current

        mutations = {
            "outcome revise": lambda h: h[1]["attempts"][0].update(
                outcome="revise", candidate_commit="2" * 40, review_run_id="run-review-3"),
            "outcome approve": lambda h: h[1]["attempts"][0].update(
                outcome="approve", candidate_commit="2" * 40, review_run_id="run-review-3"),
            "outcome blocked": lambda h: h[1]["attempts"][0].update(outcome="blocked"),
            "outcome infrastructure_failed": lambda h: h[1]["attempts"][0].update(
                outcome="infrastructure_failed", infrastructure_retries=1),
            "infrastructure retry": lambda h: h[1]["attempts"][0].update(infrastructure_retries=1),
            "approach id": lambda h: h[1].update(approach_id="a3"),
            "strategy": lambda h: h[1].update(strategy="Persist the attempt counter in a new table",
                                              strategy_sha256=strategy_digest(
                                                  "Persist the attempt counter in a new table")),
            "material review": lambda h: h[1].update(material_difference_review_run_id="run-review-4"),
            "earlier approach": lambda h: h[0].update(approach_id="a0"),
            "appended attempt": lambda h: h[1]["attempts"].append(attempt(run=None)),
        }
        for name, mutate in mutations.items():
            with self.subTest(change=name):
                self.assertFalse(self.transition(base, changed(mutate)))

    def test_null_run_id_never_moves_directly_to_another_outcome(self):
        for outcome, fields in (("blocked", {}), ("approve", {"candidate_commit": "2" * 40,
                                                              "review_run_id": "run-review-3"}),
                                ("revise", {"candidate_commit": "2" * 40, "review_run_id": "run-review-3"}),
                                ("pivot", {"candidate_commit": "2" * 40, "review_run_id": "run-review-3"})):
            with self.subTest(outcome=outcome):
                current = copy(before_dispatch())
                current[0]["attempts"][0].update(outcome=outcome, **fields)
                self.assertFalse(self.transition(before_dispatch(), current))
                current[0]["attempts"][0]["implementation_run_id"] = "run-worker-1"
                self.assertFalse(self.transition(before_dispatch(), current))

    def test_infrastructure_retry_still_needs_two_different_non_null_run_ids(self):
        retried = copy(before_dispatch())
        retried[0]["attempts"][0].update(implementation_run_id="run-worker-retry", infrastructure_retries=1)
        self.assertFalse(self.transition(before_dispatch(), retried))
        started = self.started(before_dispatch())
        self.assertTrue(self.transition(started, retried))
        same_run = copy(retried)
        same_run[0]["attempts"][0]["implementation_run_id"] = "run-worker-1"
        self.assertFalse(self.transition(started, same_run))

    def test_run_id_cannot_return_to_null_or_be_rewritten(self):
        started = self.started(before_dispatch())
        self.assertFalse(self.transition(started, before_dispatch()))
        self.assertFalse(self.transition(started, self.started(before_dispatch(), "run-worker-other")))
        self.assertFalse(self.transition(before_dispatch(), before_dispatch()))


def tracked_files(*prefixes):
    listed = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--", *prefixes],
                            capture_output=True, check=True)
    return [name for name in listed.stdout.decode().split("\0") if name]


class InstructionTextTests(unittest.TestCase):
    def setUp(self):
        self.verifier = load_validator()
        # The later repair_history candidate rule change (t_6436ac1c) inserts three bullet
        # points into FORMAT_RULES and adds a second example line in the six skill files;
        # tests/test_repair_history_candidate_rules_policy.py checks that change, and it is
        # reversed here so these checks keep reading the text this card wrote.
        self.text = {path: reverse_candidate_rule_edits(path, (ROOT / path).read_text())
                     for path in SKILL_FILES + POLICY_FILES}

    def example_lines(self, path):
        return [line for line in self.text[path].splitlines() if line.startswith("repair_history: ")]

    def test_each_example_snapshot_parses_validates_and_its_hash_recomputes(self):
        for path in SKILL_FILES + POLICY_FILES:
            with self.subTest(path=path):
                lines = self.example_lines(path)
                self.assertEqual(lines, [EXAMPLE_LINE])
                history = json.loads(lines[0][len("repair_history: "):])
                self.assertTrue(self.verifier.valid_project_repair_history(history))
                self.assertTrue(self.verifier.REPAIR_HISTORY_LINE.fullmatch(lines[0]))
                self.assertIsNone(history[0]["attempts"][0]["implementation_run_id"])
                self.assertEqual(history[0]["strategy_sha256"], strategy_digest(history[0]["strategy"]))

    def test_documented_hash_command_computes_the_example_hash(self):
        match = re.fullmatch(r"python3 -I -c '([^']+)' \"<strategy text>\"", HASH_COMMAND)
        self.assertIsNotNone(match)
        result = subprocess.run([sys.executable, "-I", "-c", match.group(1), "  " + EXAMPLE_STRATEGY + "\n"],
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), EXAMPLE_STRATEGY_SHA256)

    def test_format_rules_appear_once_in_each_instruction_file(self):
        for path in SKILL_FILES + POLICY_FILES:
            with self.subTest(path=path):
                self.assertEqual(self.text[path].count(FORMAT_RULES), 1)
                self.assertEqual(self.text[path].count("`" + HASH_COMMAND + "`"), 1)

    def test_each_skill_names_the_exact_repository_line_for_its_fleet(self):
        allowlists = self.verifier.PROJECT_REPOSITORY_ALLOWLISTS
        for path, boards in SKILL_BOARDS.items():
            for board in boards:
                for repository in allowlists[board]:
                    with self.subTest(path=path, repository=repository):
                        self.assertIn(repository_line(repository), self.text[path])
            with self.subTest(path=path, rule="no other wording"):
                self.assertIn("accepts no other repository wording", self.text[path])
                self.assertIn("`Repository <exact repository path> ONLY.`", self.text[path])

    def test_no_tracked_skill_or_policy_file_uses_another_repository_wording(self):
        files = tracked_files("skills", "policies")
        self.assertIn(SHARED, files)
        for name in files:
            data = (ROOT / name).read_bytes()
            with self.subTest(path=name):
                self.assertNotIn(b"Repository EXACT", data)

    def test_reversing_the_edits_recovers_the_baseline_bytes(self):
        for path, want in PRE_REPAIR_FORMAT_SHA256.items():
            with self.subTest(path=path):
                # Reverse the later repair_history candidate rule change (t_6436ac1c) and the
                # owner shell command path change (t_bd860536) first.
                current = reverse_candidate_rule_edits(path, (ROOT / path).read_bytes())
                current = reverse_owner_path_edits(path, current)
                original = reverse_repair_format_edits(path, current)
                self.assertEqual(hashlib.sha256(original).hexdigest(), want)


class ToleranceBehaviourTests(unittest.TestCase):
    def test_tolerance_test_is_unmodified_and_passes(self):
        path = ROOT / TOLERANCE_TEST
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), TOLERANCE_TEST_SHA256)
        result = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-2000:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
