import builtins
import types

from ui import UI


class _Exec:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class _Inq:
    def __init__(self, values):
        self.values = values

    def select(self, **_kwargs):
        return _Exec(self.values.pop(0))

    def checkbox(self, **_kwargs):
        return _Exec(self.values.pop(0))

    def confirm(self, **_kwargs):
        return _Exec(self.values.pop(0))

    def text(self, **_kwargs):
        return _Exec(self.values.pop(0))

    def editor(self, **_kwargs):
        return _Exec(self.values.pop(0))


def _patch_inquirer_import(monkeypatch, values):
    fake_module = types.SimpleNamespace(inquirer=_Inq(values))
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "InquirerPy":
            return fake_module
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_select_with_back_returns_none(monkeypatch):
    _patch_inquirer_import(monkeypatch, ["__back__"])
    ui = UI()
    out = ui.select("m", [{"name": "A", "value": "a"}], add_back=True)
    assert out is None


def test_checkbox_filters_back(monkeypatch):
    _patch_inquirer_import(monkeypatch, [["__back__", "x"]])
    ui = UI()
    out = ui.checkbox("m", [{"name": "X", "value": "x"}], add_back=True)
    assert out == ["x"]


def test_confirm_text_editor(monkeypatch):
    _patch_inquirer_import(monkeypatch, [True, "typed", "edited"])
    ui = UI()

    assert ui.confirm("confirm?") is True
    assert ui.text("text?") == "typed"
    assert ui.editor("edit?") == "edited"
