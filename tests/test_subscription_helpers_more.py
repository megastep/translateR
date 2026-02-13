import builtins

from workflows import subscription_translate as st


class _NonTUI:
    def available(self):
        return False


class _TUI:
    def __init__(self, checkbox_values=None, select_value=None):
        self._checkbox_values = checkbox_values or []
        self._select_value = select_value

    def available(self):
        return True

    def checkbox(self, *_args, **_kwargs):
        return self._checkbox_values.pop(0) if self._checkbox_values else None

    def select(self, *_args, **_kwargs):
        return self._select_value


def test_pick_groups_returns_empty_when_no_groups():
    ui = _NonTUI()
    asc = type("ASC", (), {"get_subscription_groups": lambda *_a, **_k: {"data": []}})()
    assert st._pick_groups(ui, asc, "app1") == []


def test_pick_groups_non_tui_invalid_numbers(monkeypatch):
    ui = _NonTUI()
    asc = type(
        "ASC",
        (),
        {"get_subscription_groups": lambda *_a, **_k: {"data": [{"id": "g1", "attributes": {"referenceName": "Main"}}]}},
    )()
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "x")
    assert st._pick_groups(ui, asc, "app1") == []


def test_pick_groups_tui_no_selection_returns_empty():
    ui = _TUI(checkbox_values=[None])
    asc = type(
        "ASC",
        (),
        {"get_subscription_groups": lambda *_a, **_k: {"data": [{"id": "g1", "attributes": {"referenceName": "Main"}}]}},
    )()
    assert st._pick_groups(ui, asc, "app1") == []


def test_pick_subscriptions_returns_empty_when_none_found(monkeypatch):
    ui = _NonTUI()
    asc = type("ASC", (), {"get_subscriptions_for_group": lambda *_a, **_k: {"data": []}})()
    groups = [{"id": "group1", "attributes": {"referenceName": "Main"}}]
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert st._pick_subscriptions(ui, asc, groups) == []


def test_pick_subscriptions_non_tui_invalid_numbers(monkeypatch):
    ui = _NonTUI()
    asc = type(
        "ASC",
        (),
        {"get_subscriptions_for_group": lambda *_a, **_k: {"data": [{"id": "s1", "attributes": {"name": "Monthly"}}]}},
    )()
    groups = [{"id": "group1", "attributes": {"referenceName": "Main"}}]
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "x")
    assert st._pick_subscriptions(ui, asc, groups) == []


def test_mode_selector_tui_defaults_to_sub_when_back():
    ui = _TUI(select_value=None)
    assert st._mode_selector(ui) == "sub"
