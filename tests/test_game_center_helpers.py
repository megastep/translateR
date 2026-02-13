import builtins

from workflows import game_center_localizations as gcl


def test_choose_resource_types_non_tui(monkeypatch):
    class UI:
        def available(self):
            return False

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "1,2,4")
    out = gcl._choose_resource_types(UI())
    assert out == ["achievement", "leaderboard", "challenge"]


def test_label_merge_and_version_helpers():
    ach = {"id": "a1", "attributes": {"referenceName": "Winner", "vendorIdentifier": "VID", "points": 50}}
    assert "50 pts" in gcl._label_item(ach, "achievement")

    merged = gcl._merge_items([{"id": "1"}], [{"id": "1"}, {"id": "2"}])
    assert sorted([x["id"] for x in merged]) == ["1", "2"]

    assert gcl._parse_version_string("1.2.3") == (1, 2, 3)
    assert gcl._parse_version_string("1.a") is None

    latest = gcl._pick_latest_version(
        [
            {"id": "v1", "attributes": {"version": "1.2.0"}},
            {"id": "v2", "attributes": {"version": "1.10.0"}},
        ]
    )
    assert latest["id"] == "v2"


def test_image_url_filename_and_content_type_helpers():
    asset = {"templateUrl": "https://x/{w}x{h}.png", "width": 640, "height": 480}
    assert gcl._image_url_from_asset(asset) == "https://x/640x480.png"
    assert gcl._filename_from_url("https://cdn.example.com/a/b/image.jpg") == "image.jpg"
    assert gcl._ext_from_content_type("image/jpeg; charset=utf-8") == "jpg"


def test_upload_operations_uses_chunks(monkeypatch):
    calls = []

    class Resp:
        def raise_for_status(self):
            return None

    def fake_request(method, url, data=None, headers=None):
        calls.append((method, url, data, headers))
        return Resp()

    monkeypatch.setattr(gcl.requests, "request", fake_request)

    ops = [
        {
            "method": "PUT",
            "url": "https://upload/1",
            "offset": 0,
            "length": 4,
            "requestHeaders": [{"name": "x-test", "value": "1"}],
        },
        {
            "method": "PUT",
            "url": "https://upload/2",
            "offset": 4,
            "length": 4,
            "requestHeaders": [],
        },
    ]
    gcl._upload_operations(ops, b"abcdefgh", content_type="image/png")

    assert calls[0][2] == b"abcd"
    assert calls[1][2] == b"efgh"


def test_select_items_and_base_locale_non_tui(monkeypatch):
    class UI:
        def available(self):
            return False

    items = [
        {"id": "i1", "attributes": {"referenceName": "One"}},
        {"id": "i2", "attributes": {"referenceName": "Two"}},
    ]

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "all")
    selected = gcl._select_items(UI(), items, "achievement")
    assert len(selected) == 2

    monkeypatch.setattr(builtins, "input", lambda *_a, **_k: "")
    base = gcl._select_base_locale(UI(), ["en-US", "fr-FR"], "en-US")
    assert base == "en-US"


def test_translate_required_retries_on_empty(fake_provider):
    calls = {"n": 0}

    def fake_translate(*_args, **_kwargs):
        calls["n"] += 1
        return "" if calls["n"] == 1 else "translated"

    fake_provider.translate = fake_translate
    out = gcl._translate_required(fake_provider, "src", "French", "", 1, "name", 30)
    assert out == "translated"
    assert calls["n"] == 2
