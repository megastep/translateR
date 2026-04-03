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


def test_release_run_non_tui_source_choice_branches(fake_cli, fake_asc, localization_payload, monkeypatch):
    class NonTUI:
        def __init__(self, values):
            self.values = iter(values)

        def available(self):
            return False

        def prompt_app_id(self, _asc):
            return "app1"

        def confirm(self, *_a, **_k):
            return None

        def prompt_multiline(self, *_a, **_k):
            return next(self.values)

    monkeypatch.setattr(
        release,
        "select_platform_versions",
        lambda *_a, **_k: ({"IOS": {"id": "ver-ios"}}, {"IOS": {"id": "ver-ios"}}, {"IOS": "iOS"}),
    )
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {
            "data": [
                localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
                localization_payload("fr-FR", loc_id="loc-fr", whatsNew="Already translated"),
            ]
        },
    )
    monkeypatch.setattr(release, "list_presets", lambda: [])

    fake_cli.ui = NonTUI(["Custom source"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "n")
    assert release.run(fake_cli) is True

    fake_cli.ui = NonTUI(["Custom source"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "c")
    assert release.run(fake_cli) is True

    fake_cli.ui = NonTUI(["unused"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "invalid")
    assert release.run(fake_cli) is True


def test_release_run_non_tui_edit_empty_and_parsed_empty(fake_cli, fake_asc, localization_payload, monkeypatch):
    class NonTUI:
        def __init__(self, value):
            self.value = value

        def available(self):
            return False

        def prompt_app_id(self, _asc):
            return "app1"

        def confirm(self, *_a, **_k):
            return None

        def prompt_multiline(self, *_a, **_k):
            return self.value

    monkeypatch.setattr(
        release,
        "select_platform_versions",
        lambda *_a, **_k: ({"IOS": {"id": "ver-ios"}}, {"IOS": {"id": "ver-ios"}}, {"IOS": "iOS"}),
    )
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {
            "data": [
                localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
                localization_payload("fr-FR", loc_id="loc-fr", whatsNew=""),
            ]
        },
    )
    monkeypatch.setattr(release, "list_presets", lambda: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "e")

    fake_cli.ui = NonTUI("")
    assert release.run(fake_cli) is True

    fake_cli.ui = NonTUI("Edited")
    monkeypatch.setattr(release, "parse_refinement_template", lambda *_a, **_k: ("", "keep"))
    assert release.run(fake_cli) is True


def test_release_run_non_tui_preset_continue_and_base_empty_custom(fake_cli, fake_asc, localization_payload, monkeypatch):
    class NonTUI:
        def __init__(self, value):
            self.value = value

        def available(self):
            return False

        def prompt_app_id(self, _asc):
            return "app1"

        def confirm(self, *_a, **_k):
            return None

        def prompt_multiline(self, *_a, **_k):
            return self.value

    preset = ReleaseNotePreset(
        preset_id="p1",
        name="Preset One",
        translations={"en-US": "Preset base"},
        path=None,
        built_in=True,
    )

    monkeypatch.setattr(
        release,
        "select_platform_versions",
        lambda *_a, **_k: ({"IOS": {"id": "ver-ios"}}, {"IOS": {"id": "ver-ios"}}, {"IOS": "iOS"}),
    )

    # Base present path: first choose preset, get none, then continue with "use".
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {
            "data": [
                localization_payload("en-US", loc_id="loc-en", whatsNew="Base notes"),
                localization_payload("fr-FR", loc_id="loc-fr", whatsNew="Already translated"),
            ]
        },
    )
    monkeypatch.setattr(release, "list_presets", lambda: [preset])
    monkeypatch.setattr(release, "prompt_preset_selection", lambda *_a, **_k: (None, False))
    answers = iter(["p", "", "n"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    fake_cli.ui = NonTUI("unused")
    assert release.run(fake_cli) is True

    # Base empty path with presets: choose custom source through prompt_preset_selection.
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {"data": [localization_payload("en-US", loc_id="loc-en", whatsNew="")]},
    )
    monkeypatch.setattr(release, "prompt_preset_selection", lambda *_a, **_k: (None, True))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "n")
    fake_cli.ui = NonTUI("Custom base source")
    assert release.run(fake_cli) is True
