"""Offline plugin/selection contracts, with an explicit native API test mode.

Default discovery uses peripheral provider-registration fakes, not installed
Hermes. --native-api is separately launched under an owned HERMES_HOME with the
installed pinned runtime; it does not call a provider or read live profiles.
"""
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/model-providers/claude-subscription'


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.registry = {}
        providers = types.ModuleType('providers')
        base = types.ModuleType('providers.base')
        class PeripheralProfile:
            def __init__(self, **fields):
                self.__dict__.update(fields)
        base.ProviderProfile = PeripheralProfile
        base.OMIT_TEMPERATURE = object()
        providers.register_provider = lambda p: self.registry.__setitem__(p.name, p)
        self.modules = patch.dict(sys.modules, {'providers': providers, 'providers.base': base})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        name = 'offline_subscription_registration'
        spec = importlib.util.spec_from_file_location(name, PLUGIN/'__init__.py', submodule_search_locations=[str(PLUGIN)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.addCleanup(lambda: [sys.modules.pop(n,None) for n in list(sys.modules) if n.startswith(name)])
        with patch('subprocess.Popen', side_effect=AssertionError('registration executed process')), \
                patch('socket.socket', side_effect=AssertionError('registration attempted network')):
            spec.loader.exec_module(module)
        self.profile = self.registry['claude-subscription']
        self.sentinel = base.OMIT_TEMPERATURE

    def test_unique_registration_does_not_hijack_ordinary_provider_names(self):
        self.assertEqual(set(self.registry), {'claude-subscription'})
        self.assertEqual(self.profile.aliases, ())
        self.assertEqual(self.profile.auth_type, 'external_process')
        self.assertEqual(self.profile.base_url, 'acp://claude-subscription')
        self.assertIs(self.profile.fixed_temperature, self.sentinel)

    def test_cli_command_comes_only_from_dedicated_setting(self):
        self.assertEqual(self.profile.process_command, '')
        self.assertEqual(self.profile.process_command_env_vars, ('HERMES_CLAUDE_SUBSCRIPTION_CLI',))

    def test_model_catalog_is_not_a_request_fallback_chain(self):
        self.assertEqual(self.profile.fallback_models, ('claude-opus-5-5',))
        self.assertEqual(self.profile.model_aliases, {})
        self.assertFalse(self.profile.supports_model_listing)
        self.assertFalse(self.profile.supports_health_check)
        self.assertFalse(self.profile.supports_vision)
        self.assertFalse(self.profile.supports_vision_tool_messages)

    def test_lazy_client_rejects_wrong_model_in_owned_path_not_factory(self):
        with patch('subprocess.Popen', side_effect=AssertionError('unexpected process')):
            c = self.profile.create_client(command='/nonexistent/synthetic-only')
            try:
                self.assertTrue(c.HERMES_SKIP_TRANSPORT_WRAP)
                self.assertTrue(c.HERMES_SKIP_ASYNC_WRAP)
                with self.assertRaisesRegex(RuntimeError, 'exact model'):
                    c.chat.completions.create(model='opus', messages=[{'role':'user','content':'unused'}])
            finally:
                c.close()

    def test_native_session_identity_roundtrips_through_extra_body(self):
        c = self.profile.create_client()
        self.addCleanup(c.close)
        kwargs = {'model':'claude-opus-5-5', 'messages':[{'role':'user','content':'unused'}],
                  'extra_body': self.profile.build_extra_body(session_id='worker-session')}
        model, scope, tools = c._validate(kwargs)
        self.assertEqual(scope[-1], 'worker-session')
        self.assertEqual(tools, [])
        c._model, c._scope, c._tools = model, scope, tools
        kwargs['extra_body'] = self.profile.build_extra_body(session_id='reviewer-session')
        with self.assertRaisesRegex(RuntimeError, 'session/worktree/profile'):
            c._validate(kwargs)


def native_api_checks():
    """Actual installed discovery/alias/transport APIs; no fake dependencies."""
    home = Path(os.environ['HERMES_HOME']).resolve()
    assert home.is_relative_to(ROOT/'private/provider')
    assert 'hermes_bootstrap' in sys.modules, 'use the inspected installed bootstrap launcher'
    from providers import get_provider_profile, list_providers, provider_source
    from hermes_cli.auth import PROVIDER_REGISTRY, resolve_provider
    from agent.transports.chat_completions import ChatCompletionsTransport
    subscription = get_provider_profile('claude-subscription')
    assert provider_source('claude-subscription') == 'user'
    assert sum(p.name == 'claude-subscription' for p in list_providers()) == 1
    assert subscription.auth_type == 'external_process'
    assert get_provider_profile('claude-code').name == 'anthropic'
    assert resolve_provider('openai-api') == 'openai-api'
    assert PROVIDER_REGISTRY['openai-api'].inference_base_url == 'https://api.openai.com/v1'
    assert resolve_provider('chatgpt') == 'openai-codex'
    zai = get_provider_profile('zai')
    assert zai.name == 'zai' and get_provider_profile('z.ai') is zai
    before = {n: (get_provider_profile(n).base_url, get_provider_profile(n).aliases,
                   dict(get_provider_profile(n).model_aliases)) for n in ('openai-codex', 'zai')}
    transport = ChatCompletionsTransport()
    assert transport.build_kwargs('gpt-6.1-sol', [{'role':'user','content':'offline'}],
        base_url=PROVIDER_REGISTRY['openai-api'].inference_base_url)['model'] == 'gpt-6.1-sol'
    for name, model in (('zai','glm-5.3'), ('claude-subscription','claude-opus-5-5')):
        p = get_provider_profile(name)
        kw = transport.build_kwargs(model, [{'role':'user','content':'offline selection only'}],
            provider_profile=p, base_url=p.base_url, provider_name=p.name, session_id='offline-native',
            max_tokens_param_fn=lambda n: {'max_tokens':n})
        assert kw['model'] == model and kw['messages'][0]['role'] == 'user'
        if name == 'claude-subscription':
            assert kw['max_tokens'] == 1024 and 'temperature' not in kw
            assert kw['extra_body']['subscription_session_id'] == 'offline-native'
    c = subscription.create_client(command='/nonexistent/synthetic-only')
    try:
        assert not c.is_closed()
        try:
            c.create(model='opus', messages=[{'role':'user','content':'unused'}])
        except RuntimeError:
            pass
        else:
            raise AssertionError('wrong Claude selection succeeded')
    finally:
        c.close()
    assert before == {n: (get_provider_profile(n).base_url, get_provider_profile(n).aliases,
                          dict(get_provider_profile(n).model_aliases)) for n in before}
    print('NATIVE API PASS: discovery, uniqueness, external-process metadata, transport, exact model rejection; ordinary OpenAI/Zai and claude-code alias unchanged; no inference')


if __name__ == '__main__':
    if sys.argv[1:] == ['--native-api']:
        native_api_checks()
    else:
        unittest.main()
