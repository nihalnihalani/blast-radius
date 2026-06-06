"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { DagCanvas } from "./DagCanvas";
import type { DagDoc } from "../lib/types";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export function Cockpit() {
  const [dag, setDag] = useState<DagDoc | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  // Stream the live DAG document for the active run.
  useEffect(() => {
    if (!runId) return;
    const es = new EventSource(`${BACKEND}/events/dag/${runId}`);
    esRef.current = es;
    es.onmessage = (e) => {
      try { setDag(JSON.parse(e.data)); } catch { /* ignore keepalives */ }
    };
    es.addEventListener("end", () => es.close());
    es.onerror = () => es.close();
    return () => es.close();
  }, [runId]);

  const startRun = useCallback(async (simulate_runaway: boolean) => {
    setBusy(true);
    setDag(null);
    esRef.current?.close();
    const res = await fetch(`${BACKEND}/demo/run`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ simulate_runaway }),
    });
    const { run_id } = await res.json();
    setRunId(run_id);
    setBusy(false);
  }, []);

  const resume = useCallback(async (approved: boolean) => {
    if (!runId) return;
    await fetch(`${BACKEND}/demo/resume`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ run_id: runId, approved }),
    });
  }, [runId]);

  const forceReset = useCallback(async () => {
    await fetch(`${BACKEND}/demo/force-reset`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ agent_id: "executor-update-lb" }),
    });
  }, []);

  const nodes = dag?.nodes ?? {};
  const edges = dag?.edges ?? [];
  const awaiting = Object.entries(nodes).find(([, n]) => n.status === "awaiting-approval");

  return (
    <main className="cockpit">
      <header className="cockpit__header">
        <span className="cockpit__brand">💥 BLAST-RADIUS</span>
        <span className="cockpit__sub">multi-agent infra-change cockpit</span>
        <div className="controls">
          <button className="btn" disabled={busy} onClick={() => startRun(false)}>▶ Scale payments (happy path)</button>
          <button className="btn btn--danger" disabled={busy} onClick={() => startRun(true)}>💥 Simulate Runaway Agent</button>
          <button className="btn" onClick={forceReset}>↻ Force breaker reset</button>
        </div>
      </header>

      {dag?.breaker_open && (
        <div className="breaker-banner pulse-red">
          ⚠️ CIRCUIT BREAKER OPEN — runaway agent <b>{dag.tripped_node}</b> killed · recovering from dead-letter queue…
        </div>
      )}

      <DagCanvas nodes={nodes} edges={edges} trippedNode={dag?.tripped_node} />

      {!dag && (
        <div className="hint">Click <b>Scale payments</b> to dispatch the agent team, or <b>Simulate Runaway Agent</b> to watch the circuit breaker trip.</div>
      )}

      {awaiting && (
        <div className="approval-overlay">
          <div className="approval">
            <div className="approval__title">⚠️ Destructive step needs approval</div>
            <div className="approval__body">
              <b>{awaiting[1].label}</b> ({awaiting[0]}) will modify production infrastructure. Approve?
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
