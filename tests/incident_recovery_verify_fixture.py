#!/usr/bin/env python3
"""TEST ONLY: real fixture coverage, never a live foreign-policy validation.

The production verifier runs unchanged under read-only worktree resource fences;
commands and sockets are forbidden. Wrapper exit is distinct from verifier exit.
"""
import builtins
from contextlib import ExitStack, redirect_stdout
import io
import os
from pathlib import Path
import socket
import subprocess
import sys
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "clean.yaml": (0, "OK: desired state matches observed state"),
    "incomplete-empty.yaml": (1, "incomplete fixture"),
    "deployed-skill-divergence.yaml": (1, "deployed skill hash mismatch"),
}


class BoundaryError(RuntimeError):
    pass


def load_verifier():
    source = ROOT / "scripts/verify-state"
    module = types.ModuleType("incident_fixture_verifier")
    module.__file__ = str(source)
    exec(compile(source.read_text(), str(source), "exec"), module.__dict__)
    return module


class LocalReads:
    """Allow only pre-resolved, existing root resources; reject symlink escapes.

    This is a test guard for inspected Python resource paths, not an OS sandbox
    for arbitrary hostile code. Enumerating here performs only worktree reads.
    """
    def __init__(self):
        self.allowed = {str(ROOT)}
        for path in ROOT.rglob("*"):
            if path.is_symlink():
                raise BoundaryError("symlink resource not permitted in fixture coverage")
            self.allowed.add(str(path))
        self.stack = ExitStack()

    def check(self, path):
        if isinstance(path, int):
            raise BoundaryError("file descriptors not permitted")
        normalized = os.path.abspath(os.fsdecode(path))
        if normalized not in self.allowed:
            raise BoundaryError("out-of-root or undeclared resource access forbidden")

    def __enter__(self):
        for owner, name in ((builtins, "open"), (io, "open"), (os, "open")):
            original = getattr(owner, name)
            def opened(path, *args, _original=original, _os_open=owner is os, **kwargs):
                self.check(path)
                if kwargs.get("dir_fd") is not None or kwargs.get("opener") is not None:
                    raise BoundaryError("custom opener/descriptor access forbidden")
                mode = args[0] if args else kwargs.get("flags" if _os_open else "mode", os.O_RDONLY if _os_open else "r")
                if isinstance(mode, int):
                    if mode & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                        raise BoundaryError("fixture writes forbidden")
                elif any(char in mode for char in "wax+"):
                    raise BoundaryError("fixture writes forbidden")
                return _original(path, *args, **kwargs)
            self.stack.enter_context(patch.object(owner, name, opened))
        for name in ("stat", "lstat", "listdir", "scandir", "readlink", "access"):
            original = getattr(os, name)
            def inspected(path, *args, _original=original, **kwargs):
                self.check(path)
                if kwargs.get("dir_fd") is not None:
                    raise BoundaryError("relative descriptor access forbidden")
                return _original(path, *args, **kwargs)
            self.stack.enter_context(patch.object(os, name, inspected))
        for owner, name in ((subprocess, "Popen"), (os, "system"), (socket, "socket"),
                            (socket, "getaddrinfo")):
            self.stack.enter_context(patch.object(owner, name, side_effect=BoundaryError("commands/network forbidden")))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)


def exercise(fixture):
    # Exact approved fixtures only, before any caller-selected path access.
    names = {str(ROOT / "tests/fixtures" / name): name for name in EXPECTED}
    path = os.path.abspath(os.fspath(fixture))
    if path not in names:
        raise BoundaryError("fixture not in exact approved test allowlist")
    verifier = load_verifier()
    output = io.StringIO()
    with LocalReads(), patch.object(sys, "argv", ["TEST-ONLY", "--fixture", path]), redirect_stdout(output):
        code = verifier.main()
    return names[path], code, output.getvalue()


def matches(name, code, output):
    expected_code, diagnostic = EXPECTED[name]
    return (type(code) is int and code == expected_code and diagnostic in output
            and (code != 0 or "FAIL:" not in output))


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("TEST-ONLY: one exact approved fixture required")
        return 2
    try:
        name, code, output = exercise(args[0])
        print("TEST-ONLY: real production fixture path under resource fences; NOT live verification")
        print(output, end="")
        print(f"embedded_verifier_exit={code}")
        if not matches(name, code, output):
            print("wrapper: unexpected verifier result")
            return 1
        print("wrapper: expected fixture result observed")
        return 0
    except (BoundaryError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"wrapper: fail closed ({type(exc).__name__}: {exc})")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
