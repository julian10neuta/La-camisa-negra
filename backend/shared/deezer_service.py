# shared/deezer_service.py
# Cliente de la API pública de Deezer (api.deezer.com). NO requiere key ni cuenta:
# son endpoints de catálogo de solo lectura. Lo usamos solo para la señal que
# Spotify dejó de dar a las apps nuevas: **artistas similares** (descubrimiento) y
# top tracks de artista. La reproducción sigue 100% en Spotify.
#
# Deezer señala los errores devolviendo 200 con un cuerpo {"error": {...}}
# (p. ej. cuota excedida o id inexistente); lo tratamos como "sin datos".
import httpx


class DeezerService:
    BASE_URL = "https://api.deezer.com"

    async def _get(self, path: str, params: dict | None = None):
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.BASE_URL}{path}", params=params or {})
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            return None
        return data

    async def search_artist(self, name: str) -> dict | None:
        """Encuentra el artista en Deezer a partir de su nombre (de Spotify)."""
        data = await self._get("/search/artist", {"q": name, "limit": 1})
        items = (data or {}).get("data") or []
        if not items:
            return None
        return {"id": items[0]["id"], "name": items[0]["name"]}

    async def get_related_artists(self, artist_id, limit: int = 20) -> list[dict]:
        """Artistas similares — la señal de descubrimiento que Spotify bloquea."""
        data = await self._get(f"/artist/{artist_id}/related", {"limit": limit})
        items = (data or {}).get("data") or []
        return [{"id": a["id"], "name": a["name"]} for a in items]

    async def get_artist_top(self, artist_id, limit: int = 5) -> list[dict]:
        """Top tracks de un artista (Deezer sí lo entrega; Spotify da 403)."""
        data = await self._get(f"/artist/{artist_id}/top", {"limit": limit})
        items = (data or {}).get("data") or []
        return [
            {"title": t["title"], "artist": t.get("artist", {}).get("name", "")}
            for t in items
        ]
