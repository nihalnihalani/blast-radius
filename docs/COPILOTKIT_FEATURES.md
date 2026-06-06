# CopilotKit / AG-UI feature map (for Best CopilotKit)

> Grounded in the official CopilotKit skill docs — **v1.51.3**, Python SDK **v0.1.78**. Goal: use and *visibly highlight* as many current CopilotKit features as possible, because the live DAG cockpit is the strongest generative-UI story in the room.

## Every feature we use and exactly how

| CopilotKit feature | Where it's used in BLAST-RADIUS |
|---|---|
| **`useCoAgent` / `useAgent` (v2)** | The single source of truth for the **live DAG**. The LangGraph backend streams `STATE_DELTA` (JSON-Patch) updates as node statuses change; `agent.state.dag` re-renders the graph in real time. `useAgent` (v2) is preferred for bidirectional sync + time-travel. |
| **`useCoAgentStateRender({name, node, render})`** | Renders a **generative status card per DAG node / LangGraph node** as each agent executes — `pending` skeleton → `running` spinner with live logs → `done`/`failed` result card. This is the per-agent progress UI. |
| **`useLangGraphInterrupt`** | Powers the **destructive-step approval gate**. The LangGraph backend calls `interrupt()` before any destructive node; this hook surfaces the graph-enforced pause as an approval card. The pause is *real* (graph-level), not advisory. |
| **`useHumanInTheLoop`** | Renders the approval / **"Resume with safe fallback"** decision UI bound to the interrupt. |
| **AG-UI `CUSTOM` events** | The backend emits a `CIRCUIT_BREAKER_TRIPPED` custom event (triggered by a Redis Keyspace Notification). The frontend catches it and fires the **red-pulse animation** on the affected DAG node + the agent-health card. |
| **`useFrontendTool({name, parameters, handler, render})`** | Interactive cockpit controls the agent can invoke with custom-rendered UI — e.g. a `request_approval` tool that draws the approve/reject buttons, and the `simulate_runaway` trigger. (Wrapper around `useCopilotAction` + `render`.) |
| **`useRenderToolCall`** | Custom UI for **backend-defined tool calls** (e.g. an `apply_infra_change` mock tool renders a diff card). |
| **`useDefaultTool`** | Fallback renderer so any unmapped agent tool call still shows a clean card — useful with many backend tools. |
| **`useCopilotReadable`** | Exposes current cockpit context (selected node, environment, operator identity) to the agents one-way. |
| **`useCopilotAction`** | Operator-issued actions (e.g. "re-run failed node", "abort run"). |
| **`useCopilotChatSuggestions`** | Context-aware suggestion chips ("Scale the payments service", "Rotate DB credentials") to drive the demo without typing. |
| **`useCopilotAdditionalInstructions`** | Injects page/run-specific context (current DAG state) into the copilot prompt. |
| **`CopilotSidebar`** | The chat surface where the operator issues the infra request and watches agent narration. |
| **`CopilotKit` provider** (`runtimeUrl`, `agent`, `showDevConsole`, `enableInspector`, `onError`) | App-level wiring to the runtime + the LangGraph agent; `enableInspector`/`showDevConsole` help us debug live. |

## Generative-UI pattern used

- **Static Generative UI (AG-UI)** — we pre-build the React DAG/node components and the agents select + populate them. Highest developer control, most reliable for a live demo. (We deliberately avoid open-ended MCP-Apps UI for demo predictability.)

## AG-UI protocol events we rely on

`RUN_STARTED` / `RUN_FINISHED` / `RUN_ERROR` · `STATE_SNAPSHOT` + `STATE_DELTA` (JSON-Patch node-status streaming — **the heart of the live DAG**) · `STEP_STARTED` / `STEP_FINISHED` (per DAG step) · `TOOL_CALL_*` · **`CUSTOM`** (`CIRCUIT_BREAKER_TRIPPED`).

## Backend wiring

```
Next.js  ── CopilotKit provider ──▶ /api/copilotkit (CopilotRuntime + OpenAIAdapter)
                                         │  CustomHttpAgent('infra_orchestrator', url)
                                         ▼
Python FastAPI  ── CopilotKitRemoteEndpoint + LangGraphAgent ──▶ LangGraph StateGraph
                                         │  emits AG-UI events (STATE_DELTA, CUSTOM)
                                         ▼
                              Redis (Streams, breaker, Keyspace, RedisJSON)
```

## "New features" we name-drop for the judges

Beyond the hooks above, we will reference CopilotKit's 2026 platform direction in the pitch: the **AG-UI protocol** (adopted by Google/Microsoft/AWS/LangChain), the **CopilotKit Intelligence Platform / CLHF** (continuous learning from human feedback — our approval clicks are exactly the human-feedback signal it consumes), and **multi-platform deploy** (the same agent could surface in Slack/Teams). These frame BLAST-RADIUS as built on the emerging standard, not a one-off.

> ⚠️ Verify exact import paths against the installed CopilotKit version during setup (`useAgent` vs `useCoAgent`, `useFrontendTool` vs `useCopilotAction`+render). The hardened build plan pins versions.
