import types

from workflows import game_center_localizations as gcl


class Resp:
    def __init__(self, content=b"", headers=None, status_ok=True):
        self.content = content
        self.headers = headers or {}
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise RuntimeError("bad status")


def test_download_origin_image_no_asset_url():
    data, file_name, content_type, status, err = gcl._download_origin_image({"attributes": {"imageAsset": {}}})
    assert status == "no_asset_url"
    assert data is None


def test_download_origin_image_success(monkeypatch):
    origin = {
        "attributes": {
            "fileName": "sample.png",
            "imageAsset": {"templateUrl": "https://cdn/{w}x{h}.{f}", "width": 100, "height": 100},
        }
    }

    monkeypatch.setattr(gcl.requests, "get", lambda *_a, **_k: Resp(content=b"img", headers={"Content-Type": "image/png"}))

    data, file_name, content_type, status, err = gcl._download_origin_image(origin)
    assert status == "ok"
    assert data == b"img"
    assert file_name.endswith(".png")


def test_copy_localization_image_basic_guards():
    asc = types.SimpleNamespace()

    assert gcl._copy_localization_image(asc, "achievement", None, "target", None)[0] == "no_origin_payload"
    assert gcl._copy_localization_image(asc, "achievement", (b"x", "a.png", "image/png"), None, None)[0] == "no_target_id"


def test_copy_localization_image_target_has_image(monkeypatch):
    asc = types.SimpleNamespace()
    monkeypatch.setattr(gcl, "_fetch_image_resource", lambda *_a, **_k: {"id": "img"})

    result, err, img_id = gcl._copy_localization_image(asc, "achievement", (b"x", "a.png", "image/png"), "target", None)
    assert result == "target_has_image"


def test_copy_localization_image_upload_and_commit(monkeypatch):
    calls = {"commit": 0}
    asc = types.SimpleNamespace(update_game_center_achievement_image=lambda *_a, **_k: calls.__setitem__("commit", calls["commit"] + 1))

    monkeypatch.setattr(gcl, "_fetch_image_resource", lambda *_a, **_k: None)
    monkeypatch.setattr(
        gcl,
        "_create_image_resource",
        lambda *_a, **_k: {"data": {"id": "img1", "attributes": {"uploadOperations": [{"url": "https://u", "method": "PUT"}]}}},
    )
    monkeypatch.setattr(gcl, "_upload_operations", lambda *_a, **_k: None)

    result, err, img_id = gcl._copy_localization_image(asc, "achievement", (b"x", "a.png", "image/png"), "target", None)
    assert result == "upload_complete"
    assert img_id == "img1"
    assert calls["commit"] == 1


def test_copy_localization_image_upload_failed(monkeypatch):
    asc = types.SimpleNamespace()

    monkeypatch.setattr(gcl, "_fetch_image_resource", lambda *_a, **_k: None)
    monkeypatch.setattr(
        gcl,
        "_create_image_resource",
        lambda *_a, **_k: {"data": {"id": "img1", "attributes": {"uploadOperations": [{"url": "https://u", "method": "PUT"}]}}},
    )
    monkeypatch.setattr(gcl, "_upload_operations", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("upload failed")))

    result, err, img_id = gcl._copy_localization_image(asc, "achievement", (b"x", "a.png", "image/png"), "target", None)
    assert result == "upload_failed"
    assert "upload failed" in err
