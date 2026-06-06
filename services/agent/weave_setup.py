"""Weave instrumentation helpers. LangGraph has no native Weave adapter, so we wrap node
functions with @weave.op manually and tag spans with weave.attributes(breaker_state=...).

Weave is OPTIONAL: without a W&B login the @weave.op decorators still run (they just warn once
and skip logging), and init_weave() degrades gracefully. Set WEAVE_DISABLED=1 to silence it.
"""
import contextlib
import os

import weave

from config import WEAVE_PROJECT

_ENABLED = False


def init_weave() -> bool:
    """Initialise Weave tracing. Returns True if tracing is live, False if skipped."""
    global _ENABLED
    if os.getenv("WEAVE_DISABLED") == "1":
        print("[weave] disabled via WEAVE_DISABLED=1")
        return False
    try:
        weave.init(WEAVE_PROJECT)
        _ENABLED = True
        print(f"[weave] tracing -> project '{WEAVE_PROJECT}'")
        return True
    except Exception as e:  # no W&B login / offline -> keep running without tracing
        print(f"[weave] init skipped ({e}); running without tracing")
        return False


def op(fn):
    """Decorator: trace with weave when available, else a no-op passthrough.

    weave.op works even before weave.init (it warns once and skips logging), so we always
    wrap when weave is importable -- this keeps tracing on whenever a W&B login exists.
    """
    try:
        return weave.op(fn)
    except Exception:
        return fn


def agent_attributes(agent_id: str, node_id: str | None, breaker_state: str, run_id: str):
    """Context manager: every op inside inherits these attrs -> filter traces by breaker_state."""
    if not _ENABLED:
        return contextlib.nullcontext()
    return weave.attributes({
        "agent_id": agent_id,
        "node_id": node_id,
        "breaker_state": breaker_state,  # CLOSED | OPEN | HALF_OPEN
        "run_id": run_id,
    })
