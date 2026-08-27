import type { BaselineActualAvoided } from "@/lib/compute";

interface Row {
  label: string;
  data: BaselineActualAvoided;
  format: (n: number) => string;
}

export default function BaselineTable({ rows }: { rows: Row[] }) {
  return (
    <div className="overflow-x-auto rounded-card border border-border bg-surface shadow-card">
      <div className="min-w-[480px]">
        <div className="grid grid-cols-4 gap-3 border-b border-border px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          <span>Metric</span>
          <span>Baseline / without Accurate</span>
          <span>Actual / with Accurate</span>
          <span>Avoided</span>
        </div>
        {rows.map((row) => (
          <div
            key={row.label}
            className="grid grid-cols-4 items-center gap-3 border-b border-border px-5 py-4 text-[13.5px] last:border-b-0"
          >
            <span className="font-medium text-ink">{row.label}</span>
            <span className="tabular text-ink-secondary">{row.format(row.data.baseline)}</span>
            <span className="tabular text-ink">{row.format(row.data.actual)}</span>
            <span className="tabular font-semibold text-accent">
              {row.format(row.data.avoided)}{" "}
              <span className="text-[12px] font-medium text-ink-muted">
                ({Math.round(row.data.avoidedRatio * 100)}%)
              </span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
