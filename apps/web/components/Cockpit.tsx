"use client";
import { DagCanvas } from "./DagCanvas";
import { useBlastAgent } from "../lib/useBlastAgent";

export function Cockpit() {
  const { state, interrupt, running, error, breakerEventNode, startRun, resume } = useBlastAgent();

  const nodes = state?.dag_nodes ?? {};
  const edges = (state?.edges ?? []) as [string, string][];
  const nodeCount = Object.keys(nodes).length;
  // Pulse driven by the CIRCUIT_BREAKER_TRIPPED CustomEvent OR the streamed breaker state.
  const trippedNode = breakerEventNode ?? state?.tripped_node ?? null;
  const breakerOpen = state?.breaker_open || !!breakerEventNode;
  const isRecovery = !!interrupt?.recovery;

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

      {error && (
        <div className="error-banner">⚠️ {error} — is the agent backend running on :8000?</div>
      )}

      {breakerOpen && (
        <div className="breaker-banner pulse-red">
          ⚠️ CIRCUIT BREAKER OPEN — runaway agent <b>{trippedNode}</b> killed · awaiting safe-fallback recovery…
        </div>
      )}

      <DagCanvas nodes={nodes} edges={edges} trippedNode={trippedNode} />

      {nodeCount === 0 && !running && !error && (
        <div className="hint">Click <b>Scale payments</b> to dispatch the agent team, or <b>Simulate Runaway Agent</b> to watch the circuit breaker trip.</div>
      )}

      {interrupt && (
        <div className="approval-overlay">
          <div className="approval" style={isRecovery ? { borderColor: "#22c55e" } : undefined}>
            <div className="approval__title">
              {isRecovery ? "🛟 Circuit breaker tripped — recover?" : "⚠️ Destructive step needs approval"}
            </div>
            <div className="approval__body">
              {isRecovery ? (
                <>Agent <b>{interrupt.node}</b> went runaway and was killed by the Redis circuit breaker.
                  Spawn a recovery agent from the dead-letter queue to finish it on a safe path?</>
              ) : (
                <><b>{interrupt.plan?.label ?? interrupt.node}</b> ({interrupt.node}) will modify production
                  infrastructure. This pause is a graph-enforced LangGraph <code>interrupt()</code> over AG-UI. Approve?</>
              )}
            </div>
            <div className="approval__actions">
              <button className="btn btn--approve" onClick={() => resume(true)}>
                {isRecovery ? "Resume with safe fallback" : "Approve"}
              </button>
              {!isRecovery && <button className="btn btn--reject" onClick={() => resume(false)}>Reject</button>}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
