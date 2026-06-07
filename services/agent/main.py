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
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from config import AGENT_NAME, ALLOWED_ORIGINS
from logging_setup import configure_logging, get_logger
from weave_setup import init_weave
from checkpointer import setup_checkpointer
from llm import llm_enabled
from redis_client import get_redis, close_redis
from breaker import keyspace_listener, force_reset
from streams import ensure_group, seed_dlq
from dag import read_dag
from graph import build_graph

configure_logging()
log = get_logger("blast.main")

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
    await setup_checkpointer()
    r = await get_redis()
    await ensure_group(r)
    # Pre-seed one DLQ message so 'Resume with safe fallback' is instant during the demo.
    await seed_dlq(r, {"node_id": "update-lb", "action": "scale", "note": "pre-seeded"})
    _bg_tasks.append(asyncio.create_task(keyspace_listener(r, _trip_queue)))
    _bg_tasks.append(asyncio.create_task(_fan_out_trips()))
    log.info("startup complete (agent=%s, openai=%s)", AGENT_NAME, llm_enabled())
    yield
    for t in _bg_tasks:
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t
    await close_redis()
    log.info("shutdown complete")


app = FastAPI(title="BLAST-RADIUS agent", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"error": "internal_error", "detail": str(exc)})

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
    log.info("AG-UI agent '%s' mounted at /agent", AGENT_NAME)
except Exception as e:
    log.exception("AG-UI endpoint NOT mounted: %s", e)

# --- CopilotKit remote endpoint (kept for compatibility / Best-CopilotKit story) ----
try:
    from copilotkit import CopilotKitRemoteEndpoint, LangGraphAGUIAgent
    from copilotkit.integrations.fastapi import add_fastapi_endpoint

    sdk = CopilotKitRemoteEndpoint(
        agents=[LangGraphAGUIAgent(name=AGENT_NAME, description=_DESC, graph=GRAPH)],
    )
    add_fastapi_endpoint(app, sdk, "/copilotkit")
    log.info("CopilotKit agent '%s' mounted at /copilotkit", AGENT_NAME)
except Exception as e:
    log.warning("CopilotKit endpoint NOT mounted: %s", e)


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


# NOTE: The cockpit is driven entirely over the AG-UI protocol (the /agent endpoint above,
# consumed by @ag-ui/client in the frontend) — there is no bespoke DAG/SSE channel. The only
# remaining SSE here is the Redis keyspace control plane (/events/breaker), which is a Redis
# feature demo, independent of the agent run.


# --- Control + introspection endpoints ----------------------------------------
class ForceResetBody(BaseModel):
    agent_id: str = "executor-update-lb"


@app.post("/demo/force-reset")
async def demo_force_reset(body: ForceResetBody):
    r = await get_redis()
    await force_reset(r, body.agent_id)
    return {"ok": True, "agent_id": body.agent_id}


@app.get("/demo/dag/{run_id}")
async def demo_dag(run_id: str):
    """Inspect the live DAG document in RedisJSON (introspection / tests)."""
    r = await get_redis()
    return await read_dag(r, run_id) or {"error": "not found"}


@app.get("/healthz")
async def healthz():
    """Liveness — is the process up."""
    return {"ok": True, "agent": AGENT_NAME, "openai": llm_enabled()}


@app.get("/readyz")
async def readyz():
    """Readiness — can we actually serve (Redis reachable)."""
    try:
        r = await get_redis()
        pong = await r.ping()
        return {"ready": bool(pong), "redis": pong}
    except Exception as e:
        return JSONResponse(status_code=503, content={"ready": False, "error": str(e)})
