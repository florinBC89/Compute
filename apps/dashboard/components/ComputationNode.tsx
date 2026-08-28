import type { GraphNode } from "@/lib/types";
import { formatCompact, formatUsd } from "@/lib/format";
import StatusBadge from "./StatusBadge";

export const NODE_WIDTH = 208;
export const NODE_HEIGHT = 132;

interface ComputationNodeProps {
  node: GraphNode;
  onClick?: () => void;
}

export default function ComputationNode({ node, onClick }: ComputationNodeProps) {
  const totalTokens = node.input_tokens + node.output_tokens;
  return (
    <div
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={(e) => {
        if (onClick && (e.key === "Enter" || e.key === " ")) onClick();
      }}
      style={{ width: NODE_WIDTH, height: NODE_HEIGHT }}
      className={`flex flex-col justify-between rounded-2xl border border-border bg-surface p-3.5 shadow-card ${
        onClick ? "cursor-pointer transition-shadow hover:shadow-[0_0_0_2px_var(--accent)]" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-[12.5px] font-semibold leading-tight text-ink">{node.name}</span>
        <StatusBadge status={node.status} reuseKind={node.reuse_kind} />
      </div>
      <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px]">
        <span className="text-ink-muted">Cost</span>
        <span className="tabular text-right text-ink">{formatUsd(node.cost_usd)}</span>
        <span className="text-ink-muted">Saved</span>
        <span className="tabular text-right text-good">{formatUsd(node.saved_usd)}</span>
        <span className="text-ink-muted">Latency</span>
        <span className="tabular text-right text-ink">
          {node.latency_ms != null ? `${node.latency_ms}ms` : "—"}
        </span>
        <span className="text-ink-muted">Tokens</span>
        <span className="tabular text-right text-ink">{formatCompact(totalTokens)}</span>
      </div>
      {onClick ? (
        <div className="text-right text-[10.5px] font-medium text-accent">Why? →</div>
      ) : null}
    </div>
  );
}
