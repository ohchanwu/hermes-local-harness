"""Owner-run live smoke test for one Claude CLI version and model. Never retries.

    python3 plugins/model-providers/claude-subscription/smoke.py --cli <path> --model <model>

Two sessions through the real client. The first does one synthetic read-only
tool round trip and one follow-up turn. The second is a new client handed that
whole transcript, so it must rebuild the session and recall the tool result. This is a live model call on the subscription; run it only
deliberately. It uses a throwaway HERMES_HOME, so no live Hermes state is touched.
"""
import argparse
import importlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import types

PLUGIN = Path(__file__).resolve().parent
TOOL = {"type": "function", "function": {"name": "read_file", "description": "Read a text file",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}},
                       "required": ["path"], "additionalProperties": False}}}


def load():
    """The plugin's modules without __init__.py, which imports installed Hermes."""
    package = types.ModuleType("claude_subscription_smoke")
    package.__path__ = [str(PLUGIN)]
    sys.modules[package.__name__] = package
    return importlib.import_module(package.__name__ + ".client"), importlib.import_module(package.__name__ + ".compat")


def check(condition, reason):
    if not condition:
        raise AssertionError(reason)


def run(command, model, workdir):
    client, compat = load()
    fixture = Path(workdir) / "fixture.txt"
    nonce = "SMOKE-" + secrets.token_hex(8)
    fixture.write_text(nonce)
    c = client.ClaudeSubscriptionClient(command=command)
    try:
        messages = [{"role": "system", "content": "You are a test harness. Use the provided tool when asked."},
                    {"role": "user", "content": f"Call read_file with path {fixture} and reply with exactly its content."}]
        first = c.create(model=model, messages=messages, tools=[TOOL])
        check(first.choices[0].finish_reason == "tool_calls", "no tool call")
        call = first.choices[0].message.tool_calls[0]
        check(call.function.name == "read_file", "wrong tool")
        arguments = json.loads(call.function.arguments)
        # The smoke test plays Hermes: it alone executes the tool, for the fixture only.
        result = fixture.read_text() if arguments.get("path") == str(fixture) else "error: unexpected path"
        messages += [first.choices[0].message.model_dump(exclude_none=True),
                     {"role": "tool", "tool_call_id": call.id, "content": result}]
        second = c.create(model=model, messages=messages, tools=[TOOL])
        check(second.choices[0].finish_reason == "stop" and nonce in second.choices[0].message.content,
              "tool result not used")
        messages += [{"role": "assistant", "content": second.choices[0].message.content},
                     {"role": "user", "content": "Reply with exactly the word FOLLOWUP."}]
        third = c.create(model=model, messages=messages, tools=[TOOL])
        check("FOLLOWUP" in third.choices[0].message.content, "follow-up failed")
        stages = [a["stage"] for a in c.audit]
        check(stages.count("result_returned") == 1 and stages.count("launch") == 1, "unexpected bridge/launch audit")
        version = c._cli_version
        messages += [{"role": "assistant", "content": third.choices[0].message.content},
                     {"role": "user", "content": "Without using any tools, reply with only the exact content "
                                                 "of the file you read earlier in this conversation."}]
    finally:
        c.close()
    check(c._runtime is not None and c._runtime.cleanup["group_absent"], "runtime process group not reaped")
    rebuilt = client.ClaudeSubscriptionClient(command=command)
    try:
        fourth = rebuilt.create(model=model, messages=messages, tools=[TOOL])
        check(fourth.choices[0].finish_reason == "stop", "rebuilt session repeated the tool call instead of recalling")
        check(nonce in fourth.choices[0].message.content, "rebuilt session did not recall the tool result")
        check([a["stage"] for a in rebuilt.audit].count("rebuild") == 1, "no recorded rebuild")
    finally:
        rebuilt.close()
    check(rebuilt._runtime is not None and rebuilt._runtime.cleanup["group_absent"], "rebuilt process group not reaped")
    return compat.version_text(version), version in compat.CLI_TESTED, version


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cli", required=True, help="path to the provider's dedicated Claude CLI")
    parser.add_argument("--model", required=True)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="claude-subscription-smoke-") as workdir:
        os.environ["HERMES_HOME"] = workdir  # throwaway cache home
        try:
            text, tested, version = run(args.cli, args.model, workdir)
        except Exception as exc:  # one attempt; report, never retry
            print(f"SMOKE FAIL: {type(exc).__name__}: {exc}")
            return 1
    print(f"SMOKE PASS cli={text} model={args.model}")
    if not tested:
        print(f"Add to compat.CLI_TESTED: {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
