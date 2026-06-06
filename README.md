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

## Status

✅ **Plan complete & scrutinized.** The full build plan was produced by a multi-agent research + devil's-advocate review (which corrected live API versions and flagged the must-avoid pitfalls now baked into the docs). Scaffolding is in place. **Next: implement the vertical slice (see [`docs/BUILD_TIMELINE.md`](docs/BUILD_TIMELINE.md)).**

## Team

_Add team members + X/LinkedIn handles here before submission._

## License

MIT — see [`LICENSE`](LICENSE). Code and rights are the team's own, per WeaveHacks eligibility rules.
