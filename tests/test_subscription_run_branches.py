import builtins

from workflows import subscription_translate as st


def _sub(sub_id, name="Monthly", product_id="monthly"):
    return {"id": sub_id, "attributes": {"name": name, "productId": product_id}}


def _group(group_id, name="Main Group"):
    return {"id": group_id, "attributes": {"referenceName": name}}


def _loc(loc_id, locale, name="Base", description="Desc"):
    return {"id": loc_id, "attributes": {"locale": locale, "name": name, "description": description}}


def test_subscription_run_returns_when_app_cancelled(fake_cli, fake_ui, monkeypatch):
    fake_ui.app_id = None
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "sub")
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert st.run(fake_cli) is True


def test_subscription_run_returns_when_groups_or_subs_missing(fake_cli, fake_ui, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "sub")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert st.run(fake_cli) is True

    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(st, "_pick_subscriptions", lambda *_a, **_k: [])
    assert st.run(fake_cli) is True


def test_subscription_run_returns_when_provider_not_selected(fake_cli, fake_ui, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "sub")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(st, "_pick_subscriptions", lambda *_a, **_k: [_sub("sub1")])
    monkeypatch.setattr(st, "get_app_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(st, "pick_provider", lambda *_a, **_k: (None, None))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert st.run(fake_cli) is True


def test_subscription_run_global_targets_and_skip_paths(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "sub")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(st, "_pick_subscriptions", lambda *_a, **_k: [_sub("sub1"), _sub("sub2")])
    monkeypatch.setattr(st, "get_app_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(st, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(st, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    fake_asc.set_response("get_subscription_localizations", {"data": []})
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert st.run(fake_cli) is True


def test_subscription_run_handles_base_or_targets_missing(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "sub")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(st, "_pick_subscriptions", lambda *_a, **_k: [_sub("sub1")])
    monkeypatch.setattr(st, "get_app_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(st, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(st, "choose_target_locales", lambda *_a, **_k: ["en-US"])
    fake_asc.set_response("get_subscription_localizations", {"data": [{"id": "bad", "attributes": {"locale": None}}]})
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert st.run(fake_cli) is True

    fake_asc.set_response(
        "get_subscription_localizations",
        {"data": [_loc("loc-en", "en-US", name="", description="Desc")]},
    )
    assert st.run(fake_cli) is True

    fake_asc.set_response(
        "get_subscription_localizations",
        {"data": [_loc("loc-en", "en-US", name="Base", description="Desc")]},
    )
    assert st.run(fake_cli) is True


def test_subscription_run_recovers_from_409_with_matching_refreshed_locale(
    fake_cli, fake_ui, fake_asc, monkeypatch
):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "sub")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(st, "_pick_subscriptions", lambda *_a, **_k: [_sub("sub1")])
    monkeypatch.setattr(st, "get_app_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(st, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(st, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(st.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(
        st,
        "parallel_map_locales",
        lambda *_a, **_k: ({"fr-FR": {"name": "Nom", "description": "Desc FR"}}, {}),
    )

    calls = {"n": 0}

    def get_sub_locs(_sub_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"data": [_loc("loc-en", "en-US", name="Base", description="Desc")]}
        return {"data": [_loc("loc-fr", "fr-FR", name="Nom", description="Desc FR")]}

    fake_asc.set_response("get_subscription_localizations", get_sub_locs)
    fake_asc.set_response(
        "create_subscription_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(Exception("409 conflict")),
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert st.run(fake_cli) is True


def test_subscription_run_recovers_from_409_with_new_id_group_scope(
    fake_cli, fake_ui, fake_asc, monkeypatch
):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "group")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(st, "get_app_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(st, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(st, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(st.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(
        st,
        "parallel_map_locales",
        lambda *_a, **_k: ({"fr-FR": {"name": "Nom", "customAppName": "Custom FR"}}, {}),
    )

    calls = {"n": 0}

    def get_group_locs(_group_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"data": [{"id": "g-loc-en", "attributes": {"locale": "en-US", "name": "Base", "customAppName": "Base App"}}]}
        return {"data": [{"id": "g-loc-fr", "attributes": {"locale": "fr-FR", "name": "Old", "customAppName": "Old"}}]}

    fake_asc.set_response("get_subscription_group_localizations", get_group_locs)
    fake_asc.set_response(
        "create_subscription_group_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(Exception("409 conflict")),
    )
    fake_asc.set_response("update_subscription_group_localization", {"data": {"id": "ok"}})
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert st.run(fake_cli) is True


def test_subscription_run_recovers_from_409_with_direct_fetch_by_loc_id(
    fake_cli, fake_ui, fake_asc, monkeypatch
):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "sub")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(st, "_pick_subscriptions", lambda *_a, **_k: [_sub("sub1")])
    monkeypatch.setattr(st, "get_app_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(st, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(st, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(st.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(
        st,
        "parallel_map_locales",
        lambda *_a, **_k: ({"fr-FR": {"name": "Nom", "description": "Desc FR"}}, {}),
    )

    fake_asc.set_response(
        "get_subscription_localizations",
        lambda *_a, **_k: {
            "data": [
                _loc("loc-en", "en-US", name="Base", description="Desc"),
                _loc("loc-fr", "fr-FR", name="Old", description="Old"),
            ]
        },
    )
    fake_asc.set_response(
        "update_subscription_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(Exception("409 conflict")),
    )
    fake_asc.set_response(
        "get_subscription_localization",
        {"data": {"attributes": {"name": "Nom", "description": "Desc FR"}}},
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert st.run(fake_cli) is True
