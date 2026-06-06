# BLAST-RADIUS — Architecture

> Hardened against the devil's-advocate review. Every API named here was verified by the research phase (June 2026).

## Three planes

```
╔══ CONTROL UI (the cockpit) ═══════════════════════════════╗
║ Next.js + CopilotKit                                       ║
║  • Live blast-radius DAG (React Flow)  ← agent.state.dag    ║
║  • Per-node status cards               ← useCoAgentStateRender║
║  • Approval gate modal                 ← useInterrupt (v2)   ║
║  • Red-pulse breaker animation         ← agent.subscribe()  ║
║  • Sidebar chat + suggestion chips     ← CopilotSidebar     ║
╚══════════════════════↑ AG-UI event stream (HTTP) ↑══════╝
                          STATE_DELTA / CUSTOM / STEP_*
╔══ ORCHESTRATION PLANE ═══════════════════════════════╗
║ Python FastAPI + CopilotKitRemoteEndpoint + LangGraphAgent  ║
║  StateGraph(BlastRadiusState extends CopilotKitState)       ║
║   orchestrator ─(Send fan-out)→ validator* → [interrupt] →   ║
║                                 executor*  → recover        ║
║  every node = @weave.op  ·  emits ag_ui CustomEvent         ║
╚══════════════════↑↓══════════════════════════╝
╔══ STATE + COORDINATION PLANE (Redis, beyond cache) ══════╗
║ • RedisJSON   dag:run:{id}         (the DAG document)        ║
║ • Streams     agents:tasks (+ DLQ) (work bus, consumer grp) ║
║ • Breaker     cb:{agent}:failures (INCR+EXPIRE), cb:{a}:open║
║ • Keyspace    __keyevent@0__:set  → pubsub → CustomEvent     ║
║ • RedisVL     recovery_context     (semantic recovery memory)║
╚═════════════════════════════════════════════╝
                       ↑ Weave traces every op + tags breaker_state
```

## Request lifecycle (happy path)

1. Operator types/clicks an infra request in `CopilotSidebar`.
2. `infra_orchestrator` LangGraph run starts. The **orchestrator node** decomposes the request into DAG steps and writes `dag:run:{id}` to RedisJSON. State (extending `CopilotKitState`) auto-streams a `STATE_SNAPSHOT` → the DAG paints.
3. A conditional edge returns a list of `Send("validator", step_state)` → **parallel fan-out** validates each step. Node status changes → `JSON.MERGE` on `$.nodes.{id}` → `STATE_DELTA` → node turns yellow then green.
4. Before any **destructive** executor node, the graph calls `interrupt({node, plan})`. `useInterrupt` renders the **approval modal**. Operator approves → `Command(resume={approved:true})` → executor runs.
5. Executors push work to the `agents:tasks` Stream; consumer-group workers `XREADGROUP` → do the (mock) change → `XACK`. On completion the run finishes; Weave shows the full trace tree.

## Runaway lifecycle (the jaw-drop)

1. Operator clicks **Simulate Runaway Agent** (`useFrontendTool` → sets a flag in state).
2. The executor loops; each failure: `INCR cb:{agent}:failures` (with `EXPIRE` on first incr, atomic via Lua/pipeline). **We trip at count ≥ 5 — deliberately below LangGraph's `recursion_limit=25`** so we animate the breaker *before* a `GraphRecursionError`.
3. On trip: `SET cb:{agent}:open 1 EX 10`. This write fires a Redis **Keyspace Notification** on `__keyevent@0__:set`.
4. A **pubsub listener task** (subscribed at startup) receives it and pushes onto an `asyncio.Queue`. The orchestrator's event loop drains the queue at the next step boundary and `yield`s an `ag_ui.core.CustomEvent(name="CIRCUIT_BREAKER_TRIPPED", value={node_id, agent_id, failure_count})`.
5. Frontend `agent.subscribe({ onCustomEvent })` fires `triggerRedPulse(node_id)` → the DAG node pulses red, the agent is killed (`abortRun`/graph short-circuit), Weave logs the trip op with `breaker_state="OPEN"`.
6. Operator clicks **Resume with safe fallback** → a **recovery agent** consumes the pre-seeded DLQ message (`XAUTOCLAIM` / `XREADGROUP` on the DLQ stream), pulls similar past-failure context from **RedisVL** `SemanticMessageHistory`, and completes the step on a safe path. When `cb:{agent}:open` expires after the TTL, `__keyevent@0__:expired` fires the "breaker reset" event for free.

## Why a single LLM call cannot do this (harness sophistication)

- **True parallelism** across DAG steps (LangGraph `Send()` superstep), not sequential prompting.
- **External, durable kill switch**: the breaker lives in Redis and trips even if the agent process is wedged — a `setTimeout` in the agent cannot.
- **Cross-process control plane**: a Keyspace Notification injected from outside the run drives UI + control flow.
- **Durable recovery**: a dead-letter queue + semantic memory survive the failure and re-enter the graph.

## Tech stack

- **Frontend:** Next.js (App Router), `@copilotkit/react-core@1.59.5` (+ `/v2`), `@copilotkit/react-ui`, `@copilotkit/runtime`, **React Flow** for the DAG, Tailwind.
- **Backend:** Python 3.12, FastAPI, `langgraph` (verify `Send` import path), `copilotkit` + `ag-ui-langgraph@0.0.40`, `redis` (redis-py 8.x), `redisvl@0.20.0`, `weave@0.52.x`, `openai`.
- **Infra:** Redis Cloud (coupon `WEAVEHACKS_4`, **paid Essentials/Pro tier — the free tier's 30-connection cap is insufficient under demo load**) or local `redis-stack` Docker (includes RedisJSON + Search).
