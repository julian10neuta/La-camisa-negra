# Test de integración de SongService (music_service): el cacheo perezoso de
# canciones. Contra SQLite, con Spotify mockeado. La propiedad clave: solo se
# pide a Spotify cuando la canción NO está ya en la BD.
import pytest
from unittest.mock import AsyncMock

from shared.models import Song
from music_service.services.song_service import SongService

pytestmark = pytest.mark.integration


def _track(tid, name="N", artist="A"):
    return {"id": tid, "name": name, "artists": [{"name": artist}],
            "album": {"name": "Alb", "images": [{"url": "c"}]}, "duration_ms": 1000}


@pytest.fixture()
def service(db_session):
    spotify = AsyncMock()
    return SongService(db=db_session, spotify_service=spotify), spotify


async def test_get_or_cache_returns_existing_without_calling_spotify(db_session, service):
    svc, spotify = service
    db_session.add(Song(spotify_track_id="t1", name="Ya", artist="Feid"))
    db_session.commit()

    song = await svc.get_or_cache("t1", "token")
    assert song.spotify_track_id == "t1"
    spotify.get_track.assert_not_awaited()      # ya estaba: cero llamadas


async def test_get_or_cache_fetches_and_persists_when_missing(db_session, service):
    svc, spotify = service
    spotify.get_track = AsyncMock(return_value=_track("t2", "Nueva", "Blessd"))

    song = await svc.get_or_cache("t2", "token")
    assert song.spotify_track_id == "t2"
    spotify.get_track.assert_awaited_once()
    # y quedó persistida en la BD para la próxima vez
    assert db_session.query(Song).filter_by(spotify_track_id="t2").count() == 1


async def test_get_or_cache_many_mixes_existing_and_new(db_session, service):
    svc, _ = service
    db_session.add(Song(spotify_track_id="old", name="Vieja", artist="A"))
    db_session.commit()

    tracks = [_track("old"), _track("new1"), _track("new2")]
    result = await svc.get_or_cache_many(tracks, "token")

    ids = {s.spotify_track_id for s in result}
    assert ids == {"old", "new1", "new2"}
    assert db_session.query(Song).count() == 3   # las 2 nuevas se crearon


async def test_search_delegates_to_spotify(service):
    svc, spotify = service
    spotify.search_tracks = AsyncMock(return_value=[{"id": "x"}])
    assert await svc.search("juanes", "token") == [{"id": "x"}]
    spotify.search_tracks.assert_awaited_once()
