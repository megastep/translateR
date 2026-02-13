import builtins

from workflows import game_center_localizations as gcl


def _setup_common_context(monkeypatch, fake_ui, fake_asc, kind):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(gcl, "_choose_resource_types", lambda _ui: [kind])
    monkeypatch.setattr(gcl, "_select_items", lambda _ui, items, _kind: items)
    monkeypatch.setattr(gcl, "_select_base_locale", lambda _ui, _locales, _recommended: "en-US")
    monkeypatch.setattr(gcl, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(gcl.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    fake_asc.set_response("get_game_center_detail", {"data": {"id": "detail1"}})
    fake_asc.set_response("get_game_center_group", {"data": None})
    fake_asc.set_response("get_latest_app_store_version", "ver-ios")
    fake_asc.set_response("get_app_store_version_localizations", {"data": [{"id": "loc-en", "attributes": {"locale": "en-US"}}]})


def _setup_achievement_resource(fake_asc):
    fake_asc.set_response(
        "get_game_center_achievements",
        {"data": [{"id": "ach1", "attributes": {"referenceName": "Ach One"}}]},
    )
    fake_asc.set_response(
        "get_game_center_achievement_localizations",
        {
            "data": [
                {
                    "id": "achloc-en",
                    "attributes": {
                        "locale": "en-US",
                        "name": "Achievement",
                        "beforeEarnedDescription": "Before",
                        "afterEarnedDescription": "After",
                    },
                }
            ]
        },
    )
    fake_asc.set_response("create_game_center_achievement_localization", {"data": {"id": "achloc-fr"}})


def _setup_leaderboard_resource(fake_asc):
    fake_asc.set_response(
        "get_game_center_leaderboards",
        {"data": [{"id": "lb1", "attributes": {"referenceName": "LB"}}]},
    )
    fake_asc.set_response(
        "get_game_center_leaderboard_localizations",
        {
            "data": [
                {
                    "id": "lbloc-en",
                    "attributes": {
                        "locale": "en-US",
                        "name": "Leaderboard",
                        "description": "Desc",
                        "formatterSuffix": "pts",
                        "formatterSuffixSingular": "pt",
                    },
                }
            ]
        },
    )
    fake_asc.set_response("create_game_center_leaderboard_localization", {"data": {"id": "lbloc-fr"}})


def _setup_activity_resource(fake_asc):
    fake_asc.set_response(
        "get_game_center_activities",
        {"data": [{"id": "act1", "attributes": {"referenceName": "Activity"}}]},
    )
    fake_asc.set_response(
        "get_game_center_activity_versions",
        {"data": [{"id": "ver1", "attributes": {"version": "1.0"}}]},
    )
    fake_asc.set_response(
        "get_game_center_activity_version_localizations",
        {"data": [{"id": "actloc-en", "attributes": {"locale": "en-US", "name": "Name", "description": "Desc"}}]},
    )
    fake_asc.set_response("create_game_center_activity_localization", {"data": {"id": "actloc-fr"}})


def _setup_achievement_run(monkeypatch, fake_ui, fake_asc):
    _setup_common_context(monkeypatch, fake_ui, fake_asc, kind="achievement")
    _setup_achievement_resource(fake_asc)


def _setup_leaderboard_run(monkeypatch, fake_ui, fake_asc):
    _setup_common_context(monkeypatch, fake_ui, fake_asc, kind="leaderboard")
    _setup_leaderboard_resource(fake_asc)


def _setup_activity_run(monkeypatch, fake_ui, fake_asc):
    _setup_common_context(monkeypatch, fake_ui, fake_asc, kind="activity")
    _setup_activity_resource(fake_asc)


def test_run_handles_missing_app_and_detail(fake_cli, fake_asc, fake_ui):
    fake_ui.app_id = None
    assert gcl.run(fake_cli) is True

    fake_ui.app_id = "app1"
    fake_asc.set_response("get_game_center_detail", {"data": None})
    assert gcl.run(fake_cli) is True

    fake_asc.set_response("get_game_center_detail", {"data": {"id": None}})
    assert gcl.run(fake_cli) is True


def test_run_no_resources_and_no_selected_items(fake_cli, fake_asc, fake_ui, monkeypatch):
    fake_ui.app_id = "app1"
    fake_asc.set_response("get_game_center_detail", {"data": {"id": "detail1"}})
    fake_asc.set_response("get_game_center_group", {"data": None})

    monkeypatch.setattr(gcl, "_choose_resource_types", lambda _ui: [])
    assert gcl.run(fake_cli) is True

    monkeypatch.setattr(gcl, "_choose_resource_types", lambda _ui: ["achievement"])
    fake_asc.set_response("get_game_center_achievements", {"data": [{"id": "ach1", "attributes": {"referenceName": "A"}}]})
    monkeypatch.setattr(gcl, "_select_items", lambda _ui, _items, _kind: [])
    assert gcl.run(fake_cli) is True


def test_run_returns_when_provider_not_selected(fake_cli, fake_asc, fake_ui, monkeypatch):
    _setup_achievement_run(monkeypatch, fake_ui, fake_asc)
    monkeypatch.setattr(gcl, "pick_provider", lambda _cli: (None, None))
    assert gcl.run(fake_cli) is True


def test_run_activity_skips_when_versions_or_localizations_missing(fake_cli, fake_asc, fake_ui, monkeypatch):
    _setup_activity_run(monkeypatch, fake_ui, fake_asc)
    fake_asc.set_response("get_game_center_activity_versions", {"data": []})
    assert gcl.run(fake_cli) is True

    _setup_activity_run(monkeypatch, fake_ui, fake_asc)
    fake_asc.set_response("get_game_center_activity_versions", {"data": [{"id": None, "attributes": {"version": "1.0"}}]})
    assert gcl.run(fake_cli) is True

    _setup_activity_run(monkeypatch, fake_ui, fake_asc)
    fake_asc.set_response("get_game_center_activity_version_localizations", {"data": []})
    assert gcl.run(fake_cli) is True


def test_run_download_failure_non_tui_abort_and_continue(fake_cli, fake_asc, fake_ui, monkeypatch):
    _setup_achievement_run(monkeypatch, fake_ui, fake_asc)
    fake_ui._tui = False
    monkeypatch.setattr(gcl, "_fetch_image_resource", lambda *_a, **_k: {"attributes": {"imageAsset": {"templateUrl": "https://cdn/{w}"}}})
    monkeypatch.setattr(gcl, "_download_origin_image", lambda *_a, **_k: (None, None, None, "download_failed", "boom"))

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "n")
    assert gcl.run(fake_cli) is True

    _setup_achievement_run(monkeypatch, fake_ui, fake_asc)
    fake_ui._tui = False
    monkeypatch.setattr(gcl, "_fetch_image_resource", lambda *_a, **_k: {"attributes": {"imageAsset": {"templateUrl": "https://cdn/{w}"}}})
    monkeypatch.setattr(gcl, "_download_origin_image", lambda *_a, **_k: (None, None, None, "download_failed", "boom"))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "y")
    assert gcl.run(fake_cli) is True


def test_run_leaderboard_parallel_error_and_empty_name(fake_cli, fake_asc, fake_ui, monkeypatch):
    _setup_leaderboard_run(monkeypatch, fake_ui, fake_asc)

    def fake_parallel(_locales, _task, **_kwargs):
        return {"fr-FR": {"name": "", "description": "", "formatterSuffix": "", "formatterSuffixSingular": ""}}, {"es-ES": "failed"}

    monkeypatch.setattr(gcl, "parallel_map_locales", fake_parallel)
    assert gcl.run(fake_cli) is True


def test_helpers_cover_selection_and_fetch_fallback_branches(monkeypatch):
    class UIYes:
        def available(self):
            return True

        def checkbox(self, *_a, **_k):
            return ["missing-id"]

        def select(self, *_a, **_k):
            return "fr-FR"

    assert gcl._select_items(UIYes(), [{"id": "i1", "attributes": {"referenceName": "One"}}], "achievement") == []
    assert gcl._select_base_locale(UIYes(), ["en-US", "fr-FR"], "en-US") == "fr-FR"

    class UINo:
        def available(self):
            return False

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "bad,1")
    assert gcl._select_items(UINo(), [{"id": "i1", "attributes": {"referenceName": "One"}}], "achievement") == []
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "x")
    assert gcl._select_base_locale(UINo(), ["en-US"], None) is None

    class ASC:
        def get_game_center_achievement_localization_image(self, _loc_id):
            raise RuntimeError("boom")

        def get_game_center_achievement_localization_image_linkage(self, _loc_id):
            return {"data": {"id": "img-a"}}

        def get_game_center_achievement_image(self, _img_id):
            return {"data": {"id": "img-a"}}

        def get_game_center_leaderboard_localization_image(self, _loc_id):
            raise RuntimeError("boom")

        def get_game_center_leaderboard_localization_image_linkage(self, _loc_id):
            return {"data": {"id": "img-l"}}

        def get_game_center_leaderboard_image(self, _img_id):
            return {"data": {"id": "img-l"}}

        def get_game_center_challenge_localization_image(self, _loc_id):
            raise RuntimeError("boom")

        def get_game_center_challenge_localization_image_linkage(self, _loc_id):
            return {"data": {"id": "img-c"}}

        def get_game_center_challenge_image(self, _img_id):
            return {"data": {"id": "img-c"}}

    asc = ASC()
    assert gcl._fetch_image_resource(asc, "achievement", "loc-a") == {"id": "img-a"}
    assert gcl._fetch_image_resource(asc, "leaderboard", "loc-l") == {"id": "img-l"}
    assert gcl._fetch_image_resource(asc, "challenge", "loc-c") == {"id": "img-c"}
