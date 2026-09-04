import { getMe, getProjectJobs } from "@/lib/api";
import ChatThread from "@/components/ChatThread";
import Sidebar from "@/components/Sidebar";

export const dynamic = "force-dynamic";

// V0.3 conversation history: a specific existing conversation, reached via
// the sidebar's "Recent" list (a conversation IS a Project -- see
// apps/api/app/routes/jobs.py's _resolve_or_create_project). Replaces the
// old V0.2 Phase 6 artifact-tree view, which is now largely superseded by
// each turn's own "Compute details" panel (see ResultScreen.tsx) -- this
// route had no incoming links left once TaskRunner was replaced by
// ChatThread earlier in V0.3.
//
// Ownership is enforced server-side (getProjectJobs -> GET /workspace/
// projects/{id}/jobs -> app.routes.workspace._owned_project): a project_id
// belonging to another workspace 404s, caught by the app's error.tsx.
export default async function ProjectPage({
  params,
}: {
  params: { projectId: string };
}) {
  const me = await getMe();
  const turns = await getProjectJobs(params.projectId);
  const project = me.projects.find((p) => p.id === params.projectId);
  //: Drives which sidebar tab/toggle position this conversation opens
  //: into, so a build project reliably shows up (and stays highlighted)
  //: under Build's own Recent list rather than defaulting to Chat's on
  //: every visit -- see Sidebar.tsx's per-mode filtering.
  const initialMode = project?.kind ?? "chat";

  return (
    <div className="flex h-dvh flex-col overflow-hidden sm:flex-row">
      <Sidebar
        email={me.email}
        projects={me.projects}
        currentProjectId={params.projectId}
        initialMode={initialMode}
      />
      <ChatThread
        initialProjectId={params.projectId}
        initialTurns={turns}
        initialTitle={project?.name ?? null}
        initialMode={initialMode}
      />
    </div>
  );
}
