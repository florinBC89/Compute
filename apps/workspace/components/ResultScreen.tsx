"use client";

import { useEffect, useState } from "react";
import type { GraphNode, RunSummary } from "@/lib/api";

function formatUsd(value: number): string {
  return `$${value.toFixed(value < 0.01 ? 4 : 2)}`;
}

function formatTokens(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return String(value);
}

// Phase 6 (V0.2 human workspace): the spec's consumer result screen --
// "Research complete / You paid $X / You avoided $Y" in plain language,
// technical detail (the node-by-node trace) behind "View details" rather
// than shown by default.
export default function ResultScreen({ runId }: { runId: string }) {
  const [summary, setSummary] = useState<RunSummary | null>(null);
  const [nodes, setNodes] = useState<GraphNode[] | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/runs/${runId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [runId]);

  useEffect(() => {
    if (!showDetails || nodes) return;
    fetch(`/api/runs/${runId}/graph`)
      .then((r) => (r.ok ? r.json() : { nodes: [] }))
      .then((data) => setNodes(data.nodes));
  }, [showDetails, nodes, runId]);

  if (error) {
    return (
      <div className="mt-8 rounded-card border border-border bg-surface p-6 text-center text-[13.5px] text-critical">
        Couldn&apos;t load the result.
      </div>
    );
  }
  if (!summary) {
    return (
      <div className="mt-8 rounded-card border border-border bg-surface p-6 text-center text-[13.5px] text-ink-muted">
        Loading result&hellip;
      </div>
    );
  }

  const withoutReuse = summary.total_cost_usd + summary.saved_usd;
  const totalTokens = summary.input_tokens + summary.output_tokens;

  return (
    <div className="mt-8 rounded-card border border-border bg-surface p-6">
      <h2 className="text-[16px] font-semibold text-ink">Research complete</h2>

      <div className="mt-4 grid grid-cols-3 gap-4 text-center">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-ink-muted">
            Without reuse
          </div>
          <div className="tabular mt-1 text-[16px] text-ink-secondary line-through">
            {formatUsd(withoutReuse)}
          </div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-wide text-ink-muted">
            You paid
          </div>
          <div className="tabular mt-1 text-[16px] font-semibold text-ink">
            {formatUsd(summary.total_cost_usd)}
          </div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-wide text-ink-muted">
            You avoided
          </div>
          <div className="tabular mt-1 text-[16px] font-semibold text-good">
            {formatUsd(summary.saved_usd)}
          </div>
        </div>
      </div>

      <p className="tabular mt-4 text-center text-[13px] text-ink-muted">
        {formatTokens(summary.tokens_avoided)} tokens avoided &middot;{" "}
        {formatTokens(totalTokens)} tokens used
      </p>

      <button
        type="button"
        onClick={() => setShowDetails((v) => !v)}
        className="mt-4 w-full text-center text-[13px] text-accent hover:underline"
      >
        {showDetails ? "Hide details" : "View details"}
      </button>

      {showDetails ? (
        <ul className="mt-4 flex flex-col gap-2 border-t border-border pt-4">
          {(nodes ?? []).map((node) => (
            <li
              key={node.id}
              className="flex items-center justify-between text-[13px] text-ink-secondary"
            >
              <span className="flex items-center gap-2">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    node.status === "HIT" ? "bg-good" : "bg-accent"
                  }`}
                />
                {node.name}
                {node.reuse_kind === "CROSS_MODEL" ? (
                  <span className="rounded-pill bg-violet/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-violet">
                    cross-model
                  </span>
                ) : null}
              </span>
              <span className="tabular">
                {node.status === "HIT" ? formatUsd(node.saved_usd) : formatUsd(node.cost_usd)}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
