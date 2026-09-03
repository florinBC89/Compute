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
      {/* Back to a plain solid shrink-0 bar (no `fixed`, no translucency/
          blur on the header itself) -- the fade is a separate, simple
          color-gradient child instead, the exact technique ChatThread.tsx
          already uses for the desktop title bar (`top-full h-20
          from-page to-transparent`) and for the composer's own fade
          above it on mobile (`-top-16 h-16 from-transparent to-page`).
          No scroll-gating needed here either, matching that composer
          fade -- it's a plain color fade, not a heavy blur, so it reads
          fine even over the very first bit of a fresh thread. */}
      <div className="relative flex shrink-0 items-center justify-between bg-page px-[26px] py-4 sm:hidden">
        <img src="/icons/logo-mark.svg" alt="Accurate" className="h-8 w-auto" />
        <button
          type="button"
          onClick={() => setOpen(true)}
          title="Menu"
          className="flex h-8 w-8 items-center justify-center"
        >
          <img src="/icons/nav-menu.svg" alt="" className="h-[17px] w-[21px]" />
        </button>
        {/* z-10: this extends past the header's own box into ChatThread's
            space (a separate sibling component, not a descendant) --
            without an explicit z-index, its paint order versus
            ChatThread's own `position: relative` root is just DOM order,
            and ChatThread comes later, which risked painting on top of
            (hiding) this fade instead of the other way around. */}
        <div className="pointer-events-none absolute inset-x-0 top-full z-10 h-16 bg-gradient-to-b from-page to-transparent" />
      </div>

      {open ? (
        <div className="fixed inset-0 z-50 flex flex-col bg-chat-warm sm:hidden">
          <div className="relative flex items-center justify-between px-[26px] pb-6 pt-8">
            <img src="/icons/logo-mark.svg" alt="Accurate" className="h-8 w-auto" />
            <button
              type="button"
              onClick={() => setOpen(false)}
              title="Close menu"
              className="flex h-8 w-8 items-center justify-center"
            >
              <img src="/icons/nav-close.svg" alt="" className="h-6 w-6 rotate-45" />
            </button>
            {/* Same plain color-fade technique as the collapsed header
                above -- from-chat-warm here, not from-page, to match this
                panel's own background. A sibling of the scrollable list
                below (not a cross-component overlay like the collapsed
                header's version), so no z-index fight with anything else
                unstyled here -- still explicit for consistency/safety. */}
            <div className="pointer-events-none absolute inset-x-0 top-full z-10 h-16 bg-gradient-to-b from-chat-warm to-transparent" />
          </div>

          {/* Nav items + Recent now scroll together as one panel (Figma's
              later mobile update) instead of Recent being a separate
              fixed-height, internally-capped section -- pb-24 leaves
              clearance so the last few scrolled items don't end up
              permanently hidden behind the floating avatar below. */}
          <div className="flex-1 overflow-y-auto pb-24">
            <nav className="flex flex-col gap-2.5 px-[42px]">
              {NAV_ITEMS.map((item) =>
                item.href ? (
                  <a
                    key={item.label}
                    href={item.href}
                    className="flex items-center gap-2 rounded-[6px] px-3 py-2 text-[22px] text-chat-ink hover:bg-white/50"
                  >
                    <img src={item.icon} alt="" className="h-5 w-5" />
                    {item.label}
                  </a>
                ) : (
                  <span
                    key={item.label}
                    className="flex items-center gap-2 rounded-[6px] px-3 py-2 text-[22px] text-chat-ink opacity-60"
                  >
                    <img src={item.icon} alt="" className="h-5 w-5" />
                    {item.label}
                  </span>
                )
              )}
            </nav>

            {projects.length > 0 ? (
              <div className="mt-6 flex flex-col px-[22px]">
                <span className="px-3 pb-1.5 text-[16px] text-chat-label">Recent</span>
                {/* capped=false: no VISIBLE_COUNT/More cutoff here -- a
                    long history just runs on below the fold as part of
                    this same scroll, per the later Figma update. */}
                <RecentConversations
                  projects={projects}
                  currentProjectId={currentProjectId}
                  capped={false}
                />
              </div>
            ) : null}
          </div>

          {/* Same fade, mirrored, at the panel's bottom edge -- pinned to
              the whole overlay (not the scroll region specifically) for
              the same reason as the avatar below: this position is
              already the true bottom of the screen since nothing else
              is fixed below the scrollable list, so it doesn't need to
              track scroll offset itself, just sit where scrolled content
              disappears. z-[5]: above the scrollable list (z-index:auto)
              but below the avatar's own z-10, so the avatar itself never
              gets faded. */}
          <div className="pointer-events-none absolute inset-x-0 bottom-0 z-[5] h-16 bg-gradient-to-b from-transparent to-chat-warm" />
          {/* Bare avatar (no name, no Support/Settings rows -- dropped
              from this later Figma update), pinned to the overlay's
              bottom-right corner regardless of how far the panel above
              scrolls. absolute + the overlay's own `fixed inset-0`
              ancestor, rather than CSS `sticky`, since it needs to float
              OVER the scrolling list, not push/reserve space within it. */}
          <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 flex justify-end p-[22px]">
            <div className="pointer-events-auto">
              <AccountMenu name={name} compact />
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
