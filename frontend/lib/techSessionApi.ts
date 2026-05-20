import type { InputMode, SessionTurn } from "./sessionRuntime";

export type SessionResponse = {
  session_id?: string;
  turns_count?: number;
  final_report?: {
    summary?: string;
  } | null;
  cv_uploaded?: boolean;
  cv_profile?: {
    candidate_name?: string;
    name?: string;
    source_filename?: string;
  } | null;
  response_language?: string;
  updated_at?: string;
  turns?: SessionTurn[];
  interview_status?: string;
  finalized_at?: string;
  finalized_by?: string;
  preferred_input_mode?: string;
  proctoring_events?: Array<{
    time?: string;
    reason?: string;
    message?: string;
    count?: number;
  }>;
  proctoring_alerts_count?: number;
};

export async function fetchSession(sessionId: string, options?: { includeInsights?: boolean }) {
  const query = options?.includeInsights ? "?include_insights=1" : "";
  const res = await fetch(`/api/tech/session/${encodeURIComponent(sessionId)}${query}`, {
    method: "GET",
    cache: "no-store",
  });
  const data = (await res.json()) as SessionResponse & { detail?: string; error?: string };
  return { res, data };
}

export async function updatePreferredInputMode(sessionId: string, preferredInputMode: InputMode) {
  const res = await fetch(`/api/tech/session/${encodeURIComponent(sessionId)}/preferences`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ preferred_input_mode: preferredInputMode }),
  });
  const data = (await res.json()) as { error?: string; detail?: string; preferred_input_mode?: string };
  return { res, data };
}

export async function finalizeInterviewSession(sessionId: string, preferredInputMode: InputMode) {
  const res = await fetch(`/api/tech/session/${encodeURIComponent(sessionId)}/finalize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ preferred_input_mode: preferredInputMode, finalized_by: "user" }),
  });
  const data = await res.json();
  return { res, data };
}

export async function recordProctoringEvent(
  sessionId: string,
  payload: { reason: string; message: string; count: number; time?: string }
) {
  const res = await fetch(`/api/tech/session/${encodeURIComponent(sessionId)}/proctoring`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  return { res, data };
}
