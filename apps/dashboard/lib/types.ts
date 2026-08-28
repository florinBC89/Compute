export type CacheStatus = "HIT" | "MISS" | "STALE" | "FORCED" | "FAILED";

// "CROSS_MODEL" when a HIT reused a portable artifact across a model
// switch (V0.2); undefined/null for an ordinary HIT or any other status.
export type ReuseKind = "CROSS_MODEL";

export type ArtifactType =
  | "source"
  | "fact"
  | "structured_data"
  | "research_note"
  | "analysis"
  | "draft"
  | "citation";

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
  tokens_avoided: number;
  llm_calls_avoided: number;
}

export interface RunListItem extends RunSummary {
  external_run_id: string | null;
  started_at: string;
  finished_at: string | null;
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
  previous_cost_usd: number | null;
  previous_input_tokens: number | null;
  previous_output_tokens: number | null;
  previous_latency_ms: number | null;
  reuse_kind: ReuseKind | null;
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
  cross_model_saved_usd: number;
  cross_model_tokens_avoided: number;
}

export interface ArtifactListItem {
  logical_key: string;
  name: string;
  artifact_type: ArtifactType | null;
  model: string | null;
  reusable: boolean;
  cost_usd: number;
  created_at: string;
}

export interface UsageBreakdownItem {
  model: string | null;
  name: string;
  computations: number;
  cost_usd: number;
  input_tokens: number;
  output_tokens: number;
}
