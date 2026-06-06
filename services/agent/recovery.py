"""Recovery agent: drain the dead-letter queue + pull similar past failures from RedisVL.

RedisVL is optional at dev time; if it's not installed / indexed yet we fall back to a
static safe path so the demo still completes. See docs/RISKS.md cut-list #1.
"""
import redis.asyncio as redis

from streams import drain_dlq_one

try:
    from redisvl.extensions.message_history import SemanticMessageHistory  # type: ignore
    _HAS_VL = True
except Exception:  # redisvl not installed yet
    _HAS_VL = False

from config import REDIS_URL


async def remember_failure(agent_id: str, summary: str) -> None:
    if not _HAS_VL:
        return
    hist = SemanticMessageHistory(name="recovery_context", redis_url=REDIS_URL)
    hist.add_message({"role": "system", "content": summary}, session_tag=agent_id)


async def recall_similar(prompt: str, top_k: int = 3) -> list[dict]:
    if not _HAS_VL:
        return []
    hist = SemanticMessageHistory(name="recovery_context", redis_url=REDIS_URL)
    return hist.get_relevant(prompt=prompt, top_k=top_k)


async def run_recovery(r: redis.Redis, run_id: str, failed_node: str) -> dict:
    """Consume a dead-lettered task and choose a safe fallback using past-failure context."""
    item = await drain_dlq_one(r)
    similar = await recall_similar(f"failure scaling {failed_node}")
    strategy = "safe-fallback"  # in a real system, picked from `similar`
    return {"recovered": True, "from_dlq": item, "similar_count": len(similar), "strategy": strategy}
