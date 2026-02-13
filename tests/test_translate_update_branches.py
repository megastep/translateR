import builtins

from workflows import translate, update_localizations


def _version():
    return {"IOS": {"id": "ver-ios", "attributes": {"versionString": "1.0"}}}


def _loc(loc_id, locale, **attrs):
    base = {
        "id": loc_id,
        "attributes": {
            "locale": locale,
            "description": attrs.get("description", "Desc"),
            "keywords": attrs.get("keywords", "a,b"),
            "promotionalText": attrs.get("promotionalText", "Promo"),
            "whatsNew": attrs.get("whatsNew", "Whats new"),
            "marketingUrl": attrs.get("marketingUrl", "https://m"),
            "supportUrl": attrs.get("supportUrl", "https://s"),
        },
    }
    return base


def test_translate_run_selection_and_early_exit_branches(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui._tui = False
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "x")
    assert translate.run(fake_cli) is True

    fake_ui.app_id = None
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1")
    assert translate.run(fake_cli) is True

    fake_ui.app_id = "app1"
    monkeypatch.setattr(translate, "select_platform_versions", lambda *_a, **_k: ({}, {}, {}))
    assert translate.run(fake_cli) is True

    monkeypatch.setattr(translate, "select_platform_versions", lambda *_a, **_k: (_version(), {}, {}))
    fake_asc.set_response("get_app_store_version_localizations", {"data": []})
    assert translate.run(fake_cli) is True

    fake_asc.set_response("get_app_store_version_localizations", {"data": [{"id": "x", "attributes": {"locale": None}}]})
    assert translate.run(fake_cli) is True


def test_translate_run_handles_unavailable_targets_or_provider(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui._tui = False
    fake_ui.app_id = "app1"
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1")
    monkeypatch.setattr(translate, "select_platform_versions", lambda *_a, **_k: (_version(), {}, {}))
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {"data": [_loc("loc-en", "en-US"), _loc("loc-fr", "fr-FR")]},
    )
    assert translate.run(fake_cli) is True

    fake_asc.set_response(
        "get_app_store_version_localizations",
        {"data": [_loc("loc-en", "en-US")]},
    )
    monkeypatch.setattr(translate, "choose_target_locales", lambda *_a, **_k: [])
    assert translate.run(fake_cli) is True

    monkeypatch.setattr(translate, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(translate, "pick_provider", lambda *_a, **_k: (None, None))
    assert translate.run(fake_cli) is True


def test_translate_run_include_app_info_path(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui._tui = False
    fake_ui.app_id = "app1"
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "2" if "Select" in (_a[0] if _a else "") else "")
    monkeypatch.setattr(translate, "select_platform_versions", lambda *_a, **_k: (_version(), {}, {}))
    fake_asc.set_response("get_app_store_version_localizations", {"data": [_loc("loc-en", "en-US")]})
    monkeypatch.setattr(translate, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(translate.time, "sleep", lambda *_a, **_k: None)
    assert translate.run(fake_cli) is True


def test_update_run_early_exit_branches(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = None
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert update_localizations.run(fake_cli) is True

    fake_ui.app_id = "app1"
    monkeypatch.setattr(update_localizations, "select_platform_versions", lambda *_a, **_k: ({}, {}, {}))
    assert update_localizations.run(fake_cli) is True

    monkeypatch.setattr(update_localizations, "select_platform_versions", lambda *_a, **_k: (_version(), {}, {}))
    fake_asc.set_response("get_app_store_version_localizations", {"data": []})
    assert update_localizations.run(fake_cli) is True

    fake_asc.set_response("get_app_store_version_localizations", {"data": [{"id": "x", "attributes": {"locale": None}}]})
    assert update_localizations.run(fake_cli) is True


def test_update_run_selection_provider_and_confirm_branches(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui._tui = False
    fake_ui.app_id = "app1"
    monkeypatch.setattr(update_localizations, "select_platform_versions", lambda *_a, **_k: (_version(), {}, {}))
    fake_asc.set_response("get_app_store_version_localizations", {"data": [_loc("loc-en", "en-US"), _loc("loc-fr", "fr-FR")]})

    answers = iter(["", "", ""])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert update_localizations.run(fake_cli) is True

    answers = iter(["fr-FR", "", ""])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert update_localizations.run(fake_cli) is True

    answers = iter(["fr-FR", "description", "n"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert update_localizations.run(fake_cli) is True


def test_update_run_handles_missing_fields_and_provider(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui._tui = False
    fake_ui.app_id = "app1"
    monkeypatch.setattr(update_localizations, "select_platform_versions", lambda *_a, **_k: (_version(), {}, {}))
    fake_asc.set_response("get_app_store_version_localizations", {"data": [_loc("loc-en", "en-US", description="", keywords="", promotionalText="", whatsNew="")]})
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert update_localizations.run(fake_cli) is True

    fake_asc.set_response("get_app_store_version_localizations", {"data": [_loc("loc-en", "en-US"), _loc("loc-fr", "fr-FR")]})
    monkeypatch.setattr(update_localizations, "pick_provider", lambda *_a, **_k: (None, None))
    answers = iter(["fr-FR", "description"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert update_localizations.run(fake_cli) is True
