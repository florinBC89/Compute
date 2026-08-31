import Link from "next/link";
import { getEthicals, getMe } from "@/lib/api";
import Sidebar from "@/components/Sidebar";

export const dynamic = "force-dynamic";

// Ethicals list (Agent OS V0.4 slice, "give Ethical a name and a face"): reached
// from the sidebar's "Project" nav item. Same two-pane shell as the chat
// pages (app/page.tsx, app/projects/[projectId]/page.tsx) -- Sidebar plus
// a scrollable main content area -- rather than the older centered-card
// layout, which no other page in this app uses anymore.
export default async function EthicalsPage() {
  const [me, ethicals] = await Promise.all([getMe(), getEthicals()]);

  return (
    <div className="flex h-screen flex-col overflow-hidden sm:flex-row">
      <Sidebar email={me.email} projects={me.projects} currentProjectId={null} />
      <div className="flex-1 overflow-y-auto bg-page">
        <div className="mx-auto max-w-[640px] px-6 py-10 sm:px-8">
          <div className="mb-8 flex items-center justify-between">
            <h1 className="text-[22px] font-semibold text-ink">Ethicals</h1>
            <Link
              href="/ethicals/new"
              className="rounded-pill bg-accent px-5 py-2.5 text-[14px] font-semibold text-white transition-opacity hover:opacity-90"
            >
              New Ethical
            </Link>
          </div>

          {ethicals.length === 0 ? (
            <div className="rounded-card border border-border bg-surface p-8 text-center">
              <p className="text-[14px] text-ink-secondary">
                No Ethicals yet — give one a name and a goal to get started.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {ethicals.map((ethical) => (
                <Link
                  key={ethical.id}
                  href={`/ethicals/${ethical.id}`}
                  className="block rounded-card border border-border bg-surface p-5 shadow-card transition-colors hover:border-accent"
                >
                  <p className="text-[16px] font-semibold text-ink">{ethical.name}</p>
                  {ethical.goal ? (
                    <p className="mt-1 text-[14px] text-ink-secondary">{ethical.goal}</p>
                  ) : null}
                  <p className="mt-3 text-[12px] uppercase tracking-wide text-ink-muted">
                    {ethical.project_name}
                  </p>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
