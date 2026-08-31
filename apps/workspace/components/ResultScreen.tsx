"use client";

import { useEffect, useState } from "react";
import type { GraphNode, RunSummary } from "@/lib/api";
import ModelSwitchPreview, { MODEL_LABELS, PROVIDER_MODEL_IDS } from "./ModelSwitchPreview";

//: full model id (what GraphNode.model actually holds) -> short display
//: label, so the trace view reads "GPT-4o mini" rather than the raw
//: "openai/gpt-4o-mini" pricing-table key.
const MODEL_ID_LABELS: Record<string, string> = Object.fromEntries(
  MODEL_LABELS.map((option) => [PROVIDER_MODEL_IDS[option.value], option.label])
);

function formatUsd(value: number): string {
  return `$${value.toFixed(value < 0.01 ? 4 : 2)}`;
}

function formatTokens(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return String(value);
}

// Copy rules from the V0.3 chat-states spec (section 6): "no new model
// inference" rather than "free" for full reuse; fully-new work gets no
// receipt line at all rather than implying a saving that didn't happen.
function receiptLine(summary: RunSummary): string | null {
  if (summary.computations > 0 && summary.misses === 0) {
    return "Answered from existing work • no new model inference";
  }
  if (summary.hits > 0) {
    return `${summary.hits} source${summary.hits === 1 ? "" : "s"} reused`;
  }
  return null;
}

// Phases 6+8 (V0.2 human workspace): the spec's consumer result screen --
// "Research complete / You paid $X / You avoided $Y" in plain language,
// technical detail (the node-by-node trace) behind "View details" rather
// than shown by default -- plus a "Switch model" preview so trying a
// different model on the same work is a visible, trustworthy choice
// instead of a hidden cache decision.
export default function ResultScreen({
  runId,
  currentModel,
  onSwitchModel,
}: {
  runId: string;
  currentModel: string;
  onSwitchModel: (model: string) => void;
}) {
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
      <div className="mt-4 rounded-card border border-border bg-surface p-6 text-center text-[13.5px] text-critical">
        Couldn&apos;t load the result.
      </div>
    );
  }
  if (!summary) {
    return (
      <div className="mt-4 rounded-card border border-border bg-surface p-6 text-center text-[13.5px] text-ink-muted">
        Loading result&hellip;
      </div>
    );
  }

  const withoutReuse = summary.total_cost_usd + summary.saved_usd;
  const totalTokens = summary.input_tokens + summary.output_tokens;
  const line = receiptLine(summary);

  return (
    <div className="mt-4">
      {line ? (
        <div className="flex items-center gap-2.5">
          {/* Same looping video as every other "Accurate is doing
              something" spot (auth loading, empty-state hero, the
              in-progress step list) instead of the static AiOrb -- one
              consistent leading icon across every state in this area. */}
          {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
          <video
            src="/videos/social-loading.mp4"
            autoPlay
            loop
            muted
            playsInline
            className="h-[34px] w-[34px] shrink-0 rounded-full object-cover"
          />
          <span className="text-[16px] font-medium text-chat-ink">{line}</span>
        </div>
      ) : null}

      <button
        type="button"
        onClick={() => setShowDetails((v) => !v)}
        className="mt-2 text-left text-[13px] text-chat-label hover:underline"
      >
        {showDetails ? "Hide compute details" : "Compute details"}
      </button>

      {showDetails ? (
        <div className="mt-3 rounded-card border border-border bg-surface p-6">
          <div className="grid grid-cols-3 gap-4 text-center">
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
                You paid (actual)
              </div>
              <div className="tabular mt-1 text-[16px] font-semibold text-ink">
                {formatUsd(summary.total_cost_usd)}
              </div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wide text-ink-muted">
                You avoided (measured)
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
                  {node.model ? (
                    <span className="rounded-pill bg-page px-1.5 py-0.5 text-[10px] text-ink-muted">
                      {MODEL_ID_LABELS[node.model] ?? node.model}
                    </span>
                  ) : null}
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

          <ModelSwitchPreview runId={runId} currentModel={currentModel} onContinue={onSwitchModel} />
        </div>
      ) : null}
    </div>
  );
}
