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


def test_release_note_preset_translation_fallback_order():
    preset = release_presets.ReleaseNotePreset(
        preset_id="p1",
        name="Preset",
        translations={"en-GB": "Hello GB", "fr-FR": "Bonjour"},
        path=release_presets.REPO_ROOT / "x.json",
        built_in=True,
    )
    assert preset.get_translation("de-DE") == "Hello GB"
    assert preset.get_translation("fr-FR") == "Bonjour"


def test_load_preset_invalid_payloads_and_get_preset_not_found(tmp_path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{", encoding="utf-8")
    assert release_presets._load_preset_from_path(bad_json, built_in=False) is None

    missing_translations = tmp_path / "missing.json"
    missing_translations.write_text(json.dumps({"id": "x"}), encoding="utf-8")
    assert release_presets._load_preset_from_path(missing_translations, built_in=False) is None

    non_dict_translations = tmp_path / "nondict.json"
    non_dict_translations.write_text(json.dumps({"translations": ["bad"]}), encoding="utf-8")
    assert release_presets._load_preset_from_path(non_dict_translations, built_in=False) is None

    assert release_presets.get_preset("does-not-exist") is None


def test_save_without_preset_id_and_payload_without_description(tmp_path, monkeypatch):
    monkeypatch.setattr(release_presets, "USER_PRESETS_DIR", tmp_path / "presets")
    preset, path = release_presets.save_user_preset(
        name="Fancy Launch Preset",
        translations={"en-US": "Hello"},
    )
    assert preset.preset_id == "fancy-launch-preset"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "description" not in payload


def test_delete_user_preset_missing_file_and_unlink_error(tmp_path, monkeypatch):
    monkeypatch.setattr(release_presets, "USER_PRESETS_DIR", tmp_path / "presets")
    assert release_presets.delete_user_preset("missing") is False

    target = release_presets.ensure_user_directory() / "broken.json"
    target.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(release_presets.Path, "unlink", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert release_presets.delete_user_preset("broken") is False


def test_builtin_presets_available_false(tmp_path, monkeypatch):
    empty_dir = tmp_path / "builtins"
    empty_dir.mkdir(parents=True)
    monkeypatch.setattr(release_presets, "BUILTIN_PRESETS_DIR", empty_dir)
    assert release_presets.builtin_presets_available() is False
