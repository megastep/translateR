import builtins

from workflows import subscription_translate as st
from conftest import build_http_error


def _sub(sub_id, name="Monthly", product_id="monthly", state=None):
    attributes = {"name": name, "productId": product_id}
    if state is not None:
        attributes["state"] = state
    return {"id": sub_id, "attributes": attributes}


def _group(group_id, name="Main Group"):
    return {"id": group_id, "attributes": {"referenceName": name}}


def _loc(loc_id, locale, name="Base", description="Desc", state=None):
    attributes = {"locale": locale, "name": name, "description": description}
    if state is not None:
        attributes["state"] = state
    return {"id": loc_id, "attributes": attributes}


def test_asc_error_summary_includes_structured_detail_and_pointer():
    error = build_http_error(
        409,
        payload={
            "errors": [
                {
                    "code": "ENTITY_ERROR.ATTRIBUTE.INVALID",
                    "title": "The provided entity has an invalid attribute",
                    "detail": "Description must not exceed 45 characters.",
                    "source": {"pointer": "/data/attributes/description"},
                }
            ]
        },
    )

    summary = st._asc_error_summary(error)
    assert "ASC 409" in summary
    assert "Description must not exceed 45 characters" in summary
    assert "/data/attributes/description" in summary


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


def test_subscription_run_skips_product_locked_by_pending_review(
    fake_cli, fake_ui, fake_asc, monkeypatch, capsys
):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "sub")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(
        st,
        "_pick_subscriptions",
        lambda *_a, **_k: [_sub("sub1", state="WAITING_FOR_REVIEW")],
    )
    monkeypatch.setattr(st, "get_app_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(st, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert st.run(fake_cli) is True
    assert fake_cli.ai_manager.get_provider("fake").calls == []
    assert not any(call[0] == "get_subscription_localizations" for call in fake_asc.calls)
    assert "Skipping before translation" in capsys.readouterr().out


def test_subscription_run_skips_when_existing_localization_is_pending_review(
    fake_cli, fake_ui, fake_asc, monkeypatch, capsys
):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "sub")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(st, "_pick_subscriptions", lambda *_a, **_k: [_sub("sub1", state="APPROVED")])
    monkeypatch.setattr(st, "get_app_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(st, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    fake_asc.set_response(
        "get_subscription_localizations",
        {"data": [_loc("loc-en", "en-US", state="WAITING_FOR_REVIEW")]},
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert st.run(fake_cli) is True
    assert fake_cli.ai_manager.get_provider("fake").calls == []
    assert "Existing subscription localization state is WAITING_FOR_REVIEW" in capsys.readouterr().out


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


def test_subscription_run_retranslates_after_asc_rejection(
    fake_cli, fake_ui, fake_asc, monkeypatch, capsys
):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "sub")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(st, "_pick_subscriptions", lambda *_a, **_k: [_sub("sub1")])
    monkeypatch.setattr(st, "get_app_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(st, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    provider = fake_cli.ai_manager.get_provider("fake")
    monkeypatch.setattr(st, "pick_provider", lambda _cli: (provider, "fake"))
    monkeypatch.setattr(st.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(
        st,
        "parallel_map_locales",
        lambda locales, task, **_kwargs: ({locale: task(locale) for locale in locales}, {}),
    )
    fake_asc.set_response(
        "get_subscription_localizations",
        {"data": [_loc("loc-en", "en-US", name="Base", description="Desc")]},
    )
    saves = {"count": 0}

    def create(*_args, **_kwargs):
        saves["count"] += 1
        if saves["count"] == 1:
            raise Exception("422 ENTITY_ERROR invalid subscription localization")
        return {"data": {"id": "loc-fr"}}

    fake_asc.set_response("create_subscription_localization", create)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert st.run(fake_cli) is True
    assert saves["count"] == 2
    assert [call["max_length"] for call in provider.calls] == [28, 41, 28, 41]
    assert "App Store Connect rejected" in provider.calls[2]["refinement"]
    output = capsys.readouterr().out
    assert "forcing one fresh translation" in output
    assert "Saved 1/1 locales" in output


def test_subscription_run_does_not_count_failed_retranslation_as_saved(
    fake_cli, fake_ui, fake_asc, monkeypatch, capsys
):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(st, "_mode_selector", lambda _ui: "sub")
    monkeypatch.setattr(st, "_pick_groups", lambda *_a, **_k: [_group("g1")])
    monkeypatch.setattr(st, "_pick_subscriptions", lambda *_a, **_k: [_sub("sub1")])
    monkeypatch.setattr(st, "get_app_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(st, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(
        st, "pick_provider", lambda _cli: (fake_cli.ai_manager.get_provider("fake"), "fake")
    )
    monkeypatch.setattr(st.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(
        st,
        "parallel_map_locales",
        lambda locales, task, **_kwargs: ({locale: task(locale) for locale in locales}, {}),
    )
    fake_asc.set_response(
        "get_subscription_localizations",
        {"data": [_loc("loc-en", "en-US", name="Base", description="Desc")]},
    )
    fake_asc.set_response(
        "create_subscription_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(Exception("422 ENTITY_ERROR")),
    )
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    assert st.run(fake_cli) is True
    output = capsys.readouterr().out
    assert "after forced retranslation" in output
    assert "Saved 0/1 locales" in output
