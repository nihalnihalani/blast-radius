export type NodeStatus =
  | "pending" | "running" | "validated" | "awaiting-approval"
  | "approved" | "blocked" | "done" | "failed";

export interface DagNode {
  label: string;
  status: NodeStatus;
  agent: string | null;
  destructive: boolean;
  detail?: string;
  validation?: string;
}

/** The DAG document streamed from the backend (RedisJSON). */
export interface DagDoc {
  run_id?: string;
  request?: string;
  nodes: Record<string, DagNode>;
  edges: [string, string][];
  breaker_open?: boolean;
  tripped_node?: string | null;
  _done?: boolean;
}

export const STATUS_COLOR: Record<NodeStatus, string> = {
  pending: "#3f3f46",
  running: "#eab308",
  validated: "#0ea5e9",
  "awaiting-approval": "#f59e0b",
  approved: "#0ea5e9",
  blocked: "#a1a1aa",
  done: "#22c55e",
  failed: "#ef4444",
};
