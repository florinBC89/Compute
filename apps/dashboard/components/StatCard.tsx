import type { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
  accentValue?: boolean;
  icon?: ReactNode;
  className?: string;
}

export default function StatCard({ label, value, sub, accentValue, icon, className }: StatCardProps) {
  return (
    <div
      className={`rounded-card border border-border bg-surface p-5 shadow-card ${className ?? ""}`}
    >
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-ink-secondary">{label}</span>
        {icon}
      </div>
      <div
        className={`tabular mt-3 text-[26px] font-semibold leading-none ${
          accentValue ? "text-accent" : "text-ink"
        }`}
      >
        {value}
      </div>
      {sub ? <div className="mt-2 text-[12px] text-ink-muted">{sub}</div> : null}
    </div>
  );
}
