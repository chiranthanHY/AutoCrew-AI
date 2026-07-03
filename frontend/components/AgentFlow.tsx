"use client";

import React from "react";
import { Check, ClipboardList, Search, PenTool, MessageSquareCode, ShieldCheck, HelpCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface AgentFlowProps {
  activeNode: string | null;
  completedNodes: string[];
  iteration: number;
  score: number;
  maxIterations?: number;
  awaitingHuman?: boolean;
  status?: string;
  enableHitl?: boolean;
}

const STAGES = [
  {
    id: "planner",
    name: "Planner",
    icon: ClipboardList,
    color: "border-amber-500 text-amber-500 bg-amber-500/10",
    glow: "shadow-amber-500/25",
    desc: "Structuring execution steps",
  },
  {
    id: "researcher",
    name: "Researcher",
    icon: Search,
    color: "border-cyan-500 text-cyan-500 bg-cyan-500/10",
    glow: "shadow-cyan-500/25",
    desc: "Gathering factual search sources",
  },
  {
    id: "executor",
    name: "Executor",
    icon: PenTool,
    color: "border-emerald-500 text-emerald-500 bg-emerald-500/10",
    glow: "shadow-emerald-500/25",
    desc: "Drafting/revising contents",
  },
  {
    id: "critic",
    name: "Critic",
    icon: MessageSquareCode,
    color: "border-amber-500 text-amber-500 bg-amber-500/10",
    glow: "shadow-amber-500/25",
    desc: "Evaluating quality and score",
  },
  {
    id: "hitl",
    name: "HITL Check",
    icon: HelpCircle,
    color: "border-sky-500 text-sky-500 bg-sky-500/10",
    glow: "shadow-sky-500/25",
    desc: "Awaiting human review",
    optional: true,
  },
  {
    id: "verifier",
    name: "Verifier",
    icon: ShieldCheck,
    color: "border-rose-500 text-rose-500 bg-rose-500/10",
    glow: "shadow-rose-500/25",
    desc: "Final copy-edit & synthesis",
  },
];

export function AgentFlow({
  activeNode,
  completedNodes,
  iteration,
  score,
  maxIterations = 5,
  awaitingHuman = false,
  status = "idle",
  enableHitl = false,
}: AgentFlowProps) {
  // Normalize node names from backend to align with frontend stage IDs
  const getStageStatus = (stageId: string) => {
    const normActive = activeNode?.toLowerCase() || "";
    const normStage = stageId.toLowerCase();

    // Special case for HITL
    if (stageId === "hitl") {
      if (awaitingHuman) return "active";
      if (completedNodes.includes("hitl")) return "completed";
      return "upcoming";
    }

    if (normActive === normStage) {
      return "active";
    }
    if (completedNodes.includes(normStage) || completedNodes.includes(stageId)) {
      return "completed";
    }
    return "upcoming";
  };

  const getStatusHeaderInfo = () => {
    if (status === "failed") {
      return {
        title: "Crew Execution Failed",
        desc: "Review error details below",
        color: "bg-red-500",
      };
    }
    if (status === "paused" || awaitingHuman) {
      return {
        title: "Awaiting Human Review",
        desc: "Review the draft and submit feedback",
        color: "bg-amber-400",
      };
    }
    if (status === "running" || activeNode) {
      return {
        title: activeNode ? `Crew Executing: ${activeNode.replace("Agent", "")}` : "Crew Running autonomous steps",
        desc: "The crew is running autonomous steps",
        color: "bg-amber-500",
      };
    }
    if (status === "completed") {
      return {
        title: "Crew Pipeline Completed",
        desc: "Deliverable is finalized and ready",
        color: "bg-emerald-500",
      };
    }
    return {
      title: "Initializing Crew Pipeline...",
      desc: "Starting execution telemetry",
      color: "bg-muted-foreground",
    };
  };

  const headerInfo = getStatusHeaderInfo();

  return (
    <div className="w-full space-y-6">
      {/* ── Status Header ───────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-2xl border border-white/8 bg-card/40 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <div className="relative flex h-3.5 w-3.5">
            {(status === "running" || activeNode) && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
            )}
            <span className={cn(
              "relative inline-flex rounded-full h-3.5 w-3.5",
              headerInfo.color
            )}></span>
          </div>
          <div>
            <h3 className="text-sm font-bold text-foreground">
              {headerInfo.title}
            </h3>
            <p className="text-xs text-muted-foreground font-medium">
              {headerInfo.desc}
            </p>
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-6 text-xs font-mono">
          <div className="space-y-0.5">
            <span className="block text-[10px] text-muted-foreground uppercase tracking-wider">Loops</span>
            <span className="block text-sm font-bold text-foreground">
              {iteration} <span className="text-muted-foreground/60">/ {maxIterations}</span>
            </span>
          </div>
          <div className="space-y-0.5">
            <span className="block text-[10px] text-muted-foreground uppercase tracking-wider">Critic Score</span>
            <span className={cn(
              "block text-sm font-bold",
              score >= 8 ? "text-emerald-400" : score >= 5 ? "text-amber-400" : "text-muted-foreground"
            )}>
              {score > 0 ? `${score.toFixed(1)}/10` : "—"}
            </span>
          </div>
        </div>
      </div>

      {/* ── Flow Nodes ──────────────────────────────────────────── */}
      <div className={cn(
        "relative grid gap-4",
        enableHitl ? "grid-cols-2 sm:grid-cols-3 lg:grid-cols-6" : "grid-cols-2 sm:grid-cols-3 lg:grid-cols-5"
      )}>
        {/* Connector line background (Desktop only) */}
        <div className="hidden lg:block absolute top-[28px] left-[5%] right-[5%] h-0.5 bg-border pointer-events-none -z-10" />

        {STAGES.filter(stage => !stage.optional || (stage.id === "hitl" && enableHitl)).map((stage) => {
          const status = getStageStatus(stage.id);
          const Icon = stage.icon;

          return (
            <div
              key={stage.id}
              className={cn(
                "relative flex flex-col items-center text-center p-4 rounded-2xl border transition-all duration-300",
                status === "completed" && "bg-emerald-500/5 border-emerald-500/20 shadow-lg shadow-emerald-500/2",
                status === "active" && "bg-primary/5 border-primary shadow-lg shadow-primary/10 scale-102",
                status === "upcoming" && "bg-card/20 border-border opacity-65"
              )}
            >
              {/* Node Indicator circle */}
              <div
                className={cn(
                  "w-10 h-10 rounded-full border-2 flex items-center justify-center transition-all duration-300 mb-3",
                  status === "completed" && "border-emerald-500 bg-emerald-500/10 text-emerald-500 shadow-md shadow-emerald-500/20",
                  status === "active" && "border-primary bg-primary/20 text-primary shadow-lg",
                  status === "upcoming" && "border-muted bg-muted/40 text-muted-foreground"
                )}
              >
                {status === "completed" ? (
                  <Check className="w-5 h-5 stroke-[2.5]" />
                ) : (
                  <Icon className="w-5 h-5" />
                )}
              </div>

              {/* Title & Description */}
              <span className="text-sm font-bold text-foreground mb-1 block">
                {stage.name}
              </span>
              <p className="text-[10px] text-muted-foreground leading-normal max-w-[120px] mx-auto">
                {status === "active" ? stage.desc : status === "completed" ? "Step Completed" : "Waiting"}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
