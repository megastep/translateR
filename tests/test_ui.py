import builtins

from ui import UI


def test_available_false_when_no_tty(monkeypatch):
    ui = UI()
    monkeypatch.setenv("TRANSLATER_NO_TUI", "1")
    assert ui.available() is False


def test_prompt_multiline_uses_console_fallback(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "available", lambda: False)
    monkeypatch.setattr(ui, "_launch_system_editor", lambda **_kwargs: None)

    answers = iter(["line 1", "line 2", "EOF"])
    monkeypatch.setattr(builtins, "input", lambda *args, **kwargs: next(answers))

    out = ui.prompt_multiline("Prompt")
    assert out == "line 1\nline 2"


def test_prompt_multiline_prefers_editor_when_available(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "available", lambda: True)
    monkeypatch.setattr(ui, "editor", lambda *_args, **_kwargs: "edited text")

    out = ui.prompt_multiline("Prompt", initial="old")
    assert out == "edited text"


def test_select_returns_none_if_inquirer_missing(monkeypatch):
    ui = UI()
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("InquirerPy"):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert ui.select("msg", [{"name": "A", "value": "a"}]) is None
