# Test unitario de la validación de identidad del gateway:
# api_gateway/security.py (is_public_path, extract_spotify_id_from_request).
# El gateway valida el JWT y saca el spotify_id; los servicios internos confían
# en la cabecera que inyecta. Si esto falla, la seguridad entera se cae.
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api_gateway.security import is_public_path, extract_spotify_id_from_request
from authentication_service.utils.jwt_utils import create_access_token


def _request(auth_header=None):
    """Un objeto mínimo con .headers.get(...), como el Request de Starlette."""
    headers = {}
    if auth_header is not None:
        headers["Authorization"] = auth_header
    return SimpleNamespace(headers=headers)


# ─── is_public_path ───────────────────────────────────────────────────────────

def test_public_paths_bypass_auth():
    assert is_public_path("/auth/login") is True
    assert is_public_path("/auth/callback?code=x") is True
    assert is_public_path("/docs") is True


def test_protected_paths_are_not_public():
    assert is_public_path("/music/interactions/likes") is False
    assert is_public_path("/dashboard") is False


# ─── extract_spotify_id_from_request ──────────────────────────────────────────

def test_valid_bearer_token_returns_spotify_id(secret_key):
    token = create_access_token({"sub": "spotify-xyz", "id": 1})
    assert extract_spotify_id_from_request(_request(f"Bearer {token}")) == "spotify-xyz"


def test_missing_header_is_401(secret_key):
    with pytest.raises(HTTPException) as exc:
        extract_spotify_id_from_request(_request(None))
    assert exc.value.status_code == 401


def test_non_bearer_header_is_401(secret_key):
    with pytest.raises(HTTPException) as exc:
        extract_spotify_id_from_request(_request("Basic abc"))
    assert exc.value.status_code == 401


def test_token_with_bad_signature_is_401(secret_key):
    # Token firmado con otra clave → firma inválida. (Clave >=32 bytes para no
    # disparar el aviso de clave HMAC corta de PyJWT.)
    import jwt
    forged = jwt.encode({"sub": "x"}, "clave-equivocada-pero-suficientemente-larga", algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        extract_spotify_id_from_request(_request(f"Bearer {forged}"))
    assert exc.value.status_code == 401


def test_token_without_sub_is_401(secret_key):
    token = create_access_token({"id": 99})   # sin 'sub'
    with pytest.raises(HTTPException) as exc:
        extract_spotify_id_from_request(_request(f"Bearer {token}"))
    assert exc.value.status_code == 401
    assert "spotify_id" in exc.value.detail
