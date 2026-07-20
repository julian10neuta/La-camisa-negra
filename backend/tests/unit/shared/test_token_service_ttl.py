# Tests del cálculo de TTL del caché de tokens de Spotify:
# shared/token_service.TokenService._compute_ttl (+ el camino de cache-hit de
# get_token con fakeredis). La regla de oro: el caché de Redis debe caducar
# SIEMPRE antes que el token real, para no servir uno ya invalidado por un
# refresh del authentication_service.
import pytest
from datetime import datetime, timedelta

from shared.token_service import TokenService


@pytest.fixture()
def svc(fake_redis):
    return TokenService(fake_redis)


def test_ttl_without_expiry_falls_back_to_max(svc):
    assert svc._compute_ttl(None) == TokenService.MAX_TTL_SECONDS


def test_ttl_with_invalid_expiry_falls_back_to_max(svc):
    assert svc._compute_ttl("no-es-una-fecha") == TokenService.MAX_TTL_SECONDS


def test_ttl_is_remaining_life_minus_buffer(svc):
    expires_at = (datetime.utcnow() + timedelta(seconds=1000)).isoformat()
    ttl = svc._compute_ttl(expires_at)
    # ~1000s de vida − 60s de margen = ~940 (con holgura por el paso del tiempo).
    assert 930 <= ttl <= 940


def test_ttl_is_capped_at_max(svc):
    expires_at = (datetime.utcnow() + timedelta(hours=10)).isoformat()
    assert svc._compute_ttl(expires_at) == TokenService.MAX_TTL_SECONDS


def test_ttl_for_already_expired_token_is_non_positive(svc):
    expires_at = (datetime.utcnow() - timedelta(seconds=30)).isoformat()
    # Vida negativa − margen → <= 0; get_token no lo cachearía (if ttl > 0).
    assert svc._compute_ttl(expires_at) <= 0


async def test_get_token_returns_cached_without_network(svc, fake_redis):
    # Si está en Redis, get_token NO debe llamar al authentication_service.
    fake_redis.set("spotify_token:u1", b"cached-token")
    assert await svc.get_token("u1") == "cached-token"


def test_invalidate_removes_cache(svc, fake_redis):
    fake_redis.set("spotify_token:u1", b"t")
    svc.invalidate("u1")
    assert fake_redis.get("spotify_token:u1") is None
