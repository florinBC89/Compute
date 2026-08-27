import type { CacheStatus } from "@/lib/types";

// Product language (per the Accurate spec): "Reused / Computed / Changed",
// never "Cache Hit / Cache Miss" -- HIT/MISS/STALE are the wire format only.
const STYLES: Record<CacheStatus, { bg: string; fg: string; icon: string; label: string }> = {
  HIT: { bg: "bg-good/10", fg: "text-good", icon: "✓", label: "REUSED" },
  MISS: { bg: "bg-info/10", fg: "text-info", icon: "+", label: "COMPUTED" },
  STALE: { bg: "bg-warning/15", fg: "text-warning", icon: "↻", label: "CHANGED" },
  FORCED: { bg: "bg-violet/10", fg: "text-violet", icon: "↳", label: "FORCED" },
  FAILED: { bg: "bg-critical/10", fg: "text-critical", icon: "✕", label: "FAILED" },
};

export default function StatusBadge({ status }: { status: CacheStatus | string }) {
  const style = STYLES[status as CacheStatus] ?? STYLES.MISS;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-pill px-2.5 py-1 text-[11px] font-semibold tracking-wide ${style.bg} ${style.fg}`}
    >
      <span aria-hidden>{style.icon}</span>
      {style.label}
    </span>
  );
}
