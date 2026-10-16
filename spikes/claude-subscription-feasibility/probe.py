"""Offline source-path and inert-process mechanisms, NOT a provider adapter."""
import ast
import builtins
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT.parents[1] / "private/feasibility"
SOURCES = {
    "main-helpers.py.txt": "735612c07ffb2d28e5d1ab555578c961e34e7e70fd53404fec574e61954e805a",
    "get-2.txt": "41d019d18574e69f64c95b8711132f08170db7c2b061e8a56578cdbd41f33cf9",
}


class RemoveImports(ast.NodeTransformer):
    """Only inspected function bodies run; imports never resolve installed code."""
    def visit_Import(self, node):
        return ast.copy_location(ast.Pass(), node)

    def visit_ImportFrom(self, node):
        return ast.copy_location(ast.Pass(), node)


def extract(filename, names, namespace):
    raw = (EVIDENCE / filename).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCES[filename], "Source drift"
    tree = ast.parse(raw)
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in functions} == set(names)
    for function in functions:
        function.returns = None
        function.decorator_list = []
        for arg in (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs):
            arg.annotation = None
        if function.args.kwarg:
            function.args.kwarg.annotation = None
        RemoveImports().visit(function)
    module = ast.fix_missing_locations(ast.Module(body=list(functions), type_ignores=[]))
    # No imports, file access, SDK execution or network dependency is supplied.
    namespace["__builtins__"] = {name: getattr(builtins, name) for name in (
        "getattr", "str", "dict", "list", "isinstance", "int", "float", "Exception",
    )}
    exec(compile(module, filename, "exec"), namespace)


class ForbiddenRoute(Exception):
    pass


def constructor_routes(factory_raises=False):
    routes = {"main": [], "auxiliary": []}
    logger = SimpleNamespace(warning=lambda *a, **k: None,
                             debug=lambda *a, **k: None, info=lambda *a, **k: None)
    for route in routes:
        def create_client(**kwargs):
            routes[route].append("profile")
            if factory_raises:
                raise RuntimeError("synthetic startup failure")
            return object()

        def forbidden_http(**kwargs):
            routes[route].append("FORBIDDEN_HTTP_CONSTRUCTOR")
            raise ForbiddenRoute("HTTP construction intercepted, never sent")

        profile = SimpleNamespace(name="synthetic", create_client=create_client,
                                  build_client_kwargs_extras=lambda **k: {})
        ns = {
            "get_provider_profile": lambda name: profile,
            "_get_provider_profile": lambda name: profile,
            "_ra": lambda: SimpleNamespace(logger=logger), "logger": logger,
            "resolve_httpx_verify": lambda **k: True,
            "_validate_proxy_env_urls": lambda: None, "_validate_base_url": lambda u: None,
            "_GEMINI_NATIVE_PROVIDER_NAMES": set(),
            "_ensure_copilot_headers": lambda k: None,
            "apply_required_codex_headers": lambda *a, **k: None,
            "process_bootstrap": SimpleNamespace(OpenAI=forbidden_http),
            "_normalize_resolved_model": lambda m, p: m,
            "_log_once_debug": lambda *a: None, "_LOGGED_UNSUPPORTED_EXTPROC_KEYS": set(),
        }
        agent = SimpleNamespace(provider="synthetic", _client_log_context=lambda: "synthetic",
                                _build_keepalive_http_client=lambda *a, **k: None)
        kwargs = {"api_key": "synthetic-not-a-credential", "base_url": "acp://synthetic"}
        if route == "main":
            extract("main-helpers.py.txt", {"_provider_supplied_client", "create_openai_client"}, ns)
            try:
                ns["create_openai_client"](agent, kwargs, reason="offline", shared=False)
            except ForbiddenRoute:
                pass
        else:
            extract("get-2.txt", {"_resolve_external_process_branch", "_route_client"}, ns)
            req = SimpleNamespace(provider="synthetic", model="fixture-model", async_mode=False)
            client, model = ns["_resolve_external_process_branch"](req, kwargs)
            assert (client is None) == factory_raises
    return routes


def exchange(timeout_mode=False):
    fixture = json.loads((ROOT / "fixtures.json").read_text())
    stdout = []
    timed_out = False
    with tempfile.TemporaryDirectory(prefix="inert-", dir=EVIDENCE) as home:
        env = {"HOME": home, "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
        command = [str(Path(sys.executable).resolve()), "-I", "-S", str(ROOT / "fake_runtime.py")]
        if timeout_mode:
            command.append("timeout")
        child = subprocess.Popen(command, cwd=home, env=env, start_new_session=True,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)

        def cleanup():
            if child.poll() is None:
                try:
                    assert os.getpgid(child.pid) == child.pid
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            child.wait(timeout=2)

        try:
            assert child.stdin is not None and child.stdout is not None and child.stderr is not None
            assert os.getpgid(child.pid) == child.pid
            child.stdin.write(json.dumps(fixture["request"]) + "\n")
            child.stdin.flush()
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                if not selector.select(timeout=2):
                    raise subprocess.TimeoutExpired(command, 2)
                line = child.stdout.readline()
                assert line, child.stderr.read()
                request = json.loads(line)
            # Frozen synthetic authorization only; NOT the Hermes executor.
            assert request == fixture["request"]
            stdout.append(request)
            rest, error = child.communicate(json.dumps(fixture["response"]) + "\n", timeout=2)
            assert not error, error
            stdout.extend(json.loads(line) for line in rest.splitlines())
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            cleanup()
            cleanup()  # Idempotence exercised on every path.
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None:
                    stream.close()
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            group_absent = True
        else:
            group_absent = False
        return {"stdout": stdout, "timed_out": timed_out, "returncode": child.returncode,
                "pid": child.pid, "reaped": child.poll() is not None, "group_absent": group_absent}
