"""Recovery agent: drain the dead-letter queue + pull similar past failures from RedisVL.

RedisVL semantic memory is OPTIONAL. It needs an embedding backend (sentence-transformers, or an
OpenAI key for OpenAITextVectorizer). If neither is available we degrade to a static safe path so
recovery still completes -- the DLQ drain is what matters for the demo. See docs/RISKS.md cut-list #1.

To enable real semantic recovery memory:  pip install sentence-transformers
"""
import os

import redis.asyncio as redis

from streams import drain_dlq_one
from config import REDIS_URL

_history = None          # lazily-built SemanticMessageHistory, or None if unavailable
_VL_TRIED = False
_VL_OK = False


def _get_history():
    """Build the semantic history lazily; cache failure so we only probe once."""
    global _history, _VL_TRIED, _VL_OK
    if _VL_TRIED:
        return _history
    _VL_TRIED = True
    try:
        from redisvl.extensions.message_history import SemanticMessageHistory
        # Prefer OpenAI embeddings if a key exists (no heavy local model); else HF (needs the lib).
        if os.getenv("OPENAI_API_KEY"):
            from redisvl.utils.vectorize import OpenAITextVectorizer
            vec = OpenAITextVectorizer(model="text-embedding-3-small")
            _history = SemanticMessageHistory(name="recovery_context", redis_url=REDIS_URL, vectorizer=vec)
        else:
            _history = SemanticMessageHistory(name="recovery_context", redis_url=REDIS_URL)
        _VL_OK = True
    except Exception as e:
        print(f"[recovery] semantic memory disabled ({type(e).__name__}); using static fallback")
        _history = None
    return _history


async def remember_failure(agent_id: str, summary: str) -> None:
    hist = _get_history()
    if hist is None:
        return
    try:
        hist.add_message({"role": "system", "content": summary}, session_tag=agent_id)
    except Exception as e:
        print(f"[recovery] remember_failure skipped: {e}")


async def recall_similar(prompt: str, top_k: int = 3) -> list:
    hist = _get_history()
    if hist is None:
        return []
    try:
        return hist.get_relevant(prompt=prompt, top_k=top_k)
    except Exception:
        return []


async def run_recovery(r: redis.Redis, run_id: str, failed_node: str) -> dict:
    """Consume a dead-lettered task and choose a safe fallback using past-failure context."""
    item = await drain_dlq_one(r)
    similar = await recall_similar(f"failure scaling {failed_node}")
    strategy = "safe-fallback"  # in a real system, picked from `similar`
    return {"recovered": True, "from_dlq": item, "similar_count": len(similar),
            "strategy": strategy, "semantic_memory": _VL_OK}
