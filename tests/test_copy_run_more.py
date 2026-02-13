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


def test_select_platforms_no_versions_and_tui_selected_subset():
    ui = UI(tui=True)
    asc_empty = types.SimpleNamespace(_request=lambda *_a, **_k: {"data": []})
    assert copy.select_platforms(ui, asc_empty, "app1") is None

    ui.checkbox_value = ["IOS"]
    asc = types.SimpleNamespace(
        _request=lambda *_a, **_k: {
            "data": [
                {"id": "v1", "attributes": {"platform": "IOS", "versionString": "1.0", "appStoreState": "READY"}},
                {"id": "v2", "attributes": {"platform": "MAC_OS", "versionString": "1.0", "appStoreState": "READY"}},
            ]
        }
    )
    selected = copy.select_platforms(ui, asc, "app1")
    assert set(selected.keys()) == {"IOS"}


def test_pick_version_for_platform_tui_and_no_versions():
    ui = UI(tui=True)
    ui.select_value = {"id": "v2", "attributes": {"platform": "IOS", "versionString": "2.0"}}
    asc = types.SimpleNamespace(
        _request=lambda *_a, **_k: {
            "data": [
                {"id": "v1", "attributes": {"platform": "IOS", "versionString": "1.0", "appStoreState": "READY"}},
                {"id": "v2", "attributes": {"platform": "IOS", "versionString": "2.0", "appStoreState": "READY"}},
            ]
        }
    )
    out = copy.pick_version_for_platform(ui, asc, "app1", "IOS", "Pick")
    assert out["id"] == "v2"

    asc_none = types.SimpleNamespace(_request=lambda *_a, **_k: {"data": []})
    assert copy.pick_version_for_platform(ui, asc_none, "app1", "IOS", "Pick") is None


def test_copy_run_target_missing_and_copy_loop_error_branches(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(copy, "select_platforms", lambda *_a, **_k: {"IOS": {"id": "ver-target", "attributes": {"versionString": "2.0"}}})

    picks = iter(
        [
            {"id": "src", "attributes": {"versionString": "1.0"}},
            None,
        ]
    )
    monkeypatch.setattr(copy, "pick_version_for_platform", lambda *_a, **_k: next(picks))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert copy.run(fake_cli) is True

    picks = iter(
        [
            {"id": "src", "attributes": {"versionString": "1.0"}},
            {"id": "dst", "attributes": {"versionString": "2.0"}},
        ]
    )
    monkeypatch.setattr(copy, "pick_version_for_platform", lambda *_a, **_k: next(picks))
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {
            "data": [
                {"attributes": {"locale": "en-US"}},
                {"attributes": {"locale": "fr-FR"}},
            ]
        },
    )

    def fake_copy(_src, _dst, locale):
        if locale == "fr-FR":
            raise RuntimeError("copy failed")
        return True

    fake_asc.set_response("copy_localization_from_previous_version", fake_copy)
    monkeypatch.setattr(copy.time, "sleep", lambda *_a, **_k: None)

    calls = {"n": 0}

    def fake_progress(i, total, label):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("progress failed")
        return f"{i}/{total} {label}"

    monkeypatch.setattr(copy, "format_progress", fake_progress)

    real_write = copy.sys.stdout.write

    def flaky_write(s):
        if isinstance(s, str) and s.startswith("\r"):
            raise RuntimeError("no tty")
        return real_write(s)

    monkeypatch.setattr(copy.sys.stdout, "write", flaky_write)
    monkeypatch.setattr(copy.sys.stdout, "flush", lambda *_a, **_k: None)

    assert copy.run(fake_cli) is True
