"""The multi-agent harness: a LangGraph StateGraph.

orchestrator --(Send fan-out)--> validator* --> approval(interrupt) --> executor* --> recover

Every node is a @weave.op. The breaker trip is detected inside the executor loop and written to
shared state (breaker_open / tripped_node), which auto-streams to the cockpit as STATE_DELTA --
the most RELIABLE path for the red pulse. A named AG-UI CustomEvent is ALSO emitted (events.py)
for flair; the UI works off either. See docs/LANGGRAPH_ORCHESTRATION.md.

Verify on-site: `from langgraph.types import Send, Command, interrupt` (import path varies by version).
"""
import uuid

import weave
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send, Command, interrupt
from langgraph.checkpoint.memory import MemorySaver

try:
    from copilotkit import CopilotKitState  # state MUST extend this to auto-stream STATE_DELTA
except Exception:  # allows importing the module before copilotkit is installed
    CopilotKitState = dict  # type: ignore

from config import BREAKER_THRESHOLD
from redis_client import get_redis
from breaker import record_failure, is_open
from dag import sample_dag, write_dag, set_node_status, set_breaker
from recovery import run_recovery, remember_failure
from events import emit_breaker_tripped
from weave_setup import agent_attributes


class BlastRadiusState(CopilotKitState):
    run_id: str
    request: str
    dag_nodes: dict
    current: str
    simulate_runaway: bool
    breaker_open: bool
    tripped_node: str | None
    completed: list


@weave.op
async def orchestrator_node(state: BlastRadiusState):
    run_id = state.get("run_id") or str(uuid.uuid4())
    request = state.get("request", "Scale the payments service")
    dag = sample_dag(run_id, request)
    r = await get_redis()
    await write_dag(r, run_id, dag)
    return {"run_id": run_id, "request": request, "dag_nodes": dag["nodes"],
            "breaker_open": False, "tripped_node": None, "completed": []}


def fan_out_steps(state: BlastRadiusState):
    """Conditional edge -> a Send per node triggers true parallel validation in one superstep."""
    return [Send("validator", {**state, "current": nid}) for nid in state["dag_nodes"]]


@weave.op
async def validator_node(state: BlastRadiusState):
    node_id = state["current"]
    r = await get_redis()
    with agent_attributes(f"validator-{node_id}", node_id, "CLOSED", state["run_id"]):
        await set_node_status(r, state["run_id"], node_id, {"status": "running", "agent": f"validator-{node_id}"})
        # (mock) validation work
        await set_node_status(r, state["run_id"], node_id, {"status": "validated"})
    return {}


def route_after_validate(state: BlastRadiusState):
    node = state["dag_nodes"][state["current"]]
    return "approval" if node.get("destructive") else "executor"


@weave.op
async def approval_node(state: BlastRadiusState):
    """Graph-enforced human gate. Pairs with CopilotKit useInterrupt on the frontend."""
    node_id = state["current"]
    decision = interrupt({"node": node_id, "plan": state["dag_nodes"][node_id]})
    return {"_approved": bool(decision.get("approved", False))}


@weave.op
async def executor_node(state: BlastRadiusState):
    node_id = state["current"]
    agent_id = f"executor-{node_id}"
    r = await get_redis()
    await set_node_status(r, state["run_id"], node_id, {"status": "running", "agent": agent_id})

    if state.get("simulate_runaway") and node_id == "update-lb":
        # The runaway path: loop and fail. Trip the Redis breaker at the threshold,
        # which is BELOW recursion_limit, so the animation fires before any GraphRecursionError.
        for _ in range(BREAKER_THRESHOLD + 2):
            count = await record_failure(r, agent_id)
            if await is_open(r, agent_id):
                with agent_attributes(agent_id, node_id, "OPEN", state["run_id"]):
                    await set_node_status(r, state["run_id"], node_id, {"status": "failed"})
                    await set_breaker(r, state["run_id"], True, node_id)
                    await emit_breaker_tripped(node_id, agent_id, count)
                    await remember_failure(agent_id, f"runaway scaling {node_id}, count={count}")
                return Command(goto="recover", update={"breaker_open": True, "tripped_node": node_id})

    # happy path (mock apply)
    with agent_attributes(agent_id, node_id, "CLOSED", state["run_id"]):
        await set_node_status(r, state["run_id"], node_id, {"status": "done"})
    return {"completed": state.get("completed", []) + [node_id]}


@weave.op
async def recover_node(state: BlastRadiusState):
    r = await get_redis()
    node_id = state.get("tripped_node")
    with agent_attributes("recovery", node_id, "HALF_OPEN", state["run_id"]):
        result = await run_recovery(r, state["run_id"], node_id)
        await set_node_status(r, state["run_id"], node_id, {"status": "done", "agent": "recovery"})
        await set_breaker(r, state["run_id"], False, None)
    return {"breaker_open": False, "tripped_node": None, "recovery": result}


def build_graph():
    g = StateGraph(BlastRadiusState)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("validator", validator_node)
    g.add_node("approval", approval_node)
    g.add_node("executor", executor_node)
    g.add_node("recover", recover_node)

    g.add_edge(START, "orchestrator")
    g.add_conditional_edges("orchestrator", fan_out_steps, ["validator"])
    g.add_conditional_edges("validator", route_after_validate, ["approval", "executor"])
    g.add_edge("approval", "executor")
    g.add_edge("recover", END)
    # executor -> END or recover is handled via Command(goto=...) returns above

    # checkpointer REQUIRED for interrupt() to pause/resume. CopilotKit may inject its own;
    # MemorySaver is safe for sync+async and fine for the hackathon.
    return g.compile(checkpointer=MemorySaver())
