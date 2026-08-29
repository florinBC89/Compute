import { getMe, getProjectJobs } from "@/lib/api";
import ChatThread from "@/components/ChatThread";
import Sidebar from "@/components/Sidebar";

export const dynamic = "force-dynamic";

// V0.3: the chat surface from the "Registered user" Figma flow. A user's
// first-ever message auto-provisions their one project (see
// app.routes.jobs._find_or_create_default_project) -- until then there's
// nothing to fetch, so `me.projects` is empty and the thread starts empty.
export default async function HomePage() {
  const me = await getMe();
  const project = me.projects[0] ?? null;
  const turns = project ? await getProjectJobs(project.id) : [];

  return (
    <div className="flex">
      <Sidebar email={me.email} />
      <ChatThread initialProjectId={project?.id ?? null} initialTurns={turns} />
    </div>
  );
}
