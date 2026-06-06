# CopilotKit / AG-UI feature map (for Best CopilotKit)

> **Versions verified by research (June 2026):** `@copilotkit/react-core` **v1.59.5** · `ag-ui-langgraph` **0.0.40** · Python `copilotkit` SDK current. The **v2 hooks** live in the `@copilotkit/react-core/v2` subpath; v1 hooks still work with no breaking changes. **Verify import paths on-site after `npm install`.**

Goal: use and *visibly highlight* as many current CopilotKit features as possible — the live DAG cockpit is the strongest generative-UI story in the room.

---

## ⚠️ Corrections from the hardening review (do not get these wrong)

| Claim to avoid | Correct fact |
|---|---|
| "`useLangGraphInterrupt` powers the gate" | That hook is **v1 / migration-recommended**. The v2 graph-enforced pause hook is **`useInterrupt`** (`@copilotkit/react-core/v2`), which binds to Python's LangGraph `interrupt()`. |
| "`useHumanInTheLoop` handles the LangGraph interrupt" | `useHumanInTheLoop` is **tool-based HITL** (the LLM decides to call it). It will **not** receive a graph `interrupt()` event. Use it for *optional* approvals, not the hard gate. |
| "render gets a `failed` status" | `ToolCallStatus` is only **`InProgress | Executing | Complete`**. Do not branch on `failed`. |
| "We use CLHF (Continuous Learning from Human Feedback)" | CLHF + Analytics are **"Coming Soon"** on the Intelligence Platform — **not buildable now**. We may *align our story* with it (our approval clicks are exactly the feedback signal), but we never claim it as a shipped feature. |
| "Emit the custom event with a copilotkit helper" | `copilotkit.langgraph` has **no** `copilotkit_emit_custom_event`. Emit `ag_ui.core.CustomEvent` via the encoder (see Redis/AG-UI wiring). |

## Every feature we use and exactly how

| CopilotKit feature (verified API) | Where it's used in BLAST-RADIUS |
|---|---|
| **`useAgent({ agentId })`** — `@copilotkit/react-core/v2` — returns `{ agent }` with `agent.state`, `setState()`, `setMessages()` (time-travel), `isRunning`, `abortRun()`, **`subscribe()`** | The single source of truth for the **live DAG**. `agent.state.dag` re-renders the graph as the backend streams `STATE_DELTA` (RFC-6902 JSON-Patch). `agent.subscribe({ onCustomEvent })` catches the breaker-trip event. `agent.abortRun()` is wired to the "Abort run" control. |
| **`useCoAgentStateRender({ name, node, render })`** — v1, still active | Renders a **generative status card per LangGraph node** (`pending` skeleton → `running` spinner+logs → `done/failed` card). One registration per DAG node type. |
| **`useInterrupt({ agentId, render, enabled })`** — `@copilotkit/react-core/v2` | **The destructive-step approval gate.** Binds to the Python `interrupt()` call; `render` gets `{ event:{value}, resolve }`. `resolve({approved:true})` resumes the graph via `Command(resume=...)`. This is the *graph-enforced* pause. |
| **`useHumanInTheLoop({ name, description, parameters, render })`** — v2 | Secondary, *tool-based* approvals the agent itself can request (e.g. "this looks risky, confirm?"). Render statuses: `InProgress / Executing / Complete`. |
| **`useFrontendTool({ name, parameters, handler, render })`** — v2 | Interactive cockpit controls the agent can invoke with custom UI — e.g. `simulate_runaway`, `force_reset`, `rerun_node`. (Wrapper around `useCopilotAction` + `render`.) **Guard against the known double-invoke loop (issue #3044) with a React ref.** |
| **`useComponent({ name, parameters, render })`** — v2 | Convenience wrapper over `useFrontendTool` for pure render-only generative components (e.g. the blast-radius summary card). A *new* v2 hook — good to highlight. |
| **`useRenderToolCall({ name, render })`** | Custom UI for **backend tool calls** (e.g. `apply_infra_change` renders a mock diff card). |
| **`useDefaultTool({ render })`** | Fallback renderer so any unmapped agent tool call still shows a clean card. |
| **`useAgentContext(...)`** (v2, replaces `useCopilotReadable`) / `useCopilotReadable` (v1) | Exposes cockpit context (selected node, environment, operator) one-way to the agents. |
| **`useCopilotAction({ name, parameters, handler })`** | Operator actions: `rerun failed node`, `abort run`. |
| **`useCopilotChatSuggestions({ instructions })`** | Context-aware suggestion chips ("Scale the payments service", "Rotate DB credentials") to drive the demo with one click, no typing. |
| **`useCopilotAdditionalInstructions({ instructions })`** | Injects current DAG state into the copilot prompt each turn. |
| **`CopilotSidebar`** (+ `import "@copilotkit/react-ui/styles.css"`) | The chat surface for issuing the infra request and reading agent narration. |
| **`CopilotKit` provider** — `runtimeUrl`, `agent`, `showDevConsole`, `enableInspector`, `onError` | App wiring to the runtime + LangGraph agent; `enableInspector` helps debug live. |

## Generative-UI pattern

**Static Generative UI (AG-UI)** — we pre-build the React DAG/node components; agents select + populate them. Highest dev control, most reliable for a live demo. We deliberately avoid open-ended MCP-Apps UI for predictability.

## AG-UI events we rely on (the JS SDK now defines 27 event types; these are ours)

`RUN_STARTED` / `RUN_FINISHED` / `RUN_ERROR` · **`STATE_SNAPSHOT` + `STATE_DELTA`** (JSON-Patch node-status streaming — the heart of the live DAG) · `STEP_STARTED` / `STEP_FINISHED` · `TOOL_CALL_*` · **`CUSTOM`** (`CIRCUIT_BREAKER_TRIPPED`).

`CustomEvent` interface: `{ type: EventType.CUSTOM, name: string, value: any }`. `STATE_DELTA`: `{ type: EventType.STATE_DELTA, delta: JsonPatch[] }`.

## Backend wiring

```
Next.js ── <CopilotKit runtimeUrl="/api/copilotkit" agent="infra_orchestrator">
            │
            ▼  /api/copilotkit  (CopilotRuntime + OpenAIAdapter + CustomHttpAgent)
Python FastAPI ── CopilotKitRemoteEndpoint + LangGraphAgent
            │   state extends CopilotKitState  → auto STATE_DELTA streaming
            │   ag_ui.core.CustomEvent          → CIRCUIT_BREAKER_TRIPPED
            ▼
        LangGraph StateGraph  ↔  Redis (Streams / breaker / Keyspace / RedisJSON)
```

## Frontend reception of the breaker event (verified)

```tsx
const { agent } = useAgent({ agentId: "infra_orchestrator" });
useEffect(() => agent.subscribe({
  onCustomEvent: ({ event: { name, value } }) => {
    if (name === "CIRCUIT_BREAKER_TRIPPED") triggerRedPulse(value.node_id);
  },
}), [agent]);
```

## Known CopilotKit bugs to design around (from research)

- **#2179** — `copilotkit_emit_state` can be overwritten when a node calls `.invoke()`. **Workaround:** also return the state from the node, not only emit it.
- **#3044** — `useFrontendTool` can double-invoke. Guard with a `useRef` latch.
- **#3154** — chat input is blocked while a `useFrontendTool` UI is pending. Design the approval UX so the operator isn't expected to also type.
- **#2574 (langgraph)** — `adispatch_custom_event` can be dropped under `langgraph up` locally. Prefer emitting `CustomEvent` from the streaming endpoint and **test custom events early**.
