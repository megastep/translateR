import builtins

from workflows import app_info


def _loc(loc_id, locale):
    return {"id": loc_id, "attributes": {"locale": locale}}


def test_app_info_run_fallback_base_locale_path(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    fake_asc.set_response("find_primary_app_info_id", "app-info-1")
    fake_asc.set_response("get_app_info_localizations", {"data": [_loc("loc-fr", "fr-FR")]})
    fake_asc.set_response("get_app_info_localization", {"data": {"attributes": {"name": "Base FR", "subtitle": "Sous-titre"}}})
    monkeypatch.setattr(app_info, "choose_target_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert app_info.run(fake_cli) is True


def test_app_info_run_success_path_creates_localization(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    fake_asc.set_response("find_primary_app_info_id", "app-info-1")
    fake_asc.set_response("get_app_info_localizations", {"data": [_loc("loc-en", "en-US")]})
    fake_asc.set_response("get_app_info_localization", {"data": {"attributes": {"name": "Base", "subtitle": "Sub"}}})
    fake_asc.set_response("create_app_info_localization", {"data": {"id": "loc-fr"}})
    monkeypatch.setattr(app_info.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(app_info, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(app_info, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert app_info.run(fake_cli) is True


def test_app_info_run_empty_translation_warning_and_save_error(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    fake_asc.set_response("find_primary_app_info_id", "app-info-1")
    fake_asc.set_response("get_app_info_localizations", {"data": [_loc("loc-en", "en-US")]})
    fake_asc.set_response("get_app_info_localization", {"data": {"attributes": {"name": "Base", "subtitle": "Sub"}}})
    monkeypatch.setattr(app_info, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(app_info, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(
        app_info,
        "parallel_map_locales",
        lambda *_a, **_k: ({"fr-FR": {"name": " ", "subtitle": " "}}, {}),
    )
    fake_asc.set_response(
        "create_app_info_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("save failed")),
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert app_info.run(fake_cli) is True
