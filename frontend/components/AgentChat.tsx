"use client";

import React, { useEffect, useRef } from "react";
import {
  ClipboardList,
  Search,
  PenTool,
  MessageSquareCode,
  ShieldCheck,
  HelpCircle,
  Terminal,
  AlertTriangle,
  Bot,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface ChatMessage {
  id: string;
  agent: string;
  message: string;
  timestamp: string;
  type?: "info" | "success" | "warning" | "error" | "system";
}

interface AgentChatProps {
  messages: ChatMessage[];
}

// ---------------------------------------------------------------------------
// Agent config (avatar color + icon per agent)
// ---------------------------------------------------------------------------
const AGENT_CONFIG: Record<
  string,
  { color: string; bg: string; border: string; icon: React.ElementType; label: string }
> = {
  system: {
    color: "text-amber-400",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    icon: Terminal,
    label: "System",
  },
  Planner: {
    color: "text-violet-400",
    bg: "bg-violet-500/10",
    border: "border-violet-500/30",
    icon: ClipboardList,
    label: "Planner",
  },
  Researcher: {
    color: "text-cyan-400",
    bg: "bg-cyan-500/10",
    border: "border-cyan-500/30",
    icon: Search,
    label: "Researcher",
  },
  Executor: {
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
    icon: PenTool,
    label: "Executor",
  },
  Critic: {
    color: "text-amber-400",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    icon: MessageSquareCode,
    label: "Critic",
  },
  hitl: {
    color: "text-sky-400",
    bg: "bg-sky-500/10",
    border: "border-sky-500/30",
    icon: HelpCircle,
    label: "HITL",
  },
  Verifier: {
    color: "text-rose-400",
    bg: "bg-rose-500/10",
    border: "border-rose-500/30",
    icon: ShieldCheck,
    label: "Verifier",
  },
  error: {
    color: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    icon: AlertTriangle,
    label: "Error",
  },
};

const DEFAULT_CONFIG = {
  color: "text-muted-foreground",
  bg: "bg-muted/30",
  border: "border-border",
  icon: Bot,
  label: "Agent",
};

// ---------------------------------------------------------------------------
// Individual chat bubble
// ---------------------------------------------------------------------------
function AgentBubble({ msg }: { msg: ChatMessage }) {
  const config = AGENT_CONFIG[msg.agent] ?? DEFAULT_CONFIG;
  const Icon = config.icon;

  return (
    <div className="flex items-start gap-3 group animate-in slide-in-from-bottom-2 duration-300">
      {/* Avatar */}
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-xl border flex items-center justify-center mt-0.5 shadow-sm",
          config.bg,
          config.border
        )}
      >
        <Icon className={cn("w-4 h-4", config.color)} />
      </div>

      {/* Bubble */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className={cn("text-[11px] font-bold tracking-wide", config.color)}>
            {config.label}
          </span>
          <span className="text-[9px] text-muted-foreground/50 font-mono">
            {msg.timestamp}
          </span>
        </div>
        <div
          className={cn(
            "relative px-3.5 py-2.5 rounded-2xl rounded-tl-sm border text-[11px] leading-relaxed",
            "text-foreground/85 font-mono break-words",
            config.bg,
            config.border,
            msg.type === "error" && "border-red-500/40 bg-red-500/10 text-red-300"
          )}
        >
          {msg.message}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main AgentChat component
// ---------------------------------------------------------------------------
export function AgentChat({ messages }: AgentChatProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="rounded-3xl border border-white/8 bg-black/40 backdrop-blur-xl overflow-hidden flex flex-col h-[500px]">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/10 bg-white/2">
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500/70" />
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/70" />
          </div>
          <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider ml-1">
            Agent Console
          </span>
        </div>
        <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3.5 scrollbar-thin">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-3 text-muted-foreground/40">
            <Bot className="w-10 h-10" />
            <p className="text-xs italic">Waiting for agents to check in...</p>
          </div>
        ) : (
          messages.map((msg) => <AgentBubble key={msg.id} msg={msg} />)
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
