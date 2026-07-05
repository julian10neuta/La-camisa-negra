# recommendation_service/services/engine.py
# Motor de recomendación.
#
# Por qué este diseño: Spotify (para apps nuevas) dejó de exponer géneros,
# populares, artistas relacionados, top-tracks y /recommendations. Lo único que
# da es búsqueda + metadata básica + los datos propios del usuario. Así que la
# señal de DESCUBRIMIENTO (a qué se parece lo que te gusta) la tomamos de la API
# pública de **Deezer** (artistas similares), y Spotify se usa solo para buscar la
# canción equivalente, reproducirla y armar la playlist.
#
# Pipeline:
#   1. Semillas = artistas favoritos (interacciones de la app PRIMERO; /me/top de
#      Spotify solo para rellenar). Así los likes nuevos sí cambian el resultado.
#   2. Por cada semilla → sus artistas similares en Deezer → sus top tracks.
#   3. Emparejar cada track con Spotify (título+artista).
#   4. **Round-robin por semilla**: cada semilla aporta recomendaciones por turnos,
#      para que la variedad (salsa, rock, indie…) no la ahogue el clúster mayoritario.
#   5. Excluir lo ya escuchado/disliked → 15 → playlist real.
#
# Se cachean en Redis las llamadas de Deezer (id de artista, similares y top tracks),
# que casi no cambian, para no repetir llamadas ni acercarnos a su límite (50/5s).
import json
from sqlalchemy.orm import Session

from shared.spotify_service import SpotifyService
from shared.deezer_service import DeezerService
from ..repositories.interaction_repo import InteractionReadRepository
from ..repositories.recommendation_playlist_repo import RecommendationPlaylistRepository
from .profile import build_profile

PLAYLIST_NAME = "Wavely — Recomendado para ti"
PLAYLIST_DESC = "Recomendaciones generadas por Wavely según tu escucha."
PERIOD = "weekly"

# Botones de diseño (ver doc del motor).
SEED_ARTISTS = 8          # artistas favoritos usados como semilla
RELATED_PER_SEED = 6      # cuántos artistas similares miramos por semilla
TRACKS_PER_ARTIST = 2     # top tracks por artista similar
PER_SEED_QUOTA = 3        # cuántas candidatas aporta cada semilla al pool
N_RECOMMENDATIONS = 15

ARTIST_ID_TTL = 60 * 60 * 24 * 30   # 30 días
RELATED_TTL = 60 * 60 * 24 * 7      # 7 días
TOP_TTL = 60 * 60 * 24 * 7          # 7 días
MATCH_TTL = 60 * 60 * 24 * 30       # 30 días — emparejado Deezer→Spotify (estable)


def serialize_track(track: dict) -> dict:
    """Aplana un track crudo de Spotify a lo que el frontend necesita."""
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
        self.redis = redis
        self.spotify = SpotifyService()
        self.deezer = DeezerService()

    # ─── Caché de Deezer en Redis ──────────────────────────────────────────────

    async def _cached(self, key: str, ttl: int, coro_factory):
        cached = self.redis.get(key)
        if cached is not None:
            return json.loads(cached)
        value = await coro_factory()
        self.redis.setex(key, ttl, json.dumps(value))
        return value

    async def _dz_search_artist(self, name: str):
        return await self._cached(
            f"deezer:artist_id:{name.strip().lower()}", ARTIST_ID_TTL,
            lambda: self.deezer.search_artist(name),
        )

    async def _dz_related(self, artist_id) -> list[dict]:
        return await self._cached(
            f"deezer:related:{artist_id}", RELATED_TTL,
            lambda: self.deezer.get_related_artists(artist_id),
        )

    async def _dz_top(self, artist_id) -> list[dict]:
        return await self._cached(
            f"deezer:top:{artist_id}", TOP_TTL,
            lambda: self.deezer.get_artist_top(artist_id, limit=TRACKS_PER_ARTIST),
        )

    # ─── Semillas: artistas favoritos ──────────────────────────────────────────

    async def _seed_artists(self, token: str, profile) -> list[tuple[str, float]]:
        # PRIMARIO: los favoritos por interacción EN LA APP (señal explícita y fresca
        # que el usuario controla). Estos mandan, para que dar likes nuevos sí cambie
        # las recomendaciones.
        favs = sorted(
            ((n, s) for n, s in profile.artist_scores.items() if s > 0),
            key=lambda x: x[1],
            reverse=True,
        )
        seeds = favs[:SEED_ARTISTS]
        seen = {n.lower() for n, _ in seeds}

        # RELLENO: si sobran cupos, los completamos con los artistas top que Spotify
        # calcula del usuario (amplitud + arranque en frío), con peso BAJO.
        if len(seeds) < SEED_ARTISTS:
            try:
                top = await self.spotify.get_top_artists(token, limit=10)
                for a in top:
                    name = a.get("name")
                    if name and name.lower() not in seen:
                        seeds.append((name, 1.0))
                        seen.add(name.lower())
                        if len(seeds) >= SEED_ARTISTS:
                            break
            except Exception:
                pass
        return seeds

    # ─── Pipeline principal ────────────────────────────────────────────────────

    async def generate(self, user_id: int, token: str) -> dict:
        rows = InteractionReadRepository.get_interactions_with_songs(self.db, user_id)
        profile = build_profile(rows)

        seeds = await self._seed_artists(token, profile)
        if not seeds:
            return self._empty()

        favorite_names = {n.lower() for n, _ in seeds}
        chosen_ids: set = set()          # evita duplicados entre semillas
        per_seed: dict[str, list] = {}   # semilla -> candidatas (tracks de Spotify)

        for name, _weight in seeds:
            dz = await self._dz_search_artist(name)
            picks: list = []
            if dz:
                for rel in (await self._dz_related(dz["id"]))[:RELATED_PER_SEED]:
                    if len(picks) >= PER_SEED_QUOTA:
                        break
                    if rel["name"].lower() in favorite_names:
                        continue  # buscamos descubrimiento, no lo que ya conoce
                    for t in await self._dz_top(rel["id"]):
                        sp = await self._match_spotify(t["title"], t["artist"], token)
                        if not sp:
                            continue
                        tid = sp["id"]
                        if tid in profile.excluded_ids or tid in chosen_ids:
                            continue
                        chosen_ids.add(tid)
                        picks.append(sp)
                        if len(picks) >= PER_SEED_QUOTA:
                            break
            per_seed[name] = picks

        # Round-robin: cada semilla aporta por turnos, para que la variedad aparezca
        # y no domine el clúster mayoritario.
        tracks: list = []
        order = [n for n, _ in seeds]
        idx = 0
        while len(tracks) < N_RECOMMENDATIONS:
            progressed = False
            for name in order:
                lst = per_seed.get(name, [])
                if idx < len(lst):
                    tracks.append(serialize_track(lst[idx]))
                    progressed = True
                    if len(tracks) >= N_RECOMMENDATIONS:
                        break
            idx += 1
            if not progressed:
                break

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

    def _empty(self) -> dict:
        return {"tracks": [], "playlist_id": None, "playlist_url": None, "generated": False}

    async def _match_spotify(self, title: str, artist: str, token: str):
        """
        Empareja una canción de Deezer con Spotify por título+artista (el /top de
        Deezer no trae ISRC). Cacheado en Redis: el emparejado título+artista →
        track de Spotify es estable y no depende del usuario, así que regenerar
        (o recomendar para otro usuario) reusa el resultado en vez de repetir la
        búsqueda en Spotify — que era la ráfaga que más pesaba en el rate limit.
        Se cachea también el "no encontrado" (null) para no reintentar fallos.
        """
        title = (title or "").replace('"', "").strip()
        artist = (artist or "").replace('"', "").strip()
        if not title:
            return None
        key = f"spotify:match:{title.lower()}|{artist.lower()}"
        return await self._cached(
            key, MATCH_TTL, lambda: self._search_match(title, artist, token)
        )

    async def _search_match(self, title: str, artist: str, token: str):
        """Búsqueda real en Spotify (sin caché). Si el filtro por campos no
        acierta, reintenta con una búsqueda simple."""
        for query in (f'track:"{title}" artist:"{artist}"', f"{title} {artist}"):
            try:
                items = await self.spotify.search_tracks(query, token, limit=1)
            except Exception:
                items = []
            if items:
                return items[0]
        return None

    # ─── Persistencia + playlist real de Spotify ───────────────────────────────

    async def _sync_playlist(self, user_id: int, token: str, track_ids: list[str]) -> str:
        existing = RecommendationPlaylistRepository.get_by_user_and_period(
            self.db, user_id, PERIOD
        )
        if existing:
            pl_id = existing.spotify_playlist_id
            try:
                current = await self.spotify.get_playlist_tracks(pl_id, token)
                current_ids = [c["id"] for c in current if c.get("id")]
                if current_ids:
                    await self.spotify.remove_tracks_from_playlist(pl_id, current_ids, token)
                await self.spotify.add_tracks_to_playlist(pl_id, track_ids, token)
                RecommendationPlaylistRepository.update(self.db, existing)
                return pl_id
            except Exception:
                pass  # la playlist pudo ser borrada en Spotify → crear una nueva

        created = await self.spotify.create_playlist(PLAYLIST_NAME, PLAYLIST_DESC, token)
        await self.spotify.add_tracks_to_playlist(created["id"], track_ids, token)
        if existing:
            RecommendationPlaylistRepository.update(
                self.db, existing, spotify_playlist_id=created["id"]
            )
        else:
            RecommendationPlaylistRepository.create(self.db, user_id, created["id"], PERIOD)
        return created["id"]
