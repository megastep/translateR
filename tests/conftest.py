import builtins
import sys
import types
from collections import deque
from pathlib import Path

import pytest
import requests


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeUI:
    def __init__(self, tui=False):
        self._tui = tui
        self.select_values = deque()
        self.checkbox_values = deque()
        self.confirm_values = deque()
        self.text_values = deque()
        self.editor_values = deque()
        self.multiline_values = deque()
        self.app_id = None

    def available(self):
        return self._tui

    def select(self, *_args, **_kwargs):
        return self.select_values.popleft() if self.select_values else None

    def checkbox(self, *_args, **_kwargs):
        return self.checkbox_values.popleft() if self.checkbox_values else None

    def confirm(self, *_args, **_kwargs):
        return self.confirm_values.popleft() if self.confirm_values else None

    def text(self, *_args, **_kwargs):
        return self.text_values.popleft() if self.text_values else None

    def editor(self, *_args, **_kwargs):
        return self.editor_values.popleft() if self.editor_values else None

    def prompt_multiline(self, *_args, **_kwargs):
        return self.multiline_values.popleft() if self.multiline_values else None

    def prompt_app_id(self, *_args, **_kwargs):
        return self.app_id


class FakeProvider:
    def __init__(self, name="Fake Provider", model="fake-model", prefix="translated"):
        self._name = name
        self.model = model
        self.prefix = prefix
        self.calls = []

    def get_name(self):
        return self._name

    def translate(self, text, target_language, max_length=None, is_keywords=False, seed=None, refinement=None):
        self.calls.append(
            {
                "text": text,
                "target_language": target_language,
                "max_length": max_length,
                "is_keywords": is_keywords,
                "seed": seed,
                "refinement": refinement,
            }
        )
        out = f"{self.prefix}-{target_language}-{text}".strip()
        if max_length:
            return out[:max_length]
        return out


class FakeProviderManager:
    def __init__(self, providers=None):
        self.providers = providers or {}

    def add_provider(self, name, provider):
        self.providers[name] = provider

    def get_provider(self, name):
        return self.providers.get(name)

    def list_providers(self):
        return list(self.providers.keys())


class FakeConfig:
    def __init__(self, default_provider="fake", prompt_refinement="", providers=None):
        self._default_provider = default_provider
        self._prompt_refinement = prompt_refinement
        self._providers = providers or {
            "anthropic": {"models": ["claude-sonnet-4-20250514"], "default_model": "claude-sonnet-4-20250514"},
            "openai": {"models": ["gpt-5.2"], "default_model": "gpt-5.2"},
            "google": {"models": ["gemini-2.5-flash"], "default_model": "gemini-2.5-flash"},
        }

    def get_default_ai_provider(self):
        return self._default_provider

    def set_default_ai_provider(self, provider):
        self._default_provider = provider

    def get_prompt_refinement(self):
        return self._prompt_refinement

    def set_prompt_refinement(self, phrase):
        self._prompt_refinement = phrase

    def load_providers(self):
        payload = dict(self._providers)
        payload["default_provider"] = self._default_provider
        payload["prompt_refinement"] = self._prompt_refinement
        return payload

    def list_provider_models(self, provider_name):
        provider = self._providers.get(provider_name, {})
        return provider.get("models", [])

    def get_default_model(self, provider_name):
        provider = self._providers.get(provider_name, {})
        return provider.get("default_model")

    def set_default_model(self, provider_name, model):
        provider = self._providers.get(provider_name)
        if not provider:
            return False
        if provider.get("models") and model not in provider["models"]:
            return False
        provider["default_model"] = model
        return True


class MainTestConfig(FakeConfig):
    def __init__(self):
        super().__init__(default_provider="openai")
        self.models = self._providers
        self._keys = {"openai": "ok", "anthropic": "ok", "google": "ok"}
        self._api_keys = {
            "app_store_connect": {"key_id": "", "issuer_id": "", "private_key_path": ""},
            "ai_providers": {"anthropic": "", "openai": "", "google": ""},
        }
        self.saved = None

    def get_ai_provider_key(self, provider):
        return self._keys.get(provider)

    def load_api_keys(self):
        return dict(self._api_keys)

    def save_api_keys(self, payload):
        self.saved = payload


class MainTestUI(FakeUI):
    def __init__(self, available=False, select_values=None, text_values=None):
        super().__init__(tui=available)
        self.select_values.extend(select_values or [])
        self.text_values.extend(text_values or [])


class FakeASC:
    def __init__(self):
        self.responses = {}
        self.calls = []

    def set_response(self, method_name, value):
        self.responses[method_name] = value

    def _record(self, method_name, *args, **kwargs):
        self.calls.append((method_name, args, kwargs))
        value = self.responses.get(method_name)
        if callable(value):
            return value(*args, **kwargs)
        if value is None:
            return {}
        return value

    def _request(self, *args, **kwargs):
        return self._record("_request", *args, **kwargs)

    def get_apps(self, *args, **kwargs):
        return self._record("get_apps", *args, **kwargs)

    def get_apps_page(self, *args, **kwargs):
        return self._record("get_apps_page", *args, **kwargs)

    def get_latest_app_store_version(self, *args, **kwargs):
        return self._record("get_latest_app_store_version", *args, **kwargs)

    def get_app_store_version_localizations(self, *args, **kwargs):
        return self._record("get_app_store_version_localizations", *args, **kwargs)

    def get_app_store_version_localization(self, *args, **kwargs):
        return self._record("get_app_store_version_localization", *args, **kwargs)

    def update_app_store_version_localization(self, *args, **kwargs):
        return self._record("update_app_store_version_localization", *args, **kwargs)

    def create_app_store_version_localization(self, *args, **kwargs):
        return self._record("create_app_store_version_localization", *args, **kwargs)

    def copy_localization_from_previous_version(self, *args, **kwargs):
        return self._record("copy_localization_from_previous_version", *args, **kwargs)

    def find_primary_app_info_id(self, *args, **kwargs):
        return self._record("find_primary_app_info_id", *args, **kwargs)

    def get_app_info_localizations(self, *args, **kwargs):
        return self._record("get_app_info_localizations", *args, **kwargs)

    def get_app_info_localization(self, *args, **kwargs):
        return self._record("get_app_info_localization", *args, **kwargs)

    def create_app_info_localization(self, *args, **kwargs):
        return self._record("create_app_info_localization", *args, **kwargs)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name in self.responses:
            return lambda *args, **kwargs: self._record(name, *args, **kwargs)
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")


class DummyResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text="", json_exc=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = text
        self._json_exc = json_exc

    def json(self):
        if self._json_exc:
            raise self._json_exc
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError("http", response=self)


def build_http_error(status=409, payload=None, text="", headers=None, json_exc=None):
    err = requests.exceptions.HTTPError("http")
    err.response = DummyResponse(
        status_code=status,
        payload=payload or {},
        text=text,
        headers=headers,
        json_exc=json_exc,
    )
    return err


class InquirerExec:
    def __init__(self, value=None, fail=False):
        self.value = value
        self.fail = fail

    def execute(self):
        if self.fail:
            raise RuntimeError("execute failed")
        return self.value


class InquirerStub:
    def __init__(self, values=None, fail=False):
        self.values = deque(values or [])
        self.fail = fail

    def _next(self):
        if self.fail:
            return InquirerExec(fail=True)
        return InquirerExec(self.values.popleft() if self.values else None)

    def select(self, **_kwargs):
        return self._next()

    def checkbox(self, **_kwargs):
        return self._next()

    def confirm(self, **_kwargs):
        return self._next()

    def text(self, **_kwargs):
        return self._next()

    def editor(self, **_kwargs):
        return self._next()

    def fuzzy(self, **_kwargs):
        return self._next()


def patch_inquirer_import(monkeypatch, values=None, fail=False):
    fake_module = types.SimpleNamespace(inquirer=InquirerStub(values=values, fail=fail))
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "InquirerPy":
            return fake_module
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


@pytest.fixture
def fake_provider():
    return FakeProvider()


@pytest.fixture
def fake_ui():
    return FakeUI(tui=True)


@pytest.fixture
def fake_asc():
    return FakeASC()


@pytest.fixture
def fake_cli(fake_ui, fake_provider, fake_asc):
    manager = FakeProviderManager({"fake": fake_provider})
    return types.SimpleNamespace(
        ui=fake_ui,
        asc_client=fake_asc,
        ai_manager=manager,
        config=FakeConfig(default_provider="fake", prompt_refinement="keep tone concise"),
        session_seed=123,
    )


@pytest.fixture
def localization_payload():
    def _mk(locale, loc_id=None, **attrs):
        out = {
            "id": loc_id or f"loc-{locale}",
            "attributes": {
                "locale": locale,
                "description": attrs.get("description", "Base description"),
                "keywords": attrs.get("keywords", "alpha,beta"),
                "promotionalText": attrs.get("promotionalText", "Promo text"),
                "whatsNew": attrs.get("whatsNew", "Bug fixes and improvements"),
                "name": attrs.get("name", "App Name"),
                "subtitle": attrs.get("subtitle", "Best app"),
            },
        }
        return out

    return _mk
