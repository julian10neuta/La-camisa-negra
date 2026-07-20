# rag_service/dependencies.py
from shared.redis import get_redis_client


def get_redis():
    client = get_redis_client()
    try:
        yield client
    finally:
        client.close()
