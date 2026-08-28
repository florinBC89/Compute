import Link from "next/link";
import { notFound } from "next/navigation";
import TopNav from "@/components/TopNav";
import RunGraph from "@/components/RunGraph";
import SavingsCard from "@/components/SavingsCard";
import BaselineTable from "@/components/BaselineTable";
import ModelSwitchPreview from "@/components/ModelSwitchPreview";
import { getRun, getRunGraph, isDemoMode } from "@/lib/api";
import { tokenEconomics, costEconomics } from "@/lib/compute";
import { formatCompact, formatUsd, shortId } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function RunDetailPage({ params }: { params: { id: string } }) {
  let run;
  let graph;
  try {
    [run, graph] = await Promise.all([getRun(params.id), getRunGraph(params.id)]);
  } catch {
    notFound();
  }

  const tokens = tokenEconomics(run.input_tokens + run.output_tokens, run.tokens_avoided);
  const cost = costEconomics(run.total_cost_usd, run.saved_usd);
  const computeAvoidedPct = Math.round(tokens.avoidedRatio * 100);

  return (
    <div className="flex flex-col gap-6">
      <TopNav demoMode={isDemoMode} />

      <div>
        <Link href="/runs" className="text-[13px] font-medium text-ink-secondary hover:text-ink">
          ← All runs
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-[26px] font-semibold text-ink">Run #{shortId(run.id)}</h1>
          <span className="rounded-pill bg-good/10 px-2.5 py-1 text-[11px] font-semibold text-good">
            {run.status}
          </span>
          <ModelSwitchPreview runId={run.id} />
        </div>
        <p className="mt-1 text-[13.5px] text-ink-secondary">research-agent / production</p>
      </div>

      <div className="rounded-card bg-surface-raised p-6 text-center shadow-card">
        <div className="tabular text-[42px] font-bold leading-none text-accent">
          {computeAvoidedPct}%
        </div>
        <div className="mt-2 text-[13px] font-semibold uppercase tracking-wide text-white/60">
          Compute avoided
        </div>
      </div>

      <BaselineTable
        rows={[
          { label: "Tokens", data: tokens, format: formatCompact },
          { label: "Cost", data: cost, format: formatUsd },
        ]}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="min-w-0">
          <h2 className="mb-3 px-1 text-[15px] font-semibold text-ink">Computation trace</h2>
          <RunGraph graph={graph} />
          <p className="mt-3 px-1 text-[13px] text-ink-secondary">
            {run.hits} / {run.computations} computations reused · {run.llm_calls_avoided} LLM
            calls avoided
          </p>
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
