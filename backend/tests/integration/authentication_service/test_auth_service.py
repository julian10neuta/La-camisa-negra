# Test de integración de AuthService.get_user_from_code (el flujo OAuth de login)
# con respx (Spotify mockeado) y SQLite. Cubre el camino feliz y los errores que
# el equipo endureció a propósito (el 429 que daba antes un 400 críptico).
import httpx
import jwt
import pytest
import respx
from fastapi import HTTPException

from shared.config import settings
from authentication_service.services.auth_service import AuthService
from shared.models import User

pytestmark = pytest.mark.integration

TOKEN_URL = "https://accounts.spotify.com/api/token"
ME_URL = "https://api.spotify.com/v1/me"


def _service(db):
    return AuthService(db, client_id="cid", client_secret="secret", redirect_uri="uri")


@respx.mock
async def test_login_success_creates_user_and_returns_jwt(db_session, secret_key):
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={
        "access_token": "AT", "refresh_token": "RT", "expires_in": 3600,
    }))
    respx.get(ME_URL).mock(return_value=httpx.Response(200, json={
        "id": "spotify-julian", "display_name": "Julian", "product": "premium",
    }))

    my_jwt, user = await _service(db_session).get_user_from_code("valid-code")

    assert user.spotify_id == "spotify-julian"
    assert user.is_premium is True
    # el usuario quedó persistido
    assert db_session.query(User).filter_by(spotify_id="spotify-julian").count() == 1
    # el JWT propio lleva el spotify_id en 'sub'
    payload = jwt.decode(my_jwt, secret_key, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "spotify-julian"


@respx.mock
async def test_invalid_code_raises_400(db_session):
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={
        "error": "invalid_grant", "error_description": "code ya usado",
    }))
    with pytest.raises(HTTPException) as exc:
        await _service(db_session).get_user_from_code("bad-code")
    assert exc.value.status_code == 400


@respx.mock
async def test_me_429_raises_429_not_cryptic_400(db_session):
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={
        "access_token": "AT", "refresh_token": "RT", "expires_in": 3600,
    }))
    respx.get(ME_URL).mock(return_value=httpx.Response(429, headers={"Retry-After": "120"},
                                                       text="Too many requests"))
    with pytest.raises(Exception) as exc:
        await _service(db_session).get_user_from_code("code")
    assert exc.value.status_code == 429


@respx.mock
async def test_me_other_error_raises_502(db_session):
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(200, json={
        "access_token": "AT", "refresh_token": "RT", "expires_in": 3600,
    }))
    respx.get(ME_URL).mock(return_value=httpx.Response(500, text="boom"))
    with pytest.raises(Exception) as exc:
        await _service(db_session).get_user_from_code("code")
    assert exc.value.status_code == 502
