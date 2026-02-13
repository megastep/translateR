from workflows import app_events_translate as aet


class DummyResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_extract_and_validation_errors_from_exception():
    err = Exception("boom")
    err.response = DummyResp({"errors": [{"code": "ENTITY_ERROR.ATTRIBUTE.INVALID"}]})

    errors = aet._extract_asc_errors(err)
    assert errors and errors[0]["code"] == "ENTITY_ERROR.ATTRIBUTE.INVALID"
    assert aet._has_validation_error(err) is True


def test_ensure_min_len():
    assert aet._ensure_min_len("ab", 2) == "ab"
    assert aet._ensure_min_len("a", 2) == ""


def test_unique_root_and_existing_locale_match():
    loc_map = {"fi-FI": "id-fi", "fr-FR": "id-fr"}
    assert aet._unique_root_match(loc_map, "fi") == "id-fi"
    assert aet._find_existing_locale_id(loc_map, "fi") == "id-fi"
    assert aet._find_existing_locale_id({"en-US": "id1", "en-GB": "id2"}, "en") == ""
    assert aet._find_existing_locale_id({"en-US": "id1"}, "en-AU") == ""


def test_translate_with_min_len_retries_once(fake_provider):
    calls = {"n": 0}

    def translate(text, target_language, max_length=None, seed=None, refinement=None):
        calls["n"] += 1
        return "" if calls["n"] == 1 else "ok-value"

    fake_provider.translate = translate

    out = aet._translate_with_min_len(
        fake_provider,
        "src",
        "French",
        max_length=20,
        seed=123,
        refinement="",
        min_len=2,
        field_label="name",
    )

    assert out == "ok-value"
    assert calls["n"] == 2
