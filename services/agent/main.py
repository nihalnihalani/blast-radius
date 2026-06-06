"""FastAPI entrypoint: exposes the LangGraph agent to the CopilotKit runtime, starts Weave,
and runs the Redis keyspace listener as a background task.

Run:  uvicorn main:app --reload --port 8000

Verify the CopilotKit FastAPI import path on-site -- it has moved between SDK versions:
  from copilotkit.fastapi import add_fastapi_endpoint        # common
  from copilotkit.integrations.fastapi import add_fastapi_endpoint  # alt
"""
import asyncio
import contextlib

from fastapi import FastAPI, Request

from config import AGENT_NAME
from weave_setup import init_weave
from redis_client import get_redis, close_redis
from breaker import keyspace_listener, force_reset
from streams import ensure_group, seed_dlq
from graph import build_graph

init_weave()
app = FastAPI(title="BLAST-RADIUS agent")

_trip_queue: "asyncio.Queue[tuple[str, str]]" = asyncio.Queue()
_bg_tasks: list[asyncio.Task] = []


@app.on_event("startup")
async def _startup():
    r = await get_redis()
    await ensure_group(r)
    # Pre-seed one DLQ message so 'Resume with safe fallback' is instant during the demo.
    await seed_dlq(r, {"node_id": "update-lb", "action": "scale", "note": "pre-seeded"})
    _bg_tasks.append(asyncio.create_task(keyspace_listener(r, _trip_queue)))


@app.on_event("shutdown")
async def _shutdown():
    for t in _bg_tasks:
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t
    await close_redis()


# --- CopilotKit endpoint -----------------------------------------------------
# Connect the compiled LangGraph graph to the CopilotKit runtime over AG-UI.
try:
    from copilotkit import CopilotKitRemoteEndpoint, LangGraphAgent
    try:
        from copilotkit.fastapi import add_fastapi_endpoint
    except Exception:
        from copilotkit.integrations.fastapi import add_fastapi_endpoint  # type: ignore

    sdk = CopilotKitRemoteEndpoint(
        agents=[LangGraphAgent(
            name=AGENT_NAME,
            description="Decomposes an infra change into a blast-radius DAG and executes it under a circuit breaker.",
            graph=build_graph(),
        )],
    )
    add_fastapi_endpoint(app, sdk, "/copilotkit")
except Exception as e:  # keep the app importable even before deps are installed
    print(f"[main] CopilotKit endpoint not mounted yet: {e}")


# --- Demo control endpoints (called by useFrontendTool handlers / buttons) ----
@app.post("/demo/force-reset")
async def demo_force_reset(req: Request):
    body = await req.json()
    r = await get_redis()
    await force_reset(r, body.get("agent_id", "executor-update-lb"))
    return {"ok": True}


@app.get("/healthz")
async def healthz():
    return {"ok": True}
