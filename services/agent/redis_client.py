"""Async Redis connection + keyspace-notification setup.

We use redis-stack (RedisJSON + Search built in). One shared async client.
"""
import redis.asyncio as redis

from config import REDIS_URL

_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        # K=keyspace, E=keyevent, $=string cmds (SET), x=expired. Catches breaker open + reset.
        # NOTE: on Redis Cloud confirm this CONFIG SET is permitted (it is on Essentials/Pro).
        await _client.config_set("notify-keyspace-events", "KE$x")
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
