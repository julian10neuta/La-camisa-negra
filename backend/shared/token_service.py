# shared/token_service.py
# Cliente de tokens de Spotify para los microservicios internos (music_service,
# recommendation_service). No refresca tokens con Spotify —eso es exclusivo del
# authentication_service—; solo consulta el token vía el auth service y lo cachea
# en Redis para no llamar al auth service en cada request.
# Se movió a shared/ para reusarlo desde varios servicios sin duplicarlo.
from datetime import datetime, timedelta
import httpx
from redis import Redis


class TokenService:

    # Margen que se le resta a la vida restante del token antes de cachear, para
    # que Redis expire SIEMPRE antes que el token real de Spotify y nunca sirva
    # uno ya invalidado por un refresh del authentication_service.
    EXPIRY_BUFFER_SECONDS = 60
    # Techo de seguridad por si el auth service no manda expires_at (no debería
    # cachearse más que la vida máxima ~60min de un token de Spotify).
    MAX_TTL_SECONDS = 50 * 60

    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.auth_service_url = "http://authentication_service:8001/auth/tokens"

    async def get_token(self, spotify_id: str) -> str:
        cache_key = f"spotify_token:{spotify_id}"

        # 1. Intentar desde Redis primero
        cached = self.redis.get(cache_key)
        if cached:
            return cached.decode("utf-8")

        # 2. Si no está en caché, pedirlo al authentication_service
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.auth_service_url}/{spotify_id}"
            )

        if response.status_code != 200:
            raise ValueError(
                f"No se pudo obtener token para {spotify_id}: {response.text}"
            )

        data = response.json()
        access_token = data["access_token"]

        # 3. Cachear atado a la vida REAL que le queda al token, no a un TTL fijo.
        #    El auth service manda 'expires_at' (UTC ISO). El TTL de Redis es esa
        #    vida restante menos un margen: así el caché caduca antes que el token
        #    y el próximo request refetchea el vigente (evita el 401 por token
        #    obsoleto que sobrevive a un refresh).
        ttl = self._compute_ttl(data.get("expires_at"))
        if ttl > 0:
            self.redis.setex(cache_key, ttl, access_token)

        return access_token

    def _compute_ttl(self, expires_at: str | None) -> int:
        """TTL en segundos = vida restante del token − margen, acotado al techo."""
        if not expires_at:
            return self.MAX_TTL_SECONDS
        try:
            remaining = (datetime.fromisoformat(expires_at) - datetime.utcnow()).total_seconds()
        except (ValueError, TypeError):
            return self.MAX_TTL_SECONDS
        ttl = int(remaining) - self.EXPIRY_BUFFER_SECONDS
        return min(ttl, self.MAX_TTL_SECONDS)

    def invalidate(self, spotify_id: str) -> None:
        """
        Invalida el caché manualmente — útil si el authentication_service
        refresca el token por expiración y necesitamos forzar una
        re-consulta en el próximo request.
        """
        self.redis.delete(f"spotify_token:{spotify_id}")
