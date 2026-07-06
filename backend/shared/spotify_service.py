# shared/spotify_service.py
# Cliente HTTP de la Spotify Web API, compartido por todos los microservicios
# (music_service, recommendation_service). Antes vivía dentro de music_service;
# se movió a shared/ para no duplicarlo cuando el recommendation_service también
# necesita hablar con Spotify.
import asyncio
import httpx


class SpotifyService:
    BASE_URL = "https://api.spotify.com/v1"
    _MAX_RETRIES = 3            # reintentos ante un 429 transitorio
    _MAX_BACKOFF_SECONDS = 8    # tope de espera: un ban largo se propaga, no se duerme

    def _headers(self, access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    async def _get(
        self,
        client: httpx.AsyncClient,
        url: str,
        access_token: str,
        params: dict | None = None,
    ) -> httpx.Response:
        """
        GET a Spotify con reintentos ante 429 (rate limit) respetando el header
        Retry-After, con backoff ACOTADO: si Spotify pide esperar más que
        _MAX_BACKOFF_SECONDS (bloqueo prolongado), no dormimos — dejamos que el
        429 suba — para no colgar la petición del usuario minutos u horas.
        Reintentar solo las esperas cortas evita que un pico momentáneo escale
        al bloqueo largo (que es justo lo que nos baneó la app).
        """
        response = await client.get(
            url, params=params, headers=self._headers(access_token)
        )
        for _ in range(self._MAX_RETRIES):
            if response.status_code != 429:
                break
            retry_after = response.headers.get("Retry-After")
            try:
                wait = int(retry_after) if retry_after is not None else 1
            except ValueError:
                wait = 1
            if wait > self._MAX_BACKOFF_SECONDS:
                break
            await asyncio.sleep(wait)
            response = await client.get(
                url, params=params, headers=self._headers(access_token)
            )
        return response

    # ─── Canciones ───────────────────────────────────────────────────────────

    async def search_tracks(
        self,
        query: str,
        access_token: str,
        limit: int = 10,
    ) -> list[dict]:
        async with httpx.AsyncClient() as client:
            response = await self._get(
                client,
                f"{self.BASE_URL}/search",
                access_token,
                params={"q": query, "type": "track", "limit": limit},
            )
        response.raise_for_status()
        return response.json()["tracks"]["items"]

    async def get_track(self, track_id: str, access_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await self._get(
                client, f"{self.BASE_URL}/tracks/{track_id}", access_token
            )
        response.raise_for_status()
        return response.json()

    async def get_artist(self, artist_id: str, access_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await self._get(
                client, f"{self.BASE_URL}/artists/{artist_id}", access_token
            )
        response.raise_for_status()
        return response.json()

    async def get_artists_batch(
        self,
        artist_ids: list[str],
        access_token: str,
    ) -> list[dict]:
        """
        GET /artists?ids= — hasta 50 artistas por llamada. Devuelve los objetos
        de artista (que incluyen `genres`). Para el recommendation_service:
        enriquecer en lote los géneros de muchas canciones candidatas sin hacer
        una llamada por artista.
        """
        artists: list[dict] = []
        # Deduplicamos preservando orden.
        unique_ids = list(dict.fromkeys(a for a in artist_ids if a))
        async with httpx.AsyncClient() as client:
            for i in range(0, len(unique_ids), 50):
                batch = unique_ids[i:i + 50]
                response = await self._get(
                    client,
                    f"{self.BASE_URL}/artists",
                    access_token,
                    params={"ids": ",".join(batch)},
                )
                response.raise_for_status()
                artists.extend(a for a in response.json().get("artists", []) if a)
        return artists

    async def get_top_artists(
        self,
        access_token: str,
        limit: int = 10,
        time_range: str = "medium_term",
    ) -> list[dict]:
        """
        GET /me/top/artists — los artistas más escuchados del usuario (calculado
        por Spotify). Sigue disponible pese a las restricciones y es una gran
        semilla de gustos para el recommendation_service.
        """
        async with httpx.AsyncClient() as client:
            response = await self._get(
                client,
                f"{self.BASE_URL}/me/top/artists",
                access_token,
                params={"limit": limit, "time_range": time_range},
            )
        response.raise_for_status()
        return response.json().get("items", [])

    async def get_artist_top_tracks(
        self,
        artist_id: str,
        access_token: str,
        market: str = "US",
    ) -> list[dict]:
        """
        GET /artists/{id}/top-tracks — las canciones más populares de un artista.
        Fuente de candidatas "seguras" para el recommendation_service (artistas
        que ya le gustan al usuario).
        """
        async with httpx.AsyncClient() as client:
            response = await self._get(
                client,
                f"{self.BASE_URL}/artists/{artist_id}/top-tracks",
                access_token,
                params={"market": market},
            )
        response.raise_for_status()
        return response.json().get("tracks", [])

    # ─── Biblioteca (Liked Songs) ─────────────────────────────────────────────

    async def get_liked_songs(
        self,
        access_token: str,
        limit: int = 50,
        known_ids: set[str] | None = None,
    ) -> list[dict]:
        """
        Usa el endpoint legacy /me/tracks que aún funciona para GET.
        El nuevo /me/library es para escritura.

        Sync incremental: /me/tracks viene ordenado de más nuevo a más viejo
        (por la fecha en que se dio el like). Si se pasa ``known_ids`` (los ids
        que ya tenemos importados), dejamos de paginar en cuanto topamos el
        primero de ellos: todo lo que va después también se importó en un sync
        previo. Así, tras la primera importación, cada login cuesta ~1 llamada
        si no hay likes nuevos. Sin ``known_ids`` se descarga la biblioteca
        completa (comportamiento original).
        """
        all_tracks = []
        url = f"{self.BASE_URL}/me/tracks"
        params = {"limit": limit}

        async with httpx.AsyncClient() as client:
            while url:
                response = await self._get(client, url, access_token, params)
                response.raise_for_status()
                data = response.json()
                for item in data["items"]:
                    track = item.get("track")
                    # Spotify a veces devuelve tracks nulos (ya no disponibles).
                    if not track or not track.get("id"):
                        continue
                    # Llegamos a lo ya importado → el resto también lo está.
                    if known_ids is not None and track["id"] in known_ids:
                        return all_tracks
                    all_tracks.append(track)
                url = data.get("next")
                params = {}

        return all_tracks

    async def add_to_liked_songs(
        self,
        track_id: str,
        access_token: str,
    ) -> None:
        """PUT /v1/me/library — nuevo endpoint no deprecated."""
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.BASE_URL}/me/library",
                params={"uris": f"spotify:track:{track_id}"},
                headers=self._headers(access_token),
            )
        response.raise_for_status()

    async def remove_from_liked_songs(
        self,
        track_id: str,
        access_token: str,
    ) -> None:
        """DELETE /v1/me/library — nuevo endpoint no deprecated."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.BASE_URL}/me/library",
                params={"uris": f"spotify:track:{track_id}"},
                headers=self._headers(access_token),
            )
        response.raise_for_status()

    # ─── Playlists ────────────────────────────────────────────────────────────

    async def get_user_playlists(
        self,
        access_token: str,
        limit: int = 50,
    ) -> list[dict]:
        all_playlists = []
        url = f"{self.BASE_URL}/me/playlists"
        params = {"limit": limit}

        async with httpx.AsyncClient() as client:
            while url:
                response = await self._get(client, url, access_token, params)
                response.raise_for_status()
                data = response.json()
                all_playlists.extend(data["items"])
                url = data.get("next")
                params = {}

        return all_playlists

    async def get_playlist_tracks(
        self,
        playlist_id: str,
        access_token: str,
    ) -> list[dict]:
        all_tracks = []
        url = f"{self.BASE_URL}/playlists/{playlist_id}/items"
        params = {"limit": 100}

        async with httpx.AsyncClient() as client:
            while url:
                response = await self._get(client, url, access_token, params)
                response.raise_for_status()
                data = response.json()
                all_tracks.extend(
                    item["item"] for item in data["items"] if item.get("item")
                )
                url = data.get("next")
                params = {}

        return all_tracks

    async def create_playlist(
        self,
        name: str,
        description: str,
        access_token: str,
        public: bool = False,
    ) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/me/playlists",
                json={
                    "name": name,
                    "description": description,
                    "public": public,
                },
                headers=self._headers(access_token),
            )
        response.raise_for_status()
        return response.json()

    async def add_tracks_to_playlist(
        self,
        playlist_id: str,
        track_ids: list[str],
        access_token: str,
    ) -> None:
        uris = [f"spotify:track:{tid}" for tid in track_ids]
        async with httpx.AsyncClient() as client:
            for i in range(0, len(uris), 100):
                batch = uris[i:i + 100]
                response = await client.post(
                    f"{self.BASE_URL}/playlists/{playlist_id}/items",
                    json={"uris": batch},
                    headers=self._headers(access_token),
                )
                response.raise_for_status()

    async def remove_tracks_from_playlist(
        self,
        playlist_id: str,
        track_ids: list[str],
        access_token: str,
    ) -> None:
        import json

        items = [{"uri": f"spotify:track:{tid}"} for tid in track_ids]

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method="DELETE",
                url=f"{self.BASE_URL}/playlists/{playlist_id}/items",
                content=json.dumps({"items": items}),
                headers={
                    **self._headers(access_token),
                    "Content-Type": "application/json",
                },
            )
        response.raise_for_status()

    async def remove_playlist_from_library(
        self,
        playlist_id: str,
        access_token: str,
    ) -> None:
        print(f"DEBUG remove_playlist token: '{access_token[:30]}...'")
        print(f"DEBUG remove_playlist id: '{playlist_id}'")

        # Formateamos el URI tal cual como lo exige el nuevo estándar
        playlist_uri = f"spotify:playlist:{playlist_id}"

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.BASE_URL}/me/library",
                params={"uris": playlist_uri},  # httpx se encarga de codificar el %3A y la coma automáticamente
                headers=self._headers(access_token),
            )

        print(f"DEBUG remove_playlist status: {response.status_code}")
        # Al ser un borrado exitoso, Spotify devolverá 200 OK con un body vacío
        response.raise_for_status()
