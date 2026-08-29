import Link from "next/link";
import { getProjectArtifacts, type Artifact, type ArtifactType } from "@/lib/api";

export const dynamic = "force-dynamic";

// Phase 6 (V0.2 human workspace): the project view from the spec's "AI NEWS
// PROJECT" tree -- sources, facts, research, analysis and drafts a project
// has built up, grouped exactly the way the spec's mockup groups them.
const SECTION_LABELS: Record<ArtifactType, string> = {
  source: "Sources",
  fact: "Facts",
  structured_data: "Data",
  research_note: "Research",
  analysis: "Analysis",
  draft: "Drafts",
  citation: "Citations",
};

const SECTION_ORDER: ArtifactType[] = [
  "source",
  "fact",
  "research_note",
  "structured_data",
  "analysis",
  "draft",
  "citation",
];

function groupByType(artifacts: Artifact[]): Map<ArtifactType, Artifact[]> {
  const groups = new Map<ArtifactType, Artifact[]>();
  for (const artifact of artifacts) {
    if (!artifact.artifact_type) continue;
    const list = groups.get(artifact.artifact_type) ?? [];
    list.push(artifact);
    groups.set(artifact.artifact_type, list);
  }
  return groups;
}

export default async function ProjectPage({
  params,
}: {
  params: { projectId: string };
}) {
  const artifacts = await getProjectArtifacts(params.projectId);
  const groups = groupByType(artifacts);

  return (
    <div className="mx-auto min-h-screen max-w-[720px] px-6 py-8 sm:px-8">
      <div className="flex items-center justify-between">
        <h1 className="text-[20px] font-semibold text-ink">This project</h1>
        <Link href="/" className="text-[13px] text-ink-muted hover:text-ink">
          &larr; Back
        </Link>
      </div>
      <p className="mt-1 text-[14px] text-ink-secondary">
        Everything reusable this project has built up so far.
      </p>

      {artifacts.length === 0 ? (
        <div className="mt-8 rounded-card border border-border bg-surface p-8 text-center">
          <p className="text-[14px] text-ink-secondary">Nothing here yet.</p>
        </div>
      ) : (
        <div className="mt-8 flex flex-col gap-6">
          {SECTION_ORDER.filter((type) => groups.has(type)).map((type) => (
            <section key={type}>
              <h2 className="text-[12px] font-semibold uppercase tracking-wide text-ink-muted">
                {SECTION_LABELS[type]}
              </h2>
              <ul className="mt-2 flex flex-col gap-2">
                {groups.get(type)!.map((artifact) => (
                  <li
                    key={artifact.logical_key}
                    className="flex items-center justify-between rounded-2xl border border-border bg-surface px-4 py-3"
                  >
                    <div>
                      <div className="text-[14px] text-ink">{artifact.name}</div>
                      <div className="mt-0.5 text-[12px] text-ink-muted">
                        {artifact.model ?? "no model"} &middot;{" "}
                        {artifact.reusable ? "reusable" : "not reusable"}
                      </div>
                    </div>
                    <div className="tabular text-[13px] text-ink-secondary">
                      ${artifact.cost_usd.toFixed(4)}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
