"""The REAL circuit breaker (Redis), and the keyspace-notification control plane.

This is the heart of the 'beyond cache' Redis story. A setTimeout in the agent
process cannot do this: the breaker state is external and durable, trips even if
the agent is wedged, and is visible to every worker instantly.

Key schema:
  cb:{agent_id}:failures   String, INCR + TTL window   -> failure counter
  cb:{agent_id}:open       String, SET EX               -> breaker-open flag (fires keyevents)
"""
import asyncio

import redis.asyncio as redis

from config import (
    BREAKER_OPEN_TTL_SECONDS,
    BREAKER_THRESHOLD,
    BREAKER_WINDOW_SECONDS,
)

# Atomic INCR + EXPIRE(on first) + SET-open(at threshold). Removes the INCR/EXPIRE race
# that would otherwise leak a counter with no TTL. Returns the current failure count.
_TRIP_LUA = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
if n >= tonumber(ARGV[2]) then redis.call('SET', KEYS[2], '1', 'EX', ARGV[3]) end
return n
"""


def _keys(agent_id: str) -> tuple[str, str]:
    return f"cb:{agent_id}:failures", f"cb:{agent_id}:open"


async def record_failure(r: redis.Redis, agent_id: str) -> int:
    """Record one failure; trips the breaker atomically at the threshold. Returns count."""
    fkey, okey = _keys(agent_id)
    count = await r.eval(
        _TRIP_LUA, 2, fkey, okey,
        BREAKER_WINDOW_SECONDS, BREAKER_THRESHOLD, BREAKER_OPEN_TTL_SECONDS,
    )
    return int(count)


async def is_open(r: redis.Redis, agent_id: str) -> bool:
    _, okey = _keys(agent_id)
    return bool(await r.exists(okey))


async def force_reset(r: redis.Redis, agent_id: str) -> None:
    """Q&A button: delete the open key now -> fires an :expired keyevent immediately."""
    fkey, okey = _keys(agent_id)
    await r.delete(okey, fkey)


async def keyspace_listener(r: redis.Redis, trip_queue: "asyncio.Queue[tuple[str, str]]") -> None:
    """Zero-polling control plane: subscribe to keyspace events and push trips/resets onto a queue.

    Subscribe to :set for the INSTANT trip signal (the :expired event lags under load because
    it fires only when Redis actually deletes the key). :expired gives us the auto-reset beat.
    The orchestrator drains `trip_queue` inside the run context and updates shared state / emits
    the AG-UI CustomEvent. Do NOT emit AG-UI events directly from this background task -- it has
    no LangGraph run context and the emit would silently no-op. See docs/RISKS.md #5.
    """
    pubsub = r.pubsub()
    await pubsub.subscribe("__keyevent@0__:set", "__keyevent@0__:expired")
    async for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue
        channel, key = msg["channel"], msg["data"]
        if not key.endswith(":open"):
            continue
        agent_id = key.split(":")[1]
        if channel.endswith(":set"):
            await trip_queue.put(("TRIPPED", agent_id))
        elif channel.endswith(":expired"):
            await trip_queue.put(("RESET", agent_id))
