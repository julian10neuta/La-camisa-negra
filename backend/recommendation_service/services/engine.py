# recommendation_service/services/engine.py
# Orquesta el pipeline de recomendación:
#   perfil → candidatas (híbrido) → enriquecer género → puntuar → top 15 →
#   crear/actualizar la playlist real en Spotify.
from sqlalchemy.orm import Session

from shared.spotify_service import SpotifyService
from ..repositories.interaction_repo import InteractionReadRepository
from ..repositories.recommendation_playlist_repo import RecommendationPlaylistRepository
from .profile import build_profile, score_candidate

PLAYLIST_NAME = "Wavely — Recomendado para ti"
PLAYLIST_DESC = "Recomendaciones generadas por Wavely según tu escucha."
PERIOD = "weekly"

# Presupuesto de candidatas (botones de diseño; ver el doc del motor).
TOP_ARTISTS = 5
TOP_GENRES = 3
PER_SEED = 20
CANDIDATE_CAP = 150
N_RECOMMENDATIONS = 15


def serialize_track(track: dict) -> dict:
    """Aplana un track crudo de Spotify a lo que el frontend necesita (igual
    que el serializador de la búsqueda)."""
    artists = track.get("artists") or []
    album = track.get("album") or {}
    images = album.get("images") or []
    return {
        "spotify_track_id": track["id"],
        "name": track.get("name", "Unknown"),
        "artist": artists[0]["name"] if artists else "Unknown",
        "album": album.get("name"),
        "cover_url": images[0]["url"] if images else None,
        "duration_ms": track.get("duration_ms"),
    }


class RecommendationEngine:

    def __init__(self, db: Session, redis):
        self.db = db
        self.spotify = SpotifyService()

    async def generate(self, user_id: int, token: str) -> dict:
        rows = InteractionReadRepository.get_interactions_with_songs(self.db, user_id)
        profile = build_profile(rows)

        # Cold start: sin señal no hay de dónde recomendar.
        if not profile.has_signal:
            return {"tracks": [], "playlist_id": None, "playlist_url": None, "generated": False}

        candidates = await self._gather_candidates(profile, token)
        genres_by_artist = await self._enrich_genres(candidates, token)

        scored: list[tuple[float, dict]] = []
        for track in candidates.values():
            artist_ids = [a["id"] for a in (track.get("artists") or []) if a.get("id")]
            cand_genres: set[str] = set()
            for aid in artist_ids:
                cand_genres.update(genres_by_artist.get(aid, []))
            artist_name = (track.get("artists") or [{}])[0].get("name", "")
            s = score_candidate(profile, cand_genres, artist_name)
            if s > 0:
                scored.append((s, track))

        scored.sort(key=lambda x: x[0], reverse=True)
        tracks = [serialize_track(t) for _, t in scored[:N_RECOMMENDATIONS]]

        playlist_id = None
        if tracks:
            playlist_id = await self._sync_playlist(
                user_id, token, [t["spotify_track_id"] for t in tracks]
            )

        return {
            "tracks": tracks,
            "playlist_id": playlist_id,
            "playlist_url": (
                f"https://open.spotify.com/playlist/{playlist_id}" if playlist_id else None
            ),
            "generated": True,
        }

    # ─── Candidatas (híbrido: artistas favoritos + géneros) ────────────────────

    async def _gather_candidates(self, profile, token: str) -> dict:
        found: dict[str, dict] = {}

        # Semillas por artista favorito (precisión).
        for artist in profile.top_artists[:TOP_ARTISTS]:
            try:
                tracks = await self.spotify.search_tracks(
                    f'artist:"{artist}"', token, limit=PER_SEED
                )
            except Exception:
                tracks = []
            for t in tracks:
                if t.get("id"):
                    found.setdefault(t["id"], t)

        # Semillas por género del perfil (descubrimiento).
        for genre in profile.top_genres[:TOP_GENRES]:
            try:
                tracks = await self.spotify.search_tracks(
                    f'genre:"{genre}"', token, limit=PER_SEED
                )
                if not tracks:  # el filtro genre: puede no devolver nada
                    tracks = await self.spotify.search_tracks(genre, token, limit=PER_SEED)
            except Exception:
                tracks = []
            for t in tracks:
                if t.get("id"):
                    found.setdefault(t["id"], t)

        # Excluir lo ya escuchado / disliked y topar el presupuesto.
        candidates = {
            tid: t for tid, t in found.items() if tid not in profile.excluded_ids
        }
        return dict(list(candidates.items())[:CANDIDATE_CAP])

    # ─── Enriquecer géneros de las candidatas (en lote) ────────────────────────

    async def _enrich_genres(self, candidates: dict, token: str) -> dict:
        artist_ids: list[str] = []
        for t in candidates.values():
            for a in (t.get("artists") or []):
                if a.get("id"):
                    artist_ids.append(a["id"])
        if not artist_ids:
            return {}
        artists = await self.spotify.get_artists_batch(artist_ids, token)
        return {a["id"]: a.get("genres", []) for a in artists if a.get("id")}

    # ─── Persistencia + playlist real de Spotify ───────────────────────────────

    async def _sync_playlist(self, user_id: int, token: str, track_ids: list[str]) -> str:
        existing = RecommendationPlaylistRepository.get_by_user_and_period(
            self.db, user_id, PERIOD
        )
        if existing:
            pl_id = existing.spotify_playlist_id
            try:
                # Reemplazar el contenido en sitio: vaciar y volver a poblar.
                current = await self.spotify.get_playlist_tracks(pl_id, token)
                current_ids = [c["id"] for c in current if c.get("id")]
                if current_ids:
                    await self.spotify.remove_tracks_from_playlist(pl_id, current_ids, token)
                await self.spotify.add_tracks_to_playlist(pl_id, track_ids, token)
                RecommendationPlaylistRepository.update(self.db, existing)
                return pl_id
            except Exception:
                # La playlist pudo ser borrada en Spotify → crear una nueva abajo.
                pass

        created = await self.spotify.create_playlist(PLAYLIST_NAME, PLAYLIST_DESC, token)
        await self.spotify.add_tracks_to_playlist(created["id"], track_ids, token)
        if existing:
            RecommendationPlaylistRepository.update(
                self.db, existing, spotify_playlist_id=created["id"]
            )
        else:
            RecommendationPlaylistRepository.create(self.db, user_id, created["id"], PERIOD)
        return created["id"]
