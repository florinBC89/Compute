import { getMe } from "@/lib/api";
import ChatThread from "@/components/ChatThread";
import Sidebar from "@/components/Sidebar";

export const dynamic = "force-dynamic";

// V0.3: the chat surface from the "Registered user" Figma flow. "/" is
// always a fresh, blank conversation -- both the true empty-workspace
// state AND exactly what the sidebar's "New" link should do, so "New"
// linking here needs no separate route or redirect logic. An existing
// conversation is only ever reached via the sidebar's "Recent" list, at
// /projects/[projectId].
export default async function HomePage() {
  const me = await getMe();

  return (
    <div className="flex h-dvh flex-col overflow-hidden sm:flex-row">
      <Sidebar email={me.email} projects={me.projects} currentProjectId={null} />
      <ChatThread initialProjectId={null} initialTurns={[]} initialTitle={null} />
    </div>
  );
}
