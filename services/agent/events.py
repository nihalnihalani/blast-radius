"""AG-UI CustomEvent emission for the breaker-trip animation.

The PRIMARY, reliable signal for the red pulse is shared STATE (breaker_open / tripped_node in
dag.py + graph.py) which auto-streams as STATE_DELTA. This module adds a NAMED AG-UI CUSTOM
event as well, because it's flashier and gives the frontend an explicit hook
(agent.subscribe({onCustomEvent})). If custom-event delivery is flaky on your local LangGraph
(see langgraph issue #2574), the UI still works off state alone -- do not block on this.

Under the hood CopilotKit forwards langchain custom events to the AG-UI stream. We dispatch via
langchain_core's adispatch_custom_event from WITHIN a node (it needs the run context).
"""


async def emit_breaker_tripped(node_id: str, agent_id: str, failure_count: int) -> None:
    payload = {"node_id": node_id, "agent_id": agent_id, "failure_count": failure_count}
    try:
        from langchain_core.callbacks.manager import adispatch_custom_event
        # CopilotKit/ag-ui-langgraph relays this to the frontend as an AG-UI CUSTOM event.
        await adispatch_custom_event("CIRCUIT_BREAKER_TRIPPED", payload)
    except Exception:
        # Non-fatal: the shared-state path already drives the UI. Log and continue.
        print(f"[events] custom-event dispatch skipped: {payload}")
