# Tests de integración de InteractionRepository contra SQLite en memoria.
# Aquí vive la parte que el equipo destacó: la deduplicación y los rankings se
# hacen EN SQL (group by + agregados), no en Python. Se siembra un escenario
# concreto y se comprueba el comportamiento observable.
import pytest
from datetime import datetime

from shared.models import User, Song, Interaction
from music_service.repositories.interaction_repository import InteractionRepository as Repo

pytestmark = pytest.mark.integration

SINCE = datetime(2026, 7, 1)


@pytest.fixture()
def seeded(db_session):
    """
    Escenario:
      - Feid tiene 2 canciones: s1 (3 plays) y s2 (2 plays) → 5 plays de artista.
      - Bad Bunny: s3 (1 play), y ADEMÁS un play viejo (antes de SINCE) + un skip.
      - "Nadie": s4 (1 play) SIN álbum.
      - un like sobre s1 (time_reproduced NULL) que NO debe contar como escucha.
    """
    user = User(spotify_id="u1", name="Julian", access_token="a",
                refresh_token="r", token_expiry=datetime(2030, 1, 1))
    s1 = Song(spotify_track_id="s1", name="A", artist="Feid", album="AlbX", cover_url="cA")
    s2 = Song(spotify_track_id="s2", name="B", artist="Feid", album="AlbX", cover_url="cB")
    s3 = Song(spotify_track_id="s3", name="C", artist="Bad Bunny", album="AlbY", cover_url="cC")
    s4 = Song(spotify_track_id="s4", name="D", artist="Nadie", album=None, cover_url="cD")
    db_session.add_all([user, s1, s2, s3, s4])
    db_session.commit()

    def play(song, day, secs=60):
        db_session.add(Interaction(user_id=user.id, song_id=song.id, type="play",
                                   date=datetime(2026, 7, day), time_reproduced=secs))

    play(s1, 10); play(s1, 11); play(s1, 12)     # 3 plays, la más reciente el 12
    play(s2, 9, secs=100); play(s2, 9, secs=100)  # 2 plays
    play(s3, 8, secs=50)                          # 1 play
    play(s4, 7, secs=30)                          # 1 play, álbum None
    # ruido que NO debe contar en las ventanas/rankings:
    db_session.add(Interaction(user_id=user.id, song_id=s3.id, type="play",
                               date=datetime(2026, 6, 1), time_reproduced=999))  # antes de SINCE
    db_session.add(Interaction(user_id=user.id, song_id=s3.id, type="skip",
                               date=datetime(2026, 7, 6), time_reproduced=20))   # skip: suma segundos
    db_session.add(Interaction(user_id=user.id, song_id=s1.id, type="like",
                               date=datetime(2026, 7, 5), time_reproduced=None))  # like: no es escucha
    db_session.commit()
    return user, {"s1": s1, "s2": s2, "s3": s3, "s4": s4}


def test_get_recent_plays_dedups_and_orders_by_last_play(db_session, seeded):
    user, s = seeded
    rows = Repo.get_recent_plays(db_session, user.id, limit=8)
    songs = [song.spotify_track_id for song, _last in rows]
    # s1 sonó 3 veces pero aparece UNA sola vez; orden por reproducción más reciente.
    assert songs == ["s1", "s2", "s3", "s4"]
    # la fecha devuelta para s1 es su play más reciente (07-12), no la primera.
    assert rows[0][1] == datetime(2026, 7, 12)


def test_get_recent_plays_respects_limit(db_session, seeded):
    user, _ = seeded
    assert len(Repo.get_recent_plays(db_session, user.id, limit=2)) == 2


def test_get_top_songs_counts_plays_since(db_session, seeded):
    user, _ = seeded
    rows = Repo.get_top_songs(db_session, user.id, SINCE, limit=5)
    top_song, plays = rows[0]
    assert top_song.spotify_track_id == "s1"
    assert plays == 3          # los 3 plays; el like sobre s1 NO cuenta
    ids = [song.spotify_track_id for song, _ in rows]
    assert ids[:2] == ["s1", "s2"]


def test_get_top_artists_aggregates_across_songs(db_session, seeded):
    user, _ = seeded
    rows = Repo.get_top_artists(db_session, user.id, SINCE, limit=5)
    # Feid encabeza con 5 (3 de s1 + 2 de s2), aunque ninguna sola canción llegue a 5.
    assert rows[0]["artist"] == "Feid"
    assert rows[0]["plays"] == 5
    assert rows[0]["cover_url"] in ("cA", "cB")


def test_get_top_albums_groups_by_album_artist_and_excludes_none(db_session, seeded):
    user, _ = seeded
    rows = Repo.get_top_albums(db_session, user.id, SINCE, limit=5)
    albums = [(r["album"], r["artist"], r["plays"]) for r in rows]
    assert ("AlbX", "Feid", 5) in albums
    assert ("AlbY", "Bad Bunny", 1) in albums
    # s4 no tiene álbum → NO aparece ninguna fila "None".
    assert all(r["album"] is not None for r in rows)


def test_get_stats_summarizes_window(db_session, seeded):
    user, _ = seeded
    stats = Repo.get_stats(db_session, user.id, SINCE)
    assert stats["plays"] == 7          # 3+2+1+1 (viejo excluido por SINCE)
    assert stats["distinct_songs"] == 4
    # segundos = plays (180+200+50+30) + el skip (20) = 480. El like (NULL) no suma.
    assert stats["seconds_listened"] == 480
    assert stats["top_artist"] == "Feid"
    assert stats["top_artist_plays"] == 5


def test_get_stats_empty_window_is_all_zero(db_session, seeded):
    user, _ = seeded
    stats = Repo.get_stats(db_session, user.id, datetime(2030, 1, 1))  # futuro: nada
    assert stats == {
        "plays": 0, "distinct_songs": 0, "seconds_listened": 0,
        "top_artist": None, "top_artist_plays": 0,
    }


def test_count_plays_ignores_since_and_other_types(db_session, seeded):
    user, s = seeded
    # count_plays cuenta TODOS los play de esa canción (sin ventana). s1 tiene 3.
    assert Repo.count_plays(db_session, user.id, s["s1"].id) == 3
