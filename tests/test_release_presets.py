import json

import release_presets


def test_slugify_and_generate_preset_id():
    assert release_presets.generate_preset_id("  My Fancy Preset  ") == "my-fancy-preset"


def test_normalize_translations_fills_missing_locales():
    normalized = release_presets._normalize_translations({"en-US": "Hello", "fr-FR": "Bonjour"})

    assert normalized["fr-FR"] == "Bonjour"
    assert normalized["de-DE"] == "Hello"


def test_save_get_delete_user_preset(tmp_path, monkeypatch):
    monkeypatch.setattr(release_presets, "USER_PRESETS_DIR", tmp_path / "presets")

    preset, path = release_presets.save_user_preset(
        name="Launch",
        translations={"en-US": "Hello", "fr-FR": "Bonjour"},
        description="desc",
        preset_id="launch",
    )

    assert path.exists()
    assert preset.preset_id == "launch"
    got = release_presets.get_preset("launch")
    assert got is not None
    assert got.name == "Launch"

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["id"] == "launch"
    assert release_presets.delete_user_preset("launch") is True
    assert release_presets.get_preset("launch") is None
