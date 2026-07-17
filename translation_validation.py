"""Shared validated translation and shortening retries for every workflow."""

import re
import unicodedata
from typing import Optional


MAX_TRANSLATION_ATTEMPTS = 4


def clean_translation(value: str, *, single_line: bool) -> str:
    """Normalize harmless model formatting without truncating translated text."""
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1].strip()
    if single_line:
        return " ".join(value.split())
    lines = [line.rstrip() for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def validate_translation(
    value: str,
    *,
    field_label: str,
    max_length: Optional[int],
    min_length: int = 1,
    single_line: bool = False,
) -> None:
    """Reject empty, malformed, or out-of-range text before it reaches a store API."""
    if len(value) < min_length:
        raise ValueError(
            f"{field_label} translation is {len(value)} characters; minimum is {min_length}"
        )
    if max_length is not None and len(value) > max_length:
        raise ValueError(
            f"{field_label} translation is {len(value)} characters; allowed maximum is {max_length}"
        )
    allowed_controls = {"\n", "\t"} if not single_line else set()
    allowed_format_chars = {"\u200c", "\u200d"}  # ZWNJ and ZWJ are meaningful in Indic scripts.
    if any(
        char not in allowed_controls
        and (
            unicodedata.category(char) in ("Cc", "Cs")
            or (
                unicodedata.category(char) == "Cf"
                and char not in allowed_format_chars
            )
        )
        for char in value
    ):
        raise ValueError(f"{field_label} translation contains a control or invisible character")
    if re.search(r"</?[a-zA-Z][^>]*>", value):
        raise ValueError(f"{field_label} translation contains markup")


def translate_with_validation(
    provider,
    text: str,
    language_name: str,
    *,
    max_length: Optional[int],
    seed,
    refinement: str = "",
    field_label: str = "App Store metadata field",
    is_keywords: bool = False,
    min_length: int = 1,
    single_line: bool = False,
    forbid_emoji: bool = False,
    submission_retry: bool = False,
) -> str:
    """Translate, validate, and rewrite overlong output with progressively stricter targets."""
    step = max(2, min(4, round((max_length or 25) * 0.08)))
    last_error = None
    retry_source = None

    for attempt in range(MAX_TRANSLATION_ATTEMPTS):
        requested_limit = None
        if max_length is not None:
            requested_limit = max(1, max_length - step * (attempt + 1))
        retry_context = " App Store Connect rejected an earlier version." if submission_retry else ""
        if retry_source is None:
            task_instruction = (
                f"Translate the supplied source into {language_name}. Preserve the core customer-facing meaning."
            )
            input_text = text
        else:
            task_instruction = (
                f"The supplied text is already a {language_name} translation and is "
                f"{len(retry_source)} characters long. DO NOT translate from the original source again. "
                f"Rewrite this existing translation to satisfy the output contract. Remove nonessential "
                f"wording and compress phrasing while preserving the core meaning."
            )
            input_text = retry_source

        format_instruction = (
            "Return ONLY the final text on one line"
            if single_line
            else "Return ONLY the final translated text and preserve meaningful line breaks"
        )
        limit_instruction = ""
        if requested_limit is not None:
            limit_instruction = (
                f" The answer is INVALID if it exceeds {requested_limit} characters, counting every "
                f"space, line break, and punctuation mark. Count characters before answering."
            )
        abbreviation_instruction = (
            f" You may use a standard, natural abbreviation commonly understood in {language_name} "
            f"when it preserves the core meaning; do not invent abbreviations."
        )
        emoji_instruction = " no emoji," if forbid_emoji else ""
        strict_guidance = (
            f"MANDATORY OUTPUT CONTRACT — {field_label}.{retry_context} {task_instruction} "
            f"{format_instruction}: no label, explanation, quotes, markup,{emoji_instruction} or invisible "
            f"characters.{limit_instruction}{abbreviation_instruction} If necessary, omit secondary marketing "
            f"wording rather than exceeding the limit or cutting a word in half. Preserve brand names, URLs, "
            f"numbers, and placeholders such as {{var}}, %d, and %@. Minimum output length is {min_length}. "
            f"This is validation attempt {attempt + 1} of {MAX_TRANSLATION_ATTEMPTS}."
        )
        guidance = " ".join(part for part in (refinement, strict_guidance) if part)
        attempt_seed = seed + attempt if isinstance(seed, int) else seed
        translate_kwargs = {
            "max_length": requested_limit,
            "seed": attempt_seed,
            "refinement": guidance,
        }
        if is_keywords:
            translate_kwargs["is_keywords"] = True
        translated = provider.translate(input_text, language_name, **translate_kwargs)
        translated = clean_translation(translated, single_line=single_line)
        try:
            validate_translation(
                translated,
                field_label=field_label,
                # The shrinking requested limit is prompt headroom. Accept anything
                # within the real store limit instead of rejecting a valid result.
                max_length=max_length,
                min_length=min_length,
                single_line=single_line,
            )
            return translated
        except ValueError as error:
            last_error = error
            if translated:
                retry_source = translated

    limit_suffix = f"; store limit is {max_length}" if max_length is not None else ""
    raise ValueError(
        f"{last_error}{limit_suffix}; provider failed {MAX_TRANSLATION_ATTEMPTS} progressively stricter attempts"
    )
