import CodeCard, { dim, kw, str } from "./CodeCard";
import LogoMark from "./LogoMark";

const CIRCLE = 560;

export default function WhereFrom() {
  return (
    <section className="overflow-x-clip px-6 py-24 sm:px-10">
      <div className="relative mx-auto" style={{ maxWidth: CIRCLE }}>
        <div className="relative mx-auto w-full" style={{ maxWidth: CIRCLE, aspectRatio: "1 / 1" }}>
          <LogoMark variant="hero" responsive />

          <p className="absolute inset-x-0 top-[16%] px-8 text-center font-serif text-[16px] font-semibold leading-snug text-white sm:text-[22px]">
            Just so you understand where{" "}
            <span className="inline-flex items-center rounded-pill bg-dark px-3 py-1 align-middle text-[13px] font-semibold not-italic text-white sm:text-[16px]">
              accurate
            </span>{" "}
            come from
          </p>
        </div>

        <div className="relative z-10 mx-auto -mt-[15%] flex max-w-[1000px] flex-col items-center gap-4 md:mt-[-38%] md:flex-row md:items-center md:justify-between">
          <div className="w-full md:w-[340px] md:-translate-x-[38%]">
            <CodeCard label="Without Accurate">
              {kw("from")} accurate {kw("import")} Accurate{"\n"}
              accurate {dim("=")} Accurate(api_key={str('"acc_..."')})
            </CodeCard>
          </div>

          <div className="w-full md:w-[380px] md:translate-x-[38%]">
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
        </div>
      </div>
    </section>
  );
}
