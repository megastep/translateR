import builtins

from app_events_test_helpers import make_event, make_event_loc
from workflows import app_events_translate as aet


def test_app_events_run_returns_on_cancel_empty_selection_or_provider(fake_cli, fake_ui, monkeypatch):
    fake_ui.app_id = None
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    assert aet.run(fake_cli) is True

    fake_ui.app_id = "app1"
    monkeypatch.setattr(aet, "_select_app_events", lambda *_a, **_k: [])
    assert aet.run(fake_cli) is True

    monkeypatch.setattr(aet, "_select_app_events", lambda *_a, **_k: [make_event()])
    monkeypatch.setattr(aet, "pick_provider", lambda *_a, **_k: (None, None))
    assert aet.run(fake_cli) is True


def test_app_events_run_skips_missing_id_and_missing_localizations(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(aet, "_select_app_events", lambda *_a, **_k: [make_event(event_id=""), make_event("event2")])
    monkeypatch.setattr(aet, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(aet, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(aet.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    fake_asc.set_response("get_app_event_localizations", {"data": []})
    fake_asc.set_response("get_app_event", {"included": []})

    assert aet.run(fake_cli) is True


def test_app_events_run_prompts_for_missing_base_fields_and_skips(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    fake_ui.text_values.extend(["", ""])
    fake_ui.multiline_values.append("")
    monkeypatch.setattr(aet, "_select_app_events", lambda *_a, **_k: [make_event("event1")])
    monkeypatch.setattr(aet, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(aet.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    fake_asc.set_response("get_app_event_localizations", {"data": [make_event_loc("loc-en", "en-US", name="", short="", long="")]})

    assert aet.run(fake_cli) is True


def test_app_events_run_recovers_from_409_update_conflict_via_fetch_match(
    fake_cli, fake_ui, fake_asc, monkeypatch
):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(aet, "_select_app_events", lambda *_a, **_k: [make_event("event1")])
    monkeypatch.setattr(aet, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(aet, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(
        aet,
        "parallel_map_locales",
        lambda *_a, **_k: (
            {"fr-FR": {"name": "Nom FR", "shortDescription": "Court FR", "longDescription": "Description FR"}},
            {"de-DE": "translation failed"},
        ),
    )
    monkeypatch.setattr(aet.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    monkeypatch.setattr(aet, "_DEBUG_APP_EVENTS", True)
    debug_lines = []
    monkeypatch.setattr(aet, "_debug", lambda msg: debug_lines.append(msg))

    calls = {"locs": 0}

    def get_event_locs(_event_id):
        calls["locs"] += 1
        if calls["locs"] == 1:
            return {"data": [make_event_loc("loc-en", "en-US")]}
        return {"data": []}

    fake_asc.set_response("get_app_event_localizations", get_event_locs)
    fake_asc.set_response(
        "get_app_event",
        {
            "included": [
                make_event_loc("loc-fr", "fr-FR", name="Nom FR", short="Court FR", long="Description FR"),
            ]
        },
    )
    fake_asc.set_response(
        "create_app_event_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(Exception("409 create conflict")),
    )
    fake_asc.set_response(
        "update_app_event_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(Exception("409 update conflict")),
    )
    fake_asc.set_response(
        "get_app_event_localization",
        {"data": {"attributes": {"name": "Nom FR", "shortDescription": "Court FR", "longDescription": "Description FR"}}},
    )

    assert aet.run(fake_cli) is True
    assert debug_lines
