from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    spotify_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    token_expiry = Column(DateTime, nullable=False)
    is_premium = Column(Boolean, default=False)
    registration_date = Column(DateTime, default=func.now())


class Song(Base):
    __tablename__ = "songs"
    id = Column(Integer, primary_key=True)
    spotify_track_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    genres = Column(String)  # feature para recommendation_service (KMeans)
    duration_ms = Column(Integer)  # pendiente de decisión de equipo sobre umbral de skip

    # album y cover_url EXISTIERON y se quitaron en 48f053f ("starting with
    # routers", 2026-07-01), sin motivo documentado. Vuelven a propósito, y
    # conviene saber por qué para no volver a quitarlas:
    #
    #  1. El documento de análisis las pide: la entidad "Canción" lista Álbum y
    #     Portada entre sus atributos.
    #  2. Guardarlas es GRATIS: el objeto de Spotify que recibe
    #     SongRepository.create_from_spotify_data ya trae album.name y
    #     album.images. Antes se descartaban.
    #  3. No guardarlas es CARO: /tracks?ids= (el lote) devuelve 403 para esta
    #     app, así que recuperarlas después cuesta UNA llamada por canción —
    #     justo la ráfaga que hizo que Spotify baneara la app. Ese dato no se
    #     conocía cuando se quitaron.
    album = Column(String)
    cover_url = Column(String)


class Interaction(Base):
    __tablename__ = "interactions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    song_id = Column(Integer, ForeignKey("songs.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    time_reproduced = Column(Integer, nullable=True)


class RecommendationPlaylist(Base):
    __tablename__ = "recommendation_playlists"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    spotify_playlist_id = Column(String, nullable=False)
    period_type = Column(String, nullable=False)
    last_updated = Column(DateTime)

    __table_args__ = (
        UniqueConstraint("user_id", "period_type", name="uq_user_period"),
    )