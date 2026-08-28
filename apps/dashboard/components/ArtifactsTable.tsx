import type { ArtifactListItem } from "@/lib/types";
import { formatRelativeTime, formatUsd } from "@/lib/format";

const ARTIFACT_TYPE_STYLE: Record<string, string> = {
  source: "bg-info/10 text-info",
  fact: "bg-good/10 text-good",
  structured_data: "bg-good/10 text-good",
  research_note: "bg-accent-soft text-accent",
  analysis: "bg-accent-soft text-accent",
  draft: "bg-violet/10 text-violet",
  citation: "bg-info/10 text-info",
};

export default function ArtifactsTable({ artifacts }: { artifacts: ArtifactListItem[] }) {
  if (artifacts.length === 0) {
    return (
      <div className="rounded-card border border-border bg-surface p-8 text-center text-[13.5px] text-ink-muted shadow-card">
        No artifacts classified with an artifact_type yet — pass{" "}
        <code className="rounded bg-page px-1.5 py-0.5 font-mono text-[12px]">
          artifact_type=
        </code>{" "}
        to <code className="rounded bg-page px-1.5 py-0.5 font-mono text-[12px]">compute.run</code>{" "}
        to make a computation eligible for cross-model reuse.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-card border border-border bg-surface p-2 shadow-card">
      <div className="min-w-[720px]">
        <div className="grid grid-cols-[1.4fr_0.9fr_1.1fr_0.8fr_0.7fr_0.9fr] gap-3 px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          <span>Artifact</span>
          <span>Type</span>
          <span>Model</span>
          <span>Cost</span>
          <span>Reusable</span>
          <span>Updated</span>
        </div>
        <div className="flex flex-col">
          {artifacts.map((artifact) => (
            <div
              key={artifact.logical_key}
              className="grid grid-cols-[1.4fr_0.9fr_1.1fr_0.8fr_0.7fr_0.9fr] items-center gap-3 rounded-2xl px-4 py-3.5 text-[13px]"
            >
              <span className="flex flex-col">
                <span className="font-medium text-ink">{artifact.name}</span>
                <span className="truncate font-mono text-[11px] text-ink-muted">
                  {artifact.logical_key}
                </span>
              </span>
              <span>
                {artifact.artifact_type ? (
                  <span
                    className={`inline-flex rounded-pill px-2.5 py-1 text-[11px] font-semibold ${
                      ARTIFACT_TYPE_STYLE[artifact.artifact_type] ?? "bg-page text-ink-secondary"
                    }`}
                  >
                    {artifact.artifact_type}
                  </span>
                ) : (
                  <span className="text-ink-muted">—</span>
                )}
              </span>
              <span className="text-ink-secondary">{artifact.model ?? "—"}</span>
              <span className="tabular text-ink">{formatUsd(artifact.cost_usd)}</span>
              <span className={artifact.reusable ? "text-good" : "text-ink-muted"}>
                {artifact.reusable ? "Yes" : "No"}
              </span>
              <span className="tabular text-ink-secondary">
                {formatRelativeTime(artifact.created_at)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
