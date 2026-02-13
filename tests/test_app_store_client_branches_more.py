import requests

from app_store_client import AppStoreConnectClient
from conftest import DummyResponse


def test_request_retries_5xx_and_raises_with_unprintable_preview(monkeypatch):
    class _Bad:
        def __str__(self):
            raise RuntimeError("boom")

        def __repr__(self):
            raise RuntimeError("boom")

    monkeypatch.setattr("app_store_client.jwt.encode", lambda *_a, **_k: "t")
    monkeypatch.setattr("app_store_client.time.sleep", lambda *_a, **_k: None)

    calls = {"n": 0}

    def fake_request(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return DummyResponse(
                status_code=500,
                headers={"Retry-After": "0", "x-request-id": "req-1"},
                text="server down",
            )
        return DummyResponse(payload={"data": [{"id": "ok"}]})

    monkeypatch.setattr("app_store_client.requests.request", fake_request)
    client = AppStoreConnectClient("kid", "issuer", "pk")
    out = client._request("GET", "apps", params={"x": _Bad()}, max_retries=1)
    assert out["data"][0]["id"] == "ok"

    monkeypatch.setattr(
        "app_store_client.requests.request",
        lambda *_a, **_k: DummyResponse(status_code=500, headers={"request-id": "req-2"}, text="still down"),
    )
    try:
        client._request("GET", "apps", data={"x": _Bad()}, max_retries=0)
        assert False, "expected HTTPError"
    except requests.exceptions.HTTPError:
        pass


def test_apps_paging_and_latest_version_helpers(monkeypatch):
    seen = []

    def fake_request(_self, method, endpoint, params=None, data=None, max_retries=3):
        seen.append((method, endpoint, params))
        if endpoint == "apps":
            if params and params.get("cursor") == "bad":
                return {"data": [{"id": "a2"}], "links": {"next": "%%%%"}}
            return {
                "data": [{"id": "a1"}],
                "links": {"next": "https://example.test/apps?cursor=next-token"},
            }
        if endpoint == "apps/app1/appStoreVersions":
            return {"data": [{"id": "ver1", "attributes": {"versionString": "1.2.3", "appStoreState": "READY_FOR_SALE"}}]}
        if endpoint == "appStoreVersions/ver1/appStoreVersionLocalizations":
            return {"data": [{"id": "loc1"}]}
        return {"data": []}

    monkeypatch.setattr(AppStoreConnectClient, "_request", fake_request)
    client = AppStoreConnectClient("kid", "issuer", "pk")

    apps = client.get_apps(limit=999)
    page = client.get_apps_page(limit=500)
    bad_page = client.get_apps_page(limit=10, cursor="bad")
    latest_id = client.get_latest_app_store_version("app1")
    latest_info = client.get_latest_app_store_version_info("app1")
    locs = client.get_app_store_version_localizations("ver1")

    assert apps["data"][0]["id"] == "a1"
    assert page["next_cursor"] == "next-token"
    assert bad_page["next_cursor"] is None
    assert latest_id == "ver1"
    assert latest_info["versionString"] == "1.2.3"
    assert locs["data"][0]["id"] == "loc1"
    assert any(call[2] == {"limit": 200} for call in seen if call[1] == "apps")


def test_update_app_store_version_localization_no_changes_and_fallback(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")
    seen = []

    monkeypatch.setattr(
        client,
        "get_app_store_version_localization",
        lambda _loc_id: {
            "data": {
                "attributes": {
                    "description": "desc",
                    "keywords": "a,b",
                    "promotionalText": "promo",
                    "whatsNew": "wn",
                    "marketingUrl": "https://m",
                    "supportUrl": "https://s",
                }
            }
        },
    )
    monkeypatch.setattr(
        client,
        "_request",
        lambda method, endpoint, params=None, data=None, max_retries=3: seen.append((method, endpoint, data)) or {"data": {"id": "x"}},
    )

    same = client.update_app_store_version_localization(
        "loc1",
        description="desc",
        keywords="a,b",
        promotional_text="promo",
        whats_new="wn",
        marketing_url="https://m",
        support_url="https://s",
    )
    assert same["data"]["attributes"]["description"] == "desc"
    assert not any(call[0] == "PATCH" for call in seen)

    monkeypatch.setattr(
        client,
        "get_app_store_version_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    client.update_app_store_version_localization(
        "loc2",
        description="new",
        keywords="k",
        promotional_text="p",
        whats_new="w" * 5000,
        marketing_url="https://m2",
        support_url="https://s2",
    )
    patch = [x for x in seen if x[0] == "PATCH" and x[1] == "appStoreVersionLocalizations/loc2"][0]
    attrs = patch[2]["data"]["attributes"]
    assert attrs["description"] == "new"
    assert attrs["whatsNew"].endswith("...")


def test_app_info_and_copy_localization_paths(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")
    sent = []

    def fake_request(method, endpoint, params=None, data=None, max_retries=3):
        sent.append((method, endpoint, data))
        if endpoint == "appInfos/app-info/appInfoLocalizations":
            return {"data": [{"id": "loc-en", "attributes": {"locale": "en-US"}}]}
        if endpoint == "appInfoLocalizations/loc-en":
            return {"data": {"attributes": {"name": "Old", "subtitle": "Old"}}}
        if endpoint == "appStoreVersions/src/appStoreVersionLocalizations":
            return {"data": [{"id": "src-loc", "attributes": {"locale": "fr-FR", "description": "Desc"}}]}
        if endpoint == "appStoreVersions/dst/appStoreVersionLocalizations":
            return {"data": []}
        return {"data": {"id": "ok"}}

    monkeypatch.setattr(client, "_request", fake_request)
    created = client.create_app_info_localization("app-info", "fr-FR", name="N" * 80, subtitle="S" * 80)
    updated = client.update_app_info_localization("loc-en", name="Old", subtitle="Old")
    assert created["data"]["id"] == "ok"
    assert updated["data"]["attributes"]["name"] == "Old"
    assert client.find_primary_app_info_id("app1") is None

    monkeypatch.setattr(client, "get_app_infos", lambda _app_id: {"data": [{"id": "a1", "attributes": {"appStoreState": "READY"}}]})
    assert client.find_primary_app_info_id("app1") == "a1"
    monkeypatch.setattr(
        client,
        "get_app_infos",
        lambda _app_id: {"data": [{"id": "a2", "attributes": {"appStoreState": "PREPARE_FOR_SUBMISSION"}}, {"id": "a1"}]},
    )
    assert client.find_primary_app_info_id("app1") == "a2"

    assert client.copy_localization_from_previous_version("src", "dst", "fr-FR") is True
    assert client.copy_localization_from_previous_version("src", "dst", "ja") is False


def test_subscription_conflict_fallback_paths(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")

    def _http_409():
        err = requests.exceptions.HTTPError("http")
        err.response = DummyResponse(status_code=409, payload={})
        return err

    def sub_request(method, endpoint, params=None, data=None, max_retries=3):
        if method == "POST" and endpoint == "v1/subscriptionLocalizations":
            raise _http_409()
        if endpoint == "v1/subscriptions/sub1/subscriptionLocalizations":
            return {"data": [{"id": "loc-en", "attributes": {"locale": "en-US"}}]}
        return {"data": []}

    monkeypatch.setattr(client, "_request", sub_request)
    out = client.create_subscription_localization("sub1", "fr-FR", "Nom", "Desc")
    assert out == {"en-US": "loc-en"}

    def group_request(method, endpoint, params=None, data=None, max_retries=3):
        if method == "POST" and endpoint == "v1/subscriptionGroupLocalizations":
            raise _http_409()
        if endpoint == "v1/subscriptionGroups/group1/subscriptionGroupLocalizations":
            raise RuntimeError("boom")
        return {"data": []}

    monkeypatch.setattr(client, "_request", group_request)
    try:
        client.create_subscription_group_localization("group1", "fr-FR", "Nom", "Custom")
        assert False, "expected HTTPError"
    except requests.exceptions.HTTPError:
        pass


def test_game_center_optional_fields_and_image_accessors(monkeypatch):
    seen = []

    def fake_request(self, method, endpoint, params=None, data=None, max_retries=3):
        seen.append((method, endpoint, params, data))
        return {"data": {"id": "ok"}}

    monkeypatch.setattr(AppStoreConnectClient, "_request", fake_request)
    client = AppStoreConnectClient("kid", "issuer", "pk")

    client.get_game_center_achievement_localizations("ach1")
    client.get_game_center_leaderboard_localizations("lb1")
    client.get_game_center_achievement_localization_image("loc1")
    client.get_game_center_achievement_localization_image_linkage("loc1")
    client.get_game_center_achievement_image("img1")
    client.get_game_center_leaderboard_localization_image("loc2")
    client.get_game_center_leaderboard_localization_image_linkage("loc2")
    client.get_game_center_leaderboard_image("img2")
    client.get_game_center_activity_localization_image("loc3")
    client.get_game_center_activity_localization_image_linkage("loc3")
    client.get_game_center_activity_image("img3")
    client.get_game_center_challenge_localization_image("loc4")
    client.get_game_center_challenge_localization_image_linkage("loc4")
    client.get_game_center_challenge_image("img4")

    client.update_game_center_achievement_image("img1")
    client.update_game_center_leaderboard_image("img2")
    client.update_game_center_activity_image("img3")
    client.update_game_center_challenge_image("img4")

    client.update_game_center_achievement_localization("locA", before_earned_description="before", after_earned_description="after")
    client.create_game_center_leaderboard_localization(
        "lb1",
        "fr-FR",
        "Nom",
        description="Desc",
        formatter_suffix="pts",
        formatter_suffix_singular="pt",
        formatter_override="%d",
    )
    client.update_game_center_leaderboard_localization(
        "locB",
        name="Nom2",
        description="Desc2",
        formatter_suffix="pts2",
        formatter_suffix_singular="pt2",
        formatter_override="%s",
    )
    client.update_game_center_activity_localization("locC", description="Desc")
    client.update_game_center_challenge_localization("locD", description="Desc")

    endpoints = [x[1] for x in seen]
    assert "v1/gameCenterAchievements/ach1/localizations" in endpoints
    assert "v1/gameCenterLeaderboardLocalizations/loc2/relationships/gameCenterLeaderboardImage" in endpoints
    assert "v1/gameCenterChallengeLocalizations/loc4/relationships/image" in endpoints
    assert "v1/gameCenterChallengeImages/img4" in endpoints
    assert "v1/gameCenterLeaderboardLocalizations" in endpoints
