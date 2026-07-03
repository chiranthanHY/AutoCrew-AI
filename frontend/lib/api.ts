/**
 * lib/api.ts — AutoCrew AI API client
 * Typed fetch wrappers for every backend endpoint.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Types ────────────────────────────────────────────────────────────────────

export interface TaskRequest {
  task: string;
  stream?: boolean;
  enable_hitl?: boolean;
}

export interface TaskResponse {
  task_id: string;
  final_output: string;
  critique_score: number;
  iterations: number;
  plan: PlanStep[];
  awaiting_human: boolean;
  error: string | null;
}

export interface TaskStateResponse {
  task_id: string;
  task: string;
  plan: PlanStep[];
  draft: string;
  critique: string;
  critique_score: number;
  iteration: number;
  awaiting_human: boolean;
  enable_hitl: boolean;
  final_output: string;
  error: string | null;
}

export interface PlanStep {
  step_id: number;
  task_description: string;
  assignee: string;
  depends_on: number[];
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  groq_configured: boolean;
  tavily_configured: boolean;
  model: string;
  database: { status: string; latency_ms: number; error?: string };
  neon: boolean;
}

export interface CheckpointSummary {
  checkpoint_id: string | null;
  next: string[];
  created_at: string | null;
  iteration: number;
  critique_score: number;
}

export interface SSEEvent {
  type:
    | "task_start"
    | "node_update"
    | "hitl"
    | "final"
    | "error";
  task_id?: string;
  task?: string;
  node?: string;
  plan?: PlanStep[];
  draft?: string;
  critique?: string;
  critique_score?: number;
  iterations?: number;
  output?: string;
  awaiting_human?: boolean;
  message?: string;
  // node-specific fields
  iteration?: number;
  final_output?: string;
  research_results?: unknown[];
  messages?: { role: string; content: string }[];
  next?: string;
  error?: string;
  // token usage & memory
  token_usage?: {
    node: string;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    cost_usd: number;
    model: string;
  }[];
  memory_used?: boolean;
}

// ── API helpers ───────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Endpoints ─────────────────────────────────────────────────────────────────

export const api = {
  /** Health check — includes DB ping and config status. */
  health(): Promise<HealthResponse> {
    return apiFetch("/health");
  },

  /** Run a task in blocking mode (no stream). */
  runTask(payload: TaskRequest): Promise<TaskResponse> {
    return apiFetch("/tasks/run", {
      method: "POST",
      body: JSON.stringify({ ...payload, stream: false }),
    });
  },

  /** Get the persisted state of a task by ID. */
  getTaskState(taskId: string): Promise<TaskStateResponse> {
    return apiFetch(`/tasks/${taskId}/state`);
  },

  /** Resume a HITL-paused task. Returns SSE stream URL. */
  resumeTask(taskId: string, humanFeedback?: string): Promise<Response> {
    return fetch(`${API_BASE}/tasks/${taskId}/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ human_feedback: humanFeedback ?? null }),
    });
  },

  /** List checkpoint history for a task. */
  getTaskHistory(
    taskId: string,
    limit = 10
  ): Promise<{ task_id: string; checkpoint_count: number; checkpoints: CheckpointSummary[] }> {
    return apiFetch(`/tasks/${taskId}/history?limit=${limit}`);
  },

  /**
   * Open an EventSource stream for a new task run.
   * Caller is responsible for closing the EventSource.
   */
  streamTask(payload: TaskRequest): EventSource {
    // We POST the request via fetch first (can't POST with EventSource natively),
    // so we use a GET-compatible URL trick — the backend supports SSE via POST.
    // For SSE we build a URL with query params for GET fallback compatibility.
    // The real streaming happens via fetch + ReadableStream below.
    throw new Error("Use streamTaskFetch instead");
  },
};

/**
 * Stream a task using fetch + ReadableStream (works with POST).
 * Yields parsed SSEEvent objects as they arrive.
 */
export async function* streamTaskFetch(
  payload: TaskRequest
): AsyncGenerator<SSEEvent> {
  const res = await fetch(`${API_BASE}/tasks/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, stream: true }),
  });

  if (!res.ok || !res.body) {
    const msg = await res.text().catch(() => "Unknown error");
    throw new Error(`Stream failed (${res.status}): ${msg}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;
        try {
          yield JSON.parse(jsonStr) as SSEEvent;
        } catch {
          // Malformed line — skip
        }
      }
    }
  }
}

/**
 * Resume a HITL-paused task and stream remaining events.
 */
export async function* streamResumeFetch(
  taskId: string,
  humanFeedback?: string
): AsyncGenerator<SSEEvent> {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ human_feedback: humanFeedback ?? null }),
  });

  if (!res.ok || !res.body) {
    const msg = await res.text().catch(() => "Unknown error");
    throw new Error(`Resume stream failed (${res.status}): ${msg}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;
        try {
          yield JSON.parse(jsonStr) as SSEEvent;
        } catch {
          // skip
        }
      }
    }
  }
}
