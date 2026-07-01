# music_service/services/spotify_service.py
import httpx


class SpotifyService:
    """
    Capa de integración con la Spotify Web API.
    Todas las llamadas HTTP a Spotify pasan por aquí — ningún otro
    service o router debe llamar a Spotify directamente.
    """

    BASE_URL = "https://api.spotify.com/v1"

    def _headers(self, access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    # ─── Canciones ───────────────────────────────────────────────────────────

    async def search_tracks(
        self,
        query: str,
        access_token: str,
        limit: int = 20,
    ) -> list[dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/search",
                params={"q": query, "type": "track", "limit": limit},
                headers=self._headers(access_token),
            )
        #print(f"DEBUG status: {response.status_code}")
        #print(f"DEBUG response body: {response.text}")
        response.raise_for_status()
        return response.json()["tracks"]["items"]

    async def get_track(self, track_id: str, access_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/tracks/{track_id}",
                headers=self._headers(access_token),
            )
        response.raise_for_status()
        return response.json()

    async def get_artist(self, artist_id: str, access_token: str) -> dict:
        """
        Necesario para obtener genres — viven en el artista, no en el track.
        Ver nota en song_repository sobre este detalle de la Spotify API.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/artists/{artist_id}",
                headers=self._headers(access_token),
            )
        response.raise_for_status()
        return response.json()

    # ─── Liked Songs ─────────────────────────────────────────────────────────

    async def get_liked_songs(
        self,
        access_token: str,
        limit: int = 50,
    ) -> list[dict]:
        """
        Trae TODAS las Liked Songs del usuario paginando.
        Spotify devuelve máximo 50 por request.
        """
        all_tracks = []
        url = f"{self.BASE_URL}/me/tracks"
        params = {"limit": limit}

        async with httpx.AsyncClient() as client:
            while url:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._headers(access_token),
                )
                response.raise_for_status()
                data = response.json()
                all_tracks.extend(item["track"] for item in data["items"])
                url = data.get("next")
                params = {}  # "next" ya incluye los params

        return all_tracks

    async def add_to_liked_songs(
        self,
        track_id: str,
        access_token: str,
    ) -> None:
        print(f"DEBUG add_like token: '{access_token[:30]}...'")
        print(f"DEBUG add_like track_id: '{track_id}'")
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.BASE_URL}/me/tracks",
                json={"ids": [track_id]},  # ← JSON body, y debe ser lista
                headers=self._headers(access_token),
            )
        print(f"DEBUG add_like status: {response.status_code}")
        print(f"DEBUG add_like body: {response.text}")
        response.raise_for_status()

    async def remove_from_liked_songs(
        self,
        track_id: str,
        access_token: str,
    ) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.BASE_URL}/me/tracks",
                params={"ids": track_id},
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
                response = await client.get(
                    url,
                    params=params,
                    headers=self._headers(access_token),
                )
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
        url = f"{self.BASE_URL}/playlists/{playlist_id}/tracks"
        params = {"limit": 100}

        async with httpx.AsyncClient() as client:
            while url:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._headers(access_token),
                )
                response.raise_for_status()
                data = response.json()
                all_tracks.extend(
                    item["track"] for item in data["items"] if item["track"]
                )
                url = data.get("next")
                params = {}

        return all_tracks

    async def create_playlist(
        self,
        spotify_user_id: str,
        name: str,
        description: str,
        access_token: str,
        public: bool = False,
    ) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/users/{spotify_user_id}/playlists",
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
        """
        Spotify acepta máximo 100 tracks por request.
        """
        uris = [f"spotify:track:{tid}" for tid in track_ids]

        async with httpx.AsyncClient() as client:
            for i in range(0, len(uris), 100):
                batch = uris[i:i + 100]
                response = await client.post(
                    f"{self.BASE_URL}/playlists/{playlist_id}/tracks",
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
        tracks = [{"uri": f"spotify:track:{tid}"} for tid in track_ids]

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.BASE_URL}/playlists/{playlist_id}/tracks",
                json={"tracks": tracks},
                headers=self._headers(access_token),
            )
        response.raise_for_status()