"use client";

import { useState } from "react";
import type { GraphNode, RunGraph as RunGraphData } from "@/lib/types";
import ComputationNode, { NODE_HEIGHT, NODE_WIDTH } from "./ComputationNode";
import WhyDrawer from "./WhyDrawer";

const COL_GAP = 56;
const ROW_GAP = 18;

function layerOf(nodes: RunGraphData["nodes"], edges: RunGraphData["edges"]): Map<string, number> {
  const parents = new Map<string, string[]>();
  for (const node of nodes) parents.set(node.id, []);
  for (const edge of edges) {
    if (!parents.has(edge.to)) parents.set(edge.to, []);
    parents.get(edge.to)!.push(edge.from);
  }

  const layer = new Map<string, number>();
  const resolving = new Set<string>();

  function resolve(id: string): number {
    if (layer.has(id)) return layer.get(id)!;
    if (resolving.has(id)) return 0; // guard against unexpected cycles
    resolving.add(id);
    const ps = parents.get(id) ?? [];
    const value = ps.length === 0 ? 0 : Math.max(...ps.map(resolve)) + 1;
    layer.set(id, value);
    resolving.delete(id);
    return value;
  }

  for (const node of nodes) resolve(node.id);
  return layer;
}

export default function RunGraph({ graph }: { graph: RunGraphData }) {
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const layers = layerOf(graph.nodes, graph.edges);
  const byLayer = new Map<number, string[]>();
  for (const node of graph.nodes) {
    const l = layers.get(node.id) ?? 0;
    if (!byLayer.has(l)) byLayer.set(l, []);
    byLayer.get(l)!.push(node.id);
  }

  const position = new Map<string, { x: number; y: number }>();
  const maxLayer = Math.max(0, ...byLayer.keys());
  const maxRows = Math.max(1, ...Array.from(byLayer.values(), (ids) => ids.length));
  const columnHeight = maxRows * NODE_HEIGHT + (maxRows - 1) * ROW_GAP;

  for (let l = 0; l <= maxLayer; l++) {
    const ids = byLayer.get(l) ?? [];
    const colHeight = ids.length * NODE_HEIGHT + Math.max(0, ids.length - 1) * ROW_GAP;
    const yOffset = (columnHeight - colHeight) / 2;
    ids.forEach((id, i) => {
      position.set(id, {
        x: l * (NODE_WIDTH + COL_GAP),
        y: yOffset + i * (NODE_HEIGHT + ROW_GAP),
      });
    });
  }

  const width = (maxLayer + 1) * NODE_WIDTH + maxLayer * COL_GAP;
  const height = columnHeight;
  const nodeById = new Map(graph.nodes.map((n) => [n.id, n]));

  return (
    <div className="overflow-x-auto rounded-card border border-border bg-page/60 p-6">
      <div className="relative" style={{ width, height }}>
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          className="pointer-events-none absolute inset-0"
        >
          {graph.edges.map((edge) => {
            const from = position.get(edge.from);
            const to = position.get(edge.to);
            if (!from || !to) return null;
            const x1 = from.x + NODE_WIDTH;
            const y1 = from.y + NODE_HEIGHT / 2;
            const x2 = to.x;
            const y2 = to.y + NODE_HEIGHT / 2;
            const midX = (x1 + x2) / 2;
            return (
              <path
                key={`${edge.from}-${edge.to}-${edge.key}`}
                d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                fill="none"
                stroke="var(--border)"
                strokeWidth={1.75}
              />
            );
          })}
        </svg>
        {graph.nodes.map((node) => {
          const pos = position.get(node.id);
          if (!pos) return null;
          const fullNode = nodeById.get(node.id)!;
          return (
            <div key={node.id} className="absolute" style={{ left: pos.x, top: pos.y }}>
              <ComputationNode node={fullNode} onClick={() => setSelected(fullNode)} />
            </div>
          );
        })}
      </div>
      {selected ? <WhyDrawer node={selected} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}
