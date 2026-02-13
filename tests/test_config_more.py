import json

from config import ConfigManager


def test_sync_provider_catalog_handles_load_and_save_exceptions(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "providers.json").write_text("{invalid json", encoding="utf-8")
    (config_dir / "api_keys.json").write_text("{}", encoding="utf-8")
    (config_dir / "instructions.txt").write_text("x", encoding="utf-8")

    cfg = ConfigManager(config_dir=str(config_dir))

    providers_file = config_dir / "providers.json"
    providers_file.write_text(
        json.dumps(
            {
                "openai": {
                    "name": "OpenAI GPT",
                    "class": "OpenAIProvider",
                    "models": ["custom-model"],
                    "default_model": "not-in-list",
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cfg, "save_providers", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("readonly")))
    cfg._sync_provider_catalog()


def test_load_instructions_and_app_store_config_paths(tmp_path):
    cfg = ConfigManager(config_dir=str(tmp_path / "config"))
    assert isinstance(cfg.load_instructions(), str)

    keys = cfg.load_api_keys()
    keys["app_store_connect"]["key_id"] = "kid"
    keys["app_store_connect"]["issuer_id"] = "iss"
    cfg.save_api_keys(keys)
    assert cfg.get_app_store_config()["key_id"] == "kid"

    keys["app_store_connect"]["issuer_id"] = ""
    cfg.save_api_keys(keys)
    assert cfg.get_app_store_config() is None


def test_config_provider_model_accessors_and_failures(tmp_path, monkeypatch):
    cfg = ConfigManager(config_dir=str(tmp_path / "config"))
    providers = cfg.load_providers()
    providers["custom"] = {"models": ["m1"], "default_model": "m1"}
    cfg.save_providers(providers)

    assert cfg.get_ai_provider_key("openai") == ""
    assert cfg.list_provider_models("custom") == ["m1"]
    assert cfg.list_provider_models("missing") is None
    assert cfg.get_default_model("custom") == "m1"
    assert cfg.get_default_model("missing") is None
    assert cfg.set_default_model("missing", "m1") is False

    monkeypatch.setattr(cfg, "load_providers", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cfg.get_prompt_refinement() == ""
