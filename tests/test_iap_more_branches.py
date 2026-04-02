import builtins

from workflows import iap_translate as iap


def _iap(iap_id="iap1", name="Premium", product_id="premium.monthly", iap_type=None):
    attrs = {"referenceName": name, "productId": product_id}
    if iap_type:
        attrs["inAppPurchaseType"] = iap_type
    return {"id": iap_id, "type": "inAppPurchasesV2", "attributes": attrs}


def _loc(loc_id, locale, name="Base", description="Desc"):
    return {"id": loc_id, "attributes": {"locale": locale, "name": name, "description": description}}


def _setup_run(monkeypatch, fake_ui, fake_asc, iap_items=None):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(iap, "_select_iaps", lambda *_a, **_k: iap_items or [_iap()])
    monkeypatch.setattr(iap, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(iap, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(iap.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")


def test_select_iaps_non_tui_includes_iap_type_label(monkeypatch):
    class NonTUI:
        def available(self):
            return False

    asc = type(
        "ASC",
        (),
        {
            "get_in_app_purchases": lambda *_a, **_k: {
                "data": [_iap("iap1", iap_type="AUTO_RENEWABLE_SUBSCRIPTION")]
            }
        },
    )()
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1")
    selected = iap._select_iaps(NonTUI(), asc, "app1")
    assert [it["id"] for it in selected] == ["iap1"]


def test_iap_run_all_supported_languages_already_localized(fake_cli, fake_ui, fake_asc, monkeypatch):
    _setup_run(monkeypatch, fake_ui, fake_asc)
    monkeypatch.setattr(iap, "APP_STORE_LOCALES", {"en-US": "English", "fr-FR": "French"})
    fake_asc.set_response(
        "get_in_app_purchase_localizations",
        {"data": [_loc("loc-en", "en-US"), _loc("loc-fr", "fr-FR", name="Nom", description="Desc FR")]},
    )
    assert iap.run(fake_cli) is True


def test_iap_run_empty_name_progress_update_and_clear_line_exception(fake_cli, fake_ui, fake_asc, monkeypatch):
    _setup_run(monkeypatch, fake_ui, fake_asc)
    fake_asc.set_response("get_in_app_purchase_localizations", {"data": [_loc("loc-en", "en-US")]})
    monkeypatch.setattr(
        iap,
        "parallel_map_locales",
        lambda *_a, **_k: ({"fr-FR": {"name": "", "description": ""}}, {}),
    )
    monkeypatch.setattr(iap, "format_progress", lambda c, t, m: f"{c}/{t}:{m}")

    real_print = builtins.print

    def fake_print(*args, **kwargs):
        s = args[0] if args else ""
        if isinstance(s, str) and s.startswith("\r") and s.endswith("\r"):
            raise RuntimeError("clear failed")
        return real_print(*args, **kwargs)

    monkeypatch.setattr(iap, "print", fake_print, raising=False)
    assert iap.run(fake_cli) is True


def test_iap_run_success_progress_update_exception_branch(fake_cli, fake_ui, fake_asc, monkeypatch):
    _setup_run(monkeypatch, fake_ui, fake_asc)
    fake_asc.set_response("get_in_app_purchase_localizations", {"data": [_loc("loc-en", "en-US")]})

    def format_progress(completed, _total, message):
        if completed > 0 and message.startswith("Saved"):
            raise RuntimeError("progress failed")
        return "progress"

    monkeypatch.setattr(iap, "format_progress", format_progress)
    assert iap.run(fake_cli) is True


def test_iap_run_create_409_recovery_success_and_refresh_failure(fake_cli, fake_ui, fake_asc, monkeypatch):
    _setup_run(monkeypatch, fake_ui, fake_asc, iap_items=[_iap("iap-success"), _iap("iap-fail", "Pro", "pro.yearly")])
    call_counts = {"success": 0, "fail": 0}

    def get_locs(iap_id):
        if iap_id == "iap-success":
            call_counts["success"] += 1
            if call_counts["success"] == 1:
                return {"data": [_loc("loc-en", "en-US")]}
            return {"data": [_loc("loc-en", "en-US"), _loc("loc-fr", "fr-FR", name="Nom", description="Desc FR")]}
        if iap_id == "iap-fail":
            call_counts["fail"] += 1
            if call_counts["fail"] == 1:
                return {"data": [_loc("loc-en-2", "en-US")]}
            raise RuntimeError("refresh failed")
        return {"data": []}

    fake_asc.set_response("get_in_app_purchase_localizations", get_locs)
    fake_asc.set_response(
        "create_in_app_purchase_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(Exception("409 conflict")),
    )
    fake_asc.set_response("update_in_app_purchase_localization", {"data": {"id": "updated"}})
    monkeypatch.setattr(iap, "format_progress", lambda c, t, m: f"{c}/{t}:{m}")
    assert iap.run(fake_cli) is True


def test_iap_run_reuses_target_language_confirmation_for_matching_iaps(fake_cli, fake_ui, fake_asc, monkeypatch):
    _setup_run(monkeypatch, fake_ui, fake_asc, iap_items=[_iap("iap1"), _iap("iap2", "Pro", "pro.yearly")])
    prompts = {"scope": 0, "targets": 0}

    def pick_scope(*_args, **_kwargs):
        prompts["scope"] += 1
        return "missing"

    def choose_targets(*_args, **_kwargs):
        prompts["targets"] += 1
        return ["fr-FR"]

    monkeypatch.setattr(iap, "pick_locale_scope", pick_scope)
    monkeypatch.setattr(iap, "choose_target_locales", choose_targets)
    fake_asc.set_response(
        "get_in_app_purchase_localizations",
        lambda _iap_id: {"data": [_loc("loc-en", "en-US", name="Base", description="Desc")]},
    )
    fake_asc.set_response("create_in_app_purchase_localization", {"data": {"id": "created"}})

    assert iap.run(fake_cli) is True
    assert prompts == {"scope": 1, "targets": 1}

    creates = [c for c in fake_asc.calls if c[0] == "create_in_app_purchase_localization"]
    assert len(creates) == 2


def test_iap_run_reasks_for_target_languages_when_iaps_materially_differ(fake_cli, fake_ui, fake_asc, monkeypatch):
    _setup_run(monkeypatch, fake_ui, fake_asc, iap_items=[_iap("iap1"), _iap("iap2", "Pro", "pro.yearly")])
    prompts = {"scope": 0, "targets": 0}

    def pick_scope(*_args, **_kwargs):
        prompts["scope"] += 1
        return "missing"

    def choose_targets(*_args, **_kwargs):
        prompts["targets"] += 1
        return ["fr-FR"]

    monkeypatch.setattr(iap, "pick_locale_scope", pick_scope)
    monkeypatch.setattr(iap, "choose_target_locales", choose_targets)

    def get_locs(iap_id):
        if iap_id == "iap1":
            return {"data": [_loc("loc-en", "en-US", name="Base", description="Desc")]}
        return {
            "data": [
                _loc("loc-en-2", "en-US", name="Base", description="Desc"),
                _loc("loc-fr-2", "fr-FR", name="Nom", description="Desc FR"),
            ]
        }

    fake_asc.set_response("get_in_app_purchase_localizations", get_locs)
    fake_asc.set_response("create_in_app_purchase_localization", {"data": {"id": "created"}})

    assert iap.run(fake_cli) is True
    assert prompts == {"scope": 2, "targets": 2}
