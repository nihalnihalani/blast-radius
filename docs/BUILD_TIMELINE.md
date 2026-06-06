# Build timeline — Sat 11:15am → Sun 1:00pm (~18 working hours, 4 builders)

> **Golden rule (from the feasibility audit):** integrate END-TO-END by the end of Day 1. The classic loss is "merge at hour 17." We have a thin vertical slice working Saturday night, then harden.

## Roles

| | Owner | Domain |
|---|---|---|
| **A** | Agents/Backend lead | LangGraph graph, orchestrator/validator/executor/recover nodes, OpenAI |
| **B** | Redis/Infra lead | Streams, breaker (Lua), Keyspace listener, RedisJSON, RedisVL, DLQ |
| **C** | Weave/Eval lead | `@weave.op` wrapping, `weave.attributes`, threads, Online Monitor, scorer |
| **D** | Frontend lead | Next.js, CopilotKit hooks, React Flow DAG, approval modal, red-pulse anim |

## SATURDAY

**11:15–12:00 — ALL: setup + de-risk.** Repo clone. `npx copilotkit@latest create -f next`. Start `redis-stack` Docker (or Redis Cloud + `WEAVEHACKS_4`). `weave.init`. **Verify on-site immediately:** `pip show langgraph` (Send import path), `npm ls @copilotkit/react-core` (confirm v1.59.x + `/v2` subpath resolves), Weave plan tier for Online Monitor, GPT-5.5 credits/rate limits. Grab credits form. **Spike the riskiest thing first: emit one AG-UI `CustomEvent` from Python and catch it in `agent.subscribe` (issue #2574 risk).**

**12:00–15:00 — parallel build of the vertical slice.**
- **A:** `StateGraph(BlastRadiusState extends CopilotKitState)`; orchestrator node returns a hardcoded 4-node DAG; one validator + one executor; `Send` fan-out. Prove state streams.
- **B:** Redis up; `dag:run:{id}` JSON doc; `JSON.MERGE` per node; breaker Lua script unit-tested (INCR→EXPIRE→SET EX); Keyspace `KE$x` listener → `asyncio.Queue`. **Prove the breaker fires on real state.**
- **C:** wrap A's nodes with `@weave.op`; `weave.attributes({breaker_state,...})`; `weave.thread(run_id)`. **Prove the trace tree appears.**
- **D:** CopilotKit provider + `CopilotSidebar`; React Flow canvas; `useAgent` → render DAG from `agent.state`; `useCoAgentStateRender` node cards. **Prove a node turns green from backend state.**

**15:00 — INTEGRATION CHECKPOINT #1:** type a request → DAG paints → a node goes pending→running→done end-to-end. If not working, stop feature work and fix the seam.

**15:00–18:30 — the two hero beats.**
- **A+D:** approval gate: `interrupt()` in `approval_node` ↔ `useInterrupt` modal ↔ `Command(resume)`. A judge can click Approve.
- **B+A:** runaway path: `simulate_runaway` loop → breaker trips at 5 → Keyspace `:set` → queue → `CustomEvent(CIRCUIT_BREAKER_TRIPPED)`.
- **D:** `agent.subscribe(onCustomEvent)` → **red-pulse animation** on the node. Guard `useFrontendTool` with a ref (#3044).

**18:30 dinner / 18:30–21:00:** INTEGRATION CHECKPOINT #2 — the full runaway beat works once, live. Then **DECISION:** lock the demo path — hardcode the request via a suggestion chip, pre-seed the DLQ message, set TTLs (breaker 10s). Commit a tag `demo-working`.

## SUNDAY

**09:00–11:00 — harden + recover beat.**
- **B+A:** "Resume with safe fallback" → DLQ consume + RedisVL `get_relevant` → node completes.
- **C:** Online Monitor configured in Weave UI (15 min); scorer firing; `breaker_state` filter view ready to show.
- **D:** polish — remove UI noise from the approval moment; split-screen Redis Cloud key browser (`cb:executor-1:open` appears/disappears).

**11:00–12:00 — demo safety.** Deterministic fixtures, localhost fallback, **record a full-loop fallback video**. Pre-warm everything. 1 slide.

**12:00–13:00 — rehearse ×5 to the second.** Roles: 1 driver, 1 narrator, 1 clock-watcher, 1 on the fallback video. README + submission blurb. **Submit before 1:00pm.**

## Integration checkpoints (non-negotiable)
- **#1 (Sat 15:00):** state round-trips backend→UI.
- **#2 (Sat 21:00):** full runaway beat works once.
- **#3 (Sun 11:00):** recover beat + Weave evidence ready.
