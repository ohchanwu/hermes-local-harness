#!/usr/bin/env python3
"""Repair-history tolerance tests for scripts/verify-state and check-repair-history.

Loads the validator via importlib SourceFileLoader (never live mode). Covers the
261017 incident shapes: outcome alias acceptance, append-only correction of a
superseded malformed snapshot, trailing-malformed failure, no-reset enforcement,
and the pure checker CLI exit codes.
"""
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/check-repair-history"
sys.path.insert(0, str(ROOT / "tests"))


def load_validator():
    source = ROOT / "scripts/verify-state"
    loader = SourceFileLoader("verify_state_tolerance", str(source))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module

REPAIR_CARD_BODY = "authorization_mode: autonomous\nrepair_policy: bounded-convergence-v1"


def make_history(outcome="pending", retries=0, candidate=None, review=None):
    strategy = "Use transaction fencing around the retry clock"
    return [{
        "approach_id": "transaction-fence",
        "strategy": strategy,
        "strategy_sha256": hashlib.sha256(strategy.encode()).hexdigest(),
        "material_difference_review_run_id": None,
        "attempts": [{
            "candidate_commit": candidate,
            "implementation_run_id": "run-worker-1",
            "review_run_id": review,
            "infrastructure_retries": retries,
            "outcome": outcome,
        }],
    }]


def history_line(history):
    return f"repair_history: {json.dumps(history, separators=(',', ':'))}"


def run_checker(args, stdin_text=None):
    return subprocess.run([sys.executable, str(CHECKER), *args], input=stdin_text,
                          text=True, capture_output=True)


def check_cards(verifier, cards):
    errors, warnings = [], []
    output = io.StringIO()
    with redirect_stdout(output):
        verifier.check_project_repair_cards(errors, cards, warnings)
    return errors, warnings, output.getvalue()


class AliasToleranceTests(unittest.TestCase):
    def setUp(self):
        self.verifier = load_validator()

    def test_valid_pending_to_approved_final_passes(self):
        pending = make_history()
        completed = make_history(outcome="approved", candidate="2" * 40, review="run-review-1")
        card = {"id": "t_alias", "board": "jobcron", "body": REPAIR_CARD_BODY,
                "comments": [{"body": history_line(pending)},
                             {"body": history_line(completed)}]}
        errors, warnings, _ = check_cards(self.verifier, [card])
        self.assertEqual(errors, [], errors)
        self.assertEqual(warnings, [], warnings)

    def test_outcome_alias_normalized_in_valid_history(self):
        aliased = make_history(outcome="approved", candidate="2" * 40, review="run-review-1")
        self.assertTrue(self.verifier.valid_project_repair_history(aliased))
        self.assertFalse(self.verifier.valid_project_repair_history(
            make_history(outcome="greenlit")))

    def test_alias_map_is_exactly_the_single_entry(self):
        self.assertEqual(self.verifier.REPAIR_OUTCOME_ALIASES, {"approved": "approve"})

    def test_unknown_outcome_still_rejected(self):
        self.assertFalse(self.verifier.valid_project_repair_history(make_history(outcome="accepted")))
        self.assertFalse(self.verifier.valid_project_repair_history(make_history(outcome="APPROVE")))


class AppendOnlyCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.verifier = load_validator()

    def test_valid_malformed_corrected_chain_passes_with_warning(self):
        pending = make_history()
        malformed = make_history(outcome="approved", candidate=None, review="run-review-1")
        corrected = make_history(outcome="approve", candidate="2" * 40, review="run-review-1")
        card = {"id": "t_corr", "board": "jobcron", "body": REPAIR_CARD_BODY,
                "comments": [{"body": history_line(pending)},
                             {"body": history_line(malformed)},
                             {"body": history_line(corrected)}]}
        errors, warnings, _ = check_cards(self.verifier, [card])
        self.assertEqual(errors, [], errors)
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("skipped malformed repair history snapshot #2", warnings[0])

    def test_trailing_malformed_without_successor_fails(self):
        pending = make_history()
        malformed = make_history(outcome="zzz", candidate="2" * 40, review="run-review-1")
        card = {"id": "t_trail", "board": "jobcron", "body": REPAIR_CARD_BODY,
                "comments": [{"body": history_line(pending)},
                             {"body": history_line(malformed)}]}
        errors, warnings, _ = check_cards(self.verifier, [card])
        self.assertEqual(errors, ["project repair contract drift t_trail: invalid repair history"])
        self.assertEqual(warnings, [], warnings)

    def test_unparseable_line_superseded_by_valid_snapshot_warns(self):
        pending = make_history()
        corrected = make_history(outcome="approve", candidate="2" * 40, review="run-review-1")
        card = {"id": "t_json", "board": "jobcron", "body": REPAIR_CARD_BODY,
                "comments": [{"body": history_line(pending)},
                             {"body": "repair_history: [not json"},
                             {"body": history_line(corrected)}]}
        errors, warnings, _ = check_cards(self.verifier, [card])
        self.assertEqual(errors, [], errors)
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("snapshot #2", warnings[0])

    def test_first_snapshot_rules_still_apply_to_first_valid(self):
        # First valid snapshot must be single-approach single-pending-retry-0.
        first_invalid_shape = make_history(outcome="revise", candidate="3" * 40, review="run-review-9")
        card = {"id": "t_first", "board": "jobcron", "body": REPAIR_CARD_BODY,
                "comments": [{"body": "repair_history: [not json"},
                             {"body": history_line(first_invalid_shape)}]}
        errors, _, _ = check_cards(self.verifier, [card])
        self.assertEqual(errors, ["project repair contract drift t_first: invalid repair history"])

    def test_correction_that_resets_counters_fails(self):
        pending = make_history()
        reset = make_history(outcome="pending", retries=0)
        reset[0]["approach_id"] = "fresh-reset"
        strategy = "Rename the old idea and reset its counters"
        reset[0]["strategy"] = strategy
        reset[0]["strategy_sha256"] = hashlib.sha256(strategy.encode()).hexdigest()
        card = {"id": "t_reset", "board": "jobcron", "body": REPAIR_CARD_BODY,
                "comments": [{"body": history_line(pending)},
                             {"body": history_line(reset)}]}
        errors, _, _ = check_cards(self.verifier, [card])
        self.assertEqual(errors, ["project repair contract drift t_reset: invalid repair history"])

    def test_correction_that_drops_prior_attempt_fails(self):
        pending = make_history()
        first_completed = make_history(outcome="revise", candidate="2" * 40, review="run-review-1")
        second_pending = json.loads(json.dumps(first_completed))
        second_pending[0]["attempts"].append({
            "candidate_commit": None, "implementation_run_id": "run-worker-2",
            "review_run_id": None, "infrastructure_retries": 0, "outcome": "pending"})
        dropped = json.loads(json.dumps(second_pending))
        dropped[0]["attempts"] = dropped[0]["attempts"][:1]
        dropped[0]["attempts"][0]["outcome"] = "approve"
        card = {"id": "t_drop", "board": "jobcron", "body": REPAIR_CARD_BODY,
                "comments": [{"body": history_line(pending)},
                             {"body": history_line(first_completed)},
                             {"body": history_line(second_pending)},
                             {"body": history_line(dropped)}]}
        errors, warnings, _ = check_cards(self.verifier, [card])
        self.assertEqual(errors, ["project repair contract drift t_drop: invalid repair history"])
        self.assertEqual(warnings, [], warnings)

    def test_correction_that_changes_candidate_identity_fails(self):
        pending = make_history()
        corrected_a = make_history(outcome="approve", candidate="2" * 40, review="run-review-1")
        corrected_b = make_history(outcome="approve", candidate="3" * 40, review="run-review-1")
        card = {"id": "t_ident", "board": "jobcron", "body": REPAIR_CARD_BODY,
                "comments": [{"body": history_line(pending)},
                             {"body": history_line(corrected_a)},
                             {"body": history_line(corrected_b)}]}
        errors, _, _ = check_cards(self.verifier, [card])
        self.assertEqual(errors, ["project repair contract drift t_ident: invalid repair history"])

    def test_identical_duplicate_snapshot_still_fails(self):
        pending = make_history()
        card = {"id": "t_dup", "board": "jobcron", "body": REPAIR_CARD_BODY,
                "comments": [{"body": history_line(pending)},
                             {"body": history_line(pending)}]}
        errors, _, _ = check_cards(self.verifier, [card])
        self.assertEqual(errors, ["project repair contract drift t_dup: invalid repair history"])

    def test_backward_compat_two_arg_call(self):
        pending = make_history()
        card = {"id": "t_compat", "board": "jobcron", "body": REPAIR_CARD_BODY,
                "comments": [{"body": history_line(pending)}]}
        errors = []
        output = io.StringIO()
        with redirect_stdout(output):
            self.verifier.check_project_repair_cards(errors, [card])
        self.assertEqual(errors, [], errors)


class CheckerCliTests(unittest.TestCase):
    def test_checker_exit_zero_for_valid_snapshot(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(make_history(), handle)
            path = handle.name
        result = run_checker([path])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK: valid repair history", result.stdout)

    def test_checker_exit_zero_for_valid_successor(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as previous, \
                tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as proposed:
            json.dump(make_history(), previous)
            json.dump(make_history(outcome="approved", candidate="2" * 40,
                                   review="run-review-1"), proposed)
            previous_path, proposed_path = previous.name, proposed.name
        result = run_checker([proposed_path, "--previous", previous_path])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("valid successor", result.stdout)

    def test_checker_exit_one_for_invalid_snapshot(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(make_history(outcome="accepted"), handle)
            path = handle.name
        result = run_checker([path])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("not a valid repair history", result.stdout)
        self.assertEqual(len(result.stdout.strip().splitlines()), 1)

    def test_checker_exit_one_for_invalid_successor(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as previous, \
                tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as proposed:
            json.dump(make_history(), previous)
            json.dump(make_history(outcome="pending", retries=0,
                                   candidate=None), proposed)
            previous_path, proposed_path = previous.name, proposed.name
        # Same pending snapshot is not a successor of itself.
        result = run_checker([proposed_path, "--previous", previous_path])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("not a valid successor", result.stdout)
        self.assertEqual(len(result.stdout.strip().splitlines()), 1)

    def test_checker_accepts_stdin(self):
        payload = json.dumps(make_history())
        result = run_checker([], stdin_text=payload)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK: valid repair history", result.stdout)


class FixtureDriftOutcomeTests(unittest.TestCase):
    """Cover the drift fixture check in-process (card contract for fixtures)."""

    def test_drift_fixture_stays_red_via_authorization_gate(self):
        # The terminal invocation `python3 scripts/verify-state --fixture
        # tests/fixtures/project-repair-card-drift.yaml` exits 1 with
        # "exact authorization missing" (verified in this run). Mirror the same
        # check in-process here so the outcome is executable.
        fixture = json.loads((ROOT / "tests/fixtures/project-repair-card-drift.yaml").read_text())
        card = fixture["project_repair_cards"][0]
        verifier = load_validator()
        errors, warnings = [], []
        output = io.StringIO()
        with redirect_stdout(output):
            verifier.check_project_repair_cards(errors, [card], warnings)
        self.assertEqual(errors, ["project repair contract drift t_fixture_repair: "
                                  "exact authorization missing"])
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
