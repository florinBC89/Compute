import type { ReactNode } from "react";

interface CodeCardProps {
  label?: string;
  children: ReactNode;
  flush?: boolean;
}

export default function CodeCard({ label, children, flush = false }: CodeCardProps) {
  return (
    <div
      className={`flex h-full w-full flex-col bg-dark ${
        flush ? "" : "overflow-hidden rounded-2xl shadow-[0_20px_60px_-20px_rgba(20,15,10,0.5)]"
      }`}
    >
      <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <span className="inline-flex items-center gap-1.5 rounded-pill bg-accent px-3 py-1.5 text-[12px] font-semibold text-white">
          {"</>"} Python
        </span>
        {label ? (
          <span className="font-serif text-[16px] font-bold text-white sm:text-[20px]">{label}</span>
        ) : null}
      </div>
      <pre className="flex-1 overflow-x-auto px-5 py-5 font-mono text-[12.5px] leading-[1.8] text-white/90">
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
