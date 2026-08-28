import { createClient } from "@/lib/supabase/server";

export interface ProjectSummary {
  id: string;
  name: string;
  slug: string;
}

export interface Me {
  user_id: string;
  email: string;
  workspace_id: string;
  workspace_name: string;
  projects: ProjectSummary[];
}

export type ArtifactType =
  | "source"
  | "fact"
  | "structured_data"
  | "research_note"
  | "analysis"
  | "draft"
  | "citation";

export interface Artifact {
  logical_key: string;
  name: string;
  artifact_type: ArtifactType | null;
  model: string | null;
  reusable: boolean;
  cost_usd: number;
  created_at: string;
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
  tokens_avoided: number;
  llm_calls_avoided: number;
}

export interface GraphNode {
  id: string;
  name: string;
  status: string;
  cost_usd: number;
  saved_usd: number;
  latency_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  reuse_kind: string | null;
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

export const API_URL = process.env.COMPUTELAYER_API_URL ?? "http://localhost:8000/v1";

// Server-side only: forwards the signed-in user's own Supabase access token
// as the bearer token, so the API's resolve_user_scope/resolve_current_user
// verifies it exactly as it would any other Supabase session (see
// apps/api/app/services/user_scope.py). Exported for the app/api/* route
// handlers, which proxy specific API calls the browser can't make directly
// (streaming SSE needs the token forwarded server-side; POST/cancel keep
// the API's URL out of the client bundle, same reasoning as getMe below).
export async function authorizedFetch(path: string, init?: RequestInit): Promise<Response> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    throw new Error("no active session");
  }

  return fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...init?.headers,
      Authorization: `Bearer ${session.access_token}`,
    },
    cache: "no-store",
  });
}

export async function getMe(): Promise<Me> {
  const response = await authorizedFetch("/me");
  if (!response.ok) {
    throw new Error(`GET /me failed: ${response.status}`);
  }
  return response.json();
}

export async function getProjectArtifacts(projectId: string): Promise<Artifact[]> {
  const response = await authorizedFetch(`/workspace/projects/${projectId}/artifacts`);
  if (!response.ok) {
    throw new Error(`GET project artifacts failed: ${response.status}`);
  }
  const data = await response.json();
  return data.artifacts;
}

export async function getRunSummary(runId: string): Promise<RunSummary> {
  const response = await authorizedFetch(`/workspace/runs/${runId}`);
  if (!response.ok) {
    throw new Error(`GET run summary failed: ${response.status}`);
  }
  return response.json();
}

export async function getRunGraph(runId: string): Promise<RunGraph> {
  const response = await authorizedFetch(`/workspace/runs/${runId}/graph`);
  if (!response.ok) {
    throw new Error(`GET run graph failed: ${response.status}`);
  }
  return response.json();
}
