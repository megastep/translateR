import builtins
from pathlib import Path

from release_presets import ReleaseNotePreset
from workflows import manage_presets


class NonTUI:
    def available(self):
        return False

    def confirm(self, *_args, **_kwargs):
        return None


def _preset(preset_id, name, built_in=False):
    return ReleaseNotePreset(
        preset_id=preset_id,
        name=name,
        translations={"en-US": "Hello"},
        path=Path(f"config/presets/{preset_id}.json"),
        built_in=built_in,
    )


def test_delete_preset_non_tui_confirm_yes(monkeypatch):
    ui = NonTUI()
    presets = [_preset("p1", "Preset One", built_in=False)]

    answers = iter(["1", "y"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))

    called = {"ok": False}
    monkeypatch.setattr(manage_presets, "delete_user_preset", lambda _pid: called.__setitem__("ok", True) or True)

    manage_presets._delete_preset(ui, presets)
    assert called["ok"] is True


def test_view_preset_non_tui_displays_selected(monkeypatch):
    ui = NonTUI()
    presets = [_preset("p1", "Preset One", built_in=True)]

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1")
    manage_presets._view_preset(ui, presets)


def test_create_preset_aborts_when_translation_errors(fake_cli, fake_ui, monkeypatch):
    fake_ui.text_values.extend(["Launch Notes", "desc"])
    fake_ui.multiline_values.append("English source notes")

    monkeypatch.setattr(manage_presets, "preset_exists", lambda _pid: False)
    monkeypatch.setattr(manage_presets, "generate_preset_id", lambda _name: "launch-notes")
    monkeypatch.setattr(manage_presets, "_select_provider", lambda _cli: ("fake", fake_cli.ai_manager.get_provider("fake")))
    monkeypatch.setattr(
        manage_presets,
        "parallel_map_locales",
        lambda target_locales, _task, **_kwargs: ({}, {target_locales[0]: "failed"}),
    )

    called = {"saved": False}
    monkeypatch.setattr(
        manage_presets,
        "save_user_preset",
        lambda **_kwargs: called.__setitem__("saved", True),
    )

    manage_presets._create_preset(fake_cli)
    assert called["saved"] is False
