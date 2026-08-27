import TopNav from "@/components/TopNav";
import StatCard from "@/components/StatCard";
import GaugeRing from "@/components/GaugeRing";
import BaselineTable from "@/components/BaselineTable";
import { getProjectMetrics, isDemoMode } from "@/lib/api";
import { tokenEconomics, costEconomics } from "@/lib/compute";
import { formatCompact, formatUsd } from "@/lib/format";

export const dynamic = "force-dynamic";

// Overview answers the primary dashboard question directly: where AI compute
// is going, and how much Accurate prevented. Compute Avoided is the hero KPI
// -- not Reuse Rate, which measures computation *count*, not the economics.
export default async function OverviewPage() {
  const metrics = await getProjectMetrics("30d");
  const tokens = tokenEconomics(metrics.tokens_consumed, metrics.tokens_avoided);
  const cost = costEconomics(metrics.cost_usd, metrics.saved_usd);

  return (
    <div className="flex flex-col gap-6">
      <TopNav demoMode={isDemoMode} />

      <div>
        <h1 className="text-[32px] font-semibold leading-tight text-ink">Overview</h1>
        <p className="mt-1 text-[14px] text-ink-secondary">
          Where your AI compute is going, and how much Accurate prevented — last 30 days
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="col-span-2 flex items-center justify-center rounded-card bg-surface-raised p-5 shadow-card lg:col-span-1">
          <GaugeRing value={tokens.avoidedRatio} label="Compute avoided" sublabel="30d" size={132} />
        </div>
        <StatCard label="Baseline tokens" value={formatCompact(tokens.baseline)} sub="without Accurate" />
        <StatCard label="Consumed" value={formatCompact(tokens.actual)} sub="with Accurate" />
        <StatCard label="Tokens avoided" value={formatCompact(tokens.avoided)} sub="not sent to a model" accentValue />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Actual spend" value={formatUsd(cost.actual)} sub="last 30 days" />
        <StatCard label="Cost avoided" value={formatUsd(cost.avoided)} sub="vs. no reuse" accentValue />
        <StatCard label="LLM calls avoided" value={formatCompact(metrics.llm_calls_avoided)} sub={`${formatCompact(metrics.computations)} computations`} />
      </div>

      <div>
        <h2 className="mb-3 px-1 text-[15px] font-semibold text-ink">Baseline vs. actual vs. avoided</h2>
        <BaselineTable
          rows={[
            { label: "Tokens", data: tokens, format: formatCompact },
            { label: "Cost", data: cost, format: formatUsd },
          ]}
        />
      </div>
    </div>
  );
}
