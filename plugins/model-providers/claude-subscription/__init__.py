"""Opt-in, uniquely named official-CLI subscription provider (no HTTP client)."""
from providers import register_provider
from providers.base import OMIT_TEMPERATURE, ProviderProfile

from .client import ClaudeSubscriptionClient
from .compat import MODELS


class ClaudeSubscriptionProfile(ProviderProfile):
    def create_client(self, **client_kwargs):
        # Construction is deliberately lazy and stdlib-only. Runtime failures
        # belong to create(), not Hermes' exception-to-HTTP factory fallback.
        return ClaudeSubscriptionClient(**client_kwargs)

    def build_extra_body(self, *, session_id=None, **context):
        return {"subscription_session_id": session_id}


claude_subscription = ClaudeSubscriptionProfile(
    name="claude-subscription", aliases=(), display_name="Claude subscription (serial CLI)",
    description="Bounded synchronous text/tool session; official CLI owns subscription authentication",
    api_mode="chat_completions", auth_type="external_process", base_url="acp://claude-subscription",
    env_vars=(), process_command="claude", process_args=(),
    supports_health_check=False, supports_model_listing=False,
    supports_vision=False, supports_vision_tool_messages=False,
    fixed_temperature=OMIT_TEMPERATURE, default_max_tokens=1024,
    fallback_models=tuple(MODELS), model_aliases={},
    model_capabilities={name: {"context_length": spec["context_length"]} for name, spec in MODELS.items()},
)
register_provider(claude_subscription)
