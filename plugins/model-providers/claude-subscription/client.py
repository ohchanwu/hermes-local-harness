"""Serial subscription CLI client. No runtime or Hermes I/O on import."""
import copy
import asyncio
import hashlib

import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

MODEL = "claude-opus-5-5"
PREFIX = "mcp__hermes__"


class ProviderError(RuntimeError):
    """Terminal client/protocol error; never a successful substitute response."""


def response_seconds(value):
    if value is None:
        return 60
    seconds = value if type(value) in (int, float) else getattr(value, "read", None)
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
        raise ProviderError("invalid response timeout")
    return min(seconds, 150)


def convert_tools(tools):
    """Convert the caller's function tools to MCP declarations."""
    if tools is None:
        return []
    if not isinstance(tools, list):
        raise ProviderError("tools must be a list of functions")
    converted, names = [], set()
    for tool in tools:
        if not isinstance(tool, dict) or tool.get("type") != "function" or set(tool) != {"type", "function"}:
            raise ProviderError("only function tools are supported")
        fn = tool["function"]
        if not isinstance(fn, dict) or set(fn) - {"name", "description", "parameters", "strict"}:
            raise ProviderError("unsupported function declaration")
        name = fn.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", name) or name in names:
            raise ProviderError("invalid or duplicate function name")
        schema = fn.get("parameters")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ProviderError("MCP function input must be an object schema")
        if not isinstance(fn.get("description", ""), str):
            raise ProviderError("function description must be text")
        names.add(name)
        converted.append({"name": name, "description": fn.get("description", ""), "inputSchema": copy.deepcopy(schema)})
    return converted


class History:
    """In-memory transcript owned by exactly one synchronous client."""
    def __init__(self):
        self.messages = []
        self.pending_id = None

    def accept(self, messages):
        if not isinstance(messages, list) or not messages:
            raise ProviderError("messages must be a nonempty transcript")
        canonical = [self.canonical(m) for m in messages]
        if not self.messages:
            roles = [m["role"] for m in canonical]
            if roles not in (["user"], ["system", "user"]):
                raise ProviderError("new clients require a fresh system/user turn; imported history is unsupported")
        else:
            if len(canonical) != len(self.messages) + 1 or canonical[:-1] != self.messages:
                raise ProviderError("history prefix changed, missing, replayed or compacted; use a new client")
            tail = canonical[-1]
            if self.pending_id:
                if tail["role"] != "tool" or tail.get("tool_call_id") != self.pending_id:
                    raise ProviderError("one matching tool result is required before continuation")
            elif tail["role"] != "user":
                raise ProviderError("expected one new user turn, not a stale tool result")
        self.messages = canonical
        self.pending_id = None
        return copy.deepcopy(canonical[-1])

    @staticmethod
    def canonical(message):
        if not isinstance(message, dict):
            raise ProviderError("message must be an object")
        role = message.get("role")
        allowed = {"role", "content"}
        if role == "assistant":
            allowed |= {"tool_calls", "reasoning_content"}
        elif role == "tool":
            allowed |= {"tool_call_id"}
        elif role not in ("system", "user"):
            raise ProviderError("unsupported message role")
        if set(message) - allowed or message.get("reasoning_content"):
            raise ProviderError("unsupported message fields or imported reasoning")
        text = message.get("content")
        if text is None and role == "assistant":
            text = ""
        if not isinstance(text, str):
            raise ProviderError("only plain text message content is supported; no images or multipart content")
        out: dict = {"role": role, "content": text}
        if role == "tool":
            if not isinstance(message.get("tool_call_id"), str) or not message["tool_call_id"]:
                raise ProviderError("tool result requires its original id")
            out["tool_call_id"] = message["tool_call_id"]
        calls = message.get("tool_calls")
        if calls:
            if not isinstance(calls, list) or len(calls) != 1:
                raise ProviderError("parallel/multiple tool calls are unsupported")
            call = calls[0]
            if not isinstance(call, dict) or set(call) != {"id", "type", "function"} or call["type"] != "function":
                raise ProviderError("invalid tool call")
            fn = call["function"]
            if not isinstance(fn, dict) or set(fn) != {"name", "arguments"}:
                raise ProviderError("invalid tool function")
            if not isinstance(call["id"], str) or not call["id"] or not isinstance(fn["name"], str):
                raise ProviderError("invalid tool identity")
            try:
                args = json.loads(fn["arguments"])
            except (ValueError, TypeError):
                raise ProviderError("invalid JSON tool arguments") from None
            if not isinstance(args, dict):
                raise ProviderError("tool arguments must be an object")
            out["tool_calls"] = [{"id": call["id"], "type": "function", "function": {
                "name": fn["name"], "arguments": json.dumps(args, sort_keys=True, separators=(",", ":"))}}]
        return out

    def assistant(self, message):
        self.messages.append(self.canonical(message))
        calls = message.get("tool_calls") or []
        self.pending_id = calls[0]["id"] if calls else None


class Record(SimpleNamespace):
    """Small attribute/model_dump-compatible ChatCompletion wire objects."""
    def model_dump(self, *, exclude_none=False, **kwargs):
        def plain(value):
            if isinstance(value, Record):
                return {k: plain(v) for k, v in vars(value).items() if not exclude_none or v is not None}
            if isinstance(value, list):
                return [plain(v) for v in value]
            return value
        return plain(self)


def record(value):
    if isinstance(value, dict):
        return Record(**{k: record(v) for k, v in value.items()})
    if isinstance(value, list):
        return [record(v) for v in value]
    return value


def save(path, value):
    """Atomic exclusive IPC write (the server has no authority over tool paths)."""
    temporary = path.with_name(path.name + ".writing")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def usage(value):
    keys = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    if not isinstance(value, dict) or not all(type(value.get(k, 0)) is int and value.get(k, 0) >= 0 for k in keys):
        raise ProviderError("invalid runtime usage")
    if not all(k in value for k in ("input_tokens", "output_tokens")):
        return None  # unavailable, not zero
    prompt = sum(value.get(k, 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return {"prompt_tokens": prompt, "completion_tokens": value["output_tokens"],
            "total_tokens": prompt + value["output_tokens"], "prompt_tokens_details": {
                "cached_tokens": value.get("cache_read_input_tokens", 0),
                "cache_write_tokens": value.get("cache_creation_input_tokens", 0)}}


class Message:
    """One real streamed assistant message, not a canned completion rechunked."""
    def __init__(self):
        self.id = None
        self.blocks = {}
        self.text = ""
        self.stop = None
        self.done = False
        self.snapshot = None
        self.usage = {}
        self.call = None
        self.argument_fragments = []

    def feed(self, obj):
        kind = obj.get("type")
        if kind == "assistant":
            msg = obj.get("message", {})
            if obj.get("error") or msg.get("model") != MODEL or self.snapshot is not None:
                raise ProviderError("runtime assistant error, duplicate snapshot or unexpected model")
            self.snapshot = msg
            self.usage.update(msg.get("usage") or {})
            return []
        if kind != "stream_event":
            return []
        ev = obj.get("event", {})
        event = ev.get("type")
        if event == "message_start":
            msg = ev.get("message", {})
            if self.id is not None or msg.get("model") != MODEL or not isinstance(msg.get("id"), str) or not msg["id"]:
                raise ProviderError("unexpected/duplicate streamed message or model")
            self.id = msg["id"]
            self.usage.update(msg.get("usage") or {})
            return [{"role": "assistant"}]
        if not self.id or self.done:
            raise ProviderError("event outside message boundary")
        index = ev.get("index")
        if event == "content_block_start":
            block = ev.get("content_block", {})
            if type(index) is not int or index in self.blocks:
                raise ProviderError("invalid/duplicate content block")
            self.blocks[index] = {"kind": block.get("type"), "closed": False}
            if block.get("type") == "tool_use":
                if self.call is not None or not isinstance(block.get("id"), str) or not block["id"] or not isinstance(block.get("name"), str):
                    raise ProviderError("parallel, duplicate or invalid runtime tool calls")
                self.call = {"id": block["id"], "name": block["name"], "arguments": block.get("input", {})}
            elif block.get("type") not in ("text", "thinking", "redacted_thinking"):
                raise ProviderError("unsupported runtime content block")
            if block.get("type") == "text" and block.get("text"):
                self.text += block["text"]
                return [{"content": block["text"]}]
        elif event == "content_block_delta":
            block = self.blocks.get(index)
            if block is None or block["closed"]:
                raise ProviderError("delta for missing/closed block")
            delta = ev.get("delta", {})
            if block["kind"] == "tool_use":
                if delta.get("type") != "input_json_delta" or not isinstance(delta.get("partial_json"), str):
                    raise ProviderError("invalid tool argument delta")
                self.argument_fragments.append(delta["partial_json"])
                return []  # serial validation fence: no tool escapes a partial message
            if block["kind"] == "text":
                if delta.get("type") != "text_delta" or not isinstance(delta.get("text"), str):
                    raise ProviderError("invalid text delta")
                self.text += delta["text"]
                return [{"content": delta["text"]}]
            if delta.get("type") not in ("thinking_delta", "signature_delta"):
                raise ProviderError("unsupported thinking delta")
        elif event == "content_block_stop":
            block = self.blocks.get(index)
            if block is None or block["closed"]:
                raise ProviderError("duplicate/missing block stop")
            block["closed"] = True
            if block["kind"] == "tool_use" and self.argument_fragments:
                self.call["arguments"] = json.loads("".join(self.argument_fragments))
                if not isinstance(self.call["arguments"], dict):
                    raise ProviderError("tool arguments must be an object")
        elif event == "message_delta":
            self.stop = ev.get("delta", {}).get("stop_reason")
            self.usage.update(ev.get("usage") or {})
        elif event == "message_stop":
            if any(not b["closed"] for b in self.blocks.values()) or self.snapshot is None:
                raise ProviderError("incomplete assistant message")
            if self.stop not in ("end_turn", "max_tokens", "tool_use") or bool(self.call) != (self.stop == "tool_use"):
                raise ProviderError("runtime refusal or unsupported stop reason")
            text = "".join(b.get("text", "") for b in self.snapshot.get("content", []) if b.get("type") == "text")
            if text != self.text or self.snapshot.get("id") != self.id:
                raise ProviderError("stream/snapshot content or identity mismatch")
            tools = [b for b in self.snapshot.get("content", []) if b.get("type") == "tool_use"]
            expected = [{"type": "tool_use", "id": self.call["id"], "name": self.call["name"], "input": self.call["arguments"]}] if self.call else []
            if [{k: b.get(k) for k in ("type", "id", "name", "input")} for b in tools] != expected:
                raise ProviderError("stream/snapshot tool identity or arguments mismatch")
            self.done = True
        else:
            raise ProviderError("unknown assistant stream event")
        return []


class Runtime:
    """One process group with a hard session deadline, including parked time."""
    def __init__(self, argv, env, directory):
        self.directory = directory
        self.lock = threading.Lock()
        self.cleanup = None
        self.started = time.monotonic()
        self.process = subprocess.Popen(argv, cwd=directory, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.buffer = b""
        self.stderr_bytes = 0
        self.total = 0
        for pipe in (self.process.stdout, self.process.stderr):
            assert pipe is not None
            os.set_blocking(pipe.fileno(), False)
            self.selector.register(pipe, selectors.EVENT_READ)

    def send(self, text):
        data = json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n"
        assert self.process.stdin is not None
        self.process.stdin.write(data.encode())
        self.process.stdin.flush()

    def read(self):
        if b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            return json.loads(line)
        for key, _ in self.selector.select(0.01):
            data = os.read(key.fd, 65536)
            if not data:
                self.selector.unregister(key.fileobj)
                continue
            self.total += len(data)
            if self.total > 4_000_000:
                raise ProviderError("runtime output bound exceeded")
            if key.fileobj is self.process.stderr:
                self.stderr_bytes += len(data)  # never store arbitrary stderr/account data
            else:
                self.buffer += data
        if self.process.poll() is not None and not self.selector.get_map() and not self.buffer:
            raise ProviderError("runtime process died before the next complete response")
        if self.process.poll() is not None and not self.selector.get_map() and b"\n" not in self.buffer:
            raise ProviderError("malformed/truncated runtime JSON")
        return None

    def group_exists(self):
        try:
            os.killpg(self.process.pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            result = subprocess.run(["/bin/ps", "-g", str(self.process.pid), "-o", "pid="], capture_output=True, timeout=2)
            if result.returncode not in (0, 1) or result.stderr:
                raise ProviderError("cannot establish owned process group state")
            return bool(result.stdout.strip())

    def close(self):
        with self.lock:
            if self.cleanup is not None:
                return self.cleanup
            (self.directory / "cancel").touch(mode=0o600, exist_ok=True)
            for sig, seconds in ((signal.SIGTERM, 4), (signal.SIGKILL, 0.5)):
                try:
                    os.killpg(self.process.pid, sig)
                except ProcessLookupError:
                    pass
                end = time.monotonic() + seconds
                while time.monotonic() < end:
                    self.process.poll()
                    if not self.group_exists():
                        break
                    time.sleep(0.01)
            self.process.wait(timeout=0.5)
            # read() can be running on another thread; the client cancellation event
            # makes it unwind. Only close pipe FDs after its create lock is released.
            self.cleanup = {"pid": self.process.pid, "reaped": self.process.poll() is not None,
                            "group_absent": not self.group_exists(), "exit": self.process.returncode}
            return self.cleanup

    def dispose(self):
        self.selector.close()
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            if pipe is not None:
                pipe.close()


class Stream:
    def __init__(self, client, iterator):
        self.client, self.iterator, self.finished = client, iterator, False

    def __iter__(self):
        return self

    def __next__(self):
        if self.finished:
            raise StopIteration
        try:
            return next(self.iterator)
        except BaseException:
            self.finished = True
            self.client._busy.release()
            self.client._dispose_if_closed()
            raise

    def close(self):
        if not self.finished:
            self.client.cancel()
            self.iterator.close()
            self.finished = True
            self.client._busy.release()
            self.client._dispose_if_closed()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ClaudeSubscriptionClient:
    HERMES_SKIP_TRANSPORT_WRAP = True
    # Prevent an HTTP AsyncOpenAI rebuild. create() rejects running-event-loop
    # callers before effects; this flag does NOT advertise async support.
    HERMES_SKIP_ASYNC_WRAP = True

    def __init__(self, *, command=None, args=None, timeout=None, **kwargs):
        self.api_key = "claude-subscription"  # routing placeholder, never a credential
        self.base_url = "acp://claude-subscription"
        self.command, self.args, self.timeout = command or "claude", args or [], timeout
        self._busy = threading.Lock()
        self._closed = threading.Event()
        self._runtime = None
        self._temporary = None
        self._timer = None
        self._history = History()
        self._scope = None
        self._tools = None
        self._inputs = self._turns = 0
        self._pending = None
        self._sequence = 0
        self._seen_ids = set()
        self._last_response = None
        self.audit = []
        self.chat = SimpleNamespace(completions=self)

    def is_closed(self):
        return self._closed.is_set()

    def _validate(self, kwargs):
        if kwargs.get("model") != MODEL:
            raise ProviderError("claude-subscription requires exact model claude-opus-5-5")
        allowed = {"model", "messages", "tools", "stream", "stream_options", "timeout", "max_tokens",
                   "max_completion_tokens", "parallel_tool_calls", "tool_choice", "extra_body"}
        if set(kwargs) - allowed:
            raise ProviderError("unsupported completion options: " + ", ".join(sorted(set(kwargs) - allowed)))
        if kwargs.get("parallel_tool_calls") not in (None, False) or kwargs.get("tool_choice", "auto") != "auto":
            raise ProviderError("only automatic serial tool calls are supported")
        if kwargs.get("stream_options", {"include_usage": True}) != {"include_usage": True}:
            raise ProviderError("unsupported stream options")
        for key in ("max_tokens", "max_completion_tokens"):
            if key in kwargs and kwargs[key] != 1024:
                raise ProviderError("this bounded provider supports only a 1024-token requested cap")
        if self.args:
            raise ProviderError("arbitrary runtime arguments are unsupported")
        response_seconds(kwargs.get("timeout", self.timeout))
        messages = kwargs.get("messages")
        if self._inputs >= 2 and isinstance(messages, list) and messages and messages[-1].get("role") == "user":
            raise ProviderError("two-user-input session limit; start a new client")
        body = kwargs.get("extra_body") or {}
        if not isinstance(body, dict) or set(body) - {"subscription_session_id"}:
            raise ProviderError("unsupported extra_body configuration")
        scope = (os.getcwd(), os.environ.get("HERMES_HOME"), os.environ.get("HERMES_PROFILE"),
                 os.environ.get("HERMES_KANBAN_TASK"), body.get("subscription_session_id"))
        tools = convert_tools(kwargs.get("tools"))
        if self._scope is not None and (scope != self._scope or tools != self._tools):
            raise ProviderError("session/worktree/profile or tool schema changed; use a separate client")
        return scope, tools

    def create(self, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise ProviderError("synchronous claude-subscription client does not support async helpers")
        if not self._busy.acquire(blocking=False):
            raise ProviderError("concurrent create on a serial client")
        try:
            if self.is_closed():
                raise ProviderError("client closed or cancelled; no retry/resume")
            scope, tools = self._validate(kwargs)
            tail = self._history.accept(kwargs.get("messages"))
            self._scope, self._tools = scope, tools
            stream = Stream(self, self._drive(tail, kwargs))
        except BaseException:
            self._busy.release()
            raise
        if kwargs.get("stream", False):
            return stream
        for _ in stream:
            pass
        return self._last_response

    def _environment(self, directory):
        env = {k: os.environ[k] for k in ("HOME", "PATH", "LANG", "TMPDIR") if k in os.environ}
        env.update({"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL": "1",
                    "CLAUDE_CODE_PLUGIN_CACHE_DIR": str(directory / "empty-plugins"), "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
                    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1", "CLAUDE_CODE_DISABLE_CRON": "1",
                    "CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK": "1", "CLAUDE_CODE_MAX_RETRIES": "0",
                    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "1024", "DISABLE_AUTO_COMPACT": "1",
                    "ENABLE_CLAUDEAI_MCP_SERVERS": "false", "ENABLE_TOOL_SEARCH": "false"})
        return env

    def _start(self):
        assert self._tools is not None
        root = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes") / "cache/claude-subscription"
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._temporary = tempfile.TemporaryDirectory(prefix="session-", dir=root)
        directory = Path(self._temporary.name)
        (directory / "empty-plugins").mkdir(mode=0o700)
        env = self._environment(directory)
        check = subprocess.run([self.command, "--version"], env=env, cwd=directory, capture_output=True, timeout=10)
        if check.returncode != 0 or check.stdout.strip() != b"2.1.283 (Claude Code)":
            raise ProviderError("untested Claude CLI version; required 2.1.283")
        settings = {"disableAllHooks": True, "autoMemoryEnabled": False, "syncClaudeAiPlugins": False,
                    "claudeMdExcludes": ["**"], "enabledPlugins": {}}
        save(directory / "settings.json", settings)
        save(directory / "bridge.json", {"tools": self._tools, "deadline": time.time() + 150})
        config = {"mcpServers": {"hermes": {"type": "stdio", "command": sys.executable,
                  "args": ["-I", "-S", str(Path(__file__).with_name("mcp_server.py")), str(directory)],
                  "env": {"HOME": str(directory), "PATH": "/usr/bin:/bin"}}}} if self._tools else {"mcpServers": {}}
        save(directory / "mcp.json", config)
        system = self._history.messages[0]["content"] if self._history.messages[0]["role"] == "system" else ""
        argv = [self.command, "--print", "--model", MODEL, "--effort", "low", "--max-turns", "3",
                "--input-format", "stream-json", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
                "--no-session-persistence", "--restricted", "--setting-sources", "", "--settings", str(directory / "settings.json"),
                "--disable-slash-commands", "--no-chrome", "--tools", "", "--strict-mcp-config", "--mcp-config", str(directory / "mcp.json"),
                "--allowedTools", ",".join(PREFIX + t["name"] for t in self._tools), "--permission-mode", "dontAsk",
                "--permission-prompts", "none", "--system-prompt", system]
        if self.is_closed():
            raise ProviderError("cancelled during startup")
        self._runtime = Runtime(argv, env, directory)
        if self.is_closed():
            self._runtime.close()
            raise ProviderError("cancelled during process startup")
        self._timer = threading.Timer(150, self.cancel)
        self._timer.daemon = True
        self._timer.start()
        self.audit.append({"stage": "launch", "pid": self._runtime.process.pid, "model": MODEL})

    def _drive(self, tail, kwargs):
        try:
            if self._runtime is None:
                self._start()
            runtime = self._runtime
            assert runtime is not None and self._tools is not None
            deadline = time.monotonic() + response_seconds(kwargs.get("timeout", self.timeout))
            if tail["role"] == "tool":
                if self._pending is None or tail["tool_call_id"] != self._pending["tool_use_id"]:
                    raise ProviderError("missing/mismatched parked invocation")
                delivery = {**self._pending, "text": tail["content"]}
                save(runtime.directory / f"result-{self._sequence}.json", delivery)
                self.audit.append({"stage": "result_delivered", "tool_use_id": tail["tool_call_id"],
                                   "rpc_id": delivery["rpc_id"], "text_sha256": hashlib.sha256(tail["content"].encode()).hexdigest()})
                self._sequence += 1
                self._pending = None
            else:
                if self._inputs >= 2:
                    raise ProviderError("two-user-input session limit; start a new client")
                self._inputs += 1
                runtime.send(tail["content"])
                self.audit.append({"stage": "user_input", "number": self._inputs})
            message = Message()
            initialized = bool(self._turns)
            while True:
                if self.is_closed():
                    raise ProviderError("client cancelled or session timed out")
                if time.monotonic() >= deadline:
                    raise ProviderError("runtime response timed out")
                if message.done and message.call:
                    pending_path = runtime.directory / f"call-{self._sequence}.json"
                    if pending_path.exists():
                        pending = json.loads(pending_path.read_text())
                        call = message.call
                        if (call["id"] in self._seen_ids or call["name"] != PREFIX + pending.get("name", "")
                                or pending.get("name") not in {t["name"] for t in self._tools}
                                or call["arguments"] != pending.get("arguments") or type(pending.get("rpc_id")) not in (str, int)):
                            raise ProviderError("unmatched/replayed/unadvertised model and MCP invocation")
                        self._seen_ids.add(call["id"])
                        self._pending = {"rpc_id": pending["rpc_id"], "tool_use_id": call["id"]}
                        self._turns += 1
                        if self._turns >= 4:
                            raise ProviderError("session turn budget cannot accommodate tool continuation")
                        native_call = {"id": call["id"], "type": "function", "function": {
                            "name": pending["name"], "arguments": json.dumps(call["arguments"], sort_keys=True, separators=(",", ":"))}}
                        assistant = {"role": "assistant", "content": message.text, "tool_calls": [native_call]}
                        self._history.assistant(assistant)
                        self._last_response = record({"id": message.id, "object": "chat.completion", "created": int(time.time()),
                            "model": MODEL, "choices": [{"index": 0, "message": assistant, "finish_reason": "tool_calls"}], "usage": usage(message.usage)})
                        self.audit.append({"stage": "tool_parked", "tool_use_id": call["id"], "rpc_id": pending["rpc_id"],
                                           "name": pending["name"], "arguments": call["arguments"], "model": MODEL})
                        yield self._chunk(message, {"tool_calls": [{"index": 0, "id": call["id"], "type": "function",
                                                      "function": {"name": pending["name"], "arguments": ""}}]})
                        for fragment in message.argument_fragments or [json.dumps(call["arguments"])]:
                            yield self._chunk(message, {"tool_calls": [{"index": 0, "function": {"arguments": fragment}}]})
                        yield self._chunk(message, {}, finish="tool_calls", token_usage=usage(message.usage))
                        return
                obj = runtime.read()
                if obj is None:
                    continue
                if not isinstance(obj, dict) or obj.get("parent_tool_use_id"):
                    raise ProviderError("malformed runtime event or unexpected subagent")
                kind = obj.get("type")
                if kind == "system" and obj.get("subtype") == "init":
                    expected = {PREFIX + t["name"] for t in self._tools}
                    if obj.get("model") != MODEL or set(obj.get("tools", [])) != expected or obj.get("apiKeySource") != "none":
                        raise ProviderError("unexpected runtime model/auth source/executor")
                    if obj.get("claude_code_version") != "2.1.283":
                        raise ProviderError("unexpected runtime version")
                    initialized = True
                    self.audit.append({"stage": "init", "model": obj["model"], "tools": obj["tools"]})
                elif kind in ("assistant", "stream_event"):
                    if not initialized:
                        raise ProviderError("model event before verified initialization")
                    for delta in message.feed(obj):
                        yield self._chunk(message, delta)
                elif kind == "result":
                    if not message.done or message.call or obj.get("is_error") or obj.get("subtype") != "success" or obj.get("permission_denials"):
                        raise ProviderError("runtime quota/refusal/permission/turn error or incomplete result")
                    self._turns += 1
                    if self._turns > 4 or type(obj.get("num_turns")) is not int or obj["num_turns"] > 3:
                        raise ProviderError("runtime model-turn bound exceeded")
                    meta = obj.get("modelUsage") or {}
                    if any(k != MODEL or v.get("canonicalModel", MODEL) != MODEL or v.get("provider") != "firstParty" for k, v in meta.items()):
                        raise ProviderError("unexpected result model/provider")
                    self.audit.append({"stage": "result", "num_turns": obj["num_turns"], "modelUsage": meta, "usage": obj.get("usage")})
                    finish = "length" if message.stop == "max_tokens" else "stop"
                    assistant = {"role": "assistant", "content": message.text}
                    self._history.assistant(assistant)
                    self._last_response = record({"id": message.id, "object": "chat.completion", "created": int(time.time()),
                        "model": MODEL, "choices": [{"index": 0, "message": {**assistant, "tool_calls": None}, "finish_reason": finish}],
                        "usage": usage(message.usage), "runtime_metadata": {"usage": obj.get("usage"), "modelUsage": meta}})
                    yield self._chunk(message, {}, finish=finish, token_usage=usage(message.usage))
                    return
                elif kind == "rate_limit_event":
                    if obj.get("rate_limit_info", {}).get("status") == "rejected":
                        raise ProviderError("runtime subscription rate limit rejected; no retry or substitute")
                elif kind not in ("system", "user"):
                    raise ProviderError("unknown runtime event")
        except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError) as exc:
            self.cancel()
            raise ProviderError("runtime startup, I/O or malformed protocol: " + type(exc).__name__) from None
        except BaseException:
            self.cancel()
            raise

    def _chunk(self, message, delta, *, finish=None, token_usage=None):
        return record({"id": message.id, "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL,
                       "choices": [{"index": 0, "delta": delta, "finish_reason": finish}], "usage": token_usage})

    def cancel(self):
        self._closed.set()
        if self._timer is not None:
            self._timer.cancel()
        if self._runtime is not None:
            self._runtime.close()

    def _dispose_if_closed(self):
        if self.is_closed():
            if self._runtime is not None:
                self._runtime.dispose()
            if self._temporary is not None:
                self._temporary.cleanup()

    def close(self):
        self.cancel()
        if self._busy.acquire(blocking=False):
            try:
                self._dispose_if_closed()
            finally:
                self._busy.release()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
