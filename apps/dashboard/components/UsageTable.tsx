import type { UsageBreakdownItem } from "@/lib/types";
import { formatCompact, formatUsd } from "@/lib/format";

export default function UsageTable({ items }: { items: UsageBreakdownItem[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-card border border-border bg-surface p-8 text-center text-[13.5px] text-ink-muted shadow-card">
        No executions in this period.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-card border border-border bg-surface p-2 shadow-card">
      <div className="min-w-[640px]">
        <div className="grid grid-cols-[1fr_1.2fr_0.8fr_0.9fr_1fr] gap-3 px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          <span>Model</span>
          <span>Task</span>
          <span>Runs</span>
          <span>Cost</span>
          <span>Tokens</span>
        </div>
        <div className="flex flex-col">
          {items.map((item) => (
            <div
              key={`${item.model ?? ""}:${item.name}`}
              className="grid grid-cols-[1fr_1.2fr_0.8fr_0.9fr_1fr] items-center gap-3 rounded-2xl px-4 py-3.5 text-[13px]"
            >
              <span className="font-medium text-ink">{item.model ?? "—"}</span>
              <span className="text-ink-secondary">{item.name}</span>
              <span className="tabular text-ink-secondary">{item.computations}</span>
              <span className="tabular text-ink">{formatUsd(item.cost_usd)}</span>
              <span className="tabular text-ink-secondary">
                {formatCompact(item.input_tokens + item.output_tokens)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
