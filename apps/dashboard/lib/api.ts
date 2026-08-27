import { DEMO_RUNS, DEMO_RUN_GRAPHS, demoMetrics } from "./fixtures";
import type { ProjectMetrics, RunGraph, RunListItem, RunSummary } from "./types";

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
