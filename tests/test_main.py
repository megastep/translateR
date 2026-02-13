import types

import main


class DummyUI:
    def __init__(self, available=False, selected=""):
        self._available = available
        self._selected = selected

    def available(self):
        return self._available

    def select(self, *_args, **_kwargs):
        return self._selected


def _make_cli(choice):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.ui = DummyUI(available=True, selected=choice)
    cli.configuration_mode = lambda: "config"
    return cli


def test_show_main_menu_dispatches_translate(monkeypatch):
    cli = _make_cli("1")
    monkeypatch.setattr(main, "translate_run", lambda _cli: "translated")

    assert main.TranslateRCLI.show_main_menu(cli) == "translated"


def test_show_main_menu_dispatches_release(monkeypatch):
    cli = _make_cli("2")
    monkeypatch.setattr(main, "release_run", lambda _cli: "released")

    assert main.TranslateRCLI.show_main_menu(cli) == "released"


def test_show_main_menu_dispatches_configuration():
    cli = _make_cli("14")
    assert main.TranslateRCLI.show_main_menu(cli) == "config"


def test_show_main_menu_exit_returns_false():
    cli = _make_cli("15")
    assert main.TranslateRCLI.show_main_menu(cli) is False


def test_show_main_menu_invalid_choice_returns_true():
    cli = _make_cli("bogus")
    assert main.TranslateRCLI.show_main_menu(cli) is True


def test_main_entry_invokes_cli_run(monkeypatch):
    calls = []

    class DummyCLI:
        def run(self):
            calls.append("ran")

    monkeypatch.setattr(main, "TranslateRCLI", DummyCLI)
    main.main()

    assert calls == ["ran"]
