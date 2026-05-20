"use client";

import type { ReactNode } from "react";
import type { InputMode } from "../../lib/sessionRuntime";

type MeetingHeaderProps = {
  cvFileSelected: boolean;
  cvUploaded: boolean;
  finalReportReady: boolean;
  inputMode: InputMode;
  interviewEnded: boolean;
  interviewStarted: boolean;
  interviewTimeLabel: string;
  controls?: ReactNode;
  copy: {
    title: string;
    subtitle: string;
    session: string;
    ended: string;
    running: string;
    active: string;
    finalizedByUser: string;
    interviewStarted: string;
    waitingLaunch: string;
    resume: string;
    uploaded: string;
    notUploaded: string;
    fileSelected: string;
    uploadCvToStart: string;
    report: string;
    available: string;
    inProgress: string;
    readyForDownload: string;
    generatedAtEnd: string;
    timer: string;
    finalDuration: string;
    liveInterviewClock: string;
    startsAtFirstReply: string;
  };
};

export function MeetingHeader({
  cvFileSelected,
  cvUploaded,
  finalReportReady,
  inputMode,
  interviewEnded,
  interviewStarted,
  interviewTimeLabel,
  controls,
  copy,
}: MeetingHeaderProps) {
  const sessionCardClass = interviewEnded ? "status-danger" : interviewStarted ? "status-live" : "status-idle";
  const resumeCardClass = cvUploaded ? "status-success" : "status-danger";
  const reportCardClass = finalReportReady ? "status-success" : "status-progress";
  const timerCardClass = interviewEnded ? "status-progress" : interviewStarted ? "status-live" : "status-idle";

  return (
    <header className="meeting-topbar">
      <div className="topbar-aura topbar-aura-left" aria-hidden="true" />
      <div className="topbar-aura topbar-aura-right" aria-hidden="true" />
      <div className="brand-block">
        <div className="brand-lockup">
          <div className="brand-copy">
            <div className="brand-wordmark">{copy.title}</div>
            <p className="brand-subtitle">{copy.subtitle}</p>
          </div>
        </div>
      </div>
      <div className="topbar-meta">
        {controls ? (
          <div className="status-card controls-card">
            <div className="status-card-copy controls-card-copy">
              <div className="topbar-controls">{controls}</div>
            </div>
          </div>
        ) : null}

        <div className={`status-card session-card ${sessionCardClass}`}>
          <span className="status-card-icon session" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M20 12A8 8 0 1 1 4 12" />
              <path d="M9 12l2 2 4-5" />
            </svg>
          </span>
          <div className="status-card-copy">
            <span className="status-card-label">{copy.session}</span>
            <strong>{interviewEnded ? copy.ended : interviewStarted ? copy.running : copy.active}</strong>
            <span className="status-card-meta">
              {interviewEnded
                ? copy.finalizedByUser
                : interviewStarted
                  ? `${copy.interviewStarted} | ${inputMode}`
                  : `${copy.waitingLaunch} | ${inputMode}`}
            </span>
          </div>
        </div>

        <div className={`status-card resume-card ${resumeCardClass}`}>
          <span className="status-card-icon resume" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M8 3h6l5 5v11a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
              <path d="M14 3v5h5" />
              <path d="M9 13h6" />
              <path d="M9 17h4" />
            </svg>
          </span>
          <div className="status-card-copy">
            <span className="status-card-label">{copy.resume}</span>
            <strong>{cvUploaded ? copy.uploaded : copy.notUploaded}</strong>
            <span className="status-card-meta">{cvFileSelected ? copy.fileSelected : copy.uploadCvToStart}</span>
          </div>
        </div>

        <div className={`status-card report-card ${reportCardClass}`}>
          <span className="status-card-icon report" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
              <path d="M14 3v5h5" />
              <path d="M9 14h6" />
              <path d="M9 10h2" />
              <path d="M9 18h6" />
            </svg>
          </span>
          <div className="status-card-copy">
            <span className="status-card-label">{copy.report}</span>
            <strong>{finalReportReady ? copy.available : copy.inProgress}</strong>
            <span className="status-card-meta">{finalReportReady ? copy.readyForDownload : copy.generatedAtEnd}</span>
          </div>
        </div>

        <div className={`status-card timer-card ${timerCardClass}`}>
          <span className="status-card-icon timer" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="8" />
              <path d="M12 8v5l3 2" />
            </svg>
          </span>
          <div className="status-card-copy">
            <span className="status-card-label">{copy.timer}</span>
            <strong>{interviewTimeLabel}</strong>
            <span className="status-card-meta">
              {interviewEnded ? copy.finalDuration : interviewStarted ? copy.liveInterviewClock : copy.startsAtFirstReply}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
