import copy

from ai_providers import AnthropicProvider, GoogleGeminiProvider, OpenAIProvider

from conftest import DummyResponse


def test_google_translate_retries_without_seed(monkeypatch):
    calls = {"n": 0, "payloads": []}

    def fake_post(_url, headers=None, json=None, **_kwargs):
        calls["n"] += 1
        calls["payloads"].append(copy.deepcopy(json))
        if calls["n"] == 1:
            return DummyResponse(status_code=400, payload={"error": {"message": "seed unsupported", "code": 400, "status": "INVALID_ARGUMENT"}}, text="seed unsupported")
        return DummyResponse(payload={"candidates": [{"content": {"parts": [{"text": "Bonjour"}]}}]})

    monkeypatch.setattr("ai_providers.requests.post", fake_post)

    provider = GoogleGeminiProvider("key", "gemini-2.5-flash")
    out = provider.translate("Hello", "French", seed=12)

    assert out == "Bonjour"
    assert calls["n"] == 2
    assert "seed" in calls["payloads"][0]["generationConfig"]
    assert "seed" not in calls["payloads"][1]["generationConfig"]


def test_google_translate_retries_when_too_long(monkeypatch):
    calls = {"n": 0}

    def fake_post(_url, headers=None, json=None, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return DummyResponse(payload={"candidates": [{"content": {"parts": [{"text": "x" * 50}]}}]})
        return DummyResponse(payload={"candidates": [{"content": {"parts": [{"text": "short"}]}}]})

    monkeypatch.setattr("ai_providers.requests.post", fake_post)

    provider = GoogleGeminiProvider("key", "gemini-2.5-flash")
    out = provider.translate("Hello", "German", max_length=10)

    assert out == "short"
    assert calls["n"] == 2


def test_google_translate_max_tokens_finish_reason_raises(monkeypatch):
    monkeypatch.setattr(
        "ai_providers.requests.post",
        lambda *_a, **_k: DummyResponse(payload={"candidates": [{"finishReason": "MAX_TOKENS"}]})
    )

    provider = GoogleGeminiProvider("key", "gemini-2.5-flash")
    try:
        provider.translate("Hello", "French")
        assert False, "expected exception"
    except Exception as e:
        assert "Google Gemini translation failed" in str(e)


def test_openai_gpt5_uses_max_completion_tokens(monkeypatch):
    captured = {}

    def fake_post(_url, headers=None, json=None, **_kwargs):
        captured["json"] = copy.deepcopy(json)
        return DummyResponse(payload={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr("ai_providers.requests.post", fake_post)
    provider = OpenAIProvider("key", "gpt-5.2")
    out = provider.translate("hello", "French")

    assert out == "ok"
    assert "max_completion_tokens" in captured["json"]


def test_openai_supports_service_tier_flex(monkeypatch):
    captured = {}

    def fake_post(_url, headers=None, json=None, **_kwargs):
        captured["json"] = copy.deepcopy(json)
        captured["timeout"] = _kwargs.get("timeout")
        return DummyResponse(payload={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr("ai_providers.requests.post", fake_post)
    provider = OpenAIProvider("key", "gpt-4.1", service_tier="flex")
    out = provider.translate("hello", "French")

    assert out == "ok"
    assert captured["json"]["service_tier"] == "flex"
    assert captured["timeout"] == (10, 120)


def test_openai_non_flex_timeout_is_lower_by_default(monkeypatch):
    captured = {}

    def fake_post(_url, headers=None, json=None, **_kwargs):
        captured["timeout"] = _kwargs.get("timeout")
        return DummyResponse(payload={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr("ai_providers.requests.post", fake_post)
    provider = OpenAIProvider("key", "gpt-4.1")  # no tier
    out = provider.translate("hello", "French")

    assert out == "ok"
    assert captured["timeout"] == (10, 30)


def test_anthropic_http_error_bubbles_as_wrapped_exception(monkeypatch):
    def fake_post(_url, headers=None, json=None, **_kwargs):
        return DummyResponse(status_code=401, payload={"error": {"type": "auth_error", "message": "bad key"}}, text="bad key")

    monkeypatch.setattr("ai_providers.requests.post", fake_post)
    provider = AnthropicProvider("bad", "claude-sonnet-4-20250514")

    try:
        provider.translate("hi", "French")
        assert False, "expected exception"
    except Exception as e:
        assert "Anthropic API error 401" in str(e)
