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


def test_release_run_cancel_and_no_platforms(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = None
    assert release.run(fake_cli) is True

    fake_ui.app_id = "app1"
    monkeypatch.setattr(release, "select_platform_versions", lambda *_a, **_k: (None, None, None))
    assert release.run(fake_cli) is True


def test_release_run_base_empty_with_presets_cancel_or_empty_custom(fake_cli, fake_ui, fake_asc, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {
            "data": [
                localization_payload("en-US", loc_id="loc-en", whatsNew=""),
                localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
            ]
        },
    )

    preset = ReleaseNotePreset(
        preset_id="preset1",
        name="Preset One",
        translations={"en-US": "Base preset", "fr-FR": "Bonjour preset"},
        path=None,
        built_in=True,
    )
    monkeypatch.setattr(release, "list_presets", lambda: [preset])
    monkeypatch.setattr(release, "prompt_preset_selection", lambda *_a, **_k: (None, False))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert release.run(fake_cli) is True

    monkeypatch.setattr(release, "prompt_preset_selection", lambda *_a, **_k: (None, True))
    fake_ui.multiline_values.append("")
    assert release.run(fake_cli) is True

    fake_ui.multiline_values.append("   ")
    assert release.run(fake_cli) is True


def test_release_run_base_empty_no_presets_and_provider_none(fake_cli, fake_ui, fake_asc, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {
            "data": [
                localization_payload("en-US", loc_id="loc-en", whatsNew=""),
                localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
            ]
        },
    )
    monkeypatch.setattr(release, "list_presets", lambda: [])
    fake_ui.multiline_values.append("")
    assert release.run(fake_cli) is True

    fake_ui.multiline_values.append("  ")
    assert release.run(fake_cli) is True

    fake_ui.multiline_values.append("Custom source")
    fake_ui.select_values.append("apply")
    fake_ui.checkbox_values.extend([["IOS"], []])
    monkeypatch.setattr(release, "pick_provider", lambda *_a, **_k: (None, None))
    assert release.run(fake_cli) is True


def test_release_run_apply_error_and_verify_warning_paths(fake_cli, fake_ui, fake_asc, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], []])
    fake_ui.confirm_values.append(True)

    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {
            "data": [
                localization_payload("en-US", loc_id="loc-en", whatsNew=""),
                localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
            ]
        },
    )

    def update_loc(localization_id=None, **_kwargs):
        if localization_id == "loc-en":
            raise RuntimeError("base failed")
        return {"data": {"id": localization_id}}

    fake_asc.set_response("update_app_store_version_localization", update_loc)
    fake_asc.set_response("get_app_store_version_localization", {"data": {"attributes": {"whatsNew": ""}}})

    def fake_parallel(locales, task, progress_action=None, **_kwargs):
        if progress_action == "Translated":
            return {loc: task(loc) for loc in locales}, {}
        return {}, {"fr-FR": "apply failed"}

    monkeypatch.setattr(release, "parallel_map_locales", fake_parallel)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert release.run(fake_cli) is True
