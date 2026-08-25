import { DEMO_RUNS, DEMO_RUN_GRAPHS, demoMetrics } from "./fixtures";
import type { ProjectMetrics, RunGraph, RunListItem, RunSummary } from "./types";

const API_URL = process.env.NEXT_PUBLIC_COMPUTELAYER_API_URL;
const API_KEY = process.env.NEXT_PUBLIC_COMPUTELAYER_API_KEY;
const PROJECT = process.env.NEXT_PUBLIC_COMPUTELAYER_PROJECT ?? "research-agent";

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
