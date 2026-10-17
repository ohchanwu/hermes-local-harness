"""Serial subscription CLI client. No runtime or Hermes I/O on import."""
import asyncio
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

from .bridge import save
from . import compat
from .compat import CHILD_ENV, CLI_FLAGS, CLI_MINIMUM, CLI_TESTED, PREFIX, SETTINGS, served_names, version_text
from .errors import ProviderError
from .history import History
from .runtime import Runtime
from .stream_events import Message
from .translate import convert_tools, record, usage

__all__ = ["ClaudeSubscriptionClient", "ProviderError", "History", "Message", "Runtime", "convert_tools",
           "record", "usage", "save", "PREFIX"]

log = logging.getLogger(__name__)


def parse_version(output):
    match = re.fullmatch(rb"(\d+)\.(\d+)\.(\d+) \(Claude Code\)", output.strip())
    if match is None:
        raise ProviderError("unrecognized Claude CLI version output")
    return tuple(int(part) for part in match.groups())


def response_seconds(value):
    if value is None:
        return 60
    seconds = value if type(value) in (int, float) else getattr(value, "read", None)
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
        raise ProviderError("invalid response timeout")
    return min(seconds, 150)


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
        self._lifecycle = threading.RLock()
        self._closed = threading.Event()
        self._startup = None
        self._runtime = None
        self._temporary = None
        self._timer = None
        self._cli_version = None
        self._model = None
        self._session_deadline = self._request_deadline = None
        self._process_env = None
        self._home = None
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

    @staticmethod
    def _current_scope(session_id):
        return (os.getcwd(), os.environ.get("HERMES_HOME"), os.environ.get("HERMES_PROFILE"),
                os.environ.get("HERMES_KANBAN_TASK"), os.environ.get("HOME"),
                os.environ.get("HERMES_KANBAN_WORKSPACE"), session_id)

    def _check_active(self):
        if self.is_closed():
            raise ProviderError("client closed or cancelled; no retry/resume")
        if self._scope is None or self._current_scope(self._scope[-1]) != self._scope:
            raise ProviderError("session/worktree/profile changed during execution; use a separate client")
        now = time.monotonic()
        if self._session_deadline is not None and now >= self._session_deadline:
            raise ProviderError("runtime session timed out")
        if self._request_deadline is not None and now >= self._request_deadline:
            raise ProviderError("runtime response timed out")

    def _validate(self, kwargs):
        model = kwargs.get("model")
        if not isinstance(model, str) or model not in compat.MODELS:
            raise ProviderError("claude-subscription requires an exact model id from its allowlist: "
                                + ", ".join(sorted(compat.MODELS)))
        if self._model is not None and model != self._model:
            raise ProviderError("model changed; use a separate client")
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
        session_id = body.get("subscription_session_id")
        if session_id is not None and (not isinstance(session_id, str) or not session_id):
            raise ProviderError("subscription session id must be nonempty text")
        scope = self._current_scope(session_id)
        tools = convert_tools(kwargs.get("tools"))
        if self._scope is not None and (scope != self._scope or tools != self._tools):
            raise ProviderError("session/worktree/profile or tool schema changed; use a separate client")
        return model, scope, tools

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
            model, scope, tools = self._validate(kwargs)
            tail = self._history.accept(kwargs.get("messages"))
            self._model, self._scope, self._tools = model, scope, tools
            if self._process_env is None:
                self._process_env = {k: os.environ[k] for k in ("HOME", "PATH", "LANG", "TMPDIR") if k in os.environ}
                self._home = Path(scope[1] or Path(scope[4] or Path.home()) / ".hermes").absolute()
            stream = Stream(self, self._drive(tail, response_seconds(kwargs.get("timeout", self.timeout))))
        except BaseException:
            self._busy.release()
            raise
        if kwargs.get("stream", False):
            return stream
        for _ in stream:
            pass
        return self._last_response

    def _environment(self, directory):
        assert self._process_env is not None
        env = dict(self._process_env)
        env.update(CHILD_ENV)
        env["CLAUDE_CODE_PLUGIN_CACHE_DIR"] = str(directory / "empty-plugins")
        return env

    def _start(self):
        assert self._tools is not None
        assert self._home is not None and self._session_deadline is not None
        # Serialize ownership registration with cancel(), not the blocking read.
        # Paths and child environment are bound at create(), never a later home.
        with self._lifecycle:
            self._check_active()
            root = self._home / "cache/claude-subscription"
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._temporary = tempfile.TemporaryDirectory(prefix="session-", dir=root)
            directory = Path(self._temporary.name)
            (directory / "empty-plugins").mkdir(mode=0o700)
            env = self._environment(directory)
            self._check_active()
            self._startup = Runtime([self.command, "--version"], env, directory, cancel_mailbox=False)
        try:
            code, output = self._startup.version_output(time.monotonic() + 10, self._check_active)
        finally:
            self._startup.close()
            self._startup.dispose()
        if code != 0:
            raise ProviderError("Claude CLI version check failed")
        self._cli_version = parse_version(output)
        if self._cli_version < CLI_MINIMUM:
            raise ProviderError(f"Claude CLI {version_text(self._cli_version)} is older than the minimum "
                                + version_text(CLI_MINIMUM))
        if self._cli_version not in CLI_TESTED:
            self.audit.append({"stage": "untested_cli", "version": version_text(self._cli_version)})
            log.warning("untested Claude CLI %s; run smoke.py against it", version_text(self._cli_version))
        settings = SETTINGS
        config = {"mcpServers": {"hermes": {"type": "stdio", "command": sys.executable,
                  "args": ["-I", "-S", str(Path(__file__).with_name("mcp_server.py")), str(directory)],
                  "env": {"HOME": str(directory), "PATH": "/usr/bin:/bin"}}}} if self._tools else {"mcpServers": {}}
        system = self._history.messages[0]["content"] if self._history.messages[0]["role"] == "system" else ""
        argv = [self.command, *CLI_FLAGS, "--model", self._model, "--settings", str(directory / "settings.json"),
                "--mcp-config", str(directory / "mcp.json"), "--allowedTools", ",".join(PREFIX + t["name"] for t in self._tools),
                "--system-prompt", system]
        with self._lifecycle:
            self._check_active()
            save(directory / "settings.json", settings)
            save(directory / "bridge.json", {"tools": self._tools,
                 "deadline": time.time() + max(0, self._session_deadline - time.monotonic())})
            save(directory / "mcp.json", config)
            self._check_active()
            self._runtime = Runtime(argv, env, directory)
            self.audit.append({"stage": "launch", "pid": self._runtime.process.pid, "model": self._model})

    def _drive(self, tail, seconds):
        try:
            with self._lifecycle:
                self._request_deadline = time.monotonic() + seconds
                self._check_active()  # a deferred closed/drifted stream has no startup effects
                if self._session_deadline is None:
                    self._session_deadline = time.monotonic() + 150
                    self._timer = threading.Timer(150, self.cancel)
                    self._timer.daemon = True
                    self._timer.start()
            if self._runtime is None:
                self._start()
            runtime = self._runtime
            assert runtime is not None and self._tools is not None
            with self._lifecycle:
                self._check_active()
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
            if tail["role"] != "tool":
                self._check_active()
                # A full pipe must not hold the ownership lock and prevent
                # cancel() from killing/reaping the reader to unblock this write.
                runtime.send(tail["content"], self._check_active)
                self.audit.append({"stage": "user_input", "number": self._inputs})
            served = served_names(self._model)
            message = Message(served)
            initialized = bool(self._turns)
            while True:
                self._check_active()
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
                            "model": self._model, "choices": [{"index": 0, "message": assistant, "finish_reason": "tool_calls"}], "usage": usage(message.usage)})
                        self.audit.append({"stage": "tool_parked", "tool_use_id": call["id"], "rpc_id": pending["rpc_id"],
                                           "name": pending["name"], "arguments": call["arguments"], "model": self._model})
                        yield self._chunk(message, {"tool_calls": [{"index": 0, "id": call["id"], "type": "function",
                                                      "function": {"name": pending["name"], "arguments": ""}}]})
                        for fragment in message.argument_fragments or [json.dumps(call["arguments"])]:
                            yield self._chunk(message, {"tool_calls": [{"index": 0, "function": {"arguments": fragment}}]})
                        yield self._chunk(message, {}, finish="tool_calls", token_usage=usage(message.usage))
                        return
                try:
                    obj = runtime.read()
                except ProviderError as exc:
                    if initialized:
                        raise
                    raise ProviderError(f"{exc} (before initialization; an upgraded Claude CLI "
                                        f"{version_text(self._cli_version)} may reject a flag: run smoke.py)") from None
                if obj is None:
                    continue
                if not isinstance(obj, dict) or obj.get("parent_tool_use_id"):
                    raise ProviderError("malformed runtime event or unexpected subagent")
                kind = obj.get("type")
                if kind == "system" and obj.get("subtype") == "init":
                    expected = {PREFIX + t["name"] for t in self._tools}
                    if obj.get("model") not in served or set(obj.get("tools", [])) != expected or obj.get("apiKeySource") != "none":
                        raise ProviderError("unexpected runtime model/auth source/executor")
                    if obj.get("claude_code_version") != version_text(self._cli_version):
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
                    if any(k not in served or v.get("canonicalModel", k) not in served or v.get("provider") != "firstParty" for k, v in meta.items()):
                        raise ProviderError("unexpected result model/provider")
                    self.audit.append({"stage": "result", "num_turns": obj["num_turns"], "modelUsage": meta, "usage": obj.get("usage")})
                    finish = "length" if message.stop == "max_tokens" else "stop"
                    assistant = {"role": "assistant", "content": message.text}
                    self._history.assistant(assistant)
                    self._last_response = record({"id": message.id, "object": "chat.completion", "created": int(time.time()),
                        "model": self._model, "choices": [{"index": 0, "message": {**assistant, "tool_calls": None}, "finish_reason": finish}],
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
        self._check_active()  # recheck even between deferred tool-argument chunks
        return record({"id": message.id, "object": "chat.completion.chunk", "created": int(time.time()), "model": self._model,
                       "choices": [{"index": 0, "delta": delta, "finish_reason": finish}], "usage": token_usage})

    def cancel(self):
        with self._lifecycle:
            self._closed.set()
            if self._timer is not None:
                self._timer.cancel()
            children = (self._startup, self._runtime)
        for child in children:
            if child is not None:
                child.close()

    def _dispose_if_closed(self):
        if self.is_closed():
            if self._startup is not None:
                self._startup.dispose()
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
