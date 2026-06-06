"use client";
import { useCoAgent, useCopilotAction } from "@copilotkit/react-core";
import type { BlastRadiusState } from "../lib/types";

const AGENT = process.env.NEXT_PUBLIC_AGENT_NAME ?? "infra_orchestrator";
const AGENT_HTTP = "http://localhost:8000";

// Demo controls. `run` starts a LangGraph run with the current shared state.
// (The exact run trigger varies by CopilotKit version; useCoAgent exposes run()/start() in
//  recent builds. If unavailable, send a chat message instead -- the agent will run.)
export function Controls() {
  const { setState, run } = useCoAgent<BlastRadiusState>({ name: AGENT });

  // Let the LLM trip the runaway too (shows up as a tool in chat).
  useCopilotAction({
    name: "simulate_runaway",
    description: "Simulate a runaway executor agent to demonstrate the circuit breaker.",
    handler: async () => startRun(true),
  });

  async function startRun(runaway: boolean) {
    setState((s) => ({ ...s, request: "Scale the payments service", simulate_runaway: runaway }));
    try { await run?.(); } catch { /* fall back to chat-driven run */ }
  }

  async function forceReset() {
    await fetch(`${AGENT_HTTP}/demo/force-reset`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ agent_id: "executor-update-lb" }),
    });
  }

  return (
    <div className="controls">
      <button className="btn" onClick={() => startRun(false)}>▶ Scale payments (happy path)</button>
      <button className="btn btn--danger" onClick={() => startRun(true)}>💥 Simulate Runaway Agent</button>
      <button className="btn" onClick={forceReset}>↻ Force breaker reset</button>
    </div>
  );
}
