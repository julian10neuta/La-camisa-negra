# Tests del cliente de Spotify (shared/spotify_service.py) con respx.
# Cubren los wrappers, la paginación, el sync incremental de Liked Songs y —lo
# más importante para este proyecto— el backoff ante 429 (rate limit), que fue lo
# que hizo que banearan la app.
import httpx
import pytest
import respx

from shared.spotify_service import SpotifyService

pytestmark = pytest.mark.integration

BASE = "https://api.spotify.com/v1"
TOKEN = "fake-token"
svc = SpotifyService()


# ─── Lecturas ─────────────────────────────────────────────────────────────────

@respx.mock
async def test_search_tracks_returns_items():
    respx.get(f"{BASE}/search").mock(
        return_value=httpx.Response(200, json={"tracks": {"items": [{"id": "t1"}]}})
    )
    assert await svc.search_tracks("juanes", TOKEN) == [{"id": "t1"}]


@respx.mock
async def test_get_track():
    respx.get(f"{BASE}/tracks/t1").mock(return_value=httpx.Response(200, json={"id": "t1"}))
    assert (await svc.get_track("t1", TOKEN))["id"] == "t1"


@respx.mock
async def test_get_top_artists_returns_items():
    respx.get(f"{BASE}/me/top/artists").mock(
        return_value=httpx.Response(200, json={"items": [{"name": "Feid"}]})
    )
    assert await svc.get_top_artists(TOKEN) == [{"name": "Feid"}]


@respx.mock
async def test_get_artists_batch_dedups_preserving_order():
    route = respx.get(f"{BASE}/artists").mock(
        return_value=httpx.Response(200, json={"artists": [{"id": "a1"}, {"id": "a2"}]})
    )
    out = await svc.get_artists_batch(["a1", "a2", "a1", "", "a2"], TOKEN)
    assert out == [{"id": "a1"}, {"id": "a2"}]
    # Una sola llamada: los duplicados y el vacío se colapsaron antes de pedir.
    assert route.call_count == 1


@respx.mock
async def test_authorization_header_is_sent():
    route = respx.get(f"{BASE}/tracks/t1").mock(return_value=httpx.Response(200, json={"id": "t1"}))
    await svc.get_track("t1", TOKEN)
    assert route.calls.last.request.headers["Authorization"] == f"Bearer {TOKEN}"


# ─── Paginación + sync incremental de Liked Songs ─────────────────────────────

@respx.mock
async def test_get_liked_songs_paginates_and_skips_null_tracks():
    # Las dos páginas comparten path (/me/tracks); se encadenan con side_effect en
    # una sola ruta (registrar dos rutas del mismo path haría que la primera
    # capturara también la segunda petición y entrara en bucle).
    respx.get(f"{BASE}/me/tracks").mock(side_effect=[
        httpx.Response(200, json={
            "items": [{"track": {"id": "s1"}}, {"track": None}, {"track": {"id": "s2"}}],
            "next": f"{BASE}/me/tracks?offset=50",
        }),
        httpx.Response(200, json={"items": [{"track": {"id": "s3"}}], "next": None}),
    ])
    out = await svc.get_liked_songs(TOKEN)
    assert [t["id"] for t in out] == ["s1", "s2", "s3"]   # el track None se saltó


@respx.mock
async def test_get_liked_songs_stops_at_known_id():
    respx.get(f"{BASE}/me/tracks").mock(return_value=httpx.Response(200, json={
        "items": [{"track": {"id": "new1"}}, {"track": {"id": "known"}}, {"track": {"id": "new2"}}],
        "next": f"{BASE}/me/tracks?offset=50",
    }))
    # Al toparse con un id ya conocido, para: lo de después ya se importó antes.
    out = await svc.get_liked_songs(TOKEN, known_ids={"known"})
    assert [t["id"] for t in out] == ["new1"]


# ─── Escrituras ───────────────────────────────────────────────────────────────

@respx.mock
async def test_add_and_remove_liked_songs():
    put = respx.put(f"{BASE}/me/library").mock(return_value=httpx.Response(200))
    delete = respx.delete(f"{BASE}/me/library").mock(return_value=httpx.Response(200))
    await svc.add_to_liked_songs("t1", TOKEN)
    await svc.remove_from_liked_songs("t1", TOKEN)
    assert put.called and delete.called


@respx.mock
async def test_create_playlist_and_add_tracks():
    respx.post(f"{BASE}/me/playlists").mock(
        return_value=httpx.Response(201, json={"id": "PL1"})
    )
    add = respx.post(f"{BASE}/playlists/PL1/items").mock(return_value=httpx.Response(201))
    created = await svc.create_playlist("Mix", "desc", TOKEN)
    assert created["id"] == "PL1"
    await svc.add_tracks_to_playlist("PL1", ["t1", "t2"], TOKEN)
    assert add.called


@respx.mock
async def test_get_playlist_tracks_unwraps_items():
    respx.get(f"{BASE}/playlists/PL1/items").mock(return_value=httpx.Response(200, json={
        "items": [{"item": {"id": "t1"}}, {"item": None}, {"item": {"id": "t2"}}],
        "next": None,
    }))
    out = await svc.get_playlist_tracks("PL1", TOKEN)
    assert [t["id"] for t in out] == ["t1", "t2"]


@respx.mock
async def test_remove_tracks_from_playlist():
    route = respx.delete(f"{BASE}/playlists/PL1/items").mock(return_value=httpx.Response(200))
    await svc.remove_tracks_from_playlist("PL1", ["t1"], TOKEN)
    assert route.called


# ─── Rate limit (429) — lo más importante ─────────────────────────────────────

@respx.mock
async def test_get_retries_after_429_then_succeeds():
    # 429 con Retry-After 0 (espera instantánea) → reintenta → 200.
    respx.get(f"{BASE}/tracks/t1").mock(side_effect=[
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"id": "t1"}),
    ])
    assert (await svc.get_track("t1", TOKEN))["id"] == "t1"


@respx.mock
async def test_get_gives_up_when_retry_after_too_long():
    # Retry-After enorme (> tope de 8s) → NO se duerme, se propaga el 429.
    respx.get(f"{BASE}/tracks/t1").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "9999"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await svc.get_track("t1", TOKEN)
