import builtins

from workflows import full_setup


def _base_locs(base_locale="en-US", with_content=True):
    attrs = {
        "locale": base_locale,
        "description": "Desc" if with_content else "",
        "keywords": "a,b" if with_content else "",
        "promotionalText": "Promo" if with_content else "",
        "whatsNew": "Notes" if with_content else "",
    }
    return {"data": [{"id": "loc-en", "attributes": attrs}]}


def test_full_setup_early_return_branches(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = None
    assert full_setup.run(fake_cli) is True

    fake_ui.app_id = "app1"
    monkeypatch.setattr(full_setup, "select_platform_versions", lambda *_a, **_k: (None, None, None))
    assert full_setup.run(fake_cli) is True

    monkeypatch.setattr(full_setup, "select_platform_versions", lambda *_a, **_k: ({"IOS": {"id": "ver1"}}, None, None))
    fake_asc.set_response("get_app_store_version_localizations", {"data": []})
    assert full_setup.run(fake_cli) is True

    fake_asc.set_response("get_app_store_version_localizations", _base_locs())
    monkeypatch.setattr(full_setup, "detect_base_language", lambda _locs: None)
    assert full_setup.run(fake_cli) is True


def test_full_setup_selection_and_provider_guard_branches(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(full_setup, "select_platform_versions", lambda *_a, **_k: ({"IOS": {"id": "ver1"}}, None, None))

    fake_asc.set_response("get_app_store_version_localizations", _base_locs(with_content=False))
    monkeypatch.setattr(full_setup, "detect_base_language", lambda _locs: "en-US")
    assert full_setup.run(fake_cli) is True

    fake_asc.set_response("get_app_store_version_localizations", _base_locs(with_content=True))
    monkeypatch.setattr(full_setup, "choose_target_locales", lambda *_a, **_k: [])
    assert full_setup.run(fake_cli) is True

    monkeypatch.setattr(full_setup, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(full_setup, "pick_provider", lambda *_a, **_k: (None, None))
    assert full_setup.run(fake_cli) is True


def test_full_setup_empty_translation_warning_path(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(full_setup, "select_platform_versions", lambda *_a, **_k: ({"IOS": {"id": "ver1"}}, None, None))
    monkeypatch.setattr(full_setup, "detect_base_language", lambda _locs: "en-US")
    monkeypatch.setattr(full_setup, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(full_setup, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(full_setup.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(
        full_setup,
        "parallel_map_locales",
        lambda _targets, _task, **_kwargs: ({"fr-FR": {}}, {}),
    )
    fake_asc.set_response("get_app_store_version_localizations", _base_locs(with_content=True))

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert full_setup.run(fake_cli) is True
