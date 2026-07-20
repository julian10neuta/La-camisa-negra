# Tests de integración de InteractionService: la lógica de likes/dislikes/playback
# corriendo contra una BD real (SQLite en memoria), con song_service y
# spotify_service MOCKEADOS (no queremos tocar Spotify ni la caché de canciones).
#
# Marca `integration` porque cruza la frontera de la BD.
import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from shared.models import User, Song, Interaction
from music_service.services.interaction_service import InteractionService

pytestmark = pytest.mark.integration


@pytest.fixture()
def user_and_song(db_session):
    user = User(spotify_id="u1", name="Julian", access_token="a",
                refresh_token="r", token_expiry=datetime(2030, 1, 1))
    song = Song(spotify_track_id="track1", name="La Camisa Negra", artist="Juanes")
    db_session.add_all([user, song])
    db_session.commit()
    return user, song


@pytest.fixture()
def service(db_session, user_and_song):
    """InteractionService con la BD real y las dependencias externas mockeadas.
    song_service.get_or_cache siempre devuelve la canción ya sembrada."""
    _, song = user_and_song
    song_service = AsyncMock()
    song_service.get_or_cache = AsyncMock(return_value=song)
    spotify = AsyncMock()
    return InteractionService(db=db_session, song_service=song_service, spotify_service=spotify)


async def test_add_like_creates_row_and_mirrors_to_spotify(db_session, service, user_and_song):
    user, song = user_and_song
    await service.add_like(user.id, "track1", "token")

    likes = db_session.query(Interaction).filter_by(type="like").all()
    assert len(likes) == 1
    assert likes[0].song_id == song.id
    service.spotify_service.add_to_liked_songs.assert_awaited_once()


async def test_add_like_is_idempotent(db_session, service, user_and_song):
    user, _ = user_and_song
    await service.add_like(user.id, "track1", "token")
    await service.add_like(user.id, "track1", "token")   # segundo like, mismo track
    assert db_session.query(Interaction).filter_by(type="like").count() == 1


async def test_like_removes_previous_dislike(db_session, service, user_and_song):
    user, song = user_and_song
    db_session.add(Interaction(user_id=user.id, song_id=song.id, type="dislike"))
    db_session.commit()

    await service.add_like(user.id, "track1", "token")

    # Exclusión mutua: ya no queda dislike, sí un like.
    assert db_session.query(Interaction).filter_by(type="dislike").count() == 0
    assert db_session.query(Interaction).filter_by(type="like").count() == 1


async def test_add_dislike_removes_like_and_unmirrors(db_session, service, user_and_song):
    user, song = user_and_song
    db_session.add(Interaction(user_id=user.id, song_id=song.id, type="like"))
    db_session.commit()

    await service.add_dislike(user.id, "track1", "token")

    assert db_session.query(Interaction).filter_by(type="like").count() == 0
    assert db_session.query(Interaction).filter_by(type="dislike").count() == 1
    # Quitar el like debe retirarlo también de las Liked Songs de Spotify.
    service.spotify_service.remove_from_liked_songs.assert_awaited_once()


async def test_register_playback_below_threshold_saves_nothing(db_session, service, user_and_song):
    user, _ = user_and_song
    result = await service.register_playback(
        user.id, "track1", seconds_played=3, reached_end=False,
        was_skipped=True, access_token="token",
    )
    assert result is None
    assert db_session.query(Interaction).count() == 0


async def test_register_playback_skip_saves_row_with_seconds(db_session, service, user_and_song):
    user, song = user_and_song
    result = await service.register_playback(
        user.id, "track1", seconds_played=8, reached_end=False,
        was_skipped=True, access_token="token",
    )
    assert result is not None
    row = db_session.query(Interaction).one()
    assert row.type == "skip"
    assert row.time_reproduced == 8      # cuánto escuchó se guarda para el motor
    assert row.song_id == song.id


async def test_register_playback_reached_end_is_play(db_session, service, user_and_song):
    user, _ = user_and_song
    await service.register_playback(
        user.id, "track1", seconds_played=200, reached_end=True,
        was_skipped=False, access_token="token",
    )
    assert db_session.query(Interaction).filter_by(type="play").count() == 1


async def test_remove_like_deletes_and_unmirrors(db_session, service, user_and_song):
    user, song = user_and_song
    db_session.add(Interaction(user_id=user.id, song_id=song.id, type="like"))
    db_session.commit()

    await service.remove_like(user.id, "track1", "token")

    assert db_session.query(Interaction).filter_by(type="like").count() == 0
    service.spotify_service.remove_from_liked_songs.assert_awaited_once()


def test_remove_dislike_noop_when_song_unknown(db_session, service, user_and_song):
    user, _ = user_and_song
    # Un track que no está en nuestra BD: no revienta, no borra nada.
    service.remove_dislike(user.id, "unknown-track")
    assert db_session.query(Interaction).count() == 0
