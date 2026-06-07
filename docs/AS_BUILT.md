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

2. **The cockpit is driven entirely over the AG-UI protocol (no bespoke SSE).** The backend
   serves the LangGraph agent as a raw AG-UI endpoint at `/agent` (`ag_ui_langgraph`), and the
   browser consumes it directly with CopilotKit's **`@ag-ui/client` `HttpAgent`**
   (`apps/web/lib/useBlastAgent.ts`):
   - `STATE_SNAPSHOT` / `STATE_DELTA` events → the live DAG (`agent.state.dag_nodes`).
   - the `on_interrupt` **CUSTOM event** (value `{node, plan}` arrives as a JSON string — parse it)
     → the human-approval gate.
   - resume = `agent.runAgent({ forwardedProps: { command: { resume: "approved" } } })` on the
     **same `threadId`**, continuing the LangGraph checkpoint to the next interrupt.

   Why not CopilotKit's `useCoAgent` runtime path: in this exact version combo (JS `@copilotkit/*`
   1.59.5 + Python `copilotkit` 0.1.94) the runtime's agent discovery reported "No agents
   registered" / "No default agent", so `useCoAgent().run()` never reached the agent. The
   `@ag-ui/client` `HttpAgent` **is** CopilotKit's own AG-UI protocol library and works directly
   (verified standalone in Node: 12 snapshots, `on_interrupt`, `RUN_FINISHED`). **Browser gotcha:**
   pass the subscriber to `runAgent(params, subscriber)` — persistent `agent.subscribe()`
   subscribers do **not** receive run events.

4. **The execution harness uses map-reduce + a sequential HITL loop.** Parallel `Send` fan-out for
   validation (real multi-agent parallelism), then a `router → approval(interrupt) → executor`
   loop so each destructive step raises exactly one interrupt — avoiding the shared-`current`-channel
   clobber that a naive parallel-approval design hits.

5. **Optional deps degrade gracefully.** Weave runs without a W&B login (warns once, no-op);
   RedisVL semantic recovery memory falls back to a static safe path if no embedding backend is
   installed; OpenAI is not required (the agent is deterministic + `ExperimentalEmptyAdapter`).

6. **Demo pacing** (`DEMO_STEP_DELAY`, `DEMO_BREAKER_HOLD`) keeps the breaker-open state visible on
   stage; set both to `0` for instant runs (and in tests).

## What's real (no mock)

Everything executes for real against live Docker (`services/agent/docker_ops.py`):
- **`scale-payments`** → `docker run`/remove real `traefik/whoami` replicas (`blast-pay-N`).
- **`update-lb`** → rewrite the real nginx upstream + `nginx -s reload` on the real `blast-lb`.
- **`healthcheck`** → real HTTP GET through the LB (returns the live backend hostname).
- **runaway** → a real crash-looping container; the **breaker counts its real Docker restart
  failures** and `docker kill`s it (the kill-switch); recovery applies a known-good LB config.

Plus the rest of the harness: LangGraph multi-agent graph, parallel `Send` fan-out, graph-enforced
`interrupt()` gates, the Redis circuit breaker (atomic Lua `INCR`+`SET EX`), Keyspace Notifications,
Streams + DLQ, RedisJSON DAG doc, durable Redis checkpointer, Weave tracing.

**Safety:** every Docker op is scoped to containers labelled `blast.managed=true` with the
`blast-` name prefix on the dedicated `blast-net` network — it never touches anything else, and
replica count is hard-capped (`MAX_REPLICAS`). The managed target is a self-contained sample
stack, not your production cloud.

## Run it

```bash
docker compose up -d                                   # redis-stack on :6379
cd services/agent && python3.12 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
uvicorn main:app --port 8000                           # backend (AG-UI /agent + /demo/* + SSE)
cd ../../apps/web && npm install && npm run dev        # http://localhost:3000
```
Then click **Scale payments (happy path)** or **Simulate Runaway Agent**.
