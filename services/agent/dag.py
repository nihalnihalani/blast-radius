"""The blast-radius DAG document, stored in RedisJSON (state, not cache).

Keep arrays (edges) on the root; never JSON.MERGE a path containing an array you want to
preserve element-wise -- MERGE replaces whole arrays. Per-node status is a leaf object.
"""
import redis.asyncio as redis


def sample_dag(run_id: str, request: str) -> dict:
    """The single demo template: 'Scale the payments service'.

    node statuses: pending | running | done | failed | blocked
    destructive nodes require a human approval gate before executing.
    """
    return {
        "run_id": run_id,
        "request": request,
        "breaker_open": False,
        "tripped_node": None,
        "nodes": {
            "validate-iam":    {"label": "Validate IAM",        "status": "pending", "agent": None, "destructive": False},
            "check-deps":      {"label": "Check dependencies",  "status": "pending", "agent": None, "destructive": False},
            "scale-payments":  {"label": "Scale payments svc",  "status": "pending", "agent": None, "destructive": True},
            "update-lb":       {"label": "Update load balancer","status": "pending", "agent": None, "destructive": True},
            "healthcheck":     {"label": "Health check",        "status": "pending", "agent": None, "destructive": False},
        },
        "edges": [
            ["validate-iam", "check-deps"],
            ["check-deps", "scale-payments"],
            ["scale-payments", "update-lb"],
            ["update-lb", "healthcheck"],
        ],
    }


def _key(run_id: str) -> str:
    return f"dag:run:{run_id}"


async def write_dag(r: redis.Redis, run_id: str, dag: dict) -> None:
    await r.json().set(_key(run_id), "$", dag)


async def set_node_status(r: redis.Redis, run_id: str, node_id: str, patch: dict) -> None:
    """RFC-7396 merge on a single node -> other keys preserved, tiny STATE_DELTA."""
    await r.json().merge(_key(run_id), f"$.nodes.{node_id}", patch)


async def set_breaker(r: redis.Redis, run_id: str, open_: bool, node_id: str | None) -> None:
    await r.json().merge(_key(run_id), "$", {"breaker_open": open_, "tripped_node": node_id})


async def read_dag(r: redis.Redis, run_id: str) -> dict | None:
    return await r.json().get(_key(run_id))
