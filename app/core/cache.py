import json
import logging
import os

from dotenv import load_dotenv
from redis import Redis
from redis.exceptions import RedisError

load_dotenv()

logger = logging.getLogger(__name__)

redis_client = Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)


def get_cached_json(key: str):
    try:
        value = redis_client.get(key)

        if value is None:
            return None

        return json.loads(value)

    except (RedisError, ValueError) as exc:
        logger.warning("Redis cache read failed: %s", exc)
        return None


def set_cached_json(key: str, value, ttl: int = 60) -> None:
    try:
        redis_client.setex(
            key,
            ttl,
            json.dumps(value, default=str),
        )

    except (RedisError, TypeError, ValueError) as exc:
        logger.warning("Redis cache write failed: %s", exc)


def delete_cache_pattern(pattern: str) -> None:
    try:
        for key in redis_client.scan_iter(match=pattern):
            redis_client.delete(key)

    except RedisError as exc:
        logger.warning("Redis cache invalidation failed: %s", exc)