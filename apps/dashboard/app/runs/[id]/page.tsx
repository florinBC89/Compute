import Link from "next/link";
import { notFound } from "next/navigation";
import TopNav from "@/components/TopNav";
import RunGraph from "@/components/RunGraph";
import SavingsCard from "@/components/SavingsCard";
import StatCard from "@/components/StatCard";
import { getRun, getRunGraph } from "@/lib/api";
import { formatUsd, shortId } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function RunDetailPage({ params }: { params: { id: string } }) {
  let run;
  let graph;
  try {
    [run, graph] = await Promise.all([getRun(params.id), getRunGraph(params.id)]);
  } catch {
    notFound();
  }

  const reuseRate = run.computations > 0 ? run.hits / run.computations : 0;

  return (
    <div className="flex flex-col gap-6">
      <TopNav />

      <div>
        <Link href="/" className="text-[13px] font-medium text-ink-secondary hover:text-ink">
          ← All runs
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-[26px] font-semibold text-ink">{shortId(run.id)}</h1>
          <span className="rounded-pill bg-good/10 px-2.5 py-1 text-[11px] font-semibold text-good">
            {run.status}
          </span>
        </div>
        <p className="mt-1 text-[13.5px] text-ink-secondary">
          {run.computations} computations · {run.hits} HIT · {run.misses} MISS · {run.stale} STALE
          {run.forced ? ` · ${run.forced} FORCED` : ""}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Reuse rate" value={`${Math.round(reuseRate * 100)}%`} accentValue />
        <StatCard label="Cost" value={formatUsd(run.total_cost_usd)} />
        <StatCard label="Saved" value={formatUsd(run.saved_usd)} sub="vs. no reuse" />
        <StatCard
          label="Tokens"
          value={new Intl.NumberFormat("en-US", { notation: "compact" }).format(
            run.input_tokens + run.output_tokens
          )}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="min-w-0">
          <h2 className="mb-3 px-1 text-[15px] font-semibold text-ink">Computation graph</h2>
          <RunGraph graph={graph} />
        </div>
        <SavingsCard
          costUsd={run.total_cost_usd}
          savedUsd={run.saved_usd}
          tokens={run.input_tokens + run.output_tokens}
        />
      </div>
    </div>
  );
}
