"""OFFLINE only: stdlib, synthetic events, owned Python children. Never Claude."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import probe

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / "private" / "capability"
FIXTURE = "/owned/synthetic.txt"
ID = "toolu_offline_example"


def event(kind, **kwargs):
    return {"type": "stream_event", "event": {"type": kind, **kwargs}}


def correlated():
    state = probe.Correlation(FIXTURE)
    state.event(event("message_start", message={"model": probe.MODEL}))
    state.event(event("content_block_start", index=0,
                      content_block={"type": "tool_use", "id": ID, "name": probe.TOOL, "input": {}}))
    data = json.dumps({"path": FIXTURE})
    for part in (data[:12], data[12:]):
        state.event(event("content_block_delta", index=0, delta={"type": "input_json_delta", "partial_json": part}))
    state.event(event("content_block_stop", index=0))
    state.pending({"rpc_id": 7, "name": "fixture_read", "arguments": {"path": FIXTURE}})
    return state


def native_result():
    return {"tool_use_id": ID, "rpc_id": 7, "name": probe.TOOL,
            "arguments": {"path": FIXTURE}, "text": "OFFLINE_ONLY\n", "native_tool": "read_file"}


class ProbeTests(unittest.TestCase):
    def setUp(self):
        PRIVATE.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=PRIVATE)
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_real_event_shaped_serial_correlation(self):
        state = correlated()
        self.assertTrue(state.ready())
        state.event({"type": "assistant", "message": {"model": probe.MODEL, "content": [
            {"type": "tool_use", "id": ID, "name": probe.TOOL, "input": {"path": FIXTURE}}]}})
        delivery = state.accept(native_result())
        self.assertEqual(delivery, {"rpc_id": 7, "tool_use_id": ID, "text": "OFFLINE_ONLY\n"})
        self.assertNotEqual(state.rpc_id, state.tool_id)
        # A subsequent model message may reuse block index zero for TEXT.
        state.event(event("message_start", message={"model": probe.MODEL}))
        state.event(event("content_block_start", index=0, content_block={"type": "text", "text": ""}))
        state.event(event("content_block_delta", index=0, delta={"type": "text_delta", "text": "OK"}))

    def test_mismatched_results_rejected_before_delivery(self):
        for key, value in (("tool_use_id", "other"), ("rpc_id", 8), ("name", "Bash"),
                           ("arguments", {"path": "/foreign"}), ("native_tool", "fake_read")):
            with self.subTest(key=key):
                state = correlated()
                result = native_result()
                result[key] = value
                with self.assertRaises(ValueError):
                    state.accept(result)
                self.assertFalse(state.delivered)
        with self.assertRaises(ValueError):
            probe.Correlation(FIXTURE).accept(native_result())

    def test_duplicate_and_stale_rejection(self):
        state = correlated()
        state.accept(native_result())
        with self.assertRaises(ValueError):
            state.accept(native_result())
        state = correlated()
        state.cancel()
        state.cancel()
        self.assertFalse(state.ready())
        with self.assertRaises(ValueError):
            state.accept(native_result())
        with self.assertRaises(ValueError):
            state.pending({"rpc_id": 7, "name": "fixture_read", "arguments": {"path": FIXTURE}})

    def test_unexpected_calls_and_duplicate_stream_rejected(self):
        for name, args in (("Bash", {"path": FIXTURE}), (probe.TOOL, {"path": "/foreign"}),
                           (probe.TOOL, {"path": FIXTURE, "extra": 1})):
            with self.subTest(name=name, args=args), self.assertRaises(ValueError):
                probe.Correlation(FIXTURE).tool(ID, name, args, "stream")
        state = correlated()
        with self.assertRaises(ValueError):
            state.tool("another_id", probe.TOOL, {"path": FIXTURE}, "assistant")
        with self.assertRaises(ValueError):
            state.tool(ID, probe.TOOL, {"path": FIXTURE}, "stream")
        with self.assertRaises(ValueError):
            state.pending({"rpc_id": 8, "name": "fixture_read", "arguments": {"path": FIXTURE}})

    def test_mcp_parks_without_reading_or_executing(self):
        # Run the actual server body with file-open scope and subprocess denial.
        # The fixture deliberately does not exist. Only parent-authored delivery
        # supplies bytes; reading the requested path would fail this test.
        probe.save(self.dir / "case.json", {"fixture": FIXTURE})
        probe.save(self.dir / "delivery.json", {"rpc_id": 7, "tool_use_id": ID, "text": "PARENT_ONLY\n"})
        requests = [
            {"id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
            {"id": 2, "method": "tools/list"},
            {"id": 7, "method": "tools/call", "params": {"name": "fixture_read", "arguments": {"path": FIXTURE}}},
        ]
        original = io.open
        allowed = {self.dir / n for n in ("case.json", "delivery.json")}
        def owned_open(path, *args, **kwargs):
            if not isinstance(path, int):
                self.assertIn(Path(path), allowed)
            return original(path, *args, **kwargs)
        out = io.StringIO()
        with patch("sys.stdin", io.StringIO("\n".join(map(json.dumps, requests)))), patch("sys.stdout", out), \
                patch("io.open", owned_open), patch("subprocess.Popen", side_effect=AssertionError("MCP executed child")):
            probe.mcp(self.dir)
        replies = list(map(json.loads, out.getvalue().splitlines()))
        self.assertEqual(replies[1]["result"]["tools"], [probe.schema(FIXTURE)])
        self.assertEqual(replies[2]["id"], 7)
        self.assertEqual(replies[2]["result"]["content"], [{"type": "text", "text": "PARENT_ONLY\n"}])
        self.assertEqual(probe.load(self.dir / "pending.json")["arguments"], {"path": FIXTURE})

    def test_mcp_cancel_never_delivers(self):
        probe.save(self.dir / "case.json", {"fixture": FIXTURE})
        probe.save(self.dir / "cancel.json", {"cancel": True})
        request = {"id": 7, "method": "tools/call", "params": {"name": "fixture_read", "arguments": {"path": FIXTURE}}}
        out = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(request))), patch("sys.stdout", out):
            probe.mcp(self.dir)
        self.assertEqual(out.getvalue(), "")
        self.assertTrue((self.dir / "mcp-stop.json").exists())
        self.assertFalse((self.dir / "mcp-return.json").exists())

    def test_actual_sleeping_child_deadline_group_reaping(self):
        child = probe.Child([sys.executable, "-I", "-S", "-c", "import time; time.sleep(30)"], self.dir,
                            {"PATH": "/usr/bin:/bin", "HOME": str(self.dir)})
        self.addCleanup(child.cleanup)
        self.assertFalse(child.expired(0.15))
        while not child.expired(0.15):
            time.sleep(0.01)
        receipt = child.cleanup()
        self.assertTrue(receipt["reaped"])
        self.assertTrue(receipt["group_absent"])
        self.assertLess(receipt["lifetime_seconds"], 2)
        self.assertEqual(child.cleanup(), receipt)

    def test_actual_process_group_with_descendant(self):
        code = ("import subprocess,signal,sys,time; "
                "p=subprocess.Popen([sys.executable,'-I','-S','-c','import time; time.sleep(30)']); "
                "signal.signal(signal.SIGTERM,lambda *_:(p.wait(timeout=2),sys.exit(0))); "
                "print('ready',flush=True); time.sleep(30)")
        child = probe.Child([sys.executable, "-I", "-S", "-c", code], self.dir, {"PATH": "/usr/bin:/bin", "HOME": str(self.dir)})
        self.addCleanup(child.cleanup)
        import select
        assert child.p.stdout is not None
        self.assertTrue(select.select([child.p.stdout], [], [], 2)[0])
        self.assertEqual(child.p.stdout.readline(), b"ready\n")
        receipt = child.cleanup()
        self.assertTrue(receipt["reaped"])
        self.assertTrue(receipt["group_absent"])
        self.assertEqual(child.cleanup(), receipt)

    def test_exclusive_mailbox_duplicate_rejected(self):
        path = self.dir / "result.json"
        probe.save(path, {"one": 1}, exclusive=True)
        with self.assertRaises(FileExistsError):
            probe.save(path, {"two": 2}, exclusive=True)
        self.assertEqual(probe.load(path), {"one": 1})
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_event_projection_excludes_private_fields(self):
        obj = {"type": "system", "subtype": "init", "account": "never-persist", "email": "never-persist",
               "tools": [probe.TOOL], "model": probe.MODEL}
        self.assertNotIn("never-persist", json.dumps(probe.project(obj)))
        obj = {"type": "assistant", "message": {"model": probe.MODEL, "content": [{"type": "thinking", "thinking": "private"}]}}
        self.assertNotIn("private", json.dumps(probe.project(obj)))


if __name__ == "__main__":
    unittest.main()
