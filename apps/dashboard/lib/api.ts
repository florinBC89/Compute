import {
  DEMO_RUNS,
  DEMO_RUN_GRAPHS,
  demoArtifacts,
  demoMetrics,
  demoModelSwitchPreview,
  demoUsage,
} from "./fixtures";
import type {
  ArtifactListItem,
  ModelSwitchPreview,
  ProjectMetrics,
  RunGraph,
  RunListItem,
  RunSummary,
  UsageBreakdownItem,
} from "./types";

// Deliberately not NEXT_PUBLIC_-prefixed: every call site is a Server
// Component (see `export const dynamic = "force-dynamic"` on each page), so
// these are read from process.env at request time on the server, never
// bundled for the browser. That means they're ordinary runtime environment
// variables -- no Docker build-arg plumbing required to change them.
const API_URL = process.env.COMPUTELAYER_API_URL;
const API_KEY = process.env.COMPUTELAYER_API_KEY;
const PROJECT = process.env.COMPUTELAYER_PROJECT ?? "research-agent";

// True whenever no live API is configured -- lets the dashboard render a
// realistic preview (shaped exactly like the research-agent benchmark) with
// no Postgres/Redis running, and makes that fact visible in the UI rather
// than silently faking a connection.
export const isDemoMode = !API_URL;

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`ComputeLayer API ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

async function requestPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`ComputeLayer API ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export async function listRuns(limit = 50): Promise<RunListItem[]> {
  if (isDemoMode) return DEMO_RUNS.slice(0, limit);
  const data = await request<{ runs: RunListItem[] }>(
    `/runs?limit=${limit}`
  );
  return data.runs;
}

export async function getRun(id: string): Promise<RunSummary> {
  if (isDemoMode) {
    const run = DEMO_RUNS.find((r) => r.id === id) ?? DEMO_RUNS[0];
    return run;
  }
  return request<RunSummary>(`/runs/${id}`);
}

export async function getRunGraph(id: string): Promise<RunGraph> {
  if (isDemoMode) {
    return DEMO_RUN_GRAPHS[id] ?? Object.values(DEMO_RUN_GRAPHS)[0];
  }
  return request<RunGraph>(`/runs/${id}/graph`);
}

export async function getProjectMetrics(period = "30d"): Promise<ProjectMetrics> {
  if (isDemoMode) return demoMetrics();
  return request<ProjectMetrics>(
    `/projects/${PROJECT}/metrics?period=${period}`
  );
}

export async function listArtifacts(artifactType?: string): Promise<ArtifactListItem[]> {
  if (isDemoMode) {
    const all = demoArtifacts();
    return artifactType ? all.filter((a) => a.artifact_type === artifactType) : all;
  }
  const query = artifactType ? `?artifact_type=${encodeURIComponent(artifactType)}` : "";
  const data = await request<{ artifacts: ArtifactListItem[] }>(
    `/projects/${PROJECT}/artifacts${query}`
  );
  return data.artifacts;
}

export async function getUsage(period = "30d"): Promise<UsageBreakdownItem[]> {
  if (isDemoMode) return demoUsage();
  const data = await request<{ period: string; items: UsageBreakdownItem[] }>(
    `/projects/${PROJECT}/usage?period=${period}`
  );
  return data.items;
}

// V0.2 (Phase 8): what would carry over if this run's work were repeated on
// a different model, before actually executing anything -- the developer
// dashboard's counterpart to the workspace app's "Switch model" screen,
// backed by the same POST /runs/{id}/preview-model-switch endpoint.
export async function previewModelSwitch(
  runId: string,
  targetModel: string
): Promise<ModelSwitchPreview> {
  if (isDemoMode) return demoModelSwitchPreview(targetModel);
  return requestPost<ModelSwitchPreview>(`/runs/${runId}/preview-model-switch`, {
    target_model: targetModel,
  });
}

// The "How Accurate thinks" example on Overview: a real run that reused some
// computations and recomputed others, so the concept is shown with an actual
// graph rather than a mockup. Returns null (never a fabricated stand-in) when
// no such run exists yet.
export async function getPartialReuseExample(): Promise<{
  runId: string;
  graph: RunGraph;
} | null> {
  if (isDemoMode) {
    return { runId: "run-e5f6a7b8-news1", graph: DEMO_RUN_GRAPHS["run-e5f6a7b8-news1"] };
  }
  const runs = await listRuns(50);
  const example = runs.find((r) => r.hits > 0 && r.stale > 0);
  if (!example) return null;
  return { runId: example.id, graph: await getRunGraph(example.id) };
}
