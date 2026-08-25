interface GaugeRingProps {
  value: number; // 0..1
  size?: number;
  label: string;
  sublabel?: string;
}

export default function GaugeRing({ value, size = 148, label, sublabel }: GaugeRingProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const stroke = size * 0.11;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped);
  const center = size / 2;

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="var(--accent-track)"
          strokeWidth={stroke}
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="tabular text-[28px] font-semibold leading-none text-white">
          {Math.round(clamped * 100)}%
        </span>
        <span className="mt-1.5 text-[11px] font-medium uppercase tracking-wide text-white/50">
          {label}
        </span>
        {sublabel ? <span className="mt-0.5 text-[11px] text-white/40">{sublabel}</span> : null}
      </div>
    </div>
  );
}
