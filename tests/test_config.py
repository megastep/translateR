import json

from config import ConfigManager


def test_config_manager_creates_default_files(tmp_path):
    cfg = ConfigManager(config_dir=str(tmp_path / "config"))

    assert cfg.providers_file.exists()
    assert cfg.api_keys_file.exists()
    assert cfg.instructions_file.exists()

    providers = cfg.load_providers()
    assert "openai" in providers
    assert providers["openai"]["default_model"]


def test_get_ai_provider_key_prefers_environment(tmp_path, monkeypatch):
    cfg = ConfigManager(config_dir=str(tmp_path / "config"))
    keys = cfg.load_api_keys()
    keys["ai_providers"]["openai"] = "from-config"
    cfg.save_api_keys(keys)

    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    assert cfg.get_ai_provider_key("openai") == "from-env"


def test_default_provider_and_refinement_round_trip(tmp_path):
    cfg = ConfigManager(config_dir=str(tmp_path / "config"))
    cfg.set_default_ai_provider("openai")
    cfg.set_prompt_refinement("keep product names")

    assert cfg.get_default_ai_provider() == "openai"
    assert cfg.get_prompt_refinement() == "keep product names"


def test_set_default_model_validates_model_membership(tmp_path):
    cfg = ConfigManager(config_dir=str(tmp_path / "config"))
    providers = cfg.load_providers()
    openai_models = providers["openai"]["models"]

    assert "gpt-5.4" in openai_models
    assert "gpt-5.4-mini" in openai_models
    assert "gpt-5.4-nano" in openai_models
    assert cfg.set_default_model("openai", openai_models[0]) is True
    assert cfg.set_default_model("openai", "non-existent-model") is False


def test_sync_provider_catalog_recovers_missing_sections(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    providers_file = config_dir / "providers.json"
    providers_file.write_text(json.dumps({"openai": {"name": "OpenAI GPT", "class": "OpenAIProvider", "models": ["gpt-4.1"], "default_model": "bad-model"}}), encoding="utf-8")

    cfg = ConfigManager(config_dir=str(config_dir))
    providers = cfg.load_providers()

    assert "anthropic" in providers
    assert providers["openai"]["default_model"] in providers["openai"]["models"]
