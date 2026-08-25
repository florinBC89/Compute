import type { RunListItem } from "@/lib/types";
import { formatUsd, shortId } from "@/lib/format";

export default function CostSparkline({ runs }: { runs: RunListItem[] }) {
  const chronological = [...runs].reverse();
  const max = Math.max(...chronological.map((r) => r.total_cost_usd), 0.01);

  const width = 260;
  const height = 72;
  const barGap = 3;
  const barWidth = Math.min(20, chronological.length ? width / chronological.length - barGap : 20);
  const baseline = height - 4;

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
      {chronological.map((run, i) => {
        const h = Math.max(3, (run.total_cost_usd / max) * (height - 22));
        const x = i * (barWidth + barGap);
        const isLast = i === chronological.length - 1;
        return (
          <g key={run.id}>
            {isLast ? (
              <text
                x={x + barWidth / 2}
                y={baseline - h - 8}
                textAnchor="middle"
                className="fill-ink text-[9px] font-semibold"
              >
                {formatUsd(run.total_cost_usd)}
              </text>
            ) : null}
            <rect
              x={x}
              y={baseline - h}
              width={barWidth}
              height={h}
              rx={4}
              fill={isLast ? "var(--accent)" : "var(--accent-track)"}
              role="img"
              aria-label={`${shortId(run.id)}, ${formatUsd(run.total_cost_usd)}`}
            />
          </g>
        );
      })}
      <line x1={0} y1={baseline} x2={width} y2={baseline} stroke="var(--border)" strokeWidth={1} />
    </svg>
  );
}
