import type { ReactNode } from "react";

interface CodeCardProps {
  label?: string;
  children: ReactNode;
}

export default function CodeCard({ label, children }: CodeCardProps) {
  return (
    <div className="w-full overflow-hidden rounded-2xl bg-dark shadow-[0_20px_60px_-20px_rgba(20,15,10,0.5)]">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <span className="inline-flex items-center gap-1.5 rounded-pill bg-accent/15 px-2.5 py-1 text-[11px] font-semibold text-accent">
          {"</>"} Python
        </span>
        {label ? (
          <span className="text-[12px] font-medium text-white/50">{label}</span>
        ) : null}
      </div>
      <pre className="overflow-x-auto px-4 py-4 font-mono text-[12.5px] leading-[1.7] text-white/90">
        {children}
      </pre>
    </div>
  );
}

export function kw(text: string) {
  return <span className="text-accent">{text}</span>;
}

export function str(text: string) {
  return <span className="text-good">{text}</span>;
}

export function dim(text: string) {
  return <span className="text-white/40">{text}</span>;
}
