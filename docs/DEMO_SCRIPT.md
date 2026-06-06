# 3-minute demo script (strictly enforced)

> One driver, one narrator. Everything on the demo path is deterministic / pre-seeded. A recorded fallback video is cued on a second machine.

| Time | On screen | Narration |
|---|---|---|
| **0:00–0:12** | Cockpit: empty DAG canvas, `CopilotSidebar`, suggestion chips. | "Agents are starting to run real infrastructure changes. The problem: no blast-radius preview, and no kill switch when one goes rogue. This is BLAST-RADIUS." |
| **0:12–0:30** | Click chip **"Scale the payments service."** Orchestrator streams a **DAG** of 5 nodes; they paint left-to-right (validate-IAM → check-deps → scale-payments → update-LB → healthcheck). | "An orchestrator agent decomposes the request into a dependency graph — the blast radius — and fans validator agents across it in parallel." (LangGraph `Send`.) |
| **0:30–0:48** | Nodes go yellow→green via `STATE_DELTA`. The **scale-payments** node (destructive) pauses; an **approval modal** slides in. | "Every destructive step is gated. This pause is graph-enforced — a real LangGraph `interrupt`, not a prompt." |
| **0:48–1:00** | **Hand the laptop to a judge.** They click **Approve**. The node resumes and completes green. | "You're the operator. You approve it." (Judge interaction = the room is yours.) |
| **1:00–1:20** | Click **"Simulate Runaway Agent."** The update-LB executor loops; a counter ticks; at 5 the node **pulses RED**. Split-screen: Redis key `cb:executor-1:open` appears. | "Now it goes rogue. A **real Redis circuit breaker** — `INCR`, then `SET EX` — trips in three seconds. A Keyspace Notification fires the alert. Not a `setTimeout`: durable Redis state." |
| **1:20–1:35** | The agent is killed. Weave Monitors panel shows the runaway **signal** + a span tagged `breaker_state=OPEN`. | "Weave caught it — every agent step is traced, tagged with the breaker state. This is the evidence layer." |
| **1:35–1:55** | Click **"Resume with safe fallback."** A **recovery agent** spawns, consumes the dead-letter queue, pulls similar past-failure context (RedisVL), and completes the step safely. DAG goes all-green. | "Recovery isn't magic — a dead-letter queue and semantic memory survive the failure and re-enter the graph." |
| **1:55–2:10** | Split-screen: `cb:executor-1:open` **disappears** after its TTL — the breaker auto-resets (`:expired` keyevent). | "And the breaker resets itself. Self-healing, live." |
| **2:10–2:40** | **One slide:** Problem (agents take destructive actions, no kill switch) → Solution (blast-radius cockpit + real breaker) → Stack logos (Weave · CopilotKit/AG-UI · Redis · OpenAI). | "Built on CopilotKit's AG-UI — live generative UI; Redis beyond cache — streams, breaker, keyspace, vector memory; and Weave for full agent observability." |
| **2:40–3:00** | Back to the all-green DAG. | "BLAST-RADIUS: agents you can watch, gate, and trust — because the system protects itself. Thank you." |

## Q&A ammo (judges get 1–2 questions)
- *"What's actually live vs mocked?"* — "The infra backend is a deterministic mock; everything else — the LangGraph graph, the Redis breaker, the Keyspace event, the Weave traces, the recovery from the DLQ — is real. We can trip the breaker again right now: [click **Force Reset** → it deletes `cb:*:open`]."
- *"Why Redis and not a timer?"* — "A `setTimeout` dies with the process. The breaker state is external and durable; it trips even if the agent is wedged, and any worker sees it instantly."
- *"Show the harness."* — open Weave: parallel `Send` fan-out, the `interrupt`, the recover node, all as a trace tree.
