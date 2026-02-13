import builtins

from workflows import subscription_translate as st


class _NonTUI:
    def available(self):
        return False


class _TUI:
    def __init__(self, checkbox_values=None, select_value=None, app_id="app1"):
        self._checkbox_values = checkbox_values or []
        self._select_value = select_value
        self.app_id = app_id

    def available(self):
        return True

    def checkbox(self, *_args, **_kwargs):
        return self._checkbox_values.pop(0) if self._checkbox_values else None

    def select(self, *_args, **_kwargs):
        return self._select_value

    def prompt_app_id(self, _asc):
        return self.app_id


def _group(group_id="g1", name="Main Group"):
    return {"id": group_id, "attributes": {"referenceName": name}}


def _sub(sub_id="s1", name="Monthly", product_id="monthly"):
    return {"id": sub_id, "attributes": {"name": name, "productId": product_id}}


def _loc(loc_id, locale, name="Base", description="Desc", custom_app_name="App Name"):
    return {
        "id": loc_id,
        "attributes": {
            "locale": locale,
            "name": name,
            "description": description,
            "customAppName": custom_app_name,
        },
    }


def test_subscription_group_and_subscription_pickers_valid_paths(monkeypatch):
    ui = _NonTUI()
    asc_groups = type(
        "ASC",
        (),
        {"get_subscription_groups": lambda *_a, **_k: {"data": [{"id": "g1", "attributes": {"referenceName": "Main"}}]}},
    )()
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1")
    groups = st._pick_groups(ui, asc_groups, "app1")
    assert groups and groups[0]["id"] == "g1"

    asc_subs = type(
        "ASC",
        (),
        {"get_subscriptions_for_group": lambda *_a, **_k: {"data": [{"id": "s1", "attributes": {"name": "Monthly"}}]}},
    )()
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1")
    subs = st._pick_subscriptions(ui, asc_subs, [_group("g1")])
    assert subs and subs[0]["id"] == "s1"

    tui = _TUI(checkbox_values=[["s1"]])
    subs_tui = st._pick_subscriptions(tui, asc_subs, [_group("g1")])
    assert subs_tui and subs_tui[0]["id"] == "s1"


def test_subscription_mode_selector_non_tui_group(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "2")
    assert st._mode_selector(_NonTUI()) == "group"


def test_subscription_run_executes_task_and_save_for_sub_and_group(fake_cli, fake_asc, monkeypatch):
    ui = _TUI(app_id="app1")
    fake_cli.ui = ui
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(st, "_pick_subscriptions", lambda *_a, **_k: [_sub("s1"), _sub("s2")])
    monkeypatch.setattr(st, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(st, "get_app_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(st, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(st.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(st, "format_progress", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("progress fail")))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    def fake_parallel(locales, task, **_kwargs):
        return {loc: task(loc) for loc in locales}, {}

    monkeypatch.setattr(st, "parallel_map_locales", fake_parallel)

    # Sub scope
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "sub")
    fake_asc.set_response(
        "get_subscription_localizations",
        lambda sub_id: {"data": [_loc("loc-en", "en-US", name="Base", description="Desc")] if sub_id == "s1" else [_loc("loc-en2", "en-US", name="Base2", description="Desc2")]},
    )
    fake_asc.set_response("create_subscription_localization", {"data": {"id": "ok"}})
    assert st.run(fake_cli) is True

    # Group scope
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "group")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    fake_asc.set_response(
        "get_subscription_group_localizations",
        {"data": [_loc("g-loc-en", "en-US", name="Base", custom_app_name="App Name")]},
    )
    fake_asc.set_response("create_subscription_group_localization", {"data": {"id": "ok"}})
    assert st.run(fake_cli) is True


def test_subscription_run_refresh_locale_ids_fallback_on_exception(fake_cli, fake_asc, monkeypatch):
    fake_cli.ui = _TUI(app_id="app1")
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "sub")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(st, "_pick_subscriptions", lambda *_a, **_k: [_sub("s1")])
    monkeypatch.setattr(st, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(st, "get_app_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(st, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(st.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(st, "parallel_map_locales", lambda *_a, **_k: ({"fr-FR": {"name": "Nom", "description": "Desc FR"}}, {}))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    calls = {"n": 0}

    def sub_locs(_sub_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"data": [_loc("loc-en", "en-US", name="Base", description="Desc")]}
        raise RuntimeError("refresh failed")

    fake_asc.set_response("get_subscription_localizations", sub_locs)
    fake_asc.set_response("create_subscription_localization", {"data": {"id": "created"}})
    assert st.run(fake_cli) is True


def test_subscription_run_409_direct_fetch_fallback_and_clear_progress_error(fake_cli, fake_asc, monkeypatch):
    fake_cli.ui = _TUI(app_id="app1")
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "group")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(st, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(st, "get_app_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(st, "choose_target_locales", lambda *_a, **_k: ["fr"])
    monkeypatch.setattr(st.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(
        st,
        "parallel_map_locales",
        lambda *_a, **_k: ({"fr": {"name": "Nom", "customAppName": "Custom FR"}}, {}),
    )
    monkeypatch.setattr(st, "format_progress", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("fmt fail")))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    # Raise only on the final clear line print (line 376 path), not on regular output.
    real_print = builtins.print

    def flaky_print(*args, **kwargs):
        first = args[0] if args else ""
        if isinstance(first, str) and first.startswith("\r") and first.strip() == "":
            raise RuntimeError("clear print failed")
        return real_print(*args, **kwargs)

    monkeypatch.setattr(st, "print", flaky_print, raising=False)

    calls = {"n": 0}

    def group_locs(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "data": [
                    _loc("g-loc-en", "en-US", name="Base", custom_app_name="Base App"),
                    _loc("g-loc-fr", "fr", name="Old", custom_app_name="Old"),
                ]
            }
        return {
            "data": [
                _loc("g-loc-fr-fr", "fr-FR", name="French", custom_app_name="French"),
                _loc("g-loc-fr-ca", "fr-CA", name="French CA", custom_app_name="French CA"),
            ]
        }

    fake_asc.set_response("get_subscription_group_localizations", group_locs)
    fake_asc.set_response(
        "update_subscription_group_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(Exception("409 conflict")),
    )
    fake_asc.set_response(
        "get_subscription_group_localization",
        {"data": {"attributes": {"name": "Nom", "customAppName": "Custom FR"}}},
    )
    assert st.run(fake_cli) is True


def test_subscription_run_409_recovered_update_with_progress_format_exception(fake_cli, fake_asc, monkeypatch):
    fake_cli.ui = _TUI(app_id="app1")
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "sub")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(st, "_pick_subscriptions", lambda *_a, **_k: [_sub("s1")])
    monkeypatch.setattr(st, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(st, "get_app_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(st, "choose_target_locales", lambda *_a, **_k: ["fr"])
    monkeypatch.setattr(st.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(st, "format_progress", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("fmt fail")))
    monkeypatch.setattr(
        st,
        "parallel_map_locales",
        lambda *_a, **_k: ({"fr": {"name": "Nom", "description": "Desc FR"}}, {}),
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    calls = {"n": 0}

    def sub_locs(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"data": [_loc("loc-en", "en-US", name="Base", description="Desc")]}
        return {"data": [_loc("loc-fr-fr", "fr-FR", name="Old", description="Old")]}

    fake_asc.set_response("get_subscription_localizations", sub_locs)
    fake_asc.set_response(
        "create_subscription_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(Exception("409 conflict")),
    )
    fake_asc.set_response("update_subscription_localization", {"data": {"id": "ok"}})
    assert st.run(fake_cli) is True
