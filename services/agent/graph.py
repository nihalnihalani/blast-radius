"""The multi-agent harness: a LangGraph StateGraph.

orchestrator --(Send fan-out)--> validator* --> approval(interrupt) --> executor* --> recover

The cockpit renders off the LangGraph STATE (streamed as AG-UI STATE_DELTA at every node
boundary by the CopilotKit/ag-ui-langgraph adapter), so node-status updates flow through graph
state via a concurrency-safe reducer (parallel Send writes would otherwise collide). We ALSO
mirror state into RedisJSON for durability + the keyspace/breaker control plane + the split-screen
key-browser demo. See docs/LANGGRAPH_ORCHESTRATION.md and docs/RISKS.md.

Verify on-site: `from langgraph.types import Send, Command, interrupt` (import path varies by version).
"""
import operator
import uuid
from typing import Annotated

import weave
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send, Command, interrupt
from langgraph.checkpoint.memory import MemorySaver

try:
    from copilotkit import CopilotKitState  # state MUST extend this to auto-stream STATE_DELTA
except Exception:  # allows importing this module before copilotkit is installed
    CopilotKitState = dict  # type: ignore

from config import BREAKER_THRESHOLD
from redis_client import get_redis
from breaker import record_failure, is_open
from dag import sample_dag, write_dag, set_node_status, set_breaker
from recovery import run_recovery, remember_failure
from events import emit_breaker_tripped
from weave_setup import agent_attributes


def _merge_nodes(a: dict, b: dict) -> dict:
    """Reducer: shallow-merge node patches by id so parallel Send writes don't clobber.
    Each writer returns the FULL node object for its id (spread of the existing node)."""
    return {**(a or {}), **(b or {})}


class BlastRadiusState(CopilotKitState):
    run_id: str
    request: str
    dag_nodes: Annotated[dict, _merge_nodes]   # {node_id: {label,status,agent,destructive}}
    edges: list                                 # [[from,to], ...]  (single writer: orchestrator)
    current: str
    simulate_runaway: bool
    breaker_open: bool
    tripped_node: str | None
    completed: Annotated[list, operator.add]


@weave.op
async def orchestrator_node(state: BlastRadiusState):
    run_id = state.get("run_id") or str(uuid.uuid4())
    request = state.get("request", "Scale the payments service")
    dag = sample_dag(run_id, request)
    r = await get_redis()
    await write_dag(r, run_id, dag)
    return {"run_id": run_id, "request": request, "dag_nodes": dag["nodes"],
            "edges": dag["edges"], "breaker_open": False, "tripped_node": None}


def fan_out_steps(state: BlastRadiusState):
    """Conditional edge -> a Send per node triggers true parallel validation in one superstep."""
    return [Send("validator", {**state, "current": nid}) for nid in state["dag_nodes"]]


@weave.op
async def validator_node(state: BlastRadiusState):
    nid = state["current"]
    node = dict(state["dag_nodes"][nid])
    r = await get_redis()
    with agent_attributes(f"validator-{nid}", nid, "CLOSED", state["run_id"]):
        node = {**node, "status": "validated", "agent": f"validator-{nid}"}
        await set_node_status(r, state["run_id"], nid, node)  # mirror to RedisJSON
    return {"dag_nodes": {nid: node}}                          # stream to cockpit


def route_after_validate(state: BlastRadiusState):
    node = state["dag_nodes"][state["current"]]
    return "approval" if node.get("destructive") else "executor"


@weave.op
async def approval_node(state: BlastRadiusState):
    """Graph-enforced human gate. Pairs with CopilotKit useLangGraphInterrupt/useInterrupt."""
    nid = state["current"]
    decision = interrupt({"node": nid, "plan": state["dag_nodes"][nid]})
    approved = bool(decision.get("approved", False)) if isinstance(decision, dict) else bool(decision)
    nid_patch = {**state["dag_nodes"][nid], "status": "approved" if approved else "blocked"}
    return {"dag_nodes": {nid: nid_patch}}


@weave.op
async def executor_node(state: BlastRadiusState):
    nid = state["current"]
    agent_id = f"executor-{nid}"
    node = dict(state["dag_nodes"][nid])
    r = await get_redis()
    running = {**node, "status": "running", "agent": agent_id}
    await set_node_status(r, state["run_id"], nid, running)

    if state.get("simulate_runaway") and nid == "update-lb":
        # Runaway path: loop + fail. Trip the Redis breaker at the threshold (below recursion_limit)
        # so the red pulse fires BEFORE any GraphRecursionError.
        for _ in range(BREAKER_THRESHOLD + 2):
            count = await record_failure(r, agent_id)
            if await is_open(r, agent_id):
                with agent_attributes(agent_id, nid, "OPEN", state["run_id"]):
                    failed = {**node, "status": "failed", "agent": agent_id}
                    await set_node_status(r, state["run_id"], nid, failed)
                    await set_breaker(r, state["run_id"], True, nid)
                    await emit_breaker_tripped(nid, agent_id, count)
                    await remember_failure(agent_id, f"runaway scaling {nid}, count={count}")
                return Command(goto="recover", update={
                    "dag_nodes": {nid: failed}, "breaker_open": True, "tripped_node": nid})

    with agent_attributes(agent_id, nid, "CLOSED", state["run_id"]):
        done = {**node, "status": "done", "agent": agent_id}
        await set_node_status(r, state["run_id"], nid, done)
    return {"dag_nodes": {nid: done}, "completed": [nid]}


@weave.op
async def recover_node(state: BlastRadiusState):
    r = await get_redis()
    nid = state.get("tripped_node")
    node = dict(state["dag_nodes"][nid])
    with agent_attributes("recovery", nid, "HALF_OPEN", state["run_id"]):
        result = await run_recovery(r, state["run_id"], nid)
        done = {**node, "status": "done", "agent": "recovery"}
        await set_node_status(r, state["run_id"], nid, done)
        await set_breaker(r, state["run_id"], False, None)
    return {"dag_nodes": {nid: done}, "breaker_open": False, "tripped_node": None, "recovery": result}


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
    # executor -> END (return) or -> recover (Command(goto=...)) is decided inside the node

    # checkpointer REQUIRED for interrupt() to pause/resume. MemorySaver is safe for sync+async.
    return g.compile(checkpointer=MemorySaver())
