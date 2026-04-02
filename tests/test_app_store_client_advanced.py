from app_store_client import AppStoreConnectClient

from conftest import build_http_error


def test_create_app_store_version_localization_conflict_updates_existing(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")

    calls = {"update": 0}

    def fake_request(method, endpoint, params=None, data=None, max_retries=3):
        if method == "POST" and endpoint == "appStoreVersionLocalizations":
            raise build_http_error(409)
        if endpoint == "appStoreVersions/ver1/appStoreVersionLocalizations":
            return {"data": [{"id": "loc-sl", "attributes": {"locale": "sl-SI"}}]}
        if method == "PATCH" and endpoint == "appStoreVersionLocalizations/loc-sl":
            calls["update"] += 1
            return {"data": {"id": "loc-sl"}}
        if method == "GET" and endpoint == "appStoreVersionLocalizations/loc-sl":
            return {"data": {"id": "loc-sl", "attributes": {"locale": "sl-SI", "description": "Old description"}}}
        return {"data": []}

    monkeypatch.setattr(client, "_request", fake_request)

    out = client.create_app_store_version_localization("ver1", "sl", "New description")
    assert out["data"]["id"] == "loc-sl"
    assert calls["update"] == 1


def test_create_app_store_version_localization_normalizes_slovenian_locale(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")
    seen = []

    def fake_request(method, endpoint, params=None, data=None, max_retries=3):
        seen.append((method, endpoint, data))
        return {"data": {"id": "loc-sl"}}

    monkeypatch.setattr(client, "_request", fake_request)

    client.create_app_store_version_localization("ver1", "sl", "New description")

    post = [x for x in seen if x[0] == "POST" and x[1] == "appStoreVersionLocalizations"][0]
    assert post[2]["data"]["attributes"]["locale"] == "sl-SI"


def test_create_app_store_version_localization_normalizes_case_insensitive_locale(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")
    seen = []

    def fake_request(method, endpoint, params=None, data=None, max_retries=3):
        seen.append((method, endpoint, data))
        return {"data": {"id": "loc-sl"}}

    monkeypatch.setattr(client, "_request", fake_request)

    client.create_app_store_version_localization("ver1", "SL", "New description")

    post = [x for x in seen if x[0] == "POST" and x[1] == "appStoreVersionLocalizations"][0]
    assert post[2]["data"]["attributes"]["locale"] == "sl-SI"


def test_create_app_store_version_localization_normalizes_new_regioned_locales(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")
    seen = []

    def fake_request(method, endpoint, params=None, data=None, max_retries=3):
        seen.append((method, endpoint, data))
        return {"data": {"id": "loc-x"}}

    monkeypatch.setattr(client, "_request", fake_request)

    for requested, expected in [
        ("bn", "bn-BD"),
        ("gu", "gu-IN"),
        ("kn", "kn-IN"),
        ("ml", "ml-IN"),
        ("mr", "mr-IN"),
        ("or", "or-IN"),
        ("pa", "pa-IN"),
        ("ta", "ta-IN"),
        ("te", "te-IN"),
        ("ur", "ur-PK"),
    ]:
        client.create_app_store_version_localization("ver1", requested, "Desc")
        post = [x for x in seen if x[0] == "POST"][-1]
        assert post[2]["data"]["attributes"]["locale"] == expected


def test_create_app_store_version_localization_conflict_root_matches_existing(monkeypatch):
    client = AppStoreConnectClient("kid", "issuer", "pk")

    calls = {"update": 0}

    def fake_request(method, endpoint, params=None, data=None, max_retries=3):
        if method == "POST" and endpoint == "appStoreVersionLocalizations":
            raise build_http_error(409)
        if endpoint == "appStoreVersions/ver1/appStoreVersionLocalizations":
            return {"data": [{"id": "loc-fi", "attributes": {"locale": "fi-FI"}}]}
        if method == "PATCH" and endpoint == "appStoreVersionLocalizations/loc-fi":
            calls["update"] += 1
            return {"data": {"id": "loc-fi"}}
        if method == "GET" and endpoint == "appStoreVersionLocalizations/loc-fi":
            return {"data": {"id": "loc-fi", "attributes": {"locale": "fi-FI", "description": "Old description"}}}
        return {"data": []}

    monkeypatch.setattr(client, "_request", fake_request)

    out = client.create_app_store_version_localization("ver1", "fi", "New description")
    assert out["data"]["id"] == "loc-fi"
    assert calls["update"] == 1


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
