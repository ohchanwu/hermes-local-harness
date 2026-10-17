"""Owner end of the MCP bridge: one authenticated Unix-socket connection, newline-delimited JSON.

The Claude CLI, not this client, starts mcp_server.py, so the two cannot share an
inherited pipe. The server connects here, proves it holds the per-session token
and receives the advertised tools; each tool call then parks on its blocking
read until the owner sends the matching result. Closing the socket cancels it.
"""
import hmac
import json
import os
from pathlib import Path
import secrets
import select
import shutil
import socket
import tempfile

from .errors import ProviderError

LINE_BOUND = 2_000_000  # bytes per bridge message, matching the MCP input bound
SOCKET_PATH_BOUND = 103  # macOS sun_path holds 104 bytes including the terminator


def save(path, value):
    """Atomic exclusive owner-only session file write."""
    temporary = path.with_name(path.name + ".writing")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Bridge:
    def __init__(self, tools, root="/tmp"):
        # A short private directory: the session cache path is too long for a socket.
        self.directory = Path(tempfile.mkdtemp(prefix="hcs-", dir=root))
        self.path = self.directory / "bridge.sock"
        if len(os.fsencode(self.path)) > SOCKET_PATH_BOUND:
            shutil.rmtree(self.directory, ignore_errors=True)
            raise ProviderError("MCP bridge socket path is too long")
        self.tools = tools
        self.token = secrets.token_hex(32)
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(str(self.path))
        self.listener.listen(1)
        self.listener.setblocking(False)
        self.connection = None
        self.authenticated = False
        self.buffer = b""
        self.calls = []
        self.returns = []
        self.closed_by_server = False

    def pump(self):
        """Nonblocking: accept and authenticate the one server, then queue complete messages."""
        if self.connection is None:
            try:
                self.connection, _ = self.listener.accept()
            except BlockingIOError:
                return
            self.listener.close()
            self.path.unlink()  # no second connection can reach this session
            self.connection.setblocking(False)
        while True:
            try:
                data = self.connection.recv(65536)
            except BlockingIOError:
                break
            if not data:
                self.closed_by_server = True  # an error only while the owner still expects a message
                break
            self.buffer += data
            if len(self.buffer) > LINE_BOUND and b"\n" not in self.buffer:
                raise ProviderError("MCP bridge line bound exceeded")
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            if len(line) > LINE_BOUND:
                raise ProviderError("MCP bridge line bound exceeded")
            message = json.loads(line)
            if not isinstance(message, dict):
                raise ProviderError("malformed MCP bridge message")
            if not self.authenticated:
                if not isinstance(message.get("hello"), str) or not hmac.compare_digest(message["hello"], self.token):
                    raise ProviderError("MCP bridge authentication failed")
                self.authenticated = True
                self.send({"tools": self.tools}, lambda: None)
            elif "call" in message:
                self.calls.append(message)
            elif "returned" in message:
                self.returns.append(message)
            else:
                raise ProviderError("unknown MCP bridge message")

    def require_open(self):
        if self.closed_by_server:
            raise ProviderError("MCP bridge closed by server")

    def send(self, value, check_active):
        if self.connection is None:
            raise ProviderError("MCP bridge is not connected")
        remaining = memoryview(json.dumps(value).encode() + b"\n")
        while remaining:
            check_active()
            try:
                remaining = remaining[self.connection.send(remaining):]
            except BlockingIOError:
                select.select([], [self.connection], [], 0.01)

    def shutdown(self):
        """Cancel: the server sees end-of-file and exits without answering a parked call."""
        for sock in (self.connection, self.listener):
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def close(self):
        self.shutdown()
        for sock in (self.connection, self.listener):
            if sock is not None:
                sock.close()
        shutil.rmtree(self.directory, ignore_errors=True)
