"use client";

import React from "react";
import { Coins, Zap, TrendingUp, Database, Brain } from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface TokenUsageRecord {
  node: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
  model: string;
}

interface CostPanelProps {
  tokenUsage: TokenUsageRecord[];
  memoryUsed?: boolean;
  status?: string;
}

// ---------------------------------------------------------------------------
// Per-agent color mapping
// ---------------------------------------------------------------------------
const NODE_COLORS: Record<string, string> = {
  planner: "bg-violet-500",
  researcher: "bg-cyan-500",
  executor: "bg-emerald-500",
  critic: "bg-amber-500",
  verifier: "bg-rose-500",
};

const NODE_LABELS: Record<string, string> = {
  planner: "Planner",
  researcher: "Researcher",
  executor: "Executor",
  critic: "Critic",
  verifier: "Verifier",
};

// ---------------------------------------------------------------------------
// Aggregation helpers
// ---------------------------------------------------------------------------
function aggregateByNode(records: TokenUsageRecord[]) {
  const map: Record<string, TokenUsageRecord> = {};
  for (const rec of records) {
    const key = rec.node.toLowerCase();
    if (!map[key]) {
      map[key] = { ...rec, node: key };
    } else {
      map[key].input_tokens += rec.input_tokens;
      map[key].output_tokens += rec.output_tokens;
      map[key].total_tokens += rec.total_tokens;
      map[key].cost_usd += rec.cost_usd;
    }
  }
  return Object.values(map);
}

function formatCost(usd: number): string {
  if (usd < 0.000001) return "$0.00";
  if (usd < 0.001) return `$${(usd * 1000).toFixed(3)}m`;
  return `$${usd.toFixed(4)}`;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return `${n}`;
}

// ---------------------------------------------------------------------------
// Main CostPanel component
// ---------------------------------------------------------------------------
export function CostPanel({ tokenUsage, memoryUsed = false, status }: CostPanelProps) {
  const aggregated = aggregateByNode(tokenUsage);
  const totalTokens = aggregated.reduce((s, r) => s + r.total_tokens, 0);
  const totalCost = aggregated.reduce((s, r) => s + r.cost_usd, 0);
  const totalInput = aggregated.reduce((s, r) => s + r.input_tokens, 0);
  const totalOutput = aggregated.reduce((s, r) => s + r.output_tokens, 0);
  const maxTokens = Math.max(...aggregated.map((r) => r.total_tokens), 1);

  const isEmpty = totalTokens === 0;

  return (
    <div className="rounded-3xl border border-white/8 bg-card/40 backdrop-blur-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-border bg-card/60">
        <div className="flex items-center gap-2">
          <Coins className="w-4 h-4 text-amber-400" />
          <span className="text-sm font-bold text-foreground">Token Usage & Cost</span>
        </div>
        {memoryUsed && (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
            <Brain className="w-3 h-3" />
            Memory Active
          </span>
        )}
      </div>

      <div className="p-5 space-y-5">
        {/* Summary Stats */}
        <div className="grid grid-cols-3 gap-3">
          <div className="p-3 rounded-xl bg-white/3 border border-border text-center space-y-1">
            <Zap className="w-4 h-4 text-amber-400 mx-auto" />
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Tokens</p>
            <p className="text-sm font-black text-foreground">{formatTokens(totalTokens)}</p>
          </div>
          <div className="p-3 rounded-xl bg-white/3 border border-border text-center space-y-1">
            <Coins className="w-4 h-4 text-emerald-400 mx-auto" />
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Est. Cost</p>
            <p className="text-sm font-black text-emerald-400">{formatCost(totalCost)}</p>
          </div>
          <div className="p-3 rounded-xl bg-white/3 border border-border text-center space-y-1">
            <TrendingUp className="w-4 h-4 text-cyan-400 mx-auto" />
            <p className="text-[10px] text-muted-foreground uppercase tracking-wider">In / Out</p>
            <p className="text-sm font-black text-foreground">
              <span className="text-cyan-400">{formatTokens(totalInput)}</span>
              <span className="text-muted-foreground/50 mx-1">/</span>
              <span className="text-violet-400">{formatTokens(totalOutput)}</span>
            </p>
          </div>
        </div>

        {/* Per-Agent Breakdown */}
        {isEmpty ? (
          <div className="text-center py-6 text-muted-foreground/40 text-xs italic">
            Token data will appear as agents run...
          </div>
        ) : (
          <div className="space-y-2.5">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">
              Per-Agent Breakdown
            </p>
            {aggregated.map((rec) => {
              const pct = Math.round((rec.total_tokens / maxTokens) * 100);
              const barColor = NODE_COLORS[rec.node] ?? "bg-muted-foreground";
              const label = NODE_LABELS[rec.node] ?? rec.node;
              return (
                <div key={rec.node} className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <div className="flex items-center gap-2">
                      <span className={cn("w-2 h-2 rounded-full flex-shrink-0", barColor)} />
                      <span className="font-semibold text-foreground/80">{label}</span>
                    </div>
                    <div className="flex items-center gap-3 font-mono text-muted-foreground">
                      <span>{formatTokens(rec.total_tokens)} tok</span>
                      <span className="text-emerald-400 font-bold">{formatCost(rec.cost_usd)}</span>
                    </div>
                  </div>
                  {/* Progress bar */}
                  <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
                    <div
                      className={cn("h-full rounded-full transition-all duration-700", barColor, "opacity-70")}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Model info */}
        {aggregated.length > 0 && aggregated[0].model && (
          <p className="text-[10px] text-muted-foreground/50 text-center font-mono">
            Model: {aggregated[0].model}
          </p>
        )}
      </div>
    </div>
  );
}
