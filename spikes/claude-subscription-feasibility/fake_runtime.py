"""Inert owned child. Source-shaped SDK MCP envelopes, never a model runtime."""
import json
import hashlib
import os
from pathlib import Path
import signal
import sys

ALLOWED = {"HOME", "PATH", "LANG", "LC_ALL"}
# macOS adds this locale hint even when Popen receives an explicit environment.
os.environ.pop("__CF_USER_TEXT_ENCODING", None)
assert set(os.environ) == ALLOWED
assert os.getpgrp() == os.getpid()
HOME = Path(os.environ["HOME"]).resolve()
assert HOME == Path.cwd().resolve()


def deny_access(event, args):
    if event == "open" or event.startswith("socket.") or event == "subprocess.Popen":
        raise RuntimeError("Inert runtime forbids files, network and children")


sys.addaudithook(deny_access)
if sys.argv[1:] == ["timeout"]:
    signal.pause()
elif sys.argv[1:2] == ["rendezvous"]:
    # Synthetic model event and independent MCP IDs; not an official-runtime trace.
    variant = sys.argv[2] if len(sys.argv) > 2 else ""
    if variant == "startup_timeout":
        signal.pause()
    if variant == "process_death":
        sys.exit(3)
    tool = {"type": "tool_use", "id": "toolu-synthetic-1",
            "name": "mcp__hermes__fixture_read", "input": {"path": "fixture.txt"}}
    content = [] if variant == "missing_tool" else [tool]
    if variant == "duplicate_tool":
        content.append(dict(tool))
    print(json.dumps({"type": "assistant", "message": {"content": content}}), flush=True)
    request = {"type": "control_request", "request_id": "control-1", "request": {
        "subtype": "mcp_message", "server_name": "hermes", "message": {
            "jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {
                "name": "fixture_read", "arguments": {"path": "fixture.txt"}}}}}
    if variant == "mismatch_rpc":
        request["request"]["message"]["params"]["arguments"] = {"path": "wrong.txt"}
    print(json.dumps(request), flush=True)
    response = json.loads(sys.stdin.readline())["response"]
    if variant == "continuation_timeout":
        signal.pause()
    assert response["request_id"] == "control-1"
    rpc_response = response["response"]["mcp_response"]
    assert rpc_response["id"] == 7
    result = rpc_response["result"]
    # Receipt computed from the actual supplied result, not a canned answer.
    text = result["content"][0]["text"]
    print(json.dumps({"type": "result", "subtype": "success",
                      "result_hash": hashlib.sha256(text.encode()).hexdigest()}), flush=True)
else:
    request = json.loads(sys.stdin.readline())
    print(json.dumps(request), flush=True)
    response = json.loads(sys.stdin.readline())["response"]
    assert response["request_id"] == request["request_id"]
    rpc_response = response["response"]["mcp_response"]
    assert rpc_response["id"] == request["request"]["message"]["id"]
    print(json.dumps({"accepted_result": rpc_response["result"],
                      "environment_keys": sorted(os.environ)}), flush=True)
