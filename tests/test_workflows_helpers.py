import builtins
import types

from workflows import helpers


class TinyUI:
    def __init__(self, tui=True):
        self._tui = tui
        self.confirm_value = None
        self.select_value = None
        self.checkbox_value = None

    def available(self):
        return self._tui

    def confirm(self, *_args, **_kwargs):
        return self.confirm_value

    def select(self, *_args, **_kwargs):
        return self.select_value

    def checkbox(self, *_args, **_kwargs):
        return self.checkbox_value


class TinyManager:
    def __init__(self, providers):
        self.providers = providers

    def list_providers(self):
        return list(self.providers.keys())

    def get_provider(self, name):
        return self.providers.get(name)


class TinyConfig:
    def __init__(self, default):
        self.default = default

    def get_default_ai_provider(self):
        return self.default


def test_pick_provider_single_provider_returns_it():
    provider = object()
    cli = types.SimpleNamespace(
        ui=TinyUI(tui=True),
        ai_manager=TinyManager({"openai": provider}),
        config=TinyConfig(default="openai"),
    )

    selected, key = helpers.pick_provider(cli)
    assert selected is provider
    assert key == "openai"


def test_pick_provider_uses_default_when_confirmed():
    p1 = object()
    p2 = object()
    ui = TinyUI(tui=True)
    ui.confirm_value = True
    cli = types.SimpleNamespace(
        ui=ui,
        ai_manager=TinyManager({"openai": p1, "anthropic": p2}),
        config=TinyConfig(default="anthropic"),
    )

    selected, key = helpers.pick_provider(cli)
    assert selected is p2
    assert key == "anthropic"


def test_choose_target_locales_tui_select_all():
    ui = TinyUI(tui=True)
    ui.checkbox_value = ["__all__"]

    out = helpers.choose_target_locales(
        ui,
        {"en-US": "English", "fr-FR": "French", "de-DE": "German"},
        base_locale="en-US",
    )

    assert out == ["fr-FR", "de-DE"]


def test_choose_target_locales_non_tui_uses_default_preferred(monkeypatch):
    ui = TinyUI(tui=False)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    out = helpers.choose_target_locales(
        ui,
        {"fr-FR": "French", "de-DE": "German"},
        base_locale="en-US",
        preferred_locales=["de-DE"],
    )

    assert out == ["de-DE"]


def test_select_platform_versions_handles_empty_versions():
    ui = TinyUI(tui=True)
    asc = types.SimpleNamespace(_request=lambda *_a, **_k: {"data": []})

    selected, latest, labels = helpers.select_platform_versions(ui, asc, "app1")
    assert selected is None
    assert latest is None
    assert labels is None


def test_get_app_locales_returns_empty_on_exception():
    asc = types.SimpleNamespace(get_latest_app_store_version=lambda _a: (_ for _ in ()).throw(RuntimeError("boom")))
    assert helpers.get_app_locales(asc, "app1") == set()


def test_pick_provider_non_tui_numeric_input(monkeypatch):
    p1 = object()
    p2 = object()
    ui = TinyUI(tui=False)
    cli = types.SimpleNamespace(
        ui=ui,
        ai_manager=TinyManager({"openai": p1, "anthropic": p2}),
        config=TinyConfig(default=""),
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "2")

    provider, key = helpers.pick_provider(cli, allow_cancel=True)
    assert provider is p2
    assert key == "anthropic"


def test_select_platform_versions_non_tui_all(monkeypatch):
    ui = TinyUI(tui=False)
    asc = types.SimpleNamespace(
        _request=lambda *_a, **_k: {
            "data": [
                {"id": "v1", "attributes": {"platform": "IOS", "versionString": "1.0", "appStoreState": "READY"}},
                {"id": "v2", "attributes": {"platform": "MAC_OS", "versionString": "1.0", "appStoreState": "READY"}},
            ]
        }
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    selected, latest, labels = helpers.select_platform_versions(ui, asc, "app1")
    assert set(selected.keys()) == {"IOS", "MAC_OS"}
    assert labels["IOS"] == "iOS"
