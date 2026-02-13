import builtins
import io
import types

from ui import UI


def _patch_inquirer_success(monkeypatch):
    fake_module = types.SimpleNamespace(inquirer=object())
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "InquirerPy":
            return fake_module
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_available_true_with_tty_and_inquirer(monkeypatch):
    ui = UI()
    _patch_inquirer_success(monkeypatch)
    monkeypatch.setattr("sys.stdin", io.StringIO())
    monkeypatch.setattr("sys.stdout", io.StringIO())
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.delenv("TRANSLATER_NO_TUI", raising=False)
    assert ui.available() is True


def test_checkbox_back_only_returns_none(monkeypatch):
    class _Exec:
        def execute(self):
            return ["__back__"]

    class _Inq:
        def checkbox(self, **_kwargs):
            return _Exec()

    fake_module = types.SimpleNamespace(inquirer=_Inq())
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "InquirerPy":
            return fake_module
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    ui = UI()
    assert ui.checkbox("msg", [{"name": "x", "value": "x"}], add_back=True) is None


def test_prompt_multiline_uses_system_editor_result(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "available", lambda: False)
    monkeypatch.setattr(ui, "_launch_system_editor", lambda **_kwargs: "from editor")
    assert ui.prompt_multiline("Prompt", initial="old") == "from editor"


def test_launch_system_editor_fallback_editor(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "_default_editor_cmd", lambda: "missing_editor")

    calls = {"n": 0}

    def fake_run(args, check=False):
        calls["n"] += 1
        path = args[-1]
        if calls["n"] == 1:
            raise FileNotFoundError("missing")
        with open(path, "w", encoding="utf-8") as f:
            f.write("edited by fallback")

    monkeypatch.setattr("subprocess.run", fake_run)
    out = ui._launch_system_editor(initial="start")
    assert out == "edited by fallback"


def test_launch_system_editor_returns_none_when_both_editors_fail(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "_default_editor_cmd", lambda: "missing_editor")

    def fake_run(_args, check=False):
        raise FileNotFoundError("missing")

    monkeypatch.setattr("subprocess.run", fake_run)
    assert ui._launch_system_editor(initial="start") is None


def test_prompt_app_id_tui_fuzzy_path(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "available", lambda: True)
    monkeypatch.setattr(
        ui,
        "_fuzzy_app_picker",
        lambda _apps: "picked-app",
    )

    asc = types.SimpleNamespace(
        get_apps=lambda **_kwargs: {
            "data": [{"id": "app1", "attributes": {"name": "Demo", "bundleId": "x.y"}}]
        }
    )
    assert ui.prompt_app_id(asc) == "picked-app"


def test_prompt_app_id_handles_fetch_exception_then_manual(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "available", lambda: True)

    class _ASC:
        def get_apps(self, **_kwargs):
            raise RuntimeError("boom")

        def get_apps_page(self, **_kwargs):
            raise RuntimeError("boom-page")

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "manual-id")
    assert ui.prompt_app_id(_ASC()) == "manual-id"


def test_prompt_app_id_non_tui_reprompts_then_accepts_manual(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "available", lambda: False)

    asc = types.SimpleNamespace(
        get_apps_page=lambda **_kwargs: {
            "data": [{"id": "app1", "attributes": {"name": "Demo", "bundleId": "bundle"}}],
            "next_cursor": None,
        }
    )
    answers = iter(["", "99", "manual-id"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert ui.prompt_app_id(asc) == "manual-id"
