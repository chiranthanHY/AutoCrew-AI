"use client";

import React, { Suspense } from "react";
import { TaskForm } from "@/components/TaskForm";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function NewTaskPage() {
  return (
    <div className="relative min-h-screen pt-24 pb-16 px-4 sm:px-6">
      {/* Background decorations */}
      <div className="absolute inset-0 bg-dots opacity-40 pointer-events-none" />
      <div className="absolute top-20 left-1/4 w-80 h-80 bg-amber-500/5 rounded-full blur-3xl pointer-events-none" />

      <div className="max-w-4xl mx-auto space-y-8 relative">
        {/* Back Link */}
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-all"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Home
        </Link>

        {/* Header */}
        <div className="space-y-2">
          <h1 className="text-3xl sm:text-4xl font-black tracking-tight">
            Create a New <span className="gradient-text">Task Campaign</span>
          </h1>
          <p className="text-sm text-muted-foreground max-w-xl">
            Input a high-level task. The crew of Planner, Researcher, Executor, Critic, and Verifier will run the pipeline.
          </p>
        </div>

        {/* Form Form */}
        <Suspense fallback={
          <div className="w-full h-64 border border-border rounded-3xl flex items-center justify-center text-muted-foreground text-sm">
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin mr-2" />
            Loading task interface...
          </div>
        }>
          <TaskForm />
        </Suspense>
      </div>
    </div>
  );
}
