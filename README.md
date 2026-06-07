# 💥 BLAST-RADIUS

> **The multi-agent infra-change cockpit.** You ask an agent team to make an infrastructure change. It decomposes the request into a live **blast-radius DAG**, fans specialist agents out across it, gates every destructive step behind a human approval — and a **real Redis circuit breaker** kills any agent that goes runaway, visualized as a red pulse racing across the graph.

Built at **WeaveHacks 4** (June 2026). Powered by **W&B Weave · CopilotKit / AG-UI · Redis · OpenAI Agents SDK + LangGraph**.

---

## The 30-second pitch

Agents that take *destructive* actions — infra changes, deployments, credential rotations, migrations — have no **blast-radius preview** and no automated **kill switch**. When an agent loops or goes rogue mid-execution, nothing stands between it and production. The trending failure mode of 2026 is *"multi-agent demos that stall, loop on tool calls, and blow latency budgets."*

**BLAST-RADIUS** is the cockpit that fixes it:

1. **Decompose** — an Orchestrator agent turns a natural-language infra request into a dependency **DAG** of steps.
2. **Visualize** — the DAG renders **live in the browser**, every node streaming its status (`pending → running → done / failed / blocked`).
3. **Fan out** — Validator + Executor specialist agents run across the DAG in parallel (LangGraph `Send()`).
4. **Gate** — every destructive node pauses for a **human-in-the-loop approval** before it touches anything (graph-enforced LangGraph `interrupt()`).
5. **Protect** — a **real Redis circuit breaker** trips when an agent loops or fails repeatedly, killing it instantly and spawning a recovery agent from a dead-letter queue.

## The jaw-drop demo moment

> Click **"Simulate Runaway Agent."** The agent loops → Redis `INCR` crosses a threshold in ~3s → `SET … EX` opens the breaker key → a **Keyspace Notification** fires a `CIRCUIT_BREAKER_TRIPPED` AG-UI **CUSTOM event** → a **red pulse hits the live DAG node** and the agent is killed → Weave shows the runaway signal + a span tagged `breaker_state=OPEN`. The operator clicks **"Resume with safe fallback"** → a recovery agent **spawns from the Redis dead-letter queue** and the DAG completes.
>
> *"Real Redis state — not a `setTimeout`. The system protects itself, live, on stage."*

---

## Why this wins (mapped to the judging criteria)

| Criterion | How BLAST-RADIUS scores |
|---|---|
| **Creativity** | A live blast-radius DAG with a circuit breaker tripping as a graph animation — a visual no other team will have. |
| **Multi-agent harness sophistication** | Real parallel fan-out (LangGraph `Send()`), graph-enforced HITL interrupts, and an *external* circuit breaker protecting the agents from themselves. |
| **Utility** | Runaway-agent safety + blast-radius preview for any system that lets agents take destructive actions. |
| **Technical execution** | Deterministic mock infra backend + pre-warmed paths = a demo engineered not to stall on the weekend "agent demos fail" is the meme. |
| **Sponsor usage** | Weave (deep), CopilotKit/AG-UI (the standout visual), Redis (5 primitives beyond cache), OpenAI Agents SDK + LangGraph. Targets **Best CopilotKit (AirPods Max)** + Grand Prize, threatens **Best Redis**. |

## Sponsor usage at a glance

- **W&B Weave** *(required + Best Weave)* — every agent step is a `@weave.op`; `weave.attributes()` tags every span with `breaker_state` / `node_id` / `agent_id`; `weave.thread()` groups a run; an LLM-judge scorer + Online Monitor flag runaway behavior. See [`docs/WEAVE_DESIGN.md`](docs/WEAVE_DESIGN.md).
- **CopilotKit / AG-UI** *(Best CopilotKit)* — `useAgent` (v2) shared state drives the live DAG, `useCoAgentStateRender` renders per-node cards, **`useInterrupt` (v2)** powers the graph-enforced approval gate, AG-UI `CUSTOM` events drive the breaker-trip animation (`agent.subscribe`), `useFrontendTool`/`useComponent` render interactive controls. See [`docs/COPILOTKIT_FEATURES.md`](docs/COPILOTKIT_FEATURES.md).
- **Redis** *(Best Redis — beyond cache)* — Streams consumer groups (work bus + dead-letter), a real circuit breaker (`INCR` + `SET EX` + Lua), Keyspace Notifications (zero-polling control plane), RedisJSON (the DAG document), RedisVL (semantic recovery memory). See [`docs/REDIS_DESIGN.md`](docs/REDIS_DESIGN.md).
- **OpenAI** — Agents SDK + LangGraph orchestration; GPT-5.5 for planning/validation. See [`docs/LANGGRAPH_ORCHESTRATION.md`](docs/LANGGRAPH_ORCHESTRATION.md).
- **Cursor** — built with Cursor; dev-agent hooks emit Weave spans.

---

## Documentation

| Doc | What's in it |
|---|---|
| [`docs/AS_BUILT.md`](docs/AS_BUILT.md) | **What's actually implemented & verified running** + deviations from the plan |
| [`docs/CONCEPT.md`](docs/CONCEPT.md) | Problem, idea, why-it-wins, devil's-advocate counter-case |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Three-plane system design + request/runaway lifecycles |
| [`docs/COPILOTKIT_FEATURES.md`](docs/COPILOTKIT_FEATURES.md) | Every CopilotKit/AG-UI feature + exact verified APIs (v1.59.5) |
| [`docs/REDIS_DESIGN.md`](docs/REDIS_DESIGN.md) | Key schema + commands for all 5 Redis primitives (beyond cache) |
| [`docs/WEAVE_DESIGN.md`](docs/WEAVE_DESIGN.md) | 5-layer Weave instrumentation plan |
| [`docs/LANGGRAPH_ORCHESTRATION.md`](docs/LANGGRAPH_ORCHESTRATION.md) | The multi-agent harness: graph shape, `Send`, `interrupt`, bounded runaway |
| [`docs/BUILD_TIMELINE.md`](docs/BUILD_TIMELINE.md) | Hour-by-hour 4-person plan, Sat 11:15 → Sun 1:00pm |
| [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) | Second-by-second 3-minute demo + Q&A ammo |
| [`docs/RISKS.md`](docs/RISKS.md) | Devil's-advocate risk register + cut list |
| [`docs/SETUP.md`](docs/SETUP.md) | Exact install/run commands + sponsor credits |

## Repository layout

```
blast-radius/
├── README.md
├── docs/                      ← the full, hardened project plan (see table above)
├── apps/web/                  ← Next.js + CopilotKit cockpit  (package.json + env scaffolded)
└── services/agent/           ← Python FastAPI + LangGraph agent (requirements + env scaffolded)
```

## Run it

**One command (full stack — redis + agent + cockpit):**
```bash
docker compose up --build      # → cockpit at http://localhost:3000
```

**Or locally for dev:**
```bash
docker compose up -d redis                                           # redis-stack on :6379
cd services/agent && python3.12 -m venv .venv && . .venv/bin/activate \
  && pip install -r requirements.txt && uvicorn main:app --port 8000 # backend (:8000)
cd apps/web && npm install && npm run dev                            # cockpit (:3000)
```
No API keys required to run (Weave/OpenAI are optional). Click **Scale payments (happy path)** or
**Simulate Runaway Agent**. Tests: `cd services/agent && pytest tests -q` (8 pass).

## Production hardening

| Concern | Status |
|---|---|
| **Durable agent state** | ✅ Redis-backed LangGraph checkpointer (`langgraph-checkpoint-redis`) — in-flight/interrupted runs survive a restart. Falls back to in-memory. |
| **Human-in-the-loop** | ✅ Destructive-step gates **and** a "Resume with safe fallback" recovery gate, all over AG-UI `interrupt()` |
| **Observability** | ✅ Structured logging; Weave tracing + `weave.attributes(breaker_state)`; `RunawayScorer` for Weave Monitors |
| **Health** | ✅ `/healthz` (liveness) + `/readyz` (Redis readiness) |
| **Input validation / errors** | ✅ Pydantic request models, global exception handler, env-driven CORS; frontend error banner + error boundary |
| **LLM** | ✅ Optional OpenAI risk-validation (gated on `OPENAI_API_KEY`, deterministic fallback) |
| **Containers / CI** | ✅ Dockerfiles + full `docker-compose`; GitHub Actions (backend pytest on redis-stack + frontend typecheck/build) |
| **Known limits** | infra actions are deterministic mocks (demo safety); no auth/multi-tenancy/rate-limiting yet; CopilotKit *React hooks* unused (the cockpit uses the AG-UI protocol via `@ag-ui/client` — see [`docs/AS_BUILT.md`](docs/AS_BUILT.md)) |

## Status

✅ **Built & verified running end-to-end** (browser-tested: happy path with human-approval gates,
and the runaway → circuit-breaker-trip → recovery self-healing loop). 7/7 backend integration tests
pass against live Redis. See [`docs/AS_BUILT.md`](docs/AS_BUILT.md) for exactly what's implemented,
the confirmed stack versions, and where reality diverged from the plan.

## Team

_Add team members + X/LinkedIn handles here before submission._

## License

MIT — see [`LICENSE`](LICENSE). Code and rights are the team's own, per WeaveHacks eligibility rules.
