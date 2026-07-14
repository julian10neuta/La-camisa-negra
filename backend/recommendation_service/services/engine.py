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
from datetime import timedelta
from sqlalchemy.orm import Session

from shared.spotify_service import SpotifyService
from shared.deezer_service import DeezerService
from ..repositories.interaction_repo import InteractionReadRepository
from ..repositories.recommendation_playlist_repo import RecommendationPlaylistRepository
from .profile import build_profile

# ─── Períodos ─────────────────────────────────────────────────────────────────
# El usuario elige en Ajustes si quiere sus recomendaciones semanales o mensuales.
# Entre un período y otro cambian dos cosas:
#   1. Cada cuánto se regenera la lista (`stale_after`).
#   2. Que cada período tiene su PROPIA playlist en Spotify — el modelo tiene la
#      restricción única (user_id, period_type), así que las dos pueden coexistir
#      y el usuario puede alternar sin perder ninguna.
#
# OJO CON LO QUE **NO** CAMBIA: el perfil se construye con TODO el historial de
# interacciones, sin ventana temporal (ver profile.build_profile). O sea que
# "mensual" NO significa "calculado con lo que escuchaste este mes": significa que
# se refresca cada 30 días. Si algún día se quiere una ventana temporal de verdad,
# hay que tocar el repositorio de interacciones y el perfil, no esto.
PERIODS = {
    "weekly": {
        "stale_after": timedelta(days=7),
        "playlist_name": "Wavely — Recomendado para ti (semanal)",
        "playlist_desc": "Recomendaciones de Wavely según tu escucha. Se renuevan cada semana.",
    },
    "monthly": {
        "stale_after": timedelta(days=30),
        "playlist_name": "Wavely — Recomendado para ti (mensual)",
        "playlist_desc": "Recomendaciones de Wavely según tu escucha. Se renuevan cada mes.",
    },
}
DEFAULT_PERIOD = "weekly"


def period_config(period: str) -> dict:
    """Config de un período, cayendo al default si llega uno desconocido. El
    router ya valida el valor; esto es solo un cinturón de seguridad para que el
    motor nunca reviente con un KeyError."""
    return PERIODS.get(period, PERIODS[DEFAULT_PERIOD])


# Botones de diseño (ver doc del motor).
SEED_ARTISTS = 8          # artistas favoritos usados como semilla
RELATED_PER_SEED = 6      # cuántos artistas similares miramos por semilla
TRACKS_PER_ARTIST = 2     # top tracks por artista similar
PER_SEED_QUOTA = 3        # cuántas candidatas aporta cada semilla al pool
N_RECOMMENDATIONS = 15    # default; el usuario puede pedir otro en Ajustes
MIN_RECOMMENDATIONS = 1
MAX_RECOMMENDATIONS = 50  # tope duro: cada recomendación cuesta llamadas a Deezer+Spotify

ARTIST_ID_TTL = 60 * 60 * 24 * 30   # 30 días
RELATED_TTL = 60 * 60 * 24 * 7      # 7 días
TOP_TTL = 60 * 60 * 24 * 7          # 7 días
MATCH_TTL = 60 * 60 * 24 * 30       # 30 días — emparejado Deezer→Spotify (estable)


def build_response(
    tracks: list,
    playlist_id: str | None,
    period: str,
    last_updated,
    generated: bool,
) -> dict:
    """
    Forma única de la respuesta de /list y /refresh, para que las dos rutas no se
    desincronicen.

    `period` y `next_refresh` van aquí y no se calculan en el frontend a
    propósito: cuándo caduca una lista es una regla del motor, y si el cliente la
    replicara habría que acordarse de cambiarla en dos sitios.
    """
    cfg = period_config(period)
    return {
        "tracks": tracks,
        "playlist_id": playlist_id,
        "playlist_url": (
            f"https://open.spotify.com/playlist/{playlist_id}" if playlist_id else None
        ),
        "generated": generated,
        "period": period,
        "last_updated": last_updated.isoformat() if last_updated else None,
        "next_refresh": (
            (last_updated + cfg["stale_after"]).isoformat() if last_updated else None
        ),
    }


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

    async def generate(
        self,
        user_id: int,
        token: str,
        period: str = DEFAULT_PERIOD,
        limit: int = N_RECOMMENDATIONS,
    ) -> dict:
        rows = InteractionReadRepository.get_interactions_with_songs(self.db, user_id)
        profile = build_profile(rows)

        seeds = await self._seed_artists(token, profile)
        if not seeds:
            return self._empty(period)

        # La cuota por semilla se adapta al total pedido. Con los valores fijos
        # (8 semillas × 3) el pool tope era 24, así que pedir 25 habría devuelto
        # 24 en silencio; y si el usuario tiene pocas semillas, el tope caía aún
        # más. Se reparte el objetivo entre las semillas que realmente haya.
        # El techo real por semilla es RELATED_PER_SEED × TRACKS_PER_ARTIST.
        quota = max(PER_SEED_QUOTA, -(-limit // len(seeds)))  # ceil(limit/semillas)

        favorite_names = {n.lower() for n, _ in seeds}
        chosen_ids: set = set()          # evita duplicados entre semillas
        per_seed: dict[str, list] = {}   # semilla -> candidatas (tracks de Spotify)

        for name, _weight in seeds:
            dz = await self._dz_search_artist(name)
            picks: list = []
            if dz:
                for rel in (await self._dz_related(dz["id"]))[:RELATED_PER_SEED]:
                    if len(picks) >= quota:
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
                        if len(picks) >= quota:
                            break
            per_seed[name] = picks

        # Round-robin: cada semilla aporta por turnos, para que la variedad aparezca
        # y no domine el clúster mayoritario.
        tracks: list = []
        order = [n for n, _ in seeds]
        idx = 0
        while len(tracks) < limit:
            progressed = False
            for name in order:
                lst = per_seed.get(name, [])
                if idx < len(lst):
                    tracks.append(serialize_track(lst[idx]))
                    progressed = True
                    if len(tracks) >= limit:
                        break
            idx += 1
            if not progressed:
                break

        playlist_id = None
        last_updated = None
        if tracks:
            pl = await self._sync_playlist(
                user_id, token, [t["spotify_track_id"] for t in tracks], period
            )
            playlist_id = pl.spotify_playlist_id
            last_updated = pl.last_updated

        return build_response(
            tracks=tracks,
            playlist_id=playlist_id,
            period=period,
            last_updated=last_updated,
            generated=True,
        )

    def _empty(self, period: str = DEFAULT_PERIOD) -> dict:
        return build_response(
            tracks=[], playlist_id=None, period=period, last_updated=None, generated=False
        )

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

    async def _sync_playlist(
        self,
        user_id: int,
        token: str,
        track_ids: list[str],
        period: str,
    ):
        """
        Vuelca las recomendaciones en la playlist real de Spotify del usuario para
        ESE período y devuelve la fila de RecommendationPlaylist (quien llama
        necesita su `last_updated` para saber cuándo toca renovar).

        Cada período tiene su propia playlist: la semanal y la mensual conviven y
        no se pisan.
        """
        cfg = period_config(period)
        existing = RecommendationPlaylistRepository.get_by_user_and_period(
            self.db, user_id, period
        )
        if existing:
            pl_id = existing.spotify_playlist_id
            try:
                current = await self.spotify.get_playlist_tracks(pl_id, token)
                current_ids = [c["id"] for c in current if c.get("id")]
                if current_ids:
                    await self.spotify.remove_tracks_from_playlist(pl_id, current_ids, token)
                await self.spotify.add_tracks_to_playlist(pl_id, track_ids, token)
                return RecommendationPlaylistRepository.update(self.db, existing)
            except Exception:
                pass  # la playlist pudo ser borrada en Spotify → crear una nueva

        created = await self.spotify.create_playlist(
            cfg["playlist_name"], cfg["playlist_desc"], token
        )
        await self.spotify.add_tracks_to_playlist(created["id"], track_ids, token)
        if existing:
            return RecommendationPlaylistRepository.update(
                self.db, existing, spotify_playlist_id=created["id"]
            )
        return RecommendationPlaylistRepository.create(
            self.db, user_id, created["id"], period
        )
