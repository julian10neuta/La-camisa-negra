# recommendation_service/services/profile.py
# El "cerebro" del recomendador, en Python puro (sin numpy/sklearn):
#   - build_profile: convierte las interacciones del usuario en un vector de
#     géneros ponderado + artistas favoritos + canciones a excluir.
#   - score_candidate: mide qué tan afín es una canción candidata al perfil
#     (coseno entre el vector de géneros de la candidata y el del perfil).
import math
from dataclasses import dataclass, field

# ─── Pesos por tipo de interacción (señal → afinidad). Ajustables. ─────────────
LIKE_WEIGHT = 3.0
DISLIKE_WEIGHT = -4.0
PLAY_WEIGHT = 2.0
SKIP_EARLY_WEIGHT = -2.0   # la saltó casi de inmediato → rechazo fuerte
SKIP_LATE_WEIGHT = -0.5    # la escuchó un rato y luego saltó → desinterés leve
SKIP_EARLY_SECONDS = 10
ARTIST_BOOST = 1.15        # multiplicador si la candidata es de un artista favorito


def interaction_weight(type_: str, time_reproduced) -> float:
    if type_ == "like":
        return LIKE_WEIGHT
    if type_ == "dislike":
        return DISLIKE_WEIGHT
    if type_ == "play":
        return PLAY_WEIGHT
    if type_ == "skip":
        secs = time_reproduced or 0
        return SKIP_EARLY_WEIGHT if secs < SKIP_EARLY_SECONDS else SKIP_LATE_WEIGHT
    return 0.0


def split_genres(genres_str) -> list[str]:
    if not genres_str:
        return []
    return [g.strip().lower() for g in genres_str.split(",") if g.strip()]


@dataclass
class Profile:
    genre_scores: dict = field(default_factory=dict)   # género -> peso acumulado
    artist_scores: dict = field(default_factory=dict)  # artista -> peso acumulado
    excluded_ids: set = field(default_factory=set)     # spotify_track_id ya vistos
    norm: float = 1.0                                  # norma del vector de géneros

    @property
    def top_genres(self) -> list[str]:
        return [
            g for g, s in sorted(self.genre_scores.items(), key=lambda x: x[1], reverse=True)
            if s > 0
        ]

    @property
    def top_artists(self) -> list[str]:
        return [
            a for a, s in sorted(self.artist_scores.items(), key=lambda x: x[1], reverse=True)
            if s > 0
        ]

    @property
    def has_signal(self) -> bool:
        return bool(self.top_genres or self.top_artists)


def build_profile(rows: list[tuple]) -> Profile:
    """rows: lista de (Interaction, Song)."""
    p = Profile()
    for interaction, song in rows:
        w = interaction_weight(interaction.type, interaction.time_reproduced)
        # No recomendar nada que el usuario ya haya tocado (de cualquier tipo).
        p.excluded_ids.add(song.spotify_track_id)
        if song.artist:
            p.artist_scores[song.artist] = p.artist_scores.get(song.artist, 0.0) + w
        for g in split_genres(song.genres):
            p.genre_scores[g] = p.genre_scores.get(g, 0.0) + w
    p.norm = math.sqrt(sum(s * s for s in p.genre_scores.values())) or 1.0
    return p


def score_candidate(profile: Profile, candidate_genres, candidate_artist: str) -> float:
    """
    Coseno entre el vector 0/1 de géneros de la candidata y el vector ponderado
    del perfil. Un género que al usuario le disgusta tiene peso negativo en el
    perfil, así que arrastra el puntaje hacia abajo. Boost si el artista ya gusta.
    """
    genres = [g.strip().lower() for g in candidate_genres if g and g.strip()]
    if not genres:
        return 0.0
    dot = sum(profile.genre_scores.get(g, 0.0) for g in genres)
    if dot == 0.0:
        return 0.0
    score = dot / (math.sqrt(len(genres)) * profile.norm)
    if candidate_artist and profile.artist_scores.get(candidate_artist, 0.0) > 0:
        score *= ARTIST_BOOST
    return score
