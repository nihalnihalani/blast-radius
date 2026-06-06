"""FastAPI entrypoint: exposes the LangGraph agent to the CopilotKit runtime, starts Weave,
and runs the Redis keyspace listener that drives the breaker control-plane SSE.

Run:  uvicorn main:app --reload --port 8000
"""
import asyncio
import contextlib
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import AGENT_NAME
from weave_setup import init_weave
from redis_client import get_redis, close_redis
from breaker import keyspace_listener, force_reset
from streams import ensure_group, seed_dlq
from dag import read_dag, set_node_status
from graph import build_graph

# Background tasks + a fan-out of subscribers for the breaker control plane.
_trip_queue: "asyncio.Queue[tuple[str, str]]" = asyncio.Queue()
_subscribers: set[asyncio.Queue] = set()
_bg_tasks: list[asyncio.Task] = []


async def _fan_out_trips() -> None:
    """Drain the keyspace queue and broadcast trip/reset events to all SSE subscribers."""
    while True:
        kind, agent_id = await _trip_queue.get()
        payload = json.dumps({"kind": kind, "agent_id": agent_id})
        for q in list(_subscribers):
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(payload)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    init_weave()
    r = await get_redis()
    await ensure_group(r)
    # Pre-seed one DLQ message so 'Resume with safe fallback' is instant during the demo.
    await seed_dlq(r, {"node_id": "update-lb", "action": "scale", "note": "pre-seeded"})
    _bg_tasks.append(asyncio.create_task(keyspace_listener(r, _trip_queue)))
    _bg_tasks.append(asyncio.create_task(_fan_out_trips()))
    print("[main] startup complete")
    yield
    for t in _bg_tasks:
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t
    await close_redis()


app = FastAPI(title="BLAST-RADIUS agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Build the compiled graph once; share it across both endpoints.
GRAPH = build_graph()
_DESC = "Decomposes an infra change into a blast-radius DAG and executes it under a circuit breaker."

# --- AG-UI native endpoint (PRIMARY) -----------------------------------------
# Served as a raw AG-UI stream and consumed by @ag-ui/client HttpAgent on the frontend.
# This is the reliable agent-registration path (the copilotkit remote-endpoint discovery did
# not surface the agent as routable -> "No default agent provided").
try:
    from ag_ui_langgraph import LangGraphAgent as AGUIAgent, add_langgraph_fastapi_endpoint
    add_langgraph_fastapi_endpoint(app, AGUIAgent(name=AGENT_NAME, graph=GRAPH, description=_DESC), "/agent")
    print(f"[main] AG-UI agent '{AGENT_NAME}' mounted at /agent")
except Exception as e:
    import traceback
    print(f"[main] AG-UI endpoint NOT mounted: {e}")
    traceback.print_exc()

# --- CopilotKit remote endpoint (kept for compatibility / Best-CopilotKit story) ----
try:
    from copilotkit import CopilotKitRemoteEndpoint, LangGraphAGUIAgent
    from copilotkit.integrations.fastapi import add_fastapi_endpoint

    sdk = CopilotKitRemoteEndpoint(
        agents=[LangGraphAGUIAgent(name=AGENT_NAME, description=_DESC, graph=GRAPH)],
    )
    add_fastapi_endpoint(app, sdk, "/copilotkit")
    print(f"[main] CopilotKit agent '{AGENT_NAME}' mounted at /copilotkit")
except Exception as e:
    print(f"[main] CopilotKit endpoint NOT mounted: {e}")


# --- Breaker control-plane SSE (driven by Redis keyspace notifications) -------
@app.get("/events/breaker")
async def breaker_events() -> StreamingResponse:
    """Zero-polling stream of circuit-breaker trip/reset events for the cockpit.

    This is the keyspace-notification control plane surfaced to the browser, independent of the
    agent run -- a resilient secondary channel for the red-pulse animation.
    """
    q: asyncio.Queue = asyncio.Queue(maxsize=64)
    _subscribers.add(q)

    async def gen() -> AsyncIterator[str]:
        try:
            yield "event: ping\ndata: {}\n\n"
            while True:
                payload = await q.get()
                yield f"data: {payload}\n\n"
        finally:
            _subscribers.discard(q)

    return StreamingResponse(gen(), media_type="text/event-stream")


# --- Run manager: drive the graph + stream the DAG over SSE (reliable cockpit channel) ----
# The CopilotKit useCoAgent state-sync is version-fragile; this direct channel guarantees the
# cockpit renders. It runs the SAME graph (interrupts, breaker, recovery) and streams the
# RedisJSON DAG document as it changes. CopilotKit hooks remain wired as the "intended" path.
import uuid as _uuid
from langgraph.types import Command


class _Run:
    def __init__(self):
        self.resume: asyncio.Queue = asyncio.Queue()
        self.awaiting: str | None = None
        self.done = False


_runs: dict[str, _Run] = {}


async def _drive_run(run_id: str, simulate_runaway: bool):
    r = await get_redis()
    cfg = {"configurable": {"thread_id": run_id}, "recursion_limit": 60}
    state = {"run_id": run_id, "request": "Scale the payments service",
             "simulate_runaway": simulate_runaway}
    try:
        res = await GRAPH.ainvoke(state, cfg)
        while isinstance(res, dict) and res.get("__interrupt__"):
            intr = res["__interrupt__"][0]
            node = (getattr(intr, "value", {}) or {}).get("node")
            _runs[run_id].awaiting = node
            if node:
                await set_node_status(r, run_id, node, {"status": "awaiting-approval"})
            decision = await _runs[run_id].resume.get()          # "approved" / "rejected"
            _runs[run_id].awaiting = None
            res = await GRAPH.ainvoke(Command(resume=decision), cfg)
    except Exception as e:
        import traceback
        print(f"[run {run_id}] error: {e}")
        traceback.print_exc()
    finally:
        _runs[run_id].done = True
        try:
            await r.json().merge(f"dag:run:{run_id}", "$", {"_done": True})
        except Exception:
            pass


@app.post("/demo/run")
async def demo_run(req: Request):
    body = await req.json()
    run_id = _uuid.uuid4().hex
    _runs[run_id] = _Run()
    asyncio.create_task(_drive_run(run_id, bool(body.get("simulate_runaway", False))))
    return {"run_id": run_id}


@app.post("/demo/resume")
async def demo_resume(req: Request):
    body = await req.json()
    run = _runs.get(body.get("run_id", ""))
    if not run:
        return {"ok": False, "error": "unknown run"}
    await run.resume.put("approved" if body.get("approved") else "rejected")
    return {"ok": True}


@app.get("/events/dag/{run_id}")
async def dag_events(run_id: str) -> StreamingResponse:
    """Stream the live DAG document (RedisJSON) to the cockpit as it changes."""
    async def gen() -> AsyncIterator[str]:
        r = await get_redis()
        last = None
        for _ in range(1200):                                    # ~6 min cap @ 300ms
            doc = await read_dag(r, run_id)
            if doc:
                s = json.dumps(doc)
                if s != last:
                    last = s
                    yield f"data: {s}\n\n"
                if doc.get("_done"):
                    break
            await asyncio.sleep(0.3)
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


# --- Demo control + introspection endpoints ----------------------------------
@app.post("/demo/force-reset")
async def demo_force_reset(req: Request):
    body = await req.json()
    r = await get_redis()
    await force_reset(r, body.get("agent_id", "executor-update-lb"))
    return {"ok": True}


@app.get("/demo/dag/{run_id}")
async def demo_dag(run_id: str):
    """Inspect the live DAG document in RedisJSON (used by tests + as a UI fallback)."""
    r = await get_redis()
    return await read_dag(r, run_id) or {"error": "not found"}


@app.get("/healthz")
async def healthz():
    r = await get_redis()
    pong = await r.ping()
    return {"ok": True, "redis": pong, "agent": AGENT_NAME}
