"use client";

import { useEffect, useMemo, useState } from "react";
import { SessionHistoryEntry } from "../../lib/sessionHistory";

type SessionHistorySidebarProps = {
  activeSessionId: string;
  sessions: SessionHistoryEntry[];
  loading: boolean;
  error: string;
  open: boolean;
  standalone?: boolean;
  searchValue: string;
  onSearchChange: (value: string) => void;
  onCreateSession: () => void;
  onOpenSession: (sessionId: string) => void;
  onRenameSession: (sessionId: string, currentTitle: string) => void | Promise<void>;
  onTogglePinned: (sessionId: string, nextPinned: boolean) => void | Promise<void>;
  onToggleArchived: (sessionId: string, nextArchived: boolean) => void | Promise<void>;
  onDeleteSessions: (sessions: SessionHistoryEntry[]) => void | Promise<void>;
  onToggle: () => void;
  copy?: {
    hideHistory: string;
    showHistory: string;
    brandSubtitle: string;
    closePanel: string;
    newInterview: string;
    searchChats: string;
    score: string;
    all: string;
    archived: string;
    recents: string;
    showActive: string;
    showArchived: string;
    loadingHistory: string;
    noMatchingConversation: string;
    noArchivedConversation: string;
    noSavedConversation: string;
    openHistoryFallback: string;
    conversationActions: string;
    rename: string;
    pin: string;
    unpin: string;
    archive: string;
    unarchive: string;
    delete: string;
    select: string;
    cancelSelection: string;
    deleteSelection: string;
    selectedLabel: string;
    selectConversation: string;
    pinned: string;
    today: string;
    yesterday: string;
    previous7Days: string;
    previous30Days: string;
    older: string;
  };
};

type SessionSection = {
  key: string;
  label: string;
  sessions: SessionHistoryEntry[];
};

function matchesSearch(session: SessionHistoryEntry, query: string) {
  if (!query.trim()) return true;
  const normalized = query.trim().toLowerCase();
  const haystack = [session.title, session.preview, session.candidate_name, session.headline].join(" ").toLowerCase();
  return haystack.includes(normalized);
}

function buildDateSectionKey(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "older";
  }

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfItemDay = new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());
  const dayDiff = Math.floor((startOfToday.getTime() - startOfItemDay.getTime()) / 86400000);

  if (dayDiff <= 0) return "today";
  if (dayDiff === 1) return "yesterday";
  if (dayDiff <= 7) return "last_7_days";
  if (dayDiff <= 30) return "last_30_days";
  return "older";
}

function buildSections(
  sessions: SessionHistoryEntry[],
  labels: {
    pinned: string;
    today: string;
    yesterday: string;
    last7Days: string;
    last30Days: string;
    older: string;
  }
) {
  const sectionLabels: Record<string, string> = {
    pinned: labels.pinned,
    today: labels.today,
    yesterday: labels.yesterday,
    last_7_days: labels.last7Days,
    last_30_days: labels.last30Days,
    older: labels.older,
  };

  const pinned = sessions.filter((session) => session.pinned);
  const regular = sessions.filter((session) => !session.pinned);
  const groups = new Map<string, SessionHistoryEntry[]>();

  regular.forEach((session) => {
    const key = buildDateSectionKey(session.history_at || session.updated_at);
    const existing = groups.get(key) || [];
    existing.push(session);
    groups.set(key, existing);
  });

  const orderedKeys = ["today", "yesterday", "last_7_days", "last_30_days", "older"];
  const sections: SessionSection[] = [];

  if (pinned.length) {
    sections.push({ key: "pinned", label: sectionLabels.pinned, sessions: pinned });
  }

  orderedKeys.forEach((key) => {
    const items = groups.get(key) || [];
    if (!items.length) return;
    sections.push({ key, label: sectionLabels[key], sessions: items });
  });

  return sections;
}

function SessionRow({
  entry,
  active,
  selected,
  selectionMode,
  menuOpen,
  copy,
  onOpen,
  onToggleSelected,
  onMenuToggle,
  onRename,
  onTogglePinned,
  onToggleArchived,
  onDelete,
}: {
  entry: SessionHistoryEntry;
  active: boolean;
  selected: boolean;
  selectionMode: boolean;
  menuOpen: boolean;
  copy: NonNullable<SessionHistorySidebarProps["copy"]>;
  onOpen: (sessionId: string) => void;
  onToggleSelected: (sessionId: string) => void;
  onMenuToggle: (sessionId: string | null) => void;
  onRename: (sessionId: string, currentTitle: string) => void | Promise<void>;
  onTogglePinned: (sessionId: string, nextPinned: boolean) => void | Promise<void>;
  onToggleArchived: (sessionId: string, nextArchived: boolean) => void | Promise<void>;
  onDelete: (session: SessionHistoryEntry) => void | Promise<void>;
}) {
  return (
    <div
      className={`history-chat-row ${active ? "is-active" : ""} ${selected ? "is-selected" : ""} ${
        selectionMode ? "is-selection-mode" : ""
      }`.trim()}
    >
      {selectionMode ? (
        <button
          type="button"
          className={`history-chat-select ${selected ? "is-selected" : ""}`}
          aria-label={copy.selectConversation}
          aria-pressed={selected}
          onClick={() => onToggleSelected(entry.session_id)}
        >
          <span className="history-chat-select-box" aria-hidden="true">
            {selected ? (
              <svg viewBox="0 0 24 24">
                <path d="M5 12.5 10 17l9-10" />
              </svg>
            ) : null}
          </span>
        </button>
      ) : null}

      <button
        type="button"
        className="history-chat-main"
        onClick={() => {
          if (selectionMode) {
            onToggleSelected(entry.session_id);
            return;
          }
          onOpen(entry.session_id);
        }}
      >
        <strong>{entry.title}</strong>
        <span className="history-chat-subline">
          {entry.candidate_name}
          {entry.headline ? ` | ${entry.headline}` : ""}
        </span>
        <span className="history-chat-preview">{entry.preview || copy.openHistoryFallback}</span>
      </button>

      <div className="history-chat-actions">
        {entry.pinned ? <span className="history-chat-pin" aria-hidden="true">&bull;</span> : null}
        {!selectionMode ? (
          <>
            <button
              type="button"
              className="history-chat-menu-trigger"
              aria-label={copy.conversationActions}
              onClick={(event) => {
                event.stopPropagation();
                onMenuToggle(menuOpen ? null : entry.session_id);
              }}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="5" cy="12" r="1.3" />
                <circle cx="12" cy="12" r="1.3" />
                <circle cx="19" cy="12" r="1.3" />
              </svg>
            </button>

            {menuOpen ? (
              <div className="history-chat-menu">
                <button
                  type="button"
                  onClick={() => {
                    onMenuToggle(null);
                    void onRename(entry.session_id, entry.title);
                  }}
                >
                  {copy.rename}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onMenuToggle(null);
                    void onTogglePinned(entry.session_id, !entry.pinned);
                  }}
                >
                  {entry.pinned ? copy.unpin : copy.pin}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onMenuToggle(null);
                    void onToggleArchived(entry.session_id, !entry.archived);
                  }}
                >
                  {entry.archived ? copy.unarchive : copy.archive}
                </button>
                <button
                  type="button"
                  className="is-danger"
                  onClick={() => {
                    onMenuToggle(null);
                    void onDelete(entry);
                  }}
                >
                  {copy.delete}
                </button>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}

export function SessionHistorySidebar({
  activeSessionId,
  sessions,
  loading,
  error,
  open,
  standalone = false,
  searchValue,
  onSearchChange,
  onCreateSession,
  onOpenSession,
  onRenameSession,
  onTogglePinned,
  onToggleArchived,
  onDeleteSessions,
  onToggle,
  copy = {
    hideHistory: "Hide history",
    showHistory: "Show history",
    brandSubtitle: "Candidate history",
    closePanel: "Close panel",
    newInterview: "New interview",
    searchChats: "Search chats",
    score: "Score",
    all: "All",
    archived: "Archived",
    recents: "Recents",
    showActive: "Show active",
    showArchived: "Show archived",
    loadingHistory: "Loading candidate history...",
    noMatchingConversation: "No matching conversation was found.",
    noArchivedConversation: "No archived conversation yet.",
    noSavedConversation: "No saved conversation yet.",
    openHistoryFallback: "Open this interview history.",
    conversationActions: "Conversation actions",
    rename: "Rename",
    pin: "Pin",
    unpin: "Unpin",
    archive: "Archive",
    unarchive: "Unarchive",
    delete: "Delete",
    select: "Select",
    cancelSelection: "Cancel",
    deleteSelection: "Delete selection",
    selectedLabel: "selected",
    selectConversation: "Select conversation",
    pinned: "Pinned",
    today: "Today",
    yesterday: "Yesterday",
    previous7Days: "Previous 7 Days",
    previous30Days: "Previous 30 Days",
    older: "Older",
  },
}: SessionHistorySidebarProps) {
  const [menuSessionId, setMenuSessionId] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [scoreFilter, setScoreFilter] = useState("all");
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedSessionIds, setSelectedSessionIds] = useState<string[]>([]);

  useEffect(() => {
    if (!open) {
      setMenuSessionId(null);
      setSelectionMode(false);
      setSelectedSessionIds([]);
    }
  }, [open]);

  useEffect(() => {
    if (!menuSessionId) return;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest(".history-chat-actions")) {
        return;
      }
      setMenuSessionId(null);
    };

    window.addEventListener("pointerdown", handlePointerDown);
    return () => window.removeEventListener("pointerdown", handlePointerDown);
  }, [menuSessionId]);

  const { activeSessions, archivedSessions } = useMemo(() => {
    const filtered = sessions.filter((session) => {
      if (!matchesSearch(session, searchValue)) {
        return false;
      }

      const score = typeof session.score_total === "number" ? session.score_total : null;
      if (scoreFilter === "all") return true;
      if (scoreFilter === "high") return score !== null && score >= 80;
      if (scoreFilter === "mid") return score !== null && score >= 60 && score < 80;
      if (scoreFilter === "low") return score !== null && score < 60;
      if (scoreFilter === "unscored") return score === null;
      return true;
    });
    return {
      activeSessions: filtered.filter((session) => !session.archived),
      archivedSessions: filtered.filter((session) => session.archived),
    };
  }, [scoreFilter, searchValue, sessions]);

  const visibleSessions = showArchived ? archivedSessions : activeSessions;
  const selectedCount = selectedSessionIds.length;

  useEffect(() => {
    const visibleSessionIdSet = new Set(visibleSessions.map((session) => session.session_id));
    setSelectedSessionIds((prev) => {
      const filtered = prev.filter((sessionId) => visibleSessionIdSet.has(sessionId));
      return filtered.length === prev.length ? prev : filtered;
    });
  }, [visibleSessions]);

  const toggleSessionSelected = (sessionId: string) => {
    setSelectedSessionIds((prev) =>
      prev.includes(sessionId) ? prev.filter((current) => current !== sessionId) : [...prev, sessionId]
    );
  };

  const toggleSelectionMode = () => {
    setMenuSessionId(null);
    setSelectionMode((prev) => {
      if (prev) {
        setSelectedSessionIds([]);
      }
      return !prev;
    });
  };

  const deleteSelectedSessions = () => {
    const selectedSessions = visibleSessions.filter((session) => selectedSessionIds.includes(session.session_id));
    if (!selectedSessions.length) return;
    void onDeleteSessions(selectedSessions);
  };

  const sections = buildSections(visibleSessions, {
    pinned: copy.pinned,
    today: copy.today,
    yesterday: copy.yesterday,
    last7Days: copy.previous7Days,
    last30Days: copy.previous30Days,
    older: copy.older,
  });
  const showSectionHead = visibleSessions.length > 0 || showArchived || archivedSessions.length > 0;

  return (
    <>
      {!standalone ? (
        <button
          type="button"
          className={`history-sidebar-toggle ${open ? "is-open" : ""}`}
          onClick={onToggle}
          aria-label={open ? copy.hideHistory : copy.showHistory}
          aria-expanded={open}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 6h16" />
            <path d="M4 12h16" />
            <path d="M4 18h16" />
          </svg>
        </button>
      ) : null}

      {!standalone && open ? <button type="button" className="history-sidebar-backdrop" onClick={onToggle} aria-label={copy.hideHistory} /> : null}

      <aside className={`history-sidebar ${open ? "is-open" : ""} ${standalone ? "is-standalone" : ""}`}>
        <div className={`history-sidebar-inner ${showSectionHead ? "" : "is-compact"}`.trim()}>
          <div className="history-sidebar-top">
            {!standalone ? (
              <button type="button" className="history-close-button" onClick={onToggle} aria-label={copy.closePanel}>
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6 6l12 12" />
                  <path d="M18 6L6 18" />
                </svg>
              </button>
            ) : null}

            <div className="history-search-row">
              <label className="history-search-shell" htmlFor="history-search">
                <span className="history-search-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <circle cx="11" cy="11" r="6.5" />
                    <path d="M16 16l4 4" />
                  </svg>
                </span>
                <input
                  id="history-search"
                  value={searchValue}
                  onChange={(event) => onSearchChange(event.target.value)}
                  placeholder={copy.searchChats}
                />
              </label>

              <label className="history-score-filter" htmlFor="history-score-filter">
                <span className="history-score-filter-label">{copy.score}</span>
                <select
                  id="history-score-filter"
                  value={scoreFilter}
                  onChange={(event) => setScoreFilter(event.target.value)}
                >
                  <option value="all">{copy.all}</option>
                  <option value="high">80+</option>
                  <option value="mid">60-79</option>
                  <option value="low">{"<60"}</option>
                  <option value="unscored">N/A</option>
                </select>
              </label>
            </div>
          </div>

          {showSectionHead ? (
            <div className="history-section-head">
              <span>{showArchived ? copy.archived : copy.recents}</span>
              <div className="history-section-actions">
                {visibleSessions.length && !selectionMode ? (
                  <button type="button" className="history-inline-toggle" onClick={toggleSelectionMode}>
                    {copy.select}
                  </button>
                ) : null}
                {archivedSessions.length ? (
                  <button type="button" className="history-inline-toggle" onClick={() => setShowArchived((prev) => !prev)}>
                    {showArchived ? copy.showActive : copy.showArchived}
                  </button>
                ) : null}
                <strong>{visibleSessions.length}</strong>
              </div>
            </div>
          ) : null}

          {selectionMode ? (
            <div className="history-selection-bar">
              <div className="history-selection-copy">
                <strong>{selectedCount}</strong>
                <span>{copy.selectedLabel}</span>
              </div>
              <div className="history-selection-actions">
                <button
                  type="button"
                  className="history-inline-toggle is-danger"
                  onClick={deleteSelectedSessions}
                  disabled={!selectedCount}
                >
                  {copy.deleteSelection}
                </button>
                <button type="button" className="history-inline-toggle" onClick={toggleSelectionMode}>
                  {copy.cancelSelection}
                </button>
              </div>
            </div>
          ) : null}

          <div className="history-scroll">
            {loading ? <div className="history-empty-card">{copy.loadingHistory}</div> : null}
            {!loading && error ? <div className="history-empty-card is-error">{error}</div> : null}
            {!loading && !error && sections.length === 0 ? (
              <div className="history-empty-card">
                {searchValue.trim()
                  ? copy.noMatchingConversation
                  : showArchived
                  ? copy.noArchivedConversation
                  : copy.noSavedConversation}
              </div>
            ) : null}

            {!loading && !error
              ? sections.map((section) => (
                  <section key={section.key} className="history-chat-section">
                    <div className="history-chat-section-title">{section.label}</div>
                    <div className="history-chat-list">
                      {section.sessions.map((session) => (
                        <SessionRow
                          key={session.session_id}
                          entry={session}
                          active={session.session_id === activeSessionId}
                          selected={selectedSessionIds.includes(session.session_id)}
                          selectionMode={selectionMode}
                          menuOpen={menuSessionId === session.session_id}
                          copy={copy}
                          onOpen={onOpenSession}
                          onToggleSelected={toggleSessionSelected}
                          onMenuToggle={setMenuSessionId}
                          onRename={onRenameSession}
                          onTogglePinned={onTogglePinned}
                          onToggleArchived={onToggleArchived}
                          onDelete={(targetSession) => {
                            void onDeleteSessions([targetSession]);
                          }}
                        />
                      ))}
                    </div>
                  </section>
                ))
              : null}
          </div>
        </div>
      </aside>
    </>
  );
}
