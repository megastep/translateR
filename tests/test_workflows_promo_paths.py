import builtins

from workflows import promo


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


def test_promo_run_updates_base_and_selected_locale(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.append(True)

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", promotionalText="Base promo"),
            localization_payload("fr-FR", loc_id="loc-fr", promotionalText="Ancien"),
        ]
    }
    verify_payload = {
        "data": {
            "attributes": {
                "promotionalText": "translated-French-Base promo"
            }
        }
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response("get_app_store_version_localization", verify_payload)

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert promo.run(fake_cli) is True
    update_calls = [c for c in fake_asc.calls if c[0] == "update_app_store_version_localization"]
    assert len(update_calls) >= 2


def test_promo_run_reenter_source_then_apply(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "reenter", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.append(True)
    fake_ui.multiline_values.append("New promo source")

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", promotionalText="Base promo"),
            localization_payload("fr-FR", loc_id="loc-fr", promotionalText="Ancien"),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response(
        "get_app_store_version_localization",
        {"data": {"attributes": {"promotionalText": "translated-French-New promo source"}}},
    )

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert promo.run(fake_cli) is True
    assert fake_cli.ai_manager.get_provider("fake").calls[-1]["text"] == "New promo source"


def test_promo_run_non_tui_apply_path(fake_cli, fake_asc, localization_payload, monkeypatch):
    class NonTUI:
        def available(self):
            return False

        def prompt_app_id(self, _asc):
            return "app1"

        def confirm(self, *_args, **_kwargs):
            return None

        def prompt_multiline(self, *_args, **_kwargs):
            return "not-used"

    fake_cli.ui = NonTUI()
    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", promotionalText="Base promo"),
            localization_payload("fr-FR", loc_id="loc-fr", promotionalText=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response("get_app_store_version_localization", {"data": {"attributes": {"promotionalText": "translated-French-Base promo"}}})

    answers = iter(["", "", "", "", "", ""])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))

    assert promo.run(fake_cli) is True


def test_promo_run_edit_selected_locale_then_apply(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "edit"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"], ["fr-FR"]])
    fake_ui.confirm_values.append(True)
    fake_ui.multiline_values.append("Edited promo")

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", promotionalText="Base promo"),
            localization_payload("fr-FR", loc_id="loc-fr", promotionalText=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response(
        "get_app_store_version_localization",
        {"data": {"attributes": {"promotionalText": "Edited promo"}}},
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert promo.run(fake_cli) is True
    updates = [c for c in fake_asc.calls if c[0] == "update_app_store_version_localization"]
    assert any(call[2].get("promotional_text") == "Edited promo" for call in updates)


def test_promo_run_cancelled_at_next_step(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "cancel"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", promotionalText="Base promo"),
            localization_payload("fr-FR", loc_id="loc-fr", promotionalText=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert promo.run(fake_cli) is True


def test_promo_run_declines_apply_confirmation(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.append(False)
    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", promotionalText="Base promo"),
            localization_payload("fr-FR", loc_id="loc-fr", promotionalText=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert promo.run(fake_cli) is True
    assert not any(call[0] == "update_app_store_version_localization" for call in fake_asc.calls)


def test_promo_run_returns_when_base_language_not_detected(fake_cli, fake_asc, fake_ui, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.checkbox_values.extend([["IOS"]])
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response(
        "get_app_store_version_localizations",
        lambda *_a, **_k: {"data": [{"id": "loc-1", "attributes": {"locale": None, "promotionalText": ""}}]},
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert promo.run(fake_cli) is True
