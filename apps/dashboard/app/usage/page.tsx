import TopNav from "@/components/TopNav";
import StatCard from "@/components/StatCard";
import UsageTable from "@/components/UsageTable";
import { getUsage, isDemoMode } from "@/lib/api";
import { formatCompact, formatUsd } from "@/lib/format";

export const dynamic = "force-dynamic";

// Usage: cost and tokens broken down by model and task (V0.2) -- real
// executions only, so this answers "what is each model actually costing,"
// distinct from Overview's baseline/avoided framing.
export default async function UsagePage() {
  const items = await getUsage("30d");

  const totalCost = items.reduce((sum, item) => sum + item.cost_usd, 0);
  const totalTokens = items.reduce((sum, item) => sum + item.input_tokens + item.output_tokens, 0);
  const modelCount = new Set(items.map((item) => item.model).filter(Boolean)).size;

  return (
    <div className="flex flex-col gap-6">
      <TopNav demoMode={isDemoMode} />

      <div>
        <h1 className="text-[32px] font-semibold leading-tight text-ink">Usage</h1>
        <p className="mt-1 text-[14px] text-ink-secondary">
          Cost and tokens by model and task, last 30 days — real executions only
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Total spend" value={formatUsd(totalCost)} sub="last 30 days" />
        <StatCard label="Total tokens" value={formatCompact(totalTokens)} sub="input + output" />
        <StatCard label="Models in use" value={String(modelCount)} sub="distinct providers/models" />
      </div>

      <UsageTable items={items} />
    </div>
  );
}
