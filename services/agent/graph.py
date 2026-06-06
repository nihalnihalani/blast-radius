"""The multi-agent harness: a LangGraph StateGraph.

Shape (map-reduce validation, then a sequential HITL execution loop):

  orchestrator --(Send fan-out)--> validator*  (parallel)  --> router
  router --(cond)--> approval --> executor --(cond)--> router | recover --> router | END

Why this shape: parallel `Send` gives real multi-agent fan-out for VALIDATION (the harness
story), while execution runs sequentially so each destructive step raises exactly ONE
interrupt() at a time -- which is what CopilotKit's useLangGraphInterrupt/useInterrupt expects.
Routing keys off an order index (not a shared 'current' channel, which parallel branches would
clobber -- the bug a naive design hits).

The cockpit renders off the LangGraph STATE (streamed as AG-UI STATE_DELTA by ag-ui-langgraph),
so node-status updates flow through state via a concurrency-safe reducer. We ALSO mirror state
into RedisJSON for durability + the keyspace/breaker control plane + the split-screen demo.
"""
import asyncio
import operator
import os
import uuid
from typing import Annotated

# Demo pacing so the DAG progression + breaker trip are VISIBLE on stage (set 0 to disable).
_STEP_DELAY = float(os.getenv("DEMO_STEP_DELAY", "0.45"))      # per-node running->done
_BREAKER_HOLD = float(os.getenv("DEMO_BREAKER_HOLD", "2.5"))   # how long the breaker stays visibly OPEN

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send, Command, interrupt
from langgraph.checkpoint.memory import MemorySaver

try:
    from copilotkit import CopilotKitState  # state extends this to auto-stream STATE_DELTA
except Exception:  # allow importing before copilotkit is installed
    from typing import TypedDict
    class CopilotKitState(TypedDict, total=False):  # type: ignore
        pass

from config import BREAKER_THRESHOLD
from redis_client import get_redis
from breaker import record_failure, is_open
from dag import sample_dag, write_dag, set_node_status, set_breaker
from recovery import run_recovery, remember_failure
from events import emit_breaker_tripped
from weave_setup import op, agent_attributes


def _merge_nodes(a: dict, b: dict) -> dict:
    """Reducer: shallow-merge node patches by id so parallel Send writes don't clobber.
    Each writer returns the FULL node object for its id."""
    return {**(a or {}), **(b or {})}


def _last(a, b):
    return b if b is not None else a


class BlastRadiusState(CopilotKitState):
    run_id: str
    request: str
    dag_nodes: Annotated[dict, _merge_nodes]   # {node_id: {label,status,agent,destructive}}
    edges: list
    order: list                                 # topological node order (single writer)
    idx: Annotated[int, _last]                  # execution pointer
    simulate_runaway: bool
    breaker_open: bool
    tripped_node: str | None
    completed: Annotated[list, operator.add]


def _topo_order(nodes: dict, edges: list) -> list:
    """Kahn topological sort; falls back to insertion order if assumptions fail."""
    ids = list(nodes.keys())
    indeg = {n: 0 for n in ids}
    adj: dict = {n: [] for n in ids}
    for a, b in edges:
        if a in indeg and b in indeg:
            adj[a].append(b)
            indeg[b] += 1
    queue = [n for n in ids if indeg[n] == 0]
    out: list = []
    while queue:
        n = queue.pop(0)
        out.append(n)
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    return out if len(out) == len(ids) else ids


@op
async def orchestrator_node(state: BlastRadiusState):
    run_id = state.get("run_id") or str(uuid.uuid4())
    request = state.get("request", "Scale the payments service")
    d = sample_dag(run_id, request)
    r = await get_redis()
    await write_dag(r, run_id, d)
    return {"run_id": run_id, "request": request, "dag_nodes": d["nodes"], "edges": d["edges"],
            "order": _topo_order(d["nodes"], d["edges"]), "idx": 0,
            "breaker_open": False, "tripped_node": None}


def fan_out_steps(state: BlastRadiusState):
    """Conditional edge -> a Send per node triggers true parallel validation in one superstep."""
    return [Send("validator", {**state, "_target": nid}) for nid in state["dag_nodes"]]


@op
async def validator_node(state: BlastRadiusState):
    nid = state["_target"]                       # travels with the Send payload, not shared state
    node = dict(state["dag_nodes"][nid])
    r = await get_redis()
    with agent_attributes(f"validator-{nid}", nid, "CLOSED", state["run_id"]):
        node = {**node, "status": "validated", "agent": f"validator-{nid}"}
        await set_node_status(r, state["run_id"], nid, node)
    return {"dag_nodes": {nid: node}}


def route_from_router(state: BlastRadiusState):
    idx, order = state["idx"], state["order"]
    if idx >= len(order):
        return "recover" if state.get("breaker_open") else END
    node = state["dag_nodes"][order[idx]]
    if node.get("destructive") and node["status"] == "validated":
        return "approval"
    return "executor"


@op
async def router_node(state: BlastRadiusState):
    return {}                                    # pure routing; decision in route_from_router


@op
async def approval_node(state: BlastRadiusState):
    """Graph-enforced human gate for ONE destructive node. Pairs with useLangGraphInterrupt."""
    nid = state["order"][state["idx"]]
    decision = interrupt({"node": nid, "plan": state["dag_nodes"][nid]})
    # CopilotKit useLangGraphInterrupt resolves a STRING ("approved"/"rejected"); also accept a dict.
    if isinstance(decision, dict):
        approved = bool(decision.get("approved", False))
    else:
        approved = str(decision).strip().lower() in ("approved", "approve", "true", "yes", "1")
    node = {**state["dag_nodes"][nid], "status": "approved" if approved else "blocked"}
    r = await get_redis()
    await set_node_status(r, state["run_id"], nid, node)
    return {"dag_nodes": {nid: node}}


@op
async def executor_node(state: BlastRadiusState):
    nid = state["order"][state["idx"]]
    node = dict(state["dag_nodes"][nid])
    r = await get_redis()

    if node["status"] == "blocked":              # operator rejected -> skip
        return {"idx": state["idx"] + 1}

    agent_id = f"executor-{nid}"
    running = {**node, "status": "running", "agent": agent_id}
    await set_node_status(r, state["run_id"], nid, running)
    if _STEP_DELAY:
        await asyncio.sleep(_STEP_DELAY)                       # let "running" (yellow) be seen

    if state.get("simulate_runaway") and nid == "update-lb":
        # Runaway: loop + fail. Trip the Redis breaker at the threshold (below recursion_limit)
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
    return {"dag_nodes": {nid: done}, "completed": [nid], "idx": state["idx"] + 1}


@op
async def recover_node(state: BlastRadiusState):
    r = await get_redis()
    nid = state.get("tripped_node") or state["order"][state["idx"]]
    node = dict(state["dag_nodes"][nid])
    if _BREAKER_HOLD:
        await asyncio.sleep(_BREAKER_HOLD)                     # keep the breaker visibly OPEN (red pulse)
    with agent_attributes("recovery", nid, "HALF_OPEN", state["run_id"]):
        result = await run_recovery(r, state["run_id"], nid)
        done = {**node, "status": "done", "agent": "recovery"}
        await set_node_status(r, state["run_id"], nid, done)
        await set_breaker(r, state["run_id"], False, None)
    return {"dag_nodes": {nid: done}, "breaker_open": False, "tripped_node": None,
            "idx": state["idx"] + 1, "recovery": result}


def build_graph():
    g = StateGraph(BlastRadiusState)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("validator", validator_node)
    g.add_node("router", router_node)
    g.add_node("approval", approval_node)
    g.add_node("executor", executor_node)
    g.add_node("recover", recover_node)

    g.add_edge(START, "orchestrator")
    g.add_conditional_edges("orchestrator", fan_out_steps, ["validator"])
    g.add_edge("validator", "router")            # join: router runs once after all validators
    g.add_conditional_edges("router", route_from_router, ["approval", "executor", "recover", END])
    g.add_edge("approval", "executor")
    g.add_conditional_edges("executor", lambda s: "recover" if s.get("breaker_open") else "router",
                            ["recover", "router"])
    g.add_edge("recover", "router")

    # checkpointer REQUIRED for interrupt() to pause/resume. MemorySaver is safe for sync+async.
    return g.compile(checkpointer=MemorySaver())
