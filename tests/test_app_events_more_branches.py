import builtins

from app_events_test_helpers import make_event, make_event_loc
from workflows import app_events_translate as aet


class _Resp:
    def __init__(self, payload=None, text="", json_error=False):
        self._payload = payload or {}
        self.text = text
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise RuntimeError("bad json")
        return self._payload


def test_app_events_debug_and_extract_helper_paths(monkeypatch, fake_provider):
    monkeypatch.setattr(aet, "_DEBUG_APP_EVENTS", True)
    monkeypatch.setattr(aet, "print_info", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("no print")))
    aet._debug("hello")

    monkeypatch.setattr(aet, "_DEBUG_APP_EVENTS", False)
    aet._debug_http_error("prefix", Exception("boom"))

    monkeypatch.setattr(aet, "_DEBUG_APP_EVENTS", True)
    err = Exception("http")
    err.response = _Resp(payload={"x": 1}, text="fallback text", json_error=True)
    aet._debug_http_error("prefix", err)

    plain = Exception("plain")
    plain.response = _Resp(json_error=True)
    assert aet._extract_asc_errors(plain) == []
    assert aet._translate_with_min_len(
        fake_provider,
        "src",
        "French",
        max_length=10,
        seed=1,
        refinement="",
        min_len=1,
        field_label="name",
    )

    assert aet._unique_root_match({"fi-FI": "id-fi"}, "") == ""
    assert aet._find_existing_locale_id({"fi-FI": "id-fi"}, "") == ""


def test_select_app_events_tui_label_branches(monkeypatch):
    class UI:
        def available(self):
            return True

        def checkbox(self, *_a, **_k):
            return ["e1"]

    asc = type(
        "ASC",
        (),
        {
            "get_app_events": lambda self, _app_id: {
                "data": [
                    {
                        "id": "e1",
                        "attributes": {
                            "referenceName": "Event One",
                            "badge": "LIVE",
                            "eventState": "ACTIVE",
                            "primaryLocale": "en-US",
                        },
                    }
                ]
            }
        },
    )()
    selected = aet._select_app_events(UI(), asc, "app1")
    assert selected and selected[0]["id"] == "e1"


def test_app_events_run_fallback_and_target_skip_paths(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(aet, "_select_app_events", lambda *_a, **_k: [make_event("event1", primary=None)])
    monkeypatch.setattr(aet, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(aet, "choose_target_locales", lambda *_a, **_k: [])
    monkeypatch.setattr(aet.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")

    fake_asc.set_response("get_app_event_localizations", {"data": []})
    fake_asc.set_response("get_app_event", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("fallback failed")))
    assert aet.run(fake_cli) is True

    fake_asc.set_response("get_app_event_localizations", {"data": [make_event_loc("loc-en", "en-US")]})
    monkeypatch.setattr(aet, "detect_base_language", lambda *_a, **_k: None)
    assert aet.run(fake_cli) is True


def test_app_events_run_conflict_recovery_and_failure_paths(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(aet, "_select_app_events", lambda *_a, **_k: [make_event("event1")])
    monkeypatch.setattr(aet, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(aet, "choose_target_locales", lambda *_a, **_k: ["de-DE", "fr-FR"])
    monkeypatch.setattr(aet.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    monkeypatch.setattr(
        aet,
        "format_progress",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("no progress")),
        raising=False,
    )

    call_count = {"locs": 0}

    def get_event_locs(_event_id):
        call_count["locs"] += 1
        if call_count["locs"] == 1:
            return {"data": [make_event_loc("loc-en", "en-US"), make_event_loc("loc-fr", "fr-FR")]}
        return {"data": [make_event_loc("loc-en", "en-US"), make_event_loc("loc-fr", "fr-FR"), make_event_loc("loc-de", "de-DE")]}

    fake_asc.set_response("get_app_event_localizations", get_event_locs)
    fake_asc.set_response(
        "parallel_map_locales",
        {},
    )

    def fake_parallel(targets, task, progress_action=None, **_kwargs):
        if progress_action == "Translated":
            return {loc: task(loc) for loc in targets}, {"es-ES": "translate fail"}
        return {}, {}

    monkeypatch.setattr(aet, "parallel_map_locales", fake_parallel)

    fake_asc.set_response(
        "create_app_event_localization",
        lambda _event_id, locale, **_kwargs: (_ for _ in ()).throw(Exception("409 create conflict"))
        if locale == "de-DE"
        else {"data": {"id": "created"}},
    )
    fake_asc.set_response(
        "update_app_event_localization",
        lambda loc_id, **_kwargs: (_ for _ in ()).throw(Exception("hard fail")) if loc_id == "loc-fr" else {"data": {"id": loc_id}},
    )
    fake_asc.set_response(
        "get_app_event",
        {"included": [make_event_loc("loc-de", "de-DE", name="Name", short="Short", long="Long text")]},
    )
    fake_asc.set_response("get_app_event_localization", {"data": {"attributes": {"name": "Name", "shortDescription": "Short", "longDescription": "Long text"}}})

    assert aet.run(fake_cli) is True


def test_app_events_run_filtered_targets_empty_after_base_removal(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(aet, "_select_app_events", lambda *_a, **_k: [make_event("event1")])
    monkeypatch.setattr(aet, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(aet, "choose_target_locales", lambda *_a, **_k: ["en-US"])
    monkeypatch.setattr(aet.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    fake_asc.set_response(
        "get_app_event_localizations",
        {"data": [make_event_loc("loc-en", "en-US", name="Name", short="Short", long="Long text")]},
    )
    assert aet.run(fake_cli) is True


def test_app_events_run_update_path_progress_and_clear_errors(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(aet, "_select_app_events", lambda *_a, **_k: [make_event("event1")])
    monkeypatch.setattr(aet, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(aet, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(aet.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    fake_asc.set_response(
        "get_app_event_localizations",
        {"data": [make_event_loc("loc-en", "en-US"), make_event_loc("loc-fr", "fr-FR")]},
    )
    fake_asc.set_response("update_app_event_localization", {"data": {"id": "loc-fr"}})

    def format_progress(completed, _total, _message):
        if completed > 0:
            raise RuntimeError("progress fail")
        return "0/1 Saving locales..."

    real_print = builtins.print

    def fake_print(*args, **kwargs):
        s = args[0] if args else ""
        if isinstance(s, str) and s.startswith("\r") and s.endswith("\r"):
            raise RuntimeError("clear fail")
        return real_print(*args, **kwargs)

    monkeypatch.setattr(aet, "format_progress", format_progress)
    monkeypatch.setattr(aet, "print", fake_print, raising=False)
    assert aet.run(fake_cli) is True


def test_app_events_run_409_refresh_fallback_and_recovered_progress_error(fake_cli, fake_ui, fake_asc, monkeypatch):
    fake_ui.app_id = "app1"
    monkeypatch.setattr(aet, "_select_app_events", lambda *_a, **_k: [make_event("event1")])
    monkeypatch.setattr(aet, "pick_provider", lambda cli: (cli.ai_manager.get_provider("fake"), "fake"))
    monkeypatch.setattr(aet, "choose_target_locales", lambda *_a, **_k: ["fr-FR"])
    monkeypatch.setattr(aet.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    calls = {"locs": 0}

    def get_event_locs(_event_id):
        calls["locs"] += 1
        if calls["locs"] == 1:
            return {"data": [make_event_loc("loc-en", "en-US")]}
        return {"data": []}

    fake_asc.set_response("get_app_event_localizations", get_event_locs)
    fake_asc.set_response(
        "create_app_event_localization",
        lambda *_a, **_k: (_ for _ in ()).throw(Exception("409 create conflict")),
    )
    fake_asc.set_response("update_app_event_localization", {"data": {"id": "loc-fr"}})
    fake_asc.set_response(
        "get_app_event",
        {
            "included": [
                {"type": "other", "id": "x"},
                make_event_loc("loc-fr", "fr-FR", name="Name", short="Short", long="Long text"),
            ]
        },
    )

    def format_progress(completed, _total, _message):
        if completed > 0:
            raise RuntimeError("progress fail")
        return "0/1 Saving locales..."

    monkeypatch.setattr(aet, "format_progress", format_progress)
    assert aet.run(fake_cli) is True
