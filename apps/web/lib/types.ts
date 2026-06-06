export type NodeStatus =
  | "pending" | "running" | "validated" | "approved" | "blocked" | "done" | "failed";

export interface DagNode {
  label: string;
  status: NodeStatus;
  agent: string | null;
  destructive: boolean;
}

export interface BlastRadiusState {
  run_id?: string;
  request?: string;
  dag_nodes?: Record<string, DagNode>;
  edges?: [string, string][];
  breaker_open?: boolean;
  tripped_node?: string | null;
  simulate_runaway?: boolean;
}

export const STATUS_COLOR: Record<NodeStatus, string> = {
  pending: "#3f3f46",
  running: "#eab308",
  validated: "#0ea5e9",
  approved: "#0ea5e9",
  blocked: "#a1a1aa",
  done: "#22c55e",
  failed: "#ef4444",
};
