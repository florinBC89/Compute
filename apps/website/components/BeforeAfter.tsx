import CodeCard, { dim, kw, str } from "./CodeCard";
import LogoMark from "./LogoMark";

const FEATURES = [
  { label: "Measure Tokens", icon: "📊" },
  { label: "Track Costs", icon: "💳" },
  { label: "Reuse Compute", icon: "♻️" },
];

export default function BeforeAfter() {
  return (
    <section className="mx-auto max-w-[1000px] px-6 sm:px-10">
      <div className="grid grid-cols-1 items-center gap-4 md:grid-cols-[1fr_auto_1fr]">
        <CodeCard label="Before">
          {kw("result")} {dim("=")} {kw("await")} run_research_agent({str('"NVDA"')})
        </CodeCard>

        <div className="flex justify-center py-2 md:py-0">
          <LogoMark size={56} />
        </div>

        <CodeCard label="After">
          {kw("result")} {dim("=")} {kw("await")} accurate.compute.run(
          {"\n  "}name={str('"company_analysis"')},{"\n  "}inputs=&#123;
          {str('"ticker"')}: {str('"NVDA"')}&#125;,{"\n  "}fn={kw("lambda")}: run_research_agent(
          {str('"NVDA"')})
          {"\n"})
        </CodeCard>
      </div>

      <div className="glow-hero relative mt-8 overflow-hidden rounded-card px-6 py-10 text-center">
        <p className="font-serif text-[22px] font-semibold text-ink">
          Your Agent code stays the same
        </p>
        <p className="mt-1 text-[13px] text-ink-secondary">You will just</p>

        <div className="mx-auto mt-8 grid max-w-[640px] grid-cols-1 gap-3 sm:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.label}
              className="flex items-center justify-center gap-2 rounded-2xl border border-border bg-surface px-4 py-3.5 text-[13.5px] font-medium text-ink shadow-sm"
            >
              <span aria-hidden>{f.icon}</span>
              {f.label}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
