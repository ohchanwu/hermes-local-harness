"""Compatibility constants: the only home for model and CLI version literals."""

PREFIX = "mcp__hermes__"

# Oldest CLI with every flag/event this client relies on, and the versions that
# passed the live smoke test (smoke.py). Newer untested versions only warn.
CLI_MINIMUM = (2, 1, 283)
CLI_TESTED = {(2, 1, 283), (2, 1, 302)}

# Allowlisted models and their Hermes capabilities. The served model must equal
# the requested one; a provider-side variant name goes in "served_aliases".
MODELS = {"claude-opus-5-5": {"context_length": 1000000},
          "claude-fable-5-1": {"context_length": 1000000}}

# Fixed runtime flags. Per-session values (model, paths, tools, system prompt)
# are appended by the client.
CLI_FLAGS = ["--print", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
             "--no-session-persistence", "--restricted", "--setting-sources", "",
             "--disable-slash-commands", "--no-chrome", "--tools", "", "--strict-mcp-config",
             "--permission-mode", "dontAsk", "--permission-prompts", "none"]

EFFORT_SETTING = "HERMES_CLAUDE_SUBSCRIPTION_EFFORT"
EFFORTS = ("low", "medium", "high", "xhigh", "max")
DEFAULT_EFFORT = "medium"

# Official headless login from `claude setup-token`, kept in an owner-only file and
# handed to the CLI as an open descriptor: Hermes passes a CLAUDE_CODE_OAUTH_TOKEN
# variable to every tool subprocess, so the token never travels as a variable.
# Unset means the Keychain login is used.
TOKEN_FILE_SETTING = "HERMES_CLAUDE_SUBSCRIPTION_TOKEN_FILE"
TOKEN_FD_VARIABLE = "CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR"

# Hermes resolves the provider's dedicated, version-locked CLI from this setting.
CLI_SETTING = "HERMES_CLAUDE_SUBSCRIPTION_CLI"

CHILD_ENV = {"DISABLE_AUTOUPDATER": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL": "1",
             "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
             "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1", "CLAUDE_CODE_DISABLE_CRON": "1",
             "CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK": "1", "CLAUDE_CODE_MAX_RETRIES": "0",
             "DISABLE_AUTO_COMPACT": "1",
             "ENABLE_CLAUDEAI_MCP_SERVERS": "false", "ENABLE_TOOL_SEARCH": "false"}

SETTINGS = {"disableAllHooks": True, "autoMemoryEnabled": False, "syncClaudeAiPlugins": False,
            "claudeMdExcludes": ["**"], "enabledPlugins": {}}


def version_text(version):
    return ".".join(map(str, version))


def served_names(model):
    return {model, *MODELS[model].get("served_aliases", ())}
