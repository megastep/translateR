import builtins
import types

from workflows import copy


class UI:
    def __init__(self, tui):
        self._tui = tui
        self.checkbox_value = None
        self.select_value = None

    def available(self):
        return self._tui

    def checkbox(self, *_args, **_kwargs):
        return self.checkbox_value

    def select(self, *_args, **_kwargs):
        return self.select_value


def test_select_platforms_non_tui_returns_all():
    ui = UI(tui=False)
    asc = types.SimpleNamespace(
        _request=lambda *_a, **_k: {
            "data": [
                {"id": "v1", "attributes": {"platform": "IOS", "versionString": "1.0", "appStoreState": "READY"}},
                {"id": "v2", "attributes": {"platform": "MAC_OS", "versionString": "1.0", "appStoreState": "READY"}},
            ]
        }
    )

    selected = copy.select_platforms(ui, asc, "app1")
    assert set(selected.keys()) == {"IOS", "MAC_OS"}


def test_select_platforms_tui_cancel_returns_none():
    ui = UI(tui=True)
    ui.checkbox_value = []
    asc = types.SimpleNamespace(
        _request=lambda *_a, **_k: {"data": [{"id": "v1", "attributes": {"platform": "IOS"}}]}
    )

    assert copy.select_platforms(ui, asc, "app1") is None


def test_pick_version_for_platform_non_tui_valid_and_invalid(monkeypatch):
    ui = UI(tui=False)
    asc = types.SimpleNamespace(
        _request=lambda *_a, **_k: {
            "data": [
                {"id": "v1", "attributes": {"platform": "IOS", "versionString": "1.0", "appStoreState": "READY"}},
                {"id": "v2", "attributes": {"platform": "IOS", "versionString": "2.0", "appStoreState": "READY"}},
            ]
        }
    )

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "2")
    out = copy.pick_version_for_platform(ui, asc, "app1", "IOS", "Select")
    assert out["id"] == "v2"

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "bad")
    assert copy.pick_version_for_platform(ui, asc, "app1", "IOS", "Select") is None
