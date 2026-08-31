"use client";

import { useState } from "react";
import AccountMenu from "@/components/AccountMenu";
import { NAV_ITEMS, displayName } from "@/components/Sidebar";
import RecentConversations from "@/components/RecentConversations";
import type { ProjectSummary } from "@/lib/api";

// The mobile variant of Sidebar.tsx's nav (Figma "Mobile layout" header +
// "Navigation menu mobile" overlay frames): a slim logo+hamburger bar,
// always visible below the sm breakpoint (Sidebar.tsx's own <aside> stays
// hidden there), that opens a full-screen panel with the same nav items,
// Recent conversations, and account row as the desktop sidebar -- same
// content, reusing the same NAV_ITEMS/displayName/RecentConversations/
// AccountMenu, just laid out full-width instead of in a 179px column.
export default function MobileNav({
  email,
  projects,
  currentProjectId,
}: {
  email: string;
  projects: ProjectSummary[];
  currentProjectId: string | null;
}) {
  const [open, setOpen] = useState(false);
  const name = displayName(email);

  return (
    <>
      <div className="flex shrink-0 items-center justify-between bg-page px-[26px] py-4 sm:hidden">
        <img src="/icons/logo-mark.svg" alt="Accurate" className="h-8 w-auto" />
        <button
          type="button"
          onClick={() => setOpen(true)}
          title="Menu"
          className="flex h-8 w-8 items-center justify-center"
        >
          <img src="/icons/nav-menu.svg" alt="" className="h-[17px] w-[21px]" />
        </button>
      </div>

      {open ? (
        <div className="fixed inset-0 z-50 flex flex-col bg-chat-warm sm:hidden">
          <div className="flex items-center justify-between px-[26px] pb-6 pt-8">
            <img src="/icons/logo-mark.svg" alt="Accurate" className="h-8 w-auto" />
            <button
              type="button"
              onClick={() => setOpen(false)}
              title="Close menu"
              className="flex h-8 w-8 items-center justify-center"
            >
              <img src="/icons/nav-close.svg" alt="" className="h-6 w-6 rotate-45" />
            </button>
          </div>

          <nav className="flex flex-col gap-0.5 px-[22px]">
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
            <div className="mt-6 flex min-h-0 flex-1 flex-col px-[22px]">
              <span className="px-3 pb-1.5 text-[12px] font-semibold uppercase tracking-wide text-chat-label">
                Recent
              </span>
              <RecentConversations projects={projects} currentProjectId={currentProjectId} />
            </div>
          ) : (
            <div className="flex-1" />
          )}

          <div className="flex flex-col gap-6 px-[22px] pb-[26px]">
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
        </div>
      ) : null}
    </>
  );
}
