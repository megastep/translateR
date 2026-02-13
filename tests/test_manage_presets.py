from pathlib import Path

from release_presets import ReleaseNotePreset
from workflows import manage_presets


def test_create_preset_generates_all_translations(fake_cli, fake_ui, fake_provider, monkeypatch):
    fake_ui.text_values.extend(["Launch Notes", "short desc"])
    fake_ui.multiline_values.append("English source notes")

    monkeypatch.setattr(manage_presets, "preset_exists", lambda _pid: False)
    monkeypatch.setattr(manage_presets, "generate_preset_id", lambda _name: "launch-notes")
    monkeypatch.setattr(manage_presets, "_select_provider", lambda _cli: ("fake", fake_provider))
    monkeypatch.setattr(
        manage_presets,
        "parallel_map_locales",
        lambda target_locales, _task, **_kwargs: ({loc: f"tx-{loc}" for loc in target_locales}, {}),
    )

    saved = {}

    def fake_save_user_preset(name, translations, description=None, preset_id=None):
        saved["name"] = name
        saved["translations"] = translations
        saved["description"] = description
        saved["preset_id"] = preset_id
        return (
            ReleaseNotePreset(
                preset_id=preset_id,
                name=name,
                translations=translations,
                path=Path("config/presets/launch-notes.json"),
                built_in=False,
            ),
            Path("config/presets/launch-notes.json"),
        )

    monkeypatch.setattr(manage_presets, "save_user_preset", fake_save_user_preset)

    manage_presets._create_preset(fake_cli)

    assert saved["name"] == "Launch Notes"
    assert saved["preset_id"] == "launch-notes"
    assert saved["translations"]["en-US"] == "English source notes"
    assert saved["translations"]["fr-FR"].startswith("tx-")


def test_manage_presets_run_back_returns_true(fake_cli, fake_ui, monkeypatch):
    fake_ui.select_values.append("back")
    monkeypatch.setattr(manage_presets, "list_presets", lambda: [])

    assert manage_presets.run(fake_cli) is True
