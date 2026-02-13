import requests

from app_store_client import AppStoreConnectClient

from conftest import DummyResponse


def test_request_uses_v1_base_and_auth_header(monkeypatch):
    captured = {}

    def fake_encode(*_args, **_kwargs):
        return "token-123"

    def fake_request(method, url, headers=None, params=None, json=None):
        captured.update({"method": method, "url": url, "headers": headers, "params": params, "json": json})
        return DummyResponse(payload={"ok": True})

    monkeypatch.setattr("app_store_client.jwt.encode", fake_encode)
    monkeypatch.setattr("app_store_client.requests.request", fake_request)

    client = AppStoreConnectClient("kid", "issuer", "pk")
    out = client._request("GET", "apps", params={"limit": 1})

    assert out == {"ok": True}
    assert captured["url"] == "https://api.appstoreconnect.apple.com/v1/apps"
    assert captured["headers"]["Authorization"] == "Bearer token-123"


def test_request_routes_v2_endpoint(monkeypatch):
    monkeypatch.setattr("app_store_client.jwt.encode", lambda *_a, **_k: "t")
    monkeypatch.setattr(
        "app_store_client.requests.request",
        lambda *_a, **_k: DummyResponse(payload={"data": [{"id": "1"}]})
    )

    client = AppStoreConnectClient("kid", "issuer", "pk")
    out = client._request("GET", "v2/inAppPurchases")
    assert out["data"][0]["id"] == "1"


def test_request_retries_on_409(monkeypatch):
    calls = {"n": 0}

    def fake_request(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            return DummyResponse(status_code=409, payload={"errors": []})
        return DummyResponse(payload={"data": [{"id": "ok"}]})

    monkeypatch.setattr("app_store_client.jwt.encode", lambda *_a, **_k: "t")
    monkeypatch.setattr("app_store_client.requests.request", fake_request)
    monkeypatch.setattr("app_store_client.time.sleep", lambda *_a, **_k: None)

    client = AppStoreConnectClient("kid", "issuer", "pk")
    out = client._request("GET", "apps", max_retries=2)

    assert out["data"][0]["id"] == "ok"
    assert calls["n"] == 2


def test_create_and_update_localization_payload_mapping(monkeypatch):
    sent = []

    def fake_request(_self, method, endpoint, params=None, data=None, max_retries=3):
        sent.append((method, endpoint, params, data, max_retries))
        return {"data": {"id": "loc-1"}}

    monkeypatch.setattr(AppStoreConnectClient, "_request", fake_request)
    client = AppStoreConnectClient("kid", "issuer", "pk")

    client.create_app_store_version_localization(
        version_id="ver1",
        locale="fr-FR",
        description="desc",
        keywords="a,b",
        promotional_text="promo",
        whats_new="wn",
        marketing_url="https://m",
        support_url="https://s",
    )
    client.update_app_store_version_localization(
        localization_id="loc-1",
        description="new desc",
        whats_new="new wn",
    )

    assert sent[0][0] == "POST"
    assert sent[0][1] == "appStoreVersionLocalizations"
    attrs = sent[0][3]["data"]["attributes"]
    assert attrs["locale"] == "fr-FR"
    assert attrs["promotionalText"] == "promo"
    patch_calls = [call for call in sent if call[0] == "PATCH"]
    assert patch_calls
    assert patch_calls[0][1] == "appStoreVersionLocalizations/loc-1"


def test_many_wrapper_methods_hit_expected_endpoints(monkeypatch):
    seen = []

    def fake_request(self, method, endpoint, params=None, data=None, max_retries=3):
        seen.append((method, endpoint, params, data))
        return {"data": []}

    monkeypatch.setattr(AppStoreConnectClient, "_request", fake_request)
    client = AppStoreConnectClient("kid", "issuer", "pk")

    client.get_app_infos("app1")
    client.get_app_info_localizations("info1")
    client.get_app_info_localization("loc1")
    client.get_in_app_purchases("app1")
    client.get_in_app_purchase_localizations("iap1")
    client.get_subscription_groups("app1")
    client.get_subscriptions_for_group("group1")
    client.get_subscription_localizations("sub1")
    client.get_subscription_group_localizations("group1")
    client.get_app_events("app1")
    client.get_app_event_localizations("event1")
    client.get_game_center_detail("app1")
    client.get_game_center_group("detail1")
    client.get_game_center_achievements("detail1")
    client.get_game_center_leaderboards("detail1")
    client.get_game_center_activities("detail1")
    client.get_game_center_challenges("detail1")
    client.get_game_center_group_achievements("group1")
    client.get_game_center_group_leaderboards("group1")
    client.get_game_center_group_activities("group1")
    client.get_game_center_group_challenges("group1")
    client.get_game_center_activity_versions("activity1")
    client.get_game_center_challenge_versions("challenge1")
    client.get_game_center_activity_version_localizations("version1")
    client.get_game_center_challenge_version_localizations("version1")

    endpoints = [e for _m, e, _p, _d in seen]
    assert "apps/app1/appInfos" in endpoints
    assert any("inAppPurchases" in e for e in endpoints)
    assert any("subscriptions" in e for e in endpoints)
    assert any("appEvents" in e for e in endpoints)
    assert any("gameCenterDetails" in e for e in endpoints)
    assert any("gameCenterActivities/activity1/versions" in e for e in endpoints)
