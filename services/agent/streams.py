"""Redis Streams work bus + dead-letter queue (consumer groups).

  agents:tasks   Stream + group 'workers'   -> units of work
  agents:dlq     Stream                      -> dead-lettered work for the recovery agent
"""
import redis.asyncio as redis

from config import DLQ_REDELIVERY_THRESHOLD

TASKS = "agents:tasks"
DLQ = "agents:dlq"
GROUP = "workers"


async def ensure_group(r: redis.Redis) -> None:
    try:
        await r.xgroup_create(TASKS, GROUP, id="$", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):  # group already exists -> fine
            raise


async def enqueue(r: redis.Redis, fields: dict) -> str:
    return await r.xadd(TASKS, fields)


async def claim_new(r: redis.Redis, consumer: str, count: int = 10, block_ms: int = 2000):
    return await r.xreadgroup(GROUP, consumer, {TASKS: ">"}, count=count, block=block_ms)


async def ack(r: redis.Redis, msg_id: str) -> int:
    return await r.xack(TASKS, GROUP, msg_id)


async def reap_to_dlq(r: redis.Redis, consumer: str, min_idle_ms: int = 2000) -> int:
    """Reclaim stuck work; route anything redelivered too many times to the DLQ. Returns DLQ count."""
    moved = 0
    _next, claimed, _deleted = await r.xautoclaim(TASKS, GROUP, consumer, min_idle_ms, "0")
    for msg_id, fields in claimed:
        pend = await r.xpending_range(TASKS, GROUP, min=msg_id, max=msg_id, count=1)
        # NB: redis-py names the delivery-count field 'times_delivered'.
        if pend and pend[0]["times_delivered"] >= DLQ_REDELIVERY_THRESHOLD:
            await r.xadd(DLQ, fields)
            await r.xack(TASKS, GROUP, msg_id)
            moved += 1
    return moved


async def seed_dlq(r: redis.Redis, fields: dict) -> str:
    """Pre-seed one DLQ message before the demo so 'Resume with safe fallback' is instant."""
    return await r.xadd(DLQ, fields)


async def drain_dlq_one(r: redis.Redis):
    """Recovery agent pulls one dead-lettered item."""
    items = await r.xrange(DLQ, count=1)
    if items:
        msg_id, fields = items[0]
        await r.xdel(DLQ, msg_id)
        return fields
    return None
