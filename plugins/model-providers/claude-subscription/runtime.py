"""Owned runtime child process group with nonblocking I/O and bounded cleanup."""
import json
import os
import selectors
import signal
import subprocess
import threading
import time

from .errors import ProviderError
from .history import content_blocks

LINE_BOUND = 8_000_000  # bytes per runtime JSON line


class Runtime:
    """Owned child process group; the client bounds startup and parked time."""
    def __init__(self, argv, env, directory, pass_fds=()):
        self.directory = directory
        self.lock = threading.Lock()
        self.cleanup = None
        self.started = time.monotonic()
        self.process = subprocess.Popen(argv, cwd=directory, env=env, pass_fds=pass_fds, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        assert self.process.stdin is not None
        os.set_blocking(self.process.stdin.fileno(), False)
        self.selector = selectors.DefaultSelector()
        self.buffer = b""
        self.stderr_bytes = 0
        for pipe in (self.process.stdout, self.process.stderr):
            assert pipe is not None
            os.set_blocking(pipe.fileno(), False)
            self.selector.register(pipe, selectors.EVENT_READ)

    def send(self, text, check_active, idle=None):
        data = json.dumps({"type": "user", "message": {"role": "user", "content": content_blocks(text)}}) + "\n"
        assert self.process.stdin is not None
        remaining = memoryview(data.encode())
        while remaining:
            check_active()
            try:
                sent = os.write(self.process.stdin.fileno(), remaining)
                remaining = remaining[sent:]
            except BlockingIOError:
                if idle is not None:
                    idle()
                time.sleep(0.01)

    def version_output(self, deadline, check_active):
        """Read a bounded version response without an unowned blocking run()."""
        output = b""
        total = 0
        while True:
            check_active()
            if time.monotonic() >= deadline:
                raise ProviderError("runtime version startup timed out")
            for key, _ in self.selector.select(0.01):
                data = os.read(key.fd, 65536)
                if not data:
                    self.selector.unregister(key.fileobj)
                    continue
                total += len(data)
                if total > 65536:
                    raise ProviderError("runtime version output bound exceeded")
                if key.fileobj is self.process.stdout:
                    output += data
            if self.process.poll() is not None and not self.selector.get_map():
                return self.process.returncode, output

    def read(self):
        if b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            return json.loads(line)
        for key, _ in self.selector.select(0.01):
            data = os.read(key.fd, 65536)
            if not data:
                self.selector.unregister(key.fileobj)
                continue
            if key.fileobj is self.process.stderr:
                self.stderr_bytes += len(data)  # never store arbitrary stderr/account data
            else:
                self.buffer += data
                if len(self.buffer) > LINE_BOUND and b"\n" not in self.buffer:
                    raise ProviderError("runtime JSON line bound exceeded")
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
            for sig, seconds in ((signal.SIGTERM, 4), (signal.SIGKILL, 0.5)):
                try:
                    os.killpg(self.process.pid, sig)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    # macOS may report EPERM for a just-reaped group. Establish
                    # absence via the same exact-PGID check, never ignore a denial
                    # while an owned group is actually still present. An exited,
                    # unreaped leader (zombie) also gives EPERM, so reap first.
                    self.process.poll()
                    if self.group_exists():
                        raise
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
