from app_store_client import AppStoreConnectClient

from conftest import build_http_error


def test_create_subscription_group_localization_conflict_updates(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")

    def fake_request(method, endpoint, params=None, data=None, max_retries=3):
        if method == "POST" and endpoint == "v1/subscriptionGroupLocalizations":
            raise build_http_error(409)
        if endpoint == "v1/subscriptionGroups/group1/subscriptionGroupLocalizations":
            return {"data": [{"id": "group-loc-fr", "attributes": {"locale": "fr-FR"}}]}
        if method == "PATCH" and endpoint == "v1/subscriptionGroupLocalizations/group-loc-fr":
            return {"data": {"id": "group-loc-fr"}}
        return {"data": []}

    monkeypatch.setattr(client, "_request", fake_request)
    out = client.create_subscription_group_localization("group1", "fr-FR", "Nom", "Custom")
    assert out["data"]["id"] == "group-loc-fr"


def test_update_in_app_purchase_localization_truncates_and_get_fallback(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")
    seen = []

    def fake_request(method, endpoint, params=None, data=None, max_retries=3):
        seen.append((method, endpoint, data))
        return {"data": {"id": "x"}}

    monkeypatch.setattr(client, "_request", fake_request)

    client.update_in_app_purchase_localization("loc1")
    client.update_in_app_purchase_localization("loc1", name="n" * 100, description="d" * 100)

    assert ("GET", "inAppPurchaseLocalizations/loc1", None) in seen
    patch = [x for x in seen if x[0] == "PATCH" and x[1] == "inAppPurchaseLocalizations/loc1"][0]
    attrs = patch[2]["data"]["attributes"]
    assert len(attrs["name"]) <= 30
    assert len(attrs["description"]) <= 45


def test_create_and_update_app_event_localization_field_rules(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")
    sent = []

    def fake_request(method, endpoint, params=None, data=None, max_retries=3):
        sent.append((method, endpoint, data))
        return {"data": {"id": "ev-loc"}}

    monkeypatch.setattr(client, "_request", fake_request)

    client.create_app_event_localization(
        "event1",
        "fr-FR",
        name="N" * 200,
        short_description="S" * 200,
        long_description="x",  # too short, should be omitted
    )
    client.update_app_event_localization("loc1")
    client.update_app_event_localization("loc1", long_description="xy")

    post = [x for x in sent if x[0] == "POST"][0]
    attrs = post[2]["data"]["attributes"]
    assert attrs["locale"] == "fr-FR"
    assert "longDescription" not in attrs

    assert any(x[0] == "GET" and x[1] == "v1/appEventLocalizations/loc1" for x in sent)
    assert any(x[0] == "PATCH" and x[1] == "v1/appEventLocalizations/loc1" for x in sent)


def test_get_app_event_localization_id_map_fallback(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")

    monkeypatch.setattr(client, "get_app_event_localizations", lambda _event_id: {"data": []})
    monkeypatch.setattr(
        client,
        "get_app_event",
        lambda _event_id, include_localizations=False: {
            "included": [
                {"type": "appEventLocalizations", "id": "l1", "attributes": {"locale": "en-US"}},
                {"type": "appEventLocalizations", "id": "l2", "attributes": {"locale": "fr-FR"}},
            ]
        },
    )

    loc_map = client._get_app_event_localization_id_map("event1")
    assert loc_map["en-US"] == "l1"
    assert loc_map["fr-FR"] == "l2"
