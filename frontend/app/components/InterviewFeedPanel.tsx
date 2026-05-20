"use client";

import { FormEvent, Ref } from "react";
import { FeedItem } from "../../lib/interview";
import type { InputMode } from "../../lib/sessionRuntime";

type InterviewFeedPanelProps = {
  candidateText: string;
  copy: {
    title: string;
    subtitle: string;
    messageCountSingular: string;
    messageCountPlural: string;
    readyToBegin: string;
    interviewEnded: string;
    interviewEndedDescription: string;
    readyDescription: string;
    liveTranscript: string;
    candidateMessage: string;
    endedPlaceholder: string;
    voicePlaceholder: string;
    defaultPlaceholder: string;
    cvRequiredPlaceholder: string;
    sendingMessage: string;
    sendMessage: string;
    roleYou: string;
    roleInterviewer: string;
    roleSystem: string;
  };
  inputMode: InputMode;
  cvUploaded: boolean;
  interviewEnded: boolean;
  feedEndRef: Ref<HTMLDivElement>;
  feed: FeedItem[];
  interviewActive: boolean;
  liveTranscript: string;
  onCandidateTextChange: (value: string) => void;
  onSendMessage: (event: FormEvent) => Promise<void>;
  sending: boolean;
};

export function InterviewFeedPanel({
  candidateText,
  copy,
  inputMode,
  cvUploaded,
  interviewEnded,
  feedEndRef,
  feed,
  interviewActive: _interviewActive,
  liveTranscript,
  onCandidateTextChange,
  onSendMessage,
  sending,
}: InterviewFeedPanelProps) {
  const hasCandidateMessage = feed.some((item) => item.role === "you");
  const allowVoiceStarterMessage = inputMode === "voice" && !hasCandidateMessage;
  const textDisabled = !cvUploaded || interviewEnded || sending || (inputMode === "voice" && !allowVoiceStarterMessage);

  const formatRole = (role: FeedItem["role"]) => {
    if (role === "you") return copy.roleYou;
    if (role === "interviewer") return copy.roleInterviewer;
    return copy.roleSystem;
  };

  const isProctoringAlert = (item: FeedItem) =>
    item.role === "system" && /^(alerte surveillance|proctoring alert)\b/i.test(item.text.trim());
  const visibleFeed = feed.filter((item) => !isProctoringAlert(item));

  return (
    <aside className="chat-panel">
      <div className="chat-panel-glow" aria-hidden="true" />
      <div className="chat-header">
        <div className="chat-header-copy">
          <div className="section-kicker">{copy.title}</div>
          <div className="section-subtitle">{copy.subtitle}</div>
        </div>
        <span className="message-count">
          <span className="message-count-pulse" aria-hidden="true" />
          {visibleFeed.length} {visibleFeed.length > 1 ? copy.messageCountPlural : copy.messageCountSingular}
        </span>
      </div>

      <div className="feed-shell">
        <div className="feed">
          {visibleFeed.length === 0 ? (
            <div className="empty-state">
              <div className="empty-title">{interviewEnded ? copy.interviewEnded : copy.readyToBegin}</div>
              <div className="empty-text">
                {interviewEnded
                  ? copy.interviewEndedDescription
                  : copy.readyDescription}
              </div>
            </div>
          ) : (
            visibleFeed.map((item) => (
              <div
                key={item.id}
                className={`item ${item.role}`}
                onCopy={item.role === "interviewer" ? (event) => event.preventDefault() : undefined}
                onCut={item.role === "interviewer" ? (event) => event.preventDefault() : undefined}
              >
                <div className="item-meta">
                  <span className="item-role">{formatRole(item.role)}</span>
                  <time className="item-time">{item.timestamp}</time>
                </div>
                <div className="item-text">{item.text}</div>
              </div>
            ))
          )}
          <div ref={feedEndRef} />
        </div>
      </div>

      <form className="chat-composer" onSubmit={onSendMessage}>
        {liveTranscript ? (
          <div className="chat-live-transcript" aria-live="polite">
            <div className="chat-live-indicator" aria-hidden="true">
              <span className="chat-live-indicator-dot" />
              <span className="chat-live-indicator-dot" />
              <span className="chat-live-indicator-dot" />
            </div>
            <span className="sr-only">{`${copy.liveTranscript}: ${liveTranscript}`}</span>
          </div>
        ) : null}
        <label className="chat-input-label" htmlFor="candidate-message">
          <span className="sr-only">{copy.candidateMessage}</span>
          <div className={`chat-input-shell ${candidateText.trim() ? "filled" : ""}`}>
            <input
              id="candidate-message"
              className="chat-input-field"
              value={candidateText}
              onChange={(event) => onCandidateTextChange(event.target.value)}
              placeholder={
                interviewEnded
                  ? copy.endedPlaceholder
                  : !cvUploaded
                  ? copy.cvRequiredPlaceholder
                  : inputMode === "voice" && !allowVoiceStarterMessage
                  ? copy.voicePlaceholder
                  : copy.defaultPlaceholder
              }
              onPaste={inputMode === "voice" && hasCandidateMessage ? (event) => event.preventDefault() : undefined}
              disabled={textDisabled}
            />
            <button
              type="submit"
              className="chat-send"
              disabled={textDisabled || !candidateText.trim()}
              aria-label={sending ? copy.sendingMessage : copy.sendMessage}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 12L18 12" />
                <path d="M12 6L18 12L12 18" />
              </svg>
            </button>
          </div>
        </label>
      </form>
    </aside>
  );
}
