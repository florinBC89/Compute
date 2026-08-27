"use client";

import { useEffect, useState } from "react";
import type { GraphNode } from "@/lib/types";
import { formatCompact, formatUsd } from "@/lib/format";
import StatusBadge from "./StatusBadge";

interface ExplainChange {
  kind: string;
  key: string | null;
  old: string | null;
  new: string | null;
}

interface ExplainResponse {
  changes: ExplainChange[];
}

const UNCHANGED_CHECKLIST = [
  "Inputs",
  "Dependency versions",
  "Prompt",
  "Model",
  "Code version",
];

function describeChange(change: ExplainChange): string {
  const key = change.key ?? "dependency";
  if (change.kind === "dependency_added") return `${key} is new (no prior version to compare)`;
  if (change.kind === "dependency_removed") return `${key} was dropped`;
  return `${key} changed: ${change.old ?? "?"} → ${change.new ?? "?"}`;
}

export default function WhyDrawer({ node, onClose }: { node: GraphNode; onClose: () => void }) {
  const [explain, setExplain] = useState<ExplainResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const needsExplain = node.status !== "HIT";

  useEffect(() => {
    if (!needsExplain) return;
    let cancelled = false;
    setLoading(true);
    fetch(`/api/explain/${node.id}`)
      .then((r) => (r.ok ? r.json() : { changes: [] }))
      .then((data) => {
        if (!cancelled) setExplain(data);
      })
      .catch(() => {
        if (!cancelled) setExplain({ changes: [] });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [node.id, needsExplain]);

  const totalTokens = node.input_tokens + node.output_tokens;
  const prevTokens = (node.previous_input_tokens ?? 0) + (node.previous_output_tokens ?? 0);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-[380px] flex-col overflow-y-auto bg-surface p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-[17px] font-semibold text-ink">{node.name}</h2>
            <div className="mt-2">
              <StatusBadge status={node.status} />
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-8 w-8 items-center justify-center rounded-full text-ink-muted hover:bg-page hover:text-ink"
          >
            ✕
          </button>
        </div>

        <h3 className="mt-6 text-[13px] font-semibold uppercase tracking-wide text-ink-muted">
          Why?
        </h3>

        {node.status === "HIT" ? (
          <ul className="mt-3 flex flex-col gap-2">
            {UNCHANGED_CHECKLIST.map((item) => (
              <li key={item} className="flex items-center gap-2 text-[13.5px] text-ink">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-good/10 text-[11px] text-good">
                  ✓
                </span>
                {item} — unchanged
              </li>
            ))}
          </ul>
        ) : loading ? (
          <p className="mt-3 text-[13.5px] text-ink-muted">Checking what changed…</p>
        ) : explain && explain.changes.length > 0 ? (
          <ul className="mt-3 flex flex-col gap-2">
            {explain.changes.map((change, i) => (
              <li key={i} className="flex items-start gap-2 text-[13.5px] text-ink">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-warning/15 text-[11px] text-warning">
                  ↻
                </span>
                {describeChange(change)}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-[13.5px] text-ink-muted">
            {node.status === "MISS"
              ? "First time this exact computation has run — nothing existed to reuse."
              : "No prior computation to compare against."}
          </p>
        )}

        <div className="mt-6 rounded-2xl border border-border bg-page p-4">
          <div className="grid grid-cols-2 gap-4 text-[13px]">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                Previous execution
              </div>
              {node.previous_cost_usd != null ? (
                <div className="mt-2 flex flex-col gap-1 text-ink">
                  <span className="tabular">{formatCompact(prevTokens)} tokens</span>
                  <span className="tabular">{formatUsd(node.previous_cost_usd)}</span>
                  <span className="tabular">{node.previous_latency_ms ?? "—"}ms</span>
                </div>
              ) : (
                <div className="mt-2 text-ink-muted">—</div>
              )}
            </div>
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                This run
              </div>
              <div className="mt-2 flex flex-col gap-1 text-ink">
                <span className="tabular">{formatCompact(totalTokens)} tokens</span>
                <span className="tabular">{formatUsd(node.cost_usd)}</span>
                <span className="tabular">{node.latency_ms ?? "—"}ms</span>
              </div>
            </div>
          </div>
        </div>

        {node.saved_usd > 0 ? (
          <div className="mt-4 rounded-2xl bg-good/10 px-4 py-3 text-center text-[13.5px] font-semibold text-good">
            {formatUsd(node.saved_usd)} avoided
          </div>
        ) : null}
      </div>
    </div>
  );
}
