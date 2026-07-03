/**
 * lib/utils.ts — Shared utility functions
 */

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind class names safely (used by shadcn components). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format a date string to a human-readable relative time. */
export function timeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return date.toLocaleDateString();
}

/** Truncate a string with ellipsis. */
export function truncate(str: string, maxLen = 120): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen).trimEnd() + "…";
}

/** Score → color class (for critique scores). */
export function scoreColor(score: number): string {
  if (score >= 8.5) return "text-emerald-400";
  if (score >= 6.5) return "text-amber-400";
  return "text-red-400";
}

/** Score → label. */
export function scoreLabel(score: number): string {
  if (score >= 8.5) return "Excellent";
  if (score >= 6.5) return "Good";
  return "Needs Work";
}

/** Agent name → accent color class. */
export function agentColor(agent: string): string {
  const map: Record<string, string> = {
    planner: "amber",
    researcher: "cyan",
    executor: "emerald",
    critic: "amber",
    verifier: "rose",
    hitl: "sky",
    error: "red",
  };
  return map[agent.toLowerCase()] ?? "slate";
}

/** Copy text to clipboard. Returns true on success. */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** Trigger a browser download of text content. */
export function downloadText(content: string, filename: string, mime = "text/markdown") {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
