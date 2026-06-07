"""Hermetic test config: in-memory checkpointer per test, no demo pacing, Weave off."""
import os

import pytest

os.environ.setdefault("DEMO_STEP_DELAY", "0")
os.environ.setdefault("DEMO_BREAKER_HOLD", "0")
os.environ.setdefault("WEAVE_DISABLED", "1")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")


@pytest.fixture(autouse=True)
def _reset_checkpointer():
    """Default every test to a fresh in-memory checkpointer (a test may opt into Redis itself)."""
    os.environ["CHECKPOINTER"] = "memory"
    import checkpointer
    checkpointer._saver = None
    yield
    checkpointer._saver = None
    os.environ["CHECKPOINTER"] = "memory"
