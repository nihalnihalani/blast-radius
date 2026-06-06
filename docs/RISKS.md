# Risk register (devil's-advocate hardened)

> Consolidated from the multi-agent research + adversarial review. Severity: 🔴 BLOCKER · 🟠 MAJOR · 🟡 MINOR.

| # | Risk | Sev | Mitigation |
|---|---|---|---|
| 1 | **CopilotKit version/import drift.** Brief assumed v1.51.3; live is **v1.59.5** with v2 hooks in `/v2` subpath. Wrong import = nothing renders. | 🔴 | First thing Saturday: `npm ls @copilotkit/react-core`; confirm `import { useAgent } from "@copilotkit/react-core/v2"` resolves. Fall back to v1 `useCoAgent` if `/v2` path is unavailable. |
| 2 | **Wrong HITL hook.** `useHumanInTheLoop` is tool-based and will NOT receive LangGraph `interrupt()`. | 🔴 | Use **`useInterrupt`** (v2) for the graph gate. `useHumanInTheLoop` only for optional agent-requested confirmations. |
| 3 | **`GraphRecursionError` on the runaway loop.** Default `recursion_limit=25` throws an uncaught error CopilotKit won't surface. | 🔴 | Trip the Redis breaker at count **5** (well below 25); short-circuit with `Command(goto="recover")`. Optionally raise limit to 50. |
| 4 | **State doesn't stream to the DAG.** A plain `TypedDict` won't auto-emit `STATE_DELTA`. | 🔴 | State **must extend `CopilotKitState`**. Also return changed state from each node (bug #2179), not only `copilotkit_emit_state`. |
| 5 | **Custom event dropped/delayed** (langgraph #2574; emitting from a background task fails). | 🟠 | Route Keyspace notifications through an `asyncio.Queue` drained **inside** the orchestrator's run context; emit `ag_ui.core.CustomEvent` from the streaming endpoint. **Spike this hour 1.** |
| 6 | **Redis free tier 30-conn cap** — 4 consumers + pubsub + JSON reads exceed it under demo load. | 🟠 | Use paid Essentials/Pro with `WEAVEHACKS_4`, or local `redis-stack` Docker. Pool connections. |
| 7 | **Keyspace `:expired` lag** — fires when Redis deletes the key, not at TTL=0. | 🟠 | Subscribe to **`:set`** for the instant trip; use `:expired` only for the (non-critical) reset beat. |
| 8 | **Breaker INCR/EXPIRE race** leaks a counter with no TTL. | 🟡 | Atomic **Lua script** (or MULTI/EXEC). |
| 9 | **`JSON.MERGE` overwrites arrays.** | 🟡 | Keep `edges` arrays at root/leaves; use `JSON.ARRAPPEND` for lists. |
| 10 | **Online Monitor is UI-only** (no `weave.create_monitor()`). | 🟡 | Budget 15 min to click it together in the Weave UI; don't claim code created it. |
| 11 | **`useFrontendTool` double-invoke (#3044) / chat blocked while pending (#3154).** | 🟡 | Guard with a `useRef` latch; don't require typing during an approval. |
| 12 | **"Beyond cache" challenged by Guy Royse.** | 🟠 | Lead with Streams+breaker+Keyspace+RedisVL; explicitly say "zero caching in this project." |
| 13 | **Merge-at-hour-17 integration failure.** | 🔴 | Integration checkpoints at Sat 15:00, Sat 21:00, Sun 11:00. Vertical slice first. |
| 14 | **Live demo stalls on stage** (the reliability product fails on reliability — worst irony). | 🔴 | Deterministic mock backend, pre-seeded DLQ, pre-warmed everything, **recorded fallback video** cued. |
| 15 | **Weave reads as "just instrumentation."** | 🟡 | `weave.attributes(breaker_state)` + Online Monitor signal make Weave the *evidence layer* for the reliability claim — an on-stage beat, not a footnote. |
| 16 | **CLHF claimed as built** (it's "Coming Soon"). | 🟡 | Never claim it. Reference only as roadmap our approval-clicks align with. |

## Cut list (drop in this order if behind)
1. RedisVL semantic recovery → replace with a static "safe fallback" path (still consume the DLQ).
2. Online Monitor UI setup → show `breaker_state`-tagged traces instead.
3. `:expired` auto-reset beat → use the **Force Reset** button only.
4. Parallel `Send` fan-out across many nodes → validate sequentially (keep ONE parallel pair for the harness story).
5. Multiple DAG templates → ship exactly one ("scale payments").

**Never cut:** the live DAG, the approval gate, the breaker-trip red-pulse, Weave tracing. Those four are the score.
