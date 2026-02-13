from pathlib import Path

import ai_logger


def test_ai_logger_logs_request_response_and_retry(tmp_path):
    logger = ai_logger.AILogger(log_dir=str(tmp_path))
    logger.log_request(
        provider="openai",
        model="gpt-test",
        text="hello",
        target_language="French",
        max_length=20,
        is_keywords=True,
        seed=123,
        refinement="keep concise",
    )
    logger.log_response("openai", "bonjour", success=True)
    logger.log_response("openai", "", success=False, error="bad request")
    logger.log_character_limit_retry("openai", original_length=100, max_length=20)

    content = Path(logger.get_log_file_path()).read_text(encoding="utf-8")
    assert "REQUEST" in content
    assert "RESPONSE - SUCCESS" in content
    assert "RESPONSE - ERROR" in content
    assert "CHARACTER LIMIT RETRY" in content


def test_ai_logger_log_error_uses_string_fallback_on_non_serializable_details(tmp_path):
    logger = ai_logger.AILogger(log_dir=str(tmp_path))
    details = {"broken": {1, 2, 3}}
    logger.log_error("openai", "message", details=details)
    content = Path(logger.get_log_file_path()).read_text(encoding="utf-8")
    assert "ERROR" in content
    assert "broken" in content


def test_ai_logger_log_http_error_redacts_and_truncates(tmp_path):
    logger = ai_logger.AILogger(log_dir=str(tmp_path))
    long_excerpt = "x" * 2500
    logger.log_http_error(
        provider="openai",
        endpoint="/v1/responses",
        status_code=429,
        request_id="req-1",
        error_code="rate_limit",
        error_type="too_many_requests",
        response_excerpt=long_excerpt,
        duration_ms=123,
        model="gpt-test",
        headers_excerpt={"Authorization": "secret", "X-Test": "ok"},
    )

    content = Path(logger.get_log_file_path()).read_text(encoding="utf-8")
    assert "<redacted>" in content
    assert "[...truncated...]" in content
    assert "X-Test" in content


def test_ai_logger_log_http_error_header_sanitization_exception(tmp_path):
    class BadStr:
        def __str__(self):
            raise RuntimeError("cannot stringify")

    logger = ai_logger.AILogger(log_dir=str(tmp_path))
    logger.log_http_error(
        provider="openai",
        endpoint="/v1/responses",
        status_code=500,
        headers_excerpt={BadStr(): "value"},
    )
    content = Path(logger.get_log_file_path()).read_text(encoding="utf-8")
    assert "HTTP ERROR" in content
    assert "Headers:" in content


def test_ai_logger_singleton_and_convenience_wrappers(tmp_path, monkeypatch):
    original_cls = ai_logger.AILogger
    monkeypatch.setattr(ai_logger, "_logger_instance", None)
    monkeypatch.setattr(ai_logger, "AILogger", lambda: original_cls(log_dir=str(tmp_path)))

    first = ai_logger.get_ai_logger()
    second = ai_logger.get_ai_logger()
    assert first is second

    ai_logger.log_ai_request("openai", "gpt-test", "hello", "French")
    ai_logger.log_ai_response("openai", "bonjour", success=True)
    ai_logger.log_character_limit_retry("openai", 80, 20)
    ai_logger.log_ai_error("openai", "oops", details={"a": 1})
    ai_logger.log_ai_http_error("openai", "/v1/responses", 500, headers_excerpt={"api-key": "x"})

    content = Path(first.get_log_file_path()).read_text(encoding="utf-8")
    assert "REQUEST" in content
    assert "RESPONSE - SUCCESS" in content
    assert "ERROR" in content
