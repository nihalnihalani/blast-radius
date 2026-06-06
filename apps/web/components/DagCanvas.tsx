"use client";
import { useMemo } from "react";
import { ReactFlow, Background, Controls as RFControls, type Node, type Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { DagNode } from "./DagNode";
import type { DagNode as TNode } from "../lib/types";

const nodeTypes = { dagNode: DagNode };

// Deterministic left-to-right layout by topological depth derived from edges.
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
    pos[id] = { x: d * 260, y: 80 + row * 130 };
  });
  return pos;
}

export function DagCanvas({
  nodes, edges, trippedNode,
}: {
  nodes: Record<string, TNode>;
  edges: [string, string][];
  trippedNode?: string | null;
}) {
  const { rfNodes, rfEdges } = useMemo(() => {
    const ids = Object.keys(nodes);
    const pos = layout(ids, edges);
    const rfNodes: Node[] = ids.map((id) => ({
      id, type: "dagNode", position: pos[id],
      data: { ...nodes[id], tripped: trippedNode === id },
    }));
    const rfEdges: Edge[] = edges.map(([a, b]) => ({
      id: `${a}-${b}`, source: a, target: b,
      animated: nodes[a]?.status === "running" || nodes[a]?.status === "done",
    }));
    return { rfNodes, rfEdges };
  }, [nodes, edges, trippedNode]);

  return (
    <div className="dag-canvas">
      <ReactFlow nodes={rfNodes} edges={rfEdges} nodeTypes={nodeTypes} fitView
        proOptions={{ hideAttribution: true }} nodesDraggable={false} nodesConnectable={false}>
        <Background />
        <RFControls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
