import CodeCard, { dim, kw, str } from "./CodeCard";
import LogoMark from "./LogoMark";

export default function WhereFrom() {
  return (
    <section className="relative overflow-hidden px-6 py-24 sm:px-10">
      <div className="glow-orb pointer-events-none absolute left-1/2 top-8 h-[420px] w-[420px] -translate-x-1/2 opacity-70" />

      <div className="relative mx-auto max-w-[720px] text-center">
        <p className="font-serif text-[22px] font-semibold leading-snug text-ink">
          Just so you understand where{" "}
          <span className="inline-flex items-center rounded-pill bg-dark px-3 py-1 align-middle text-[16px] font-semibold not-italic text-white">
            accurate
          </span>{" "}
          come from
        </p>

        <div className="my-10 flex justify-center">
          <LogoMark size={180} />
        </div>
      </div>

      <div className="relative mx-auto grid max-w-[900px] grid-cols-1 gap-4 md:grid-cols-2">
        <CodeCard label="Without Accurate">
          {kw("from")} accurate {kw("import")} Accurate{"\n"}
          accurate {dim("=")} Accurate(api_key={str('"acc_..."')})
        </CodeCard>

        <CodeCard label="With Accurate">
          {kw("from")} accurate {kw("import")} Accurate{"\n"}
          accurate {dim("=")} Accurate(api_key={str('"acc_..."')}){"\n"}
          result {dim("=")} {kw("await")} accurate.compute(
          {"\n  "}name={str('"company_analysis"')},{"\n  "}inputs=&#123;
          {str('"ticker"')}: {str('"NVDA"')}&#125;,{"\n  "}fn={kw("lambda")}: run_research_agent(
          {str('"NVDA"')})
          {"\n"})
        </CodeCard>
      </div>
    </section>
  );
}
