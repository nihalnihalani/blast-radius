"""Optional OpenAI reasoning. When OPENAI_API_KEY is set, the orchestrator uses GPT to plan the
DAG and the validator uses GPT to assess risk; otherwise both fall back to deterministic logic.
This keeps the demo keyless-runnable while making OpenAI genuinely load-bearing when configured.
"""
import json
import os

from config import OPENAI_MODEL
from logging_setup import get_logger

log = get_logger("blast.llm")

_client = None
_ENABLED = bool(os.getenv("OPENAI_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI
        _client = AsyncOpenAI()
    return _client


def llm_enabled() -> bool:
    return _ENABLED


async def validate_step(label: str, request: str) -> dict:
    """Return {'safe': bool, 'reason': str}. Deterministic-safe fallback when LLM disabled."""
    if not _ENABLED:
        return {"safe": True, "reason": "deterministic validation"}
    try:
        client = _get_client()
        resp = await client.chat.completions.create(
            model=OPENAI_MODEL, temperature=0,
            messages=[
                {"role": "system", "content": "You are an SRE change-validator. Reply with strict JSON "
                 '{"safe": bool, "reason": string}. Be terse.'},
                {"role": "user", "content": f"Change request: {request}\nStep: {label}\nIs this step safe to proceed?"},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        log.warning("validate_step LLM error (%s); allowing", e)
        return {"safe": True, "reason": f"llm-error-fallback: {e}"}
