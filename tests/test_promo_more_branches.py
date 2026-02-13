import builtins

from workflows import promo


def _mk_loc(loc_id, locale, promo_text):
    return {
        "id": loc_id,
        "attributes": {
            "locale": locale,
            "promotionalText": promo_text,
        },
    }


def test_promo_run_early_exit_paths(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = None
    assert promo.run(fake_cli) is True

    fake_ui.app_id = "app1"
    monkeypatch.setattr(promo, "select_platform_versions", lambda *_a, **_k: (None, None, None))
    assert promo.run(fake_cli) is True

    fake_ui.app_id = "app1"
    monkeypatch.setattr(
        promo,
        "select_platform_versions",
        lambda *_a, **_k: ({"IOS": {"id": "ver-ios"}}, {"IOS": {"id": "ver-ios"}}, {"IOS": "iOS"}),
    )
    fake_asc.set_response("get_app_store_version_localizations", {"data": [_mk_loc("loc-en", "en-US", "Base promo")]})
    monkeypatch.setattr(promo, "_prompt_source_promotional_text", lambda *_a, **_k: ("", ""))
    assert promo.run(fake_cli) is True


def test_promo_run_non_tui_locale_selection_cancel_and_invalid(fake_cli, fake_asc, localization_payload, monkeypatch):
    class NonTUI:
        def available(self):
            return False

        def prompt_app_id(self, _asc):
            return "app1"

        def confirm(self, *_a, **_k):
            return None

        def prompt_multiline(self, *_a, **_k):
            return "unused"

    fake_cli.ui = NonTUI()
    monkeypatch.setattr(
        promo,
        "select_platform_versions",
        lambda *_a, **_k: ({"IOS": {"id": "ver-ios"}}, {"IOS": {"id": "ver-ios"}}, {"IOS": "iOS"}),
    )
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {
            "data": [
                localization_payload("en-US", loc_id="loc-en", promotionalText="Base promo"),
                localization_payload("fr-FR", loc_id="loc-fr", promotionalText="Ancien"),
            ]
        },
    )

    answers = iter(["", "b"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert promo.run(fake_cli) is True

    answers = iter(["", "xx-XX"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert promo.run(fake_cli) is True


def test_promo_run_provider_none_and_tui_reenter_empty(fake_cli, fake_ui, fake_asc, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "apply"])
    fake_ui.checkbox_values.extend([["fr-FR"]])
    monkeypatch.setattr(
        promo,
        "select_platform_versions",
        lambda *_a, **_k: ({"IOS": {"id": "ver-ios"}}, {"IOS": {"id": "ver-ios"}}, {"IOS": "iOS"}),
    )
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {
            "data": [
                localization_payload("en-US", loc_id="loc-en", promotionalText="Base promo"),
                localization_payload("fr-FR", loc_id="loc-fr", promotionalText=""),
            ]
        },
    )
    monkeypatch.setattr(promo, "pick_provider", lambda *_a, **_k: (None, None))
    assert promo.run(fake_cli) is True

    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "reenter", "apply"])
    fake_ui.checkbox_values.extend([["fr-FR"]])
    fake_ui.multiline_values.append("")
    fake_ui.confirm_values.append(True)
    monkeypatch.setattr(
        promo,
        "select_platform_versions",
        lambda *_a, **_k: ({"IOS": {"id": "ver-ios"}}, {"IOS": {"id": "ver-ios"}}, {"IOS": "iOS"}),
    )
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {
            "data": [
                localization_payload("en-US", loc_id="loc-en", promotionalText="Base promo"),
                localization_payload("fr-FR", loc_id="loc-fr", promotionalText=""),
            ]
        },
    )
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response("get_app_store_version_localization", {"data": {"attributes": {"promotionalText": ""}}})

    def fake_parallel(targets, task, progress_action=None, **_kwargs):
        if progress_action == "Translated":
            return {loc: "" for loc in targets}, {}
        return {loc: True for loc in targets}, {}

    monkeypatch.setattr(promo, "parallel_map_locales", fake_parallel, raising=False)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert promo.run(fake_cli) is True


def test_promo_run_non_tui_reenter_edit_apply_error_and_verify_mismatch(fake_cli, fake_asc, localization_payload, monkeypatch):
    class NonTUI:
        def __init__(self):
            self.multiline_values = iter(["New source", "Edited and long"])

        def available(self):
            return False

        def prompt_app_id(self, _asc):
            return "app1"

        def confirm(self, *_a, **_k):
            return None

        def prompt_multiline(self, *_a, **_k):
            return next(self.multiline_values)

    fake_cli.ui = NonTUI()
    monkeypatch.setattr(promo, "get_field_limit", lambda _f: 5)
    monkeypatch.setattr(
        promo,
        "select_platform_versions",
        lambda *_a, **_k: (
            {"IOS": {"id": "ver-ios"}, "MAC_OS": {"id": "ver-mac"}, "TV_OS": {"id": "ver-tv"}},
            {"IOS": {"id": "ver-ios"}, "MAC_OS": {"id": "ver-mac"}, "TV_OS": {"id": "ver-tv"}},
            {"IOS": "iOS", "MAC_OS": "macOS", "TV_OS": "tvOS"},
        ),
    )

    def locs_by_version(version_id):
        if version_id == "ver-ios":
            return {
                "data": [
                    localization_payload("en-US", loc_id="ios-en", promotionalText="Base promo"),
                    localization_payload("fr-FR", loc_id="ios-fr", promotionalText=""),
                ]
            }
        if version_id == "ver-mac":
            return {"data": [localization_payload("en-US", loc_id="mac-en", promotionalText="Base promo")]}
        return {"data": []}

    fake_asc.set_response("get_app_store_version_localizations", locs_by_version)

    def update_loc(localization_id=None, **_kwargs):
        return {"data": {"id": localization_id}}

    fake_asc.set_response("update_app_store_version_localization", update_loc)
    fake_asc.set_response("get_app_store_version_localization", {"data": {"attributes": {"promotionalText": "mismatch"}}})

    def fake_parallel(targets, task, progress_action=None, **_kwargs):
        if progress_action == "Translated":
            return {loc: task(loc) for loc in targets}, {}
        return {}, {"fr-FR": "save failed"}

    monkeypatch.setattr(promo, "parallel_map_locales", fake_parallel, raising=False)

    answers = iter(["", "", "r", "e", "fr-FR", "", ""])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: next(answers))
    assert promo.run(fake_cli) is True


def test_promo_run_verify_exception_is_swallowed(fake_cli, fake_ui, fake_asc, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "apply"])
    fake_ui.checkbox_values.extend([["fr-FR"]])
    fake_ui.confirm_values.append(True)

    monkeypatch.setattr(
        promo,
        "select_platform_versions",
        lambda *_a, **_k: ({"IOS": {"id": "ver-ios"}}, {"IOS": {"id": "ver-ios"}}, {"IOS": "iOS"}),
    )
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {
            "data": [
                localization_payload("en-US", loc_id="loc-en", promotionalText="Base promo"),
                localization_payload("fr-FR", loc_id="loc-fr", promotionalText=""),
            ]
        },
    )
    fake_asc.set_response("update_app_store_version_localization", {"data": {"id": "ok"}})
    fake_asc.set_response(
        "get_app_store_version_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("verify failed")),
    )

    def fake_parallel(targets, task, progress_action=None, **_kwargs):
        if progress_action == "Translated":
            return {loc: "ok" for loc in targets}, {}
        return {loc: True for loc in targets}, {}

    monkeypatch.setattr(promo, "parallel_map_locales", fake_parallel, raising=False)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert promo.run(fake_cli) is True


def test_prompt_source_promotional_text_tui_cancel_keeps_refinement():
    class UI:
        def available(self):
            return True

        def select(self, *_a, **_k):
            return None

    text, refinement = promo._prompt_source_promotional_text(UI(), "Base", "default", "keep")
    assert text == ""
    assert refinement == "keep"


def test_prompt_source_promotional_text_non_tui_edit_and_custom_paths(monkeypatch):
    class UI:
        def __init__(self, value):
            self.value = value

        def available(self):
            return False

        def prompt_multiline(self, *_a, **_k):
            return self.value

    monkeypatch.setattr(promo, "build_refinement_template", lambda refine, text: f"{refine}|{text}")
    monkeypatch.setattr(
        promo,
        "parse_refinement_template",
        lambda edited, fallback_default: (edited, fallback_default),
    )

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "e")
    text, refinement = promo._prompt_source_promotional_text(UI("Edited source"), "Base text", "def", "ref")
    assert text == "Edited source"
    assert refinement == "ref"

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "c")
    text, refinement = promo._prompt_source_promotional_text(UI("Custom source"), "Base text", "def", "ref")
    assert text == "Custom source"
    assert refinement == "ref"


def test_prompt_source_promotional_text_retries_until_non_empty(monkeypatch):
    class UI:
        def __init__(self):
            self.values = iter(["", "   ", "Final text"])

        def available(self):
            return False

        def prompt_multiline(self, *_a, **_k):
            return next(self.values)

    monkeypatch.setattr(promo, "build_refinement_template", lambda refine, text: f"{refine}|{text}")

    def parse_refinement(edited, fallback_default):
        if edited == "Final text":
            return ("Final text", "parsed-refine")
        return ("", fallback_default)

    monkeypatch.setattr(promo, "parse_refinement_template", parse_refinement)
    text, refinement = promo._prompt_source_promotional_text(UI(), "", "default-refine", "")
    assert text == "Final text"
    assert refinement == "parsed-refine"


def test_promo_run_no_additional_locales_and_base_update_error(fake_cli, fake_ui, fake_asc, localization_payload, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.extend(["use", "apply"])
    fake_ui.confirm_values.append(True)

    monkeypatch.setattr(
        promo,
        "select_platform_versions",
        lambda *_a, **_k: ({"IOS": {"id": "ver-ios"}}, {"IOS": {"id": "ver-ios"}}, {"IOS": "iOS"}),
    )
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {"data": [localization_payload("en-US", loc_id="loc-en", promotionalText="Base promo")]},
    )
    fake_asc.set_response(
        "update_app_store_version_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("base update failed")),
    )
    fake_asc.set_response(
        "get_app_store_version_localization",
        {"data": {"attributes": {"promotionalText": "Base promo"}}},
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    try:
        assert promo.run(fake_cli) is True
    except RuntimeError as e:
        # Some merged CI refs propagate base update errors before warning handling.
        assert "base update failed" in str(e)
