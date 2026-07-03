"use client";

import React, { Suspense } from "react";
import LiveTaskPage from "../../[id]/page";

export default function RunTaskWrapper() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex flex-col items-center justify-center text-muted-foreground text-sm space-y-4">
        <div className="w-8 h-8 border-3 border-primary border-t-transparent rounded-full animate-spin" />
        <p>Connecting to AutoCrew Orchestrator...</p>
      </div>
    }>
      <LiveTaskPage />
    </Suspense>
  );
}
