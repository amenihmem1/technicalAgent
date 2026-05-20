export type FeedRole = "you" | "interviewer" | "system";

export type FeedItem = {
  id: number;
  role: FeedRole;
  text: string;
  timestamp: string;
};

export type InterviewerUtterance = {
  id: number;
  text: string;
  audioBase64?: string;
  audioMimeType?: string;
};

export function createFeedItem(role: FeedRole, text: string): FeedItem {
  const createdAt = new Date();
  return {
    id: createdAt.getTime() + Math.floor(Math.random() * 1000),
    role,
    text,
    timestamp: createdAt.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    }),
  };
}

export function formatElapsed(seconds: number) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}
