function ProviderDot({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block h-4 w-4 rounded-full border border-ink-muted/40 bg-page ${className}`}
    />
  );
}

export default function Hero() {
  return (
    <div className="relative mx-auto max-w-[820px] px-6 pb-16 pt-6 text-center sm:px-10">
      <h1 className="font-serif text-[40px] font-semibold leading-[1.12] tracking-tight text-ink sm:text-[56px]">
        Your AI doesn&apos;t
        <br />
        need to <span className="text-accent">recompute</span>
        <br />
        <span className="text-accent">everything</span>
      </h1>
      <p className="mx-auto mt-6 max-w-[420px] text-[15px] leading-relaxed text-ink-secondary">
        Accurate tracks what changed across your agent workflow and reuses everything that
        didn&apos;t.
      </p>
      <p className="mt-5 text-[13px] font-semibold text-ink">
        Measure every token. Compute only what changed.
      </p>

      <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row sm:gap-6">
        <div className="flex items-center gap-2 text-[12.5px] font-medium text-ink-secondary">
          Compatible with +100 LLMs
          <span className="flex items-center -space-x-1.5">
            {Array.from({ length: 5 }).map((_, i) => (
              <ProviderDot key={i} />
            ))}
          </span>
        </div>
        <div className="hidden h-4 w-px bg-border sm:block" />
        <div className="flex items-center gap-1.5 text-[12.5px] font-medium text-ink-secondary">
          On top of
          <span className="inline-flex items-center gap-1 rounded-pill border border-border bg-surface px-2.5 py-1 font-semibold text-ink">
            <span className="h-2 w-2 rounded-full bg-accent" />
            OpenRouter
          </span>
        </div>
      </div>
    </div>
  );
}
