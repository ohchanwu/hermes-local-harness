"""Hermetic mechanism tests. No installed Hermes, Claude, profiles or network.

Synthetic child tests below execute only this interpreter and repository-owned
code. Native discovery/integration is separate, explicit isolated-home evidence.
"""
import copy
import asyncio
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/model-providers/claude-subscription"
spec = importlib.util.spec_from_file_location("subscription_client", PLUGIN / "client.py")
assert spec is not None and spec.loader is not None
client = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = client
spec.loader.exec_module(client)
mcp_spec = importlib.util.spec_from_file_location("subscription_mcp", PLUGIN / "mcp_server.py")
assert mcp_spec is not None and mcp_spec.loader is not None
mcp = importlib.util.module_from_spec(mcp_spec)
mcp_spec.loader.exec_module(mcp)

TOOL = {"type": "function", "function": {"name": "read_file", "description": "Native read",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                       "required": ["path"], "additionalProperties": False}}}


class SchemaTests(unittest.TestCase):
    def test_mcp_conversion_preserves_schema_without_mutation_or_effects(self):
        original = copy.deepcopy(TOOL)
        with patch("subprocess.Popen", side_effect=AssertionError("unexpected process")):
            converted = client.convert_tools([TOOL])
        self.assertEqual(converted, [{"name": "read_file", "description": "Native read",
                                      "inputSchema": TOOL["function"]["parameters"]}])
        converted[0]["inputSchema"]["required"].append("other")
        self.assertEqual(TOOL, original)

    def test_rejects_duplicate_names_nonfunctions_and_unsupported_schema(self):
        for tools in ([TOOL, TOOL], [{"type": "web_search"}],
                      [{"type": "function", "function": {"name": "bad/name", "parameters": {}}}],
                      [{"type": "function", "function": {"name": "read", "parameters": {"type": "array"}}}]):
            with self.subTest(tools=tools), self.assertRaises(client.ProviderError):
                client.convert_tools(tools)


class MCPTests(unittest.TestCase):
    def setUp(self):
        private = ROOT / "private/provider/unit"
        private.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        mcp.save(self.directory / "bridge.json", {"tools": client.convert_tools([TOOL]), "deadline": time.time() + 5})

    def test_actual_mcp_returns_only_matching_owner_result_and_never_reads_tool_path(self):
        mcp.save(self.directory / "result-0.json", {"rpc_id": 7, "tool_use_id": "toolu_synthetic", "text": "OWNER ONLY\n"})
        requests = [{"id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
                    {"id": 2, "method": "tools/list"}, {"id": 7, "method": "tools/call",
                     "params": {"name": "read_file", "arguments": {"path": "/nonexistent/not-read-by-MCP"}}}]
        out = io.StringIO()
        original = io.open
        def owned_open(path, *args, **kwargs):
            if not isinstance(path, int):
                self.assertEqual(Path(path).parent, self.directory)
            return original(path, *args, **kwargs)
        with patch("io.open", owned_open), patch("subprocess.Popen", side_effect=AssertionError("MCP executed")):
            mcp.serve(self.directory, io.StringIO("\n".join(map(json.dumps, requests))), out)
        replies = list(map(json.loads, out.getvalue().splitlines()))
        self.assertEqual(replies[-1], {"jsonrpc": "2.0", "id": 7,
                         "result": {"content": [{"type": "text", "text": "OWNER ONLY\n"}]}})
        self.assertEqual(json.loads((self.directory / "call-0.json").read_text()),
                         {"rpc_id": 7, "name": "read_file", "arguments": {"path": "/nonexistent/not-read-by-MCP"}})
        self.assertTrue((self.directory / "returned-0.json").exists())

    def test_cancelled_or_expired_mcp_cannot_return_result(self):
        (self.directory / "cancel").touch()
        out = io.StringIO()
        request = {"id": 7, "method": "tools/call", "params": {"name": "read_file", "arguments": {}}}
        mcp.serve(self.directory, io.StringIO(json.dumps(request)), out)
        self.assertEqual(out.getvalue(), "")
        self.assertFalse((self.directory / "returned-0.json").exists())

    def test_mcp_mismatched_delivery_and_duplicate_rpc_rejected(self):
        request = {"id": 7, "method": "tools/call", "params": {"name": "read_file", "arguments": {}}}
        mcp.save(self.directory / "result-0.json", {"rpc_id": 8, "tool_use_id": "toolu_synthetic", "text": "wrong"})
        with self.assertRaises(ValueError):
            mcp.serve(self.directory, io.StringIO(json.dumps(request)), io.StringIO())


class HistoryTests(unittest.TestCase):
    def start(self):
        h = client.History()
        messages = [{"role": "system", "content": "SYSTEM"}, {"role": "user", "content": "Read"}]
        h.accept(messages)
        return h, messages

    def call(self):
        return {"role": "assistant", "content": "", "tool_calls": [{"id": "toolu_synthetic",
                "type": "function", "function": {"name": "read_file", "arguments": '{"path":"/synthetic"}'}}]}

    def test_history_remembers_roles_and_does_not_replay_prompt(self):
        h, messages = self.start()
        self.assertEqual(h.messages, messages)
        call = self.call()
        h.assistant(call)
        messages += [call, {"role": "tool", "tool_call_id": "toolu_synthetic", "content": "RESULT\n"}]
        self.assertEqual(h.accept(messages), messages[-1])
        self.assertIsNone(h.pending_id)
        answer = {"role": "assistant", "content": "RESULT"}
        h.assistant(answer)
        messages += [answer, {"role": "user", "content": "Follow up"}]
        self.assertEqual(h.accept(messages), {"role": "user", "content": "Follow up"})
        self.assertEqual(h.messages, messages)

    def test_unknown_imported_history_and_content_are_explicitly_rejected(self):
        invalid = [[], [{"role": "assistant", "content": "imported"}, {"role": "user", "content": "next"}],
                   [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "unused"}}]}],
                   [{"role": "developer", "content": "unsupported"}, {"role": "user", "content": "next"}],
                   [{"role": "user", "content": "one"}, {"role": "user", "content": "two"}]]
        for messages in invalid:
            with self.subTest(messages=messages), self.assertRaises(client.ProviderError):
                client.History().accept(messages)

    def test_mismatched_missing_duplicate_and_replayed_results_have_no_effect(self):
        for tail in ([{"role": "tool", "tool_call_id": "wrong", "content": "bad"}],
                     [{"role": "user", "content": "missing result"}],
                     [{"role": "tool", "tool_call_id": "toolu_synthetic", "content": "ok"}] * 2):
            h, messages = self.start()
            call = self.call()
            h.assistant(call)
            before = copy.deepcopy(h.messages)
            with self.subTest(tail=tail), self.assertRaises(client.ProviderError):
                h.accept(messages + [call] + tail)
            self.assertEqual(h.messages, before)
            self.assertEqual(h.pending_id, "toolu_synthetic")
        h, messages = self.start()
        h.assistant(self.call())
        messages += [self.call(), {"role": "tool", "tool_call_id": "toolu_synthetic", "content": "ok"}]
        h.accept(messages)
        with self.assertRaises(client.ProviderError):
            h.accept(messages)

    def test_prefix_edits_and_compaction_are_not_silently_discarded(self):
        h, messages = self.start()
        h.assistant({"role": "assistant", "content": "done"})
        for history in ([{"role": "user", "content": "new session"}],
                        [{"role": "system", "content": "changed"}] + h.messages[1:] + [{"role": "user", "content": "next"}]):
            with self.subTest(history=history), self.assertRaises(client.ProviderError):
                h.accept(history)


class ClientTests(unittest.TestCase):
    def setUp(self):
        private = ROOT / "private/provider/unit"
        private.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        env = {"HOME": str(self.directory), "HERMES_HOME": str(self.directory),
               "PATH": "/usr/bin:/bin", "TMPDIR": str(self.directory)}
        self.environment = patch.dict(os.environ, env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.launches = []
        popen = subprocess.Popen
        def inert_only(argv, *args, **kwargs):
            if argv[0] == "synthetic-claude":
                self.launches.append(argv)
                argv = [sys.executable, "-I", "-S", str(Path(__file__).resolve()), "--synthetic-runtime"] + argv[1:]
            elif argv[0] != "/bin/ps":
                raise AssertionError("unit test attempted non-synthetic process: " + str(argv[0]))
            return popen(argv, *args, **kwargs)
        self.process_guard = patch("subprocess.Popen", inert_only)
        self.process_guard.start()
        self.addCleanup(self.process_guard.stop)
        real_socket = socket.socket
        def no_network(family=socket.AF_INET, *args, **kwargs):
            if family != socket.AF_UNIX:
                raise AssertionError("unit test attempted network")
            return real_socket(family, *args, **kwargs)  # asyncio's local wakeup socketpair only
        self.network_guard = patch("socket.socket", no_network)
        self.network_guard.start()
        self.addCleanup(self.network_guard.stop)
        self.c = client.ClaudeSubscriptionClient(command="synthetic-claude")
        self.addCleanup(self.c.close)

    def request(self, text="Hello", **kwargs):
        return self.c.chat.completions.create(model=client.MODEL,
                messages=[{"role": "system", "content": "Synthetic system"}, {"role": "user", "content": text}], **kwargs)

    def continuation(self, response, result="OWNER RESULT\n", *, stream=False):
        messages = copy.deepcopy(self.c._history.messages)
        messages.append({"role": "tool", "tool_call_id": response.choices[0].message.tool_calls[0].id, "content": result})
        return self.c.create(model=client.MODEL, messages=messages, tools=[TOOL], stream=stream)

    def test_lazy_constructor_and_invalid_configuration_have_no_runtime_effects(self):
        self.assertEqual(self.launches, [])
        for extras in ({"model": "opus"}, {"parallel_tool_calls": True}, {"temperature": 0.5},
                       {"max_tokens": 2048}, {"extra_body": {"unknown": True}}):
            kwargs = {"model": client.MODEL, "messages": [{"role": "user", "content": "unused"}], **extras}
            with self.subTest(extras=extras), self.assertRaises(client.ProviderError):
                self.c.create(**kwargs)
        self.assertEqual(self.launches, [])

    def test_nonstream_text_and_same_session_followup_shapes(self):
        response = self.request()
        self.assertEqual(response.choices[0].message.content, "YES")
        self.assertEqual(response.choices[0].finish_reason, "stop")
        self.assertEqual(response.model, client.MODEL)
        self.assertEqual(response.usage.prompt_tokens, 9)
        self.assertEqual(response.usage.completion_tokens, 2)
        messages = copy.deepcopy(self.c._history.messages) + [{"role": "user", "content": "Followup"}]
        second = self.c.create(model=client.MODEL, messages=messages)
        self.assertEqual(second.choices[0].message.content, "FOLLOWUP")
        self.assertNotEqual(second.id, response.id)
        self.assertEqual(len([a for a in self.c.audit if a["stage"] == "launch"]), 1)
        self.assertEqual(len([a for a in self.c.audit if a["stage"] == "user_input"]), 2)

    def test_stream_uses_real_text_deltas_and_terminal_finish_usage(self):
        stream = self.request(stream=True, stream_options={"include_usage": True})
        chunks = list(stream)
        self.assertEqual([c.choices[0].delta.content for c in chunks if hasattr(c.choices[0].delta, "content")], ["Y", "ES"])
        self.assertEqual(chunks[-1].choices[0].finish_reason, "stop")
        self.assertEqual(chunks[-1].usage.total_tokens, 11)
        self.assertTrue(all(c.id == chunks[0].id and c.model == client.MODEL for c in chunks))
        stream.close()  # clean stream close must not cancel the persistent runtime
        self.assertFalse(self.c.is_closed())

    def test_automatic_parked_tool_roundtrip_and_exact_once_result(self):
        response = self.request("__tool__", tools=[TOOL])
        call = response.choices[0].message.tool_calls[0]
        self.assertEqual(call.id, "toolu_synthetic_1_1")
        self.assertEqual(call.function.name, "read_file")
        self.assertEqual(json.loads(call.function.arguments), {"path": "/nonexistent/synthetic"})
        self.assertEqual(response.choices[0].finish_reason, "tool_calls")
        directory = self.c._runtime.directory
        self.assertTrue((directory / "call-0.json").exists())
        self.assertFalse((directory / "returned-0.json").exists())
        answer = self.continuation(response)
        self.assertEqual(answer.choices[0].message.content, "OWNER RESULT\n")
        self.assertEqual(json.loads((directory / "result-0.json").read_text())["text"], "OWNER RESULT\n")
        returned = json.loads((directory / "returned-0.json").read_text())
        self.assertEqual(returned, {"rpc_id": 2, "tool_use_id": call.id})
        with self.assertRaises(client.ProviderError):
            self.continuation(response)
        self.assertEqual(len(list(directory.glob("result-*.json"))), 1)

    def test_serial_multistep_and_streamed_tool_identity_arguments(self):
        chunks = list(self.request("__multi__", tools=[TOOL], stream=True))
        calls = [c.choices[0].delta.tool_calls[0] for c in chunks if hasattr(c.choices[0].delta, "tool_calls")]
        self.assertEqual(calls[0].id, "toolu_synthetic_1_1")
        self.assertEqual(calls[0].function.name, "read_file")
        self.assertEqual(json.loads("".join(c.function.arguments for c in calls)), {"path": "/nonexistent/synthetic"})
        first = self.c._last_response
        second = self.continuation(first, "FIRST")
        self.assertEqual(second.choices[0].finish_reason, "tool_calls")
        self.assertNotEqual(first.choices[0].message.tool_calls[0].id, second.choices[0].message.tool_calls[0].id)
        final = self.continuation(second, "SECOND")
        self.assertEqual(final.choices[0].message.content, "FIRST|SECOND")
        self.assertEqual(len([a for a in self.c.audit if a["stage"] == "user_input"]), 1)

    def test_parallel_model_calls_rejected_before_exposing_any_tool(self):
        stream = self.request("__two_tools__", tools=[TOOL], stream=True)
        seen = []
        with self.assertRaises(client.ProviderError):
            for chunk in stream:
                seen.extend(getattr(chunk.choices[0].delta, "tool_calls", []) or [])
        self.assertEqual(seen, [])
        self.assertTrue(self.c.is_closed())

    def test_concurrent_create_and_close_before_iteration(self):
        stream = self.request(stream=True)
        with self.assertRaisesRegex(client.ProviderError, "concurrent"):
            self.request()
        self.assertEqual(self.launches, [])
        stream.close()
        self.c.close()
        self.assertTrue(self.c.is_closed())
        with self.assertRaises(client.ProviderError):
            self.request()
        self.assertEqual(self.launches, [])

    def test_running_async_helper_rejected_before_effects(self):
        async def attempt():
            with self.assertRaisesRegex(client.ProviderError, "async"):
                self.request()
        asyncio.run(attempt())
        self.assertEqual(self.launches, [])

    def test_real_sleeping_child_timeout_cleanup_and_no_relaunch(self):
        started = time.monotonic()
        with self.assertRaisesRegex(client.ProviderError, "timed out"):
            self.request("__sleep__", timeout=0.2)
        self.assertLess(time.monotonic() - started, 3)
        self.assertTrue(self.c._runtime.cleanup["reaped"])
        self.assertTrue(self.c._runtime.cleanup["group_absent"])
        self.c.close()
        self.c.close()
        with self.assertRaises(client.ProviderError):
            self.request()
        self.assertEqual(len(self.launches), 2)  # one version check + one owned runtime

    def test_quota_death_malformed_and_wrong_model_are_not_success(self):
        for prompt in ("__quota__", "__death__", "__malformed__", "__wrongmodel__"):
            with self.subTest(prompt=prompt):
                c = client.ClaudeSubscriptionClient(command="synthetic-claude")
                with self.assertRaises((client.ProviderError, ValueError)):
                    c.create(model=client.MODEL, messages=[{"role": "user", "content": prompt}], timeout=1)
                self.assertTrue(c.is_closed())
                self.assertTrue(c._runtime.cleanup["group_absent"])
                c.close()

    def test_invalid_timeout_is_rejected_before_process_or_history_effects(self):
        for value in (0, -1, float('inf'), float('nan'), True, '60'):
            with self.subTest(timeout=value), self.assertRaises(client.ProviderError):
                self.request(timeout=value)
            self.assertEqual(self.launches, [])
            self.assertEqual(self.c._history.messages, [])

    def test_close_parked_and_during_active_stream_reaps_once(self):
        response = self.request('__tool__', tools=[TOOL])
        directory = self.c._runtime.directory
        self.c.close()
        self.assertTrue(self.c._runtime.cleanup['group_absent'])
        self.assertFalse((directory / 'returned-0.json').exists())
        with self.assertRaises(client.ProviderError):
            self.continuation(response)
        other = client.ClaudeSubscriptionClient(command='synthetic-claude')
        self.addCleanup(other.close)
        stream = other.create(model=client.MODEL, messages=[{'role':'user','content':'__sleep__'}], stream=True)
        errors = []
        def consume():
            try:
                list(stream)
            except client.ProviderError as exc:
                errors.append(str(exc))
        thread = threading.Thread(target=consume)
        thread.start()
        end = time.monotonic() + 2
        while other._runtime is None and time.monotonic() < end:
            time.sleep(.01)
        other.close()
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertTrue(other._runtime.cleanup['group_absent'])
        other.close()

    def test_same_client_scope_change_and_third_user_input_rejected_before_send(self):
        self.request()
        messages = copy.deepcopy(self.c._history.messages) + [{'role':'user','content':'next'}]
        before = copy.deepcopy(self.c._history.messages)
        with patch.dict(os.environ, {'HERMES_PROFILE':'different-reviewer'}), self.assertRaises(client.ProviderError):
            self.c.create(model=client.MODEL, messages=messages)
        self.assertEqual(before, self.c._history.messages)
        self.c.create(model=client.MODEL, messages=messages)
        messages = copy.deepcopy(self.c._history.messages) + [{'role':'user','content':'third'}]
        before = copy.deepcopy(self.c._history.messages)
        with self.assertRaises(client.ProviderError):
            self.c.create(model=client.MODEL, messages=messages)
        self.assertEqual(before, self.c._history.messages)

    def test_malformed_stream_arguments_are_provider_errors(self):
        with self.assertRaises(client.ProviderError):
            self.request('__badargs__', tools=[TOOL])
        self.assertTrue(self.c._runtime.cleanup['group_absent'])

    def test_stubborn_owned_child_is_killed_within_five_second_cleanup_grace(self):
        started=time.monotonic()
        with self.assertRaises(client.ProviderError):
            self.request('__stubborn__', timeout=.2)
        self.assertLess(time.monotonic()-started, 5)
        self.assertTrue(self.c._runtime.cleanup['reaped'])
        self.assertTrue(self.c._runtime.cleanup['group_absent'])

    def test_unmatched_tool_cannot_be_silently_returned_as_text_success(self):
        with self.assertRaises(client.ProviderError):
            self.request('__unmatched_tool__', tools=[TOOL])
        self.assertIsNone(self.c._pending)
        self.assertTrue(self.c._runtime.cleanup['group_absent'])

    def test_missing_binary_and_wrong_version_fail_in_owned_runtime_not_construction(self):
        c=client.ClaudeSubscriptionClient(command='/nonexistent/synthetic-only')
        self.addCleanup(c.close)
        with patch('subprocess.run', side_effect=FileNotFoundError('synthetic missing binary')):
            with self.assertRaises(client.ProviderError):
                c.create(model=client.MODEL,messages=[{'role':'user','content':'unused'}])
        other=client.ClaudeSubscriptionClient(command='synthetic-claude')
        self.addCleanup(other.close)
        with patch('subprocess.run', return_value=subprocess.CompletedProcess([],0,b'wrong-version',b'')):
            with self.assertRaisesRegex(client.ProviderError,'untested Claude CLI version'):
                other.create(model=client.MODEL,messages=[{'role':'user','content':'unused'}])
        self.assertEqual(self.launches,[])

    def test_rejected_rate_limit_stops_instead_of_accepting_later_success(self):
        with self.assertRaises(client.ProviderError):
            self.request('__ratelimit__')
        self.assertTrue(self.c.is_closed())
        self.assertTrue(self.c._runtime.cleanup['group_absent'])

    def test_cancel_during_version_startup_prevents_model_process(self):
        entered, release = threading.Event(), threading.Event()
        def version(*args,**kwargs):
            entered.set()
            self.assertTrue(release.wait(2))
            return subprocess.CompletedProcess([],0,b'2.1.283 (Claude Code)',b'')
        errors=[]
        def run():
            try:
                self.request()
            except client.ProviderError as exc:
                errors.append(str(exc))
        with patch('subprocess.run', side_effect=version):
            thread=threading.Thread(target=run)
            thread.start()
            self.assertTrue(entered.wait(2))
            self.c.close()
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors),1)
        self.assertEqual(self.launches,[])


def synthetic_runtime(argv):
    """Inert event producer, never an installed runtime, service or tool executor."""
    if "--version" in argv:
        print("2.1.283 (Claude Code)", flush=True)
        return
    def emit(obj):
        print(json.dumps(obj), flush=True)
    def ev(kind, **kwargs):
        emit({"type": "stream_event", "event": {"type": kind, **kwargs}})
    def message(message_id, text=None, tool_ids=None):
        ev("message_start", message={"id": message_id, "model": client.MODEL,
                                    "usage": {"input_tokens": 1, "output_tokens": 0}})
        content = []
        if tool_ids:
            for index, tool_id in enumerate(tool_ids):
                args = {"path": fixture}
                ev("content_block_start", index=index, content_block={"type": "tool_use", "id": tool_id,
                    "name": client.PREFIX + "read_file", "input": {}})
                data = '{invalid' if badargs else json.dumps(args)
                for fragment in (data[:9], data[9:]):
                    ev("content_block_delta", index=index, delta={"type": "input_json_delta", "partial_json": fragment})
                content.append({"type": "tool_use", "id": tool_id, "name": client.PREFIX + "read_file", "input": args})
        else:
            ev("content_block_start", index=0, content_block={"type": "text", "text": ""})
            assert text is not None
            for fragment in (text[:1], text[1:]):
                ev("content_block_delta", index=0, delta={"type": "text_delta", "text": fragment})
            content = [{"type": "text", "text": text}]
        emit({"type": "assistant", "message": {"id": message_id, "model": client.MODEL, "content": content,
              "usage": {"input_tokens": 1, "cache_read_input_tokens": 5, "cache_creation_input_tokens": 3, "output_tokens": 2}}})
        for index in range(len(content)):
            ev("content_block_stop", index=index)
        ev("message_delta", delta={"stop_reason": "tool_use" if tool_ids else "end_turn"}, usage={"output_tokens": 2})
        ev("message_stop")
    config = json.loads(Path(argv[argv.index("--mcp-config") + 1]).read_text())
    tools = [client.PREFIX + "read_file"] if config["mcpServers"] else []
    bridge = None
    fixture = argv[argv.index('--native-fixture')+1] if '--native-fixture' in argv else '/nonexistent/synthetic'
    badargs = False
    ordinal = 0
    for line in sys.stdin:
        ordinal += 1
        text = json.loads(line)["message"]["content"]
        if '--native-fixture' in argv:
            text = '__tool__' if ordinal == 1 else 'Followup'
        badargs = text == '__badargs__'
        if ordinal == 1:
            emit({"type": "system", "subtype": "init", "model": "wrong" if text == "__wrongmodel__" else client.MODEL,
                  "tools": tools, "apiKeySource": "none", "claude_code_version": "2.1.283"})
        if text == "__sleep__":
            time.sleep(30)
        if text == '__stubborn__':
            import signal
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            time.sleep(30)
        if text == "__death__":
            return
        if text == "__malformed__":
            print("not-json", flush=True)
            return
        if text == "__quota__":
            emit({"type": "result", "subtype": "error_during_execution", "is_error": True})
            continue
        if text == '__unmatched_tool__':
            message('msg_unmatched',tool_ids=['toolu_unmatched'])
            emit({'type':'result','subtype':'success','is_error':False,'num_turns':1})
            continue
        if text == '__ratelimit__':
            emit({'type':'rate_limit_event','rate_limit_info':{'status':'rejected'}})
        count = 2 if text == "__multi__" else 1 if text in ('__tool__', '__badargs__') else 0
        if text == "__two_tools__":
            message("msg_parallel", tool_ids=["toolu_a", "toolu_b"])
            time.sleep(30)
        results = []
        for turn in range(1, count + 1):
            message(f"msg_{ordinal}_{turn}", tool_ids=[f"toolu_synthetic_{ordinal}_{turn}"])
            if bridge is None:
                cfg = config["mcpServers"]["hermes"]
                bridge = subprocess.Popen([cfg["command"]] + cfg["args"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
                def rpc(value):
                    assert bridge is not None and bridge.stdin is not None and bridge.stdout is not None
                    bridge.stdin.write(json.dumps(value) + "\n")
                    bridge.stdin.flush()
                    return json.loads(bridge.stdout.readline())
                rpc({"id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
            reply = rpc({"id": turn + 1, "method": "tools/call", "params": {"name": "read_file", "arguments": {"path": fixture}}})
            results.append(reply["result"]["content"][0]["text"])
        message(f"msg_{ordinal}_final", text="|".join(results) if results else "YES" if ordinal == 1 else "FOLLOWUP")
        emit({"type": "result", "subtype": "success", "is_error": False, "num_turns": count + 1,
              "modelUsage": {client.MODEL: {"canonicalModel": client.MODEL, "provider": "firstParty"}}, "usage": {"input_tokens": 1, "output_tokens": 2}})
    if bridge:
        bridge.terminate()
        bridge.wait(timeout=2)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--synthetic-runtime"]:
        synthetic_runtime(sys.argv[2:])
    else:
        unittest.main()
