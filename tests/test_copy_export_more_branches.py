import builtins
import types

from workflows import copy, export_localizations


def test_copy_run_warns_when_source_has_no_localizations(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(copy, "select_platforms", lambda *_a, **_k: {"IOS": {"id": "ver-target", "attributes": {"versionString": "2.0"}}})
    picks = iter(
        [
            {"id": "src", "attributes": {"versionString": "1.0"}},
            {"id": "dst", "attributes": {"versionString": "2.0"}},
        ]
    )
    monkeypatch.setattr(copy, "pick_version_for_platform", lambda *_a, **_k: next(picks))
    fake_asc.set_response("get_app_store_version_localizations", {"data": []})
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert copy.run(fake_cli) is True


def test_export_select_platform_non_tui_returns_latest_by_platform():
    class UI:
        def available(self):
            return False

    asc = types.SimpleNamespace(
        _request=lambda *_a, **_k: {
            "data": [
                {"id": "v1", "attributes": {"platform": "IOS", "versionString": "1.0", "appStoreState": "READY"}},
                {"id": "v2", "attributes": {"platform": "MAC_OS", "versionString": "1.0", "appStoreState": "READY"}},
            ]
        }
    )
    selected = export_localizations.select_platform(UI(), asc, "app1")
    assert set(selected.keys()) == {"IOS", "MAC_OS"}


def test_export_run_no_platform_selected_branch(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(export_localizations, "select_platform", lambda *_a, **_k: {})
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert export_localizations.run(fake_cli) is True


def test_export_run_cancelled_when_no_app_selected(fake_cli, fake_ui, monkeypatch):
    fake_ui.app_id = None
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert export_localizations.run(fake_cli) is True
