# shared/redis.py
from redis import Redis
from .config import settings


def get_redis_client() -> Redis:
    return Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=0,
        decode_responses=False,
    )