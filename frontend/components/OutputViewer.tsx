"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Copy, Check, Download, Sparkles } from "lucide-react";
import { copyToClipboard, downloadText } from "@/lib/utils";

interface OutputViewerProps {
  content: string;
  title?: string;
  score?: number;
  taskId?: string;
  showExport?: boolean;
}

export function OutputViewer({
  content,
  title = "Agent Draft",
  score,
  taskId,
  showExport = true,
}: OutputViewerProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!content) return;
    const ok = await copyToClipboard(content);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownloadMD = () => {
    if (!content) return;
    const cleanTitle = title.toLowerCase().replace(/[^a-z0-9]+/g, "_");
    downloadText(content, `${cleanTitle || "autocrew_output"}.md`, "text/markdown");
  };

  return (
    <div className="w-full rounded-3xl border border-white/8 bg-card/40 backdrop-blur-xl shadow-xl overflow-hidden">
      {/* ── Action Header ────────────────────────────────────────── */}
      <div className="flex items-center justify-between gap-4 p-5 border-b border-border bg-card/60">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-bold text-foreground">{title}</h3>
          {score !== undefined && score > 0 && (
            <span className="inline-flex text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 ml-2">
              Quality Score: {score.toFixed(1)}/10
            </span>
          )}
        </div>

        {showExport && content && (
          <div className="flex items-center gap-2">
            {/* Copy button */}
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:text-foreground hover:bg-white/5 transition-all"
              title="Copy markdown to clipboard"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  Copy
                </>
              )}
            </button>

            {/* Download Markdown */}
            <button
              onClick={handleDownloadMD}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs text-muted-foreground hover:text-foreground hover:bg-white/5 transition-all"
              title="Download as Markdown"
            >
              <Download className="w-3.5 h-3.5" />
              Download
            </button>
          </div>
        )}
      </div>

      {/* ── Content Body ────────────────────────────────────────── */}
      <div className="p-6 overflow-y-auto max-h-[600px] prose prose-invert prose-amber dark:prose-invert max-w-none text-sm text-foreground/80 leading-relaxed space-y-4">
        {content ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
        ) : (
          <div className="flex flex-col items-center justify-center py-16 text-center text-muted-foreground space-y-3">
            <div className="w-12 h-12 rounded-full border border-dashed border-border flex items-center justify-center text-xl">
              ✍️
            </div>
            <p className="text-xs">No content drafted yet. Waiting for Executor agent...</p>
          </div>
        )}
      </div>
    </div>
  );
}
