from pathlib import Path

import utils


def test_truncate_keywords_normalizes_spaces_and_limit():
    assert utils.truncate_keywords("  a, b , c. ") == "a,b,c"
    assert utils.truncate_keywords("longword,another", max_length=8) == "longword"


def test_validate_and_get_field_limit():
    assert utils.get_field_limit("name") == 30
    assert utils.validate_field_length("x" * 30, "name") is True
    assert utils.validate_field_length("x" * 31, "name") is False
    assert utils.validate_field_length("anything", "unknown") is True


def test_app_store_locales_include_api_shortcode_for_slovenian():
    assert len(utils.APP_STORE_LOCALES) == 50
    assert "sl" not in utils.APP_STORE_LOCALES
    assert utils.APP_STORE_LOCALES["sl-SI"] == "Slovenian"
    assert utils.APP_STORE_LOCALES["bn-BD"] == "Bangla"
    assert utils.APP_STORE_LOCALES["gu-IN"] == "Gujarati"
    assert utils.APP_STORE_LOCALES["kn-IN"] == "Kannada"
    assert utils.APP_STORE_LOCALES["ml-IN"] == "Malayalam"
    assert utils.APP_STORE_LOCALES["mr-IN"] == "Marathi"
    assert utils.APP_STORE_LOCALES["or-IN"] == "Odia"
    assert utils.APP_STORE_LOCALES["pa-IN"] == "Punjabi"
    assert utils.APP_STORE_LOCALES["ta-IN"] == "Tamil"
    assert utils.APP_STORE_LOCALES["te-IN"] == "Telugu"
    assert utils.APP_STORE_LOCALES["ur-PK"] == "Urdu"
    assert "hi" in utils.APP_STORE_LOCALES


def test_detect_base_language_prefers_english(localization_payload):
    localizations = [
        localization_payload("fr-FR"),
        localization_payload("en-GB"),
        localization_payload("de-DE"),
    ]
    assert utils.detect_base_language(localizations) == "en-GB"


def test_build_and_parse_refinement_template_round_trip():
    template = utils.build_refinement_template("stay concise", "Line 1\nLine 2")
    clean, refine = utils.parse_refinement_template(template)
    assert clean == "Line 1\nLine 2"
    assert refine == "stay concise"


def test_parse_refinement_collects_extra_comment_guidance():
    text = "\n".join(
        [
            utils.REFINE_HEADER,
            "# PROMPT: clear tone",
            "# Keep product names untranslated",
            "",
            "Body",
        ]
    )
    clean, refine = utils.parse_refinement_template(text)
    assert clean == "Body"
    assert "clear tone" in refine
    assert "Keep product names untranslated" in refine


def test_parallel_map_locales_runs_all_tasks(monkeypatch):
    monkeypatch.setenv("TRANSLATER_CONCURRENCY", "2")

    def task(loc):
        if loc == "fr-FR":
            raise RuntimeError("boom")
        return loc.upper()

    results, errors = utils.parallel_map_locales(["en-US", "fr-FR", "de-DE", "en-US"], task, progress_action="Testing")

    assert results["en-US"] == "EN-US"
    assert results["de-DE"] == "DE-DE"
    assert "fr-FR" in errors


def test_export_existing_localizations_writes_file(tmp_path, monkeypatch, localization_payload):
    monkeypatch.chdir(tmp_path)
    locs = [localization_payload("en-US"), localization_payload("fr-FR", description="Bonjour")]

    output = utils.export_existing_localizations(locs, app_name="My App", app_id="123", version_string="1.2.3")

    out_path = Path(output)
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "App: My App" in content
    assert "French" in content
    assert "Bonjour" in content


def test_resolve_private_key_path_uses_explicit_and_default(tmp_path, monkeypatch):
    explicit = tmp_path / "AuthKey_ABC123.p8"
    explicit.write_text("secret", encoding="utf-8")
    assert utils.resolve_private_key_path("ABC123", str(explicit)) == explicit

    default_dir = tmp_path / "keys"
    default_dir.mkdir()
    monkeypatch.setattr(utils, "DEFAULT_APPSTORE_P8_DIR", default_dir)

    default_key = default_dir / "AuthKey_ZZZ999.p8"
    default_key.write_text("secret", encoding="utf-8")
    assert utils.resolve_private_key_path("ZZZ999", "") == default_key
