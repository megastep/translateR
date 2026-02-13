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


def test_release_run_non_tui_reenter_from_preset_then_apply(fake_cli, fake_asc, localization_payload, monkeypatch):
    class NonTUI:
        def available(self):
            return False

        def prompt_app_id(self, _asc):
            return "app1"

        def confirm(self, *_args, **_kwargs):
            return None

        def prompt_multiline(self, *_args, **_kwargs):
            return ""

    fake_cli.ui = NonTUI()
    preset = ReleaseNotePreset(
        preset_id="preset1",
        name="Preset One",
        translations={"en-US": "Base preset", "fr-FR": "Bonjour preset"},
        path=None,
        built_in=True,
    )
    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response("get_app_store_version_localization", {"data": {"attributes": {"whatsNew": "Bonjour preset"}}})
    monkeypatch.setattr(release, "list_presets", lambda: [preset])
    picks = iter([(preset, False), (None, True)])
    monkeypatch.setattr(release, "prompt_preset_selection", lambda *_a, **_k: next(picks))
    answers = iter(["", "p", "", "r", "a", "y", ""])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert release.run(fake_cli) is True


def test_release_run_non_tui_edit_locale_list_path(fake_cli, fake_asc, localization_payload, monkeypatch):
    class NonTUI:
        def available(self):
            return False

        def prompt_app_id(self, _asc):
            return "app1"

        def confirm(self, *_args, **_kwargs):
            return None

        def prompt_multiline(self, *_args, **_kwargs):
            return "Edited in non-tui"

    fake_cli.ui = NonTUI()
    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response("get_app_store_version_localization", {"data": {"attributes": {"whatsNew": "Edited in non-tui"}}})
    monkeypatch.setattr(release, "list_presets", lambda: [])
    answers = iter(["", "", "", "e", "fr-FR", "y", ""])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert release.run(fake_cli) is True

def test_release_run_non_tui_apply_path(fake_cli, fake_asc, localization_payload, monkeypatch):
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
            localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response("get_app_store_version_localization", {"data": {"attributes": {"whatsNew": "translated-French-Base notes"}}})

    answers = iter(["", "", "", "", "", ""])
    monkeypatch.setattr(release, "list_presets", lambda: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))

    assert release.run(fake_cli) is True
