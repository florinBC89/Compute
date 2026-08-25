export type CacheStatus = "HIT" | "MISS" | "STALE" | "FORCED" | "FAILED";

export interface RunListItem {
  id: string;
  status: string;
  external_run_id: string | null;
  computations: number;
  hits: number;
  misses: number;
  stale: number;
  forced: number;
  total_cost_usd: number;
  saved_usd: number;
  input_tokens: number;
  output_tokens: number;
  started_at: string;
  finished_at: string | null;
}

export interface RunSummary {
  id: string;
  status: string;
  computations: number;
  hits: number;
  misses: number;
  stale: number;
  forced: number;
  total_cost_usd: number;
  saved_usd: number;
  input_tokens: number;
  output_tokens: number;
}

export interface GraphNode {
  id: string;
  name: string;
  status: CacheStatus;
  cost_usd: number;
  saved_usd: number;
  latency_ms: number | null;
  input_tokens: number;
  output_tokens: number;
}

export interface GraphEdge {
  from: string;
  to: string;
  key: string;
}

export interface RunGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ProjectMetrics {
  period: string;
  runs: number;
  computations: number;
  hit_rate: number;
  cost_usd: number;
  saved_usd: number;
  tokens_consumed: number;
  tokens_avoided: number;
  llm_calls_avoided: number;
}
