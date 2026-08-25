import { formatCompact, formatUsd } from "@/lib/format";

interface SavingsCardProps {
  costUsd: number;
  savedUsd: number;
  tokens: number;
}

export default function SavingsCard({ costUsd, savedUsd, tokens }: SavingsCardProps) {
  const baseline = costUsd + savedUsd;
  const reduction = baseline > 0 ? savedUsd / baseline : 0;

  return (
    <div className="rounded-card bg-surface-raised p-5 text-white shadow-card">
      <span className="text-[12px] font-medium text-white/55">Saved on this run</span>
      <div className="tabular mt-2 text-[30px] font-semibold leading-none text-accent">
        {formatUsd(savedUsd)}
      </div>
      <div className="mt-4 flex items-center justify-between border-t border-white/10 pt-4 text-[12px]">
        <span className="text-white/55">Cost reduction</span>
        <span className="tabular font-semibold text-white">{Math.round(reduction * 100)}%</span>
      </div>
      <div className="mt-2 flex items-center justify-between text-[12px]">
        <span className="text-white/55">Tokens moved</span>
        <span className="tabular font-semibold text-white">{formatCompact(tokens)}</span>
      </div>
    </div>
  );
}
