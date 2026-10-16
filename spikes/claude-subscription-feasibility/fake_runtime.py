"""Inert owned child. Source-shaped SDK MCP envelopes, never a model runtime."""
import json
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
else:
    request = json.loads(sys.stdin.readline())
    print(json.dumps(request), flush=True)
    response = json.loads(sys.stdin.readline())["response"]
    assert response["request_id"] == request["request_id"]
    rpc_response = response["response"]["mcp_response"]
    assert rpc_response["id"] == request["request"]["message"]["id"]
    print(json.dumps({"accepted_result": rpc_response["result"],
                      "environment_keys": sorted(os.environ)}), flush=True)
