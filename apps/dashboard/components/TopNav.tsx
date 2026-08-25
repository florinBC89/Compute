import Link from "next/link";
import { isDemoMode } from "@/lib/api";

export default function TopNav() {
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
          CL
        </div>
        <div className="leading-tight">
          <div className="text-[15px] font-semibold text-ink">ComputeLayer</div>
          <div className="text-[12px] text-ink-muted">research-agent</div>
        </div>
      </div>

      <nav className="hidden items-center gap-1 rounded-pill border border-border bg-surface p-1 shadow-card sm:flex">
        <Link
          href="/"
          className="rounded-pill px-4 py-2 text-[13px] font-medium text-ink-secondary hover:bg-page hover:text-ink"
        >
          Runs
        </Link>
        <Link
          href="/metrics"
          className="rounded-pill px-4 py-2 text-[13px] font-medium text-ink-secondary hover:bg-page hover:text-ink"
        >
          Project metrics
        </Link>
      </nav>

      <div className="flex items-center gap-3">
        {isDemoMode ? (
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
