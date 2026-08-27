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

// Real asset sizes (public/black-chart.svg is 575x416, green-chart.svg is
// 316x367) placed in one combined frame so the green chart continues where
// the black one ends, both positioned in percent so they scale together.
const FRAME_W = 745;
const FRAME_H = 416;
const BLACK = { w: 575, h: 416, x: 0, y: 0 };
const GREEN = { w: 316, h: 367, x: 429, y: 41 };
const pct = (v: number, of: number) => `${(v / of) * 100}%`;

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
        <div
          className="relative mx-auto w-full"
          style={{ maxWidth: FRAME_W, aspectRatio: `${FRAME_W} / ${FRAME_H}` }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/black-chart.svg"
            alt=""
            className="absolute"
            style={{ left: pct(BLACK.x, FRAME_W), top: pct(BLACK.y, FRAME_H), width: pct(BLACK.w, FRAME_W), height: pct(BLACK.h, FRAME_H) }}
          />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/green-chart.svg"
            alt=""
            className="absolute"
            style={{ left: pct(GREEN.x, FRAME_W), top: pct(GREEN.y, FRAME_H), width: pct(GREEN.w, FRAME_W), height: pct(GREEN.h, FRAME_H) }}
          />

          <span
            className="absolute font-serif text-[28px] font-semibold text-white"
            style={{ left: pct(210, FRAME_W), top: pct(150, FRAME_H) }}
          >
            $500
          </span>
          <span
            className="absolute font-serif text-[28px] font-semibold text-white"
            style={{ left: pct(560, FRAME_W), top: pct(150, FRAME_H) }}
          >
            $200
          </span>
        </div>

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
