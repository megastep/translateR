import builtins

from workflows import full_setup, translate, update_localizations


def _versions_response():
    return {
        "data": [
            {
                "id": "ver-ios",
                "attributes": {
                    "platform": "IOS",
                    "versionString": "1.0",
                    "appStoreState": "PREPARE_FOR_SUBMISSION",
                },
            }
        ]
    }


def test_translate_run_creates_missing_locale(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["1"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])

    localizations = {"data": [localization_payload("en-US")]}
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: localizations)
    fake_asc.set_response("create_app_store_version_localization", {"data": {"id": "new-loc"}})

    monkeypatch.setattr(translate.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert translate.run(fake_cli) is True
    assert any(call[0] == "create_app_store_version_localization" for call in fake_asc.calls)


def test_update_run_updates_selected_locale(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"], ["whats_new"]])
    fake_ui.confirm_values.append(True)

    localizations = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew="Source"),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew="Old"),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: localizations)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "loc-fr"}})

    monkeypatch.setattr(update_localizations.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert update_localizations.run(fake_cli) is True
    update_calls = [c for c in fake_asc.calls if c[0] == "update_app_store_version_localization"]
    assert update_calls
    assert any(call[2].get("localization_id") == "loc-fr" for call in update_calls)


def test_full_setup_run_creates_translations_for_missing_locales(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])

    localizations = {"data": [localization_payload("en-US")]}
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: localizations)
    fake_asc.set_response("create_app_store_version_localization", {"data": {"id": "new-loc"}})

    monkeypatch.setattr(full_setup.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert full_setup.run(fake_cli) is True
    assert any(call[0] == "create_app_store_version_localization" for call in fake_asc.calls)
