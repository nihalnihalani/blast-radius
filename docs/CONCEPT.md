# BLAST-RADIUS — Concept

## The problem

AI agents increasingly take **destructive, irreversible actions**: scaling services, rotating credentials, running migrations, deploying, modifying infrastructure. Two things are missing from every such system:

1. **Blast-radius preview** — before an agent acts, *what else does this touch?* There is no dependency-aware view of the change.
2. **A real kill switch** — when an agent loops, rate-limits, or goes rogue mid-execution, there is nothing automated between it and production. A `setTimeout` is not a circuit breaker.

This maps directly onto the most-shared agent meme of 2026: *multi-agent systems that stall under load, loop on tool calls, and blow latency budgets.* 60% of production LLM-span errors trace to rate limits. The reliability/resilience layer — circuit breakers, bulkheads, blast-radius limiters, dead-letter queues — is the hot, unsolved frontier.

## The idea

**BLAST-RADIUS** is a multi-agent *infra-change cockpit*:

- An **Orchestrator** agent decomposes a natural-language infra request into a **dependency DAG** of steps, stored as a RedisJSON document.
- **Validator** and **Executor** specialist agents fan out across the DAG in parallel (LangGraph `Send()`).
- The DAG renders **live in the browser** via CopilotKit shared state — each node streams `pending → running → done / failed / blocked`.
- Every **destructive** node is gated by a **human-in-the-loop approval** (graph-enforced LangGraph `interrupt()`).
- A **real Redis circuit breaker** protects the agents from themselves: repeated failures `INCR` a per-agent counter; crossing the threshold `SETEX`s a breaker key with a TTL; a **Keyspace Notification** fires a `CIRCUIT_BREAKER_TRIPPED` AG-UI **CUSTOM event** that animates a red pulse on the DAG node and kills the agent. A **recovery agent** is spawned from a Redis **dead-letter queue**.

The infra backend is **mocked and deterministic** — we are demonstrating the *control plane and reliability harness*, not actually mutating real cloud infra on stage.

## Why it wins

This was selected over two strong alternatives (**SENTINEL**, an eval-driven deploy gate; **MUTATION-HUNT**, a parallel hypothesis engine) through a simulated panel of the actual WeaveHacks judges. BLAST-RADIUS won on:

- **Creativity (8/10 in the internal panel)** — the live DAG + breaker-trip animation is a visual nobody else will have.
- **Engineering credibility** — it lands dead-center in Patrick Ma's (Cognition/Devin) and Guy Royse's (Redis) domains: real distributed-systems reliability, not a wrapper.
- **Sponsor sweep potential** — strongest possible CopilotKit generative-UI story (Best CopilotKit / AirPods Max) *and* the hardest Redis-beyond-cache story (Best Redis), on top of the required Weave usage and Grand Prize contention.

## The honest counter-case (devil's advocate)

- **More live moving parts at the climax than a safe demo wants.** → Mitigation: the breaker trip runs on *real* Redis state but against a *deterministic* mock workload; a recorded fallback video is cued.
- **The DAG visual is frontend-heavy** and can eat hours. → Mitigation: P0 is a static-layout DAG with streamed node-status colors; physics/auto-layout is P2.
- **Weave can read as instrumentation, not load-bearing.** → Mitigation: the LLM-judge runaway-detection signal and `breaker_state`-tagged spans make Weave the *evidence layer* for the reliability story, and the Monitors view is an on-stage beat.

## Judges (engineering-heavy panel)

Patrick Ma (Cognition/Devin) · Dominik Kundel (OpenAI Codex) · LingXi Li (Cursor) · Paige Bailey (Google DeepMind) · Nina Olding (Staff PM @ Weave) · Sam Stowers (WeaveHacks creator) · Jay Hack (Head of AI @ ClickUp) · Guy Royse (Redis DevRel).
