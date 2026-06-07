"use client";
import { useCallback, useRef, useState } from "react";
import { HttpAgent, type AgentSubscriber } from "@ag-ui/client";
import type { DagNode } from "./types";

// Pure AG-UI protocol client (CopilotKit's @ag-ui/client). The browser speaks AG-UI directly to
// the Python LangGraph agent at /agent: STATE_SNAPSHOT/STATE_DELTA drive the live DAG, the
// `on_interrupt` CUSTOM event surfaces the human-approval gate, and resume re-runs the same
// thread with forwardedProps.command.resume. No bespoke transport — this is the AG-UI standard.
const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_HTTP_URL ?? "http://localhost:8000/agent";

export interface AgentState {
  dag_nodes?: Record<string, DagNode>;
  edges?: [string, string][];
  breaker_open?: boolean;
  tripped_node?: string | null;
  request?: string;
  simulate_runaway?: boolean;
}

export interface InterruptInfo {
  node: string;
  plan: { label?: string; destructive?: boolean };
}

export function useBlastAgent() {
  const agentRef = useRef<HttpAgent | null>(null);
  const [state, setStateObj] = useState<AgentState | null>(null);
  const [interrupt, setInterrupt] = useState<InterruptInfo | null>(null);
  const [running, setRunning] = useState(false);

  // Read the client's authoritative merged state and accumulate nodes (snapshots are per-node).
  const applyState = useCallback(() => {
    const s = agentRef.current?.state as AgentState | undefined;
    if (!s) return;
    setStateObj((prev) => ({
      ...prev,
      ...s,
      dag_nodes: { ...(prev?.dag_nodes ?? {}), ...(s.dag_nodes ?? {}) },
      edges: s.edges && s.edges.length ? s.edges : prev?.edges,
    }));
  }, []);

  const makeSubscriber = useCallback((): AgentSubscriber => ({
    onStateSnapshotEvent: () => applyState(),
    onStateDeltaEvent: () => applyState(),
    onCustomEvent: (p: { event: { name?: string; value?: unknown } }) => {
      if (p.event?.name === "on_interrupt") {
        let v: unknown = p.event.value;
        if (typeof v === "string") { try { v = JSON.parse(v); } catch { /* keep string */ } }
        setInterrupt(v as InterruptInfo);
      }
    },
    onRunFinishedEvent: () => { applyState(); setRunning(false); },
    onRunFailed: (p: unknown) => { console.error("[AGUI] run failed", p); setRunning(false); },
  }), [applyState]);

  const startRun = useCallback(async (simulate_runaway: boolean) => {
    const agent = new HttpAgent({ url: AGENT_URL, threadId: crypto.randomUUID() });
    agentRef.current = agent;
    agent.setState({
      request: "Scale the payments service", simulate_runaway,
      dag_nodes: {}, edges: [], breaker_open: false, tripped_node: null,
    } as AgentState);
    setStateObj(null);
    setInterrupt(null);
    setRunning(true);
    try {
      await agent.runAgent({}, makeSubscriber());
    } catch (e) {
      console.error("[AGUI] runAgent error", e);
    } finally {
      setRunning(false);
    }
  }, [makeSubscriber]);

  const resume = useCallback(async (approved: boolean) => {
    const agent = agentRef.current;
    if (!agent) return;
    setInterrupt(null);
    setRunning(true);
    try {
      await agent.runAgent(
        { forwardedProps: { command: { resume: approved ? "approved" : "rejected" } } },
        makeSubscriber(),
      );
    } catch (e) {
      console.error("[AGUI] resume error", e);
    } finally {
      setRunning(false);
    }
  }, [makeSubscriber]);

  return { state, interrupt, running, startRun, resume };
}
