#!/usr/bin/env python3
"""The Hermes interfaces that the claude-subscription provider uses, checked against the installed Hermes.

Decision record docs/decisions/261120-plugin-behaviour-across-hermes-updates.md, section 3.3 (change 7).
Run from the repository root with any python3:

    python3 tests/test_hermes_interfaces_claude_subscription.py

The file runs twice. As the parent it takes the isolated HERMES_HOME, the minimal environment and the
interpreter of the installed Hermes from isolated_hermes_home() of tests/hermes_isolated_home.py, and
runs itself with that interpreter and the argument --child. The child imports the installed Hermes,
copies the provider into $HERMES_HOME/plugins/model-providers/claude-subscription and checks P1 to P10.
The parent prints one line per dependency ID with PASS or FAIL, prints a FAIL line for every ID the
child did not report (for example when the installed Hermes cannot be imported), and exits 1 on any
FAIL. P11 and P12 are not covered and are reported as such.

No model inference, no network (the child refuses every socket other than AF_UNIX, which the provider's
MCP bridge uses), no live profile state: P7 runs the client against the synthetic Claude command-line
program of tests/test_claude_subscription_provider.py (`--synthetic-runtime`), which writes recorded
stream events.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROVIDER = REPO_ROOT / "plugins" / "model-providers" / "claude-subscription"
FIXTURE_PROGRAM = REPO_ROOT / "tests" / "test_claude_subscription_provider.py"
IDS = ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10")
NOT_COVERED = {"P11": "environment variables of a Kanban worker; needs a dispatcher-started worker",
               "P12": "process_command_env_vars resolution; needs a real Claude command-line program"}
MODEL = "claude-opus-5-5"
# The 20 ProviderProfile fields that plugins/model-providers/claude-subscription/__init__.py sets.
PROFILE_FIELDS = ("name", "aliases", "display_name", "description", "api_mode", "auth_type", "base_url",
                  "env_vars", "process_command", "process_command_env_vars", "process_args",
                  "supports_health_check", "supports_model_listing", "supports_vision",
                  "supports_vision_tool_messages", "fixed_temperature", "default_max_tokens",
                  "fallback_models", "model_aliases", "model_capabilities")
TOOL = {"type": "function", "function": {"name": "read_file", "description": "Read a file",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                       "required": ["path"], "additionalProperties": False}}}


def child():
    """Checks P1 to P10 inside the isolated home with the interpreter of the installed Hermes."""
    import socket

    class UnixOnlySocket(socket.socket):  # a subclass, because ssl and asyncio subclass socket.socket
        def __init__(self, family=socket.AF_INET, *args, **kwargs):
            if family != socket.AF_UNIX:
                raise AssertionError(f"network access attempted (family={family!r})")
            super().__init__(family, *args, **kwargs)
    socket.socket = UnixOnlySocket

    import inspect
    import shutil
    checkout = Path(sys.argv[2])
    home = Path(os.environ["HERMES_HOME"])
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(checkout))
    shutil.copytree(PROVIDER, home / "plugins" / "model-providers" / "claude-subscription",
                    ignore=shutil.ignore_patterns("__pycache__"))

    def report(dep, ok, facts):
        print(f"{'PASS' if ok else 'FAIL'} {dep}: {facts}", flush=True)

    def run(dep, check):
        try:
            ok, facts = check()
        except Exception as exc:  # any error is a FAIL of this one ID; the others still run
            ok, facts = False, f"{type(exc).__name__}: {exc}"
        report(dep, ok, facts)

    import hermes_bootstrap  # noqa: F401  same import order as the helper's import exercise
    import providers
    from providers.base import OMIT_TEMPERATURE, ProviderProfile
    from agent.transports.chat_completions import ChatCompletionsTransport
    import agent.auxiliary_client as auxiliary_client
    import agent.redact as redact

    profile = providers.get_provider_profile("claude-subscription")
    found = profile is not None
    client_module = None
    state = {}

    def p1():
        source = providers.provider_source("claude-subscription")
        # Hermes v0.23.3 imports a copy that it makes under $HERMES_HOME/runtime/provider-plugins/.
        location = Path(inspect.getfile(type(profile))).resolve()
        return (source == "user" and location.is_relative_to(home.resolve()),
                f"provider_source={source!r} class file={location}")

    def p2():
        return (callable(getattr(providers, "register_provider", None)) and found,
                f"get_provider_profile returned {type(profile).__name__}")

    def p3():
        import dataclasses
        missing = sorted(set(PROFILE_FIELDS) - {f.name for f in dataclasses.fields(ProviderProfile)})
        return (found and isinstance(profile, ProviderProfile) and profile.auth_type == "external_process"
                and profile.api_mode == "chat_completions" and profile.fixed_temperature is OMIT_TEMPERATURE
                and not missing,
                f"auth_type={profile.auth_type!r} api_mode={profile.api_mode!r} "
                f"fields not in ProviderProfile={missing}")

    def p4():
        params = inspect.signature(ProviderProfile.create_client).parameters
        var_keyword = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
        client = profile.create_client(command="/synthetic/claude", args=[], api_key="claude-subscription",
                                       base_url="acp://claude-subscription")
        nonlocal client_module
        client_module = sys.modules[type(client).__module__]
        state["client"] = client
        return (var_keyword and type(client).__name__ == "ClaudeSubscriptionClient",
                f"ProviderProfile.create_client{inspect.signature(ProviderProfile.create_client)} "
                f"returned {type(client).__name__}")

    def p5():
        signature = inspect.signature(ProviderProfile.build_extra_body)
        params = signature.parameters
        ok = ("session_id" in params and params["session_id"].kind is inspect.Parameter.KEYWORD_ONLY
              and any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()))
        body = profile.build_extra_body(session_id="synthetic-session", model=MODEL)
        return (ok and body == {"subscription_session_id": "synthetic-session"},
                f"ProviderProfile.build_extra_body{signature}")

    def p6():
        client = state["client"]
        source = inspect.getsource(auxiliary_client)
        names = ("HERMES_SKIP_TRANSPORT_WRAP", "HERMES_SKIP_ASYNC_WRAP")
        return (all(getattr(client, n, False) is True for n in names) and all(n in source for n in names),
                "client sets both attributes and agent/auxiliary_client.py reads both names")

    def p7():
        program = home / "synthetic-claude"
        program.write_text(f'#!/bin/sh\nexec "{sys.executable}" -I -S -B "{FIXTURE_PROGRAM}" '
                           '--synthetic-runtime "$@"\n', encoding="utf-8")
        program.chmod(0o700)
        client = profile.create_client(command=str(program), args=[])
        transport = ChatCompletionsTransport()
        try:
            messages = [{"role": "system", "content": "Synthetic system"}, {"role": "user", "content": "__tool__"}]
            first = transport.normalize_response(client.chat.completions.create(model=MODEL, messages=messages,
                                                                                tools=[TOOL]))
            call = (first.tool_calls or [None])[0]
            messages = [*client._history.messages,
                        {"role": "tool", "tool_call_id": getattr(call, "id", None), "content": "RECORDED RESULT"}]
            second = transport.normalize_response(client.chat.completions.create(model=MODEL, messages=messages,
                                                                                 tools=[TOOL]))
        finally:
            client.close()
        ok = (first.finish_reason == "tool_calls" and len(first.tool_calls) == 1
              and call.id == "toolu_synthetic_1_1" and call.name == "read_file"
              and json.loads(call.arguments) == {"path": "/nonexistent/synthetic"}
              and second.finish_reason == "stop" and second.content == "RECORDED RESULT"
              and second.tool_calls is None and second.usage is not None
              and (second.usage.prompt_tokens, second.usage.completion_tokens) == (9, 2))
        return ok, (f"tool call {call.name if call else None}({call.arguments if call else None}) "
                    f"finish={first.finish_reason}; text {second.content!r} finish={second.finish_reason} "
                    f"usage prompt={getattr(second.usage, 'prompt_tokens', None)} "
                    f"completion={getattr(second.usage, 'completion_tokens', None)}")

    def p8():
        kwargs = ChatCompletionsTransport().build_kwargs(
            model=MODEL, messages=[{"role": "system", "content": "Synthetic system"},
                                   {"role": "user", "content": "Synthetic request"}],
            tools=[TOOL], provider_profile=profile, base_url=profile.base_url, timeout=300.0,
            max_tokens=4096, ephemeral_max_output_tokens=None, max_tokens_param_fn=lambda v: {"max_tokens": v},
            reasoning_config={"enabled": True, "effort": "medium"}, request_overrides=None,
            session_id="synthetic-session", cache_scope_id=None, ollama_num_ctx=None, provider_preferences=None,
            openrouter_min_coding_score=None, supports_reasoning=True, lmstudio_reasoning_options=None,
            qwen_session_metadata=None)
        options = sorted(kwargs)
        body = sorted(kwargs.get("extra_body") or {})
        extra_options = sorted(set(options) - client_module.ACCEPTED_OPTIONS)
        extra_keys = sorted(set(body) - client_module.ACCEPTED_EXTRA_BODY_KEYS)
        return (not extra_options and not extra_keys,
                f"keywords={options} extra_body={body}; not accepted: keywords={extra_options} "
                f"extra_body={extra_keys}")

    def p9():
        evict = getattr(auxiliary_client, "_evict_cached_client_instance", None)
        return callable(evict), f"agent.auxiliary_client._evict_cached_client_instance callable={callable(evict)}"

    def p10():
        params = inspect.signature(redact.redact_sensitive_text).parameters
        result = redact.redact_sensitive_text("synthetic text", force=True)
        return ("force" in params and isinstance(result, str),
                f"redact_sensitive_text{inspect.signature(redact.redact_sensitive_text)}")

    for dep, check in zip(IDS, (p1, p2, p3, p4, p5, p6, p7, p8, p9, p10)):
        if not found and dep != "P9" and dep != "P10":
            report(dep, False, "providers.get_provider_profile('claude-subscription') returned None")
        elif client_module is None and dep in ("P6", "P8"):
            report(dep, False, "no client from create_client (see P4)")
        else:
            run(dep, check)
    return 0


def parent():
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from hermes_isolated_home import IsolatedHomeError, isolated_hermes_home
    lines, returncode, problem = [], None, None
    try:
        with isolated_hermes_home() as iso:
            command = iso.child_command(Path(__file__).resolve()) + ["--child", str(iso.checkout_root)]
            result = subprocess.run(command, env=iso.env, capture_output=True, text=True, timeout=600,
                                    check=False, cwd=str(iso.home))
            lines, returncode = result.stdout.splitlines(), result.returncode
            if returncode != 0:
                problem = f"child exited {returncode}: {result.stderr.strip()[-1500:]}"
    except (IsolatedHomeError, OSError, subprocess.SubprocessError) as exc:
        problem = f"installed Hermes not available: {type(exc).__name__}: {exc}"
    reported = {}
    for line in lines:
        status, _, rest = line.partition(" ")
        dep = rest.split(":", 1)[0]
        if status in ("PASS", "FAIL") and dep in IDS:
            reported[dep] = status
            print(line)
    for dep in IDS:
        if dep not in reported:
            reported[dep] = "FAIL"
            print(f"FAIL {dep}: no result for this ID from the installed Hermes")
    for dep, reason in NOT_COVERED.items():
        print(f"NOT COVERED {dep}: {reason} (decision record section 3.3)")
    failed = sorted((d for d, s in reported.items() if s == "FAIL"), key=IDS.index)
    if problem:
        print(f"FAIL child: {problem}")
        failed = failed or ["child"]
    print(f"{'FAILED' if failed else 'OK'}: {len(IDS) - len(failed)} of {len(IDS)} dependencies passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(child() if sys.argv[1:2] == ["--child"] else parent())
