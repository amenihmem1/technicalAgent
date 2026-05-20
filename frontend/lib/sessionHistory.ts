export type SessionHistoryEntry = {
  session_id: string;
  candidate_key: string;
  candidate_name: string;
  headline: string;
  updated_at: string;
  /** First save time; preserved across updates */
  created_at?: string;
  /** Date of the interview for grouping/display (finalized_at, first turn, or created_at) */
  history_at?: string;
  finalized_at?: string;
  turns_count: number;
  score_total: number | null;
  status: "completed" | "active" | "draft";
  title: string;
  preview: string;
  response_language: string;
  pinned: boolean;
  archived: boolean;
  title_customized: boolean;
  proctoring_alerts_count?: number;
};

export type CandidateProgression = {
  latest_score: number | null;
  previous_score: number | null;
  delta: number | null;
  label: "improving" | "declining" | "stable" | "first_completed_session" | "no_completed_session";
};

export type CandidateHistoryGroup = {
  candidate_key: string;
  candidate_name: string;
  headline: string;
  latest_updated_at: string;
  sessions_count: number;
  progression: CandidateProgression;
  sessions: SessionHistoryEntry[];
};

export type SessionHistoryResponse = {
  candidates: CandidateHistoryGroup[];
  sessions: SessionHistoryEntry[];
  total_candidates: number;
  total_sessions: number;
};

/** Milliseconds for charts and timelines — stable across later saves/opens. */
export function getSessionHistoryAnchorMs(session: SessionHistoryEntry): number {
  const raw =
    session.history_at ||
    session.finalized_at ||
    session.created_at ||
    session.updated_at ||
    "";
  const t = new Date(raw).getTime();
  return Number.isFinite(t) ? t : NaN;
}
