"""Async Redis connection + keyspace-notification setup.

We use redis-stack (RedisJSON + Search built in). One client per event loop -- in production
that's a single loop / single client; in tests each loop gets its own so connections never
cross loops (avoids 'Event loop is closed').
"""
import asyncio

import redis.asyncio as redis

from config import REDIS_URL

_clients: dict[asyncio.AbstractEventLoop, redis.Redis] = {}


async def get_redis() -> redis.Redis:
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None:
        client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        # K=keyspace, E=keyevent, $=string cmds (SET), x=expired. Catches breaker open + reset.
        # NOTE: on Redis Cloud confirm this CONFIG SET is permitted (it is on Essentials/Pro).
        await client.config_set("notify-keyspace-events", "KE$x")
        _clients[loop] = client
    return client


async def close_redis() -> None:
    loop = asyncio.get_running_loop()
    client = _clients.pop(loop, None)
    if client is not None:
        await client.aclose()
