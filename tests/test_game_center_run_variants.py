import builtins

from workflows import game_center_localizations as gcl


def _base_monkeypatches(monkeypatch):
    monkeypatch.setattr(gcl, "_select_items", lambda _ui, items, _kind: items)
    monkeypatch.setattr(gcl, "_select_base_locale", lambda _ui, _locales, _recommended: "en-US")
    monkeypatch.setattr(gcl, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(gcl.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")


def test_game_center_run_leaderboard_happy_path(fake_cli, fake_asc, fake_ui, monkeypatch):
    fake_ui.app_id = "app1"
    _base_monkeypatches(monkeypatch)
    monkeypatch.setattr(gcl, "_choose_resource_types", lambda _ui: ["leaderboard"])

    fake_asc.set_response("get_game_center_detail", {"data": {"id": "detail1"}})
    fake_asc.set_response("get_game_center_group", {"data": None})
    fake_asc.set_response(
        "get_game_center_leaderboards",
        {"data": [{"id": "lb1", "attributes": {"referenceName": "LB"}}]},
    )
    fake_asc.set_response("get_latest_app_store_version", "ver-ios")
    fake_asc.set_response("get_app_store_version_localizations", {"data": [{"id": "loc-en", "attributes": {"locale": "en-US"}}]})
    fake_asc.set_response(
        "get_game_center_leaderboard_localizations",
        {"data": [{"id": "lbloc-en", "attributes": {"locale": "en-US", "name": "Name", "description": "Desc"}}]},
    )
    fake_asc.set_response("create_game_center_leaderboard_localization", {"data": {"id": "lbloc-fr"}})

    assert gcl.run(fake_cli) is True
    assert any(call[0] == "create_game_center_leaderboard_localization" for call in fake_asc.calls)


def test_game_center_run_activity_happy_path(fake_cli, fake_asc, fake_ui, monkeypatch):
    fake_ui.app_id = "app1"
    _base_monkeypatches(monkeypatch)
    monkeypatch.setattr(gcl, "_choose_resource_types", lambda _ui: ["activity"])

    fake_asc.set_response("get_game_center_detail", {"data": {"id": "detail1"}})
    fake_asc.set_response("get_game_center_group", {"data": None})
    fake_asc.set_response(
        "get_game_center_activities",
        {"data": [{"id": "act1", "attributes": {"referenceName": "Activity"}}]},
    )
    fake_asc.set_response("get_latest_app_store_version", "ver-ios")
    fake_asc.set_response("get_app_store_version_localizations", {"data": [{"id": "loc-en", "attributes": {"locale": "en-US"}}]})
    fake_asc.set_response(
        "get_game_center_activity_versions",
        {"data": [{"id": "ver1", "attributes": {"version": "1.0"}}]},
    )
    fake_asc.set_response(
        "get_game_center_activity_version_localizations",
        {"data": [{"id": "actloc-en", "attributes": {"locale": "en-US", "name": "Name", "description": "Desc"}}]},
    )
    fake_asc.set_response("create_game_center_activity_localization", {"data": {"id": "actloc-fr"}})

    assert gcl.run(fake_cli) is True
    assert any(call[0] == "create_game_center_activity_localization" for call in fake_asc.calls)
