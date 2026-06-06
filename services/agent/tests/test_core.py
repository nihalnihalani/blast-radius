"""Integration tests for the Redis 'beyond cache' core against a live redis-stack.

Run:  cd services/agent && . .venv/bin/activate && python -m pytest tests -q
(requires a running redis-stack on REDIS_URL)

Each test uses its own redis client bound to that test's event loop (pytest-anyio runs each
async test in a fresh loop), so we don't share the app's module-global client here.
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
import redis.asyncio as redis

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import breaker  # noqa: E402
import streams  # noqa: E402
import dag  # noqa: E402

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


@pytest_asyncio.fixture
async def r():
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    await client.config_set("notify-keyspace-events", "KE$x")
    try:
        yield client
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_breaker_trips_at_threshold(r):
    agent = f"test-{uuid.uuid4().hex[:6]}"
    counts = [await breaker.record_failure(r, agent) for _ in range(breaker.BREAKER_THRESHOLD)]
    assert counts == list(range(1, breaker.BREAKER_THRESHOLD + 1))
    assert await breaker.is_open(r, agent) is True
    await breaker.force_reset(r, agent)
    assert await breaker.is_open(r, agent) is False


@pytest.mark.asyncio
async def test_streams_enqueue_consume_ack(r):
    await streams.ensure_group(r)
    mid = await streams.enqueue(r, {"node_id": "x", "action": "scale"})
    assert mid
    msgs = await streams.claim_new(r, "test-consumer", count=10, block_ms=500)
    flat = [m for _, entries in (msgs or []) for m in entries]
    assert any(m_id == mid for m_id, _ in flat)
    assert await streams.ack(r, mid) == 1


@pytest.mark.asyncio
async def test_dlq_seed_and_drain(r):
    await streams.seed_dlq(r, {"node_id": "update-lb", "note": "test"})
    item = await streams.drain_dlq_one(r)
    assert item and item.get("node_id") == "update-lb"


@pytest.mark.asyncio
async def test_redisjson_dag_merge_preserves_other_keys(r):
    run_id = uuid.uuid4().hex
    await dag.write_dag(r, run_id, dag.sample_dag(run_id, "Scale the payments service"))
    await dag.set_node_status(r, run_id, "scale-payments", {"status": "running", "agent": "executor-1"})
    doc = await dag.read_dag(r, run_id)
    node = doc["nodes"]["scale-payments"]
    assert node["status"] == "running"
    assert node["label"] == "Scale payments svc"      # MERGE preserved the label
    assert node["destructive"] is True
    assert doc["nodes"]["validate-iam"]["status"] == "pending"  # untouched node intact


@pytest.mark.asyncio
async def test_keyspace_notification_fires_on_breaker_open(r):
    agent = f"ks-{uuid.uuid4().hex[:6]}"
    q: asyncio.Queue = asyncio.Queue()
    listener = asyncio.create_task(breaker.keyspace_listener(r, q))
    await asyncio.sleep(0.3)  # let the pubsub subscribe
    for _ in range(breaker.BREAKER_THRESHOLD):
        await breaker.record_failure(r, agent)
    kind, got_agent = await asyncio.wait_for(q.get(), timeout=3)
    assert kind == "TRIPPED" and got_agent == agent
    listener.cancel()
    import contextlib
    with contextlib.suppress(asyncio.CancelledError):
        await listener
    await breaker.force_reset(r, agent)
