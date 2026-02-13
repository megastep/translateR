import builtins
import types
from pathlib import Path

import main


def test_setup_app_store_client_success(monkeypatch, tmp_path):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    key_file = tmp_path / "AuthKey_TEST.p8"
    key_file.write_text("private-key", encoding="utf-8")

    cli.config = types.SimpleNamespace(
        get_app_store_config=lambda: {"key_id": "KID", "issuer_id": "ISS", "private_key_path": str(key_file)}
    )
    cli.setup_wizard = lambda: False

    class DummyASC:
        def __init__(self, key_id, issuer_id, private_key):
            self.key_id = key_id
            self.issuer_id = issuer_id
            self.private_key = private_key

        def get_apps(self):
            return {"data": []}

    monkeypatch.setattr(main, "AppStoreConnectClient", DummyASC)
    monkeypatch.setattr(main, "resolve_private_key_path", lambda key_id, configured_path=None: Path(configured_path))

    assert main.TranslateRCLI.setup_app_store_client(cli) is True
    assert cli.asc_client.key_id == "KID"


def test_setup_app_store_client_missing_config_runs_wizard(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.config = types.SimpleNamespace(get_app_store_config=lambda: None)
    cli.setup_wizard = lambda: "wizard-called"

    out = main.TranslateRCLI.setup_app_store_client(cli)
    assert out == "wizard-called"


def test_setup_app_store_client_failure_runs_wizard(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.config = types.SimpleNamespace(
        get_app_store_config=lambda: {"key_id": "KID", "issuer_id": "ISS", "private_key_path": "/bad/path"}
    )
    cli.setup_wizard = lambda: "wizard-called"

    monkeypatch.setattr(main, "resolve_private_key_path", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("missing")))

    out = main.TranslateRCLI.setup_app_store_client(cli)
    assert out == "wizard-called"


def test_run_handles_keyboard_interrupt(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.show_logo = lambda: None
    cli.setup_app_store_client = lambda: True
    cli.ai_manager = types.SimpleNamespace(list_providers=lambda: ["openai"])

    def boom():
        raise KeyboardInterrupt

    cli.show_main_menu = boom
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert main.TranslateRCLI.run(cli) is None


def test_run_handles_runtime_error_then_continues(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cli.show_logo = lambda: None
    cli.setup_app_store_client = lambda: True
    cli.ai_manager = types.SimpleNamespace(list_providers=lambda: ["openai"])
    calls = {"n": 0}

    def menu():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return False

    cli.show_main_menu = menu
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert main.TranslateRCLI.run(cli) is None
