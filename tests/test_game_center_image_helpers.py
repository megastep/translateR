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


def test_download_origin_image_all_candidates_fail(monkeypatch):
    origin = {
        "attributes": {
            "fileName": "sample",
            "imageAsset": {"templateUrl": "https://cdn/{w}x{h}.{f}", "width": 64, "height": 64},
        }
    }

    def fail_get(*_a, **_k):
        raise RuntimeError("download failed")

    monkeypatch.setattr(gcl.requests, "get", fail_get)
    data, file_name, content_type, status, err = gcl._download_origin_image(origin)
    assert status == "download_failed"
    assert data is None
    assert "download failed" in err
    assert file_name is None
    assert content_type is None


def test_download_origin_image_appends_extension_when_filename_has_no_dot(monkeypatch):
    origin = {
        "attributes": {
            "fileName": "sample",
            "imageAsset": {"templateUrl": "https://cdn/{w}x{h}.{f}", "width": 128, "height": 128},
        }
    }

    monkeypatch.setattr(
        gcl.requests,
        "get",
        lambda *_a, **_k: Resp(content=b"img", headers={"Content-Type": "image/jpeg"}),
    )

    data, file_name, content_type, status, err = gcl._download_origin_image(origin)
    assert status == "ok"
    assert file_name == "sample.jpg"
    assert data == b"img"
    assert content_type == "image/jpeg"
    assert err is None


def test_copy_localization_image_no_upload_ops(monkeypatch):
    asc = types.SimpleNamespace()
    monkeypatch.setattr(gcl, "_fetch_image_resource", lambda *_a, **_k: None)
    monkeypatch.setattr(
        gcl,
        "_create_image_resource",
        lambda *_a, **_k: {"data": {"id": "img1", "attributes": {}}},
    )

    result, err, img_id = gcl._copy_localization_image(asc, "achievement", (b"x", "a.png", "image/png"), "target", None)
    assert result == "no_upload_ops"
    assert err is None
    assert img_id == "img1"


def test_copy_localization_image_commit_failed_for_non_achievement(monkeypatch):
    monkeypatch.setattr(gcl, "_fetch_image_resource", lambda *_a, **_k: None)
    monkeypatch.setattr(
        gcl,
        "_create_image_resource",
        lambda *_a, **_k: {"data": {"id": "img1", "attributes": {"uploadOperations": [{"url": "https://u", "method": "PUT"}]}}},
    )
    monkeypatch.setattr(gcl, "_upload_operations", lambda *_a, **_k: None)

    for kind, method_name in [
        ("leaderboard", "update_game_center_leaderboard_image"),
        ("activity", "update_game_center_activity_image"),
        ("challenge", "update_game_center_challenge_image"),
    ]:
        asc = types.SimpleNamespace(
            **{
                method_name: lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("commit failed")),
            }
        )
        result, err, img_id = gcl._copy_localization_image(asc, kind, (b"x", "a.png", "image/png"), "target", "ver1")
        assert result == "commit_failed"
        assert "commit failed" in err
        assert img_id == "img1"
