"use client";
import { useMemo } from "react";
import { ReactFlow, Background, Controls as RFControls, type Node, type Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCoAgent } from "@copilotkit/react-core";
import { DagNode } from "./DagNode";
import type { BlastRadiusState } from "../lib/types";

const AGENT = process.env.NEXT_PUBLIC_AGENT_NAME ?? "infra_orchestrator";
const nodeTypes = { dagNode: DagNode };

// Deterministic left-to-right layout by topological order derived from edges.
function layout(ids: string[], edges: [string, string][]): Record<string, { x: number; y: number }> {
  const depth: Record<string, number> = {};
  ids.forEach((id) => (depth[id] = 0));
  for (let i = 0; i < ids.length; i++)
    for (const [a, b] of edges) depth[b] = Math.max(depth[b] ?? 0, (depth[a] ?? 0) + 1);
  const perCol: Record<number, number> = {};
  const pos: Record<string, { x: number; y: number }> = {};
  ids.forEach((id) => {
    const d = depth[id] ?? 0;
    const row = (perCol[d] = (perCol[d] ?? 0) + 1) - 1;
    pos[id] = { x: d * 240, y: row * 120 };
  });
  return pos;
}

export function BlastRadiusDAG() {
  // useCoAgent (v1) gives bidirectional shared state. v2 equivalent: useAgent({agentId}) from
  // "@copilotkit/react-core/v2" -> agent.state. The backend streams STATE_DELTA as nodes update.
  const { state } = useCoAgent<BlastRadiusState>({
    name: AGENT,
    initialState: { dag_nodes: {}, edges: [], breaker_open: false, tripped_node: null },
  });

  const { nodes, edges } = useMemo(() => {
    const dn = state?.dag_nodes ?? {};
    const ed = (state?.edges ?? []) as [string, string][];
    const ids = Object.keys(dn);
    const pos = layout(ids, ed);
    const nodes: Node[] = ids.map((id) => ({
      id,
      type: "dagNode",
      position: pos[id],
      data: { ...dn[id], tripped: state?.tripped_node === id },
    }));
    const edges: Edge[] = ed.map(([a, b]) => ({
      id: `${a}-${b}`, source: a, target: b, animated: dn[a]?.status === "running",
    }));
    return { nodes, edges };
  }, [state]);

  return (
    <div className="dag-canvas">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }}>
        <Background />
        <RFControls />
      </ReactFlow>
    </div>
  );
}
