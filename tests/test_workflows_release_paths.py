import builtins

from release_presets import ReleaseNotePreset
from workflows import release


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


def test_release_run_translates_and_applies(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.append(True)

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response(
        "get_app_store_version_localization",
        {"data": {"attributes": {"whatsNew": "translated-French-Base notes"}}},
    )

    monkeypatch.setattr(release, "list_presets", lambda: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True
    assert any(call[0] == "update_app_store_version_localization" for call in fake_asc.calls)


def test_release_run_reenter_source_then_apply(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "reenter", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.append(True)
    fake_ui.multiline_values.append("New source notes")

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response(
        "get_app_store_version_localization",
        {"data": {"attributes": {"whatsNew": "translated-French-New source notes"}}},
    )

    monkeypatch.setattr(release, "list_presets", lambda: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True
    assert fake_cli.ai_manager.get_provider("fake").calls[-1]["text"] == "New source notes"


def test_release_run_uses_selected_preset_when_base_empty(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["preset1", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.append(True)

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew=""),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response(
        "get_app_store_version_localization",
        {"data": {"attributes": {"whatsNew": "Bonjour preset"}}},
    )

    preset = ReleaseNotePreset(
        preset_id="preset1",
        name="Preset One",
        translations={"en-US": "Base preset", "fr-FR": "Bonjour preset"},
        path=None,
        built_in=True,
    )
    monkeypatch.setattr(release, "list_presets", lambda: [preset])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True
    updates = [c for c in fake_asc.calls if c[0] == "update_app_store_version_localization"]
    assert updates


def test_release_run_preset_also_updates_base_locale_when_base_already_has_notes(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["preset", "preset1", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.append(True)

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew="Old base notes"),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    preset = ReleaseNotePreset(
        preset_id="preset1",
        name="Preset One",
        translations={"en-US": "Preset base", "fr-FR": "Bonjour preset"},
        path=None,
        built_in=True,
    )

    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response(
        "get_app_store_version_localization",
        {"data": {"attributes": {"whatsNew": "Bonjour preset"}}},
    )

    monkeypatch.setattr(release, "list_presets", lambda: [preset])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True
    update_calls = [c for c in fake_asc.calls if c[0] == "update_app_store_version_localization"]
    assert any(
        call[2].get("localization_id") == "loc-en" and call[2].get("whats_new") == "Preset base"
        for call in update_calls
    )


def test_release_run_preset_can_apply_when_only_base_locale_needs_change(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["preset", "preset1", "apply"])
    fake_ui.checkbox_values.extend([["IOS"]])
    fake_ui.confirm_values.extend([False, True])

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew="Old base notes"),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew="Existing French notes"),
        ]
    }
    preset = ReleaseNotePreset(
        preset_id="preset1",
        name="Preset One",
        translations={"en-US": "Preset base", "fr-FR": "Bonjour preset"},
        path=None,
        built_in=True,
    )

    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    monkeypatch.setattr(release, "list_presets", lambda: [preset])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True
    update_calls = [c for c in fake_asc.calls if c[0] == "update_app_store_version_localization"]
    assert any(
        call[2].get("localization_id") == "loc-en" and call[2].get("whats_new") == "Preset base"
        for call in update_calls
    )


def test_release_run_preset_preview_includes_base_locale(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch, capsys):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["preset", "preset1", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.append(True)

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew="Old base notes"),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    preset = ReleaseNotePreset(
        preset_id="preset1",
        name="Preset One",
        translations={"en-US": "Preset base", "fr-FR": "Bonjour preset"},
        path=None,
        built_in=True,
    )

    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response(
        "get_app_store_version_localization",
        {"data": {"attributes": {"whatsNew": "Bonjour preset"}}},
    )

    monkeypatch.setattr(release, "list_presets", lambda: [preset])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True
    out = capsys.readouterr().out
    assert "English (U.S.) [en-US]" in out
    assert "Preset base" in out


def test_release_run_custom_source_when_no_preset(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.append("apply")
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.append(True)
    fake_ui.multiline_values.append("Custom release notes")

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew=""),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response(
        "get_app_store_version_localization",
        {"data": {"attributes": {"whatsNew": "translated-French-Custom release notes"}}},
    )

    monkeypatch.setattr(release, "list_presets", lambda: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True
    assert fake_cli.ai_manager.get_provider("fake").calls[-1]["text"] == "Custom release notes"


def test_release_run_returns_when_base_language_not_detected(fake_cli, fake_asc, fake_ui, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.checkbox_values.extend([["IOS"]])
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response(
        "get_app_store_version_localizations",
        lambda *_a, **_k: {"data": [{"id": "loc-1", "attributes": {"locale": None, "whatsNew": ""}}]},
    )
    monkeypatch.setattr(release, "list_presets", lambda: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert release.run(fake_cli) is True


def test_release_run_returns_when_all_locales_already_have_notes(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.checkbox_values.extend([["IOS"]])
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response(
        "get_app_store_version_localizations",
        lambda *_a, **_k: {
            "data": [
                localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
                localization_payload("fr-FR", loc_id="loc-fr", whatsNew="Already translated"),
            ]
        },
    )
    monkeypatch.setattr(release, "list_presets", lambda: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert release.run(fake_cli) is True


def test_release_run_non_tui_back_from_locale_selection(fake_cli, fake_asc, localization_payload, monkeypatch):
    class NonTUI:
        def available(self):
            return False

        def prompt_app_id(self, _asc):
            return "app1"

        def confirm(self, *_args, **_kwargs):
            return None

        def prompt_multiline(self, *_args, **_kwargs):
            return "unused"

    fake_cli.ui = NonTUI()
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response(
        "get_app_store_version_localizations",
        lambda *_a, **_k: {
            "data": [
                localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
                localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
            ]
        },
    )
    monkeypatch.setattr(release, "list_presets", lambda: [])
    answers = iter(["", "", "b"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert release.run(fake_cli) is True


def test_release_run_edit_selected_locale_then_apply(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "edit"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"], ["fr-FR"]])
    fake_ui.confirm_values.append(True)
    fake_ui.multiline_values.append("Edited French text")

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response(
        "get_app_store_version_localization",
        {"data": {"attributes": {"whatsNew": "Edited French text"}}},
    )
    monkeypatch.setattr(release, "list_presets", lambda: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True
    update_calls = [c for c in fake_asc.calls if c[0] == "update_app_store_version_localization"]
    assert any(call[2].get("whats_new") == "Edited French text" for call in update_calls)


def test_release_run_cancelled_at_next_step(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "cancel"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    monkeypatch.setattr(release, "list_presets", lambda: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True


def test_release_run_declines_apply_at_confirmation(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.append(False)

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    monkeypatch.setattr(release, "list_presets", lambda: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True
    assert not any(call[0] == "update_app_store_version_localization" for call in fake_asc.calls)


def test_release_run_updates_base_when_only_base_missing(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["custom", "apply"])
    fake_ui.checkbox_values.extend([["IOS"]])
    fake_ui.confirm_values.append(True)
    fake_ui.multiline_values.append("Fresh base notes")

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew=""),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew="Existing"),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    monkeypatch.setattr(release, "list_presets", lambda: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True
    base_updates = [
        c for c in fake_asc.calls
        if c[0] == "update_app_store_version_localization" and c[2].get("localization_id") == "loc-en"
    ]
    assert base_updates


def test_release_run_can_overwrite_existing_release_notes(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.extend([True, True])

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew="Old French notes"),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response(
        "get_app_store_version_localization",
        {"data": {"attributes": {"whatsNew": "translated-French-Base notes"}}},
    )

    monkeypatch.setattr(release, "list_presets", lambda: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True
    update_calls = [c for c in fake_asc.calls if c[0] == "update_app_store_version_localization"]
    assert any(call[2].get("localization_id") == "loc-fr" for call in update_calls)


def test_release_run_preset_reenter_to_custom_source(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["reenter", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.append(True)
    fake_ui.multiline_values.append("Custom from reenter")

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew=""),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    preset = ReleaseNotePreset(
        preset_id="preset1",
        name="Preset One",
        translations={"en-US": "Base preset", "fr-FR": "Bonjour preset"},
        path=None,
        built_in=True,
    )
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response(
        "get_app_store_version_localization",
        {"data": {"attributes": {"whatsNew": "translated-French-Custom from reenter"}}},
    )
    monkeypatch.setattr(release, "list_presets", lambda: [preset])
    picks = iter([(preset, False), (None, True)])
    monkeypatch.setattr(release, "prompt_preset_selection", lambda *_a, **_k: next(picks))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True
    assert fake_cli.ai_manager.get_provider("fake").calls[-1]["text"] == "Custom from reenter"


def test_release_run_preset_reenter_switches_to_other_preset(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["reenter", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.append(True)

    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew=""),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    preset1 = ReleaseNotePreset(
        preset_id="preset1",
        name="Preset One",
        translations={"en-US": "Base preset", "fr-FR": "Bonjour preset"},
        path=None,
        built_in=True,
    )
    preset2 = ReleaseNotePreset(
        preset_id="preset2",
        name="Preset Two",
        translations={"en-US": "Second base", "fr-FR": "Deuxieme"},
        path=None,
        built_in=True,
    )
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response(
        "get_app_store_version_localization",
        {"data": {"attributes": {"whatsNew": "Deuxieme"}}},
    )
    monkeypatch.setattr(release, "list_presets", lambda: [preset1, preset2])
    picks = iter([(preset1, False), (preset2, False)])
    monkeypatch.setattr(release, "prompt_preset_selection", lambda *_a, **_k: next(picks))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True
    updates = [c for c in fake_asc.calls if c[0] == "update_app_store_version_localization"]
    assert any(call[2].get("whats_new") == "Deuxieme" for call in updates)
