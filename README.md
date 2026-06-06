# 💥 BLAST-RADIUS

> **The multi-agent infra-change cockpit.** You ask an agent team to make an infrastructure change. It decomposes the request into a live **blast-radius DAG**, fans specialist agents out across it, gates every destructive step behind a human approval — and a **real Redis circuit breaker** kills any agent that goes runaway, visualized as a red pulse racing across the graph.

Built at **WeaveHacks 4** (June 2026). Powered by **W&B Weave · CopilotKit / AG-UI · Redis · OpenAI Agents SDK + LangGraph**.

---

## The 30-second pitch

Agents that take *destructive* actions — infra changes, deployments, credential rotations, migrations — have no **blast-radius preview** and no automated **kill switch**. When an agent loops or goes rogue mid-execution, nothing stands between it and production. The trending failure mode of 2026 is *"multi-agent demos that stall, loop on tool calls, and blow latency budgets."*

**BLAST-RADIUS** is the cockpit that fixes it:

1. **Decompose** — an Orchestrator agent turns a natural-language infra request into a dependency **DAG** of steps.
2. **Visualize** — the DAG renders **live in the browser**, every node streaming its status (`pending → running → done / failed / blocked`).
3. **Fan out** — Validator + Executor specialist agents run across the DAG in parallel.
4. **Gate** — every destructive node pauses for a **human-in-the-loop approval** before it touches anything.
5. **Protect** — a **real Redis circuit breaker** trips when an agent loops or fails repeatedly, killing it instantly and spawning a recovery agent from a dead-letter queue.

## The jaw-drop demo moment

> Click **"Simulate Runaway Agent."** The agent loops → Redis `INCR` crosses a threshold in ~3s → `SETEX` opens the breaker key with a TTL → a **Keyspace Notification** fires a `CIRCUIT_BREAKER_TRIPPED` AG-UI **CUSTOM event** → a **red pulse hits the live DAG node** and the agent is killed → Weave Monitors lights up the Bug signal. The operator clicks **"Resume with safe fallback"** → a recovery agent **spawns from the Redis dead-letter queue** and the DAG completes.
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

- **W&B Weave** *(required + Best Weave)* — every agent step is a `@weave.op`; `weave.attributes()` tags every span with `breaker_state` / `node_id` / `agent_id`; Online Monitoring signals + an LLM-judge scorer flag runaway behavior; W&B MCP server for trace queries. See [`docs/WEAVE_DESIGN.md`](docs/WEAVE_DESIGN.md).
- **CopilotKit / AG-UI** *(Best CopilotKit)* — `useCoAgent`/`useAgent` shared state drives the live DAG, `useCoAgentStateRender` renders per-node cards, `useLangGraphInterrupt` + `useHumanInTheLoop` power the approval gates, AG-UI `CUSTOM` events drive the breaker-trip animation, `useFrontendTool` renders interactive controls. See [`docs/COPILOTKIT_FEATURES.md`](docs/COPILOTKIT_FEATURES.md).
- **Redis** *(Best Redis — beyond cache)* — Streams consumer groups (work bus + dead-letter), a real circuit breaker (`INCR` + `SETEX` + TTL), Keyspace Notifications (zero-polling control plane), RedisJSON (the DAG document), RedisVL (recovery memory). See [`docs/REDIS_DESIGN.md`](docs/REDIS_DESIGN.md).
- **OpenAI** — Agents SDK + LangGraph orchestration; GPT-5.5 for planning/validation.
- **Cursor** — built with Cursor; dev-agent hooks emit Weave spans.

---

## Repository layout

```
blast-radius/
├── README.md                  ← you are here
├── docs/
│   ├── CONCEPT.md             ← problem, idea, why-it-wins, the debate
│   ├── COPILOTKIT_FEATURES.md ← every CopilotKit feature we use + how (authoritative)
│   ├── ARCHITECTURE.md        ← system design + data flow  (added after review)
│   ├── REDIS_DESIGN.md        ← Redis key schema + commands (added after review)
│   ├── WEAVE_DESIGN.md        ← Weave instrumentation plan  (added after review)
│   ├── BUILD_TIMELINE.md      ← hour-by-hour 4-person plan   (added after review)
│   └── DEMO_SCRIPT.md         ← second-by-second 3-min demo  (added after review)
├── apps/web/                  ← Next.js + CopilotKit frontend (the cockpit)
└── services/agent/           ← Python FastAPI + LangGraph agent backend
```

## Status

🏗️ **Planning → build.** This repo currently contains the fully-scrutinized project plan (hardened by a multi-agent research + devil's-advocate review). Scaffolding and implementation land next.

## License

MIT — see [`LICENSE`](LICENSE). Code and rights are the team's own, per WeaveHacks eligibility rules.
