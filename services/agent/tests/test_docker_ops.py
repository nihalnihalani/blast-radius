"""Real Docker integration test — proves the agent operates REAL containers (no mocks).
Skips automatically if Docker is unavailable."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import docker_ops as infra  # noqa: E402

pytestmark = pytest.mark.realdocker

try:
    infra.client().ping()
    HAS_DOCKER = True
except Exception:
    HAS_DOCKER = False


@pytest.mark.skipif(not HAS_DOCKER, reason="Docker not available")
def test_real_scale_lb_healthcheck_runaway_kill():
    infra.cleanup()
    assert infra.check_deps()["safe"]
    assert infra.scale_payments(2)["count"] == 2
    infra.update_lb()
    health = infra.healthcheck()
    assert health["ok"] and health["status"] == 200          # real HTTP through the real LB
    infra.start_runaway()
    import time
    for _ in range(8):
        time.sleep(0.5)
        if infra.runaway_failures() >= 2:
            break
    assert infra.runaway_failures() >= 1                     # real container really crash-looped
    assert infra.kill_runaway()["killed"] == "blast-runaway"  # real docker kill
    infra.cleanup()
