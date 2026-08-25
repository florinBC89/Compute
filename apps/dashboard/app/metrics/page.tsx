import TopNav from "@/components/TopNav";
import StatCard from "@/components/StatCard";
import GaugeRing from "@/components/GaugeRing";
import CostRings from "@/components/CostRings";
import { getProjectMetrics } from "@/lib/api";
import { formatCompact, formatUsd } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function MetricsPage() {
  const metrics = await getProjectMetrics("30d");

  return (
    <div className="flex flex-col gap-6">
      <TopNav />

      <div>
        <h1 className="text-[32px] font-semibold leading-tight text-ink">Project metrics</h1>
        <p className="mt-1 text-[14px] text-ink-secondary">
          research-agent · last {metrics.period}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="flex flex-col items-center justify-center gap-4 rounded-card bg-surface-raised p-8 shadow-card">
          <GaugeRing value={metrics.hit_rate} label="Reuse rate" sublabel={metrics.period} size={176} />
          <p className="text-center text-[12px] text-white/45">
            {metrics.computations} computations · {metrics.runs} runs
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <StatCard label="Total spend" value={formatUsd(metrics.cost_usd)} />
          <StatCard label="Estimated savings" value={formatUsd(metrics.saved_usd)} accentValue />
          <StatCard label="Tokens consumed" value={formatCompact(metrics.tokens_consumed)} />
          <StatCard label="Tokens avoided" value={formatCompact(metrics.tokens_avoided)} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1fr]">
        <div className="rounded-card border border-border bg-surface p-6 shadow-card">
          <h2 className="text-[15px] font-semibold text-ink">Cost breakdown</h2>
          <p className="mt-1 text-[12.5px] text-ink-muted">
            what reuse actually avoided, area-true to the dollar amounts
          </p>
          <div className="mt-4 flex justify-center">
            <CostRings actualUsd={metrics.cost_usd} savedUsd={metrics.saved_usd} />
          </div>
        </div>

        <div className="rounded-card border border-border bg-surface p-6 shadow-card">
          <h2 className="text-[15px] font-semibold text-ink">LLM calls avoided</h2>
          <p className="mt-1 text-[12.5px] text-ink-muted">
            calls that never had to leave the process because the surrounding
            computation was reused
          </p>
          <div className="tabular mt-6 text-[42px] font-semibold leading-none text-accent">
            {formatCompact(metrics.llm_calls_avoided)}
          </div>
          <p className="mt-2 text-[12.5px] text-ink-secondary">
            out of {formatCompact(metrics.computations)} total computations this period
          </p>
        </div>
      </div>
    </div>
  );
}
