"use client";

import { useState } from "react";
import type { ModelSwitchPreview as Preview } from "@/lib/api";

//: Short picker key -> the pricing-table model id app.agent.pipeline
//: actually records (see PROVIDER_MODULES in apps/api/app/agent/pipeline.py).
//: The preview endpoint compares against this exact string, not the short key.
export const PROVIDER_MODEL_IDS: Record<string, string> = {
  openai: "openai/gpt-4o-mini",
  anthropic: "anthropic/claude-haiku-4-5",
  gemini: "google/gemini-3.6-flash",
};

export const MODEL_LABELS: { value: string; label: string }[] = [
  { value: "openai", label: "GPT-4o mini" },
  { value: "anthropic", label: "Claude Haiku 4.5" },
  { value: "gemini", label: "Gemini 3.6 Flash" },
];

function formatUsd(value: number): string {
  return `$${value.toFixed(value < 0.01 ? 4 : 2)}`;
}

// Phase 8 (V0.2 human workspace): the spec's "Switch model" screen -- what
// would carry over before actually executing anything, shown as a visible,
// trustworthy checklist rather than a hidden cache decision.
export default function ModelSwitchPreview({
  runId,
  currentModel,
  onContinue,
}: {
  runId: string;
  currentModel: string;
  onContinue: (model: string) => void;
}) {
  const options = MODEL_LABELS.filter((m) => m.value !== currentModel);
  const [target, setTarget] = useState(options[0]?.value ?? "");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  async function runPreview() {
    setLoading(true);
    setPreview(null);
    const response = await fetch(`/api/runs/${runId}/preview-model-switch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_model: PROVIDER_MODEL_IDS[target] }),
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
        className="mt-3 block w-full text-center text-[13px] text-ink-muted hover:text-ink"
      >
        Switch model &rarr;
      </button>
    );
  }

  const targetLabel = MODEL_LABELS.find((m) => m.value === target)?.label ?? target;

  return (
    <div className="mt-4 rounded-card border border-border bg-surface p-6">
      <div className="flex items-center gap-2 text-[14px] text-ink">
        Switch to
        <select
          value={target}
          onChange={(e) => {
            setTarget(e.target.value);
            setPreview(null);
          }}
          className="rounded-pill border border-border bg-page px-3 py-1 text-[13px] text-ink outline-none focus:border-accent"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={runPreview}
          className="text-[13px] text-accent hover:underline"
        >
          Preview
        </button>
      </div>

      {loading ? (
        <p className="mt-3 text-[13px] text-ink-muted">Checking what carries over&hellip;</p>
      ) : preview ? (
        <>
          <p className="mt-3 text-[13px] text-ink-secondary">
            {targetLabel} can reuse:
          </p>
          <ul className="mt-2 flex flex-col gap-1.5">
            {preview.items.map((item) => (
              <li
                key={item.logical_key}
                className="flex items-center gap-2 text-[13px] text-ink-secondary"
              >
                <span
                  className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] ${
                    item.decision === "REUSE"
                      ? "bg-good/15 text-good"
                      : "bg-warning/15 text-warning"
                  }`}
                >
                  {item.decision === "REUSE" ? "✓" : "↻"}
                </span>
                {item.name}
              </li>
            ))}
          </ul>
          <p className="tabular mt-3 text-[13px] text-ink-muted">
            Estimated incremental cost: {formatUsd(preview.estimated_incremental_cost_usd)}
          </p>
          <button
            type="button"
            onClick={() => onContinue(target)}
            className="mt-3 w-full rounded-pill bg-accent px-4 py-2 text-[13px] font-semibold text-white"
          >
            Continue with {targetLabel} &rarr;
          </button>
        </>
      ) : null}
    </div>
  );
}
