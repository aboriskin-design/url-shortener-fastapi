import redis

from app.config import settings


# простой клиент (без asyncio, нам хватит для дз)
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

CACHE_TTL_SECONDS = 300  # 5 минут


def cache_key(short_code: str) -> str:
    return f"link:{short_code}"


def get_cached_url(short_code: str) -> str | None:
    return redis_client.get(cache_key(short_code))


def set_cached_url(short_code: str, original_url: str):
    redis_client.setex(cache_key(short_code), CACHE_TTL_SECONDS, original_url)


def delete_cached_url(short_code: str):
    redis_client.delete(cache_key(short_code))