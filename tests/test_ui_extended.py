import builtins

from ui import UI


class FakeASC:
    def __init__(self, pages):
        self.pages = pages
        self.calls = 0

    def get_apps_page(self, limit=25, cursor=None):
        idx = self.calls
        self.calls += 1
        return self.pages[idx]


def test_prompt_app_id_non_tui_selects_number(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "available", lambda: False)

    pages = [
        {
            "data": [
                {"id": "app1", "attributes": {"name": "Demo", "bundleId": "com.demo"}},
            ],
            "next_cursor": None,
        }
    ]
    asc = FakeASC(pages)

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1")
    out = ui.prompt_app_id(asc)
    assert out == "app1"


def test_prompt_app_id_non_tui_manual_when_empty(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "available", lambda: False)

    pages = [{"data": [], "next_cursor": None}]
    asc = FakeASC(pages)

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "manual-app-id")
    out = ui.prompt_app_id(asc)
    assert out == "manual-app-id"


def test_prompt_app_id_non_tui_next_page_then_select(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "available", lambda: False)

    pages = [
        {
            "data": [{"id": "app1", "attributes": {"name": "First", "bundleId": "a.first"}}],
            "next_cursor": "cursor-2",
        },
        {
            "data": [{"id": "app2", "attributes": {"name": "Second", "bundleId": "a.second"}}],
            "next_cursor": None,
        },
    ]
    asc = FakeASC(pages)

    answers = iter(["n", "1"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    out = ui.prompt_app_id(asc)
    assert out == "app2"


def test_prompt_app_id_non_tui_cancel(monkeypatch):
    ui = UI()
    monkeypatch.setattr(ui, "available", lambda: False)

    pages = [
        {
            "data": [{"id": "app1", "attributes": {"name": "First", "bundleId": "a.first"}}],
            "next_cursor": None,
        }
    ]
    asc = FakeASC(pages)

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "q")
    out = ui.prompt_app_id(asc)
    assert out is None


def test_default_editor_cmd_prefers_visual_then_editor(monkeypatch):
    ui = UI()
    monkeypatch.setenv("VISUAL", "code -w")
    monkeypatch.setenv("EDITOR", "vim")
    assert ui._default_editor_cmd() == "code -w"

    monkeypatch.delenv("VISUAL", raising=False)
    assert ui._default_editor_cmd() == "vim"
