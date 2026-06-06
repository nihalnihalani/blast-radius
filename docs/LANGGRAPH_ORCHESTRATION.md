# LangGraph orchestration (the multi-agent harness)

> Verified APIs (June 2026). The harness is what the engineering judges scrutinize — make it genuinely parallel + interruptible + bounded.

## State (must extend CopilotKitState for auto STATE_DELTA streaming)

```python
from copilotkit import CopilotKitState
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send, Command, interrupt
from langgraph.checkpoint.memory import MemorySaver

class BlastRadiusState(CopilotKitState):     # NOT a plain TypedDict
    run_id: str
    request: str
    dag_nodes: dict        # {node_id: {status, agent, deps}}
    failure_counts: dict
    breaker_open: bool
    pending_approvals: list
    completed_steps: list
```
**Gotcha:** a plain `TypedDict` will **not** auto-stream to the frontend. It must extend `CopilotKitState`. Also (issue #2179) always **return** changed state from a node, don't rely solely on `copilotkit_emit_state`.

## Graph shape

```python
g = StateGraph(BlastRadiusState)
g.add_node("orchestrator", orchestrator_node)     # decompose -> dag_nodes, write RedisJSON
g.add_node("validator", validator_node)           # per-step validation
g.add_node("approval", approval_node)             # calls interrupt() for destructive steps
g.add_node("executor", executor_node)             # mock apply + Stream enqueue + breaker
g.add_node("recover", recover_node)               # DLQ + RedisVL fallback

g.add_edge(START, "orchestrator")
g.add_conditional_edges("orchestrator", fan_out_steps)   # returns [Send("validator", s) ...]
g.add_conditional_edges("validator", route_after_validate)  # -> "approval" if destructive else "executor"
g.add_edge("approval", "executor")
g.add_conditional_edges("executor", route_after_exec)    # -> "recover" if breaker_open else END
g.add_edge("recover", END)

graph = g.compile(checkpointer=MemorySaver())     # checkpointer REQUIRED for interrupt()
```

## Parallel fan-out (Send)

```python
def fan_out_steps(state: BlastRadiusState):
    return [Send("validator", {**state, "current": nid}) for nid in state["dag_nodes"]]
```
`Send(node, state)` triggers **true parallel execution within one superstep**. **Gotcha:** `Send` imports from `langgraph.types` (or `langgraph.constants`); verify with `pip show langgraph` on-site. Use the **async** graph (`astream`/`ainvoke` + `MemorySaver`) since nodes do async Redis I/O.

## Human-in-the-loop gate (interrupt)

```python
def approval_node(state):
    decision = interrupt({"node": state["current"], "plan": state["dag_nodes"][state["current"]]})
    return {"pending_approvals": [...], "approved": decision.get("approved", False)}
# resume from frontend: useInterrupt.resolve({approved:true}) -> Command(resume={"approved":true})
```
Requires `checkpointer` + `config={"configurable":{"thread_id": run_id}}` on every `ainvoke/astream`.

## Bounded runaway (the demo, done safely)

```python
async def executor_node(state):
    if state.get("simulate_runaway"):
        for i in range(10):                       # loop on purpose
            n = await trip_breaker(state["current"])   # Redis INCR+...
            if await breaker_open(state["current"]):
                return Command(goto="recover")     # short-circuit BEFORE recursion_limit
    ...
```
**Gotcha:** LangGraph's default `recursion_limit=25` raises an **uncaught** `GraphRecursionError` that CopilotKit does not surface gracefully. We trip the Redis breaker at count **5** so the animation fires first. Optionally raise the limit via `ainvoke(state, {"recursion_limit": 50})`.

## Why OpenAI Agents SDK is also in play

The orchestrator's planning + validator reasoning use GPT-5.5 via the OpenAI Agents SDK (handoffs as an alternative to raw LangGraph edges for the reasoning sub-steps). LangGraph owns the durable graph + interrupts; the Agents SDK owns the per-agent reasoning. Both traced by Weave.
