"""Drives the LangGraph harness end-to-end against live Redis.

Verifies: orchestrator -> parallel validate -> approval(interrupt) -> executor -> (recover).
- happy path: every node reaches 'done'
- runaway path: the breaker trips on update-lb, then the recover node heals it
"""
import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langgraph.types import Command  # noqa: E402
import graph as g  # noqa: E402
import dag as dagmod  # noqa: E402
import redis.asyncio as redis  # noqa: E402

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


async def _drive(compiled, init_state, run_id, approve=True, max_steps=20):
    """Run the graph, auto-approving every interrupt, until it finishes. Returns final state."""
    cfg = {"configurable": {"thread_id": run_id}, "recursion_limit": 60}
    result = await compiled.ainvoke(init_state, cfg)
    steps = 0
    while "__interrupt__" in result and steps < max_steps:
        result = await compiled.ainvoke(Command(resume={"approved": approve}), cfg)
        steps += 1
    return result


@pytest.mark.asyncio
async def test_happy_path_all_nodes_done():
    compiled = g.build_graph()
    run_id = uuid.uuid4().hex
    await _drive(compiled, {"run_id": run_id, "request": "Scale the payments service",
                            "simulate_runaway": False}, run_id)
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        doc = await dagmod.read_dag(r, run_id)
        statuses = {nid: n["status"] for nid, n in doc["nodes"].items()}
        assert all(s == "done" for s in statuses.values()), statuses
        assert doc["breaker_open"] is False
    finally:
        await r.aclose()


@pytest.mark.asyncio
async def test_runaway_trips_breaker_then_recovers():
    compiled = g.build_graph()
    run_id = uuid.uuid4().hex
    final = await _drive(compiled, {"run_id": run_id, "request": "Scale the payments service",
                                    "simulate_runaway": True}, run_id)
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        doc = await dagmod.read_dag(r, run_id)
        # update-lb went runaway, breaker tripped, recover node healed it back to done.
        assert doc["nodes"]["update-lb"]["status"] == "done", doc["nodes"]["update-lb"]
        assert doc["nodes"]["update-lb"]["agent"] == "recovery"  # healed by the recovery agent
        assert doc["breaker_open"] is False                      # recover reset it
        assert doc["nodes"]["healthcheck"]["status"] == "done"   # run continued past the failure
        assert final["completed"] == ["validate-iam", "check-deps", "scale-payments", "healthcheck"]
    finally:
        await r.aclose()
