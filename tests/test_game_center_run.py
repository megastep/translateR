import builtins

from workflows import game_center_localizations as gcl


def test_game_center_run_achievement_happy_path(fake_cli, fake_asc, fake_ui, monkeypatch):
    fake_ui.app_id = "app1"

    monkeypatch.setattr(gcl, "_choose_resource_types", lambda _ui: ["achievement"])
    monkeypatch.setattr(gcl, "_select_items", lambda _ui, items, _kind: items)
    monkeypatch.setattr(gcl, "_select_base_locale", lambda _ui, _locales, _recommended: "en-US")
    monkeypatch.setattr(gcl, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])

    fake_asc.set_response("get_game_center_detail", {"data": {"id": "detail1"}})
    fake_asc.set_response("get_game_center_group", {"data": None})
    fake_asc.set_response(
        "get_game_center_achievements",
        {"data": [{"id": "ach1", "attributes": {"referenceName": "Ach One"}}]},
    )
    fake_asc.set_response("get_latest_app_store_version", "ver-ios")
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {"data": [{"id": "loc-en", "attributes": {"locale": "en-US"}}]},
    )
    fake_asc.set_response(
        "get_game_center_achievement_localizations",
        {
            "data": [
                {
                    "id": "achloc-en",
                    "attributes": {
                        "locale": "en-US",
                        "name": "Achievement",
                        "beforeEarnedDescription": "Do it",
                        "afterEarnedDescription": "Done",
                    },
                }
            ]
        },
    )
    fake_asc.set_response("create_game_center_achievement_localization", {"data": {"id": "achloc-fr"}})

    monkeypatch.setattr(gcl.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert gcl.run(fake_cli) is True
    assert any(call[0] == "create_game_center_achievement_localization" for call in fake_asc.calls)
