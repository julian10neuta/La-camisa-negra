# Tests del cliente de Deezer (shared/deezer_service.py) con respx, que intercepta
# httpx para que no salga ninguna petición real a la red.
import httpx
import pytest
import respx

from shared.deezer_service import DeezerService

pytestmark = pytest.mark.integration

BASE = "https://api.deezer.com"


@respx.mock
async def test_search_artist_returns_id_and_name():
    respx.get(f"{BASE}/search/artist").mock(
        return_value=httpx.Response(200, json={"data": [{"id": 27, "name": "Daft Punk"}]})
    )
    out = await DeezerService().search_artist("daft punk")
    assert out == {"id": 27, "name": "Daft Punk"}


@respx.mock
async def test_search_artist_empty_is_none():
    respx.get(f"{BASE}/search/artist").mock(return_value=httpx.Response(200, json={"data": []}))
    assert await DeezerService().search_artist("nadie") is None


@respx.mock
async def test_error_body_is_treated_as_no_data():
    # Deezer señala errores con 200 + {"error": {...}} → se trata como sin datos.
    respx.get(f"{BASE}/search/artist").mock(
        return_value=httpx.Response(200, json={"error": {"code": 4, "message": "Quota"}})
    )
    assert await DeezerService().search_artist("x") is None


@respx.mock
async def test_get_related_artists_maps_items():
    respx.get(f"{BASE}/artist/27/related").mock(
        return_value=httpx.Response(200, json={"data": [
            {"id": 1, "name": "Justice"}, {"id": 2, "name": "Cassius"},
        ]})
    )
    out = await DeezerService().get_related_artists(27)
    assert out == [{"id": 1, "name": "Justice"}, {"id": 2, "name": "Cassius"}]


@respx.mock
async def test_get_artist_top_maps_title_and_artist():
    respx.get(f"{BASE}/artist/27/top").mock(
        return_value=httpx.Response(200, json={"data": [
            {"title": "One More Time", "artist": {"name": "Daft Punk"}},
            {"title": "Solo sin artista"},   # sin artist → cadena vacía
        ]})
    )
    out = await DeezerService().get_artist_top(27)
    assert out == [
        {"title": "One More Time", "artist": "Daft Punk"},
        {"title": "Solo sin artista", "artist": ""},
    ]
