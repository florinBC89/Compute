const STATS = [
  { value: "16.9 M", label: "Baseline Tokens", tone: "dark" as const },
  { value: "12.4 M", label: "Tokens Consumed", tone: "dark" as const },
  { value: "24%", label: "Compute Avoided", tone: "accentSoft" as const },
  { value: "12.4 M", label: "Tokens Avoided", tone: "light" as const },
  { value: "24%", label: "Cost Avoided", tone: "light" as const },
];

const TONE_STYLES = {
  dark: "bg-dark text-white",
  accentSoft: "bg-accent-soft text-ink",
  light: "bg-surface text-ink border border-border",
};

const VALUE_TONE = {
  dark: "text-white",
  accentSoft: "text-good",
  light: "text-good",
};

const LABEL_TONE = {
  dark: "text-accent",
  accentSoft: "text-ink-secondary",
  light: "text-ink-secondary",
};

export default function ComputeOverview() {
  return (
    <section className="mx-auto max-w-[1000px] px-6 py-24 sm:px-10">
      <h2 className="text-center font-serif text-[22px] font-semibold text-ink">
        AI Compute Overview
      </h2>

      <div className="mt-8 grid grid-cols-2 overflow-hidden rounded-card sm:grid-cols-5">
        {STATS.map((s) => (
          <div
            key={s.label}
            className={`flex flex-col items-center justify-center gap-1.5 px-4 py-9 ${TONE_STYLES[s.tone]}`}
          >
            <span className={`font-serif text-[26px] font-semibold ${VALUE_TONE[s.tone]}`}>
              {s.value}
            </span>
            <span className={`text-[11.5px] font-semibold uppercase tracking-wide ${LABEL_TONE[s.tone]}`}>
              {s.label}
            </span>
          </div>
        ))}
      </div>

      <div className="glow-hero relative mt-4 flex flex-col items-center overflow-hidden rounded-card px-6 py-14">
        <svg width="320" height="180" viewBox="0 0 320 180" className="max-w-full">
          <path
            d="M 20,160 A 140,140 0 0 1 247.27,50.53"
            fill="none"
            stroke="var(--dark)"
            strokeWidth="34"
            strokeLinecap="round"
          />
          <path
            d="M 247.27,50.53 A 140,140 0 0 1 300,160"
            fill="none"
            stroke="var(--good)"
            strokeWidth="34"
            strokeLinecap="round"
          />
          <text x="14" y="97" className="fill-white font-serif text-[22px] font-semibold">
            $500
          </text>
          <text x="255" y="107" className="fill-good font-serif text-[22px] font-semibold">
            $200
          </text>
        </svg>

        <p className="mt-2 text-center font-serif text-[20px] font-semibold text-ink">
          Your Bill Has Two Parts
        </p>

        <div className="mt-4 flex w-full max-w-[420px] justify-between px-2 text-[12.5px] font-medium">
          <span className="text-ink-secondary">Compute you need</span>
          <span className="text-good">Compute you didn&apos;t need to repeat</span>
        </div>
      </div>
    </section>
  );
}
