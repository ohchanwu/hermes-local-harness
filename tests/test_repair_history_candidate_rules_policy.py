#!/usr/bin/env python3
"""repair_history candidate commit, review run ID and outcome rules in the
orchestrator skills (t_6436ac1c).

Offline checks of tracked bytes and of the scripts/verify-state validator only:
no live ~/.hermes reads, board access, network or model calls. All histories,
commit IDs and run IDs are synthetic.

The six orchestrator skills state three more rules that scripts/verify-state
already enforces in valid_project_repair_history: candidate_commit and
review_run_id stay null until the review outcome is recorded, a candidate_commit
is a full 40-character lowercase hexadecimal commit ID, and outcome is one of
REPAIR_OUTCOMES (with the REPAIR_OUTCOME_ALIASES alias). A second example line
shows the history after the first review requested changes.

CANDIDATE_RULE_EDITS lists the exact (new, old) text this card changed in each
skill file, so tests that pin older bytes of these files can reverse the change
byte for byte with reverse_candidate_rule_edits(). This module imports no other
test module, so any test module can import it.
"""
import hashlib
import importlib.util
import io
import json
import re
import unittest
from contextlib import redirect_stdout
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = "autonomous-ai-agents/multi-agent-coding-orchestrator/SKILL.md"
SHARED = "skills/multi-agent-coding-orchestrator/SKILL.md"
HARNESS = f"policies/profile-skills/harness-orchestrator/{RELATIVE}"
JOBCRON = f"policies/profile-skills/jobcron-orchestrator/{RELATIVE}"
CHAPT = f"policies/profile-skills/chapt-orchestrator/{RELATIVE}"
JSS = f"policies/profile-skills/jss-orchestrator/{RELATIVE}"
ANKI = f"policies/profile-skills/anki-orchestrator/{RELATIVE}"
SKILL_FILES = (SHARED, HARNESS, JOBCRON, CHAPT, JSS, ANKI)
SNAPSHOT = "snapshots/sanitized-current-state.yaml"

# File -> (new version, old version).
VERSIONS = {
    SHARED: ("0.6.13", "0.6.12"),
    HARNESS: ("0.6.7-harness.6", "0.6.7-harness.5"),
    JOBCRON: ("0.6.9-jobcron.7", "0.6.9-jobcron.6"),
    CHAPT: ("0.6.7-chapt.7", "0.6.7-chapt.6"),
    JSS: ("0.6.7-jss.8", "0.6.7-jss.7"),
    ANKI: ("0.6.10-anki.4", "0.6.10-anki.3"),
}

# Bytes of each file at baseline a15aa824c10146686d1d7e473c0798717ffa2326,
# recovered by reversing CANDIDATE_RULE_EDITS.
PRE_CANDIDATE_RULE_SHA256 = {
    SHARED: "ffcf50bbc41ba8cf2902f41a6f2c233b11a7601f837dbb2c54a796cc723c016f",
    HARNESS: "53e58db39a80e56afaadfa862d056370bf1664ecfe41bcf79e837ff9e160e3bd",
    JOBCRON: "9bb48a0be64da790e134a5e620bd84adef1e1b37ad6a255df6ca50808d444cee",
    CHAPT: "d15c27510ceeaf9ccc4e72081ff0d4c310d44ca015e25111fb084901f0e1328f",
    JSS: "9c10b023e1ef50c291f248e276eb637c1e7600a2bb95eac6345e90385733e90f",
    ANKI: "15d0dec13bb7d1172f6d78012bbecf3843df2ec3036b777b493ec6673d72c575",
}

LIST_START = "Exact `repair_history` formats. `scripts/verify-state` rejects a snapshot that does not follow them:\n"
LAST_EXISTING_BULLET_END = "A pending attempt with a null run ID never changes directly to another outcome.\n"
PRE_DISPATCH_INTRO = "Complete example of a valid snapshot line before the first dispatch:\n"
PRE_DISPATCH_LINE = (
    'repair_history: [{"approach_id":"a1","strategy":"Add a bounded retry limit to the export job and '
    'cover the limit with one unit test","strategy_sha256":'
    '"95a031c63f8d9676ebce8a6628f6c9681318ef99b653ca6619e1ff9a941aa934",'
    '"material_difference_review_run_id":null,"attempts":[{"candidate_commit":null,'
    '"implementation_run_id":null,"review_run_id":null,"infrastructure_retries":0,'
    '"outcome":"pending"}]}]'
)

CANDIDATE_BULLET = (
    "- `candidate_commit` and `review_run_id` stay null until the snapshot that records the review outcome "
    "of the attempt. While an attempt has `outcome: \"pending\"` or `outcome: \"infrastructure_failed\"`, "
    "both are null, even after the worker has committed a candidate. Record the candidate commit and the "
    "review run ID in the same successor snapshot that changes the outcome from `pending` to the review "
    "outcome. With `outcome: \"blocked\"`, both are null or both are set. With `outcome: \"revise\"`, "
    "`outcome: \"pivot\"` or `outcome: \"approve\"`, both are set. A set `review_run_id` is a non-empty "
    "string without leading or trailing whitespace. A `candidate_commit` value is never used by more than "
    "one attempt, and a `review_run_id` value is never used by more than one attempt or by any "
    "`material_difference_review_run_id` in the same history.\n"
)
COMMIT_BULLET = (
    "- A non-null `candidate_commit` is the full 40-character lowercase hexadecimal commit ID. Get it with "
    "`git rev-parse <commit>`. An abbreviated commit ID such as `abc1234`, or a commit ID with uppercase "
    "letters, is rejected.\n"
)
OUTCOME_BULLET = (
    "- `outcome` is exactly one of `pending`, `revise`, `pivot`, `approve`, `blocked` or "
    "`infrastructure_failed`. The value `approved` is accepted as an alias of `approve`. Any other value, "
    "such as `changes_requested`, is rejected. Record a reviewer change request as `revise` when the work "
    "continues with the same approach, and as `pivot` when the work continues with a materially different "
    "approach. A `revise` on the third attempt of an approach exhausts that approach, and `pivot` is "
    "rejected on the third approach.\n"
)
NEW_BULLETS = CANDIDATE_BULLET + COMMIT_BULLET + OUTCOME_BULLET

SYNTHETIC_CANDIDATE = "0123456789abcdef0123456789abcdef01234567"
SYNTHETIC_RUN = "run-worker-1"
SYNTHETIC_REVIEW = "run-review-1"
REVISE_INTRO = (
    f"Complete example of the same history after the dispatched run `{SYNTHETIC_RUN}` committed a candidate "
    f"and the first review, run `{SYNTHETIC_REVIEW}`, requested changes on the same approach:\n"
)
REVISE_LINE = PRE_DISPATCH_LINE.replace(
    '"attempts":[{"candidate_commit":null,"implementation_run_id":null,"review_run_id":null,'
    '"infrastructure_retries":0,"outcome":"pending"}]',
    f'"attempts":[{{"candidate_commit":"{SYNTHETIC_CANDIDATE}","implementation_run_id":"{SYNTHETIC_RUN}",'
    f'"review_run_id":"{SYNTHETIC_REVIEW}","infrastructure_retries":0,"outcome":"revise"}}]')

OLD_BLOCK = (LAST_EXISTING_BULLET_END + "\n" + PRE_DISPATCH_INTRO + "\n```text\n" + PRE_DISPATCH_LINE
             + "\n```\n")
NEW_BLOCK = (LAST_EXISTING_BULLET_END + NEW_BULLETS + "\n" + PRE_DISPATCH_INTRO + "\n```text\n"
             + PRE_DISPATCH_LINE + "\n```\n\n" + REVISE_INTRO + "\n```text\n" + REVISE_LINE + "\n```\n")


def _version(new, old):
    return (f"version: {new}\n", f"version: {old}\n")


# File -> ((new text, old text), ...). Each new text occurs exactly once.
CANDIDATE_RULE_EDITS = {path: (_version(*VERSIONS[path]), (NEW_BLOCK, OLD_BLOCK)) for path in SKILL_FILES}


def reverse_candidate_rule_edits(relative_path, text):
    """Return text with this card's edits reversed; text may be str or bytes."""
    as_bytes = isinstance(text, bytes)
    if as_bytes:
        text = text.decode()
    for new, old in CANDIDATE_RULE_EDITS.get(relative_path, ()):
        if text.count(new) != 1:
            raise AssertionError(f"{relative_path}: expected one occurrence of {new[:60]!r}")
        text = text.replace(new, old, 1)
    return text.encode() if as_bytes else text


def load_validator():
    source = ROOT / "scripts/verify-state"
    loader = SourceFileLoader("verify_state_candidate_rules", str(source))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def parse_line(line):
    return json.loads(line[len("repair_history: "):])


def history_line(history):
    return "repair_history: " + json.dumps(history, separators=(",", ":"))


def started_history():
    """The successor of the pre-dispatch example: the run ID is set and nothing else changes."""
    history = parse_line(PRE_DISPATCH_LINE)
    history[0]["attempts"][0]["implementation_run_id"] = SYNTHETIC_RUN
    return history


def card(comments):
    return {"id": "t_synthetic_candidate_rules", "board": "harness",
            "body": "authorization_mode: autonomous\nrepair_policy: bounded-convergence-v1",
            "comments": [{"body": comment} for comment in comments]}


class InstructionText(unittest.TestCase):
    def setUp(self):
        self.verifier = load_validator()
        self.text = {path: (ROOT / path).read_text() for path in SKILL_FILES}

    def format_list(self, path):
        text = self.text[path]
        self.assertEqual(text.count(LIST_START), 1)
        start = text.index(LIST_START)
        return text[start:text.index(PRE_DISPATCH_INTRO, start)]

    def test_new_bullets_are_in_the_format_list_of_each_file(self):
        for path in SKILL_FILES:
            with self.subTest(path=path):
                self.assertEqual(self.text[path].count(NEW_BULLETS), 1)
                self.assertEqual(self.text[path].count(NEW_BLOCK), 1)
                self.assertIn(LAST_EXISTING_BULLET_END + NEW_BULLETS + "\n", self.format_list(path))

    def test_format_list_is_byte_identical_in_the_six_files(self):
        lists = {path: self.format_list(path) for path in SKILL_FILES}
        self.assertEqual(len(set(lists.values())), 1, sorted(lists))

    def test_new_text_is_ascii_and_uses_no_coined_compound(self):
        for text in (NEW_BULLETS, REVISE_INTRO, REVISE_LINE):
            text.encode("ascii")
            self.assertIsNone(re.search(r"[Vv]alue-blind", text))

    def test_outcome_list_equals_the_verifier_outcomes_and_alias(self):
        sentence = OUTCOME_BULLET.split(". ", 1)[0]
        listed = re.findall(r"`([a-z_]+)`", sentence)
        self.assertEqual(listed[0], "outcome")
        self.assertEqual(len(listed[1:]), len(set(listed[1:])))
        self.assertEqual(set(listed[1:]), self.verifier.REPAIR_OUTCOMES)
        aliases = dict(re.findall(r"`([a-z_]+)` is accepted as an alias of `([a-z_]+)`", OUTCOME_BULLET))
        self.assertEqual(aliases, self.verifier.REPAIR_OUTCOME_ALIASES)
        for path in SKILL_FILES:
            with self.subTest(path=path):
                self.assertIn(OUTCOME_BULLET, self.format_list(path))

    def test_example_lines_in_each_file(self):
        for path in SKILL_FILES:
            with self.subTest(path=path):
                lines = [line for line in self.text[path].splitlines() if line.startswith("repair_history: ")]
                self.assertEqual(lines, [PRE_DISPATCH_LINE, REVISE_LINE])

    def test_versions_are_bumped_and_the_snapshot_agrees(self):
        for path, (new, _old) in VERSIONS.items():
            with self.subTest(path=path):
                self.assertEqual(re.findall(r"(?m)^version: (.+)$", self.text[path]), [new])
        snapshot = json.loads((ROOT / SNAPSHOT).read_text())
        shared = next(entry for entry in snapshot["skill"]["shared_skills"]
                      if entry["name"] == "multi-agent-coding-orchestrator")
        self.assertEqual(shared["version"], VERSIONS[SHARED][0])
        self.assertEqual(shared["source"], "skills/multi-agent-coding-orchestrator")

    def test_reversing_the_edits_recovers_the_baseline_bytes(self):
        for path, want in PRE_CANDIDATE_RULE_SHA256.items():
            with self.subTest(path=path):
                original = reverse_candidate_rule_edits(path, (ROOT / path).read_bytes())
                self.assertEqual(hashlib.sha256(original).hexdigest(), want)


class ExampleValidity(unittest.TestCase):
    def setUp(self):
        self.verifier = load_validator()

    def test_revise_example_parses_and_is_valid(self):
        self.assertTrue(self.verifier.REPAIR_HISTORY_LINE.fullmatch(REVISE_LINE))
        history = parse_line(REVISE_LINE)
        self.assertTrue(self.verifier.valid_project_repair_history(history))
        attempt = history[0]["attempts"][0]
        self.assertEqual((attempt["candidate_commit"], attempt["implementation_run_id"],
                          attempt["review_run_id"], attempt["outcome"]),
                         (SYNTHETIC_CANDIDATE, SYNTHETIC_RUN, SYNTHETIC_REVIEW, "revise"))
        self.assertTrue(self.verifier.REPAIR_COMMIT.fullmatch(SYNTHETIC_CANDIDATE))

    def test_revise_example_is_a_valid_successor_of_the_started_example(self):
        self.assertTrue(self.verifier.valid_project_repair_history(started_history()))
        self.assertTrue(self.verifier.project_repair_transition_valid(
            parse_line(PRE_DISPATCH_LINE), started_history()))
        self.assertTrue(self.verifier.project_repair_transition_valid(started_history(), parse_line(REVISE_LINE)))
        # The pre-dispatch example never changes directly to the review outcome.
        self.assertFalse(self.verifier.project_repair_transition_valid(
            parse_line(PRE_DISPATCH_LINE), parse_line(REVISE_LINE)))

    def test_three_snapshot_card_passes_check_project_repair_cards(self):
        errors, warnings = [], []
        self.verifier.check_project_repair_cards(
            errors, [card([PRE_DISPATCH_LINE, history_line(started_history()), REVISE_LINE])], warnings)
        self.assertEqual((errors, warnings), ([], []))


class StatedRulesMatchTheVerifier(unittest.TestCase):
    def setUp(self):
        self.verifier = load_validator()

    def valid(self, history):
        return self.verifier.valid_project_repair_history(history)

    def with_attempt(self, **fields):
        history = started_history()
        history[0]["attempts"][0].update(fields)
        return history

    def assert_card_fails(self, history):
        errors, warnings = [], []
        with redirect_stdout(io.StringIO()):
            self.verifier.check_project_repair_cards(
                errors, [card([PRE_DISPATCH_LINE, history_line(started_history()), history_line(history)])],
                warnings)
        self.assertEqual(errors, ["project repair contract drift t_synthetic_candidate_rules: "
                                  "invalid repair history"])

    def test_pending_or_infrastructure_failed_attempt_with_candidate_or_review_is_rejected(self):
        for outcome, retries in (("pending", 0), ("infrastructure_failed", 1)):
            self.assertTrue(self.valid(self.with_attempt(outcome=outcome, infrastructure_retries=retries)))
            for fields in ({"candidate_commit": SYNTHETIC_CANDIDATE}, {"review_run_id": SYNTHETIC_REVIEW},
                           {"candidate_commit": SYNTHETIC_CANDIDATE, "review_run_id": SYNTHETIC_REVIEW}):
                with self.subTest(outcome=outcome, fields=fields):
                    history = self.with_attempt(outcome=outcome, infrastructure_retries=retries, **fields)
                    self.assertFalse(self.valid(history))
        self.assert_card_fails(self.with_attempt(candidate_commit=SYNTHETIC_CANDIDATE))

    def test_blocked_needs_both_null_or_both_set(self):
        self.assertTrue(self.valid(self.with_attempt(outcome="blocked")))
        self.assertTrue(self.valid(self.with_attempt(
            outcome="blocked", candidate_commit=SYNTHETIC_CANDIDATE, review_run_id=SYNTHETIC_REVIEW)))
        self.assertFalse(self.valid(self.with_attempt(outcome="blocked", candidate_commit=SYNTHETIC_CANDIDATE)))
        self.assertFalse(self.valid(self.with_attempt(outcome="blocked", review_run_id=SYNTHETIC_REVIEW)))

    def test_revise_pivot_and_approve_need_both_set(self):
        for outcome in ("revise", "pivot", "approve"):
            with self.subTest(outcome=outcome):
                self.assertTrue(self.valid(self.with_attempt(
                    outcome=outcome, candidate_commit=SYNTHETIC_CANDIDATE, review_run_id=SYNTHETIC_REVIEW)))
                self.assertFalse(self.valid(self.with_attempt(outcome=outcome)))
                self.assertFalse(self.valid(self.with_attempt(outcome=outcome,
                                                              candidate_commit=SYNTHETIC_CANDIDATE)))
                self.assertFalse(self.valid(self.with_attempt(outcome=outcome, review_run_id=SYNTHETIC_REVIEW)))
                for review in ("", "   ", " " + SYNTHETIC_REVIEW):
                    self.assertFalse(self.valid(self.with_attempt(
                        outcome=outcome, candidate_commit=SYNTHETIC_CANDIDATE, review_run_id=review)))

    def test_candidate_and_review_values_are_never_reused(self):
        strategy = "Replace the export retry with a persisted attempt counter"
        first = {"candidate_commit": SYNTHETIC_CANDIDATE, "implementation_run_id": SYNTHETIC_RUN,
                 "review_run_id": SYNTHETIC_REVIEW, "infrastructure_retries": 0, "outcome": "revise"}
        second = dict(first, candidate_commit="f" * 40, implementation_run_id="run-worker-2",
                      review_run_id="run-review-2")
        history = parse_line(REVISE_LINE)
        history[0]["attempts"].append(second)
        self.assertTrue(self.valid(history))
        for field in ("candidate_commit", "review_run_id"):
            with self.subTest(field=field):
                reused = parse_line(REVISE_LINE)
                reused[0]["attempts"].append(dict(second, **{field: first[field]}))
                self.assertFalse(self.valid(reused))
        pivoted = parse_line(REVISE_LINE)
        pivoted[0]["attempts"][0]["outcome"] = "pivot"
        pivoted.append({"approach_id": "a2", "strategy": strategy,
                        "strategy_sha256": hashlib.sha256(strategy.encode()).hexdigest(),
                        "material_difference_review_run_id": "run-review-2",
                        "attempts": [dict(second, outcome="pending", candidate_commit=None, review_run_id=None)]})
        self.assertTrue(self.valid(pivoted))
        pivoted[1]["material_difference_review_run_id"] = SYNTHETIC_REVIEW
        self.assertFalse(self.valid(pivoted))

    def test_abbreviated_or_uppercase_commit_id_is_rejected(self):
        for candidate in ("0123456", SYNTHETIC_CANDIDATE[:39], SYNTHETIC_CANDIDATE.upper(),
                          SYNTHETIC_CANDIDATE + "0", "g" * 40):
            with self.subTest(candidate=candidate):
                self.assertFalse(self.valid(self.with_attempt(
                    outcome="revise", candidate_commit=candidate, review_run_id=SYNTHETIC_REVIEW)))
        self.assert_card_fails(self.with_attempt(
            outcome="revise", candidate_commit="0123456", review_run_id=SYNTHETIC_REVIEW))

    def test_outcome_values_outside_the_list_are_rejected(self):
        for outcome in ("changes_requested", "request_changes", "approve ", "Revise", "rejected"):
            with self.subTest(outcome=outcome):
                self.assertFalse(self.valid(self.with_attempt(
                    outcome=outcome, candidate_commit=SYNTHETIC_CANDIDATE, review_run_id=SYNTHETIC_REVIEW)))
        self.assert_card_fails(self.with_attempt(
            outcome="changes_requested", candidate_commit=SYNTHETIC_CANDIDATE, review_run_id=SYNTHETIC_REVIEW))
        self.assertTrue(self.valid(self.with_attempt(
            outcome="approved", candidate_commit=SYNTHETIC_CANDIDATE, review_run_id=SYNTHETIC_REVIEW)))

    def test_revise_on_a_third_attempt_exhausts_and_pivot_on_a_third_approach_is_rejected(self):
        verifier = self.verifier
        self.assertEqual(verifier.PROJECT_REPAIR_POLICY["max_attempts_per_approach"], 3)
        self.assertEqual(verifier.PROJECT_REPAIR_POLICY["max_approaches"], 3)

        def attempt(index, outcome):
            return {"candidate_commit": f"{index:040x}", "implementation_run_id": f"run-worker-{index}",
                    "review_run_id": f"run-review-{index}", "infrastructure_retries": 0, "outcome": outcome}

        def approach(number, attempts, material_review):
            strategy = f"Synthetic strategy number {number} for the export retry limit"
            return {"approach_id": f"a{number}", "strategy": strategy,
                    "strategy_sha256": hashlib.sha256(strategy.encode()).hexdigest(),
                    "material_difference_review_run_id": material_review, "attempts": attempts}

        exhausted = [approach(1, [attempt(1, "revise"), attempt(2, "revise"), attempt(3, "revise")], None)]
        self.assertTrue(verifier.valid_project_repair_history(exhausted))
        appended = exhausted + [approach(2, [{"candidate_commit": None, "implementation_run_id": None,
                                              "review_run_id": None, "infrastructure_retries": 0,
                                              "outcome": "pending"}], "run-review-material-2")]
        self.assertTrue(verifier.project_repair_transition_valid(exhausted, appended))
        third = [approach(1, [attempt(1, "pivot")], None),
                 approach(2, [attempt(2, "pivot")], "run-review-material-2"),
                 approach(3, [attempt(3, "revise")], "run-review-material-3")]
        self.assertTrue(verifier.valid_project_repair_history(third))
        third[2]["attempts"][0]["outcome"] = "pivot"
        self.assertFalse(verifier.valid_project_repair_history(third))


if __name__ == "__main__":
    unittest.main(verbosity=2)
