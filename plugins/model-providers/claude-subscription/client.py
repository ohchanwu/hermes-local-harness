"""Subscription CLI client. No runtime or Hermes I/O on import.

The CLI asks for tools one MCP call at a time. A message with several tool calls
goes to Hermes as one batch once the CLI's first request matches one of them;
Hermes' results then answer the CLI's remaining requests as they arrive.
"""
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
import stat
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

from .bridge import LINE_BOUND, Bridge, save
from . import compat
from .compat import CHILD_ENV, CLI_FLAGS, CLI_SETTING, TOKEN_FD_VARIABLE, TOKEN_FILE_SETTING, DEFAULT_EFFORT, EFFORT_SETTING, EFFORTS, CLI_MINIMUM, CLI_TESTED, PREFIX, SETTINGS, served_names, version_text
from .errors import ProviderError
from .history import History
from .runtime import Runtime
from . import second_message, stream_audit
from .stream_events import Message
from .transcript import render_restored
from .translate import convert_tools, record, usage

__all__ = ["ClaudeSubscriptionClient", "Bridge", "ProviderError", "History", "Message", "Runtime", "convert_tools", "render_restored",
           "record", "usage", "save", "PREFIX"]

log = logging.getLogger(__name__)
OUTPUT_FLOOR = 4096
MAX_SECOND_MESSAGES = 4  # decided follow-on messages per request before the stream counts as runaway


def owner_only(info):
    return stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077


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
            self.client._release_busy()
            self.client._dispose_if_closed()
            raise

    def close(self):
        if not self.finished:
            self.client.cancel()
            self.iterator.close()
            self.finished = True
            self.client._release_busy()
            self.client._dispose_if_closed()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ClaudeSubscriptionClient:
    HERMES_SKIP_TRANSPORT_WRAP = True
    # Prevent an HTTP AsyncOpenAI rebuild. Async callers are served instead by
    # create() returning an awaitable that runs the request in a worker thread.
    HERMES_SKIP_ASYNC_WRAP = True

    def __init__(self, *, command=None, args=None, timeout=None, **kwargs):
        self.api_key = "claude-subscription"  # routing placeholder, never a credential
        self.base_url = "acp://claude-subscription"
        self.command, self.args, self.timeout = command or os.environ.get(CLI_SETTING), args or [], timeout
        self._busy = threading.Lock()
        self._busy_owner = None  # thread whose request (possibly an open stream) holds _busy
        self._lifecycle = threading.RLock()
        self._closed = threading.Event()
        self._startup = None
        self._runtime = None
        self._bridge = None
        self._temporary = None
        self._cli_version = None
        self._model = None
        self._token_file = None
        self._request_deadline = None
        self._max_output = self._effort = None
        self._initialized = False
        self._process_env = None
        self._home = None
        self._history = History()
        self._scope = None
        self._tools = None
        self._inputs = 0
        self._pending = None  # the parked MCP call: its RPC id and tool_use id
        self._awaiting = []   # other calls of that message the CLI has not requested yet
        self._queued = {}     # Hermes' results for those calls, by tool_use id
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
        if kwargs.get("parallel_tool_calls") not in (None, False, True) or kwargs.get("tool_choice", "auto") != "auto":
            raise ProviderError("only automatic tool choice is supported")
        if kwargs.get("stream_options", {"include_usage": True}) != {"include_usage": True}:
            raise ProviderError("unsupported stream options")
        caps = {kwargs[key] for key in ("max_tokens", "max_completion_tokens") if kwargs.get(key) is not None}
        if len(caps) > 1 or any(type(cap) is not int or cap <= 0 for cap in caps):
            raise ProviderError("invalid output token cap")
        max_output = caps.pop() if caps else None
        effort = os.environ.get(EFFORT_SETTING) or DEFAULT_EFFORT
        if effort not in EFFORTS:
            raise ProviderError(f"invalid effort setting {EFFORT_SETTING}; use one of: " + ", ".join(EFFORTS))
        if self.args:
            raise ProviderError("arbitrary runtime arguments are unsupported")
        response_seconds(kwargs.get("timeout", self.timeout))
        body = kwargs.get("extra_body") or {}
        # response_format is ignored: the prompt already asks for the format. Hermes adds reasoning
        # to helper calls (titles turn thinking off); the runtime's effort setting governs instead.
        if (not isinstance(body, dict) or set(body) - {"subscription_session_id", "response_format", "reasoning"}
                or not isinstance(body.get("reasoning", {}), dict)):
            raise ProviderError("unsupported extra_body configuration")
        session_id = body.get("subscription_session_id")
        if session_id is not None and (not isinstance(session_id, str) or not session_id):
            raise ProviderError("subscription session id must be nonempty text")
        scope = self._current_scope(session_id)
        tools = convert_tools(kwargs.get("tools"))
        if self._scope is not None and scope != self._scope:
            raise ProviderError("session/worktree/profile changed; use a separate client")
        return model, scope, tools, max_output, effort

    def create(self, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return self._create(**kwargs)
        # Hermes' async helpers await create() on the event-loop thread. Run the same request
        # in a worker thread; they accept a complete response even when they asked for a stream.
        kwargs = {**{k: v for k, v in kwargs.items() if k != "stream_options"}, "stream": False}
        return asyncio.to_thread(self._create, **kwargs)

    def _release_busy(self):
        self._busy_owner = None
        self._busy.release()

    def _create(self, **kwargs):
        if self._busy_owner == threading.get_ident():
            raise ProviderError("create on the same thread while a stream from this client is still open")
        # Hermes shares one helper client across callers: queue rather than fail.
        if not self._busy.acquire(timeout=response_seconds(kwargs.get("timeout", self.timeout))):
            raise ProviderError("timed out waiting for another request on this client")
        self._busy_owner = threading.get_ident()
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
            if self._process_env is None and os.environ.get(TOKEN_FILE_SETTING):
                # Background Hermes processes cannot read a locked Keychain; see compat.
                token_file = os.environ[TOKEN_FILE_SETTING]
                try:
                    info = os.stat(token_file)
                except OSError:
                    raise ProviderError(f"{TOKEN_FILE_SETTING} does not name a readable file") from None
                if not owner_only(info):
                    raise ProviderError(f"{TOKEN_FILE_SETTING} must name an owner-only (0600) regular file")
                self._token_file = token_file
            messages = kwargs.get("messages")
            new_session = bool(self._history.messages) and (tools != self._tools or max_output != self._max_output)
            if not new_session:
                try:
                    tail = self._history.accept(messages)
                except ProviderError:
                    if not self._history.messages:
                        raise
                    new_session = True  # not a continuation of this client's own conversation
            if new_session:
                fresh = History()
                tail = fresh.accept(messages)  # still validated: fresh start or rebuild
                # All or nothing: the new conversation replaces the old before teardown, and a
                # failed teardown closes the client rather than continuing without context.
                self._history = fresh
                self._reset_session()
                self.audit.append({"stage": "session_reset"})
            self._model, self._scope, self._tools, self._max_output = model, scope, tools, max_output
            if self._effort is None:
                self._effort = effort
            if self._process_env is None:
                self._process_env = {k: os.environ[k] for k in ("PATH", "LANG", "TMPDIR") if os.environ.get(k)}
                self._process_env.update(HOME=account.pw_dir, USER=account.pw_name, LOGNAME=account.pw_name)
                self._home = Path(scope[1] or Path(scope[4] or Path.home()) / ".hermes").absolute()
            stream = Stream(self, self._drive(tail, response_seconds(kwargs.get("timeout", self.timeout))))
        except BaseException:
            self._release_busy()
            self._dispose_if_closed()  # e.g. after a failed reset closed the client
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
            # Thinking counts toward the cap, so tiny helper caps (e.g. 16) are raised.
            env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(max(self._max_output, OUTPUT_FLOOR))
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
            pass_fds = ()
            if self._token_file is not None:
                # The plugin never reads the token: the CLI reads it from this descriptor.
                fd = os.open(self._token_file, os.O_RDONLY)
                if not owner_only(os.fstat(fd)):  # re-check what was actually opened
                    os.close(fd)
                    raise ProviderError(f"{TOKEN_FILE_SETTING} must name an owner-only (0600) regular file")
                pass_fds, env = (fd,), {**env, TOKEN_FD_VARIABLE: str(fd)}
            try:
                self._runtime = Runtime(argv, env, directory, pass_fds=pass_fds)
            finally:
                for fd in pass_fds:
                    os.close(fd)
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
            restored, text, last = self._history.restored, None, tail[-1]
            with self._lifecycle:
                self._check_active()
                if restored is not None:
                    # A new client handed an existing transcript replays it as its first input.
                    self._history.restored = None
                    self._inputs += 1
                    text, _ = render_restored(restored, last)
                elif last["role"] == "tool":
                    results = {m["tool_call_id"]: m["content"] for m in tail}
                    for call in self._history.dropped:
                        # The CLI still asks for a call Hermes dropped: a duplicate gets its twin's result.
                        twin = next((k for k in self._history.messages[-len(tail) - 1]["tool_calls"]
                                     if k["function"] == call["function"]), None)
                        results[call["id"]] = results[twin["id"]] if twin else (
                            "error: Hermes did not run this tool call (it removed it from the batch, "
                            "for example over its delegation limit)")
                    owed = {c["id"] for c in self._awaiting} | ({self._pending["tool_use_id"]} if self._pending else set())
                    if self._pending is None or set(results) != owed or self._bridge is None:
                        raise ProviderError("missing/mismatched parked invocation")
                    # Margin for the real sequence number and each call's own RPC id.
                    if any(len(json.dumps({"result": self._sequence, **self._pending, "text": r})) >= LINE_BOUND - 256
                           for r in results.values()):
                        raise ProviderError("tool result exceeds the MCP bridge line bound; nothing was delivered")
                    parked, self._pending = self._pending, None
                    self._queued = {c["id"]: results[c["id"]] for c in self._awaiting}
                else:
                    self._inputs += 1
                    text = last["content"]
            if text is None:
                # Outside the lock: a full socket must not keep cancel() from running.
                self._deliver(parked["rpc_id"], parked["tool_use_id"], results[parked["tool_use_id"]])
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
                    self.audit.append({"stage": "rebuild", "messages": len(restored), "tail": last["role"],
                                       "skipped_leading": self._history.skipped,
                                       "sha256": hashlib.sha256(json.dumps(text).encode()).hexdigest()})
                    log.warning("claude-subscription rebuilt a session from a %d-message transcript", len(restored))
                else:
                    self.audit.append({"stage": "user_input", "number": self._inputs})
            served = served_names(self._model)
            # Every message is held whole: Hermes receives text only once the message is final
            # (parked for its tool calls, or ended by the turn's result), so a retried or second
            # message can still be decided without Hermes holding text that is later dropped.
            message = Message(served)
            follower = None    # a message streamed after `message` completed, held until it completes
            requested = False  # the CLI had asked over MCP for one of `message`'s calls when it began
            decisions = 0
            stream_log = stream_audit.StreamLog()  # this request's events, persisted if the stream fails
            restarts = 0
            while True:
                self._check_active()
                self._pump_bridge()
                if self._queued:
                    # Hermes answered every call; the CLI asks for the rest one at a time.
                    if not self._bridge.calls:
                        self._bridge.require_open()
                    else:
                        pending = self._bridge.calls.pop(0)
                        call = self._match(pending, self._awaiting)
                        self._awaiting.remove(call)
                        self._deliver(pending["rpc_id"], call["id"], self._queued.pop(call["id"]))
                        continue
                if message.done and message.calls and follower is None:
                    if self._bridge is not None and not self._bridge.calls:
                        self._bridge.require_open()
                    if self._bridge is not None and self._bridge.calls:
                        pending = self._bridge.calls.pop(0)
                        calls = message.calls
                        if any(c["id"] in self._seen_ids or not c["name"].startswith(PREFIX)
                               or c["name"][len(PREFIX):] not in {t["name"] for t in self._tools} for c in calls):
                            raise ProviderError("replayed or unadvertised model tool call")
                        bare = [{"id": c["id"], "name": c["name"][len(PREFIX):], "arguments": c["arguments"]} for c in calls]
                        first = self._match(pending, bare)
                        self._seen_ids.update(c["id"] for c in calls)
                        self._pending = {"rpc_id": pending["rpc_id"], "tool_use_id": first["id"]}
                        self._awaiting = [c for c in bare if c is not first]
                        native_calls = [{"id": c["id"], "type": "function", "function": {
                            "name": c["name"], "arguments": json.dumps(c["arguments"], sort_keys=True, separators=(",", ":"))}} for c in bare]
                        assistant = {"role": "assistant", "content": message.text, "tool_calls": native_calls}
                        self._history.assistant(assistant)
                        self._last_response = record({"id": message.id, "object": "chat.completion", "created": int(time.time()),
                            "model": self._model, "choices": [{"index": 0, "message": assistant, "finish_reason": "tool_calls"}], "usage": usage(message.usage)})
                        self.audit.append({"stage": "tool_parked", "tool_use_id": first["id"], "rpc_id": pending["rpc_id"],
                                           "name": first["name"], "arguments": first["arguments"], "model": self._model,
                                           "calls": len(calls)})
                        yield from self._flush(message)
                        for index, (call, plain) in enumerate(zip(calls, bare)):
                            yield self._chunk(message, {"tool_calls": [{"index": index, "id": call["id"], "type": "function",
                                                          "function": {"name": plain["name"], "arguments": ""}}]})
                            for fragment in call["fragments"] or [json.dumps(call["arguments"])]:
                                yield self._chunk(message, {"tool_calls": [{"index": index, "function": {"arguments": fragment}}]})
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
                    error = ProviderError("malformed runtime event or unexpected subagent")
                    self._persist_stream_audit(stream_log, error, runtime, obj)
                    raise error
                kind = obj.get("type")
                if kind not in ("assistant", "stream_event"):
                    stream_log.observe(obj)
                if kind == "system" and obj.get("subtype") == "init":
                    expected = {PREFIX + t["name"] for t in self._tools}
                    if obj.get("model") not in served or set(obj.get("tools", [])) != expected or obj.get("apiKeySource") != "none":
                        raise ProviderError("unexpected runtime model/auth source/executor")
                    if obj.get("claude_code_version") != version_text(self._cli_version):
                        raise ProviderError("unexpected runtime version")
                    self._initialized = True
                    self.audit.append({"stage": "init", "model": obj["model"], "tools": obj["tools"]})
                elif kind in ("assistant", "stream_event", "result") and self._awaiting:
                    error = ProviderError("runtime continued before requesting every tool call of its message")
                    self._persist_stream_audit(stream_log, error, runtime, obj, observed=kind == "result")
                    raise error
                elif kind in ("assistant", "stream_event"):
                    if not self._initialized:
                        error = ProviderError("model event before verified initialization")
                        self._persist_stream_audit(stream_log, error, runtime, obj)
                        raise error
                    event = obj.get("event") if kind == "stream_event" else None
                    if message.done and follower is None and isinstance(event, dict) and event.get("type") == "message_start":
                        # Any MCP request queued now is for `message`: the new one has no complete call yet.
                        requested = self._bridge is not None and any(
                            (PREFIX + pending.get("name", ""), pending.get("arguments")) == (c["name"], c["arguments"])
                            for pending in self._bridge.calls for c in message.calls)
                        follower = Message(served)
                    target = follower or message
                    before, finished = target.restarts, target.done
                    try:
                        target.feed(obj)  # held, not yielded: see _flush
                    except ProviderError as exc:
                        self._persist_stream_audit(stream_log, exc, runtime, obj)
                        raise
                    stream_log.observe(obj)
                    for accepted in target.escapes if target.done and not finished else ():
                        self.audit.append({"stage": "snapshot_unicode_escape_accepted", **accepted})
                    if target.restarts > before:
                        restarts += 1
                        self.audit.append({"stage": "runtime_retry", "number": restarts})
                        log.warning("claude-subscription: the Claude CLI retried a failed API call; the partial message was dropped")
                    if follower is not None and follower.done:
                        decisions += 1
                        message = self._second_message(message, follower, requested, decisions, stream_log, runtime, obj)
                        follower, requested = None, False
                elif kind == "user":
                    # Tool results the runtime fed back. After a delivery they precede the next message;
                    # while a message is current they are the CLI answering its calls without Hermes.
                    (follower or message).observe_user(obj)
                elif kind == "result":
                    if (not message.done or message.calls or follower is not None or obj.get("is_error")
                            or obj.get("subtype") != "success" or obj.get("permission_denials")):
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
                    yield from self._flush(message)
                    yield self._chunk(message, {}, finish=finish, token_usage=usage(message.usage))
                    return
                elif kind == "rate_limit_event":
                    if obj.get("rate_limit_info", {}).get("status") == "rejected":
                        raise ProviderError("runtime subscription rate limit rejected; no retry or substitute")
                elif kind != "system":
                    error = ProviderError("unknown runtime event")
                    self._persist_stream_audit(stream_log, error, runtime, obj, observed=True)
                    raise error
        except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError) as exc:
            self.cancel()
            raise ProviderError("runtime startup, I/O or malformed protocol: " + type(exc).__name__) from None
        except BaseException:
            self.cancel()
            raise

    def _flush(self, message):
        """Hand Hermes a final message's text, in the deltas it streamed in."""
        yield self._chunk(message, {"role": "assistant"})
        for delta in message.deltas:
            yield self._chunk(message, delta)

    def _second_message(self, first, second, requested, decisions, stream_log, runtime, failed):
        """Resolve a message that followed a completed one (second_message.decide); FAIL raises after the audit.

        Nothing of either has reached Hermes yet (whole-message buffering), so forwarding is never a reason to fail.
        """
        if decisions > MAX_SECOND_MESSAGES:
            outcome, row = second_message.FAIL, "too_many_messages"
        else:
            outcome, row = second_message.decide(first.facts(), second.facts(), answered=first.answered,
                                                 errored=first.errored, requested=requested, forwarded=False)
        dropped = second if outcome == second_message.KEEP_FIRST else None
        self.audit.append({"stage": "second_message", "outcome": outcome, "row": row, "number": decisions,
                           "first_id": first.id, "second_id": second.id, "first_stop": first.stop, "second_stop": second.stop,
                           "relation": stream_audit.relation(first.text, second.text), "same_model": first.model == second.model,
                           "first_calls": len(first.calls), "second_calls": len(second.calls), "answered": len(first.answered),
                           "answered_errors": len(first.errored), "requested": requested,
                           "dropped_text_chars": len(dropped.text) if dropped else 0,
                           "dropped_calls": len(dropped.calls) if dropped else len(first.calls) if outcome == second_message.KEEP_LAST else 0})
        if outcome == second_message.FAIL:
            error = ProviderError("duplicate streamed message")
            self._persist_stream_audit(stream_log, error, runtime, failed, observed=True)
            raise error
        log.warning("claude-subscription: a second streamed message was resolved as %s (%s)", outcome, row)
        if outcome == second_message.KEEP_FIRST:
            return first
        if outcome == second_message.KEEP_LAST:
            # Hermes never saw or ran the first message's calls; they can never be parked later.
            # Its visible text is kept ahead of the second's (as text blocks of one message are), not dropped.
            self._seen_ids.update(c["id"] for c in first.calls)
            second.stream_id = first.stream_id
            second.text, second.deltas = first.text + second.text, first.deltas + second.deltas
            return second
        added = second_message.appended_text(first.text, second.text)
        first.text += added
        first.deltas.extend([{"content": added}] if added else [])
        first.calls, first.stop = second.calls, second.stop
        first.answered, first.errored = second.answered, second.errored
        merged = {**first.usage, **second.usage}
        if type(first.usage.get("output_tokens")) is int and type(second.usage.get("output_tokens")) is int:
            merged["output_tokens"] = first.usage["output_tokens"] + second.usage["output_tokens"]
        first.usage = merged
        return first

    def _persist_stream_audit(self, stream_log, error, runtime, failed, *, observed=False):
        """Write this request's stream audit; the caller then raises the original error unchanged.

        The event that failed is recorded (as not forwarded) unless it already was, then the rest of
        the current message is read briefly into the record only, never to Hermes, so a second
        message's relation to the first is known. Any failure here is one warning, never a new error.
        """
        try:
            if not observed:
                stream_log.observe(failed)
            stream_log.drain(runtime.read, lambda: not self.is_closed())
            if self._home is None:
                raise ProviderError("no profile home")
            session = self._scope[-1] if self._scope else None
            record = stream_audit.payload(error, session, self._model,
                                          version_text(self._cli_version) if self._cli_version else None,
                                          self.audit, stream_log, declared={PREFIX + t["name"] for t in self._tools or ()})
            path = stream_audit.write(self._home, session, record)
        except Exception as exc:
            log.warning("claude-subscription stream failed (%s); stream audit not written (%s)", error, type(exc).__name__)
        else:
            log.warning("claude-subscription stream failed (%s); stream audit written to %s", error, path.name)

    def _match(self, pending, calls):
        """The first of the message's calls that this MCP request is for; the CLI may request them in any order."""
        if (pending.get("call") != self._sequence or self._delivered or type(pending.get("rpc_id")) not in (str, int)
                or pending.get("name") not in {t["name"] for t in self._tools}):
            raise ProviderError("unmatched/replayed/unadvertised model and MCP invocation")
        for call in calls:
            if call["name"] == pending["name"] and call["arguments"] == pending.get("arguments"):
                return call
        raise ProviderError("unmatched/replayed/unadvertised model and MCP invocation")

    def _deliver(self, rpc_id, tool_use_id, text):
        """Answer one parked MCP call; outside the lock, so a full socket cannot block cancel()."""
        delivery = {"result": self._sequence, "rpc_id": rpc_id, "tool_use_id": tool_use_id, "text": text}
        self._bridge.send(delivery, self._check_active)
        self._delivered.append({"returned": delivery["result"], "rpc_id": rpc_id, "tool_use_id": tool_use_id})
        self.audit.append({"stage": "result_delivered", "tool_use_id": tool_use_id, "rpc_id": rpc_id,
                           "text_sha256": hashlib.sha256(text.encode()).hexdigest()})
        self._sequence += 1

    def _chunk(self, message, delta, *, finish=None, token_usage=None):
        self._check_active()  # recheck even between deferred tool-argument chunks
        return record({"id": message.stream_id, "object": "chat.completion.chunk", "created": int(time.time()), "model": self._model,
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

    def _reset_session(self):
        """End the current CLI session (cancelling any parked tool call) without closing the client."""
        with self._lifecycle:
            runtime, bridge, temporary = self._runtime, self._bridge, self._temporary
            self._runtime = self._bridge = self._temporary = self._startup = None
        self._pending, self._sequence, self._delivered, self._awaiting, self._queued = None, 0, [], [], {}
        self._initialized, self._request_deadline = False, None
        try:
            if bridge is not None:
                bridge.shutdown()
            if runtime is not None:
                runtime.close()
                runtime.dispose()
            if bridge is not None:
                bridge.close()
            if temporary is not None:
                temporary.cleanup()
        except BaseException as exc:
            with self._lifecycle:  # put the remains back so close() can still reap them
                self._runtime, self._bridge, self._temporary = runtime, bridge, temporary
            try:
                self.cancel()  # marks the client closed first, then retries the cleanup
            except BaseException:
                pass
            raise ProviderError(f"session reset failed ({type(exc).__name__}); client closed") from None

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
