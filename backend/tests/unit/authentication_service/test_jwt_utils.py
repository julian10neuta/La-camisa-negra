# Test unitario del minteo del JWT propio de la app:
# authentication_service/utils/jwt_utils.create_access_token
# (El JWT de la app NO es el token de Spotify; lleva {sub: spotify_id, id: user.id}.)
import jwt
import pytest
from datetime import datetime, timezone

from authentication_service.utils.jwt_utils import create_access_token
from shared.config import settings


def test_token_roundtrips_with_the_configured_secret(secret_key):
    token = create_access_token({"sub": "spotify-abc", "id": 5})
    payload = jwt.decode(token, secret_key, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "spotify-abc"
    assert payload["id"] == 5


def test_token_has_expiry_about_seven_days_out(secret_key):
    token = create_access_token({"sub": "x"})
    payload = jwt.decode(token, secret_key, algorithms=[settings.ALGORITHM])
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    days_out = (exp - datetime.now(timezone.utc)).total_seconds() / 86400
    assert 6.9 < days_out <= 7.0


def test_token_signed_with_other_key_is_rejected(secret_key):
    token = create_access_token({"sub": "x"})
    # Clave distinta (y >=32 bytes, para no disparar el aviso de clave HMAC corta).
    other_key = "otra-clave-distinta-pero-suficientemente-larga"
    with pytest.raises(jwt.InvalidTokenError):
        jwt.decode(token, other_key, algorithms=[settings.ALGORITHM])
