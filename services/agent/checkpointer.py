"""Durable LangGraph checkpointer.

Production default: Redis (langgraph-checkpoint-redis) so in-flight runs + interrupt state
survive a process restart -- and the checkpoint store is another genuine Redis-beyond-cache use.
Falls back to in-memory if Redis is unavailable or CHECKPOINTER=memory.
"""
import os

from config import REDIS_URL
from logging_setup import get_logger

log = get_logger("blast.checkpointer")
_saver = None


def get_checkpointer():
    global _saver
    if _saver is not None:
        return _saver
    if os.getenv("CHECKPOINTER", "redis").lower() == "memory":
        from langgraph.checkpoint.memory import MemorySaver
        _saver = MemorySaver()
        log.info("checkpointer: in-memory (CHECKPOINTER=memory)")
        return _saver
    try:
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver
        _saver = AsyncRedisSaver(redis_url=REDIS_URL)
        log.info("checkpointer: Redis (%s)", REDIS_URL)
    except Exception as e:  # package missing / connection issue
        from langgraph.checkpoint.memory import MemorySaver
        _saver = MemorySaver()
        log.warning("checkpointer: Redis unavailable (%s); using in-memory", e)
    return _saver


async def setup_checkpointer() -> None:
    """Create Redis indices (idempotent). No-op for in-memory."""
    s = get_checkpointer()
    if hasattr(s, "asetup"):
        try:
            await s.asetup()
            log.info("checkpointer: Redis indices ready")
        except Exception as e:
            log.warning("checkpointer asetup failed (continuing): %s", e)
