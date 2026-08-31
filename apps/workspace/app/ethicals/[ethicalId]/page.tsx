import { getEthical, getMe } from "@/lib/api";
import type { EthicalWorkItem, WorkReuseLabel } from "@/lib/api";
import Sidebar from "@/components/Sidebar";

export const dynamic = "force-dynamic";

function formatUsd(value: number): string {
  return `$${value.toFixed(value < 0.01 ? 4 : 2)}`;
}

const REUSE_LABEL_TEXT: Record<WorkReuseLabel, string> = {
  reused: "Reused",
  partially_reused: "Partially reused",
  fresh: "Fresh",
};

const REUSE_LABEL_CLASSES: Record<WorkReuseLabel, string> = {
  reused: "bg-good/10 text-good",
  partially_reused: "bg-warning/10 text-warning",
  fresh: "bg-ink-muted/10 text-ink-muted",
};

function WorkStatusPill({ item }: { item: EthicalWorkItem }) {
  if (item.reuse_label) {
    return (
      <span
        className={`rounded-pill px-2.5 py-1 text-[12px] font-medium ${REUSE_LABEL_CLASSES[item.reuse_label]}`}
      >
        {REUSE_LABEL_TEXT[item.reuse_label]}
      </span>
    );
  }
  return (
    <span className="rounded-pill bg-ink-muted/10 px-2.5 py-1 text-[12px] font-medium text-ink-muted">
      {item.status === "QUEUED" ? "Queued" : item.status === "RUNNING" ? "Running" : item.status}
    </span>
  );
}

// Ethical detail (Agent OS V0.4 slice, "give Ethical a name and a face"): identity
// up top, then its "Work" -- the linked Project's Jobs (see
// apps/api/app/services/ethicals.py), each labeled from the same run totals
// the chat thread's result screen already computes, not a new pipeline.
// A missing/unauthorized Ethical throws in getEthical and is caught by this app's
// root error.tsx, same as every other server-rendered page here.
export default async function EthicalDetailPage({
  params,
}: {
  params: { ethicalId: string };
}) {
  const [me, ethical] = await Promise.all([getMe(), getEthical(params.ethicalId)]);

  return (
    <div className="flex h-screen flex-col overflow-hidden sm:flex-row">
      <Sidebar email={me.email} projects={me.projects} currentProjectId={null} />
      <div className="flex-1 overflow-y-auto bg-page">
        <div className="mx-auto max-w-[640px] px-6 py-10 sm:px-8">
          <div className="rounded-card border border-border bg-surface p-8 shadow-card">
            <p className="text-[12px] uppercase tracking-wide text-ink-muted">
              {ethical.project_name}
            </p>
            <h1 className="mt-1 text-[22px] font-semibold text-ink">{ethical.name}</h1>
            {ethical.goal ? (
              <p className="mt-2 text-[14px] text-ink-secondary">{ethical.goal}</p>
            ) : (
              <p className="mt-2 text-[14px] text-ink-muted">No goal set.</p>
            )}
          </div>

          <h2 className="mb-3 mt-8 text-[15px] font-semibold text-ink">Work</h2>
          {ethical.work.length === 0 ? (
            <div className="rounded-card border border-border bg-surface p-8 text-center">
              <p className="text-[14px] text-ink-secondary">No work yet.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {ethical.work.map((item) => (
                <div
                  key={item.job_id}
                  className="flex items-center justify-between gap-4 rounded-card border border-border bg-surface px-5 py-4"
                >
                  <p className="min-w-0 flex-1 truncate text-[14px] text-ink">{item.task_text}</p>
                  <div className="flex shrink-0 items-center gap-3">
                    {item.reuse_label ? (
                      <span className="text-[13px] tabular-nums text-ink-secondary">
                        {formatUsd(item.cost_usd)}
                        {item.saved_usd > 0 ? (
                          <span className="text-good"> · saved {formatUsd(item.saved_usd)}</span>
                        ) : null}
                      </span>
                    ) : null}
                    <WorkStatusPill item={item} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
