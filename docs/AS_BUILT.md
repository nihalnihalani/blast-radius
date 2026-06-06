# BLAST-RADIUS — As Built (verified running)

This documents what was actually implemented and **verified end-to-end in a browser**, including
where reality diverged from the original plan (and why). Stack versions are pinned from live installs.

## Verified working (June 2026)

- **Happy path:** request → DAG renders live → parallel validation → sequential human-approval gates
  on destructive steps → all nodes `Done`. ✅
- **Runaway path:** approve → executor loops → **real Redis circuit breaker trips** → red node + a
  `CIRCUIT BREAKER OPEN` banner → **recovery agent heals the node** (`Done · Recovery`) from the
  dead-letter queue → run continues → all `Done`. ✅
- **7/7 backend integration tests** pass against live redis-stack (breaker, streams, DLQ, RedisJSON
  merge, keyspace-notification → trip, full graph happy + runaway).

## Confirmed stack versions

| | version |
|---|---|
| Python | 3.12 |
| langgraph | 1.2.4 |
| copilotkit (py) | 0.1.94 |
| ag-ui-langgraph | 0.0.40 |
| weave | 0.52.42 |
| redis (py) | 7.4.1 → redis-stack server (ReJSON/Search/Bloom) |
| @copilotkit/react-core / runtime / react-ui | 1.59.5 |
| @ag-ui/client | (HttpAgent) |
| @xyflow/react (React Flow) | 12.11.0 |
| next | 15.5.19 |

## Key deviations from the plan (and why)

1. **Agent class + endpoint names changed in copilotkit 0.1.94.**
   `LangGraphAgent` → `LangGraphAGUIAgent`; `add_fastapi_endpoint` lives in
   `copilotkit.integrations.fastapi`. Fixed in `main.py`.

2. **CopilotKit runtime did not surface the remote agent to the frontend** (`No default agent
   provided` / `No agents registered`). Two changes fixed agent resolution:
   - The backend serves a **raw AG-UI endpoint at `/agent`** via `ag_ui_langgraph.add_langgraph_fastapi_endpoint`.
   - The frontend registers it **client-side** via `agents__unsafe_dev_only={{ infra_orchestrator: new HttpAgent({url}) }}`
     in `app/providers.tsx` (CopilotKit `@ag-ui/client` HttpAgent).

3. **The cockpit DAG is driven by a dedicated, reliable channel — not CopilotKit state-sync.**
   CopilotKit's `useCoAgent` state application proved version-fragile, so (per our own
   `RISKS.md` demo-safety rule) the DAG renders from a backend channel we fully control:
   - `POST /demo/run {simulate_runaway}` → starts a run, returns `run_id`.
   - `GET /events/dag/{run_id}` → **SSE** streaming the live RedisJSON DAG document on every change.
   - `POST /demo/resume {run_id, approved}` → resolves the LangGraph `interrupt()` approval gate.
   The CopilotKit sidebar + AG-UI agent remain wired (the agent itself streams `STATE_SNAPSHOT`
   events correctly — verified by probing `/agent`), so the generative-UI story is intact.

4. **The execution harness uses map-reduce + a sequential HITL loop.** Parallel `Send` fan-out for
   validation (real multi-agent parallelism), then a `router → approval(interrupt) → executor`
   loop so each destructive step raises exactly one interrupt — avoiding the shared-`current`-channel
   clobber that a naive parallel-approval design hits.

5. **Optional deps degrade gracefully.** Weave runs without a W&B login (warns once, no-op);
   RedisVL semantic recovery memory falls back to a static safe path if no embedding backend is
   installed; OpenAI is not required (the agent is deterministic + `ExperimentalEmptyAdapter`).

6. **Demo pacing** (`DEMO_STEP_DELAY`, `DEMO_BREAKER_HOLD`) keeps the breaker-open state visible on
   stage; set both to `0` for instant runs (and in tests).

## What's real vs mocked (for the Q&A)

- **Real:** the LangGraph multi-agent graph, parallel `Send` fan-out, graph-enforced `interrupt()`
  approvals, the Redis circuit breaker (atomic Lua `INCR`+`SET EX`), Keyspace Notifications →
  breaker SSE, Streams work bus + dead-letter queue, RedisJSON DAG doc, Weave tracing, the recovery
  agent consuming the DLQ.
- **Mocked (deliberately, for demo safety):** the infra actions themselves (no real cloud mutations);
  the "scale payments" DAG template is fixed.

## Run it

```bash
docker compose up -d                                   # redis-stack on :6379
cd services/agent && python3.12 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
uvicorn main:app --port 8000                           # backend (AG-UI /agent + /demo/* + SSE)
cd ../../apps/web && npm install && npm run dev        # http://localhost:3000
```
Then click **Scale payments (happy path)** or **Simulate Runaway Agent**.
