import builtins

from conftest import patch_inquirer_import
from ui import UI


def test_inquirer_primitives_return_none_on_execute_error(monkeypatch):
    patch_inquirer_import(monkeypatch, fail=True)
    ui = UI()
    assert ui.select("m", [{"name": "A", "value": "a"}]) is None
    assert ui.checkbox("m", [{"name": "A", "value": "a"}]) is None
    assert ui.confirm("m") is None
    assert ui.text("m") is None
    assert ui.editor("m") is None


def test_inquirer_primitives_return_none_when_module_missing(monkeypatch):
    ui = UI()
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "InquirerPy":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert ui.confirm("m") is None
    assert ui.text("m") is None
    assert ui.editor("m") is None


def test_default_editor_cmd_windows(monkeypatch):
    ui = UI()
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.setattr("ui.os.name", "nt")
    assert ui._default_editor_cmd() == "notepad"


def test_launch_system_editor_ignores_remove_failure(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "_default_editor_cmd", lambda: "vi")
    monkeypatch.setattr("subprocess.run", lambda *_a, **_k: None)
    monkeypatch.setattr("ui.os.remove", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("rm failed")))
    out = ui._launch_system_editor(initial="hello")
    assert out == "hello"


def test_prompt_multiline_console_with_initial_and_eof_error(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "available", lambda: False)
    monkeypatch.setattr(ui, "_launch_system_editor", lambda **_kwargs: None)

    answers = iter(["line one", EOFError()])

    def fake_input(*_a, **_k):
        nxt = next(answers)
        if isinstance(nxt, BaseException):
            raise nxt
        return nxt

    monkeypatch.setattr(builtins, "input", fake_input)
    out = ui.prompt_multiline("Prompt", initial="seed text")
    assert out == "line one"


def test_fuzzy_picker_manual_and_failure(monkeypatch):
    patch_inquirer_import(monkeypatch, values=["__manual__"])
    ui = UI()
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "manual-id")
    apps = [{"id": "a1", "attributes": {"name": "Demo", "bundleId": "x.y"}}]
    assert ui._fuzzy_app_picker(apps) == "manual-id"

    patch_inquirer_import(monkeypatch, fail=True)
    assert ui._fuzzy_app_picker(apps) is None


def test_prompt_app_id_non_tui_prev_navigation(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "available", lambda: False)

    pages = [
        {
            "data": [{"id": "app1", "attributes": {"name": "One", "bundleId": "a.one"}}],
            "next_cursor": "cursor-2",
        },
        {
            "data": [{"id": "app2", "attributes": {"name": "Two", "bundleId": "a.two"}}],
            "next_cursor": None,
        },
    ]

    class ASC:
        def __init__(self):
            self.calls = 0

        def get_apps_page(self, limit=25, cursor=None):
            idx = self.calls
            self.calls += 1
            return pages[idx]

    answers = iter(["n", "p", "1"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert ui.prompt_app_id(ASC()) == "app1"
