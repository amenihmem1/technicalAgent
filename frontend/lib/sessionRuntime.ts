import { createFeedItem, type FeedItem } from "./interview";

export type SessionTurn = {
  time?: string;
  candidate_text?: string;
  say?: string;
};

export type InputMode = "text" | "voice" | "mixed";

export function createSessionId() {
  return `session-${Date.now()}`;
}

export function formatTimestamp(value?: string) {
  if (!value) return createFeedItem("system", "").timestamp;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return createFeedItem("system", "").timestamp;
  return parsed.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function buildFeedFromTurns(turns: SessionTurn[], summary?: string): FeedItem[] {
  const items: FeedItem[] = [];

  turns.forEach((turn, index) => {
    const stamp = formatTimestamp(turn.time);
    const candidateText = String(turn.candidate_text || "").trim();
    const interviewerText = String(turn.say || "").trim();

    if (candidateText) {
      items.push({
        id: index * 2 + 1,
        role: "you",
        text: `[Candidate]: ${candidateText}`,
        timestamp: stamp,
      });
    }

    if (interviewerText) {
      items.push({
        id: index * 2 + 2,
        role: "interviewer",
        text: `[Interviewer]: ${interviewerText}`,
        timestamp: stamp,
      });
    }
  });

  const finalSummary = String(summary || "").trim();
  if (finalSummary) {
    items.push({
      id: turns.length * 2 + 3,
      role: "system",
      text: `Final report: ${finalSummary}`,
      timestamp: formatTimestamp(turns[turns.length - 1]?.time),
    });
  }

  return items;
}

export function computeElapsedFromTurns(turns: SessionTurn[]) {
  const first = turns[0]?.time ? new Date(turns[0].time) : null;
  const last = turns[turns.length - 1]?.time ? new Date(turns[turns.length - 1].time as string) : null;

  if (!first || !last || Number.isNaN(first.getTime()) || Number.isNaN(last.getTime())) {
    return 0;
  }

  return Math.max(0, Math.floor((last.getTime() - first.getTime()) / 1000));
}

export function normalizeInputMode(value?: string): InputMode {
  if (value === "text" || value === "voice" || value === "mixed") {
    return value;
  }
  return "voice";
}
