import { formatUsd } from "@/lib/format";

interface CostRingsProps {
  actualUsd: number;
  savedUsd: number;
}

// Area-proportional (radius ∝ sqrt(value)) so the rings never misstate the
// relationship: baseline = actual + saved, drawn as an outline (baseline),
// a ring (saved) and a solid disc (actual) rather than three independent
// circles.
export default function CostRings({ actualUsd, savedUsd }: CostRingsProps) {
  const baseline = Math.max(actualUsd + savedUsd, 0.01);
  const size = 220;
  const center = size / 2;
  const maxRadius = 96;
  const k = maxRadius / Math.sqrt(baseline);
  const rBaseline = Math.max(maxRadius, 40);
  const rActual = Math.max(k * Math.sqrt(Math.max(actualUsd, 0)), 26);

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={center}
          cy={center}
          r={rBaseline}
          fill="var(--accent-soft)"
          stroke="var(--border)"
          strokeWidth={1}
        />
        <circle cx={center} cy={center} r={rActual} fill="var(--accent)" />
        <text
          x={center}
          y={center - 4}
          textAnchor="middle"
          className="fill-white text-[15px] font-semibold"
        >
          {formatUsd(actualUsd)}
        </text>
        <text
          x={center}
          y={center + 12}
          textAnchor="middle"
          className="fill-white/75 text-[9px] font-medium uppercase tracking-wide"
        >
          Actual
        </text>
        <text
          x={center}
          y={20}
          textAnchor="middle"
          className="fill-ink-secondary text-[10px] font-medium uppercase tracking-wide"
        >
          Baseline {formatUsd(baseline)}
        </text>
      </svg>
      <div className="mt-1 flex items-center gap-1.5 text-[12px] text-ink-secondary">
        <span className="h-2 w-2 rounded-full" style={{ background: "var(--accent-soft)" }} />
        Saved {formatUsd(savedUsd)}
      </div>
    </div>
  );
}
