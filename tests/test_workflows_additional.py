import builtins

from workflows import app_info, copy, export_localizations, iap_translate, subscription_translate


def _versions_resp():
    return {
        "data": [
            {
                "id": "ver-ios",
                "attributes": {"platform": "IOS", "versionString": "1.0", "appStoreState": "READY"},
            }
        ]
    }


def test_app_info_run_creates_localization(fake_cli, fake_asc, fake_ui, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.checkbox_values.append(["fr-FR"])

    fake_asc.set_response("find_primary_app_info_id", "app-info-1")
    fake_asc.set_response(
        "get_app_info_localizations",
        {
            "data": [
                {"id": "loc-en", "attributes": {"locale": "en-US"}},
            ]
        },
    )
    fake_asc.set_response(
        "get_app_info_localization",
        {"data": {"attributes": {"name": "My App", "subtitle": "Best subtitle"}}},
    )
    fake_asc.set_response("create_app_info_localization", {"data": {"id": "loc-fr"}})

    monkeypatch.setattr(app_info.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert app_info.run(fake_cli) is True
    assert any(call[0] == "create_app_info_localization" for call in fake_asc.calls)


def test_export_localizations_run_exports_selected_platform(fake_cli, fake_asc, fake_ui, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.select_values.append("IOS")

    fake_asc.set_response("_request", _versions_resp())
    fake_asc.set_response(
        "get_apps",
        {"data": [{"id": "app1", "attributes": {"name": "Demo App"}}]},
    )
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {"data": [{"id": "loc-en", "attributes": {"locale": "en-US"}}]},
    )

    exported = {}
    monkeypatch.setattr(
        export_localizations,
        "export_existing_localizations",
        lambda locs, app_name, app_id, version_string: exported.setdefault("path", "existing_localizations/demo.txt"),
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert export_localizations.run(fake_cli) is True
    assert exported["path"].endswith("demo.txt")


def test_copy_run_copies_locales(fake_cli, fake_asc, fake_ui, monkeypatch):
    fake_ui.app_id = "app1"

    monkeypatch.setattr(copy, "select_platforms", lambda *_a, **_k: {"IOS": {"id": "ver-target", "attributes": {"versionString": "2.0"}}})
    monkeypatch.setattr(
        copy,
        "pick_version_for_platform",
        lambda _ui, _asc, _app_id, _plat, prompt: {"id": "ver-source" if "FROM" in prompt else "ver-target", "attributes": {"versionString": "1.0" if "FROM" in prompt else "2.0"}},
    )
    fake_asc.set_response(
        "get_app_store_version_localizations",
        {"data": [{"id": "loc-en", "attributes": {"locale": "en-US"}}]},
    )
    fake_asc.set_response("copy_localization_from_previous_version", True)

    monkeypatch.setattr(copy.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert copy.run(fake_cli) is True
    assert any(call[0] == "copy_localization_from_previous_version" for call in fake_asc.calls)


def test_select_iaps_returns_selected_items(fake_ui, fake_asc, monkeypatch):
    fake_ui._tui = False
    fake_asc.set_response(
        "get_in_app_purchases",
        {
            "data": [
                {"id": "iap1", "attributes": {"referenceName": "Premium", "productId": "premium_monthly"}},
                {"id": "iap2", "attributes": {"referenceName": "Pro", "productId": "pro_yearly"}},
            ]
        },
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1")

    selected = iap_translate._select_iaps(fake_ui, fake_asc, "app1")
    assert len(selected) == 1
    assert selected[0]["id"] == "iap1"


def test_subscription_pickers_select_groups_and_subs(fake_ui, fake_asc, monkeypatch):
    fake_ui._tui = False
    fake_asc.set_response(
        "get_subscription_groups",
        {"data": [{"id": "group1", "attributes": {"referenceName": "Main"}}]},
    )
    fake_asc.set_response(
        "get_subscriptions_for_group",
        {"data": [{"id": "sub1", "attributes": {"name": "Monthly", "productId": "monthly"}}]},
    )

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1")
    groups = subscription_translate._pick_groups(fake_ui, fake_asc, "app1")
    assert groups and groups[0]["id"] == "group1"

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1")
    subs = subscription_translate._pick_subscriptions(fake_ui, fake_asc, groups)
    assert subs and subs[0]["id"] == "sub1"
