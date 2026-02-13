from pathlib import Path

from release_presets import ReleaseNotePreset
from workflows import manage_presets


def test_manage_presets_run_action_flow(fake_cli, fake_ui, monkeypatch):
    fake_ui.select_values.extend(["create", "view", "delete", "back"])

    preset = ReleaseNotePreset(
        preset_id="p1",
        name="Preset",
        translations={"en-US": "Hello"},
        path=Path("presets/p1.json"),
        built_in=False,
    )
    monkeypatch.setattr(manage_presets, "list_presets", lambda: [preset])

    calls = {"create": 0, "view": 0, "delete": 0}
    monkeypatch.setattr(manage_presets, "_create_preset", lambda _cli: calls.__setitem__("create", calls["create"] + 1))
    monkeypatch.setattr(manage_presets, "_view_preset", lambda _ui, _presets: calls.__setitem__("view", calls["view"] + 1))
    monkeypatch.setattr(manage_presets, "_delete_preset", lambda _ui, _presets: calls.__setitem__("delete", calls["delete"] + 1))

    assert manage_presets.run(fake_cli) is True
    assert calls == {"create": 1, "view": 1, "delete": 1}


def test_manage_presets_run_non_tui_unknown_then_back(fake_cli, localization_payload, monkeypatch):
    class NonTUI:
        def available(self):
            return False

    fake_cli.ui = NonTUI()
    preset = ReleaseNotePreset(
        preset_id="p1",
        name="Preset",
        translations={"en-US": "Hello"},
        path=Path("presets/p1.json"),
        built_in=True,
    )
    monkeypatch.setattr(manage_presets, "list_presets", lambda: [preset])
    answers = iter(["9", "4"])
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: next(answers))
    assert manage_presets.run(fake_cli) is True
