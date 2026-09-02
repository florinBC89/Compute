"use client";

import { useState } from "react";
import type { ProjectSummary } from "@/lib/api";

// Sidebar's "Recent" list shows at most this many conversations by default
// -- a long history would otherwise push the account row at the bottom off
// screen. "More"/"Less" toggles the rest, rather than a separate page or a
// permanently scrollable list. The mobile overlay opts out via `capped`
// (below) -- its later Figma update scrolls as one continuous panel
// instead, so there's no fixed-height footer for a long list to collide
// with.
const VISIBLE_COUNT = 6;

// Caps a conversation name at 3 words for the nav list (Figma's later
// mobile update) -- long titles otherwise wrapped or got clipped mid-word
// by the CSS `truncate` ellipsis; this keeps the cut at a word boundary
// and predictable regardless of column width.
function truncateName(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length <= 3) return name;
  return `${words.slice(0, 3).join(" ")}...`;
}

export default function RecentConversations({
  projects,
  currentProjectId,
  capped = true,
}: {
  projects: ProjectSummary[];
  currentProjectId: string | null;
  //: Desktop keeps the VISIBLE_COUNT cap + More/Less toggle (a tall,
  //: uncapped list would push the account row off the bottom of its
  //: fixed-height sidebar). MobileNav.tsx's overlay passes capped=false
  //: to just list everything -- the whole panel scrolls together there,
  //: so there's no fixed footer for a long list to push off screen.
  capped?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  // Pins the active conversation to the top of the list instead of leaving
  // it wherever it falls chronologically -- otherwise it could sit past
  // VISIBLE_COUNT (hidden behind "More") or require scrolling to spot,
  // even though it's the one conversation you already know you're in.
  const ordered = currentProjectId
    ? [
        ...projects.filter((p) => p.id === currentProjectId),
        ...projects.filter((p) => p.id !== currentProjectId),
      ]
    : projects;
  const visible = !capped || expanded ? ordered : ordered.slice(0, VISIBLE_COUNT);
  const hasMore = capped && ordered.length > VISIBLE_COUNT;

  return (
    <div className={`flex flex-col gap-0.5 ${capped ? "overflow-y-auto" : ""}`}>
      {visible.map((project) => (
        <a
          key={project.id}
          href={`/projects/${project.id}`}
          title={project.name}
          className={`truncate rounded-[6px] px-3 py-[3px] text-[20px] sm:text-[14px] ${
            project.id === currentProjectId
              ? "bg-surface font-medium text-chat-ink"
              : "text-chat-ink-soft hover:bg-white/50"
          }`}
        >
          {truncateName(project.name)}
        </a>
      ))}
      {hasMore ? (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-1.5 rounded-[6px] px-3 py-[3px] text-[14px] text-chat-label hover:bg-white/50"
        >
          {expanded ? "Less" : "More"}
          <img
            src="/icons/chevron-down.svg"
            alt=""
            className={`h-[5.5px] w-[9.5px] transition-transform ${expanded ? "rotate-180" : ""}`}
          />
        </button>
      ) : null}
    </div>
  );
}
