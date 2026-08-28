"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_LINKS = [
  { href: "/", label: "Overview" },
  { href: "/runs", label: "Runs" },
  { href: "/projects", label: "Projects" },
  { href: "/usage", label: "Usage" },
];

// demoMode is passed in rather than imported from lib/api: this is a client
// component, and importing that module here would pull its server-only env
// var reads into the browser bundle, where they always read as undefined.
export default function TopNav({ demoMode = false }: { demoMode?: boolean }) {
  const pathname = usePathname();

  return (
    <header className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label="Menu"
          className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-surface text-ink shadow-card"
        >
          <svg width="16" height="12" viewBox="0 0 16 12" fill="none">
            <path d="M0 1h16M0 6h16M0 11h16" stroke="currentColor" strokeWidth="1.6" />
          </svg>
        </button>
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-surface-raised text-[13px] font-bold text-white">
          A
        </div>
        <div className="leading-tight">
          <div className="text-[15px] font-semibold text-ink">Accurate</div>
          <div className="text-[12px] text-ink-muted">research-agent / production</div>
        </div>
      </div>

      <nav className="hidden items-center gap-1 rounded-pill border border-border bg-surface p-1 shadow-card sm:flex">
        {NAV_LINKS.map((link) => {
          const active = link.href === "/" ? pathname === "/" : pathname?.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`rounded-pill px-4 py-2 text-[13px] font-medium transition-colors ${
                active ? "bg-surface-raised text-white" : "text-ink-secondary hover:bg-page hover:text-ink"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>

      <div className="flex items-center gap-3">
        {demoMode ? (
          <span className="hidden rounded-pill border border-accent/30 bg-accent-soft px-3 py-1.5 text-[11px] font-semibold text-accent md:inline-block">
            Demo data — no API connected
          </span>
        ) : null}
        <div className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-surface text-ink-secondary shadow-card">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="7" cy="7" r="5.2" stroke="currentColor" strokeWidth="1.4" />
            <path d="M11 11L14.5 14.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
        </div>
      </div>
    </header>
  );
}
