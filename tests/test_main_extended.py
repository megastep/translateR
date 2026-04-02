import builtins
import types

import main


class DummyUI:
    def __init__(self, available=False):
        self._available = available

    def available(self):
        return self._available

    def select(self, *_args, **_kwargs):
        return None

    def text(self, *_args, **_kwargs):
        return None


class DummyConfig:
    def __init__(self):
        self.default_provider = "openai"
        self.default_model = {"openai": "gpt-5.2", "anthropic": "claude-sonnet-4-20250514", "google": "gemini-2.5-flash"}
        self.refine = ""

    def load_providers(self):
        return {
            "openai": {"default_model": "gpt-5.2"},
            "anthropic": {"default_model": "claude-sonnet-4-20250514"},
            "google": {"default_model": "gemini-2.5-flash"},
        }

    def get_ai_provider_key(self, provider):
        return {"openai": "ok-openai", "anthropic": "ok-anthropic", "google": "ok-google"}.get(provider)

    def get_default_model(self, provider):
        return self.default_model.get(provider)

    def get_default_ai_provider(self):
        return self.default_provider

    def set_default_ai_provider(self, provider):
        self.default_provider = provider

    def list_provider_models(self, provider):
        return ["m1", "m2"]

    def set_default_model(self, provider, model):
        self.default_model[provider] = model
        return True

    def get_prompt_refinement(self):
        return self.refine

    def set_prompt_refinement(self, phrase):
        self.refine = phrase or ""

    def get_openai_service_tier(self):
        return ""

    def set_openai_service_tier(self, _tier):
        return None


def test_setup_ai_providers_loads_all_providers(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.config = DummyConfig()

    class ProviderManager:
        def __init__(self):
            self.providers = {}

        def add_provider(self, name, provider):
            self.providers[name] = provider

        def list_providers(self):
            return list(self.providers.keys())

    monkeypatch.setattr(main, "AIProviderManager", ProviderManager)
    monkeypatch.setattr(main, "AnthropicProvider", lambda key, model: ("anthropic", key, model))
    monkeypatch.setattr(main, "OpenAIProvider", lambda key, model, **kwargs: ("openai", key, model, kwargs))
    monkeypatch.setattr(main, "GoogleGeminiProvider", lambda key, model: ("google", key, model))

    main.TranslateRCLI.setup_ai_providers(cli)

    assert set(cli.ai_manager.providers.keys()) == {"anthropic", "openai", "google"}


def test_configuration_mode_provider_branch_non_tui(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.ui = DummyUI(available=False)
    cli.config = DummyConfig()
    cli.asc_client = object()
    cli.ai_manager = types.SimpleNamespace(list_providers=lambda: ["openai", "anthropic"])

    answers = iter(["2", "1"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))

    assert main.TranslateRCLI.configuration_mode(cli) is True
    assert cli.config.get_default_ai_provider() == "openai"


def test_configuration_mode_refine_branch_non_tui(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.ui = DummyUI(available=False)
    cli.config = DummyConfig()
    cli.asc_client = object()
    cli.ai_manager = types.SimpleNamespace(list_providers=lambda: ["openai"])

    answers = iter(["5", "keep brands"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))

    assert main.TranslateRCLI.configuration_mode(cli) is True
    assert cli.config.get_prompt_refinement() == "keep brands"


def test_run_exits_when_setup_fails(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.show_logo = lambda: None
    cli.setup_app_store_client = lambda: False

    assert main.TranslateRCLI.run(cli) is None


def test_translate_app_info_updates_and_creates_localizations(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.session_seed = 7

    class ASC:
        def __init__(self):
            self.updated = []
            self.created = []

        def find_primary_app_info_id(self, _app_id):
            return "app-info-1"

        def get_app_info_localizations(self, _app_info_id):
            return {
                "data": [
                    {"id": "loc-en", "attributes": {"locale": "en-US"}},
                    {"id": "loc-fr", "attributes": {"locale": "fr-FR"}},
                ]
            }

        def get_app_info_localization(self, _loc_id):
            return {"data": {"attributes": {"name": "Base App", "subtitle": "Base Subtitle"}}}

        def update_app_info_localization(self, loc_id, **kwargs):
            self.updated.append((loc_id, kwargs))

        def create_app_info_localization(self, app_info_id, locale, **kwargs):
            self.created.append((app_info_id, locale, kwargs))

    class Provider:
        def translate(self, text, target_language, max_length=None, seed=None):
            return f"{target_language}-{text}"[:max_length]

    asc = ASC()
    cli.asc_client = asc
    monkeypatch.setattr(main.time, "sleep", lambda *_a, **_k: None)

    main.TranslateRCLI._translate_app_info(cli, "app1", ["fr-FR", "de-DE"], Provider())

    assert asc.updated and asc.updated[0][0] == "loc-fr"
    assert asc.created and asc.created[0][1] == "de-DE"


def test_translate_app_info_skips_when_no_app_info_id():
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.asc_client = types.SimpleNamespace(find_primary_app_info_id=lambda _app_id: None)

    assert main.TranslateRCLI._translate_app_info(cli, "app1", ["fr-FR"], object()) is None
