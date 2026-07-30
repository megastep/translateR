from collections import deque

import pytest

from translation_validation import (
    strip_emoji,
    translate_with_validation,
    validate_translation,
)


class SequenceProvider:
    def __init__(self, outputs):
        self.outputs = deque(outputs)
        self.calls = []

    def translate(self, text, target_language, **kwargs):
        self.calls.append((text, target_language, kwargs))
        return self.outputs.popleft()


def test_shared_translation_rewrites_overlong_target_text_with_tighter_limit():
    provider = SequenceProvider(["x" * 50, "Short translation"])

    result = translate_with_validation(
        provider,
        "Long English source",
        "French",
        max_length=45,
        seed=20,
        field_label="Promotional text",
    )

    assert result == "Short translation"
    assert provider.calls[0][0] == "Long English source"
    assert provider.calls[1][0] == "x" * 50
    assert [call[2]["max_length"] for call in provider.calls] == [41, 37]
    assert [call[2]["seed"] for call in provider.calls] == [20, 21]


def test_shared_translation_accepts_output_above_prompt_target_but_within_store_limit():
    provider = SequenceProvider(["x" * 43])

    result = translate_with_validation(
        provider,
        "Source",
        "Malayalam",
        max_length=45,
        seed=10,
        field_label="Subscription description",
        single_line=True,
    )

    assert result == "x" * 43
    assert provider.calls[0][2]["max_length"] == 41
    assert len(provider.calls) == 1


def test_shared_translation_preserves_multiline_content_when_allowed():
    provider = SequenceProvider(["Line one  \r\nLine two"])

    result = translate_with_validation(
        provider,
        "Source",
        "German",
        max_length=100,
        seed=None,
        field_label="What's New",
    )

    assert result == "Line one\nLine two"


def test_strip_emoji_removes_sequences_and_preserves_text_joiners():
    cleaned, removed = strip_emoji(
        "Ship it 🎉\nReady ✅ © 2026 മലയാളം\u200dവാചകം"
    )

    assert removed is True
    assert cleaned == "Ship it\nReady © 2026 മലയാളം\u200dവാചകം"


def test_shared_translation_retries_emoji_when_forbidden():
    provider = SequenceProvider(["Bonne nouvelle 🎉", "Bonne nouvelle"])

    result = translate_with_validation(
        provider,
        "Good news",
        "French",
        max_length=100,
        seed=20,
        field_label="What's New",
        forbid_emoji=True,
    )

    assert result == "Bonne nouvelle"
    assert len(provider.calls) == 2
    assert "no emoji" in provider.calls[0][2]["refinement"]


def test_shared_translation_enforces_minimum_and_maximum_lengths():
    with pytest.raises(ValueError, match="minimum is 2"):
        validate_translation(
            "x", field_label="Event name", max_length=30, min_length=2
        )
    with pytest.raises(ValueError, match="allowed maximum is 5"):
        validate_translation(
            "123456", field_label="App name", max_length=5
        )


def test_shared_translation_allows_comparisons_and_indic_joiners_but_rejects_markup():
    validate_translation(
        "value < 10 and value > 5",
        field_label="Description",
        max_length=100,
    )
    validate_translation(
        "മലയാളം\u200dവാചകം",
        field_label="Description",
        max_length=100,
    )

    with pytest.raises(ValueError, match="contains markup"):
        validate_translation(
            "Read <strong>this</strong>",
            field_label="Description",
            max_length=100,
        )
