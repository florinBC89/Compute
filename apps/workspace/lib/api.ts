import { createClient } from "@/lib/supabase/server";

export interface ProjectSummary {
  id: string;
  name: string;
  slug: string;
  //: Chat/Build sidebar tab this conversation belongs to (V0.3) -- set
  //: once at creation, see components/Sidebar.tsx's per-mode filtering.
  kind: "chat" | "build";
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
  model: string | null;
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

export interface PreviewItem {
  name: string;
  logical_key: string;
  decision: "REUSE" | "RECOMPUTE";
  reason: string;
  artifact_type: ArtifactType | null;
  current_model: string | null;
  cost_if_recomputed_usd: number;
}

export interface ModelSwitchPreview {
  target_model: string;
  items: PreviewItem[];
  reusable_count: number;
  recompute_count: number;
  estimated_incremental_cost_usd: number;
}

// V0.3 chat turns: a turn IS a Job (see apps/api/app/services/jobs.py) --
// no separate message type. Plain interfaces, safe to import from client
// components (unlike the authorizedFetch-based functions below, which need
// the server-only Supabase client).
export type JobStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED";

export interface JobDetail {
  id: string;
  status: JobStatus;
  task_text: string;
  answer_text: string | null;
  current_step: string | null;
  error_message: string | null;
  spent_usd: number;
  cost_cap_usd: number;
  run_id: string | null;
  project_id: string;
  //: The conversation's current title (V0.3) -- a fallback until the
  //: PROJECT_TITLED SSE event (see ChatThread.tsx) replaces it live.
  project_name: string;
  //: "Lazy" mode: this turn's system prompt was appended with a
  //: code-minimalism ruleset (apps/api's app.agent.chat.LAZY_MODE_SYSTEM_SUFFIX).
  //: Set once at creation, same lifecycle as model_preference.
  lazy_mode: boolean;
}

export interface JobEvent {
  id: number;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

// GET /v1/jobs/{job_id}/stream (V0.3 chat streaming): each `data:` line is
// one of these, discriminated on `type`. Replaces the old JobEvent-based
// SSE (/jobs/{id}/events) for chat turns -- `delta` chunks accumulate into
// the streamed answer, `title` mirrors the old PROJECT_TITLED event, and
// `done` carries the final JobDetail directly (success or failure), so no
// extra GET /jobs/{id} fetch is needed once it arrives.
export type ChatStreamEnvelope =
  | { type: "delta"; text: string }
  | { type: "title"; name: string }
  | { type: "done"; job: JobDetail };

// Ethical (Agent OS V0.4 slice, "give Ethical a name and a face"): a persistent
// named identity linked to one Project, whose "Work" is that Project's
// existing Jobs (see apps/api/app/services/ethicals.py) -- no separate
// pipeline or storage of its own yet.
export type WorkReuseLabel = "reused" | "partially_reused" | "fresh";

export interface EthicalSummary {
  id: string;
  name: string;
  goal: string | null;
  status: "active" | "archived";
  project_id: string;
  project_name: string;
  created_at: string;
}

export interface EthicalWorkItem {
  job_id: string;
  task_text: string;
  status: JobStatus;
  //: null for a job with no run_id yet (queued/running) -- nothing to
  //: classify as reused or fresh until a run has actually executed.
  reuse_label: WorkReuseLabel | null;
  cost_usd: number;
  saved_usd: number;
  created_at: string;
}

export interface EthicalDetail extends EthicalSummary {
  work: EthicalWorkItem[];
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

export async function getProjectJobs(projectId: string): Promise<JobDetail[]> {
  const response = await authorizedFetch(`/workspace/projects/${projectId}/jobs`);
  if (!response.ok) {
    throw new Error(`GET project jobs failed: ${response.status}`);
  }
  const data = await response.json();
  return data.jobs;
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

export async function getEthicals(): Promise<EthicalSummary[]> {
  const response = await authorizedFetch("/ethicals");
  if (!response.ok) {
    throw new Error(`GET ethicals failed: ${response.status}`);
  }
  const data = await response.json();
  return data.ethicals;
}

export async function getEthical(ethicalId: string): Promise<EthicalDetail> {
  const response = await authorizedFetch(`/ethicals/${ethicalId}`);
  if (!response.ok) {
    throw new Error(`GET ethical failed: ${response.status}`);
  }
  return response.json();
}
