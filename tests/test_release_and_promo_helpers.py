import builtins

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


def test_preset_preview_text_falls_back_to_en_us():
    preset = ReleaseNotePreset(
        preset_id="p1",
        name="Preset",
        translations={"en-US": "Fallback English text", "fr-FR": ""},
        path=None,
        built_in=True,
    )
    out = release._preset_preview_text(preset, "fr-FR")
    assert "Fallback English" in out


def test_preset_preview_text_empty_when_no_translation():
    preset = ReleaseNotePreset(
        preset_id="p1",
        name="Preset",
        translations={"en-US": "   ", "fr-FR": ""},
        path=None,
        built_in=True,
    )
    out = release._preset_preview_text(preset, "fr-FR")
    assert out == "(empty)"


def test_prompt_preset_selection_tui_custom_path():
    ui = DummyUI()
    ui.select_values = ["__custom__"]
    presets = [
        ReleaseNotePreset("p1", "Preset", {"en-US": "Hello"}, path=None, built_in=True),
    ]

    chosen, use_custom = release.prompt_preset_selection(ui, presets, "en-US", allow_custom=True)
    assert chosen is None
    assert use_custom is True


def test_prompt_preset_selection_returns_none_when_filtered_empty():
    ui = DummyUI()
    preset = ReleaseNotePreset("p1", "Preset", {"en-US": "Hello"}, path=None, built_in=True)
    chosen, use_custom = release.prompt_preset_selection(ui, [preset], "en-US", exclude_id="p1", allow_custom=False)
    assert chosen is None
    assert use_custom is False


def test_prompt_preset_selection_tui_returns_selected_preset():
    ui = DummyUI()
    ui.select_values = ["p1"]
    preset = ReleaseNotePreset("p1", "Preset", {"en-US": "Hello"}, path=None, built_in=True)
    chosen, use_custom = release.prompt_preset_selection(ui, [preset], "en-US", allow_custom=True)
    assert chosen is preset
    assert use_custom is False


def test_prompt_preset_selection_non_tui_custom(monkeypatch):
    ui = DummyUI()
    ui._available = False
    preset = ReleaseNotePreset("p1", "Preset", {"en-US": "Hello"}, path=None, built_in=True)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "0")
    chosen, use_custom = release.prompt_preset_selection(ui, [preset], "en-US", allow_custom=True)
    assert chosen is None
    assert use_custom is True


def test_prompt_preset_selection_non_tui_invalid_selection(monkeypatch):
    ui = DummyUI()
    ui._available = False
    preset = ReleaseNotePreset("p1", "Preset", {"en-US": "Hello"}, path=None, built_in=True)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "abc")
    chosen, use_custom = release.prompt_preset_selection(ui, [preset], "en-US", allow_custom=False)
    assert chosen is None
    assert use_custom is False


def test_prompt_preset_selection_non_tui_out_of_range(monkeypatch):
    ui = DummyUI()
    ui._available = False
    preset = ReleaseNotePreset("p1", "Preset", {"en-US": "Hello"}, path=None, built_in=True)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "9")
    chosen, use_custom = release.prompt_preset_selection(ui, [preset], "en-US", allow_custom=False)
    assert chosen is None
    assert use_custom is False


def test_prompt_preset_selection_non_tui_valid_number(monkeypatch):
    ui = DummyUI()
    ui._available = False
    preset = ReleaseNotePreset("p1", "Preset", {"en-US": "Hello"}, path=None, built_in=True)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1")
    chosen, use_custom = release.prompt_preset_selection(ui, [preset], "en-US", allow_custom=False)
    assert chosen is preset
    assert use_custom is False


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


def test_prompt_source_promotional_text_tui_cancel():
    ui = DummyUI()
    ui.select_values = [None]
    text, refine = promo._prompt_source_promotional_text(ui, "Base text", "default", "r")
    assert text == ""
    assert refine == "r"


def test_prompt_source_promotional_text_non_tui_defaults_to_use(monkeypatch):
    class NonTUI:
        def available(self):
            return False

        def prompt_multiline(self, *_args, **_kwargs):
            return None

    ui = NonTUI()
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "weird")
    text, refine = promo._prompt_source_promotional_text(ui, "Base text", "default", "")
    assert text == "Base text"
    assert refine == "default"


def test_prompt_source_promotional_text_retries_until_non_empty():
    ui = DummyUI()
    ui.select_values = ["custom", "custom", "custom"]
    ui.multiline_values = ["", "  ", "Valid promo"]
    text, refine = promo._prompt_source_promotional_text(ui, "Base text", "default", "")
    assert text == "Valid promo"
    assert refine == "default"
