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


def test_pick_provider_no_providers_returns_none():
    cli = types.SimpleNamespace(
        ui=TinyUI(tui=True),
        ai_manager=TinyManager({}),
        config=TinyConfig(default=""),
    )
    provider, key = helpers.pick_provider(cli)
    assert provider is None
    assert key is None


def test_pick_provider_tui_select_and_manual_cancel_paths(monkeypatch):
    p1 = object()
    p2 = object()

    ui = TinyUI(tui=True)
    ui.confirm_value = False
    ui.select_value = "openai"
    cli = types.SimpleNamespace(
        ui=ui,
        ai_manager=TinyManager({"openai": p1, "anthropic": p2}),
        config=TinyConfig(default="anthropic"),
    )
    provider, key = helpers.pick_provider(cli, allow_cancel=True)
    assert provider is p1
    assert key == "openai"

    ui = TinyUI(tui=True)
    ui.confirm_value = False
    ui.select_value = None
    cli = types.SimpleNamespace(
        ui=ui,
        ai_manager=TinyManager({"openai": p1, "anthropic": p2}),
        config=TinyConfig(default="anthropic"),
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "back")
    provider, key = helpers.pick_provider(cli, allow_cancel=True)
    assert provider is None
    assert key is None


def test_pick_provider_fallback_input_paths(monkeypatch):
    p1 = object()
    p2 = object()
    ui = TinyUI(tui=False)
    ui.confirm_value = None
    cli = types.SimpleNamespace(
        ui=ui,
        ai_manager=TinyManager({"openai": p1, "anthropic": p2}),
        config=TinyConfig(default="anthropic"),
    )

    answers = iter(["y"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    provider, key = helpers.pick_provider(cli, allow_cancel=False)
    assert provider is p2
    assert key == "anthropic"

    ui = TinyUI(tui=False)
    ui.confirm_value = False
    cli = types.SimpleNamespace(
        ui=ui,
        ai_manager=TinyManager({"openai": p1, "anthropic": p2}),
        config=TinyConfig(default=""),
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "bad")
    provider, key = helpers.pick_provider(cli, allow_cancel=False)
    assert provider is None
    assert key is None

    ui = TinyUI(tui=False)
    ui.confirm_value = False
    cli = types.SimpleNamespace(
        ui=ui,
        ai_manager=TinyManager({"openai": p1, "anthropic": p2}),
        config=TinyConfig(default=""),
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    provider, key = helpers.pick_provider(cli, allow_cancel=False)
    assert provider is None
    assert key is None


def test_choose_target_locales_paths(monkeypatch):
    assert helpers.choose_target_locales(TinyUI(tui=False), {}, "en-US") == []

    ui = TinyUI(tui=True)
    ui.checkbox_value = ["__manual__"]
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "fr-FR, xx-XX")
    out = helpers.choose_target_locales(ui, {"fr-FR": "French", "de-DE": "German"}, "en-US")
    assert out == ["fr-FR"]

    ui = TinyUI(tui=True)
    ui.checkbox_value = ["de-DE", "not-present"]
    out = helpers.choose_target_locales(ui, {"fr-FR": "French", "de-DE": "German"}, "en-US")
    assert out == ["de-DE"]

    ui = TinyUI(tui=False)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "all")
    out = helpers.choose_target_locales(ui, {"fr-FR": "French", "de-DE": "German"}, "en-US")
    assert out == ["fr-FR", "de-DE"]

    ui = TinyUI(tui=False)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "xx-XX")
    out = helpers.choose_target_locales(ui, {"fr-FR": "French", "de-DE": "German"}, "en-US", preferred_locales=["de-DE"])
    assert out == ["de-DE"]


def test_select_platform_versions_more_paths(monkeypatch):
    versions = {
        "data": [
            {"id": "v1", "attributes": {"platform": "IOS", "versionString": "1.0", "appStoreState": "READY"}},
            {"id": "v2", "attributes": {"platform": "TV_OS", "versionString": "2.0", "appStoreState": "PREPARE"}},
        ]
    }
    asc = types.SimpleNamespace(_request=lambda *_a, **_k: versions)

    ui = TinyUI(tui=True)
    ui.checkbox_value = None
    selected, latest, labels = helpers.select_platform_versions(ui, asc, "app1")
    assert selected is None
    assert latest is None
    assert labels is None

    ui = TinyUI(tui=True)
    ui.checkbox_value = ["IOS"]
    selected, latest, labels = helpers.select_platform_versions(ui, asc, "app1")
    assert set(selected.keys()) == {"IOS"}
    assert labels["TV_OS"] == "tvOS"

    ui = TinyUI(tui=False)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "b")
    selected, latest, labels = helpers.select_platform_versions(ui, asc, "app1")
    assert selected is None
    assert latest is None
    assert labels is None

    ui = TinyUI(tui=False)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "a,b")
    selected, latest, labels = helpers.select_platform_versions(ui, asc, "app1")
    assert selected is None
    assert latest is None
    assert labels is None

    ui = TinyUI(tui=False)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1,99")
    selected, latest, labels = helpers.select_platform_versions(ui, asc, "app1")
    assert set(selected.keys()) == {"IOS"}


def test_get_app_locales_success_and_no_latest():
    asc = types.SimpleNamespace(
        get_latest_app_store_version=lambda _a: "ver1",
        get_app_store_version_localizations=lambda _v: {"data": [{"attributes": {"locale": "en-US"}}, {"attributes": {"locale": "fr-FR"}}]},
    )
    assert helpers.get_app_locales(asc, "app1") == {"en-US", "fr-FR"}

    asc_none = types.SimpleNamespace(
        get_latest_app_store_version=lambda _a: None,
        get_app_store_version_localizations=lambda _v: {"data": [{"attributes": {"locale": "en-US"}}]},
    )
    assert helpers.get_app_locales(asc_none, "app1") == set()
