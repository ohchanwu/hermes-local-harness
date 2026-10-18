"""A failed runtime stream leaves one content-free stream audit file in the profile's sessions dir.

Hermetic: reuses the synthetic-CLI harness of test_claude_subscription_provider.py (no real CLI,
no network, a temporary HERMES_HOME). Only the model-runtime child is rerouted to the small event
producer below. All canaries and tokens are synthetic.
"""
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_claude_subscription_provider as provider  # noqa: E402

client = provider.client
stream_audit = importlib.import_module("subscription_plugin.stream_audit")
MODEL, TOOL = provider.MODEL, provider.TOOL
PROVIDER_SCRIPT = str(Path(provider.__file__).resolve())
SCRIPT = str(Path(__file__).resolve())
NAME = re.compile(r"stream_audit_(.+)_\d{8}_\d{6}_\d{6}\.json")

DUPLICATE_FIRST, DUPLICATE_SECOND = "Alpha reply.", "Alpha reply. And more."
CANARIES = {
    "env_token": "sk-ant-oat01-SYNTHETIC-CANARY-ENV-TOKEN",
    "file_token": "SYNTHETIC-CANARY-FILE-TOKEN",
    "system": "SYSTEM-PROMPT-CANARY-51d2",
    "prompt": "USER-PROMPT-CANARY-8c0e",
    "history_argument": "/HISTORY-ARGUMENT-CANARY-3b7a",
    "tool_result": "TOOL-RESULT-CANARY-92fe",
    "text": "STREAMED-TEXT-CANARY-4e1c",
    "thinking": "THINKING-CANARY-a06d",
    "stream_argument": "/STREAM-ARGUMENT-CANARY-7f30",
    "drained_text": "DRAINED-TEXT-CANARY-c5b8",
}


class StreamAuditClientTests(unittest.TestCase):
    def setUp(self):
        real = subprocess.Popen
        def reroute(argv, *args, **kwargs):
            # The provider harness turns the synthetic CLI into its own script; send model runs here.
            if "--synthetic-runtime" in argv and "--version" not in argv:
                argv = [SCRIPT if part == PROVIDER_SCRIPT else part for part in argv]
            return real(argv, *args, **kwargs)
        guard = patch("subprocess.Popen", reroute)
        guard.start()
        self.addCleanup(guard.stop)
        provider.ClientTests.setUp(self)  # temporary HERMES_HOME = HOME = self.directory
        self.sessions = self.directory / "sessions"

    def request(self, text, session="sess-1/../x", **kwargs):
        return self.c.create(model=MODEL, extra_body={"subscription_session_id": session},
                             messages=[{"role": "system", "content": "Synthetic system"},
                                       {"role": "user", "content": text}], **kwargs)

    def audits(self):
        return sorted(self.sessions.glob("stream_audit_*.json")) if self.sessions.exists() else []

    def only_audit(self):
        files = self.audits()
        self.assertEqual(len(files), 1, files)
        return files[0], json.loads(files[0].read_text())

    def test_a_duplicate_streamed_message_writes_one_owner_only_audit_and_raises_the_original_error(self):
        with self.assertLogs(client.log.name, "WARNING") as logs, \
                self.assertRaisesRegex(client.ProviderError, r"^duplicate streamed message$") as raised:
            self.request("__dup__")
        self.assertIs(type(raised.exception), client.ProviderError)
        path, record = self.only_audit()
        self.assertEqual(NAME.fullmatch(path.name).group(1), "sess-1____x")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)  # (f)
        self.assertTrue(any(path.name in line for line in logs.output))
        self.assertEqual(list(self.sessions.glob(".stream_audit_*")), [])  # no temporary file left
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual((record["session_id"], record["model"], record["cli_version"]), ("sess-1____x", MODEL, "2.1.283"))
        self.assertEqual(record["error"], {"class": "ProviderError", "message": "duplicate streamed message"})
        self.assertIn("created_at", record)
        self.assertEqual([a["stage"] for a in record["audit"]], ["launch", "user_input", "init"])
        self.assertEqual(record["audit"][2], {"stage": "init", "model": MODEL, "tool_count": 0})
        stream = record["stream"]
        self.assertEqual(stream["drain"]["ended"], "complete")
        # The drain stops once the second message ends; the turn's result is not awaited.
        self.assertEqual((stream["restarts"], stream["messages_truncated"], stream["result_seen"]), (0, 0, False))
        first, second = stream["messages"]
        self.assertEqual({k: first[k] for k in ("id", "model", "stop_reason", "stopped", "restart", "streamed_text",
                                                "forwarded_chars", "text_chars", "text_sha256", "blocks")},
                         {"id": "msg_dup_1", "model": MODEL, "stop_reason": "end_turn", "stopped": True, "restart": False,
                          "streamed_text": True, "forwarded_chars": len(DUPLICATE_FIRST), "text_chars": len(DUPLICATE_FIRST),
                          "text_sha256": hashlib.sha256(DUPLICATE_FIRST.encode()).hexdigest(),
                          "blocks": [{"index": 0, "type": "text"}]})
        self.assertEqual(first["events"], [["message_start", 1], ["content_block_start", 1], ["content_block_delta", 1],
                                           ["assistant", 1], ["content_block_stop", 1], ["message_delta", 1], ["message_stop", 1]])
        self.assertNotIn("relation_to_previous", first)
        # The second message was read into the record only, after the failure, never to Hermes.
        self.assertEqual({k: second[k] for k in ("id", "stop_reason", "stopped", "after_stopped_message", "restart",
                                                 "streamed_text", "forwarded_chars", "text_chars", "text_sha256",
                                                 "relation_to_previous", "common_prefix_chars", "same_id_as_previous",
                                                 "same_model_as_previous")},
                         {"id": "msg_dup_2", "stop_reason": "end_turn", "stopped": True, "after_stopped_message": True,
                          "restart": False, "streamed_text": False, "forwarded_chars": 0,
                          "text_chars": len(DUPLICATE_SECOND),
                          "text_sha256": hashlib.sha256(DUPLICATE_SECOND.encode()).hexdigest(),
                          "relation_to_previous": "extends_previous", "common_prefix_chars": len(DUPLICATE_FIRST),
                          "same_id_as_previous": False, "same_model_as_previous": True})
        self.assertNotIn(DUPLICATE_FIRST, path.read_text())

    def test_b_runtime_retry_after_streamed_text_writes_an_audit_and_raises_the_original_error(self):
        chunks = []
        with self.assertRaisesRegex(client.ProviderError, r"^runtime retried a reply after part of it had streamed$"):
            for chunk in self.request("__retry_after_text__", stream=True):
                chunks.append(chunk)
        self.assertEqual("".join(getattr(c.choices[0].delta, "content", None) or "" for c in chunks), "Half")
        _, record = self.only_audit()
        self.assertEqual(record["error"]["message"], "runtime retried a reply after part of it had streamed")
        first, second = record["stream"]["messages"]
        self.assertEqual((first["stopped"], first["error_type"], first["streamed_text"], first["forwarded_chars"]),
                         (False, "overloaded_error", True, 4))
        self.assertEqual((second["restart"], second["restarts"], second["streamed_text"], second["relation_to_previous"]),
                         (True, 1, False, "extends_previous"))
        self.assertEqual(record["stream"]["restarts"], 1)
        self.assertIn(["system:api_retry", 1], record["stream"]["runtime_events"])

    def test_b_other_stream_loop_failures_also_write_an_audit(self):
        for trigger, error in (("__malformed_event__", "malformed runtime event or unexpected subagent"),
                               ("__unknown_kind__", "unknown runtime event"),
                               ("__boundary__", "event outside message boundary")):
            with self.subTest(trigger):
                for path in self.audits():
                    path.unlink()
                self.c.close()
                self.c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
                self.addCleanup(self.c.close)
                with self.assertRaisesRegex(client.ProviderError, "^" + re.escape(error) + "$"):
                    self.request(trigger)
                self.assertEqual(self.only_audit()[1]["error"]["message"], error)

    def test_c_no_credential_prompt_text_thinking_or_tool_content_reaches_the_file(self):
        token_file = self.directory / "oauth-token"
        token_file.write_text(CANARIES["file_token"])
        token_file.chmod(0o600)
        environment = {"CLAUDE_CODE_OAUTH_TOKEN": CANARIES["env_token"],
                       "HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE": str(token_file)}
        history_call = {"id": "toolu_hist", "type": "function",
                        "function": {"name": "read_file", "arguments": json.dumps({"path": CANARIES["history_argument"]})}}
        messages = [{"role": "system", "content": "Synthetic system " + CANARIES["system"]},
                    {"role": "user", "content": "Earlier " + CANARIES["prompt"]},
                    {"role": "assistant", "content": "", "tool_calls": [history_call]},
                    {"role": "tool", "tool_call_id": "toolu_hist", "content": CANARIES["tool_result"]},
                    {"role": "user", "content": "__dup_canary__ " + CANARIES["prompt"]}]
        sent, original = [], client.Runtime.send
        def record_input(runtime, value, *args, **kwargs):
            sent.append(value)
            return original(runtime, value, *args, **kwargs)
        with patch.dict(os.environ, environment), patch.object(client.Runtime, "send", record_input):
            self.c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
            self.addCleanup(self.c.close)
            with self.assertRaisesRegex(client.ProviderError, r"^duplicate streamed message$"):
                self.c.create(model=MODEL, messages=messages, tools=[TOOL])
        path, record = self.only_audit()
        # The prompt-side canaries really reached the runtime (the stream-side ones come back from it).
        for name in ("prompt", "history_argument", "tool_result"):
            self.assertIn(CANARIES[name], sent[0])
        text = path.read_text()
        for name, canary in CANARIES.items():
            with self.subTest(name):
                self.assertNotIn(canary, text)
                self.assertNotIn(canary.strip("/"), text)
        for forbidden in (str(token_file), "oauth-token", str(self.directory), provider.SYNTHETIC_CLI, "--system-prompt",
                          "HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE", "CLAUDE_CODE_OAUTH_TOKEN", "arguments", "Synthetic system"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)
        self.assertEqual([a["stage"] for a in record["audit"]], ["launch", "rebuild", "init"])
        self.assertEqual(record["audit"][1]["skipped_leading"], 0)
        first, second = record["stream"]["messages"]
        self.assertEqual([b["type"] for b in first["blocks"]], ["thinking", "text", "tool_use"])
        self.assertEqual((first["stop_reason"], second["relation_to_previous"]), ("tool_use", "extends_previous"))

    def test_d_an_unwritable_sessions_dir_still_raises_the_original_error(self):
        self.sessions.mkdir(mode=0o500)
        self.addCleanup(self.sessions.chmod, 0o700)
        with self.assertLogs(client.log.name, "WARNING") as logs, \
                self.assertRaisesRegex(client.ProviderError, r"^duplicate streamed message$"):
            self.request("__dup__")
        self.assertTrue(any("stream audit not written (PermissionError)" in line for line in logs.output))
        self.assertEqual(list(self.sessions.iterdir()), [])

    def test_an_existing_file_is_never_overwritten(self):
        self.sessions.mkdir(mode=0o700)
        with patch.object(stream_audit, "_stamp", return_value="20261018_000000_000000"):
            existing = self.sessions / "stream_audit_sess-1____x_20261018_000000_000000.json"
            existing.write_text("earlier evidence\n")
            with self.assertLogs(client.log.name, "WARNING") as logs, \
                    self.assertRaisesRegex(client.ProviderError, r"^duplicate streamed message$"):
                self.request("__dup__")
        self.assertEqual(existing.read_text(), "earlier evidence\n")
        self.assertEqual(sorted(p.name for p in self.sessions.iterdir()), [existing.name])
        self.assertTrue(any("FileExistsError" in line for line in logs.output))

    def test_e_a_successful_stream_and_errors_unrelated_to_streaming_write_nothing(self):
        self.assertEqual(self.request("__ok__").choices[0].message.content, "Fine")
        self.assertEqual(list(self.request("Again __ok__", stream=True))[-1].choices[0].finish_reason, "stop")
        with self.assertRaisesRegex(client.ProviderError, "allowlist"):
            self.c.create(model="opus", messages=[{"role": "user", "content": "__dup__"}])
        self.c.close()
        self.c = client.ClaudeSubscriptionClient(command=provider.SYNTHETIC_CLI)
        self.addCleanup(self.c.close)
        with self.assertRaisesRegex(client.ProviderError, "timed out"):
            self.request("__sleep__", timeout=.5)
        self.assertEqual(self.audits(), [])


class StreamLogTests(unittest.TestCase):
    def test_event_and_message_records_are_bounded_and_count_what_they_drop(self):
        log = stream_audit.StreamLog()
        for number in range(stream_audit.MAX_MESSAGES + 3):
            log.observe({"type": "stream_event", "event": {"type": "message_start", "message": {"id": f"m{number}"}}})
            for _ in range(stream_audit.MAX_RUNS):
                log.observe({"type": "stream_event", "event": {"type": "ping"}})
                log.observe({"type": "stream_event", "event": {"type": "content_block_stop", "index": 0}})
        report = log.report()
        self.assertEqual((len(report["messages"]), report["messages_truncated"]), (stream_audit.MAX_MESSAGES, 3))
        self.assertEqual(len(report["messages"][-1]["events"]), stream_audit.MAX_RUNS)
        self.assertGreater(report["messages"][-1]["events_truncated"], 0)
        for number in range(stream_audit.MAX_RUNS):
            log.observe({"type": "system", "subtype": "status" if number % 2 else "api_retry"})
        report = log.report()
        self.assertEqual(len(report["runtime_events"]), stream_audit.MAX_RUNS)
        self.assertGreater(report["runtime_events_truncated"], 0)

    def test_relations_and_allowlisted_audit_fields(self):
        self.assertEqual([stream_audit.relation(a, b) for a, b in (("ab", "ab"), ("abc", "ab"), ("ab", "abc"),
                                                                   ("ab", "x"), ("ab", ""), ("", "x"))],
                         ["equal", "prefix_of_previous", "extends_previous", "disjoint", "empty", "previous_empty"])
        entries = [{"stage": "tool_parked", "tool_use_id": "toolu_1", "rpc_id": 2, "name": "read_file",
                    "arguments": {"path": "/secret"}, "model": MODEL, "calls": 1},
                   {"stage": "result", "num_turns": 1, "usage": {"input_tokens": 3, "note": "free text"},
                    "modelUsage": {MODEL: {"costUSD": 0.1, "provider": "firstParty"}}},
                   {"stage": "something new", "payload": "free text"}]
        self.assertEqual([stream_audit.sanitize(e) for e in entries],
                         [{"stage": "tool_parked", "tool_use_id": "toolu_1", "rpc_id": 2, "name": "read_file",
                           "model": MODEL, "calls": 1},
                          {"stage": "result", "num_turns": 1, "usage": {"input_tokens": 3},
                           "modelUsage": {MODEL: {"costUSD": 0.1}}},
                          {"stage": "<other>"}])
        self.assertEqual(stream_audit.label("free text with spaces"), "<other>")


def synthetic_runtime(argv):
    """Inert event producer for the stream-failure shapes; never an installed runtime."""
    config = json.loads(Path(argv[argv.index("--mcp-config") + 1]).read_text())
    tools = [client.PREFIX + "read_file"] if config["mcpServers"] else []
    model = argv[argv.index("--model") + 1]
    def emit(obj):
        print(json.dumps(obj), flush=True)
    def ev(kind, **kwargs):
        emit({"type": "stream_event", "event": {"type": kind, **kwargs}})
    def start(message_id):
        ev("message_start", message={"id": message_id, "model": model, "usage": {"input_tokens": 1}})
    def block(message_id, index, value):
        if value["type"] == "text":
            ev("content_block_start", index=index, content_block={"type": "text", "text": ""})
            ev("content_block_delta", index=index, delta={"type": "text_delta", "text": value["text"]})
        elif value["type"] == "thinking":
            ev("content_block_start", index=index, content_block={"type": "thinking", "thinking": ""})
            ev("content_block_delta", index=index, delta={"type": "thinking_delta", "thinking": value["thinking"]})
        else:
            ev("content_block_start", index=index, content_block={**value, "input": {}})
            ev("content_block_delta", index=index, delta={"type": "input_json_delta", "partial_json": json.dumps(value["input"])})
        emit({"type": "assistant", "message": {"id": message_id, "model": model, "content": [value], "usage": {"output_tokens": 1}}})
        ev("content_block_stop", index=index)
    def message(message_id, blocks, stop="end_turn"):
        start(message_id)
        for index, value in enumerate(blocks):
            block(message_id, index, value)
        ev("message_delta", delta={"stop_reason": stop}, usage={"output_tokens": 2})
        ev("message_stop")
    def result():
        emit({"type": "result", "subtype": "success", "is_error": False, "num_turns": 1,
              "modelUsage": {model: {"canonicalModel": model, "provider": "firstParty"}}})
    def text(value):
        return {"type": "text", "text": value}
    for ordinal, line in enumerate(sys.stdin):
        content = json.loads(line)["message"]["content"]
        prompt = content if isinstance(content, str) else "".join(b.get("text", "") for b in content if b.get("type") == "text")
        if ordinal == 0:
            emit({"type": "system", "subtype": "init", "model": model, "tools": tools, "apiKeySource": "none",
                  "claude_code_version": "2.1.283"})
        if "__dup_canary__" in prompt:
            message("msg_canary_1", [{"type": "thinking", "thinking": CANARIES["thinking"], "signature": "sig"},
                                     text("Visible " + CANARIES["text"]),
                                     {"type": "tool_use", "id": "toolu_canary", "name": client.PREFIX + "read_file",
                                      "input": {"path": CANARIES["stream_argument"]}}], stop="tool_use")
            message("msg_canary_2", [text("Visible " + CANARIES["text"] + " " + CANARIES["drained_text"])])
            result()
        elif "__dup__" in prompt:
            message("msg_dup_1", [text(DUPLICATE_FIRST)])
            message("msg_dup_2", [text(DUPLICATE_SECOND)])
            result()
        elif "__retry_after_text__" in prompt:
            start("msg_partial")
            ev("content_block_start", index=0, content_block={"type": "text", "text": ""})
            ev("content_block_delta", index=0, delta={"type": "text_delta", "text": "Half"})
            ev("error", error={"type": "overloaded_error", "message": "Overloaded"})
            emit({"type": "system", "subtype": "api_retry", "attempt": 1})
            message("msg_retried", [text("Half a reply.")])
            result()
        elif "__malformed_event__" in prompt:
            start("msg_m")
            emit([1, 2])
        elif "__unknown_kind__" in prompt:
            start("msg_u")
            emit({"type": "mystery_kind"})
        elif "__boundary__" in prompt:
            message("msg_b", [text("Done.")])
            ev("content_block_start", index=1, content_block={"type": "text", "text": ""})
        elif "__sleep__" in prompt:
            import time
            time.sleep(30)
        else:
            message(f"msg_ok_{ordinal}", [text("Fine")])
            result()


if __name__ == "__main__":
    if sys.argv[1:2] == ["--synthetic-runtime"]:
        synthetic_runtime(sys.argv[2:])
    else:
        unittest.main()
