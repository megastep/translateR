import builtins
import types

import pytest

from workflows import game_center_localizations as gcl


def test_choose_resource_types_tui_and_non_tui_empty(monkeypatch):
    class TUI:
        def available(self):
            return True

        def checkbox(self, *_args, **_kwargs):
            return ["activity", "challenge"]

    assert gcl._choose_resource_types(TUI()) == ["activity", "challenge"]

    class NonTUI:
        def available(self):
            return False

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert gcl._choose_resource_types(NonTUI()) == []

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1,3,4")
    assert gcl._choose_resource_types(NonTUI()) == ["achievement", "activity", "challenge"]


def test_label_item_challenge_activity_and_latest_version_edges():
    challenge = {"id": "c1", "attributes": {"referenceName": "Challenge", "challengeType": "MULTIPLAYER"}}
    activity = {"id": "a1", "attributes": {"referenceName": "Activity", "playStyle": "TURN_BASED"}}
    assert "MULTIPLAYER" in gcl._label_item(challenge, "challenge")
    assert "TURN_BASED" in gcl._label_item(activity, "activity")

    assert gcl._pick_latest_version([]) is None
    latest = gcl._pick_latest_version(
        [
            {"id": "v1", "attributes": {"version": "beta"}},
            {"id": "v2", "attributes": {"version": "alpha"}},
        ]
    )
    assert latest["id"] == "v1"


def test_filename_fallback_and_ext_none():
    assert gcl._filename_from_url("not-a-url") == "game_center_image.png"
    assert gcl._ext_from_content_type(None) is None
    assert gcl._ext_from_content_type("application/octet-stream") is None


def test_upload_operations_error_conditions():
    with pytest.raises(Exception):
        gcl._upload_operations([], b"abc")

    with pytest.raises(Exception):
        gcl._upload_operations([{"method": "PUT"}], b"abc")

    with pytest.raises(Exception):
        gcl._upload_operations([{"method": "PUT", "url": "https://u", "offset": 10, "length": 1}], b"abc")


def test_fetch_image_resource_fallback_and_failure_paths():
    class ASC:
        def get_game_center_activity_localization_image(self, _loc_id):
            raise RuntimeError("boom")

        def get_game_center_activity_localization_image_linkage(self, _loc_id):
            return {"data": {"id": "img-1"}}

        def get_game_center_activity_image(self, _img_id):
            return {"data": {"id": "img-1"}}

        def get_game_center_challenge_localization_image(self, _loc_id):
            raise RuntimeError("boom")

        def get_game_center_challenge_localization_image_linkage(self, _loc_id):
            raise RuntimeError("boom-link")

    asc = ASC()
    assert gcl._fetch_image_resource(asc, "activity", "loc-1") == {"id": "img-1"}
    assert gcl._fetch_image_resource(asc, "challenge", "loc-2") is None


def test_create_image_resource_requires_version_ids():
    asc = types.SimpleNamespace(
        create_game_center_achievement_image=lambda *_a, **_k: {"ok": "a"},
        create_game_center_leaderboard_image=lambda *_a, **_k: {"ok": "l"},
        create_game_center_activity_image=lambda *_a, **_k: {"ok": "act"},
        create_game_center_challenge_image=lambda *_a, **_k: {"ok": "chal"},
    )
    assert gcl._create_image_resource(asc, "achievement", "loc", None, "a.png", 1)["ok"] == "a"
    assert gcl._create_image_resource(asc, "leaderboard", "loc", None, "b.png", 1)["ok"] == "l"
    assert gcl._create_image_resource(asc, "activity", "loc", "v1", "c.png", 1)["ok"] == "act"
    assert gcl._create_image_resource(asc, "challenge", "loc", "v2", "d.png", 1)["ok"] == "chal"

    with pytest.raises(Exception):
        gcl._create_image_resource(asc, "activity", "loc", None, "c.png", 1)
    with pytest.raises(Exception):
        gcl._create_image_resource(asc, "challenge", "loc", None, "d.png", 1)
