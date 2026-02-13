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


def _setup_basic_release(fake_asc, localization_payload):
    locs = {
        "data": [
            localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
            localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
        ]
    }
    fake_asc.set_response("_request", _versions_response())
    fake_asc.set_response("get_app_store_version_localizations", lambda *_a, **_k: locs)
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response("get_app_store_version_localization", {"data": {"attributes": {"whatsNew": "ok"}}})


def test_prompt_preset_selection_tui_none_unknown_and_non_tui_empty(monkeypatch):
    class UI:
        def __init__(self, value, tui=True):
            self.value = value
            self._tui = tui

        def available(self):
            return self._tui

        def select(self, *_a, **_k):
            return self.value

    preset = ReleaseNotePreset("p1", "Preset", {"en-US": "Hello"}, path=None, built_in=True)
    chosen, use_custom = release.prompt_preset_selection(UI(None, tui=True), [preset], "en-US", allow_custom=True)
    assert chosen is None and use_custom is False

    chosen, use_custom = release.prompt_preset_selection(UI("unknown", tui=True), [preset], "en-US", allow_custom=True)
    assert chosen is None and use_custom is False

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    chosen, use_custom = release.prompt_preset_selection(UI("ignored", tui=False), [preset], "en-US", allow_custom=True)
    assert chosen is None and use_custom is False


def test_release_run_source_edit_and_empty_custom_paths(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["edit", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.append(True)
    fake_ui.multiline_values.append("Edited source")
    _setup_basic_release(fake_asc, localization_payload)

    monkeypatch.setattr(release, "list_presets", lambda: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert release.run(fake_cli) is True

    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["custom"])
    fake_ui.checkbox_values.extend([["IOS"]])
    fake_ui.multiline_values.append("")
    _setup_basic_release(fake_asc, localization_payload)
    monkeypatch.setattr(release, "list_presets", lambda: [])
    assert release.run(fake_cli) is True


def test_release_run_preset_without_base_content_then_use_base(fake_cli, fake_asc, fake_ui, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["preset", "use", "apply"])
    fake_ui.checkbox_values.extend([["IOS"], ["fr-FR"]])
    fake_ui.confirm_values.append(True)
    _setup_basic_release(fake_asc, localization_payload)

    empty_preset = ReleaseNotePreset(
        preset_id="empty",
        name="Empty preset",
        translations={"en-US": "", "fr-FR": ""},
        path=None,
        built_in=True,
    )
    monkeypatch.setattr(release, "list_presets", lambda: [empty_preset])
    monkeypatch.setattr(release, "prompt_preset_selection", lambda *_a, **_k: (empty_preset, False))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert release.run(fake_cli) is True


def test_release_run_non_tui_cancel_and_reenter_paths(fake_cli, fake_asc, localization_payload, monkeypatch):
    class NonTUI:
        def available(self):
            return False

        def prompt_app_id(self, _asc):
            return "app1"

        def confirm(self, *_a, **_k):
            return None

        def prompt_multiline(self, *_a, **_k):
            return "New from non-tui"

    fake_cli.ui = NonTUI()
    _setup_basic_release(fake_asc, localization_payload)
    monkeypatch.setattr(release, "list_presets", lambda: [])
    answers = iter(["", "", "c"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert release.run(fake_cli) is True

    _setup_basic_release(fake_asc, localization_payload)
    answers = iter(["", "", "r", "a", "", ""])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert release.run(fake_cli) is True
