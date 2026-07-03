"use client";

import React, { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Sparkles, ArrowRight, ShieldAlert } from "lucide-react";

const EXAMPLES = [
  {
    title: "AI Trends Report",
    prompt: "Research and write a comprehensive, 10-page report on the latest AI trends in 2026. Compare LangGraph, CrewAI, and AutoGen, citing sources and formatting with clear markdown headings.",
    badge: "Research",
  },
  {
    title: "Trip Planner",
    prompt: "Design a 7-day travel itinerary for Kyoto, Japan. Include seasonal recommendations, daily budgets, hotel suggestions, transport details, and hidden gems.",
    badge: "Planning",
  },
  {
    title: "LinkedIn Content Plan",
    prompt: "Create a 4-week LinkedIn content calendar (12 posts total) for a software engineering manager. Focus on developer productivity, AI coding assistants, and team leadership.",
    badge: "Marketing",
  },
  {
    title: "Market Analysis",
    prompt: "Analyze the competitive landscape of serverless database platforms in 2026. Perform a SWOT analysis, compare Neon, Supabase, and PlanetScale, and suggest a GTM strategy.",
    badge: "Strategy",
  },
];

export function TaskForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [task, setTask] = useState("");
  const [enableHitl, setEnableHitl] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const promptParam = searchParams.get("prompt");
    if (promptParam) {
      setTask(promptParam);
    }
  }, [searchParams]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim() || task.length < 10) return;

    setIsSubmitting(true);
    // Encode parameters to pass to the live progress page
    const params = new URLSearchParams();
    params.set("task", task.trim());
    if (enableHitl) {
      params.set("hitl", "true");
    }
    
    // Redirect to a page that starts the streaming run
    router.push(`/tasks/new/run?${params.toString()}`);
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-10">
      {/* ── Form Section ────────────────────────────────────────── */}
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="relative group rounded-3xl border border-white/10 dark:border-white/5 bg-card/50 dark:bg-black/20 p-6 backdrop-blur-xl shadow-xl transition-all hover:border-amber-500/25">
          <label htmlFor="task" className="block text-sm font-semibold text-foreground/80 mb-3">
            What would you like your AI Crew to build today?
          </label>
          <textarea
            id="task"
            rows={5}
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Describe your task in detail (e.g. Write a marketing report about Neon DB vs Local Postgres...)"
            className="w-full bg-background/50 dark:bg-black/30 border border-border rounded-xl p-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent transition-all resize-none"
            minLength={10}
            maxLength={4000}
            required
          />

          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mt-6 pt-6 border-t border-border">
            {/* HITL checkbox */}
            <label className="flex items-center gap-3 cursor-pointer group/toggle select-none">
              <input
                type="checkbox"
                checked={enableHitl}
                onChange={(e) => setEnableHitl(e.target.checked)}
                className="sr-only peer"
              />
              <div className="relative w-11 h-6 bg-muted peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-amber-500"></div>
              <div className="space-y-0.5">
                <span className="text-sm font-semibold text-foreground/90 flex items-center gap-1.5">
                  Human-in-the-Loop
                  <span className="inline-flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-amber-400/10 text-amber-500 border border-amber-400/20">
                    HITL
                  </span>
                </span>
                <p className="text-xs text-muted-foreground">Pause for approval before final publication pass</p>
              </div>
            </label>

            {/* Run button */}
            <button
              type="submit"
              disabled={isSubmitting || task.length < 10}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-xl bg-amber-500 hover:bg-amber-500/90 text-black font-bold text-sm shadow-lg shadow-amber-500/10 transition-all hover:scale-102 active:scale-98 disabled:opacity-50 disabled:pointer-events-none"
            >
              {isSubmitting ? (
                <>
                  <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                  Starting Crew...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Run Agent Crew
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      </form>

      {/* ── Prompts Gallery ─────────────────────────────────────── */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-amber-400" />
          <h2 className="text-lg font-bold text-foreground">Need Inspiration? Try these templates:</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.title}
              type="button"
              onClick={() => setTask(ex.prompt)}
              className="text-left group relative p-5 rounded-2xl border border-border bg-card/30 hover:border-amber-500/30 transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-amber-500/5 cursor-pointer"
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="text-sm font-bold text-foreground group-hover:text-amber-400 transition-colors">
                  {ex.title}
                </span>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-400/10 text-amber-400 border border-amber-400/20">
                  {ex.badge}
                </span>
              </div>
              <p className="text-xs text-muted-foreground line-clamp-3 leading-relaxed">
                {ex.prompt}
              </p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
