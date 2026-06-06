# Weave instrumentation (required + Best Weave)

> `weave==0.52.x` (latest 0.52.42, June 2026). Deep, not 2-line. Verified APIs only.

## Layer 1 — trace every agent op

```python
import weave
weave.init("blast-radius")          # at FastAPI startup

@weave.op
async def orchestrator_plan(request: str) -> dict: ...
@weave.op
async def validator_check(node: dict) -> dict: ...
@weave.op
async def executor_run(node: dict) -> dict: ...
@weave.op
async def circuit_breaker_trip(agent_id: str, count: int) -> dict: ...
```
**Gotcha (verified):** LangGraph has **no native Weave adapter** — Weave auto-traces LangChain *Runnables*, not `StateGraph` nodes. So we **wrap each node function with `@weave.op` manually** (chosen approach) or use the OTel OTLP endpoint. Manual `@weave.op` is the reliable path for a hackathon.

## Layer 2 — `weave.attributes()` as the breaker-state carrier (the deep, underused feature)

```python
with weave.attributes({"agent_id": agent_id, "node_id": node_id,
                       "breaker_state": state, "dag_step": step, "run_id": run_id}):
    result = await executor_run(node)
```
Every span is now filterable by `breaker_state` (`CLOSED|OPEN|HALF_OPEN`) in the Weave UI — this is the **evidence layer** that makes the reliability story real to Nina Olding & Sam Stowers. Few teams use `weave.attributes()`; it reads as expertise.

## Layer 3 — thread grouping per run

```python
with weave.thread(thread_id=run_id):     # never pass None (silently disables grouping)
    await run_dag(...)
```
Groups all agent ops for one infra-change run into one coherent session in the Weave trace view.

## Layer 4 — LLM-judge scorer for runaway detection

```python
from weave.scorers import HallucinationFreeScorer   # litellm-backed, model_id='openai/gpt-4o'
# or a custom weave.Scorer that flags loop/over-action behavior on the trace
```
Attach post-hoc with the two-value call pattern:
```python
result, call = executor_run.call(node)
call.feedback.add("breaker", {"state": "OPEN", "count": 5, "key": key, "ttl": 10})  # ≤ 1KB payload!
```

## Layer 5 — Online Monitor (configured in the W&B UI, not code)

**Gotcha (verified):** there is **no** `weave.create_monitor()`. The Online Monitor is set up by clicking **Add Monitor** in the Weave web UI (pick op + scorer + sample rate). **Budget 15 min in setup** to configure it; the Python side is only the scorer class. Present built-in Signals ("code failures", etc.) as **heuristic signals surfaced for human review**, not ground-truth detectors.

## What the judges see

- A trace tree of the whole multi-agent run (orchestrator → validators → executors → recovery).
- Spans tagged `breaker_state=OPEN` at the exact moment of the trip.
- `redis_op` attributes showing the exact Redis call chain (`xadd`, `incr`, `set`…) inside each op.
- An Online Monitor view with the runaway-detection signal firing.

## W&B MCP server (optional flex)

Connect coding agents to `https://mcp.withwandb.com/mcp` to query traces during the build ("show me the slowest executor op"). Mention in the submission as deep Weave integration.
