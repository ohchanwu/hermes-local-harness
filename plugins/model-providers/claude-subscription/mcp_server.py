"""Stdio MCP transport only. This process has no tool execution implementation.

It runs isolated (python -I -S), so it cannot import the plugin package and keeps
its own copy of the bridge framing; tests drive both ends over a real socket.
"""
import json
import os
import socket
import sys

LINE_BOUND = 2_000_000


class Bridge:
    """Server end of the owner's Unix-socket bridge."""
    def __init__(self, path, token):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(path)
        self.reader = self.sock.makefile("rb")
        self.send({"hello": token})

    def send(self, value):
        self.sock.sendall(json.dumps(value).encode() + b"\n")

    def receive(self):
        """Next owner message, or None once the owner closed (cancelled) the bridge."""
        try:
            line = self.reader.readline(LINE_BOUND + 1)
        except OSError:
            return None
        if not line:
            return None
        if len(line) > LINE_BOUND or not line.endswith(b"\n"):
            raise ValueError("MCP bridge line bound")
        return json.loads(line)


def serve(bridge, source=None, sink=None):
    source, sink = source or sys.stdin, sink or sys.stdout
    hello = bridge.receive()
    if hello is None:
        return
    tools = hello["tools"]
    sequence, seen = 0, set()
    for line in source:
        if len(line) > LINE_BOUND:
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
                      "serverInfo": {"name": "hermes", "version": "1"}}
        elif method == "tools/list":
            result = {"tools": tools}
        elif method == "ping":
            result = {}
        elif method == "tools/call":
            params = request.get("params", {})
            if rpc is None or params.get("name") not in {t["name"] for t in tools} or not isinstance(params.get("arguments"), dict):
                raise ValueError("unadvertised MCP call")
            bridge.send({"call": sequence, "rpc_id": rpc, "name": params["name"], "arguments": params["arguments"]})
            value = bridge.receive()
            if value is None:
                return
            if (value.get("result") != sequence or value.get("rpc_id") != rpc
                    or not isinstance(value.get("tool_use_id"), str) or not isinstance(value.get("text"), str)):
                raise ValueError("unmatched MCP result")
            result = {"content": [{"type": "text", "text": value["text"]}]}
        elif rpc is not None:
            sink.write(json.dumps({"jsonrpc": "2.0", "id": rpc, "error": {"code": -32601, "message": "Unknown method"}}) + "\n")
            sink.flush()
        if result is not None and rpc is not None:
            sink.write(json.dumps({"jsonrpc": "2.0", "id": rpc, "result": result}) + "\n")
            sink.flush()
        if method == "tools/call":
            try:
                bridge.send({"returned": sequence, "rpc_id": rpc, "tool_use_id": value["tool_use_id"]})
            except OSError:
                return  # owner closed after delivery
            sequence += 1


if __name__ == "__main__":
    serve(Bridge(sys.argv[1], os.environ["HERMES_BRIDGE_TOKEN"]))
