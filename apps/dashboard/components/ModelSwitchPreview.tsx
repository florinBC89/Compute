"use client";

import { useState } from "react";
import type { ModelSwitchPreview as Preview } from "@/lib/types";
import { formatUsd } from "@/lib/format";

const TARGET_MODELS = [
  "openai/gpt-4o-mini",
  "anthropic/claude-haiku-4-5",
  "google/gemini-3.6-flash",
];

// V0.2 (Phase 8): surfaces the already-built POST /runs/{id}/preview-model-
// switch endpoint on the developer dashboard -- what would carry over if
// this run's work were repeated on a different model, before anything
// actually executes.
export default function ModelSwitchPreview({ runId }: { runId: string }) {
  const [target, setTarget] = useState(TARGET_MODELS[0]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  async function runPreview() {
    setLoading(true);
    const response = await fetch(`/api/preview-model-switch/${runId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_model: target }),
    });
    if (response.ok) setPreview(await response.json());
    setLoading(false);
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => {
          setOpen(true);
          void runPreview();
        }}
        className="rounded-pill border border-border px-3 py-1.5 text-[12.5px] font-medium text-ink-secondary hover:text-ink"
      >
        Preview model switch
      </button>
    );
  }

  return (
    <div className="rounded-card border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[13px] font-semibold uppercase tracking-wide text-ink-muted">
          Model switch preview
        </h3>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-[12px] text-ink-muted hover:text-ink"
        >
          Close
        </button>
      </div>

      <div className="mt-3 flex items-center gap-2 text-[13px] text-ink">
        Target
        <select
          value={target}
          onChange={(e) => {
            setTarget(e.target.value);
            setPreview(null);
          }}
          className="rounded-pill border border-border bg-page px-2.5 py-1 text-[12.5px] text-ink outline-none focus:border-accent"
        >
          {TARGET_MODELS.map((model) => (
            <option key={model} value={model}>
              {model}
            </option>
          ))}
        </select>
        <button type="button" onClick={runPreview} className="text-[12.5px] text-accent hover:underline">
          Preview
        </button>
      </div>

      {loading ? (
        <p className="mt-3 text-[13px] text-ink-muted">Evaluating&hellip;</p>
      ) : preview ? (
        <>
          <ul className="mt-3 flex flex-col gap-1.5">
            {preview.items.map((item) => (
              <li
                key={item.logical_key}
                className="flex items-center justify-between text-[13px] text-ink-secondary"
              >
                <span className="flex items-center gap-2">
                  <span
                    className={`rounded-pill px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                      item.decision === "REUSE"
                        ? "bg-good/10 text-good"
                        : "bg-warning/15 text-warning"
                    }`}
                  >
                    {item.decision}
                  </span>
                  {item.name}
                </span>
                <span className="tabular text-[12px] text-ink-muted">{item.reason}</span>
              </li>
            ))}
          </ul>
          <p className="tabular mt-3 text-[13px] font-medium text-ink">
            {preview.reusable_count} reusable · {preview.recompute_count} to recompute · est.{" "}
            {formatUsd(preview.estimated_incremental_cost_usd)} incremental
          </p>
        </>
      ) : null}
    </div>
  );
}
