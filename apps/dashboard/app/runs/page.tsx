import TopNav from "@/components/TopNav";
import RunsTable from "@/components/RunsTable";
import CostSparkline from "@/components/CostSparkline";
import { isDemoMode, listRuns } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function RunsPage() {
  const runs = await listRuns(20);

  return (
    <div className="flex flex-col gap-6">
      <TopNav demoMode={isDemoMode} />

      <div>
        <h1 className="text-[32px] font-semibold leading-tight text-ink">Runs</h1>
        <p className="mt-1 text-[14px] text-ink-secondary">
          {runs.length} recent runs — what Accurate did on each one
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
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
