import types

import pytest

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


@pytest.mark.parametrize(
    ("choice", "attr", "result"),
    [
        ("3", "promo_run", "promo"),
        ("4", "update_run", "update"),
        ("5", "copy_run", "copy"),
        ("6", "full_setup_run", "full"),
        ("7", "app_info_run", "app-info"),
        ("8", "iap_translate_run", "iap"),
        ("9", "subscription_translate_run", "subs"),
        ("10", "game_center_localizations_run", "gc"),
        ("11", "app_events_translate_run", "events"),
        ("12", "export_run", "export"),
        ("13", "manage_presets_run", "presets"),
    ],
)
def test_show_main_menu_dispatches_remaining_choices(monkeypatch, choice, attr, result):
    cli = _make_cli(choice)
    monkeypatch.setattr(main, attr, lambda _cli: result)
    assert main.TranslateRCLI.show_main_menu(cli) == result


def test_show_main_menu_dispatches_configuration():
    cli = _make_cli("14")
    assert main.TranslateRCLI.show_main_menu(cli) == "config"


def test_show_main_menu_exit_returns_false():
    cli = _make_cli("15")
    assert main.TranslateRCLI.show_main_menu(cli) is False


def test_show_main_menu_invalid_choice_returns_true():
    cli = _make_cli("bogus")
    assert main.TranslateRCLI.show_main_menu(cli) is True


def test_show_main_menu_non_tui_reads_input(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.ui = DummyUI(available=False, selected="")
    cli.configuration_mode = lambda: "config"
    monkeypatch.setattr(main, "promo_run", lambda _cli: "promo")
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "3")
    assert main.TranslateRCLI.show_main_menu(cli) == "promo"


def test_wrapper_modes_forward_to_workflows(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.ui = types.SimpleNamespace(prompt_app_id=lambda _asc: "app-1")
    cli.asc_client = object()
    monkeypatch.setattr(main, "translate_run", lambda _cli: "t")
    monkeypatch.setattr(main, "release_run", lambda _cli: "r")
    monkeypatch.setattr(main, "update_run", lambda _cli: "u")
    monkeypatch.setattr(main, "copy_run", lambda _cli: "c")
    monkeypatch.setattr(main, "full_setup_run", lambda _cli: "f")
    monkeypatch.setattr(main, "app_info_run", lambda _cli: "a")
    monkeypatch.setattr(main, "export_run", lambda _cli: "e")

    assert main.TranslateRCLI.prompt_app_id(cli) == "app-1"
    assert main.TranslateRCLI.translation_mode(cli) == "t"
    assert main.TranslateRCLI.release_mode(cli) == "r"
    assert main.TranslateRCLI.update_mode(cli) == "u"
    assert main.TranslateRCLI.copy_mode(cli) == "c"
    assert main.TranslateRCLI.full_setup_mode(cli) == "f"
    assert main.TranslateRCLI.app_name_subtitle_mode(cli) == "a"
    assert main.TranslateRCLI.export_localizations_mode(cli) == "e"


def test_main_entry_invokes_cli_run(monkeypatch):
    calls = []

    class DummyCLI:
        def run(self):
            calls.append("ran")

    monkeypatch.setattr(main, "TranslateRCLI", DummyCLI)
    main.main()

    assert calls == ["ran"]


def test_main_entry_keyboard_interrupt(monkeypatch):
    class DummyCLI:
        def __init__(self):
            pass

        def run(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(main, "TranslateRCLI", DummyCLI)
    main.main()


def test_main_entry_fatal_error_exits(monkeypatch):
    class DummyCLI:
        def __init__(self):
            pass

        def run(self):
            raise RuntimeError("fatal")

    exit_codes = []
    monkeypatch.setattr(main, "TranslateRCLI", DummyCLI)
    monkeypatch.setattr(main.sys, "exit", lambda code: exit_codes.append(code))
    main.main()
    assert exit_codes == [1]
