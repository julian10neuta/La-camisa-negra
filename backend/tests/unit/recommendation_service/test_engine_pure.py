# Tests unitarios de las funciones PURAS del motor: recommendation_service/services/engine.py
# (period_config, build_response, serialize_track, y la caché de lista en Redis).
# El pipeline completo (generate, con Deezer/Spotify) se prueba aparte con mocks;
# aquí van las piezas sin red.
from datetime import datetime, timedelta

from recommendation_service.services import engine


# ─── period_config ────────────────────────────────────────────────────────────

def test_period_config_known_periods():
    assert engine.period_config("weekly")["stale_after"] == timedelta(days=7)
    assert engine.period_config("monthly")["stale_after"] == timedelta(days=30)


def test_period_config_unknown_falls_back_to_default():
    # El router ya valida; esto es el cinturón de seguridad: nunca un KeyError.
    assert engine.period_config("yearly") == engine.PERIODS[engine.DEFAULT_PERIOD]
    assert engine.period_config("WEEKLY") == engine.PERIODS[engine.DEFAULT_PERIOD]


# ─── build_response ───────────────────────────────────────────────────────────

def test_build_response_shape_and_next_refresh():
    last = datetime(2026, 7, 1, 12, 0, 0)
    resp = engine.build_response(
        tracks=[{"spotify_track_id": "t1"}],
        playlist_id="PL123",
        period="weekly",
        last_updated=last,
        generated=True,
    )
    assert resp["tracks"] == [{"spotify_track_id": "t1"}]
    assert resp["playlist_id"] == "PL123"
    assert resp["playlist_url"] == "https://open.spotify.com/playlist/PL123"
    assert resp["generated"] is True
    assert resp["stale"] is False
    assert resp["period"] == "weekly"
    assert resp["last_updated"] == last.isoformat()
    # next_refresh = last_updated + stale_after del período (7 días para weekly).
    assert resp["next_refresh"] == (last + timedelta(days=7)).isoformat()


def test_build_response_monthly_uses_30_day_window():
    last = datetime(2026, 7, 1)
    resp = engine.build_response([], "PL", "monthly", last, generated=True)
    assert resp["next_refresh"] == (last + timedelta(days=30)).isoformat()


def test_build_response_without_playlist_or_date_is_all_none():
    resp = engine.build_response([], None, "weekly", None, generated=False, stale=True)
    assert resp["playlist_id"] is None
    assert resp["playlist_url"] is None
    assert resp["last_updated"] is None
    assert resp["next_refresh"] is None
    assert resp["stale"] is True
    assert resp["generated"] is False


# ─── serialize_track ──────────────────────────────────────────────────────────

def test_serialize_track_full_object():
    raw = {
        "id": "abc",
        "name": "La Camisa Negra",
        "artists": [{"name": "Juanes"}, {"name": "Otro"}],
        "album": {"name": "Mi Sangre", "images": [{"url": "http://cover/big"}, {"url": "small"}]},
        "duration_ms": 213000,
    }
    out = engine.serialize_track(raw)
    assert out == {
        "spotify_track_id": "abc",
        "name": "La Camisa Negra",
        "artist": "Juanes",                 # el primer artista
        "album": "Mi Sangre",
        "cover_url": "http://cover/big",     # la primera imagen (mayor resolución)
        "duration_ms": 213000,
    }


def test_serialize_track_missing_fields_degrade_gracefully():
    out = engine.serialize_track({"id": "x"})
    assert out["spotify_track_id"] == "x"
    assert out["name"] == "Unknown"
    assert out["artist"] == "Unknown"
    assert out["album"] is None
    assert out["cover_url"] is None
    assert out["duration_ms"] is None


# ─── caché de lista en Redis (con fakeredis) ──────────────────────────────────

def test_cache_key_includes_user_and_period():
    assert engine._cache_key(7, "monthly") == "recs:7:monthly"


def test_write_then_read_cached_roundtrip(fake_redis):
    last = datetime(2026, 7, 1, 8, 30)
    tracks = [{"spotify_track_id": "t1", "name": "x"}]
    engine.write_cached(fake_redis, user_id=7, period="weekly",
                        tracks=tracks, playlist_id="PL", last_updated=last)

    data = engine.read_cached(fake_redis, 7, "weekly")
    assert data["tracks"] == tracks
    assert data["playlist_id"] == "PL"
    assert data["last_updated"] == last   # se reconstruye como datetime, no string


def test_write_cached_uses_double_the_stale_window_as_ttl(fake_redis):
    last = datetime(2026, 7, 1)
    engine.write_cached(fake_redis, 1, "weekly", [{"a": 1}], "PL", last)
    ttl = fake_redis.ttl(engine._cache_key(1, "weekly"))
    # weekly caduca a 7 días; el TTL es el DOBLE (14 días) para poder seguir
    # sirviendo la última lista marcada como stale sin volver a preguntar.
    assert 0 < ttl <= 14 * 24 * 3600
    assert ttl > 7 * 24 * 3600


def test_write_cached_noop_without_playlist_or_date(fake_redis):
    engine.write_cached(fake_redis, 1, "weekly", [{"a": 1}], None, datetime(2026, 7, 1))
    engine.write_cached(fake_redis, 1, "weekly", [{"a": 1}], "PL", None)
    assert engine.read_cached(fake_redis, 1, "weekly") is None


def test_read_cached_missing_returns_none(fake_redis):
    assert engine.read_cached(fake_redis, 999, "weekly") is None


def test_read_cached_corrupt_payload_returns_none(fake_redis):
    fake_redis.set(engine._cache_key(1, "weekly"), b"{not valid json")
    assert engine.read_cached(fake_redis, 1, "weekly") is None
