"""Bounded OFFLINE hypotheses, not a provider. See README generation2 limits.

Only named inspected source bodies execute. Imports/annotations are removed;
all peripheral bindings are explicit fakes. No downloaded module is imported.
"""
import ast
import builtins
from contextlib import contextmanager, suppress
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace as NS
from urllib.parse import parse_qs, urlparse, urlunparse

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT.parents[1] / "private/feasibility"
SOURCES = {
    "main-helpers.py.txt": "735612c07ffb2d28e5d1ab555578c961e34e7e70fd53404fec574e61954e805a",
    "get-2.txt": "41d019d18574e69f64c95b8711132f08170db7c2b061e8a56578cdbd41f33cf9",
    "generation2-client_lifecycle.py.txt": "5333b2dd5c96427996f060e9c01f6ca86d882cb89a59f60482e2281de8b66d5f",
    "generation2-agent_init.py.txt": "5befa4177caab596804f185379cbd86e3c91507693f12e20057aae122907cf0d",
    "generation2-chat_completion_helpers.py.txt": "15c2aa0e7863495546ad1bbaf8ad9c67de12fdbc65f10b91c7f51a210d0a5214",
    "generation2-turn_tool_round.py.txt": "8afef412460a4a6a0d3df0ec219919a736ba376f4add81864fd49c0e758c531f",
}
ACTIVE = False
OWNED_HOMES = set()


def audit(event, args):
    if not ACTIVE:
        return
    if event.startswith("socket.") or event in {"urllib.Request", "http.client.connect"}:
        raise AssertionError("network denied")
    if event == "open" and isinstance(args[0], (str, bytes)):
        path = Path(os.fsdecode(args[0])).resolve()
        source = path in {EVIDENCE / name for name in SOURCES}
        stdlib = path.is_relative_to(Path(sys.base_prefix).resolve()) and path.suffix == ".py"
        if not (source or stdlib or path in OWNED_HOMES):
            raise AssertionError("file denied")
        assert not args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC), "file writes denied"
    if event == "subprocess.Popen":
        executable, argv, cwd, env = args
        assert executable == str(Path(sys.executable).resolve())
        assert argv[:4] == [executable, "-I", "-S", str(ROOT / "fake_runtime.py")]
        assert argv[4:5] == ["rendezvous"]
        assert set(env) == {"HOME", "PATH", "LANG", "LC_ALL"}
        assert Path(cwd) == Path(env["HOME"]) and Path(cwd).parent == EVIDENCE
        OWNED_HOMES.add(Path(cwd).resolve())


sys.addaudithook(audit)


@contextmanager
def guarded():
    global ACTIVE
    previous, ACTIVE = ACTIVE, True
    try:
        yield
    finally:
        ACTIVE = previous


def denied_import(*args, **kwargs):
    raise ImportError("imports denied")


class BodyOnly(ast.NodeTransformer):
    def visit_Import(self, node):
        return ast.copy_location(ast.Pass(), node)

    visit_ImportFrom = visit_Import

    def visit_FunctionDef(self, node):
        node.returns, node.decorator_list = None, []
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs,
                    *([node.args.vararg] if node.args.vararg else []),
                    *([node.args.kwarg] if node.args.kwarg else [])):
            arg.annotation = None
        return self.generic_visit(node)


def load(filename, names, namespace):
    assert filename in SOURCES, "source not frozen"
    raw = (EVIDENCE / filename).read_bytes()  # Missing copies fail explicitly.
    assert hashlib.sha256(raw).hexdigest() == SOURCES[filename], "source drift"
    tree = ast.parse(raw)
    candidates = list(tree.body)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            candidates.extend(node.body)
    functions = [n for n in candidates if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(functions) == len(names) and {n.name for n in functions} == names
    module = BodyOnly().visit(ast.Module(body=functions, type_ignores=[]))
    namespace["__builtins__"] = {name: getattr(builtins, name) for name in (
        "getattr", "setattr", "hasattr", "str", "dict", "list", "tuple", "set", "bool",
        "isinstance", "int", "float", "len", "enumerate", "all", "any", "next", "type",
        "callable", "Exception", "RuntimeError", "ValueError", "ImportError", "min", "max",
    )}
    namespace["__builtins__"]["__import__"] = denied_import
    exec(compile(ast.fix_missing_locations(module), filename, "exec"), namespace)
    return namespace


LOGGER = NS(**{name: lambda *a, **k: None for name in ("warning", "info", "debug", "error")})


class ProtocolError(Exception):
    pass


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class Rendezvous:
    """Single outstanding synthetic MCP request; fail-stop, never resume/reattach."""
    def __init__(self, scope, variant=""):
        self.scope, self.variant = tuple(scope), variant
        self.sent, self.calls, self.pending = [], 0, None
        self.child, self.home, self.closed, self.buffer = None, None, False, b""
        self.chat = NS(completions=self)

    def _line(self):
        deadline = time.monotonic() + 2
        with selectors.DefaultSelector() as selector:
            selector.register(self.child.stdout, selectors.EVENT_READ)
            while b"\n" not in self.buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(timeout=remaining):
                    raise ProtocolError("inert deadline")
                chunk = os.read(self.child.stdout.fileno(), 16384)
                if not chunk:
                    raise ProtocolError("inert process death")
                self.buffer += chunk
                if len(self.buffer) > 65536:
                    raise ProtocolError("inert output bound")
        line, self.buffer = self.buffer.split(b"\n", 1)
        return json.loads(line)

    def create(self, *, messages, scope):
        try:
            if tuple(scope) != self.scope:
                raise ProtocolError("scope mismatch")
            if self.closed:
                raise ProtocolError("closed session")
            self.calls += 1
            if self.child is None:
                self.home = tempfile.TemporaryDirectory(prefix="rendezvous-", dir=EVIDENCE)
                env = {"HOME": self.home.name, "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
                self.child = subprocess.Popen(
                    [str(Path(sys.executable).resolve()), "-I", "-S", str(ROOT / "fake_runtime.py"),
                     "rendezvous", self.variant], cwd=self.home.name, env=env, start_new_session=True,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                event, self.pending = self._line(), self._line()
                tools = event.get("message", {}).get("content", [])
                rpc = self.pending.get("request", {}).get("message", {})
                params = rpc.get("params", {})
                if (event.get("type") != "assistant" or len(tools) != 1
                        or tools[0].get("type") != "tool_use" or not tools[0].get("id")
                        or self.pending.get("type") != "control_request"
                        or self.pending.get("request_id") != "control-1"
                        or self.pending["request"].get("subtype") != "mcp_message"
                        or self.pending["request"].get("server_name") != "hermes"
                        or rpc.get("jsonrpc") != "2.0" or rpc.get("id") != 7
                        or rpc.get("method") != "tools/call"
                        or tools[0].get("name") != "mcp__hermes__" + params.get("name", "")
                        or tools[0].get("input") != params.get("arguments")):
                    raise ProtocolError("model/MCP lineage")
                self.tool = tools[0]
                self.prefix = json.loads(json.dumps(messages))
                tc = NS(id=self.tool["id"], type="function", function=NS(
                    name=params["name"], arguments=json.dumps(params["arguments"])))
                return NS(finish_reason="tool_calls", message=NS(content="", tool_calls=[tc]))
            tail = messages[len(self.prefix):]
            expected = {"name": self.pending["request"]["message"]["params"]["name"],
                        "arguments": json.dumps(self.tool["input"])}
            if (messages[:len(self.prefix)] != self.prefix or len(tail) != 2
                    or tail[0].get("role") != "assistant" or len(tail[0].get("tool_calls", [])) != 1
                    or tail[0]["tool_calls"][0].get("id") != self.tool["id"]
                    or tail[0]["tool_calls"][0].get("function") != expected
                    or tail[1].get("role") != "tool" or tail[1].get("tool_call_id") != self.tool["id"]
                    or not isinstance(tail[1].get("content"), str)):
                raise ProtocolError("result lineage")
            result = {"content": [{"type": "text", "text": tail[1]["content"]}], "isError": False}
            reply = {"type": "control_response", "response": {"subtype": "success",
                "request_id": self.pending["request_id"], "response": {"mcp_response": {
                    "jsonrpc": "2.0", "id": self.pending["request"]["message"]["id"], "result": result}}}}
            self.child.stdin.write((json.dumps(reply) + "\n").encode())
            self.child.stdin.flush()
            self.sent.append(reply)
            event = self._line()
            self.child.wait(timeout=2)
            if event.get("type") != "result" or self.child.returncode != 0:
                raise ProtocolError("inert completion")
            return NS(finish_reason="stop", receipt=event["result_hash"])
        finally:
            # Park only a valid first response. Every failure or continuation retires state.
            if sys.exc_info()[0] is not None or self.calls == 2:
                self.cancel()
                self.cancel()

    @guarded()
    def cancel(self):
        self.closed, self.pending = True, None
        if self.child is not None:
            if self.child.poll() is None:
                with suppress(ProcessLookupError):
                    assert os.getpgid(self.child.pid) == self.child.pid
                    os.killpg(self.child.pid, signal.SIGKILL)
            self.child.wait(timeout=2)
            for stream in (self.child.stdin, self.child.stdout, self.child.stderr):
                stream.close()
        if self.home is not None:
            self.home.cleanup()

    def cleaned(self):
        if self.child is None:
            return self.closed
        try:
            os.killpg(self.child.pid, 0)
        except ProcessLookupError:
            return self.child.poll() is not None and not Path(self.home.name).exists()
        return False


@guarded()
def dispatch(client, messages, scope):
    ns = load("generation2-chat_completion_helpers.py.txt", {"_dispatch_nonstreaming_api_request"}, {
        "bypass_chat_sdk_request_transform": lambda kwargs, client: kwargs,
    })
    return ns["_dispatch_nonstreaming_api_request"](
        NS(api_mode="chat_completions", provider="synthetic"), {"messages": messages, "scope": scope},
        make_client=lambda *a, **k: client)


@guarded()
def tool_round(message, messages, events, persisted=True):
    # Actual Hermes round + actual call-ID serialization. Permissions, execution,
    # persistence, compression, timestamp and surrounding presentation are FAKES.
    ns = {"logger": LOGGER, "suppress": suppress, "ToolRoundVerdict": lambda **k: NS(**k),
          "validate_tool_calls": lambda *a, **k: NS(action="execute", mixed_invalid_batch=False),
          "expand_local_tool_batches": lambda calls, **k: calls,
          "normalize_provider_tool_call_ids": lambda calls: None,
          "append_message": lambda messages, row: messages.append(row),
          "finish_tool_round": lambda agent: None,
          "_HOUSEKEEPING_TOOLS": frozenset(),
          "_STALE_MARKER_RE": __import__("re").compile(r"^\[[A-Za-z_]+\]$"),
          "_assistant_reasoning_text": lambda *a: None,
          "_assistant_content_for_storage": lambda a, msg: msg.content,
          "stamp_message_timestamp": lambda msg: msg}
    def post_tool(agent, **kwargs):
        events.append("post_tool")
        return NS(**kwargs, end_turn=False)
    ns["compress_after_tool_results"] = post_tool
    load("generation2-chat_completion_helpers.py.txt", {"build_assistant_message", "_assistant_tool_call_dict"}, ns)
    load("generation2-turn_tool_round.py.txt", {"stage_tool_call_message", "run_tool_round"}, ns)
    agent = NS(quiet_mode=True, verbose_logging=False, valid_tool_names={"fixture_read"},
               stream_delta_callback=None, _tool_guardrail_halt_decision=None,
               _cap_delegate_task_calls=lambda calls: calls, _deduplicate_tool_calls=lambda calls: calls,
               _split_responses_tool_id=lambda raw: (raw, None),
               _derive_responses_function_call_id=lambda call, item: item,
               _needs_thinking_reasoning_pad=lambda: False,
               _interim_assistant_visible_text=lambda msg: "", _emit_interim_assistant_message=lambda msg: None,
               _touch_activity=lambda text: None)
    agent._build_assistant_message = lambda msg, finish: ns["build_assistant_message"](agent, msg, finish)
    def persist(*args):
        events.append("persist")
        return persisted
    def fake_execute(message, messages, task, count):
        events.extend(["fake_permission", "fake_execution"])
        tc = message.tool_calls[0]
        assert task == "t_fixture" and tc.function.name in agent.valid_tool_names
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": "HARNESS_READ_OK\n"})
    agent._flush_messages_to_session_db, agent._execute_tool_calls = persist, fake_execute
    return ns["run_tool_round"](agent, assistant_message=message, finish_reason="tool_calls", messages=messages,
        conversation_history=[], api_call_count=1, effective_task_id="t_fixture", user_message="fixture",
        system_message="synthetic", active_system_prompt="synthetic", compression_attempts=0,
        max_compression_attempts=0, final_response="", failed=False, _turn_exit_reason="",
        truncated_tool_call_retries=0, current_turn_user_idx=0)


class ForbiddenRoute(Exception):
    pass


@guarded()
def construction(factory_raises=False):
    routes, validators = [], []
    def factory(**kwargs):
        routes.append("profile")
        if factory_raises:
            raise RuntimeError("synthetic factory failure")
        return NS(is_closed=False)  # Lazy: no startup/network during construction.
    def http(**kwargs):
        routes.append("FORBIDDEN_HTTP_CONSTRUCTOR")
        raise ForbiddenRoute("never constructed/sent")
    profile = NS(name="synthetic", default_headers={}, create_client=factory,
                 build_client_kwargs_extras=lambda **k: {})
    ns = {"logger": LOGGER, "_ra": lambda: NS(logger=LOGGER), "suppress": suppress,
          "urlparse": urlparse, "urlunparse": urlunparse, "parse_qs": parse_qs,
          "get_provider_profile": lambda name: profile, "_gpf": lambda name: profile,
          "_is_external_process_provider": lambda name: True,
          "_host_default_headers_factory": lambda url: None,
          "_apply_openai_header_policy": lambda *a: None,  # Fake TLS/header peripherals.
          "configure_bedrock_openai_client_kwargs": lambda *a, **k: None,
          "is_actual_route": lambda *a: False,
          "resolve_httpx_verify": lambda **k: True,
          "normalize_proxy_env_vars": lambda: None, "os": NS(environ={}),
          "_GEMINI_NATIVE_PROVIDER_NAMES": set(), "_ensure_copilot_headers": lambda *a: None,
          "apply_required_codex_headers": lambda *a, **k: None,
          "process_bootstrap": NS(OpenAI=http)}
    load("get-2.txt", {"_validate_base_url", "_validate_proxy_env_urls"}, ns)
    validate = ns["_validate_base_url"]
    def observed_validate(url):
        validators.append(url)
        return validate(url)  # Instrument, never change the actual validator's decision.
    ns["_validate_base_url"] = observed_validate
    load("main-helpers.py.txt", {"_provider_supplied_client", "create_openai_client"}, ns)
    load("generation2-agent_init.py.txt", {"_explicit_client_kwargs", "_init_openai_client"}, ns)
    load("generation2-client_lifecycle.py.txt", {"_replace_primary_openai_client"}, ns)
    agent = NS(provider="synthetic", base_url="acp://synthetic", model="fixture-model", quiet_mode=True,
               acp_command="inert-not-launched", acp_args=[], _client_log_context=lambda: "synthetic",
               _build_keepalive_http_client=lambda *a, **k: None,
               _openai_client_lock=threading.RLock, _retire_shared_openai_client=lambda *a, **k: None)
    agent._create_openai_client = lambda kwargs, **k: ns["create_openai_client"](agent, kwargs, **k)
    replaced = False
    try:
        ns["_init_openai_client"](agent, "synthetic-not-a-credential", agent.base_url, [], None)
        replaced = ns["_replace_primary_openai_client"](agent, reason="synthetic_call_failure")
    except RuntimeError:
        assert factory_raises and routes[-1] == "FORBIDDEN_HTTP_CONSTRUCTOR"
    return {"routes": routes, "replaced": replaced, "validators": validators}


@guarded()
def main_recovery():
    routes = []
    ns = {"logger": LOGGER, "switch_deferred_by_reset": lambda *a: False,
          "_arm_rate_limit_cooldown": lambda *a, **k: None,
          "resolve_provider_client": lambda *a, **k: routes.append("FORBIDDEN_PROVIDER")}
    load("generation2-chat_completion_helpers.py.txt", {"try_activate_fallback", "_fallback_chain_exhausted"}, ns)
    load("main-helpers.py.txt", {"recover_with_credential_pool"}, ns)
    agent = NS(_fallback_chain=[], _fallback_index=0, _credential_pool=None)
    return {"fallback": ns["try_activate_fallback"](agent),
            "pool": ns["recover_with_credential_pool"](agent, status_code=429, has_retried_429=True),
            "routes": routes}


@guarded()
def aux_unavailable():
    routes = []
    factories = []
    def factory(**kwargs):
        factories.append("startup_failure")
        raise RuntimeError("synthetic startup failure")
    def no_client(*a, **k):
        assert a[0] == "synthetic", "unexpected auto/provider route"
        routes.append("explicit_client_unavailable")
        req = NS(provider="synthetic", model="fixture-model", main_runtime={}, async_mode=False)
        return ns["_resolve_external_process_branch"](req, {
            "api_key": "synthetic-not-a-credential", "base_url": "acp://synthetic"})
    def config(task):
        routes.append("task_chain_empty")
        return {"fallback_chain": []}
    ns = {"logger": LOGGER, "_get_cached_client": no_client,
          "_effective_provider_for_client": lambda client, provider: provider,
          "_get_auxiliary_task_config": config,
          "_get_provider_profile": lambda provider: NS(create_client=factory),
          "_normalize_resolved_model": lambda model, provider: model,
          "_log_once_debug": lambda *a: None, "_LOGGED_UNSUPPORTED_EXTPROC_KEYS": set(),
          "AuxiliaryClientUnavailable": ForbiddenRoute,
          "missing_provider_credentials_message": lambda p: "synthetic unavailable"}
    load("get-2.txt", {"_resolve_call_client", "_resolve_external_process_branch",
                       "_try_configured_fallback_chain", "_try_configured_fallback_for_unavailable_client"}, ns)
    try:
        ns["_resolve_call_client"]("compression", provider="synthetic", model="fixture-model", base_url=None,
            api_key=None, resolved_provider="synthetic", resolved_model="fixture-model", resolved_base_url=None,
            resolved_api_key=None, resolved_api_mode=None, main_runtime={"provider": "synthetic"}, async_mode=False)
    except ForbiddenRoute:
        routes.append("unavailable")
    assert factories == ["startup_failure"]
    return routes


@guarded()
def aux_recovery(disk_provider):
    routes = []
    def config(task):
        # Called once to inspect policy and once by the actual empty-chain body.
        if not routes:
            routes.append("task_chain_empty")
        return {"fallback_chain": []}
    def read_main():
        routes.append("disk_main:" + disk_provider)
        return disk_provider
    def resolve(*a, provider, **k):
        if provider != "synthetic":
            routes.append("FORBIDDEN_PROVIDER:" + provider)
            raise ForbiddenRoute("attempt intercepted")
        routes.append("own_client")
        return NS(base_url="acp://synthetic"), "fixture-model"
    ns = {"logger": LOGGER, "_get_auxiliary_task_config": config,
          # Classification is a fake quota fixture. Actual selected recovery bodies below are unmodified.
          "_FALLBACK_REASONS": ((lambda error: True, "rate limit"),),

          "_read_main_provider": read_main, "_read_main_model": lambda: "fixture-model",
          "_custom_health_base_url": lambda *a: "", "_is_provider_unhealthy": lambda *a: False,
          "_failed_backend_skip": lambda *a, **k: lambda *a: False,  # Identity peripheral is fake.
          "resolve_provider_client": resolve, "_record_route_info": lambda *a: None,
          "_fallback_provider_from_label": lambda label: disk_provider,
          "_LadderStep": lambda kind, args: NS(kind=kind, args=args)}
    load("get-2.txt", {"_ladder_provider_fallback", "_try_main_agent_model_fallback",
                       "_try_configured_fallback_chain"}, ns)
    route = NS(task="compression", tag="", resolved_provider="synthetic", client=object(),
               base_info="acp://synthetic", final_model="fixture-model", timeout=2, route_info={},
               main_runtime={"provider": "synthetic", "model": "fixture-model"})
    ladder = ns["_ladder_provider_fallback"](RuntimeError("synthetic quota exceeded"), route)
    try:
        next(ladder)  # Only inspect the proposed fallback step. Never perform its request.
    except StopIteration:
        pass
    finally:
        ladder.close()
    return routes


@guarded()
def discovery_control():
    routes = []
    def forbidden_chain():
        routes.append("FORBIDDEN_DISCOVERY")
        raise ForbiddenRoute("discovery intercepted")
    ns = {"logger": LOGGER, "_normalize_main_runtime": lambda runtime: runtime,
          "_get_provider_chain": forbidden_chain}
    load("get-2.txt", {"_try_payment_fallback", "_discovery_chain_allowed"}, ns)
    assert ns["_try_payment_fallback"]("synthetic", "compression", main_runtime={
        "provider": "synthetic"}) == (None, None, "")
    return routes
