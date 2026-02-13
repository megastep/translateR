from app_store_client import AppStoreConnectClient


def test_game_center_create_and_update_localization_payloads(monkeypatch):
    sent = []

    def fake_request(self, method, endpoint, params=None, data=None, max_retries=3):
        sent.append((method, endpoint, data))
        return {"data": {"id": "ok"}}

    monkeypatch.setattr(AppStoreConnectClient, "_request", fake_request)
    client = AppStoreConnectClient("kid", "issuer", "pk")

    client.create_game_center_achievement_localization("ach1", "fr-FR", "Nom", "Avant", "Apres")
    client.update_game_center_achievement_localization("loc1", name="Nom2")
    client.create_game_center_leaderboard_localization("lb1", "fr-FR", "Nom", description="Desc")
    client.update_game_center_leaderboard_localization("loc2", description="Desc2")
    client.create_game_center_activity_localization("ver1", "fr-FR", "Nom", description="Desc")
    client.update_game_center_activity_localization("loc3", name="Nom")
    client.create_game_center_challenge_localization("ver2", "fr-FR", "Nom", description="Desc")
    client.update_game_center_challenge_localization("loc4", name="Nom")

    endpoints = [e for _m, e, _d in sent]
    assert "v1/gameCenterAchievementLocalizations" in endpoints
    assert "v1/gameCenterLeaderboardLocalizations" in endpoints
    assert "v1/gameCenterActivityLocalizations" in endpoints
    assert "v1/gameCenterChallengeLocalizations" in endpoints


def test_game_center_update_without_attrs_falls_back_to_get(monkeypatch):
    seen = []

    def fake_request(self, method, endpoint, params=None, data=None, max_retries=3):
        seen.append((method, endpoint))
        return {"data": {"id": "ok"}}

    monkeypatch.setattr(AppStoreConnectClient, "_request", fake_request)
    client = AppStoreConnectClient("kid", "issuer", "pk")

    client.update_game_center_achievement_localization("locA")
    client.update_game_center_leaderboard_localization("locB")
    client.update_game_center_activity_localization("locC")
    client.update_game_center_challenge_localization("locD")

    assert ("GET", "v1/gameCenterAchievementLocalizations/locA") in seen
    assert ("GET", "v1/gameCenterLeaderboardLocalizations/locB") in seen
    assert ("GET", "v1/gameCenterActivityLocalizations/locC") in seen
    assert ("GET", "v1/gameCenterChallengeLocalizations/locD") in seen


def test_game_center_image_create_endpoints(monkeypatch):
    sent = []

    def fake_request(self, method, endpoint, params=None, data=None, max_retries=3):
        sent.append((method, endpoint, data))
        return {"data": {"id": "img"}}

    monkeypatch.setattr(AppStoreConnectClient, "_request", fake_request)
    client = AppStoreConnectClient("kid", "issuer", "pk")

    client.create_game_center_achievement_image("loc1", "a.png", 123)
    client.create_game_center_leaderboard_image("loc2", "b.png", 123)
    client.create_game_center_activity_image("loc3", "ver1", "c.png", 123)
    client.create_game_center_challenge_image("loc4", "ver2", "d.png", 123)

    endpoints = [e for _m, e, _d in sent]
    assert "v1/gameCenterAchievementImages" in endpoints
    assert "v1/gameCenterLeaderboardImages" in endpoints
    assert "v1/gameCenterActivityImages" in endpoints
    assert "v1/gameCenterChallengeImages" in endpoints
