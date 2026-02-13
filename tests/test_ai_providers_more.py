import copy

from ai_providers import AIProvider, AnthropicProvider, GoogleGeminiProvider, OpenAIProvider

from conftest import DummyResponse


def test_ai_provider_abstract_method_bodies_are_reachable():
    class MinimalProvider(AIProvider):
        def translate(self, *args, **kwargs):
            return super().translate(*args, **kwargs)

        def get_name(self):
            return super().get_name()

    provider = MinimalProvider()
    assert provider.translate("a", "b") is None
    assert provider.get_name() is None


def test_provider_get_name_methods():
    assert AnthropicProvider("k", "m").get_name() == "Anthropic Claude"
    assert OpenAIProvider("k", "m").get_name() == "OpenAI GPT"
    assert GoogleGeminiProvider("k", "m").get_name() == "Google Gemini"


def test_anthropic_retries_after_character_limit(monkeypatch):
    calls = {"n": 0, "payloads": []}

    def fake_post(_url, headers=None, json=None):
        calls["n"] += 1
        calls["payloads"].append(copy.deepcopy(json))
        if calls["n"] == 1:
            return DummyResponse(payload={"content": [{"text": "x" * 50}]})
        return DummyResponse(payload={"content": [{"text": "short"}]})

    monkeypatch.setattr("ai_providers.requests.post", fake_post)

    provider = AnthropicProvider("api-key", "claude-sonnet-4-20250514")
    out = provider.translate("hello", "French", max_length=10, refinement="tone")

    assert out == "short"
    assert calls["n"] == 2
    assert "Additional guidance: tone" in calls["payloads"][0]["system"]


def test_openai_http_error_when_error_body_not_json(monkeypatch):
    def fake_post(_url, headers=None, json=None):
        return DummyResponse(status_code=500, payload={}, text="internal", json_exc=ValueError("bad json"))

    monkeypatch.setattr("ai_providers.requests.post", fake_post)
    provider = OpenAIProvider("api-key", "gpt-4.1")

    try:
        provider.translate("hi", "French", seed=9)
        assert False, "expected exception"
    except Exception as e:
        assert "OpenAI API error 500" in str(e)


def test_openai_unexpected_payload_shape_is_wrapped(monkeypatch):
    monkeypatch.setattr("ai_providers.requests.post", lambda *_a, **_k: DummyResponse(payload={}))
    provider = OpenAIProvider("api-key", "gpt-4.1")

    try:
        provider.translate("hi", "French")
        assert False, "expected exception"
    except Exception as e:
        assert "OpenAI translation failed" in str(e)


def test_google_seed_cast_failure_and_keyword_refinement(monkeypatch):
    captured = {}

    def fake_post(_url, headers=None, json=None):
        captured["json"] = copy.deepcopy(json)
        return DummyResponse(payload={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

    monkeypatch.setattr("ai_providers.requests.post", fake_post)
    provider = GoogleGeminiProvider("key", "gemini-2.5-flash")

    out = provider.translate("hello", "German", is_keywords=True, refinement="short and formal", seed="not-an-int")
    assert out == "ok"
    prompt = captured["json"]["contents"][0]["parts"][0]["text"]
    assert "comma-separated list" in prompt
    assert "Additional guidance: short and formal" in prompt
    assert "seed" not in captured["json"]["generationConfig"]


def test_google_http_error_without_seed_retry(monkeypatch):
    monkeypatch.setattr(
        "ai_providers.requests.post",
        lambda *_a, **_k: DummyResponse(status_code=400, payload={"error": {"status": "INVALID_ARGUMENT", "code": 400, "message": "bad request"}}, text="bad request"),
    )
    provider = GoogleGeminiProvider("key", "gemini-2.5-flash")

    try:
        provider.translate("hello", "French")
        assert False, "expected exception"
    except Exception as e:
        assert "Google Gemini API error 400" in str(e)


def test_google_unexpected_payload_shape_is_wrapped(monkeypatch):
    monkeypatch.setattr("ai_providers.requests.post", lambda *_a, **_k: DummyResponse(payload={}))
    provider = GoogleGeminiProvider("key", "gemini-2.5-flash")

    try:
        provider.translate("hello", "French")
        assert False, "expected exception"
    except Exception as e:
        assert "Google Gemini translation failed" in str(e)
