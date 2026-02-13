import builtins
from pathlib import Path

from release_presets import ReleaseNotePreset
from workflows import manage_presets


def _preset(preset_id="p1", name="Preset", built_in=False, desc=None, translations=None):
    return ReleaseNotePreset(
        preset_id=preset_id,
        name=name,
        translations=translations or {"en-US": "Hello", "fr-FR": "Bonjour"},
        path=Path(f"config/presets/{preset_id}.json"),
        built_in=built_in,
        description=desc,
    )


def test_preview_select_provider_and_prompt_text_paths(fake_cli, fake_ui, monkeypatch):
    fallback_locale = next(iter(manage_presets.APP_STORE_LOCALES.keys()))
    preset = _preset(translations={"en-US": "", fallback_locale: "Fallback preview"})
    assert "Fallback preview" in manage_presets._preset_preview(preset)

    fake_provider = fake_cli.ai_manager.get_provider("fake")
    monkeypatch.setattr(manage_presets, "pick_provider", lambda *_a, **_k: (fake_provider, "fake"))
    key, provider = manage_presets._select_provider(fake_cli)
    assert key == "fake"
    assert provider is fake_provider

    fake_ui.multiline_values.append(None)
    assert manage_presets._prompt_text(fake_ui, "Prompt") is None


def test_create_preset_non_tui_overwrite_truncate_and_task_path(fake_cli, monkeypatch):
    class NonTUI:
        def available(self):
            return False

        def prompt_multiline(self, *_a, **_k):
            return "abcdefghij"

        def confirm(self, *_a, **_k):
            return None

    fake_cli.ui = NonTUI()
    monkeypatch.setattr(manage_presets, "APP_STORE_LOCALES", {"en-US": "English", "fr-FR": "French"})
    monkeypatch.setattr(manage_presets, "get_field_limit", lambda _field: 5)
    monkeypatch.setattr(manage_presets, "generate_preset_id", lambda _n: "preset-id")
    monkeypatch.setattr(manage_presets, "preset_exists", lambda _pid: True)
    monkeypatch.setattr(manage_presets, "_select_provider", lambda _cli: ("fake", fake_cli.ai_manager.get_provider("fake")))
    answers = iter(["Preset Name", "y", "desc"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))

    def fake_parallel(target_locales, task, **_kwargs):
        return {loc: task(loc) for loc in target_locales}, {}

    monkeypatch.setattr(manage_presets, "parallel_map_locales", fake_parallel)

    saved = {}

    def fake_save(**kwargs):
        saved.update(kwargs)
        return _preset(), Path("config/presets/preset-id.json")

    monkeypatch.setattr(manage_presets, "save_user_preset", fake_save)
    manage_presets._create_preset(fake_cli)

    assert saved["name"] == "Preset Name"
    assert saved["translations"]["en-US"] == "abcde"
    assert len(saved["translations"]["fr-FR"]) <= 5


def test_delete_and_view_branch_paths(fake_ui, monkeypatch):
    manage_presets._delete_preset(fake_ui, [])

    fake_ui.select_values.append(None)
    manage_presets._delete_preset(fake_ui, [_preset("p2", built_in=False)])

    fake_ui.select_values.append("p2")
    fake_ui.confirm_values.append(True)
    monkeypatch.setattr(manage_presets, "delete_user_preset", lambda _pid: False)
    manage_presets._delete_preset(fake_ui, [_preset("p2", built_in=False)])

    manage_presets._view_preset(fake_ui, [])
    fake_ui.select_values.append(None)
    manage_presets._view_preset(fake_ui, [_preset("p3", built_in=True)])

    class NonTUI:
        def available(self):
            return False

    ui = NonTUI()
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    manage_presets._view_preset(ui, [_preset("p4", built_in=True)])

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1")
    manage_presets._view_preset(
        ui,
        [_preset("p5", built_in=False, desc="Desc", translations={"en-US": "Hello", "fr-FR": "Bonjour", "de-DE": "Hallo"})],
    )


def test_run_tui_unknown_action_branch(fake_cli, fake_ui, monkeypatch):
    fake_ui.select_values.extend(["weird", "back"])
    monkeypatch.setattr(manage_presets, "list_presets", lambda: [])
    assert manage_presets.run(fake_cli) is True
