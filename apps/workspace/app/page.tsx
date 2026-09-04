import { getMe } from "@/lib/api";
import ChatThread from "@/components/ChatThread";
import Sidebar from "@/components/Sidebar";

export const dynamic = "force-dynamic";

// V0.3: the chat surface from the "Registered user" Figma flow. "/" is
// always a fresh, blank conversation -- both the true empty-workspace
// state AND exactly what the sidebar's "New Chat" link should do, so
// "New Chat" linking here needs no separate route or redirect logic. An
// existing conversation is only ever reached via the sidebar's "Recent"
// list, at /projects/[projectId].
//
// ?mode=build (the sidebar's "New Project" link, Build mode) reuses this
// exact same route rather than a separate one -- there's no backend
// concept of a "build" project distinct from a chat conversation yet (see
// Sidebar.tsx's BUILD_NAV_ITEMS comment), so this just flags the initial
// render: Sidebar shows the Build-active toggle/nav, and ChatThread shows
// build-flavored empty-state copy with Lazy mode defaulted on.
export default async function HomePage({
  searchParams,
}: {
  //: Plain object, not a Promise -- this is Next.js 14 (searchParams only
  //: became a Promise in the Next.js 15 App Router).
  searchParams: { mode?: string };
}) {
  const me = await getMe();
  const initialMode = searchParams.mode === "build" ? "build" : "chat";

  return (
    <div className="flex h-dvh flex-col overflow-hidden sm:flex-row">
      <Sidebar
        email={me.email}
        projects={me.projects}
        currentProjectId={null}
        initialMode={initialMode}
      />
      <ChatThread
        initialProjectId={null}
        initialTurns={[]}
        initialTitle={null}
        initialMode={initialMode}
      />
    </div>
  );
}
