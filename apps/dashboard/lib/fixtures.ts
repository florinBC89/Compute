import type { GraphEdge, GraphNode, ProjectMetrics, RunGraph, RunListItem } from "./types";

// Demo data shaped exactly like the research-agent benchmark (spec §42-§46):
// the same NVDA equity-research workflow the benchmark itself runs, replayed
// here so the dashboard has something honest to render without a live API.

const NODE_DEFS: Array<{
  id: string;
  name: string;
  cost: number;
  inTok: number;
  outTok: number;
  latency: number;
}> = [
  { id: "company_profile", name: "company_profile", cost: 0, inTok: 0, outTok: 0, latency: 420 },
  { id: "financials", name: "financials", cost: 0, inTok: 0, outTok: 0, latency: 380 },
  { id: "competitors", name: "competitors", cost: 0, inTok: 0, outTok: 0, latency: 310 },
  { id: "news", name: "news", cost: 0, inTok: 0, outTok: 0, latency: 290 },
  { id: "overview", name: "overview", cost: 0.14, inTok: 2400, outTok: 480, latency: 3200 },
  { id: "financial_analysis", name: "financial_analysis", cost: 0.31, inTok: 5200, outTok: 820, latency: 5100 },
  { id: "competitive_analysis", name: "competitive_analysis", cost: 0.22, inTok: 3600, outTok: 610, latency: 4200 },
  { id: "news_analysis", name: "news_analysis", cost: 0.18, inTok: 3100, outTok: 540, latency: 3600 },
  { id: "valuation", name: "valuation", cost: 0.27, inTok: 4400, outTok: 700, latency: 4700 },
  { id: "final_report", name: "final_report", cost: 0.35, inTok: 6800, outTok: 1100, latency: 6100 },
];

const EDGE_DEFS: GraphEdge[] = [
  { from: "company_profile", to: "overview", key: "company_profile" },
  { from: "financials", to: "financial_analysis", key: "financials" },
  { from: "competitors", to: "competitive_analysis", key: "competitors" },
  { from: "news", to: "news_analysis", key: "news" },
  { from: "financial_analysis", to: "valuation", key: "financial_analysis" },
  { from: "competitive_analysis", to: "valuation", key: "competitive_analysis" },
  { from: "news_analysis", to: "valuation", key: "news_analysis" },
  { from: "overview", to: "final_report", key: "overview" },
  { from: "financial_analysis", to: "final_report", key: "financial_analysis" },
  { from: "competitive_analysis", to: "final_report", key: "competitive_analysis" },
  { from: "news_analysis", to: "final_report", key: "news_analysis" },
  { from: "valuation", to: "final_report", key: "valuation" },
];

function buildGraph(statusByNode: Record<string, GraphNode["status"]>): RunGraph {
  const nodes: GraphNode[] = NODE_DEFS.map((def) => {
    const status = statusByNode[def.id] ?? "HIT";
    const isReused = status === "HIT";
    return {
      id: def.id,
      name: def.name,
      status,
      cost_usd: isReused ? 0 : def.cost,
      saved_usd: isReused ? def.cost : 0,
      latency_ms: isReused ? Math.round(def.latency * 0.02) : def.latency,
      input_tokens: isReused ? 0 : def.inTok,
      output_tokens: isReused ? 0 : def.outTok,
    };
  });
  return { nodes, edges: EDGE_DEFS };
}

// Scenario A — cold run: everything MISS.
export const DEMO_GRAPH_COLD: RunGraph = buildGraph(
  Object.fromEntries(NODE_DEFS.map((d) => [d.id, "MISS" as const]))
);

// Scenario C — news update: news branch + everything downstream of it reruns.
export const DEMO_GRAPH_NEWS_UPDATE: RunGraph = buildGraph({
  company_profile: "HIT",
  financials: "HIT",
  competitors: "HIT",
  news: "STALE",
  overview: "HIT",
  financial_analysis: "HIT",
  competitive_analysis: "HIT",
  news_analysis: "STALE",
  valuation: "STALE",
  final_report: "STALE",
});

// Scenario E — upstream execution changed but output hash didn't: financials
// re-executes but every downstream computation still HITs (README's
// load-bearing scenario).
export const DEMO_GRAPH_UPSTREAM_CHURN: RunGraph = buildGraph({
  company_profile: "HIT",
  financials: "STALE",
  competitors: "HIT",
  news: "HIT",
  overview: "HIT",
  financial_analysis: "HIT",
  competitive_analysis: "HIT",
  news_analysis: "HIT",
  valuation: "HIT",
  final_report: "HIT",
});

function summarize(graph: RunGraph) {
  const counts = { HIT: 0, MISS: 0, STALE: 0, FORCED: 0, FAILED: 0 };
  let cost = 0;
  let saved = 0;
  let inTok = 0;
  let outTok = 0;
  for (const node of graph.nodes) {
    counts[node.status] += 1;
    cost += node.cost_usd;
    saved += node.saved_usd;
    inTok += node.input_tokens;
    outTok += node.output_tokens;
  }
  return { counts, cost, saved, inTok, outTok };
}

function runListItem(
  id: string,
  hoursAgo: number,
  graph: RunGraph,
  status: string
): RunListItem {
  const { counts, cost, saved, inTok, outTok } = summarize(graph);
  const started = new Date(Date.now() - hoursAgo * 3600_000);
  const finished = new Date(started.getTime() + 22_000);
  return {
    id,
    status,
    external_run_id: `nvda-research-${id.slice(0, 8)}`,
    computations: graph.nodes.length,
    hits: counts.HIT,
    misses: counts.MISS,
    stale: counts.STALE,
    forced: counts.FORCED,
    total_cost_usd: Number(cost.toFixed(4)),
    saved_usd: Number(saved.toFixed(4)),
    input_tokens: inTok,
    output_tokens: outTok,
    started_at: started.toISOString(),
    finished_at: finished.toISOString(),
  };
}

export const DEMO_RUN_GRAPHS: Record<string, RunGraph> = {
  "run-a1b2c3d4-cold": DEMO_GRAPH_COLD,
  "run-e5f6a7b8-news1": DEMO_GRAPH_NEWS_UPDATE,
  "run-c9d0e1f2-news2": DEMO_GRAPH_NEWS_UPDATE,
  "run-b3a4c5d6-churn1": DEMO_GRAPH_UPSTREAM_CHURN,
  "run-f7e8d9c0-churn2": DEMO_GRAPH_UPSTREAM_CHURN,
  "run-11223344-identical": buildGraph(
    Object.fromEntries(NODE_DEFS.map((d) => [d.id, "HIT" as const]))
  ),
};

export const DEMO_RUNS: RunListItem[] = [
  runListItem("run-11223344-identical", 1, DEMO_RUN_GRAPHS["run-11223344-identical"], "SUCCEEDED"),
  runListItem("run-f7e8d9c0-churn2", 5, DEMO_RUN_GRAPHS["run-f7e8d9c0-churn2"], "SUCCEEDED"),
  runListItem("run-b3a4c5d6-churn1", 9, DEMO_RUN_GRAPHS["run-b3a4c5d6-churn1"], "SUCCEEDED"),
  runListItem("run-c9d0e1f2-news2", 27, DEMO_RUN_GRAPHS["run-c9d0e1f2-news2"], "SUCCEEDED"),
  runListItem("run-e5f6a7b8-news1", 33, DEMO_RUN_GRAPHS["run-e5f6a7b8-news1"], "SUCCEEDED"),
  runListItem("run-a1b2c3d4-cold", 48, DEMO_RUN_GRAPHS["run-a1b2c3d4-cold"], "SUCCEEDED"),
];

export function demoMetrics(): ProjectMetrics {
  const totalComputations = DEMO_RUNS.reduce((sum, r) => sum + r.computations, 0);
  const totalHits = DEMO_RUNS.reduce((sum, r) => sum + r.hits, 0);
  const cost = DEMO_RUNS.reduce((sum, r) => sum + r.total_cost_usd, 0);
  const saved = DEMO_RUNS.reduce((sum, r) => sum + r.saved_usd, 0);
  const inTok = DEMO_RUNS.reduce((sum, r) => sum + r.input_tokens, 0);
  const outTok = DEMO_RUNS.reduce((sum, r) => sum + r.output_tokens, 0);
  const avoidedTokensPerHit = 3400; // rough average of the LLM-step token costs above
  return {
    period: "7d",
    runs: DEMO_RUNS.length,
    computations: totalComputations,
    hit_rate: totalHits / totalComputations,
    cost_usd: Number(cost.toFixed(4)),
    saved_usd: Number(saved.toFixed(4)),
    tokens_consumed: inTok + outTok,
    tokens_avoided: totalHits * avoidedTokensPerHit,
    llm_calls_avoided: Math.round(totalHits * 0.6),
  };
}
