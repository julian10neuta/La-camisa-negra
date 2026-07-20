# Test de integración del TokenService del authentication_service
# (get_valid_spotify_token): devuelve el token vigente o lo refresca con Spotify.
import httpx
import pytest
import respx
from datetime import datetime, timedelta

from authentication_service.services.token_service import TokenService
from authentication_service.repositories.user_repository import UserRepository

pytestmark = pytest.mark.integration

REFRESH_URL = "https://accounts.spotify.com/api/token"


def _seed_user(db, expiry):
    UserRepository.create_or_update_user(db, {
        "spotify_id": "u1", "name": "J", "access_token": "current",
        "refresh_token": "R", "token_expiry": expiry, "is_premium": True,
    })


async def test_returns_current_token_when_not_expired(db_session):
    _seed_user(db_session, datetime.utcnow() + timedelta(hours=1))
    token, expiry = await TokenService(db_session).get_valid_spotify_token("u1")
    assert token == "current"      # sin tocar la red


@respx.mock
async def test_refreshes_when_expired(db_session):
    _seed_user(db_session, datetime.utcnow() - timedelta(minutes=1))  # ya expirado
    respx.post(REFRESH_URL).mock(return_value=httpx.Response(200, json={
        "access_token": "brand-new", "expires_in": 3600,
    }))

    token, expiry = await TokenService(db_session).get_valid_spotify_token("u1")
    assert token == "brand-new"
    # y quedó guardado en la BD
    assert UserRepository.get_by_spotify_id(db_session, "u1").access_token == "brand-new"


async def test_unknown_user_raises(db_session):
    with pytest.raises(ValueError):
        await TokenService(db_session).get_valid_spotify_token("nope")


@respx.mock
async def test_refresh_without_access_token_raises(db_session):
    _seed_user(db_session, datetime.utcnow() - timedelta(minutes=1))
    respx.post(REFRESH_URL).mock(return_value=httpx.Response(200, json={"error": "invalid"}))
    with pytest.raises(ValueError):
        await TokenService(db_session).get_valid_spotify_token("u1")
