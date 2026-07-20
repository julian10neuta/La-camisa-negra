# Test unitario de los esquemas Pydantic de authentication_service.
import pytest
from datetime import datetime
from pydantic import ValidationError

from authentication_service.schemas.user_schema import (
    UserCreate, UserTokenUpdate, AuthCodeRequest, UserResponse,
)


def test_user_create_requires_tokens_and_premium():
    u = UserCreate(spotify_id="u1", is_premium=True, access_token="a",
                   refresh_token="r", token_expiry=datetime(2030, 1, 1))
    assert u.spotify_id == "u1" and u.name is None   # name es opcional


def test_user_create_missing_field_raises():
    with pytest.raises(ValidationError):
        UserCreate(spotify_id="u1", is_premium=True)   # faltan tokens


def test_token_update_refresh_is_optional():
    # Spotify a veces no devuelve refresh_token nuevo: debe poder omitirse.
    upd = UserTokenUpdate(access_token="a", token_expiry=datetime(2030, 1, 1))
    assert upd.refresh_token is None


def test_auth_code_request():
    assert AuthCodeRequest(code="abc").code == "abc"


def test_user_response_shape():
    r = UserResponse(spotify_id="u1", is_premium=False, id=7,
                     registration_date=datetime(2026, 1, 1))
    assert r.id == 7 and r.is_premium is False
