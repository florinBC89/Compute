import type {
  ArtifactListItem,
  ArtifactType,
  GraphEdge,
  GraphNode,
  ModelSwitchPreview,
  ProjectMetrics,
  RunGraph,
  RunListItem,
  UsageBreakdownItem,
} from "./types";

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
  isLlmCall: boolean;
}> = [
  { id: "company_profile", name: "company_profile", cost: 0, inTok: 0, outTok: 0, latency: 420, isLlmCall: false },
  { id: "financials", name: "financials", cost: 0, inTok: 0, outTok: 0, latency: 380, isLlmCall: false },
  { id: "competitors", name: "competitors", cost: 0, inTok: 0, outTok: 0, latency: 310, isLlmCall: false },
  { id: "news", name: "news", cost: 0, inTok: 0, outTok: 0, latency: 290, isLlmCall: false },
  { id: "overview", name: "overview", cost: 0.14, inTok: 2400, outTok: 480, latency: 3200, isLlmCall: true },
  { id: "financial_analysis", name: "financial_analysis", cost: 0.31, inTok: 5200, outTok: 820, latency: 5100, isLlmCall: true },
  { id: "competitive_analysis", name: "competitive_analysis", cost: 0.22, inTok: 3600, outTok: 610, latency: 4200, isLlmCall: true },
  { id: "news_analysis", name: "news_analysis", cost: 0.18, inTok: 3100, outTok: 540, latency: 3600, isLlmCall: true },
  { id: "valuation", name: "valuation", cost: 0.27, inTok: 4400, outTok: 700, latency: 4700, isLlmCall: true },
  { id: "final_report", name: "final_report", cost: 0.35, inTok: 6800, outTok: 1100, latency: 6100, isLlmCall: true },
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
      previous_cost_usd: isReused ? def.cost : null,
      previous_input_tokens: isReused ? def.inTok : null,
      previous_output_tokens: isReused ? def.outTok : null,
      previous_latency_ms: isReused ? def.latency : null,
      // No demo scenario models a real cross-model reuse -- following the
      // same rule getPartialReuseExample() documents below: don't fabricate
      // one just to populate a field.
      reuse_kind: null,
      // This benchmark-derived demo predates the human-workspace pipeline
      // (V0.2 Phase 4+) that actually records a model per step -- same
      // "don't fabricate" rule as reuse_kind above.
      model: null,
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

const LLM_NODE_IDS = new Set(NODE_DEFS.filter((d) => d.isLlmCall).map((d) => d.id));

function summarize(graph: RunGraph) {
  const counts = { HIT: 0, MISS: 0, STALE: 0, FORCED: 0, FAILED: 0 };
  let cost = 0;
  let saved = 0;
  let inTok = 0;
  let outTok = 0;
  let tokensAvoided = 0;
  let llmCallsAvoided = 0;
  for (const node of graph.nodes) {
    counts[node.status] += 1;
    cost += node.cost_usd;
    saved += node.saved_usd;
    inTok += node.input_tokens;
    outTok += node.output_tokens;
    if (node.status === "HIT") {
      tokensAvoided += (node.previous_input_tokens ?? 0) + (node.previous_output_tokens ?? 0);
      if (LLM_NODE_IDS.has(node.id)) llmCallsAvoided += 1;
    }
  }
  return { counts, cost, saved, inTok, outTok, tokensAvoided, llmCallsAvoided };
}

function runListItem(
  id: string,
  hoursAgo: number,
  graph: RunGraph,
  status: string
): RunListItem {
  const { counts, cost, saved, inTok, outTok, tokensAvoided, llmCallsAvoided } = summarize(graph);
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
    tokens_avoided: tokensAvoided,
    llm_calls_avoided: llmCallsAvoided,
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
  const tokensAvoided = DEMO_RUNS.reduce((sum, r) => sum + r.tokens_avoided, 0);
  const llmCallsAvoided = DEMO_RUNS.reduce((sum, r) => sum + r.llm_calls_avoided, 0);
  return {
    period: "7d",
    runs: DEMO_RUNS.length,
    computations: totalComputations,
    hit_rate: totalHits / totalComputations,
    cost_usd: Number(cost.toFixed(4)),
    saved_usd: Number(saved.toFixed(4)),
    tokens_consumed: inTok + outTok,
    tokens_avoided: tokensAvoided,
    llm_calls_avoided: llmCallsAvoided,
    // No demo scenario models a real cross-model reuse, so this stays 0
    // rather than a fabricated figure -- see the reuse_kind comment above.
    cross_model_saved_usd: 0,
    cross_model_tokens_avoided: 0,
  };
}

// V0.2: artifact type per node, for the Projects page. Not every node is an
// LLM call (see NODE_DEFS.isLlmCall) -- only those have a model.
const ARTIFACT_TYPE_BY_NODE: Record<string, ArtifactType> = {
  company_profile: "source",
  financials: "structured_data",
  competitors: "source",
  news: "source",
  overview: "research_note",
  financial_analysis: "analysis",
  competitive_analysis: "analysis",
  news_analysis: "analysis",
  valuation: "analysis",
  final_report: "draft",
};

export function demoArtifacts(): ArtifactListItem[] {
  const now = Date.now();
  return NODE_DEFS.map((def, index) => ({
    logical_key: `${def.id}:NVDA`,
    name: def.name,
    artifact_type: ARTIFACT_TYPE_BY_NODE[def.id] ?? null,
    model: def.isLlmCall ? "openai/gpt-4o" : null,
    reusable: true,
    cost_usd: def.cost,
    created_at: new Date(now - (index + 1) * 3600_000).toISOString(),
  }));
}

// Derived from the same DEMO_RUN_GRAPHS every other fixture uses, rather
// than a parallel invented dataset: real executions only (a HIT's cost is
// zeroed by design -- its cost is recorded as avoided, on the source row).
export function demoUsage(): UsageBreakdownItem[] {
  const totals = new Map<string, UsageBreakdownItem>();
  for (const graph of Object.values(DEMO_RUN_GRAPHS)) {
    for (const node of graph.nodes) {
      if (node.status === "HIT") continue;
      const model = LLM_NODE_IDS.has(node.id) ? "openai/gpt-4o" : null;
      const key = `${model ?? ""}:${node.name}`;
      const existing = totals.get(key) ?? {
        model,
        name: node.name,
        computations: 0,
        cost_usd: 0,
        input_tokens: 0,
        output_tokens: 0,
      };
      existing.computations += 1;
      existing.cost_usd += node.cost_usd;
      existing.input_tokens += node.input_tokens;
      existing.output_tokens += node.output_tokens;
      totals.set(key, existing);
    }
  }
  return [...totals.values()]
    .map((item) => ({ ...item, cost_usd: Number(item.cost_usd.toFixed(4)) }))
    .sort((a, b) => b.cost_usd - a.cost_usd);
}

// V0.2 (Phase 8): derived from the same demoArtifacts() every other
// preview-adjacent fixture uses. "draft" (final_report) previews as
// RECOMPUTE, matching apps/api/app/agent/pipeline.py's real distinction --
// the draft is specifically what the new model is being asked to write, so
// reusing it across a model switch would be free but pointless. Everything
// else (sources, facts, research, analysis) previews as REUSE.
export function demoModelSwitchPreview(targetModel: string): ModelSwitchPreview {
  const items = demoArtifacts().map((artifact) => {
    const reusable = artifact.artifact_type !== "draft";
    return {
      name: artifact.name,
      logical_key: artifact.logical_key,
      decision: reusable ? ("REUSE" as const) : ("RECOMPUTE" as const),
      reason: reusable
        ? `portable ${artifact.artifact_type}; only the model would change`
        : "the draft is what the new model is being asked to (re)write",
      artifact_type: artifact.artifact_type,
      current_model: artifact.model,
      cost_if_recomputed_usd: reusable ? 0 : artifact.cost_usd,
    };
  });

  return {
    target_model: targetModel,
    items,
    reusable_count: items.filter((i) => i.decision === "REUSE").length,
    recompute_count: items.filter((i) => i.decision === "RECOMPUTE").length,
    estimated_incremental_cost_usd: Number(
      items
        .filter((i) => i.decision === "RECOMPUTE")
        .reduce((sum, i) => sum + i.cost_if_recomputed_usd, 0)
        .toFixed(4),
    ),
  };
}
