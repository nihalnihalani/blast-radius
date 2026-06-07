"""Durability: the Redis checkpointer persists a paused (interrupted) run across separate
compiled graphs — proving in-flight state survives a process restart."""
import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.mark.asyncio
async def test_redis_checkpointer_persists_interrupt():
    os.environ["CHECKPOINTER"] = "redis"
    import checkpointer
    checkpointer._saver = None
    await checkpointer.setup_checkpointer()

    import graph as g
    from langgraph.types import Command

    run_id = uuid.uuid4().hex
    cfg = {"configurable": {"thread_id": run_id}, "recursion_limit": 60}

    compiled_a = g.build_graph()
    res = await compiled_a.ainvoke(
        {"run_id": run_id, "request": "Scale the payments service", "simulate_runaway": False}, cfg)
    assert "__interrupt__" in res                      # paused at the first destructive-step gate

    # a brand-new compiled graph sharing the Redis checkpoint store resumes the persisted thread
    compiled_b = g.build_graph()
    res2 = await compiled_b.ainvoke(Command(resume="approved"), cfg)
    assert isinstance(res2, dict)
