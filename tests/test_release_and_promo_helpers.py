from release_presets import ReleaseNotePreset
from workflows import promo, release


class DummyUI:
    def __init__(self):
        self._available = True
        self.select_values = []
        self.multiline_values = []

    def available(self):
        return self._available

    def select(self, *_args, **_kwargs):
        return self.select_values.pop(0) if self.select_values else None

    def prompt_multiline(self, *_args, **_kwargs):
        return self.multiline_values.pop(0) if self.multiline_values else None


def test_preset_preview_text_uses_base_translation():
    preset = ReleaseNotePreset(
        preset_id="p1",
        name="Preset",
        translations={"en-US": "Hello world", "fr-FR": "Bonjour"},
        path=None,
        built_in=True,
    )
    out = release._preset_preview_text(preset, "fr-FR")
    assert "Bonjour" in out


def test_prompt_preset_selection_tui_custom_path():
    ui = DummyUI()
    ui.select_values = ["__custom__"]
    presets = [
        ReleaseNotePreset("p1", "Preset", {"en-US": "Hello"}, path=None, built_in=True),
    ]

    chosen, use_custom = release.prompt_preset_selection(ui, presets, "en-US", allow_custom=True)
    assert chosen is None
    assert use_custom is True


def test_prompt_source_promotional_text_use_base():
    ui = DummyUI()
    ui.select_values = ["use"]

    text, refine = promo._prompt_source_promotional_text(ui, "Base text", "default", "")
    assert text == "Base text"
    assert refine == "default"


def test_prompt_source_promotional_text_custom_multiline():
    ui = DummyUI()
    ui.select_values = ["custom"]
    ui.multiline_values = ["# Prompt Refinement: add notes below to guide the translation\n# PROMPT: keep concise\n\nNew promo"]

    text, refine = promo._prompt_source_promotional_text(ui, "Base text", "default", "")
    assert text == "New promo"
    assert "keep concise" in refine
