import builtins
import types

import main
from conftest import MainTestConfig, MainTestUI


def test_setup_ai_providers_handles_exceptions(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.config = types.SimpleNamespace(load_providers=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    main.TranslateRCLI.setup_ai_providers(cli)


def test_setup_wizard_existing_key_paths_and_validation(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.config = MainTestConfig()
    cli.setup_ai_providers = lambda: None
    cli.setup_app_store_client = lambda: True

    class _Dir:
        def exists(self):
            return True

        def glob(self, _pattern):
            class _P:
                def __init__(self, name):
                    self.name = name

                def __str__(self):
                    return f"/tmp/{self.name}"

            return [_P("AuthKey_ABC123.p8")]

        def __str__(self):
            return "/tmp"

    monkeypatch.setattr(main, "DEFAULT_APPSTORE_P8_DIR", _Dir())
    monkeypatch.setattr(main, "resolve_private_key_path", lambda key_id, configured_path=None: "/tmp/AuthKey_ABC123.p8")
    answers = iter(["1", "ISSUER", "y", "openai-key", "n", "n"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert main.TranslateRCLI.setup_wizard(cli) is True
    assert cli.config.saved["app_store_connect"]["key_id"] == "ABC123"

    answers = iter(["0", "", "", "ISSUER"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert main.TranslateRCLI.setup_wizard(cli) is False

    answers = iter(["0", "", "ABC", ""])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert main.TranslateRCLI.setup_wizard(cli) is False

    monkeypatch.setattr(main, "resolve_private_key_path", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("bad key path")))
    answers = iter(["0", "", "ABC", "ISSUER"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert main.TranslateRCLI.setup_wizard(cli) is False


def test_setup_wizard_default_provider_choice_branch(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.config = MainTestConfig()
    cli.setup_ai_providers = lambda: None
    cli.setup_app_store_client = lambda: True
    monkeypatch.setattr(main, "DEFAULT_APPSTORE_P8_DIR", types.SimpleNamespace(exists=lambda: False))
    monkeypatch.setattr(main, "resolve_private_key_path", lambda *_a, **_k: "/tmp/AuthKey_XYZ.p8")

    answers = iter([
        "", "KEY", "ISSUER",
        "y", "anth-key",
        "y", "open-key",
        "n",
        "y", "2",
    ])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert main.TranslateRCLI.setup_wizard(cli) is True

    answers = iter([
        "", "KEY", "ISSUER",
        "y", "anth-key",
        "y", "open-key",
        "n",
        "y", "x",
    ])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert main.TranslateRCLI.setup_wizard(cli) is True


def test_configuration_mode_models_non_tui_branches(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.ui = MainTestUI(available=False)
    cli.config = MainTestConfig()
    cli.asc_client = object()
    cli.ai_manager = types.SimpleNamespace(list_providers=lambda: ["openai"])
    cli.setup_ai_providers = lambda: None

    answers = iter(["3", "invalid-provider"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert main.TranslateRCLI.configuration_mode(cli) is True

    cli.config.models["openai"]["models"] = []
    answers = iter(["3", "openai"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert main.TranslateRCLI.configuration_mode(cli) is True

    cli.config.models["openai"]["models"] = ["o1", "o2"]
    answers = iter(["3", "openai", "x"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert main.TranslateRCLI.configuration_mode(cli) is True

    answers = iter(["3", "openai", "2"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert main.TranslateRCLI.configuration_mode(cli) is True
    assert cli.config.get_default_model("openai") == "o2"


def test_configuration_mode_models_tui_branches():
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.ui = MainTestUI(available=True, select_values=["models", None])
    cli.config = MainTestConfig()
    cli.asc_client = object()
    cli.ai_manager = types.SimpleNamespace(list_providers=lambda: ["openai"])
    cli.setup_ai_providers = lambda: None
    assert main.TranslateRCLI.configuration_mode(cli) is True

    cli.ui = MainTestUI(available=True, select_values=["models", "openai", None])
    assert main.TranslateRCLI.configuration_mode(cli) is True


def test_configuration_mode_keys_and_no_provider_branches(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.ui = MainTestUI(available=True, select_values=["keys"])
    cli.config = MainTestConfig()
    cli.asc_client = object()
    cli.ai_manager = types.SimpleNamespace(list_providers=lambda: ["openai"])
    cli.setup_wizard = lambda: True
    calls = {"n": 0}
    cli.setup_ai_providers = lambda: calls.__setitem__("n", calls["n"] + 1)
    assert main.TranslateRCLI.configuration_mode(cli) is True
    assert calls["n"] >= 1

    cli.ui = MainTestUI(available=False)
    cli.ai_manager = types.SimpleNamespace(list_providers=lambda: [])
    answers = iter(["2"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert main.TranslateRCLI.configuration_mode(cli) is True


def test_run_no_providers_then_setup_and_logo(capsys):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.show_logo = main.TranslateRCLI.show_logo.__get__(cli, main.TranslateRCLI)
    cli.setup_app_store_client = lambda: True
    states = {"calls": 0}

    def list_providers():
        states["calls"] += 1
        return [] if states["calls"] == 1 else ["openai"]

    cli.ai_manager = types.SimpleNamespace(list_providers=list_providers)
    cli.setup_wizard = lambda: True
    cli.show_main_menu = lambda: False
    main.TranslateRCLI.run(cli)
    out = capsys.readouterr().out
    assert "Localization Tool" in out
