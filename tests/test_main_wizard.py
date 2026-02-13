import builtins
import types

import main


class WizardConfig:
    def __init__(self):
        self.saved = None
        self.default_provider = None

    def load_api_keys(self):
        return {
            "app_store_connect": {"key_id": "", "issuer_id": "", "private_key_path": ""},
            "ai_providers": {"anthropic": "", "openai": "", "google": ""},
        }

    def save_api_keys(self, payload):
        self.saved = payload

    def set_default_ai_provider(self, provider):
        self.default_provider = provider


def test_setup_wizard_success_single_provider(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cfg = WizardConfig()
    cli.config = cfg

    called = {"setup_ai": 0, "setup_asc": 0}
    cli.setup_ai_providers = lambda: called.__setitem__("setup_ai", called["setup_ai"] + 1)
    cli.setup_app_store_client = lambda: called.__setitem__("setup_asc", called["setup_asc"] + 1) or True

    monkeypatch.setattr(main, "DEFAULT_APPSTORE_P8_DIR", types.SimpleNamespace(exists=lambda: False))
    monkeypatch.setattr(main, "resolve_private_key_path", lambda key_id, configured_path=None: "/tmp/AuthKey_X.p8")

    answers = iter([
        "",         # key path
        "ABC123",   # key id
        "ISSUER",   # issuer
        "y",        # anthropic yes
        "anth-key", # anthropic key
        "n",        # openai no
        "n",        # google no
    ])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))

    assert main.TranslateRCLI.setup_wizard(cli) is True
    assert cfg.saved["app_store_connect"]["key_id"] == "ABC123"
    assert cfg.saved["ai_providers"]["anthropic"] == "anth-key"
    assert called["setup_ai"] == 1
    assert called["setup_asc"] == 1


def test_setup_wizard_fails_when_no_ai_provider(monkeypatch):
    cli = main.TranslateRCLI.__new__(main.TranslateRCLI)
    cfg = WizardConfig()
    cli.config = cfg
    cli.setup_ai_providers = lambda: None
    cli.setup_app_store_client = lambda: True

    monkeypatch.setattr(main, "DEFAULT_APPSTORE_P8_DIR", types.SimpleNamespace(exists=lambda: False))
    monkeypatch.setattr(main, "resolve_private_key_path", lambda key_id, configured_path=None: "/tmp/AuthKey_X.p8")

    answers = iter([
        "",         # key path
        "ABC123",   # key id
        "ISSUER",   # issuer
        "n",        # anthropic no
        "n",        # openai no
        "n",        # google no
    ])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))

    assert main.TranslateRCLI.setup_wizard(cli) is False
