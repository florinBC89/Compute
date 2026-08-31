import AccountMenu from "@/components/AccountMenu";
import RecentConversations from "@/components/RecentConversations";
import type { ProjectSummary } from "@/lib/api";

// The sidebar nav from the V0.3 Figma design ("Registered user" flow).
// "New" (start a fresh conversation) and "Project" (Ethicals list, Agent OS
// V0.4 slice -- see app/ethicals/page.tsx) are functional -- Reports/Overview/
// Support have no backing page yet, so they render as static labels
// rather than dead links. The account row opens a small menu (see
// AccountMenu.tsx) whose only entry is sign out, since there's no other
// account control in the design yet.
const NAV_ITEMS = [
  { href: "/", label: "New", icon: "/icons/nav-new.svg" },
  { href: "/ethicals", label: "Project", icon: "/icons/nav-chart.svg" },
  { href: null, label: "Reports", icon: "/icons/nav-reports.svg" },
  { href: null, label: "Overview", icon: "/icons/nav-chart.svg" },
] as const;

function displayName(email: string): string {
  const local = email.split("@")[0] ?? email;
  // Take the leading run of letters only -- "bostan.florin89" -> "bostan",
  // not the raw local-part with its dot/digits still attached. No user
  // metadata/display name exists in GET /me today, so this is a heuristic,
  // not a real name.
  const lettersOnly = local.match(/^[A-Za-z]+/)?.[0] || local;
  return lettersOnly.charAt(0).toUpperCase() + lettersOnly.slice(1);
}

export default function Sidebar({
  email,
  projects,
  currentProjectId,
}: {
  email: string;
  //: V0.3 conversation history -- a conversation IS a Project (see
  //: apps/api/app/routes/jobs.py's _resolve_or_create_project). Already
  //: ordered most-recent-first by GET /me.
  projects: ProjectSummary[];
  currentProjectId: string | null;
}) {
  const name = displayName(email);

  return (
    <aside className="flex h-full w-[179px] shrink-0 flex-col bg-chat-warm">
      <div className="px-5 pb-[54px] pt-8">
        <img src="/logo.svg" alt="Accurate" className="h-[19px] w-auto" />
      </div>
      <nav className="flex flex-col gap-0.5 pl-[6px] pr-4">
        {NAV_ITEMS.map((item) =>
          item.href ? (
            <a
              key={item.label}
              href={item.href}
              className="flex items-center gap-2 rounded-[6px] px-3 py-2 text-[16px] text-chat-ink hover:bg-white/50"
            >
              <img src={item.icon} alt="" className="h-5 w-5" />
              {item.label}
            </a>
          ) : (
            <span
              key={item.label}
              className="flex items-center gap-2 rounded-[6px] px-3 py-2 text-[16px] text-chat-ink opacity-60"
            >
              <img src={item.icon} alt="" className="h-5 w-5" />
              {item.label}
            </span>
          )
        )}
      </nav>

      {projects.length > 0 ? (
        <div className="mt-6 flex min-h-0 flex-1 flex-col pl-[6px] pr-4">
          <span className="px-3 pb-1.5 text-[12px] font-semibold uppercase tracking-wide text-chat-label">
            Recent
          </span>
          <RecentConversations projects={projects} currentProjectId={currentProjectId} />
        </div>
      ) : (
        <div className="flex-1" />
      )}

      <div className="flex flex-col gap-6 pl-[6px] pr-4 pb-[26px]">
        <div className="flex flex-col gap-1">
          <span className="flex items-center gap-2 px-3 py-2 text-[16px] text-chat-ink opacity-60">
            <img src="/icons/nav-support.svg" alt="" className="h-5 w-5" />
            Support
          </span>
          <span className="flex items-center gap-2 px-3 py-2 text-[16px] text-chat-ink opacity-60">
            <img src="/icons/nav-settings.svg" alt="" className="h-5 w-5" />
            Settings
          </span>
        </div>
        <AccountMenu name={name} />
      </div>
    </aside>
  );
}
