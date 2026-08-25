import Link from "next/link";
import type { RunListItem } from "@/lib/types";
import { formatRelativeTime, formatUsd, shortId } from "@/lib/format";

const RUN_STATUS_STYLE: Record<string, string> = {
  RUNNING: "bg-info/10 text-info",
  SUCCEEDED: "bg-good/10 text-good",
  FAILED: "bg-critical/10 text-critical",
};

export default function RunsTable({ runs }: { runs: RunListItem[] }) {
  return (
    <div className="overflow-x-auto rounded-card border border-border bg-surface p-2 shadow-card">
      <div className="min-w-[640px]">
        <div className="grid grid-cols-[1.4fr_0.9fr_0.8fr_0.9fr_0.8fr_0.8fr_0.9fr] gap-3 px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          <span>Run</span>
          <span>Time</span>
          <span>Computations</span>
          <span>Reuse %</span>
          <span>Cost</span>
          <span>Saved</span>
          <span>Status</span>
        </div>
        <div className="flex flex-col">
          {runs.map((run) => {
            const reuse = run.computations > 0 ? run.hits / run.computations : 0;
            return (
              <Link
                key={run.id}
                href={`/runs/${run.id}`}
                className="grid grid-cols-[1.4fr_0.9fr_0.8fr_0.9fr_0.8fr_0.8fr_0.9fr] items-center gap-3 rounded-2xl px-4 py-3.5 text-[13px] transition-colors hover:bg-page"
              >
                <span className="flex flex-col">
                  <span className="font-mono text-[12.5px] font-medium text-ink">
                    {shortId(run.id)}
                  </span>
                  <span className="text-[11.5px] text-ink-muted">
                    {run.external_run_id ?? "—"}
                  </span>
                </span>
                <span className="tabular text-ink-secondary">
                  {formatRelativeTime(run.started_at)}
                </span>
                <span className="tabular text-ink">{run.computations}</span>
                <span className="tabular font-medium text-accent">{Math.round(reuse * 100)}%</span>
                <span className="tabular text-ink">{formatUsd(run.total_cost_usd)}</span>
                <span className="tabular font-medium text-good">{formatUsd(run.saved_usd)}</span>
                <span>
                  <span
                    className={`inline-flex rounded-pill px-2.5 py-1 text-[11px] font-semibold ${
                      RUN_STATUS_STYLE[run.status] ?? "bg-page text-ink-secondary"
                    }`}
                  >
                    {run.status}
                  </span>
                </span>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
