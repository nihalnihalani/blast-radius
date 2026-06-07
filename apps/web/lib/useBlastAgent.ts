"use client";
import { useCallback, useRef, useState } from "react";
import { HttpAgent, type AgentSubscriber } from "@ag-ui/client";
import type { DagNode } from "./types";

// Pure AG-UI protocol client (CopilotKit's @ag-ui/client). The browser speaks AG-UI directly to
// the Python LangGraph agent at /agent:
//   • STATE_SNAPSHOT / STATE_DELTA  -> the live DAG
//   • on_interrupt CUSTOM event     -> human-approval gate (destructive step) / "resume with safe
//                                       fallback" recovery gate (value.recovery)
//   • CIRCUIT_BREAKER_TRIPPED CUSTOM event -> the red-pulse (event-driven, with state as backup)
//   • resume = runAgent({forwardedProps:{command:{resume}}}) on the same threadId
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
  recovery?: boolean;
  plan: { label?: string; destructive?: boolean; action?: string };
}

export function useBlastAgent() {
  const agentRef = useRef<HttpAgent | null>(null);
  const [state, setStateObj] = useState<AgentState | null>(null);
  const [interrupt, setInterrupt] = useState<InterruptInfo | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Set by the CIRCUIT_BREAKER_TRIPPED CustomEvent — drives the pulse immediately (event-driven),
  // independent of the state snapshot. Cleared when the run finishes.
  const [breakerEventNode, setBreakerEventNode] = useState<string | null>(null);

  const applyState = useCallback(() => {
    const s = agentRef.current?.state as AgentState | undefined;
    if (!s) return;
    setStateObj((prev) => ({
      ...prev,
      ...s,
      dag_nodes: { ...(prev?.dag_nodes ?? {}), ...(s.dag_nodes ?? {}) },
      edges: s.edges && s.edges.length ? s.edges : prev?.edges,
    }));
    if (s.breaker_open === false) setBreakerEventNode(null);   // breaker recovered -> stop the pulse
  }, []);

  const makeSubscriber = useCallback((): AgentSubscriber => ({
    onStateSnapshotEvent: () => applyState(),
    onStateDeltaEvent: () => applyState(),
    onCustomEvent: (p: { event: { name?: string; value?: unknown } }) => {
      const { name, value } = p.event ?? {};
      if (name === "on_interrupt") {
        let v: unknown = value;
        if (typeof v === "string") { try { v = JSON.parse(v); } catch { /* keep */ } }
        setInterrupt(v as InterruptInfo);
      } else if (name === "CIRCUIT_BREAKER_TRIPPED") {
        const v = (typeof value === "string" ? safeParse(value) : value) as { node_id?: string };
        setBreakerEventNode(v?.node_id ?? null);
      }
    },
    onRunFinishedEvent: () => { applyState(); setRunning(false); },
    onRunFailed: (p: { error?: unknown }) => {
      console.error("[AGUI] run failed", p);
      setError(String((p && p.error) ?? "agent run failed"));
      setRunning(false);
    },
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
    setError(null);
    setBreakerEventNode(null);
    setRunning(true);
    try {
      await agent.runAgent({}, makeSubscriber());
    } catch (e) {
      console.error("[AGUI] runAgent error", e);
      setError(e instanceof Error ? e.message : "could not reach the agent backend");
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
      setError(e instanceof Error ? e.message : "resume failed");
    } finally {
      setRunning(false);
    }
  }, [makeSubscriber]);

  return { state, interrupt, running, error, breakerEventNode, startRun, resume };
}

function safeParse(s: string): unknown {
  try { return JSON.parse(s); } catch { return null; }
}
