"""Serial subscription CLI client. No runtime or Hermes I/O on import."""
import asyncio
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import pwd
import re
import selectors
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

from .bridge import LINE_BOUND, Bridge, save
from . import compat
from .compat import CHILD_ENV, CLI_FLAGS, CLI_SETTING, DEFAULT_EFFORT, EFFORT_SETTING, EFFORTS, CLI_MINIMUM, CLI_TESTED, PREFIX, SETTINGS, served_names, version_text
from .errors import ProviderError
from .history import History
from .runtime import Runtime
from .stream_events import Message
from .transcript import render_restored
from .translate import convert_tools, record, usage

__all__ = ["ClaudeSubscriptionClient", "Bridge", "ProviderError", "History", "Message", "Runtime", "convert_tools", "render_restored",
           "record", "usage", "save", "PREFIX"]

log = logging.getLogger(__name__)


def parse_version(output):
    match = re.fullmatch(rb"(\d+)\.(\d+)\.(\d+) \(Claude Code\)", output.strip())
    if match is None:
        raise ProviderError("unrecognized Claude CLI version output")
    return tuple(int(part) for part in match.groups())


def response_seconds(value):
    if value is None:
        return 300
    seconds = value if type(value) in (int, float) else getattr(value, "read", None)
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
        raise ProviderError("invalid response timeout")
    return seconds


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
        self.command, self.args, self.timeout = command or os.environ.get(CLI_SETTING), args or [], timeout
        self._busy = threading.Lock()
        self._lifecycle = threading.RLock()
        self._closed = threading.Event()
        self._startup = None
        self._runtime = None
        self._bridge = None
        self._temporary = None
        self._cli_version = None
        self._model = None
        self._request_deadline = None
        self._max_output = self._effort = None
        self._initialized = False
        self._process_env = None
        self._home = None
        self._history = History()
        self._scope = None
        self._tools = None
        self._inputs = 0
        self._pending = None
        self._sequence = 0
        self._delivered = []
        self._seen_ids = set()
        self._last_response = None
        self.audit = []
        self.chat = SimpleNamespace(completions=self)

    def is_closed(self):
        return self._closed.is_set()

    @staticmethod
    def _current_scope(session_id):
        try:
            cwd = os.getcwd()
        except FileNotFoundError:
            # e.g. Kanban removes a finished task's scratch workspace under its worker
            raise ProviderError("working directory was removed; the task scope has ended") from None
        return (cwd, os.environ.get("HERMES_HOME"), os.environ.get("HERMES_PROFILE"),
                os.environ.get("HERMES_KANBAN_TASK"), os.environ.get("HOME"),
                os.environ.get("HERMES_KANBAN_WORKSPACE"), session_id)

    def _check_active(self):
        if self.is_closed():
            raise ProviderError("client closed or cancelled; no retry/resume")
        if self._scope is None or self._current_scope(self._scope[-1]) != self._scope:
            raise ProviderError("session/worktree/profile changed during execution; use a separate client")
        now = time.monotonic()
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
        caps = {kwargs[key] for key in ("max_tokens", "max_completion_tokens") if kwargs.get(key) is not None}
        if len(caps) > 1 or any(type(cap) is not int or cap <= 0 for cap in caps):
            raise ProviderError("invalid output token cap")
        max_output = caps.pop() if caps else None
        if self._model is not None and max_output != self._max_output:
            raise ProviderError("output token cap changed; use a separate client")
        effort = os.environ.get(EFFORT_SETTING) or DEFAULT_EFFORT
        if effort not in EFFORTS:
            raise ProviderError(f"invalid effort setting {EFFORT_SETTING}; use one of: " + ", ".join(EFFORTS))
        if self.args:
            raise ProviderError("arbitrary runtime arguments are unsupported")
        response_seconds(kwargs.get("timeout", self.timeout))
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
        return model, scope, tools, max_output, effort

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
            model, scope, tools, max_output, effort = self._validate(kwargs)
            # Never fall back to the interactive `claude` on PATH: it updates itself.
            # A bare name would be resolved through PATH, so only absolute paths count.
            if not self.command:
                raise ProviderError(f"no Claude CLI configured; set {CLI_SETTING} to the provider's dedicated install")
            if not os.path.isabs(self.command) or not os.path.isabs(os.environ.get(CLI_SETTING) or self.command):
                raise ProviderError(f"{CLI_SETTING} must be an absolute path to the provider's dedicated install")
            if self._process_env is None:
                # The CLI finds the subscription login through the OS account: USER/LOGNAME
                # for the macOS Keychain and the real HOME for its config. Kanban workers
                # drop USER and run with HOME set to the profile's home, so ask the OS.
                try:
                    account = pwd.getpwuid(os.getuid())
                except KeyError:
                    raise ProviderError("cannot determine the login user for the Claude CLI's Keychain lookup") from None
            tail = self._history.accept(kwargs.get("messages"))
            self._model, self._scope, self._tools = model, scope, tools
            if self._effort is None:
                self._max_output, self._effort = max_output, effort
            if self._process_env is None:
                self._process_env = {k: os.environ[k] for k in ("PATH", "LANG", "TMPDIR") if os.environ.get(k)}
                self._process_env.update(HOME=account.pw_dir, USER=account.pw_name, LOGNAME=account.pw_name)
                # It reads the Keychain through /usr/bin/security, so system dirs must be on PATH.
                path = [d for d in self._process_env.get("PATH", "").split(":") if d]
                self._process_env["PATH"] = ":".join(path + [d for d in ("/usr/bin", "/bin") if d not in path])
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
        if self._max_output is not None:
            env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(self._max_output)
        return env

    def _start(self):
        assert self._tools is not None
        assert self._home is not None
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
            self._startup = Runtime([self.command, "--version"], env, directory)
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
        system = self._history.messages[0]["content"] if self._history.messages[0]["role"] == "system" else ""
        argv = [self.command, *CLI_FLAGS, "--model", self._model, "--effort", self._effort, "--settings", str(directory / "settings.json"),
                "--mcp-config", str(directory / "mcp.json"), "--allowedTools", ",".join(PREFIX + t["name"] for t in self._tools),
                "--system-prompt", system]
        with self._lifecycle:
            self._check_active()
            config = {"mcpServers": {}}
            if self._tools:
                self._bridge = Bridge(self._tools)
                # The token travels in the owner-only config file, never on a visible command line.
                config["mcpServers"]["hermes"] = {"type": "stdio", "command": sys.executable,
                    "args": ["-I", "-S", str(Path(__file__).with_name("mcp_server.py")), str(self._bridge.path)],
                    "env": {"HOME": str(directory), "PATH": "/usr/bin:/bin", "HERMES_BRIDGE_TOKEN": self._bridge.token}}
            save(directory / "settings.json", settings)
            save(directory / "mcp.json", config)
            self._check_active()
            self._runtime = Runtime(argv, env, directory)
            self.audit.append({"stage": "launch", "pid": self._runtime.process.pid, "model": self._model})

    def _drive(self, tail, seconds):
        try:
            with self._lifecycle:
                self._request_deadline = time.monotonic() + seconds
                self._check_active()  # a deferred closed/drifted stream has no startup effects
            if self._runtime is None:
                self._start()
            runtime = self._runtime
            assert runtime is not None and self._tools is not None
            restored, text = self._history.restored, None
            with self._lifecycle:
                self._check_active()
                if restored is not None:
                    # A new client handed an existing transcript replays it as its first input.
                    self._history.restored = None
                    self._inputs += 1
                    text, _ = render_restored(restored, tail)
                elif tail["role"] == "tool":
                    if self._pending is None or tail["tool_call_id"] != self._pending["tool_use_id"] or self._bridge is None:
                        raise ProviderError("missing/mismatched parked invocation")
                    delivery = {"result": self._sequence, **self._pending, "text": tail["content"]}
                    if len(json.dumps(delivery)) >= LINE_BOUND:
                        raise ProviderError("tool result exceeds the MCP bridge line bound; nothing was delivered")
                    self._pending = None
                else:
                    self._inputs += 1
                    text = tail["content"]
            if text is None:
                # Outside the lock: a full socket must not keep cancel() from running.
                self._bridge.send(delivery, self._check_active)
                self._delivered.append({"returned": delivery["result"], "rpc_id": delivery["rpc_id"],
                                        "tool_use_id": delivery["tool_use_id"]})
                self.audit.append({"stage": "result_delivered", "tool_use_id": tail["tool_call_id"],
                                   "rpc_id": delivery["rpc_id"], "text_sha256": hashlib.sha256(tail["content"].encode()).hexdigest()})
                self._sequence += 1
            else:
                self._check_active()
                # A full pipe must not hold the ownership lock and prevent
                # cancel() from killing/reaping the reader to unblock this write.
                try:
                    runtime.send(text, self._check_active, idle=self._pump_bridge)
                except OSError:
                    if self._initialized:
                        raise
                    raise ProviderError(f"runtime exited before reading input (before initialization; an upgraded "
                                        f"Claude CLI {version_text(self._cli_version)} may reject a flag: run smoke.py)") from None
                if restored is not None:
                    self.audit.append({"stage": "rebuild", "messages": len(restored), "tail": tail["role"],
                                       "sha256": hashlib.sha256(text.encode()).hexdigest()})
                    log.warning("claude-subscription rebuilt a session from a %d-message transcript", len(restored))
                else:
                    self.audit.append({"stage": "user_input", "number": self._inputs})
            served = served_names(self._model)
            message = Message(served)
            while True:
                self._check_active()
                self._pump_bridge()
                if message.done and message.call:
                    if self._bridge is not None and not self._bridge.calls:
                        self._bridge.require_open()
                    if self._bridge is not None and self._bridge.calls:
                        pending = self._bridge.calls.pop(0)
                        call = message.call
                        if (pending.get("call") != self._sequence or self._delivered or call["id"] in self._seen_ids or call["name"] != PREFIX + pending.get("name", "")
                                or pending.get("name") not in {t["name"] for t in self._tools}
                                or call["arguments"] != pending.get("arguments") or type(pending.get("rpc_id")) not in (str, int)):
                            raise ProviderError("unmatched/replayed/unadvertised model and MCP invocation")
                        self._seen_ids.add(call["id"])
                        self._pending = {"rpc_id": pending["rpc_id"], "tool_use_id": call["id"]}
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
                    if self._initialized:
                        raise
                    raise ProviderError(f"{exc} (before initialization; an upgraded Claude CLI "
                                        f"{version_text(self._cli_version)} may reject a flag: run smoke.py)") from None
                if obj is None:
                    continue
                self._request_deadline = time.monotonic() + seconds  # idle timeout: any runtime event is activity
                if not isinstance(obj, dict) or obj.get("parent_tool_use_id"):
                    raise ProviderError("malformed runtime event or unexpected subagent")
                kind = obj.get("type")
                if kind == "system" and obj.get("subtype") == "init":
                    expected = {PREFIX + t["name"] for t in self._tools}
                    if obj.get("model") not in served or set(obj.get("tools", [])) != expected or obj.get("apiKeySource") != "none":
                        raise ProviderError("unexpected runtime model/auth source/executor")
                    if obj.get("claude_code_version") != version_text(self._cli_version):
                        raise ProviderError("unexpected runtime version")
                    self._initialized = True
                    self.audit.append({"stage": "init", "model": obj["model"], "tools": obj["tools"]})
                elif kind in ("assistant", "stream_event"):
                    if not self._initialized:
                        raise ProviderError("model event before verified initialization")
                    for delta in message.feed(obj):
                        yield self._chunk(message, delta)
                elif kind == "result":
                    if not message.done or message.call or obj.get("is_error") or obj.get("subtype") != "success" or obj.get("permission_denials"):
                        raise ProviderError("runtime quota/refusal/permission/turn error or incomplete result")
                    if type(obj.get("num_turns")) is not int or obj["num_turns"] < 0:
                        raise ProviderError("invalid runtime turn count")
                    meta = obj.get("modelUsage") or {}
                    if any(k not in served or v.get("canonicalModel", k) not in served or v.get("provider") != "firstParty" for k, v in meta.items()):
                        raise ProviderError("unexpected result model/provider")
                    self._await_returns()
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

    def _pump_bridge(self):
        """Queue bridge messages and match each acknowledgement to its delivered result."""
        if self._bridge is None:
            return
        self._bridge.pump()
        while self._bridge.returns:
            returned = self._bridge.returns.pop(0)
            if not self._delivered or returned != self._delivered.pop(0):
                raise ProviderError("unmatched MCP result acknowledgement")
            self.audit.append({"stage": "result_returned", "rpc_id": returned["rpc_id"], "tool_use_id": returned["tool_use_id"]})

    def _await_returns(self):
        """The server acknowledges right after answering the CLI, so this wait is brief."""
        while self._delivered:
            self._check_active()
            self._pump_bridge()
            if self._delivered:
                self._bridge.require_open()
                self._bridge.wait(selectors.EVENT_READ)

    def cancel(self):
        with self._lifecycle:
            self._closed.set()
            children = (self._startup, self._runtime)
            bridge = self._bridge
        if bridge is not None:
            bridge.shutdown()
        for child in children:
            if child is not None:
                child.close()

    def _dispose_if_closed(self):
        if self.is_closed():
            if self._startup is not None:
                self._startup.dispose()
            if self._runtime is not None:
                self._runtime.dispose()
            if self._bridge is not None:
                self._bridge.close()
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
