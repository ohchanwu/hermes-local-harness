"""Generation2 oracles: real extracted seams, explicitly synthetic runtime/tools."""
import copy
import socket
import unittest

import rendezvous as rv

SCOPE = ("harness-worker", "worker", "t_fixture", "session-fixture", "/synthetic/worktree")


class RendezvousTests(unittest.TestCase):
    def setUp(self):
        self.client = rv.Rendezvous(SCOPE)
        self.messages = [{"role": "user", "content": "read synthetic fixture"}]
        self.addCleanup(self.client.cancel)

    def first(self):
        response = rv.dispatch(self.client, self.messages, SCOPE)
        self.assertEqual(response.finish_reason, "tool_calls")
        self.assertEqual(len(response.message.tool_calls), 1)
        return response

    def test_two_actual_client_dispatches_and_tool_round(self):
        response = self.first()
        self.assertEqual(self.client.sent, [])  # MCP is parked, no result/execution yet.
        tc = response.message.tool_calls[0]
        self.assertEqual(tc.id, "toolu-synthetic-1")
        self.assertNotEqual(tc.id, self.client.pending["request_id"])
        self.assertNotEqual(tc.id, str(self.client.pending["request"]["message"]["id"]))
        events = []
        verdict = rv.tool_round(response.message, self.messages, events)
        self.assertEqual(verdict.action, "continue")
        self.assertEqual(events, ["persist", "fake_permission", "fake_execution", "post_tool"])
        self.assertEqual(self.messages[-1]["tool_call_id"], tc.id)
        result = rv.dispatch(self.client, self.messages, SCOPE)
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.receipt, rv.digest(self.messages[-1]["content"]))
        self.assertEqual(self.client.calls, 2)
        self.assertEqual(len(self.client.sent), 1)
        self.assertTrue(self.client.cleaned())
        print("RENDEZVOUS", {"calls": self.client.calls, "ids": [tc.id, "control-1", 7],
                              "events": events, "reaped_group_absent": self.client.cleaned()})

    def test_persistence_failure_never_executes(self):
        response = self.first()
        events = []
        verdict = rv.tool_round(response.message, self.messages, events, persisted=False)
        self.assertEqual(verdict.action, "break")
        self.assertEqual(events, ["persist"])
        self.assertEqual(self.client.sent, [])
        self.client.cancel()
        self.assertTrue(self.client.cleaned())

    def test_missing_duplicate_mismatched_and_replayed_results_fail_closed(self):
        for kind in ("missing", "duplicate", "mismatch", "assistant_mismatch"):
            with self.subTest(kind=kind):
                client = rv.Rendezvous(SCOPE)
                self.addCleanup(client.cancel)
                messages = copy.deepcopy(self.messages)
                response = rv.dispatch(client, messages, SCOPE)
                self.assertEqual(response.finish_reason, "tool_calls")
                events = []
                rv.tool_round(response.message, messages, events)
                if kind == "missing":
                    messages.pop()
                elif kind == "duplicate":
                    messages.append(copy.deepcopy(messages[-1]))
                elif kind == "mismatch":
                    messages[-1]["tool_call_id"] = "control-1"
                else:
                    messages[-2]["tool_calls"][0]["id"] = "control-1"
                with self.assertRaisesRegex(rv.ProtocolError, "lineage"):
                    rv.dispatch(client, messages, SCOPE)
                self.assertEqual(client.sent, [])
                self.assertTrue(client.cleaned())
                with self.assertRaises(rv.ProtocolError):
                    rv.dispatch(client, messages, SCOPE)
                self.assertEqual(events.count("fake_execution"), 1)

    def test_cancel_and_scope_mismatch_cannot_attach(self):
        self.first()
        self.client.cancel()
        self.client.cancel()
        self.assertTrue(self.client.cleaned())
        with self.assertRaises(rv.ProtocolError):
            rv.dispatch(self.client, self.messages, SCOPE)
        for index in range(len(SCOPE)):
            other = rv.Rendezvous(SCOPE)
            self.addCleanup(other.cancel)
            rv.dispatch(other, self.messages, SCOPE)
            changed_scope = list(SCOPE)
            changed_scope[index] = "other-synthetic-scope"
            with self.assertRaisesRegex(rv.ProtocolError, "scope"):
                rv.dispatch(other, self.messages, changed_scope)
            self.assertEqual(other.sent, [])
            self.assertTrue(other.cleaned())

    def test_malformed_or_duplicate_model_events_never_expose_tools(self):
        for variant in ("duplicate_tool", "mismatch_rpc", "missing_tool"):
            with self.subTest(variant=variant):
                client = rv.Rendezvous(SCOPE, variant=variant)
                self.addCleanup(client.cancel)
                with self.assertRaisesRegex(rv.ProtocolError, "lineage"):
                    rv.dispatch(client, self.messages, SCOPE)
                self.assertEqual(client.sent, [])
                self.assertTrue(client.cleaned())


    def test_startup_continuation_deadline_and_process_death_reap(self):
        for variant in ("startup_timeout", "continuation_timeout", "process_death"):
            with self.subTest(variant=variant):
                client = rv.Rendezvous(SCOPE, variant=variant)
                self.addCleanup(client.cancel)
                messages = copy.deepcopy(self.messages)
                if variant == "continuation_timeout":
                    response = rv.dispatch(client, messages, SCOPE)
                    rv.tool_round(response.message, messages, [])
                with self.assertRaisesRegex(rv.ProtocolError, "deadline|death"):
                    rv.dispatch(client, messages, SCOPE)
                self.assertTrue(client.cleaned())


class RoutingTests(unittest.TestCase):
    def test_lazy_client_construction_and_rebuild_keep_profile_route(self):
        result = rv.construction()
        self.assertEqual(result["routes"], ["profile", "profile"])
        self.assertTrue(result["replaced"])
        self.assertEqual(result["validators"], ["acp://synthetic", "acp://synthetic"])

    def test_factory_failure_still_attempts_http_with_non_http_url(self):
        result = rv.construction(factory_raises=True)
        self.assertEqual(result["routes"], ["profile", "FORBIDDEN_HTTP_CONSTRUCTOR"])
        self.assertFalse(result["replaced"])
        print("UNSAFE constructor intercepted:", result)

    def test_main_empty_chain_blocks_selected_recovery_rung(self):
        result = rv.main_recovery()
        self.assertEqual(result, {"fallback": False, "pool": (False, True), "routes": []})

    def test_explicit_aux_unavailable_empty_chain_stops(self):
        result = rv.aux_unavailable()
        self.assertEqual(result, ["explicit_client_unavailable", "task_chain_empty", "unavailable"])

    def test_aux_quota_ignores_session_pin_and_attempts_disk_main(self):
        result = rv.aux_recovery("openai")
        self.assertEqual(result, ["task_chain_empty", "disk_main:openai", "FORBIDDEN_PROVIDER:openai"])
        print("UNSAFE auxiliary quota route intercepted:", result)

    def test_explicit_main_blocks_aux_discovery(self):
        self.assertEqual(rv.discovery_control(), [])

    def test_scoped_network_file_and_import_guards(self):
        with rv.guarded():
            with self.assertRaisesRegex(AssertionError, "network"):
                socket.socket()
            with self.assertRaisesRegex(AssertionError, "file"):
                (rv.ROOT / "nonexistent-synthetic-denied").read_text()
        with self.assertRaisesRegex(ImportError, "denied"):
            rv.denied_import("nonexistent_synthetic")

    def test_missing_or_drifted_snapshot_fails_explicitly(self):
        with self.assertRaisesRegex(AssertionError, "not frozen"):
            rv.load("missing-synthetic.txt", {"missing"}, {})
        original = rv.SOURCES["generation2-turn_tool_round.py.txt"]
        try:
            rv.SOURCES["generation2-turn_tool_round.py.txt"] = "0" * 64
            with self.assertRaisesRegex(AssertionError, "drift"):
                rv.load("generation2-turn_tool_round.py.txt", {"run_tool_round"}, {})
        finally:
            rv.SOURCES["generation2-turn_tool_round.py.txt"] = original


def load_tests(loader, tests, pattern):
    assert tests.countTestCases() == 14, "Generation2 case inventory drift"
    return tests


if __name__ == "__main__":
    unittest.main(verbosity=2)
