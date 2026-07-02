# music_service/services/spotify_service.py
import httpx


class SpotifyService:
    BASE_URL = "https://api.spotify.com/v1"

    def _headers(self, access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    # ─── Canciones ───────────────────────────────────────────────────────────

    async def search_tracks(
        self,
        query: str,
        access_token: str,
        limit: int = 10,
    ) -> list[dict]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/search",
                params={"q": query, "type": "track", "limit": limit},
                headers=self._headers(access_token),
            )
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
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/artists/{artist_id}",
                headers=self._headers(access_token),
            )
        response.raise_for_status()
        return response.json()

    # ─── Biblioteca (Liked Songs) ─────────────────────────────────────────────

    async def get_liked_songs(
        self,
        access_token: str,
        limit: int = 50,
    ) -> list[dict]:
        """
        Usa el endpoint legacy /me/tracks que aún funciona para GET.
        El nuevo /me/library es para escritura.
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
        url = f"{self.BASE_URL}/playlists/{playlist_id}/items"
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
                print(f"DEBUG items[0]: {data['items'][0] if data['items'] else 'VACÍO'}")
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
        print(f"DEBUG uris a agregar: {uris}")
        async with httpx.AsyncClient() as client:
            for i in range(0, len(uris), 100):
                batch = uris[i:i + 100]
                print(f"DEBUG batch: {batch}")
                response = await client.post(
                    f"{self.BASE_URL}/playlists/{playlist_id}/items",
                    json={"uris": batch},
                    headers=self._headers(access_token),
                )
                print(f"DEBUG add_tracks status: {response.status_code}")
                print(f"DEBUG add_tracks body: {response.text}")
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