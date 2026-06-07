"use client";
import { Handle, Position } from "@xyflow/react";
import { STATUS_COLOR, type DagNode as TNode } from "../lib/types";

// Custom React Flow node. `tripped` adds the red-pulse animation (see globals.css).
export function DagNode({ data }: { data: TNode & { tripped?: boolean } }) {
  const color = STATUS_COLOR[data.status] ?? "#3f3f46";
  return (
    <div className={`dag-node ${data.tripped ? "pulse-red" : ""}`} style={{ borderColor: color }}>
      <Handle type="target" position={Position.Left} />
      <div className="dag-node__label">
        {data.destructive && <span title="destructive">⚠️ </span>}
        {data.label}
      </div>
      <div className="dag-node__status" style={{ color }}>
        {data.status}{data.agent ? ` · ${data.agent}` : ""}
      </div>
      {data.detail && <div className="dag-node__detail">{data.detail}</div>}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
