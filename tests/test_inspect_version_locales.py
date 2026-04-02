import inspect_version_locales as ivl


def test_build_locale_rows_sorts_and_labels_known_locales():
    response = {
        "data": [
            {"id": "2", "attributes": {"locale": "sl-SI"}},
            {"id": "1", "attributes": {"locale": "en-US"}},
            {"id": "3", "attributes": {"locale": "xx-YY"}},
        ]
    }

    rows = ivl.build_locale_rows(response)

    assert [row["locale"] for row in rows] == ["en-US", "sl-SI", "xx-YY"]
    assert rows[0]["name"] == "English (U.S.)"
    assert rows[1]["name"] == "Slovenian"
    assert rows[2]["name"] == "<unknown>"


def test_build_locale_rows_skips_null_attributes():
    response = {
        "data": [
            {"id": "1", "attributes": None},
            {"id": "2", "attributes": {"locale": "en-US"}},
        ]
    }

    rows = ivl.build_locale_rows(response)

    assert rows == [{"locale": "en-US", "name": "English (U.S.)", "id": "2"}]


def test_format_locale_rows_emits_readable_table():
    rows = [
        {"locale": "en-US", "name": "English (U.S.)", "id": "loc-1"},
        {"locale": "sl-SI", "name": "Slovenian", "id": "loc-2"},
    ]

    output = ivl.format_locale_rows(rows)

    assert "Locale" in output
    assert "Name" in output
    assert "ID" in output
    assert "en-US" in output
    assert "sl-SI" in output
    assert "loc-2" in output


def test_resolve_target_version_id_prefers_explicit_version_id():
    class _Client:
        def get_latest_app_store_version(self, _app_id):
            raise AssertionError("should not fetch latest when version id is explicit")

    version_id = ivl.resolve_target_version_id(_Client(), app_id="app-1", version_id="ver-1")
    assert version_id == "ver-1"


def test_resolve_target_version_id_fetches_latest_from_app_id():
    class _Client:
        def get_latest_app_store_version(self, app_id):
            assert app_id == "app-1"
            return "ver-latest"

    version_id = ivl.resolve_target_version_id(_Client(), app_id="app-1", version_id=None)
    assert version_id == "ver-latest"
