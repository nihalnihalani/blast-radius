"""Hermetic test config:
- in-memory checkpointer per test (a test may opt into Redis)
- the Docker infra layer is stubbed with fast deterministic doubles so graph UNIT tests don't spin
  real containers. The REAL operations are exercised by test_docker_ops.py (integration).
"""
import os

import pytest

os.environ.setdefault("DEMO_STEP_DELAY", "0")
os.environ.setdefault("DEMO_BREAKER_HOLD", "0")
os.environ.setdefault("WEAVE_DISABLED", "1")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")


@pytest.fixture(autouse=True)
def _reset_checkpointer():
    os.environ["CHECKPOINTER"] = "memory"
    import checkpointer
    checkpointer._saver = None
    yield
    checkpointer._saver = None
    os.environ["CHECKPOINTER"] = "memory"


@pytest.fixture(autouse=True)
def _stub_infra(request, monkeypatch):
    """Stub docker_ops for graph tests. Skipped for the real integration test."""
    if request.node.get_closest_marker("realdocker"):
        return
    import docker_ops as infra
    fails = {"n": 0}
    monkeypatch.setattr(infra, "validate_iam", lambda: {"safe": True, "reason": "stub"})
    monkeypatch.setattr(infra, "check_deps", lambda: {"safe": True, "reason": "stub"})
    monkeypatch.setattr(infra, "scale_payments", lambda n: {"replicas": ["blast-pay-1"], "count": 1})
    monkeypatch.setattr(infra, "update_lb", lambda *a, **k: {"backends": ["blast-pay-1"], "port": 8090})
    monkeypatch.setattr(infra, "healthcheck", lambda *a, **k: {"ok": True, "served_by": "blast-pay-1", "status": 200})
    monkeypatch.setattr(infra, "start_runaway", lambda: fails.__setitem__("n", 0))
    monkeypatch.setattr(infra, "runaway_failures", lambda: fails.__setitem__("n", fails["n"] + 2) or fails["n"])
    monkeypatch.setattr(infra, "kill_runaway", lambda: {"killed": "blast-runaway"})
