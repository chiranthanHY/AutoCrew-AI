"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Plus, Trash2, CheckCircle2, RefreshCw, AlertCircle } from "lucide-react";
import { api, TaskStateResponse } from "@/lib/api";
import { cn, truncate } from "@/lib/utils";

export default function TaskHistoryPage() {
  const router = useRouter();
  const [tasks, setTasks] = useState<TaskStateResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    setIsLoading(true);
    try {
      // 1. Get task IDs saved in localStorage
      const stored = localStorage.getItem("autocrew_task_history");
      const ids: string[] = stored ? JSON.parse(stored) : [];

      if (ids.length === 0) {
        setTasks([]);
        setIsLoading(false);
        return;
      }

      // 2. Fetch the current state of each task from Neon DB
      const fetchedTasks = await Promise.all(
        ids.map(async (id) => {
          try {
            return await api.getTaskState(id);
          } catch {
            // If fetching failed (e.g. task deleted or local db reset), return null
            return null;
          }
        })
      );

      // 3. Filter out nulls and sort by latest iteration/updates (or keep storage order)
      const validTasks = fetchedTasks.filter((t): t is TaskStateResponse => t !== null);
      setTasks(validTasks);

      // Clean up storage if any IDs were invalid (not found in DB anymore)
      const validIds = validTasks.map((t) => t.task_id);
      localStorage.setItem("autocrew_task_history", JSON.stringify(validIds));
    } catch (err) {
      console.error("Failed to load task history:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm("Remove this task from your local history view? (The database record will remain intact)")) return;

    const stored = localStorage.getItem("autocrew_task_history");
    const ids: string[] = stored ? JSON.parse(stored) : [];
    const filtered = ids.filter((item) => item !== id);
    localStorage.setItem("autocrew_task_history", JSON.stringify(filtered));
    
    setTasks((prev) => prev.filter((t) => t.task_id !== id));
  };

  const getStatusText = (task: TaskStateResponse) => {
    if (task.final_output) return "Completed";
    if (task.awaiting_human) return "Review Required";
    if (task.error) return "Failed";
    return "Running";
  };

  return (
    <div className="relative min-h-screen pt-24 pb-16 px-4 sm:px-6">
      <div className="absolute inset-0 bg-grid opacity-30 pointer-events-none" />

      <div className="max-w-7xl mx-auto space-y-8 relative">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
          <div className="space-y-1">
            <h1 className="text-3xl sm:text-4xl font-black tracking-tight">
              Campaign <span className="gradient-text">History</span>
            </h1>
            <p className="text-sm text-muted-foreground">
              Monitor, audit, and resume your autonomous agent campaigns.
            </p>
          </div>

          <Link
            href="/tasks/new"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500 text-black font-bold text-xs shadow-lg shadow-amber-500/10 hover:scale-102 hover:opacity-90 active:scale-98 transition-all"
          >
            <Plus className="w-4 h-4" />
            New Campaign
          </Link>
        </div>

        {/* ── Loading state ───────────────────────────────────────── */}
        {isLoading ? (
          <div className="w-full py-32 flex flex-col items-center justify-center space-y-4">
            <div className="w-8 h-8 border-3 border-primary border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-muted-foreground">Querying Neon Database checkpointers...</p>
          </div>
        ) : tasks.length === 0 ? (
          /* ── Empty state ────────────────────────────────────────── */
          <div className="max-w-md mx-auto text-center py-20 p-8 rounded-3xl border border-dashed border-border bg-card/20 space-y-6">
            <div className="w-14 h-14 rounded-full bg-muted flex items-center justify-center text-2xl mx-auto">
              🗂️
            </div>
            <div className="space-y-1.5">
              <h3 className="font-bold text-base text-foreground">No Campaign History</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                You haven&apos;t run any agent automation campaigns yet. Start your first multi-agent crew run to see it here.
              </p>
            </div>
            <Link
              href="/tasks/new"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-amber-500 text-black font-bold text-xs shadow-lg shadow-amber-500/15 hover:opacity-90 transition-all"
            >
              Start Your First Crew
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        ) : (
          /* ── Task list table ─────────────────────────────────────── */
          <div className="rounded-3xl border border-white/8 bg-card/30 backdrop-blur-xl overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-border bg-card/50 text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                    <th className="py-4 px-6">Task campaign / ID</th>
                    <th className="py-4 px-6">Status</th>
                    <th className="py-4 px-6 text-center">Score</th>
                    <th className="py-4 px-6 text-center">Loops</th>
                    <th className="py-4 px-6 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border text-xs">
                  {tasks.map((task) => {
                    const statusText = getStatusText(task);

                    return (
                      <tr
                        key={task.task_id}
                        className="group hover:bg-white/5 transition-colors cursor-pointer"
                        onClick={() => router.push(`/tasks/${task.task_id}`)}
                      >
                        {/* Title & prompt */}
                        <td className="py-5 px-6 max-w-sm">
                          <div className="space-y-1">
                            <span className="font-bold text-foreground group-hover:text-amber-400 transition-colors block">
                              {truncate(task.task, 70)}
                            </span>
                            <span className="font-mono text-[9px] text-muted-foreground/60 block">
                              ID: {task.task_id}
                            </span>
                          </div>
                        </td>

                        {/* Status badge */}
                        <td className="py-5 px-6">
                          <span className={cn(
                            "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border",
                            statusText === "Completed" && "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
                            statusText === "Review Required" && "bg-amber-500/10 text-amber-400 border-amber-500/20",
                            statusText === "Failed" && "bg-red-500/10 text-red-400 border-red-500/20",
                            statusText === "Running" && "bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse"
                          )}>
                            {statusText === "Completed" && <CheckCircle2 className="w-3 h-3" />}
                            {statusText === "Review Required" && <AlertCircle className="w-3 h-3" />}
                            {statusText === "Running" && <RefreshCw className="w-3 h-3 animate-spin" />}
                            {statusText}
                          </span>
                        </td>

                        {/* Critique score */}
                        <td className="py-5 px-6 text-center font-bold">
                          {task.critique_score > 0 ? (
                            <span className={cn(
                              task.critique_score >= 8 ? "text-emerald-400" : "text-amber-400"
                            )}>
                              {task.critique_score.toFixed(1)}/10
                            </span>
                          ) : (
                            <span className="text-muted-foreground/40">—</span>
                          )}
                        </td>

                        {/* Iterations loops */}
                        <td className="py-5 px-6 text-center text-muted-foreground font-mono">
                          {task.iteration} <span className="text-muted-foreground/30">/ 5</span>
                        </td>

                        {/* Actions */}
                        <td className="py-5 px-6 text-right" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-end gap-3">
                            <Link
                              href={`/tasks/${task.task_id}`}
                              className="text-amber-500 hover:text-amber-400 font-semibold transition-all hover:underline"
                            >
                              Open Details
                            </Link>
                            <button
                              onClick={(e) => handleDelete(task.task_id, e)}
                              className="w-8 h-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-red-400 hover:bg-red-500/10 transition-all"
                              title="Delete from local view"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
