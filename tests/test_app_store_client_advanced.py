from app_store_client import AppStoreConnectClient

from conftest import build_http_error


def test_create_subscription_localization_conflict_updates_existing(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")

    calls = {"update": 0}

    def fake_request(method, endpoint, params=None, data=None, max_retries=3):
        if method == "POST" and endpoint == "v1/subscriptionLocalizations":
            raise build_http_error(409)
        if endpoint == "v1/subscriptions/sub1/subscriptionLocalizations":
            return {"data": [{"id": "loc-fr", "attributes": {"locale": "fr-FR"}}]}
        if method == "PATCH" and endpoint == "v1/subscriptionLocalizations/loc-fr":
            calls["update"] += 1
            return {"data": {"id": "loc-fr"}}
        return {"data": []}

    monkeypatch.setattr(client, "_request", fake_request)

    out = client.create_subscription_localization("sub1", "fr-FR", "Nom", "Desc")
    assert out["data"]["id"] == "loc-fr"
    assert calls["update"] == 1


def test_create_app_event_localization_conflict_routes_to_update(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")

    def fake_request(method, endpoint, params=None, data=None, max_retries=3):
        if method == "POST" and endpoint == "v1/appEventLocalizations":
            raise build_http_error(409)
        if endpoint == "v1/appEvents/event1/localizations":
            return {"data": [{"id": "evloc-fr", "attributes": {"locale": "fr-FR"}}]}
        if method == "PATCH" and endpoint == "v1/appEventLocalizations/evloc-fr":
            return {"data": {"id": "evloc-fr"}}
        return {"data": []}

    monkeypatch.setattr(client, "_request", fake_request)

    out = client.create_app_event_localization("event1", "fr-FR", name="Nom", short_description="Court", long_description="Long")
    assert out["data"]["id"] == "evloc-fr"


def test_update_localization_get_when_no_attrs(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")
    seen = []

    def fake_request(method, endpoint, params=None, data=None, max_retries=3):
        seen.append((method, endpoint))
        return {"data": {"id": "x"}}

    monkeypatch.setattr(client, "_request", fake_request)

    client.update_subscription_localization("loc1")
    client.update_subscription_group_localization("loc2")

    assert ("GET", "v1/subscriptionLocalizations/loc1") in seen
    assert ("GET", "v1/subscriptionGroupLocalizations/loc2") in seen


def test_app_event_locale_id_matching_rules():
    client = AppStoreConnectClient("kid", "issuer", "pk")

    assert client._app_event_localization_id_for_locale({"fr-FR": "1"}, "fr-FR") == "1"
    assert client._app_event_localization_id_for_locale({"fi-FI": "2"}, "fi") == "2"
    assert client._app_event_localization_id_for_locale({"en-US": "3"}, "en-AU") == ""
    assert client._app_event_localization_id_for_locale({"en-US": "3", "en-GB": "4"}, "en") == ""
