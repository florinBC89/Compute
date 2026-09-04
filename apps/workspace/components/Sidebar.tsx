"use client";

import { useState } from "react";
import AccountMenu from "@/components/AccountMenu";
import MobileNav from "@/components/MobileNav";
import RecentConversations from "@/components/RecentConversations";
import type { ProjectSummary } from "@/lib/api";

export type WorkspaceMode = "chat" | "build";

// The sidebar nav from the V0.3 Figma design ("Registered user" flow),
// extended with the Chat/Build toggle (Figma node 156:2574). "New Chat"
// (start a fresh conversation) and "Project" (Ethicals list, Agent OS V0.4
// slice -- see app/ethicals/page.tsx) are functional -- Reports/Overview/
// Support have no backing page yet, so they render as static labels rather
// than dead links. The account row opens a small menu (see AccountMenu.tsx)
// whose only entry is sign out, since there's no other account control in
// the design yet. Exported so MobileNav.tsx's slide-out overlay (the mobile
// Figma variant of this same nav) uses the identical lists rather than a
// second copy that could drift.
export const NAV_ITEMS = [
  { href: "/", label: "New Chat", icon: "/icons/nav-new-chat.svg" },
  { href: "/ethicals", label: "Project", icon: "/icons/nav-chart.svg" },
  { href: null, label: "Reports", icon: "/icons/nav-reports.svg" },
  { href: null, label: "Overview", icon: "/icons/nav-chart.svg" },
] as const;

// Build mode (Figma node 155:2397): a single "New Project" entry, no
// Project/Reports/Overview -- the Figma reference also mocks up a bigger
// "agent orchestration" landing (parallel Backend/Frontend/Security agent
// cards, a "Do It Later" control, a background-task counter) that has no
// backend behind it yet, so it isn't built here. What IS real: "New
// Project" opens the same chat composer as "New Chat", just flagged
// ?mode=build so app/page.tsx shows build-flavored copy, defaults Lazy
// mode on (see ChatThread.tsx), and tags the new conversation's
// Project.kind "build" (see app.routes.jobs.create_job) so it's the one
// that shows up under this tab's own Recent list, not Chat's.
export const BUILD_NAV_ITEMS = [
  { href: "/?mode=build", label: "New Project", icon: "/icons/nav-new-project.svg" },
] as const;

//: Exported alongside NAV_ITEMS -- MobileNav.tsx's account row needs the
//: identical name for the identical user, not a second heuristic that
//: could produce a different result.
export function displayName(email: string): string {
  const local = email.split("@")[0] ?? email;
  // Take the leading run of letters only -- "bostan.florin89" -> "bostan",
  // not the raw local-part with its dot/digits still attached. No user
  // metadata/display name exists in GET /me today, so this is a heuristic,
  // not a real name.
  const lettersOnly = local.match(/^[A-Za-z]+/)?.[0] || local;
  return lettersOnly.charAt(0).toUpperCase() + lettersOnly.slice(1);
}

// Chat/Build segmented control (Figma node 155:2383 / 156:2575): each
// option's ACTIVE fill is a different color by design -- Chat's is
// --chat-ink-strong (near-black), Build's is --chat-accent-strong (the
// app's orange) -- not the usual single-accent toggle. Exported so
// MobileNav.tsx's overlay renders the identical control rather than a
// second copy that could drift out of sync with this styling.
export function ChatBuildToggle({
  mode,
  onChange,
  //: "lg" (Figma node 158:2762/158:2768, mobile's overlay menu) is a
  //: genuinely bigger control -- 48px/20px text, not just a scaled-up
  //: "sm" (the 36px/13px desktop version, node 155:2383/156:2575) -- so
  //: this is a real size prop, not a responsive className.
  size = "sm",
}: {
  mode: WorkspaceMode;
  onChange: (mode: WorkspaceMode) => void;
  size?: "sm" | "lg";
}) {
  const options: { value: WorkspaceMode; label: string; activeClass: string }[] = [
    { value: "chat", label: "Chat", activeClass: "bg-chat-ink-strong" },
    { value: "build", label: "Build", activeClass: "bg-chat-accent-strong" },
  ];
  const sizeClass = size === "lg" ? "h-10 px-5 text-[20px]" : "h-7 px-2.5 text-[13px]";
  return (
    <div className="inline-flex items-center gap-0.5 rounded-pill bg-white p-1">
      {options.map((option) => {
        const active = option.value === mode;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`flex items-center justify-center rounded-pill ${sizeClass} ${
              active ? `${option.activeClass} font-medium text-white` : "font-normal text-chat-label"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export default function Sidebar({
  email,
  projects,
  currentProjectId,
  //: Which nav-item set + toggle position to render on first paint --
  //: driven by the URL (?mode=build), not just a locally-remembered
  //: default, so a hard reload or a link landing on ?mode=build shows the
  //: right state instead of always resetting to Chat. See app/page.tsx.
  initialMode = "chat",
}: {
  email: string;
  //: V0.3 conversation history -- a conversation IS a Project (see
  //: apps/api/app/routes/jobs.py's _resolve_or_create_project). Already
  //: ordered most-recent-first by GET /me.
  projects: ProjectSummary[];
  currentProjectId: string | null;
  initialMode?: WorkspaceMode;
}) {
  const name = displayName(email);
  const [mode, setMode] = useState<WorkspaceMode>(initialMode);
  const navItems = mode === "chat" ? NAV_ITEMS : BUILD_NAV_ITEMS;
  //: Chat's Recent shows chat conversations, Build's shows build projects
  //: -- the whole point of the toggle (see BUILD_NAV_ITEMS' comment). The
  //: CURRENT conversation stays visible even if its own kind doesn't match
  //: -- e.g. a fresh visit here before the toggle's initialMode syncs to
  //: it -- so viewing an open conversation never makes it vanish from its
  //: own sidebar.
  const visibleProjects = projects.filter(
    (p) => p.kind === mode || p.id === currentProjectId
  );

  return (
    <>
      <MobileNav
        email={email}
        projects={projects}
        currentProjectId={currentProjectId}
        initialMode={initialMode}
      />
      <aside className="hidden h-full w-[179px] shrink-0 flex-col bg-chat-warm sm:flex">
      <div className="flex flex-col items-center gap-6 px-5 pb-6 pt-8">
        <img src="/logo.svg" alt="Accurate" className="h-[19px] w-auto self-start" />
        <ChatBuildToggle mode={mode} onChange={setMode} />
      </div>
      <nav className="flex flex-col gap-0.5 pl-[6px] pr-4">
        {navItems.map((item) =>
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

      {visibleProjects.length > 0 ? (
        <div className="mt-6 flex min-h-0 flex-1 flex-col pl-[6px] pr-4">
          <span className="px-3 pb-1.5 text-[12px] font-semibold uppercase tracking-wide text-chat-label">
            Recent
          </span>
          <RecentConversations projects={visibleProjects} currentProjectId={currentProjectId} />
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
    </>
  );
}
