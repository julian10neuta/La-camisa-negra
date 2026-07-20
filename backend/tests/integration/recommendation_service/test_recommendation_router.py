# Test de integración del router de recomendaciones vía TestClient, con la BD
# (SQLite) y Redis (fakeredis) inyectados por dependency_overrides. Verifica la
# regla estrella: /list NUNCA regenera (cero llamadas a Spotify en el camino de
# lectura); /refresh sí, y delega en el motor (mockeado).
import pytest
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

import shared.database as shared_db
from recommendation_service.routers import recommendation_router as rr
from recommendation_service.dependencies import get_redis
from recommendation_service.services import engine as engine_mod
from shared.models import User, RecommendationPlaylist

pytestmark = pytest.mark.integration

app = FastAPI()
app.include_router(rr.router)
HEADERS = {"X-Spotify-ID": "u1"}


@pytest.fixture()
def client(db_session, fake_redis):
    app.dependency_overrides[shared_db.get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: fake_redis
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_user(db):
    user = User(spotify_id="u1", name="Julian", access_token="a",
                refresh_token="r", token_expiry=datetime(2030, 1, 1))
    db.add(user)
    db.commit()
    return user


def test_list_unknown_user_is_404(client):
    assert client.get("/recommendations/list", headers=HEADERS).status_code == 404


def test_list_without_playlist_returns_empty_and_stale(client, db_session):
    _make_user(db_session)
    r = client.get("/recommendations/list", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["tracks"] == []
    assert body["generated"] is False
    assert body["stale"] is True          # nunca generada → ofrecer generar


def test_list_returns_cached_tracks_without_spotify(client, db_session, fake_redis):
    user = _make_user(db_session)
    last = datetime.utcnow()
    db_session.add(RecommendationPlaylist(
        user_id=user.id, spotify_playlist_id="PL1", period_type="weekly", last_updated=last))
    db_session.commit()
    tracks = [{"spotify_track_id": "t1", "name": "X"}]
    engine_mod.write_cached(fake_redis, user.id, "weekly", tracks, "PL1", last)

    r = client.get("/recommendations/list", params={"limit": 1}, headers=HEADERS)
    body = r.json()
    assert body["tracks"] == tracks
    assert body["generated"] is False
    assert body["stale"] is False         # fresca y completa


@pytest.mark.parametrize("params", [{"period": "yearly"}, {"limit": 0}, {"limit": 999}])
def test_list_invalid_params_are_422(client, params):
    assert client.get("/recommendations/list", params=params, headers=HEADERS).status_code == 422


def test_refresh_delegates_to_engine(client, db_session, monkeypatch):
    _make_user(db_session)

    class FakeToken:
        def __init__(self, redis): ...
        async def get_token(self, sid): return "tok"

    class FakeEngine:
        def __init__(self, db, redis): ...
        async def generate(self, user_id, token, period, limit):
            return {"generated": True, "tracks": [], "period": period, "limit": limit}

    monkeypatch.setattr(rr, "TokenService", FakeToken)
    monkeypatch.setattr(rr, "RecommendationEngine", FakeEngine)

    r = client.post("/recommendations/refresh", params={"period": "monthly"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json() == {"generated": True, "tracks": [], "period": "monthly", "limit": 15}
