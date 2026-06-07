"use client";
import { DagCanvas } from "./DagCanvas";
import { useBlastAgent } from "../lib/useBlastAgent";

export function Cockpit() {
  const { state, interrupt, running, startRun, resume } = useBlastAgent();

  const nodes = state?.dag_nodes ?? {};
  const edges = (state?.edges ?? []) as [string, string][];
  const nodeCount = Object.keys(nodes).length;

  return (
    <main className="cockpit">
      <header className="cockpit__header">
        <span className="cockpit__brand">💥 BLAST-RADIUS</span>
        <span className="cockpit__sub">multi-agent infra-change cockpit · AG-UI</span>
        <span className="cockpit__debug">{running ? "● running" : "○ idle"} · {nodeCount} nodes</span>
        <div className="controls">
          <button className="btn" disabled={running} onClick={() => startRun(false)}>▶ Scale payments (happy path)</button>
          <button className="btn btn--danger" disabled={running} onClick={() => startRun(true)}>💥 Simulate Runaway Agent</button>
        </div>
      </header>

      {state?.breaker_open && (
        <div className="breaker-banner pulse-red">
          ⚠️ CIRCUIT BREAKER OPEN — runaway agent <b>{state.tripped_node}</b> killed · recovering from dead-letter queue…
        </div>
      )}

      <DagCanvas nodes={nodes} edges={edges} trippedNode={state?.tripped_node} />

      {nodeCount === 0 && !running && (
        <div className="hint">Click <b>Scale payments</b> to dispatch the agent team, or <b>Simulate Runaway Agent</b> to watch the circuit breaker trip.</div>
      )}

      {interrupt && (
        <div className="approval-overlay">
          <div className="approval">
            <div className="approval__title">⚠️ Destructive step needs approval</div>
            <div className="approval__body">
              <b>{interrupt.plan?.label ?? interrupt.node}</b> ({interrupt.node}) will modify production
              infrastructure. This pause is a graph-enforced LangGraph <code>interrupt()</code> over AG-UI. Approve?
            </div>
            <div className="approval__actions">
              <button className="btn btn--approve" onClick={() => resume(true)}>Approve</button>
              <button className="btn btn--reject" onClick={() => resume(false)}>Reject</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
