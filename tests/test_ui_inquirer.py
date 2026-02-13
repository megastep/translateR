import builtins

from conftest import patch_inquirer_import
from ui import UI


def test_select_with_back_returns_none(monkeypatch):
    patch_inquirer_import(monkeypatch, ["__back__"])
    ui = UI()
    out = ui.select("m", [{"name": "A", "value": "a"}], add_back=True)
    assert out is None


def test_checkbox_filters_back(monkeypatch):
    patch_inquirer_import(monkeypatch, [["__back__", "x"]])
    ui = UI()
    out = ui.checkbox("m", [{"name": "X", "value": "x"}], add_back=True)
    assert out == ["x"]


def test_confirm_text_editor(monkeypatch):
    patch_inquirer_import(monkeypatch, [True, "typed", "edited"])
    ui = UI()

    assert ui.confirm("confirm?") is True
    assert ui.text("text?") == "typed"
    assert ui.editor("edit?") == "edited"
