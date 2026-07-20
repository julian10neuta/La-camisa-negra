# backend/tests/conftest.py
# ----------------------------------------------------------------------------
# Fixtures COMPARTIDAS por toda la suite. La idea rectora: los tests NO tocan
# infraestructura real. Nada de Postgres, Redis ni Spotify de verdad.
#
#   - La base de datos se sustituye por SQLite EN MEMORIA (vive dentro del
#     proceso de pytest y desaparece al terminar). Los modelos usan solo tipos
#     portables, así que las mismas tablas se crean igual en SQLite.
#   - Redis se sustituye por fakeredis (un Redis falso, también en memoria).
#   - Spotify/Deezer se mockean en cada test que los necesite.
#
# Gracias a esto la suite corre con `pytest` a secas, sin `docker compose up`.
# ----------------------------------------------------------------------------
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shared.database import Base
from shared.config import settings

# Importar shared.models registra las tablas en Base.metadata (User, Song,
# Interaction, RecommendationPlaylist). Sin este import, create_all no crearía
# nada. Se importa por su efecto colateral.
import shared.models  # noqa: F401


@pytest.fixture()
def db_session():
    """
    Una sesión de SQLAlchemy contra una BD SQLite en memoria, con el esquema
    completo creado desde cero. Cada test recibe una base limpia y aislada.

    `StaticPool` + una única conexión compartida es el truco para que una BD
    ":memory:" sobreviva entre operaciones: por defecto cada conexión nueva
    tendría su propia memoria vacía.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def fake_redis():
    """Un cliente Redis falso en memoria (fakeredis), API-compatible con redis.Redis."""
    import fakeredis

    return fakeredis.FakeRedis(decode_responses=False)


@pytest.fixture()
def secret_key(monkeypatch):
    """
    Fija un SECRET_KEY conocido para los tests de JWT. El de producción vive en
    el `.env`; en tests no queremos depender de él ni de que exista.
    """
    key = "test-secret-key-not-used-in-prod-0123456789"
    monkeypatch.setattr(settings, "SECRET_KEY", key)
    monkeypatch.setattr(settings, "ALGORITHM", "HS256")
    return key
