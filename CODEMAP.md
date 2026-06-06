# Code map (scaffold)

> Starter skeleton committed. It compiles against the versions in `apps/web/package.json` /
> `services/agent/requirements.txt`, but **is not yet run-verified** — see the on-site checks in
> `docs/SETUP.md` and `docs/RISKS.md` (#1, #4, #5 especially). Build order: `docs/BUILD_TIMELINE.md`.

## Backend — `services/agent/`
| File | What it owns |
|---|---|
| `main.py` | FastAPI app, mounts the LangGraph agent on the CopilotKit runtime, starts Weave + the Redis keyspace listener, demo endpoints (`/demo/force-reset`). |
| `graph.py` | **The harness.** `BlastRadiusState` (extends `CopilotKitState`, reducer-merged `dag_nodes`), nodes: orchestrator → `Send` fan-out → validator → approval(`interrupt`) → executor → recover. Streams node status to the UI as STATE_DELTA. |
| `breaker.py` | Real circuit breaker (atomic Lua INCR+EXPIRE+SET EX), `is_open`, `force_reset`, and the keyspace-notification listener → `asyncio.Queue`. |
| `streams.py` | Redis Streams work bus + dead-letter queue (consumer group, `xautoclaim` reaping, DLQ seed/drain). |
| `dag.py` | RedisJSON DAG document (the `scale-payments` template) + per-node `JSON.MERGE`. |
| `recovery.py` | Recovery agent: drain DLQ + RedisVL semantic recall (graceful fallback if `redisvl` absent). |
| `events.py` | AG-UI `CIRCUIT_BREAKER_TRIPPED` custom event (secondary; state is the primary UI signal). |
| `weave_setup.py` | `weave.init` + `weave.attributes(breaker_state=...)` helper. |
| `config.py` | Env-driven tuning (breaker threshold/TTL, recursion limit). |

## Frontend — `apps/web/`
| File | What it owns |
|---|---|
| `app/layout.tsx` | `<CopilotKit>` provider bound to the agent. |
| `app/page.tsx` | The cockpit: header + `Controls` + `BlastRadiusDAG` + `ApprovalGate` + `CopilotSidebar`. |
| `app/api/copilotkit/route.ts` | CopilotRuntime + OpenAIAdapter + remote LangGraph endpoint proxy. |
| `components/BlastRadiusDAG.tsx` | **The live DAG** (React Flow) driven by `useCoAgent` shared state. |
| `components/DagNode.tsx` | Custom node + the red-pulse class when tripped. |
| `components/ApprovalGate.tsx` | `useLangGraphInterrupt` approval modal (v2: `useInterrupt`). |
| `components/Controls.tsx` | Demo buttons: happy path / simulate runaway / force reset. |
| `lib/types.ts` | DAG/state types + status colors. |
| `app/globals.css` | Cockpit styling + the `@keyframes pulseRed` animation. |

## First-run order
1. `make redis` 2. `make setup` 3. fill `.env` files (see `docs/SETUP.md`) 4. `make backend` 5. `make web` → http://localhost:3000

## The 4 things that must work (never cut — see docs/RISKS.md)
Live DAG · approval gate · breaker-trip red pulse · Weave tracing.
