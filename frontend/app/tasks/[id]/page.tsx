"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { ArrowLeft, RefreshCw, AlertTriangle, CheckCircle2, User } from "lucide-react";
import Link from "next/link";
import { api, streamTaskFetch, streamResumeFetch, SSEEvent, PlanStep } from "@/lib/api";
import { AgentFlow } from "@/components/AgentFlow";
import { OutputViewer } from "@/components/OutputViewer";
import { AgentChat, ChatMessage } from "@/components/AgentChat";
import { CostPanel, TokenUsageRecord } from "@/components/CostPanel";
import { cn } from "@/lib/utils";

interface LogMessage {
  node: string;
  message: string;
  timestamp: string;
}

export default function LiveTaskPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const taskIdParam = params?.id as string;
  const initTaskPrompt = searchParams?.get("task") || "";
  const initEnableHitl = searchParams?.get("hitl") === "true";

  // Task state
  const [taskId, setTaskId] = useState<string>(taskIdParam === "new" ? "" : taskIdParam);
  const [taskPrompt, setTaskPrompt] = useState("");
  const [plan, setPlan] = useState<PlanStep[]>([]);
  const [draft, setDraft] = useState("");
  const [critique, setCritique] = useState("");
  const [critiqueScore, setCritiqueScore] = useState(0);
  const [iteration, setIteration] = useState(0);
  const [awaitingHuman, setAwaitingHuman] = useState(false);
  const [finalOutput, setFinalOutput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enableHitl, setEnableHitl] = useState(initEnableHitl);

  // Token usage & memory
  const [tokenUsage, setTokenUsage] = useState<TokenUsageRecord[]>([]);
  const [memoryUsed, setMemoryUsed] = useState(false);

  // Chat messages (replaces terminal log)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  // Legacy logs kept for compatibility
  const [logs, setLogs] = useState<LogMessage[]>([]);
  
  // Status & Nodes
  const [status, setStatus] = useState<"idle" | "running" | "paused" | "completed" | "failed">("idle");
  const [activeNode, setActiveNode] = useState<string | null>(null);
  const [completedNodes, setCompletedNodes] = useState<string[]>([]);

  // HITL Feedback input
  const [feedback, setFeedback] = useState("");
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);

  // Ref to prevent duplicate stream initiations in React strict mode
  const streamStarted = useRef(false);

  // Helper to add a chat bubble message
  const addChatMessage = (agent: string, message: string, type?: ChatMessage["type"]) => {
    const id = `${Date.now()}-${Math.random()}`;
    setChatMessages((prev) => [
      ...prev,
      { id, agent, message, timestamp: new Date().toLocaleTimeString(), type },
    ]);
  };

  // Load initial task state if not "new" or "run" or empty
  useEffect(() => {
    const isNewRun = !taskIdParam || taskIdParam === "new" || taskIdParam === "run";
    if (taskIdParam && !isNewRun) {
      loadTaskState(taskIdParam);
    } else if (isNewRun && initTaskPrompt && !streamStarted.current) {
      streamStarted.current = true;
      startNewTaskCampaign(initTaskPrompt, initEnableHitl);
    }
  }, [taskIdParam, initTaskPrompt]);

  const loadTaskState = async (id: string) => {
    try {
      setStatus("running");
      const state = await api.getTaskState(id);
      setTaskPrompt(state.task);
      setPlan(state.plan || []);
      setDraft(state.draft || "");
      setCritique(state.critique || "");
      setCritiqueScore(state.critique_score || 0);
      setIteration(state.iteration || 0);
      setAwaitingHuman(state.awaiting_human || false);
      setFinalOutput(state.final_output || "");
      setError(state.error);
      setEnableHitl(state.enable_hitl || false);

      // Reconstruct completed nodes based on status
      const completed: string[] = [];
      if (state.plan && state.plan.length > 0) completed.push("planner");
      if (state.draft) {
        completed.push("researcher");
        completed.push("executor");
      }
      if (state.critique_score > 0) completed.push("critic");
      if (state.error) {
        setStatus("failed");
      } else if (state.final_output) {
        if (state.enable_hitl) completed.push("hitl");
        completed.push("verifier");
        setStatus("completed");
      } else if (state.awaiting_human) {
        completed.push("critic");
        setStatus("paused");
      } else {
        setStatus("running");
      }
      setCompletedNodes(completed);
    } catch (err: any) {
      setError(err.message || "Failed to load task state");
      setStatus("failed");
    }
  };

  const addLog = (node: string, msg: string) => {
    addChatMessage(node, msg);
    setLogs((prev) => [
      ...prev,
      { node, message: msg, timestamp: new Date().toLocaleTimeString() },
    ]);
  };

  const startNewTaskCampaign = async (task: string, enableHitlParams: boolean) => {
    setTaskPrompt(task);
    setEnableHitl(enableHitlParams);
    setStatus("running");
    addLog("system", "Initializing AutoCrew Multi-Agent Graph...");

    try {
      const generator = streamTaskFetch({ task, enable_hitl: enableHitlParams });
      for await (const event of generator) {
        handleStreamEvent(event);
      }
    } catch (err: any) {
      setError(err.message || "Streaming connection failed");
      setStatus("failed");
      addLog("error", `Error: ${err.message}`);
    }
  };

  const handleStreamEvent = (event: SSEEvent) => {
    switch (event.type) {
      case "task_start":
        if (event.task_id) {
          setTaskId(event.task_id);
          addLog("system", `Campaign started. Task ID: ${event.task_id}`);
          
          // Save task ID to history list in localstorage
          try {
            const stored = localStorage.getItem("autocrew_task_history");
            const ids: string[] = stored ? JSON.parse(stored) : [];
            if (!ids.includes(event.task_id)) {
              ids.unshift(event.task_id); // Add to beginning of history
              localStorage.setItem("autocrew_task_history", JSON.stringify(ids));
            }
          } catch (e) {
            console.error("Failed to save task to local history storage:", e);
          }

          // Update URL without page reload
          window.history.replaceState(null, "", `/tasks/${event.task_id}`);
        }
        break;


      case "node_update":
        if (event.node) {
          const nodeName = event.node.replace("Agent", "");
          setActiveNode(event.node);
          addLog(nodeName, `Agent started execution pass.`);

          if (event.node === "planner" && event.plan) {
            setPlan(event.plan);
            setCompletedNodes((prev) => [...prev, "planner"]);
            addLog("Planner", "Generated structured workflow plan.");
          }
          if (event.node === "researcher") {
            setCompletedNodes((prev) => [...prev, "researcher"]);
            addLog("Researcher", "Web research completed. Findings synthesised.");
          }
          if (event.node === "executor" && event.draft) {
            setDraft(event.draft);
            if (event.iteration !== undefined) setIteration(event.iteration);
            setCompletedNodes((prev) => [...prev, "executor"]);
            addLog("Executor", "Created draft deliverable draft.");
          }
          if (event.node === "critic") {
            if (event.critique) setCritique(event.critique);
            if (event.critique_score !== undefined) setCritiqueScore(event.critique_score);
            setCompletedNodes((prev) => [...prev, "critic"]);
            addLog("Critic", `Review complete. Score: ${event.critique_score}/10`);
          }
          if (event.node === "verifier" && event.final_output) {
            setFinalOutput(event.final_output);
            setCompletedNodes((prev) => [...prev, "verifier"]);
            addLog("Verifier", "Final polish and edits applied.");
          }
        }
        break;

      case "hitl":
        setAwaitingHuman(true);
        setStatus("paused");
        setActiveNode("hitl");
        if (event.draft) setDraft(event.draft);
        if (event.critique) setCritique(event.critique);
        if (event.critique_score !== undefined) setCritiqueScore(event.critique_score);
        addLog("hitl", "Pipeline paused. Human feedback required to proceed.");
        break;

      case "final":
        setStatus("completed");
        setActiveNode(null);
        if (event.output) setFinalOutput(event.output);
        if (event.critique_score !== undefined) setCritiqueScore(event.critique_score);
        if (event.iterations !== undefined) setIteration(event.iterations);
        // Collect token usage
        if (event.token_usage && Array.isArray(event.token_usage)) {
          setTokenUsage(event.token_usage as TokenUsageRecord[]);
        }
        if (event.memory_used) setMemoryUsed(true);
        
        // Use a functional update to ensure we don't depend on stale closure variables
        setCompletedNodes((prev) => {
           const next = [...prev, "verifier"];
           return next;
        });
        
        addLog("system", "Crew successfully finalized the campaign!");
        break;

      case "error":
        setError(event.message || "An error occurred during workflow");
        setStatus("failed");
        addLog("error", `Fatal: ${event.message}`);
        break;
    }
  };

  const handleResume = async (approve: boolean) => {
    setIsSubmittingFeedback(true);
    setError(null);
    const feedbackText = approve ? "" : feedback.trim();
    
    addLog("system", approve ? "Approving draft and resuming..." : "Submitting feedback and revising...");
    
    try {
      setAwaitingHuman(false);
      setStatus("running");
      setFeedback("");
      
      if (approve) {
        setCompletedNodes(prev => prev.includes("hitl") ? prev : [...prev, "hitl"]);
      }
      
      const generator = streamResumeFetch(taskId, feedbackText || undefined);
      for await (const event of generator) {
        handleStreamEvent(event);
      }
    } catch (err: any) {
      setError(err.message || "Failed to resume task");
      setStatus("failed");
    } finally {
      setIsSubmittingFeedback(false);
    }
  };

  return (
    <div className="relative min-h-screen pt-24 pb-16 px-4 sm:px-6">
      <div className="absolute inset-0 bg-dots opacity-30 pointer-events-none" />

      <div className="max-w-7xl mx-auto space-y-8 relative">
        {/* Navigation */}
        <Link
          href="/tasks"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-all"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to History
        </Link>

        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-6">
          <div className="space-y-1">
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight">
              Campaign: <span className="gradient-text">Live Progress</span>
            </h1>
            <p className="text-xs text-muted-foreground font-mono">
              Task ID: {taskId || "Allocating..."}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className={cn(
              "text-xs font-bold px-3 py-1.5 rounded-full uppercase tracking-wider",
              status === "completed" && "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20",
              status === "running" && "bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse",
              status === "paused" && "bg-amber-500/10 text-amber-400 border border-amber-500/20",
              status === "failed" && "bg-red-500/10 text-red-400 border border-red-500/20",
              status === "idle" && "bg-muted text-muted-foreground"
            )}>
              {status}
            </span>
          </div>
        </div>

        {/* Task prompt overview */}
        <div className="p-5 rounded-2xl border border-border bg-card/20">
          <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-2">Original Instruction</h4>
          <p className="text-sm text-foreground/80 leading-relaxed">{taskPrompt || initTaskPrompt}</p>
        </div>

        {/* Flow visualizer */}
        <AgentFlow
          activeNode={activeNode}
          completedNodes={completedNodes}
          iteration={iteration}
          score={critiqueScore}
          awaitingHuman={awaitingHuman}
          status={status}
          enableHitl={enableHitl}
        />

        {/* Error notice */}
        {error && (
          <div className="p-4 rounded-xl border border-red-500/20 bg-red-500/5 text-red-400 text-xs flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Execution Error: </span>
              {error}
            </div>
          </div>
        )}

        {/* Main Grid: Output & Console Logs */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Output Viewer (Col-span 2) */}
          <div className="lg:col-span-2 space-y-6">
            {finalOutput ? (
              <OutputViewer
                content={finalOutput}
                title="Polished Final Output"
                score={critiqueScore}
                taskId={taskId}
              />
            ) : (
              <OutputViewer
                content={draft}
                title={`Draft Progress (Revision #${iteration})`}
                score={critiqueScore}
                taskId={taskId}
              />
            )}

            {/* Human in the Loop Control panel */}
            {awaitingHuman && (
              <div className="p-6 rounded-3xl border border-amber-500/30 bg-amber-500/5 backdrop-blur-xl space-y-4">
                <div className="flex items-center gap-2 text-amber-500">
                  <User className="w-5 h-5" />
                  <h3 className="font-bold text-sm">Human Gatekeeper Action Required</h3>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  The Critic rated the draft. You can approve it to finalise, or enter review comments to send it back to the Executor for revision.
                </p>

                {critique && (
                  <div className="p-4 rounded-xl bg-card border border-border text-xs text-foreground/80 leading-relaxed font-mono">
                    <span className="font-bold text-amber-500">Critic Notes: </span>
                    {critique}
                  </div>
                )}

                <div className="space-y-3">
                  <textarea
                    rows={3}
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    placeholder="Enter feedback to request a revision (e.g. 'Add a section on performance comparisons...')"
                    className="w-full bg-background border border-border rounded-xl p-3 text-xs focus:outline-none focus:ring-1 focus:ring-amber-500 transition-all resize-none"
                  />
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      onClick={() => handleResume(true)}
                      disabled={isSubmittingFeedback}
                      className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-500 text-white font-bold text-xs shadow-lg shadow-emerald-500/10 hover:opacity-90 transition-all disabled:opacity-50"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      Approve & Publish
                    </button>
                    <button
                      onClick={() => handleResume(false)}
                      disabled={isSubmittingFeedback || !feedback.trim()}
                      className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500 text-white font-bold text-xs shadow-lg shadow-amber-500/10 hover:opacity-90 transition-all disabled:opacity-50"
                    >
                      <RefreshCw className="w-4 h-4" />
                      Request Revision
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Chat-style Agent Console */}
          <AgentChat messages={chatMessages} />

          {/* Token Cost Panel */}
          <CostPanel
            tokenUsage={tokenUsage}
            memoryUsed={memoryUsed}
            status={status}
          />
        </div>
      </div>

    </div>
  );
}
