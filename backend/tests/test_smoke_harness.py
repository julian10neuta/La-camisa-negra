# backend/tests/test_smoke_harness.py
# Valida que el ANDAMIO de tests funciona antes de escribir tests de verdad:
#   - los paquetes de los servicios importan sin intentar conectarse a nada real
#   - SQLite en memoria crea el esquema y acepta inserciones/lecturas
#   - fakeredis responde como un Redis
# Si algo de esto falla, no tiene sentido depurar los tests de negocio todavía.
from datetime import datetime


def test_service_modules_import_without_touching_infra():
    # Importar estos módulos NO debe abrir conexiones a Postgres/Redis/Spotify.
    # (create_engine es perezoso; get_redis_client solo conecta al llamarse.)
    import shared.models  # noqa: F401
    import recommendation_service.services.profile  # noqa: F401
    import music_service.serializers.song_serializer  # noqa: F401
    import authentication_service.utils.jwt_utils  # noqa: F401


def test_sqlite_schema_roundtrip(db_session):
    from shared.models import User, Song, Interaction

    user = User(
        spotify_id="u1", name="Julian", access_token="a", refresh_token="r",
        token_expiry=datetime(2030, 1, 1), is_premium=True,
    )
    song = Song(spotify_track_id="t1", name="La Camisa Negra", artist="Juanes")
    db_session.add_all([user, song])
    db_session.flush()  # asigna ids sin cerrar la transacción

    db_session.add(Interaction(user_id=user.id, song_id=song.id, type="play", time_reproduced=42))
    db_session.commit()

    stored = db_session.query(Interaction).one()
    assert stored.type == "play"
    assert stored.time_reproduced == 42
    assert stored.user_id == user.id


def test_fake_redis_behaves_like_redis(fake_redis):
    fake_redis.set("k", b"v", ex=30)
    assert fake_redis.get("k") == b"v"
    assert fake_redis.ttl("k") <= 30
    assert fake_redis.get("missing") is None
