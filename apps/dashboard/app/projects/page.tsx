import TopNav from "@/components/TopNav";
import StatCard from "@/components/StatCard";
import ArtifactsTable from "@/components/ArtifactsTable";
import { isDemoMode, listArtifacts } from "@/lib/api";
import { formatUsd } from "@/lib/format";

export const dynamic = "force-dynamic";

// Projects (V0.2): the reusable sources, facts, research, analysis and
// drafts a project has accumulated -- the artifact-typed subset of its
// computations, which is what a cross-model switch can actually carry over.
export default async function ProjectsPage() {
  const artifacts = await listArtifacts();

  const byType = new Map<string, number>();
  for (const artifact of artifacts) {
    if (!artifact.artifact_type) continue;
    byType.set(artifact.artifact_type, (byType.get(artifact.artifact_type) ?? 0) + 1);
  }
  const reusableCount = artifacts.filter((a) => a.reusable).length;
  const totalCost = artifacts.reduce((sum, a) => sum + a.cost_usd, 0);

  return (
    <div className="flex flex-col gap-6">
      <TopNav demoMode={isDemoMode} />

      <div>
        <h1 className="text-[32px] font-semibold leading-tight text-ink">Projects</h1>
        <p className="mt-1 text-[14px] text-ink-secondary">
          The reusable sources, facts, research, analysis and drafts this project has built up
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Classified artifacts" value={String(artifacts.length)} sub="have an artifact_type" />
        <StatCard label="Distinct types in use" value={String(byType.size)} sub="of 7 recognized types" />
        <StatCard label="Reusable now" value={String(reusableCount)} sub="not expired or disabled" accentValue />
        <StatCard label="Total recorded cost" value={formatUsd(totalCost)} sub="across classified artifacts" />
      </div>

      <ArtifactsTable artifacts={artifacts} />
    </div>
  );
}
