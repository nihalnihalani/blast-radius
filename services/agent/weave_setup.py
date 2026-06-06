"""Weave instrumentation helpers. LangGraph has no native Weave adapter, so we wrap node
functions with @weave.op manually and tag spans with weave.attributes(breaker_state=...).
"""
import weave

from config import WEAVE_PROJECT


def init_weave() -> None:
    weave.init(WEAVE_PROJECT)


def agent_attributes(agent_id: str, node_id: str, breaker_state: str, run_id: str):
    """Context manager: every op inside inherits these attrs -> filter traces by breaker_state."""
    return weave.attributes({
        "agent_id": agent_id,
        "node_id": node_id,
        "breaker_state": breaker_state,  # CLOSED | OPEN | HALF_OPEN
        "run_id": run_id,
    })
