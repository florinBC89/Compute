"use client";

import { useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";

// apps/website's own URL -- where signing out sends people.
const MARKETING_URL = process.env.NEXT_PUBLIC_MARKETING_URL ?? "http://localhost:3101";

// Same trigger-button + click-outside-to-close pattern as Composer.tsx's
// ModelDropdown. On desktop this row sits against the sidebar's own left
// edge, so it opens sideways (to the right, over the main content, where
// there's actually room) rather than up-and-over the trigger like the
// composer's dropdown. Reused by MobileNav.tsx's full-width overlay too,
// where there's no room to the right at all -- it opens upward there
// instead (see the responsive classes below). Sign out is the only entry
// for now; Sidebar.tsx's own comment already notes there's no other
// account control in the design yet.
export default function AccountMenu({ name }: { name: string }) {
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  // Calls Supabase directly from the browser rather than through a Server
  // Action -- confirmed live (production network panel) that a real,
  // trusted click's Server Action request was silently aborted
  // (net::ERR_ABORTED) before its response ever reached this component,
  // while the exact same call fired from a script always completed. That
  // pointed at Next's own action/transition fetch handling, not at
  // anything in this component's logic, so the fix is to not route this
  // through that machinery at all: a plain browser fetch (what
  // supabase-js's signOut() does here) isn't part of Next's action
  // lifecycle and has nothing to cancel it mid-flight.
  async function handleSignOut() {
    setSigningOut(true);
    const supabase = createClient();
    await supabase.auth.signOut();
    window.location.href = MARKETING_URL;
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title="Account"
        className="flex items-center gap-2 pl-2 pr-8 pt-6 text-[14px] font-medium text-chat-ink"
      >
        <span className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-full bg-accent text-[13px] font-semibold text-white">
          {name.charAt(0)}
        </span>
        {name}
      </button>

      {open ? (
        // z-20: this pops out past the sidebar's own width into ChatThread's
        // area (components/ChatThread.tsx's scrollable column, `position:
        // relative` with no z-index of its own). Without an explicit
        // z-index here, that column still wins hit-testing over this menu
        // wherever the two overlap, even though the menu paints visibly on
        // top -- position:relative with z-index:auto is still a positioned
        // element, and it comes after this one in the DOM, so it was
        // silently swallowing every click landing inside the popover
        // (confirmed live via elementFromPoint: it returned ChatThread's
        // div, not this menu's own button, at the exact same screen point
        // the button visually occupied).
        <div className="absolute bottom-full left-0 z-20 mb-2 w-[160px] rounded-[15px] border border-chat-border-warm bg-chat-warm p-[5px] shadow-[0_8px_24px_rgba(0,0,0,0.08)] sm:bottom-0 sm:left-full sm:mb-0 sm:ml-2">
          <ul>
            <li>
              <button
                type="button"
                onClick={handleSignOut}
                disabled={signingOut}
                className="w-full rounded-[10px] bg-surface px-2 py-1.5 text-left text-[15px] text-chat-ink hover:opacity-80 disabled:opacity-60"
              >
                {signingOut ? "Signing out…" : "Sign out"}
              </button>
            </li>
          </ul>
        </div>
      ) : null}
    </div>
  );
}
