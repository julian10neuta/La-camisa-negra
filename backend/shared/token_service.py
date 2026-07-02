# shared/token_service.py
# Cliente de tokens de Spotify para los microservicios internos (music_service,
# recommendation_service). No refresca tokens con Spotify —eso es exclusivo del
# authentication_service—; solo consulta el token vía el auth service y lo cachea
# en Redis para no llamar al auth service en cada request.
# Se movió a shared/ para reusarlo desde varios servicios sin duplicarlo.
from datetime import timedelta
import httpx
from redis import Redis


class TokenService:

    TOKEN_TTL_MINUTES = 50  # conservador vs los 60min reales de Spotify

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

        access_token = response.json()["access_token"]

        # 3. Cachear con TTL conservador
        self.redis.setex(
            cache_key,
            timedelta(minutes=self.TOKEN_TTL_MINUTES),
            access_token,
        )

        return access_token

    def invalidate(self, spotify_id: str) -> None:
        """
        Invalida el caché manualmente — útil si el authentication_service
        refresca el token por expiración y necesitamos forzar una
        re-consulta en el próximo request.
        """
        self.redis.delete(f"spotify_token:{spotify_id}")
