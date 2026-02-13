import builtins

from workflows import iap_translate as iap


def _iap(iap_id="iap1", name="Premium", product_id="premium.monthly"):
    return {"id": iap_id, "type": "inAppPurchasesV2", "attributes": {"referenceName": name, "productId": product_id}}


def _loc(loc_id, locale, name="Base", description="Desc"):
    return {"id": loc_id, "attributes": {"locale": locale, "name": name, "description": description}}


def test_select_iaps_empty_invalid_and_missing_selection(monkeypatch):
    class NonTUI:
        def available(self):
            return False

    class TUI:
        def available(self):
            return True

        def checkbox(self, *_args, **_kwargs):
            return ["ghost"]

    asc_empty = type("ASC", (), {"get_in_app_purchases": lambda *_a, **_k: {"data": []}})()
    assert iap._select_iaps(NonTUI(), asc_empty, "app1") == []

    asc_one = type("ASC", (), {"get_in_app_purchases": lambda *_a, **_k: {"data": [_iap()]}})()
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "x")
    assert iap._select_iaps(NonTUI(), asc_one, "app1") == []
    assert iap._select_iaps(TUI(), asc_one, "app1") == []


def test_iap_run_returns_on_cancel_or_no_selection(fake_cli, fake_ui, monkeypatch):
    fake_ui.app_id = None
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert iap.run(fake_cli) is True

    fake_ui.app_id = "app1"
    monkeypatch.setattr(iap, "_select_iaps", lambda *_a, **_k: [])
    assert iap.run(fake_cli) is True


def test_iap_run_returns_when_provider_missing(fake_cli, fake_ui, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(iap, "_select_iaps", lambda *_a, **_k: [_iap()])
    monkeypatch.setattr(iap, "pick_provider", lambda *_a, **_k: (None, None))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert iap.run(fake_cli) is True


def test_iap_run_skips_when_localization_data_invalid(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(iap, "_select_iaps", lambda *_a, **_k: [_iap()])
    monkeypatch.setattr(iap, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(iap, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    fake_asc.set_response("get_in_app_purchase_localizations", {"data": []})
    assert iap.run(fake_cli) is True

    fake_asc.set_response("get_in_app_purchase_localizations", {"data": [{"id": "x", "attributes": {"locale": None}}]})
    assert iap.run(fake_cli) is True

    fake_asc.set_response("get_in_app_purchase_localizations", {"data": [_loc("loc-en", "en-US", name="", description="Desc")]})
    assert iap.run(fake_cli) is True


def test_iap_run_skips_when_no_available_or_selected_targets(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(iap, "_select_iaps", lambda *_a, **_k: [_iap()])
    monkeypatch.setattr(iap, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    fake_asc.set_response(
        "get_in_app_purchase_localizations",
        {"data": [_loc("loc-en", "en-US", name="Base", description="Desc"), _loc("loc-fr", "fr-FR", name="Nom", description="Desc FR")]},
    )
    assert iap.run(fake_cli) is True

    fake_asc.set_response(
        "get_in_app_purchase_localizations",
        {"data": [_loc("loc-en", "en-US", name="Base", description="Desc")]},
    )
    monkeypatch.setattr(iap, "choose_target_locales", lambda *_a, **_k: [])
    assert iap.run(fake_cli) is True


def test_iap_run_empty_name_retry_and_skip_branch(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    provider = fake_cli.ai_manager.get_provider("fake")
    calls = {"n": 0}

    def translate(_text, _lang, max_length=None, seed=None, refinement=None):
        calls["n"] += 1
        return "" if calls["n"] <= 2 else "Desc"

    provider.translate = translate
    monkeypatch.setattr(iap, "_select_iaps", lambda *_a, **_k: [_iap()])
    monkeypatch.setattr(iap, "pick_provider", lambda *_a, **_k: (provider, "fake"))
    monkeypatch.setattr(iap, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(iap, "format_progress", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("progress")))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    monkeypatch.setattr(iap.time, "sleep", lambda *_a, **_k: None)
    fake_asc.set_response(
        "get_in_app_purchase_localizations",
        {"data": [_loc("loc-en", "en-US", name="Base", description="Desc")]},
    )
    assert iap.run(fake_cli) is True


def test_iap_run_updates_existing_and_recovers_from_409_create(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(iap, "_select_iaps", lambda *_a, **_k: [_iap("iap1"), _iap("iap2", "Pro", "pro.yearly")])
    monkeypatch.setattr(iap, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(iap, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    monkeypatch.setattr(iap.time, "sleep", lambda *_a, **_k: None)

    def iap_locs(iap_id):
        if iap_id == "iap1":
            return {"data": [_loc("loc-en", "en-US", name="Base", description="Desc"), _loc("loc-fr", "fr-FR", name="Old", description="Old")]}
        return {"data": [_loc("loc-en-2", "en-US", name="Base2", description="Desc2")]}

    fake_asc.set_response("get_in_app_purchase_localizations", iap_locs)
    fake_asc.set_response("update_in_app_purchase_localization", {"data": {"id": "ok"}})
    fake_asc.set_response(
        "create_in_app_purchase_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(Exception("409 conflict")),
    )

    assert iap.run(fake_cli) is True
    updates = [c for c in fake_asc.calls if c[0] == "update_in_app_purchase_localization"]
    assert updates
