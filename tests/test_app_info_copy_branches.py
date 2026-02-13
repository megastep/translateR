import builtins

from workflows import app_info, copy


def test_app_info_run_early_exit_paths(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = None
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert app_info.run(fake_cli) is True

    fake_ui.app_id = "app1"
    fake_asc.set_response("find_primary_app_info_id", None)
    assert app_info.run(fake_cli) is True

    fake_asc.set_response("find_primary_app_info_id", "app-info-1")
    fake_asc.set_response("get_app_info_localizations", {"data": [{"id": "loc-en", "attributes": {"locale": "en-US"}}]})
    fake_asc.set_response("get_app_info_localization", {"data": {"attributes": {"name": "", "subtitle": ""}}})
    assert app_info.run(fake_cli) is True


def test_app_info_run_target_provider_and_save_failure_paths(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.checkbox_values.append(["fr-FR"])
    fake_asc.set_response("find_primary_app_info_id", "app-info-1")
    fake_asc.set_response("get_app_info_localizations", {"data": [{"id": "loc-en", "attributes": {"locale": "en-US"}}]})
    fake_asc.set_response("get_app_info_localization", {"data": {"attributes": {"name": "Base", "subtitle": "Sub"}}})
    monkeypatch.setattr(app_info, "pick_provider", lambda *_a, **_k: (None, None))
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert app_info.run(fake_cli) is True

    monkeypatch.setattr(app_info, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    fake_asc.set_response(
        "create_app_info_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(app_info.time, "sleep", lambda *_a, **_k: None)
    assert app_info.run(fake_cli) is True


def test_copy_run_skip_branches(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = None
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert copy.run(fake_cli) is True

    fake_ui.app_id = "app1"
    monkeypatch.setattr(copy, "select_platforms", lambda *_a, **_k: None)
    assert copy.run(fake_cli) is True

    monkeypatch.setattr(copy, "select_platforms", lambda *_a, **_k: {"IOS": {"id": "ver-target", "attributes": {"versionString": "2.0"}}})
    monkeypatch.setattr(copy, "pick_version_for_platform", lambda *_a, **_k: None)
    assert copy.run(fake_cli) is True


def test_copy_run_target_validation_and_empty_source(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(copy, "select_platforms", lambda *_a, **_k: {"IOS": {"id": "ver-target", "attributes": {"versionString": "2.0"}}})
    picks = iter(
        [
            {"id": "same", "attributes": {"versionString": "1.0"}},
            {"id": "same", "attributes": {"versionString": "1.0"}},
            {"id": "src", "attributes": {"versionString": "1.0"}},
            {"id": "dst", "attributes": {"versionString": "2.0"}},
        ]
    )
    monkeypatch.setattr(copy, "pick_version_for_platform", lambda *_a, **_k: next(picks))
    fake_asc.set_response("get_app_store_version_localizations", {"data": []})
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert copy.run(fake_cli) is True
