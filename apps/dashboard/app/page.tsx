import TopNav from "@/components/TopNav";
import StatCard from "@/components/StatCard";
import GaugeRing from "@/components/GaugeRing";
import RunsTable from "@/components/RunsTable";
import CostSparkline from "@/components/CostSparkline";
import { getProjectMetrics, listRuns } from "@/lib/api";
import { formatCompact, formatUsd } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function RunsPage() {
  const [runs, metrics] = await Promise.all([listRuns(20), getProjectMetrics("30d")]);

  return (
    <div className="flex flex-col gap-6">
      <TopNav />

      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-[32px] font-semibold leading-tight text-ink">Runs</h1>
          <p className="mt-1 text-[14px] text-ink-secondary">
            {metrics.runs} runs in the last 30 days · {Math.round(metrics.hit_rate * 100)}% reused
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <div className="col-span-2 flex items-center justify-center rounded-card bg-surface-raised p-5 shadow-card lg:col-span-1">
          <GaugeRing value={metrics.hit_rate} label="Reuse rate" sublabel="30d" size={132} />
        </div>
        <StatCard label="Total spend" value={formatUsd(metrics.cost_usd)} sub="last 30 days" />
        <StatCard
          label="Estimated savings"
          value={formatUsd(metrics.saved_usd)}
          sub="vs. no reuse"
          accentValue
        />
        <StatCard label="Tokens avoided" value={formatCompact(metrics.tokens_avoided)} sub="not sent to a model" />
        <StatCard
          label="LLM calls avoided"
          value={formatCompact(metrics.llm_calls_avoided)}
          sub={`${formatCompact(metrics.computations)} computations`}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <div className="mb-3 flex items-center justify-between px-1">
            <h2 className="text-[15px] font-semibold text-ink">Recent runs</h2>
          </div>
          <RunsTable runs={runs} />
        </div>

        <div className="rounded-card border border-border bg-surface p-5 shadow-card">
          <h2 className="text-[13px] font-semibold text-ink">Cost per run</h2>
          <p className="mt-1 text-[11.5px] text-ink-muted">last {Math.min(runs.length, 10)} runs</p>
          <div className="mt-4">
            <CostSparkline runs={runs.slice(0, 10)} />
          </div>
        </div>
      </div>
    </div>
  );
}
