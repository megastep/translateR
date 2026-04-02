import builtins

from workflows import update_localizations


def _versions(single=True):
    if single:
        return {"IOS": {"id": "ver-ios", "attributes": {"versionString": "1.0"}}}
    return {
        "IOS": {"id": "ver-ios", "attributes": {"versionString": "1.0"}},
        "MAC_OS": {"id": "ver-mac", "attributes": {"versionString": "1.0"}},
    }


def _loc(loc_id, locale, **attrs):
    return {
        "id": loc_id,
        "attributes": {
            "locale": locale,
            "description": attrs.get("description", "Desc"),
            "keywords": attrs.get("keywords", "a,b,c"),
            "promotionalText": attrs.get("promotionalText", "Promo"),
            "whatsNew": attrs.get("whatsNew", "Whats new"),
        },
    }


def _setup_base(monkeypatch, fake_ui, fake_asc, locs, *, tui=False):
    fake_ui.app_id = "app1"
    fake_ui._tui = tui
    if tui:
        # Update workflow now asks for locale scope via ui.select first.
        fake_ui.select_values.append("existing")
    monkeypatch.setattr(update_localizations, "select_platform_versions", lambda *_a, **_k: (_versions(), {}, {}))
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: {"data": locs})


def test_update_run_base_data_missing_branch(fake_cli, fake_ui, fake_asc, monkeypatch):
    _setup_base(monkeypatch, fake_ui, fake_asc, [_loc("loc-fr", "fr-FR")], tui=False)
    monkeypatch.setattr(update_localizations, "detect_base_language", lambda *_a, **_k: "en-US")
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert update_localizations.run(fake_cli) is True


def test_update_run_tui_no_languages_and_no_fields_selected(fake_cli, fake_ui, fake_asc, monkeypatch):
    locs = [_loc("loc-en", "en-US"), _loc("loc-fr", "fr-FR")]
    _setup_base(monkeypatch, fake_ui, fake_asc, locs, tui=True)
    fake_ui.checkbox_values.extend([None])
    assert update_localizations.run(fake_cli) is True

    _setup_base(monkeypatch, fake_ui, fake_asc, locs, tui=True)
    fake_ui.checkbox_values.extend([["fr-FR"], None])
    assert update_localizations.run(fake_cli) is True


def test_update_run_non_tui_invalid_language_or_field_selection(fake_cli, fake_ui, fake_asc, monkeypatch):
    _setup_base(monkeypatch, fake_ui, fake_asc, [_loc("loc-en", "en-US"), _loc("loc-fr", "fr-FR")], tui=False)
    answers = iter(["n", "zz", ""])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert update_localizations.run(fake_cli) is True

    _setup_base(monkeypatch, fake_ui, fake_asc, [_loc("loc-en", "en-US"), _loc("loc-fr", "fr-FR")], tui=False)
    answers = iter(["n", "fr-FR", "bad"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert update_localizations.run(fake_cli) is True


def test_update_run_no_content_available_in_base(fake_cli, fake_ui, fake_asc, monkeypatch):
    _setup_base(
        monkeypatch,
        fake_ui,
        fake_asc,
        [_loc("loc-en", "en-US", description="", keywords="", promotionalText="", whatsNew=""), _loc("loc-fr", "fr-FR")],
        tui=False,
    )
    answers = iter(["n", "fr-FR"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert update_localizations.run(fake_cli) is True


def test_update_run_task_continue_keywords_truncate_and_missing_platform_locale(
    fake_cli, fake_ui, fake_asc, monkeypatch
):
    fake_ui.app_id = "app1"
    fake_ui._tui = False
    monkeypatch.setattr(update_localizations, "select_platform_versions", lambda *_a, **_k: (_versions(single=False), {}, {}))

    def locs_for_version(version_id):
        if version_id == "ver-ios":
            return {
                "data": [
                    _loc("loc-en-ios", "en-US", promotionalText=""),
                    _loc("loc-fr-ios", "fr-FR", promotionalText=""),
                ]
            }
        return {
            "data": [
                _loc("loc-en-mac", "en-US", promotionalText=""),
            ]
        }

    fake_asc.set_response("get_app_store_version_localizations", locs_for_version)
    monkeypatch.setattr(update_localizations.time, "sleep", lambda *_a, **_k: None)
    answers = iter(["fr-FR", "keywords,promotional_text", "y", ""])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert update_localizations.run(fake_cli) is True


def test_update_run_warns_on_empty_translations(fake_cli, fake_ui, fake_asc, monkeypatch):
    _setup_base(monkeypatch, fake_ui, fake_asc, [_loc("loc-en", "en-US"), _loc("loc-fr", "fr-FR")], tui=False)
    monkeypatch.setattr(
        update_localizations,
        "parallel_map_locales",
        lambda *_a, **_k: ({"fr-FR": {"description": "   "}}, {}),
    )
    answers = iter(["n", "fr-FR", "description", "y", ""])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert update_localizations.run(fake_cli) is True


def test_update_run_tui_selected_field_with_empty_source_hits_continue(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui._tui = True
    monkeypatch.setattr(update_localizations, "select_platform_versions", lambda *_a, **_k: (_versions(), {}, {}))
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {
            "data": [
                _loc("loc-en", "en-US", promotionalText=""),
                _loc("loc-fr", "fr-FR", promotionalText=""),
            ]
        },
    )
    fake_ui.checkbox_values.extend([["fr-FR"], ["promotional_text"]])
    fake_ui.confirm_values.append(True)
    monkeypatch.setattr(update_localizations.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert update_localizations.run(fake_cli) is True
