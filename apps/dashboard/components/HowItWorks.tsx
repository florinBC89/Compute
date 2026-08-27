import Link from "next/link";
import type { RunGraph as RunGraphData } from "@/lib/types";
import { shortId } from "@/lib/format";
import RunGraph from "./RunGraph";

interface HowItWorksProps {
  example: { runId: string; graph: RunGraphData } | null;
}

const NAIVE_STEPS = ["Request changed", "→ CACHE MISS", "→ recompute everything"];

const ACCURATE_STEPS = [
  "Company data, financials, competitors — unchanged → REUSED",
  "News — changed → COMPUTED",
  "Everything downstream of news — affected → COMPUTED",
  "Everything else — untouched → REUSED",
];

export default function HowItWorks({ example }: HowItWorksProps) {
  return (
    <div className="rounded-card border border-border bg-surface p-6 shadow-card">
      <h2 className="text-[15px] font-semibold text-ink">How Accurate thinks</h2>
      <p className="mt-1 max-w-[640px] text-[13.5px] text-ink-secondary">
        A naive cache sees one changed request and invalidates the whole result. Accurate
        tracks dependencies through the graph, so only what actually changed — and what depends
        on it — recomputes.
      </p>

      <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-2xl bg-page p-4">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            A naive cache
          </div>
          <div className="mt-3 flex flex-col gap-1.5 font-mono text-[12.5px] text-ink-secondary">
            {NAIVE_STEPS.map((step) => (
              <div key={step}>{step}</div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl bg-accent-soft p-4">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-accent">
            Accurate
          </div>
          <div className="mt-3 flex flex-col gap-1.5 text-[12.5px] text-ink">
            {ACCURATE_STEPS.map((step) => (
              <div key={step}>{step}</div>
            ))}
          </div>
        </div>
      </div>

      {example ? (
        <div className="mt-6">
          <div className="mb-3 flex items-center justify-between px-1">
            <p className="text-[13px] text-ink-secondary">
              This is a real run, not a mockup —{" "}
              <Link href={`/runs/${example.runId}`} className="font-medium text-accent hover:underline">
                run #{shortId(example.runId)}
              </Link>
              . Click any node to see why.
            </p>
          </div>
          <RunGraph graph={example.graph} />
        </div>
      ) : null}
    </div>
  );
}
