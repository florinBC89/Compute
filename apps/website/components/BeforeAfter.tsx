import CodeCard, { dim, kw, str } from "./CodeCard";
import LogoMark from "./LogoMark";

function ArrowIcon() {
  return (
    <svg
      width="20"
      height="14"
      viewBox="0 0 20 14"
      fill="none"
      className="shrink-0 rotate-90 text-accent sm:rotate-0"
    >
      <path
        d="M1 7h17M12 1l6 6-6 6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function BarsIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
      <rect x="3" y="12" width="3.4" height="7" rx="1" fill="#f2612f" />
      <rect x="9.3" y="7" width="3.4" height="12" rx="1" fill="#f2612f" />
      <rect x="15.6" y="3" width="3.4" height="16" rx="1" fill="#f2612f" />
    </svg>
  );
}

function TrackIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
      <path
        d="M3 8l5 6 4-5 7 8"
        stroke="#f2612f"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M15 15h4v-4" stroke="#f2612f" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function RecycleIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
      <path d="M8 3.5l3 3-3 3" stroke="#f2612f" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4.5 14.5A7 7 0 0111 6.5" stroke="#f2612f" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M14 18.5l-3-3 3-3" stroke="#f2612f" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M17.5 7.5A7 7 0 0111 15.5" stroke="#f2612f" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

const FEATURES = [
  { label: "Measure Tokens", icon: <BarsIcon /> },
  { label: "Track Costs", icon: <TrackIcon /> },
  { label: "Reuse Compute", icon: <RecycleIcon /> },
];

export default function BeforeAfter() {
  return (
    <section className="mx-auto max-w-[1000px] px-6 sm:px-10">
      <div className="grid grid-cols-1 items-stretch overflow-hidden rounded-2xl shadow-[0_20px_60px_-20px_rgba(20,15,10,0.5)] sm:grid-cols-[1fr_auto_1fr]">
        <CodeCard label="Before" flush>
          {kw("result")} {dim("=")} {kw("await")} run_research_agent({str('"NVDA"')})
        </CodeCard>

        <div className="flex items-center justify-center gap-4 bg-accent-soft px-8 py-8 sm:px-10">
          <ArrowIcon />
          <LogoMark variant="hero" size={88} />
          <ArrowIcon />
        </div>

        <CodeCard label="After" flush>
          {kw("result")} {dim("=")} {kw("await")} accurate.compute.run(
          {"\n  "}name={str('"company_analysis"')},{"\n  "}inputs=&#123;
          {str('"ticker"')}: {str('"NVDA"')}&#125;,{"\n  "}fn={kw("lambda")}: run_research_agent(
          {str('"NVDA"')})
          {"\n"})
        </CodeCard>
      </div>

      <div className="glow-hero relative -mx-6 mt-4 overflow-hidden px-6 pb-12 pt-16 text-center sm:-mx-10 sm:px-10 sm:pb-16 sm:pt-20">
        <h2 className="font-serif text-[30px] font-bold leading-tight text-ink sm:text-[42px]">
          Your Agent code stays the same
        </h2>
        <p className="mt-2 text-[14px] font-semibold text-accent sm:text-[15px]">You will just</p>

        <div className="relative z-10 mx-auto mt-10 grid max-w-[820px] grid-cols-1 overflow-hidden rounded-2xl border border-border bg-surface shadow-sm sm:grid-cols-3">
          {FEATURES.map((f, i) => (
            <div
              key={f.label}
              className={`flex items-center justify-center gap-2.5 px-5 py-5 text-[14.5px] font-semibold text-ink ${
                i > 0 ? "border-t border-border sm:border-l sm:border-t-0" : ""
              }`}
            >
              {f.icon}
              {f.label}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
