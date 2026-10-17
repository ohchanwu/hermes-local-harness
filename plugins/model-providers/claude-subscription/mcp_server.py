"""Stdio MCP transport only. This process has no tool execution implementation."""
import json
import os
import sys
import time
from pathlib import Path


def save(path, value):
    """Exclusive owner-only message; no overwriting a prior invocation/result."""
    path = Path(path)
    temporary = path.with_name(path.name + ".writing")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def serve(directory, source=None, sink=None):
    source, sink = source or sys.stdin, sink or sys.stdout
    directory = Path(directory)
    cfg = json.loads((directory / "bridge.json").read_text())
    sequence, seen = 0, set()
    for line in source:
        if len(line) > 2_000_000:
            raise ValueError("MCP input bound")
        request = json.loads(line)
        method, rpc = request.get("method"), request.get("id")
        if rpc is not None:
            if type(rpc) not in (str, int) or rpc in seen:
                raise ValueError("invalid/replayed MCP RPC id")
            seen.add(rpc)
        result = None
        if method == "initialize":
            result = {"protocolVersion": request["params"]["protocolVersion"], "capabilities": {"tools": {}},
                      "serverInfo": {"name": "hermes", "version": "0.1.0"}}
        elif method == "tools/list":
            result = {"tools": cfg["tools"]}
        elif method == "ping":
            result = {}
        elif method == "tools/call":
            params = request.get("params", {})
            if rpc is None or params.get("name") not in {t["name"] for t in cfg["tools"]} or not isinstance(params.get("arguments"), dict):
                raise ValueError("unadvertised MCP call")
            save(directory / f"call-{sequence}.json", {"rpc_id": rpc, "name": params["name"], "arguments": params["arguments"]})
            delivery = directory / f"result-{sequence}.json"
            while True:
                if (directory / "cancel").exists() or (cfg["deadline"] is not None and time.time() >= cfg["deadline"]):
                    return
                if delivery.exists():
                    break
                time.sleep(0.01)
            value = json.loads(delivery.read_text())
            if value.get("rpc_id") != rpc or not isinstance(value.get("tool_use_id"), str) or not isinstance(value.get("text"), str):
                raise ValueError("unmatched MCP result")
            result = {"content": [{"type": "text", "text": value["text"]}]}
            save(directory / f"returned-{sequence}.json", {"rpc_id": rpc, "tool_use_id": value["tool_use_id"]})
            sequence += 1
        elif rpc is not None:
            sink.write(json.dumps({"jsonrpc": "2.0", "id": rpc, "error": {"code": -32601, "message": "Unknown method"}}) + "\n")
            sink.flush()
        if result is not None and rpc is not None:
            sink.write(json.dumps({"jsonrpc": "2.0", "id": rpc, "result": result}) + "\n")
            sink.flush()


if __name__ == "__main__":
    serve(Path(sys.argv[1]))
