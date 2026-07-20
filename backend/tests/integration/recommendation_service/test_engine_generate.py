# Test de integración del PIPELINE completo del motor: engine.RecommendationEngine.generate
# Contra SQLite en memoria + fakeredis, con Deezer y Spotify MOCKEADOS (AsyncMock).
# Ejercita: semillas desde el perfil, Deezer (similares + top), emparejado con
# Spotify, round-robin, exclusión de lo ya visto y sincronización de la playlist.
import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from shared.models import User, Song, Interaction, RecommendationPlaylist
from recommendation_service.services.engine import RecommendationEngine, read_cached

pytestmark = pytest.mark.integration


def _sp_track(tid, name, artist):
    return {
        "id": tid, "name": name, "artists": [{"name": artist}],
        "album": {"name": "Alb", "images": [{"url": "cover"}]}, "duration_ms": 1000,
    }


@pytest.fixture()
def user_with_like(db_session):
    user = User(spotify_id="u1", name="Julian", access_token="a",
                refresh_token="r", token_expiry=datetime(2030, 1, 1))
    seed_song = Song(spotify_track_id="seedA", name="Semilla", artist="Feid", genres="reggaeton")
    db_session.add_all([user, seed_song])
    db_session.commit()
    db_session.add(Interaction(user_id=user.id, song_id=seed_song.id, type="like"))
    db_session.commit()
    return user


def _engine_with_mocks(db, redis, related, tops, matches):
    """Motor con Deezer/Spotify falsos. `matches` mapea título -> track de Spotify."""
    eng = RecommendationEngine(db, redis)

    eng.deezer = AsyncMock()
    eng.deezer.search_artist = AsyncMock(return_value={"id": "dzFeid", "name": "Feid"})
    eng.deezer.get_related_artists = AsyncMock(return_value=related)
    eng.deezer.get_artist_top = AsyncMock(side_effect=lambda aid, limit=2: tops.get(aid, []))

    async def _search(query, token, limit=1):
        # Devuelve el track cuyo título aparece en la query de búsqueda.
        for title, track in matches.items():
            if title in query:
                return [track]
        return []

    eng.spotify = AsyncMock()
    eng.spotify.get_top_artists = AsyncMock(return_value=[])   # sin relleno de semillas
    eng.spotify.search_tracks = AsyncMock(side_effect=_search)
    eng.spotify.create_playlist = AsyncMock(return_value={"id": "PLnew"})
    eng.spotify.add_tracks_to_playlist = AsyncMock()
    eng.spotify.get_playlist_tracks = AsyncMock(return_value=[])
    eng.spotify.remove_tracks_from_playlist = AsyncMock()
    return eng


async def test_generate_produces_recommendations_and_syncs_playlist(db_session, fake_redis, user_with_like):
    related = [{"id": "r1", "name": "Blessd"}, {"id": "r2", "name": "Ryan Castro"}]
    tops = {
        "r1": [{"title": "Cancion1", "artist": "Blessd"}],
        "r2": [{"title": "Cancion2", "artist": "Ryan Castro"}],
    }
    matches = {
        "Cancion1": _sp_track("sp1", "Cancion1", "Blessd"),
        "Cancion2": _sp_track("sp2", "Cancion2", "Ryan Castro"),
    }
    eng = _engine_with_mocks(db_session, fake_redis, related, tops, matches)

    result = await eng.generate(user_with_like.id, "token", period="weekly", limit=2)

    assert result["generated"] is True
    assert [t["spotify_track_id"] for t in result["tracks"]] == ["sp1", "sp2"]
    assert result["playlist_id"] == "PLnew"
    # Se creó la fila de playlist y se sincronizó en Spotify.
    eng.spotify.create_playlist.assert_awaited_once()
    eng.spotify.add_tracks_to_playlist.assert_awaited_once()
    assert db_session.query(RecommendationPlaylist).count() == 1
    # Y quedó cacheada para que la próxima lectura no toque Spotify.
    assert read_cached(fake_redis, user_with_like.id, "weekly")["tracks"] == result["tracks"]


async def test_generate_excludes_already_seen_tracks(db_session, fake_redis, user_with_like):
    # El match de Spotify devuelve una canción que el usuario YA tocó (seedA):
    # debe excluirse y no acabar en las recomendaciones.
    related = [{"id": "r1", "name": "Blessd"}]
    tops = {"r1": [{"title": "Repetida", "artist": "Blessd"}]}
    matches = {"Repetida": _sp_track("seedA", "Repetida", "Blessd")}  # id ya excluido
    eng = _engine_with_mocks(db_session, fake_redis, related, tops, matches)

    result = await eng.generate(user_with_like.id, "token", period="weekly", limit=5)

    # La única candidata era una canción ya vista → se excluye → lista vacía.
    # (Sí hubo semillas, así que el motor sí corrió el pipeline: generated=True,
    #  pero sin playlist porque no había nada que sincronizar.)
    assert result["tracks"] == []
    assert result["playlist_id"] is None
    eng.spotify.create_playlist.assert_not_awaited()


async def test_generate_with_no_seeds_returns_empty(db_session, fake_redis):
    # Usuario sin interacciones ni artistas top → no hay semillas → lista vacía.
    user = User(spotify_id="u2", name="Nadie", access_token="a",
                refresh_token="r", token_expiry=datetime(2030, 1, 1))
    db_session.add(user)
    db_session.commit()
    eng = _engine_with_mocks(db_session, fake_redis, related=[], tops={}, matches={})

    result = await eng.generate(user.id, "token", period="monthly", limit=10)
    assert result["generated"] is False
    assert result["tracks"] == []
    assert result["period"] == "monthly"
