import requests
import copy

from ai_providers import AIProviderManager, AnthropicProvider, OpenAIProvider


class DummyResponse:
    def __init__(self, status_code=200, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError("http", response=self)


def test_provider_manager_add_get_list():
    manager = AIProviderManager()
    provider = OpenAIProvider("key", "gpt-4.1")
    manager.add_provider("openai", provider)

    assert manager.get_provider("openai") is provider
    assert manager.list_providers() == ["openai"]


def test_openai_translate_retries_without_seed(monkeypatch):
    calls = {"n": 0, "payloads": []}

    def fake_post(_url, headers=None, json=None):
        calls["n"] += 1
        calls["payloads"].append(copy.deepcopy(json))
        if calls["n"] == 1:
            return DummyResponse(
                status_code=400,
                payload={"error": {"message": "seed is not supported"}},
                text='{"error":{"message":"seed is not supported"}}',
            )
        return DummyResponse(payload={"choices": [{"message": {"content": "Bonjour"}}]})

    monkeypatch.setattr("ai_providers.requests.post", fake_post)

    provider = OpenAIProvider("api-key", "gpt-4.1")
    out = provider.translate("Hello", "French", max_length=20, seed=42, refinement="be natural")

    assert out == "Bonjour"
    assert calls["n"] == 2
    assert "seed" in calls["payloads"][0]
    assert "seed" not in calls["payloads"][1]


def test_openai_translate_retries_when_too_long(monkeypatch):
    calls = {"n": 0}

    def fake_post(_url, headers=None, json=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return DummyResponse(payload={"choices": [{"message": {"content": "x" * 50}}]})
        return DummyResponse(payload={"choices": [{"message": {"content": "short"}}]})

    monkeypatch.setattr("ai_providers.requests.post", fake_post)

    provider = OpenAIProvider("api-key", "gpt-4.1")
    out = provider.translate("Hello", "German", max_length=10)

    assert out == "short"
    assert calls["n"] == 2


def test_anthropic_translate_formats_request_and_returns_text(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return DummyResponse(payload={"content": [{"text": "Salut"}]})

    monkeypatch.setattr("ai_providers.requests.post", fake_post)

    provider = AnthropicProvider("anthropic-key", "claude-sonnet-4-20250514")
    out = provider.translate("Hello", "French", max_length=20, is_keywords=True, seed=11)

    assert out == "Salut"
    assert captured["url"].endswith("/v1/messages")
    assert captured["headers"]["x-api-key"] == "anthropic-key"
    assert captured["json"]["metadata"]["seed"] == "11"
    assert "comma-separated" in captured["json"]["system"]
