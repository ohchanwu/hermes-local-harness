"""One-off serial official-CLI/MCP rendezvous; no Hermes/provider implementation.

No default live action. `mcp CASE_DIR` serves only the parked synthetic request;
`run ROOT roundtrip|cancel` consumes a pre-frozen, never-reusable case slot.
The parent Hermes worker, not this program, performs the native read_file call.
"""
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time

MODEL = "claude-opus-5-5"
TOOL = "mcp__harness_probe__fixture_read"
NORMAL_SECONDS = 60
HARD_SECONDS = 120
GRACE_SECONDS = 5
MAX_BYTES = 2_000_000


def save(path, value, exclusive=False):
    """Owner-only evidence/mailbox; exclusive writes reject duplicate delivery."""
    path = Path(path)
    temporary = path.with_name(path.name + ".writing")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(value, out, sort_keys=True)
            out.write("\n")
        if exclusive:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load(path):
    return json.loads(Path(path).read_text())


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def schema(fixture):
    return {"name": "fixture_read", "description": "Ask owning Hermes to read the one synthetic fixture; this server cannot read it.",
            "inputSchema": {"type": "object", "properties": {"path": {"type": "string", "enum": [fixture]}},
                            "required": ["path"], "additionalProperties": False}}


class Correlation:
    """Exactly one logical model invocation, independent of its MCP RPC id."""
    def __init__(self, fixture):
        self.args = {"path": fixture}
        self.tool_id = None
        self.rpc_id = None
        self.delivered = False
        self.cancelled = False
        self.blocks = {}
        self.origins = set()

    def tool(self, tool_id, name, args, origin):
        if self.cancelled or not isinstance(tool_id, str) or not tool_id:
            raise ValueError("invalid/stale tool id")
        if name != TOOL or args != self.args:
            raise ValueError("unexpected tool/arguments")
        if self.tool_id is not None and self.tool_id != tool_id:
            raise ValueError("additional invocation")
        # A partial stream and its final assistant snapshot describe the SAME
        # invocation. Repeated starts or repeated snapshots are not new calls.
        if origin in self.origins:
            raise ValueError("duplicate model event")
        self.origins.add(origin)
        self.tool_id = tool_id

    def event(self, obj):
        if obj.get("type") == "assistant":
            msg = obj.get("message", {})
            if msg.get("model") != MODEL:
                raise ValueError("unexpected served model")
            for b in msg.get("content", []):
                if b.get("type") == "tool_use":
                    self.tool(b.get("id"), b.get("name"), b.get("input"), "assistant")
        if obj.get("type") != "stream_event":
            return
        ev = obj["event"]
        kind, index = ev.get("type"), ev.get("index")
        if kind == "message_start":
            self.blocks = {}
        if kind == "content_block_start" and ev["content_block"].get("type") == "tool_use":
            if index in self.blocks:
                raise ValueError("duplicate block")
            self.blocks[index] = [ev["content_block"], "", False]
        elif kind == "content_block_delta" and index in self.blocks:
            b = self.blocks[index]
            if b[2] or ev["delta"].get("type") != "input_json_delta":
                raise ValueError("invalid input delta")
            b[1] += ev["delta"]["partial_json"]
        elif kind == "content_block_stop" and index in self.blocks:
            b = self.blocks[index]
            if b[2]:
                raise ValueError("duplicate block stop")
            b[2] = True
            self.tool(b[0].get("id"), b[0].get("name"), json.loads(b[1]) if b[1] else b[0].get("input"), "stream")

    def pending(self, request):
        if self.cancelled or request.get("name") != "fixture_read" or request.get("arguments") != self.args:
            raise ValueError("out-of-scope MCP request")
        rpc = request.get("rpc_id")
        if type(rpc) not in (str, int) or rpc == self.tool_id:
            raise ValueError("invalid MCP lineage")
        if self.rpc_id is not None and self.rpc_id != rpc:
            raise ValueError("additional MCP invocation")
        self.rpc_id = rpc

    def ready(self):
        return self.tool_id is not None and self.rpc_id is not None and not self.cancelled

    def accept(self, result):
        if not self.ready() or self.delivered:
            raise ValueError("stale/duplicate result")
        if set(result) != {"tool_use_id", "rpc_id", "name", "arguments", "text", "native_tool"}:
            raise ValueError("invalid result envelope")
        if (result["tool_use_id"] != self.tool_id or result["rpc_id"] != self.rpc_id
                or result["name"] != TOOL or result["arguments"] != self.args
                or result["native_tool"] != "read_file" or not isinstance(result["text"], str)):
            raise ValueError("mismatched result")
        self.delivered = True
        return {"rpc_id": self.rpc_id, "tool_use_id": self.tool_id, "text": result["text"]}

    def cancel(self):
        self.cancelled = True


def mcp(directory):
    """MCP has mailbox authority only: never open the requested fixture."""
    cfg = load(directory / "case.json")
    called = False
    for line in sys.stdin:
        req = json.loads(line)
        method, rpc = req.get("method"), req.get("id")
        result = None
        if method == "initialize":
            result = {"protocolVersion": req["params"]["protocolVersion"], "capabilities": {"tools": {}},
                      "serverInfo": {"name": "harness_probe", "version": "0.1"}}
        elif method == "tools/list":
            result = {"tools": [schema(cfg["fixture"])]}
        elif method == "ping":
            result = {}
        elif method == "tools/call":
            params = req["params"]
            if called or params.get("name") != "fixture_read" or params.get("arguments") != {"path": cfg["fixture"]}:
                raise ValueError("duplicate/out-of-scope invocation")
            called = True
            save(directory / "pending.json", {"rpc_id": rpc, "name": params["name"],
                 "arguments": params["arguments"], "parked_monotonic": time.monotonic()}, exclusive=True)
            deadline = time.monotonic() + 90
            while not (directory / "delivery.json").exists():
                if (directory / "cancel.json").exists() or time.monotonic() >= deadline:
                    save(directory / "mcp-stop.json", {"cancelled_or_expired": True}, exclusive=True)
                    return
                time.sleep(0.02)
            delivery = load(directory / "delivery.json")
            if delivery["rpc_id"] != rpc or not isinstance(delivery["tool_use_id"], str):
                raise ValueError("unmatched MCP delivery")
            result = {"content": [{"type": "text", "text": delivery["text"]}]}
            save(directory / "mcp-return.json", {"rpc_id": rpc, "tool_use_id": delivery["tool_use_id"],
                 "text_sha256": digest(delivery["text"]), "monotonic": time.monotonic()}, exclusive=True)
        elif rpc is not None:
            print(json.dumps({"jsonrpc": "2.0", "id": rpc, "error": {"code": -32601, "message": "Unknown method"}}), flush=True)
            continue
        if rpc is not None and result is not None:
            print(json.dumps({"jsonrpc": "2.0", "id": rpc, "result": result}), flush=True)


class Child:
    def __init__(self, argv, cwd, env):
        self.started = time.monotonic()
        self.p = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        assert self.p.stdout is not None and self.p.stderr is not None
        self.cleaned = None

    def expired(self, seconds: float = NORMAL_SECONDS):
        return time.monotonic() - self.started >= min(seconds, HARD_SECONDS)

    def group_exists(self):
        try:
            os.killpg(self.p.pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # macOS can transiently return EPERM while the owned group exits.
            # Do not treat EPERM itself as absence: check that exact PGID.
            check = subprocess.run(["/bin/ps", "-g", str(self.p.pid), "-o", "pid=,pgid=,stat="],
                                   capture_output=True, text=True, timeout=2)
            if check.returncode not in (0, 1) or check.stderr:
                raise RuntimeError("cannot establish owned group state")
            return bool(check.stdout.strip())

    def cleanup(self):
        if self.cleaned is not None:
            return self.cleaned
        for sig, wait in ((signal.SIGTERM, GRACE_SECONDS), (signal.SIGKILL, 1)):
            if self.group_exists():
                try:
                    os.killpg(self.p.pid, sig)
                except ProcessLookupError:
                    pass
            end = time.monotonic() + wait
            while time.monotonic() < end:
                self.p.poll()  # reap the leader even when descendants remain
                if not self.group_exists():
                    break
                time.sleep(0.02)
        self.p.wait(timeout=1)
        for pipe in (self.p.stdout, self.p.stderr):
            if pipe is not None:
                pipe.close()
        self.cleaned = {"exit": self.p.returncode, "reaped": self.p.poll() is not None,
                        "group_absent": not self.group_exists(), "lifetime_seconds": time.monotonic() - self.started}
        return self.cleaned


def project(obj):
    """Persist necessary value-blind stages, not raw runtime transcripts."""
    kind = obj.get("type")
    out = {"type": kind, "subtype": obj.get("subtype"), "monotonic": time.monotonic()}
    if kind == "system" and obj.get("subtype") == "init":
        for key in ("tools", "model", "mcp_servers", "permissionMode", "claude_code_version", "apiKeySource"):
            out[key] = obj.get(key)
    elif kind == "assistant":
        msg = obj.get("message", {})
        out.update(model=msg.get("model"), usage=msg.get("usage"), error=obj.get("error"))
        out["tool_uses"] = [{k: b.get(k) for k in ("id", "name", "input")} for b in msg.get("content", []) if b.get("type") == "tool_use"]
    elif kind == "stream_event":
        ev = obj.get("event", {})
        out["event_type"] = ev.get("type")
        if ev.get("type") in ("content_block_start", "content_block_delta", "content_block_stop"):
            out["index"] = ev.get("index")
            b = ev.get("content_block", {})
            if b.get("type") == "tool_use":
                out["tool"] = b
            if ev.get("delta", {}).get("type") == "input_json_delta":
                out["input_delta"] = ev["delta"]["partial_json"]
        if ev.get("type") == "message_start":
            out["model"] = ev.get("message", {}).get("model")
    elif kind == "result":
        for key in ("is_error", "num_turns", "usage", "modelUsage", "permission_denials", "stop_reason"):
            out[key] = obj.get(key)
    return out


def run(root, case):
    freeze = load(root / "freeze.json")
    if case not in ("roundtrip", "cancel"):
        raise ValueError("unknown case")
    if (root / "STOP.json").exists():
        raise ValueError("live line stopped; no retries")
    if case == "cancel" and load(root / "roundtrip" / "outcome.json")["outcome"] != "roundtrip_pass":
        raise ValueError("roundtrip did not pass")
    directory = root / case
    cfg = load(directory / "case.json")
    save(directory / "launch.json", {"argv": cfg["argv"], "utc_epoch": time.time(),
         "submission": "unknown until observed; process count is not wire count"}, exclusive=True)
    state = Correlation(cfg["fixture"])
    child = None
    events = []
    outcome = "failed"
    reason = "unclassified"
    ready_at = None
    result_seen = False
    buffers = {}
    sel = selectors.DefaultSelector()
    try:
        child = Child(cfg["argv"], directory, freeze["env"])
        for pipe in (child.p.stdout, child.p.stderr):
            assert pipe is not None
            os.set_blocking(pipe.fileno(), False)
            sel.register(pipe.fileno(), selectors.EVENT_READ, pipe)
        buffers = {child.p.stdout: b"", child.p.stderr: b""}
        total = 0
        initialized = False
        while True:
            if child.expired():
                raise TimeoutError("normal response deadline")
            for key, _ in sel.select(0.02):
                pipe = key.data
                data = os.read(pipe.fileno(), 65536)
                if not data:
                    sel.unregister(pipe)
                    continue
                total += len(data)
                if total > MAX_BYTES:
                    raise ValueError("output bound")
                if pipe is child.p.stderr:
                    # No raw stderr retention; length/hash only.
                    buffers[pipe] += data
                    continue
                buffers[pipe] += data
                while b"\n" in buffers[pipe]:
                    line, buffers[pipe] = buffers[pipe].split(b"\n", 1)
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    events.append(project(obj))
                    if obj.get("type") == "system" and obj.get("subtype") == "init":
                        tools = set(obj.get("tools", []))
                        if obj.get("model") != MODEL or not tools.issubset({TOOL, "EndConversation"}) or TOOL not in tools:
                            raise ValueError("unexpected init model/executor/tools")
                        servers = obj.get("mcp_servers", [])
                        if len(servers) != 1 or servers[0].get("name") != "harness_probe" or servers[0].get("status") != "connected":
                            raise ValueError("unexpected MCP initialization")
                        initialized = True
                    if obj.get("type") == "assistant" and obj.get("error"):
                        raise ValueError("runtime assistant error: " + str(obj["error"]))
                    if obj.get("type") == "stream_event" and obj.get("event", {}).get("type") == "message_start":
                        if obj["event"]["message"].get("model") != MODEL:
                            raise ValueError("unexpected streamed model")
                    state.event(obj)
                    if obj.get("type") == "result":
                        result_seen = True
                        if obj.get("is_error") or not state.delivered or obj.get("num_turns", 999) > cfg["max_turns"]:
                            raise ValueError("runtime error/refusal/turn limit/no continuation")
                        if digest(obj.get("result", "").rstrip("\n") + "\n") != cfg["fixture_sha256"]:
                            raise ValueError("continuation oracle mismatch")
                        if not (directory / "mcp-return.json").exists():
                            raise ValueError("missing matched MCP return")
                        outcome, reason = "roundtrip_pass", "matched real invocation/result/continuation"
            if (directory / "pending.json").exists():
                state.pending(load(directory / "pending.json"))
            if state.ready() and ready_at is None:
                if not initialized:
                    raise ValueError("tool before verified initialization")
                ready_at = time.monotonic()
                save(directory / "ready.json", {"tool_use_id": state.tool_id, "rpc_id": state.rpc_id,
                     "name": TOOL, "arguments": state.args, "monotonic": ready_at}, exclusive=True)
                if case == "cancel":
                    state.cancel()
                    save(directory / "cancel.json", {"reason": "intentional pending cancellation"}, exclusive=True)
                    outcome, reason = "cancel_pass", "pending invocation cancelled without native execution"
                    break
            if (directory / "native-result.json").exists() and not state.delivered:
                delivery = state.accept(load(directory / "native-result.json"))
                save(directory / "delivery.json", delivery, exclusive=True)
                events.append({"type": "native_result_delivered", "tool_use_id": state.tool_id,
                               "rpc_id": state.rpc_id, "text_sha256": digest(delivery["text"]), "monotonic": time.monotonic()})
            if child.p.poll() is not None and not sel.get_map():
                if buffers[child.p.stdout].strip():
                    raise ValueError("incomplete stream")
                if child.p.returncode != 0 or not result_seen:
                    raise ValueError("child exited without successful result")
                break
    except (Exception, KeyboardInterrupt) as exc:
        reason = type(exc).__name__ + ": " + str(exc)
        outcome = "failed"
        save(root / "STOP.json", {"case": case, "reason": reason}, exclusive=True)
    finally:
        sel.close()
        state.cancel()
        if child:
            cleanup = child.cleanup()
            assert cleanup == child.cleanup()
        else:
            cleanup = {"not_started": True}
        if child and (not cleanup["group_absent"] or not cleanup["reaped"] or cleanup["lifetime_seconds"] > HARD_SECONDS):
            outcome, reason = "failed", "cleanup/deadline violation"
            if not (root / "STOP.json").exists():
                save(root / "STOP.json", {"case": case, "reason": reason}, exclusive=True)
        save(directory / "events.json", events, exclusive=True)
        save(directory / "outcome.json", {"outcome": outcome, "reason": reason, "cleanup": cleanup,
             "real_tool_use_id": state.tool_id, "mcp_rpc_id": state.rpc_id, "result_delivered": state.delivered,
             "ready_monotonic": ready_at, "native_result_present": (directory / "native-result.json").exists(),
             "stderr_bytes": len(buffers[child.p.stderr]) if child else 0,
             "stderr_sha256": hashlib.sha256(buffers[child.p.stderr]).hexdigest() if child else None}, exclusive=True)
    print(json.dumps(load(directory / "outcome.json"), indent=2))
    return 0 if outcome.endswith("_pass") else 1


if __name__ == "__main__":
    os.umask(0o077)
    def interrupted(signum, frame):
        raise KeyboardInterrupt("parent signal " + str(signum))
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, interrupted)
    if len(sys.argv) == 3 and sys.argv[1] == "mcp":
        mcp(Path(sys.argv[2]).resolve())
    elif len(sys.argv) == 4 and sys.argv[1] == "run":
        sys.exit(run(Path(sys.argv[2]).resolve(), sys.argv[3]))
    else:
        sys.exit("explicit mcp CASE_DIR or run ROOT roundtrip|cancel required")
