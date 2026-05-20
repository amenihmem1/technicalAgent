"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { HistoryActionDialog } from "../components/HistoryActionDialog";
import { SessionHistorySidebar } from "../components/SessionHistorySidebar";
import { SessionHistoryEntry, SessionHistoryResponse } from "../../lib/sessionHistory";
import styles from "../report/[sessionId]/report-dashboard.module.css";
import logoImage from "../../img/logoS-transparent.png";

type Language = "fr" | "en";
type Theme = "light" | "dark";

type HistoryDialogState =
  | {
      mode: "rename";
      sessionId: string;
      title: string;
      value: string;
    }
  | {
      mode: "delete";
      sessionIds: string[];
      titles: string[];
    }
  | null;

type AnimatedHistoryStats = {
  pinned: number;
  archived: number;
};

function formatSessionHistoryDate(value: string | undefined, language: Language) {
  if (!value?.trim()) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleDateString(language === "fr" ? "fr-FR" : "en-US", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function SidebarIcon({ type }: { type: "dashboard" | "hire" | "file" | "help" | "interview" | "memory" }) {
  if (type === "memory") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9 5.5A2.5 2.5 0 0 1 11.5 3h1A2.5 2.5 0 0 1 15 5.5V6h1.5A2.5 2.5 0 0 1 19 8.5v9a2.5 2.5 0 0 1-2.5 2.5h-9A2.5 2.5 0 0 1 5 17.5v-9A2.5 2.5 0 0 1 7.5 6H9Z" />
        <path d="M9 6h6" />
        <path d="M12 10v4" />
        <path d="M10 12h4" />
      </svg>
    );
  }
  if (type === "interview") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 6h10a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3h-6l-4 3v-3H7a3 3 0 0 1-3-3V9a3 3 0 0 1 3-3Z" />
        <path d="M9 11h6" />
        <path d="M9 14h4" />
      </svg>
    );
  }
  if (type === "hire") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3.5 12s3.2-5.5 8.5-5.5S20.5 12 20.5 12 17.3 17.5 12 17.5 3.5 12 3.5 12Z" />
        <circle cx="12" cy="12" r="2.5" />
        <path d="M17.2 5.2 19 3.4" />
        <path d="M18.7 7.7h2.4" />
      </svg>
    );
  }
  if (type === "file") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
        <path d="M14 3v5h5" />
        <path d="M9 13h6" />
      </svg>
    );
  }
  if (type === "help") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z" />
        <path d="M9.4 9.2a2.7 2.7 0 1 1 4.2 2.2c-.9.6-1.6 1.1-1.6 2.1" />
        <path d="M12 16.8h.01" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 4h6v6H4Z" />
      <path d="M14 4h6v6h-6Z" />
      <path d="M4 14h6v6H4Z" />
      <path d="M14 14h6v6h-6Z" />
    </svg>
  );
}

const historyTranslations = {
  fr: {
    mainMenu: "Menu principal",
    sidebarWorkspace: "Espace de travail",
    sidebarReports: "Rapports",
    sidebarTools: "Outils",
    analytics: "Analytique",
    interview: "Interview",
    hr: "Technique",
    insights: "Insights",
    detailedReport: "Rapport detaille",
    historyNav: "Historique",
    help: "Help",
    title: "Historique",
    subtitle: "Historique des entretiens techniques et conversations candidates.",
    totalInterviews: "Total entretiens",
    completed: "completes",
    activeSessions: "Sessions actives",
    activeHint: "brouillon",
    averageScore: "Score moyen",
    scoresAvailable: "scores disponibles",
    pinnedSessions: "Sessions epinglees",
    recruiterFavorites: "favoris recruteur",
    archivedSessions: "Sessions archivees",
    archivedHint: "conversations masquees",
    recentActivity: "Activite recente",
    noRecentSession: "Aucune session recente",
    noRecentSessionDesc: "Commence un nouvel entretien pour alimenter l'historique des candidats.",
    noRecentCandidate: "Aucun candidat recent",
    newInterview: "Nouvel entretien",
    quickActions: "Actions rapides",
    openLastReport: "Ouvrir dernier rapport",
    goToInterview: "Aller a l'entretien",
    lightMode: "Clair",
    darkMode: "Sombre",
    renameTitle: "Renommer la conversation",
    deleteTitle: "Supprimer cette conversation ?",
    deleteSelectedTitle: "Supprimer les conversations selectionnees ?",
    renameDescription: "Choisissez un titre plus clair pour retrouver facilement cet entretien plus tard.",
    deleteDescription: "sera supprimee de votre historique. Cette action est definitive.",
    deleteSelectedDescription: "conversations seront supprimees de votre historique. Cette action est definitive.",
    delete: "Supprimer",
    select: "Selectionner",
    cancelSelection: "Annuler la selection",
    deleteSelection: "Supprimer la selection",
    selectedLabel: "selectionnees",
    selectConversation: "Selectionner la conversation",
    save: "Enregistrer",
    close: "Fermer",
    cancel: "Annuler",
    newTitle: "Nouveau titre",
    conversationName: "Nom de la conversation",
    pleaseWait: "Veuillez patienter...",
    historyBrandSubtitle: "Historique des candidats",
    searchChats: "Rechercher des conversations",
    score: "Score",
    all: "Tous",
    archived: "Archives",
    recents: "Recents",
    showActive: "Afficher les actives",
    showArchived: "Afficher les archives",
    loadingHistory: "Chargement de l'historique candidat...",
    noMatchingConversation: "Aucune conversation correspondante n'a ete trouvee.",
    noArchivedConversation: "Aucune conversation archivee pour le moment.",
    noSavedConversation: "Aucune conversation enregistree pour le moment.",
    openHistoryFallback: "Ouvrir cet historique d'entretien.",
    conversationActions: "Actions de la conversation",
    rename: "Renommer",
    pin: "Epingler",
    unpin: "Desepingler",
    archive: "Archiver",
    unarchive: "Desarchiver",
    pinned: "Epingles",
    today: "Aujourd'hui",
    yesterday: "Hier",
    previous7Days: "7 derniers jours",
    previous30Days: "30 derniers jours",
    older: "Plus ancien",
  },
  en: {
    mainMenu: "Main menu",
    sidebarWorkspace: "Workspace",
    sidebarReports: "Reports",
    sidebarTools: "Tools",
    analytics: "Analytics",
    interview: "Interview",
    hr: "Technical",
    insights: "Insights",
    detailedReport: "Detailed report",
    historyNav: "History",
    help: "Help",
    title: "History",
    subtitle: "Technical interview and candidate conversation history.",
    totalInterviews: "Total interviews",
    completed: "completed",
    activeSessions: "Active sessions",
    activeHint: "draft",
    averageScore: "Average score",
    scoresAvailable: "scores available",
    pinnedSessions: "Pinned sessions",
    recruiterFavorites: "recruiter favorites",
    archivedSessions: "Archived sessions",
    archivedHint: "hidden conversations",
    recentActivity: "Recent activity",
    noRecentSession: "No recent session",
    noRecentSessionDesc: "Start a new interview to build the candidate history.",
    noRecentCandidate: "No recent candidate",
    newInterview: "New interview",
    quickActions: "Quick actions",
    openLastReport: "Open last report",
    goToInterview: "Go to interview",
    lightMode: "Light",
    darkMode: "Dark",
    renameTitle: "Rename conversation",
    deleteTitle: "Delete this conversation?",
    deleteSelectedTitle: "Delete selected conversations?",
    renameDescription: "Choose a clearer title so this interview is easier to find later.",
    deleteDescription: "will be removed from your history. This action cannot be undone.",
    deleteSelectedDescription: "conversations will be removed from your history. This action cannot be undone.",
    delete: "Delete",
    select: "Select",
    cancelSelection: "Cancel selection",
    deleteSelection: "Delete selection",
    selectedLabel: "selected",
    selectConversation: "Select conversation",
    save: "Save",
    close: "Close",
    cancel: "Cancel",
    newTitle: "New title",
    conversationName: "Conversation name",
    pleaseWait: "Please wait...",
    historyBrandSubtitle: "Candidate history",
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
    pinned: "Pinned",
    today: "Today",
    yesterday: "Yesterday",
    previous7Days: "Previous 7 Days",
    previous30Days: "Previous 30 Days",
    older: "Older",
  },
} as const;

export default function HistoryPage() {
  const router = useRouter();
  const [language, setLanguage] = useState<Language>("fr");
  const [theme, setTheme] = useState<Theme>("light");
  const [historySessions, setHistorySessions] = useState<SessionHistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [historySearch, setHistorySearch] = useState("");
  const [historyDialog, setHistoryDialog] = useState<HistoryDialogState>(null);
  const [historyDialogBusy, setHistoryDialogBusy] = useState(false);
  const [animatedStats, setAnimatedStats] = useState<AnimatedHistoryStats>({ pinned: 0, archived: 0 });
  const latestSessionId = historySessions[0]?.session_id || "";
  const reportHref = latestSessionId ? `/report/${encodeURIComponent(latestSessionId)}?view=report` : "/";
  const insightsHref = latestSessionId ? `/report/${encodeURIComponent(latestSessionId)}?view=insights` : "/";
  const pinnedCount = historySessions.filter((session) => session.pinned).length;
  const archivedCount = historySessions.filter((session) => session.archived).length;
  const latestSession = historySessions[0] || null;
  const latestSessionCompleted = latestSession?.status === "completed";
  const latestSessionDateLabel = latestSession
    ? formatSessionHistoryDate(
        latestSession.history_at ||
          latestSession.finalized_at ||
          latestSession.created_at ||
          latestSession.updated_at,
        language
      )
    : "";
  const copy = historyTranslations[language];

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedTheme = window.localStorage.getItem("report-dashboard-theme");
    if (storedTheme === "light" || storedTheme === "dark") {
      setTheme(storedTheme);
    } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      setTheme("dark");
    }

    const storedLanguage = window.localStorage.getItem("dashboard-language");
    if (storedLanguage === "fr" || storedLanguage === "en") {
      setLanguage(storedLanguage);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("report-dashboard-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("dashboard-language", language);
  }, [language]);

  const loadHistory = async () => {
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const res = await fetch("/api/tech/sessions?limit=80", { method: "GET", cache: "no-store" });
      const data = (await res.json()) as SessionHistoryResponse & { error?: string };
      if (!res.ok) {
        setHistoryError(data?.error || "Unable to load interview history.");
        return;
      }
      setHistorySessions(Array.isArray(data?.sessions) ? data.sessions : []);
    } catch (error) {
      setHistoryError((error as Error).message);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    void loadHistory();
  }, []);

  useEffect(() => {
    if (historyLoading) return;

    const targetStats = {
      pinned: pinnedCount,
      archived: archivedCount,
    };

    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setAnimatedStats(targetStats);
      return;
    }

    const start = performance.now();
    const duration = 850;
    let frameId = 0;

    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setAnimatedStats({
        pinned: Math.round(targetStats.pinned * eased),
        archived: Math.round(targetStats.archived * eased),
      });

      if (progress < 1) {
        frameId = window.requestAnimationFrame(tick);
      }
    };

    frameId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frameId);
  }, [archivedCount, historyLoading, pinnedCount]);

  const updateSessionMeta = async (
    targetSessionId: string,
    payload: {
      title?: string | null;
      pinned?: boolean;
      archived?: boolean;
    }
  ) => {
    const res = await fetch(`/api/tech/session/${encodeURIComponent(targetSessionId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = (await res.json()) as { error?: string; detail?: string };
    if (!res.ok) {
      throw new Error(data?.detail || data?.error || "Unable to update this interview.");
    }
    await loadHistory();
  };

  const deleteSessionHistoryRequest = async (targetSessionId: string) => {
    const res = await fetch(`/api/tech/session/${encodeURIComponent(targetSessionId)}`, {
      method: "DELETE",
    });
    const data = (await res.json()) as { error?: string; detail?: string };
    if (!res.ok) {
      throw new Error(data?.detail || data?.error || "Unable to delete this interview.");
    }
  };

  const deleteSessionHistories = async (targetSessionIds: string[]) => {
    const uniqueSessionIds = Array.from(new Set(targetSessionIds.filter((sessionId) => sessionId.trim())));
    if (!uniqueSessionIds.length) return;

    const results = await Promise.allSettled(uniqueSessionIds.map((sessionId) => deleteSessionHistoryRequest(sessionId)));
    await loadHistory();

    const failedResult = results.find((result): result is PromiseRejectedResult => result.status === "rejected");
    if (failedResult) {
      throw failedResult.reason instanceof Error ? failedResult.reason : new Error("Unable to delete this interview.");
    }
  };

  return (
    <div
      className={`${styles.shell} ${theme === "dark" ? styles.themeDark : styles.themeLight}`}
      data-history-theme={theme}
    >
      <aside className={styles.sidebar}>
        <div className={styles.sidebarTop}>
          <Image className={styles.logoImage} src={logoImage} alt="SUBUL" priority />
        </div>

        <div className={styles.menuBlock}>
          <p className={styles.menuTitle}>{copy.mainMenu}</p>
          <nav className={styles.nav}>
            <span className={styles.navGroupTitle}>{copy.sidebarWorkspace}</span>
            <Link className={styles.navItem} href="/">
              <SidebarIcon type="interview" />
              {copy.interview}
            </Link>
            <Link className={styles.navItem} href="/dashboard">
              <SidebarIcon type="dashboard" />
              {copy.analytics}
            </Link>
            <span className={styles.navGroupTitle}>{copy.sidebarReports}</span>
            {latestSessionCompleted ? (
              <Link className={styles.navItem} href={reportHref}>
                <SidebarIcon type="dashboard" />
                {copy.hr}
              </Link>
            ) : (
              <button type="button" className={`${styles.navItem} ${styles.navButton} ${styles.navItemDisabled}`} disabled>
                <SidebarIcon type="dashboard" />
                {copy.hr}
              </button>
            )}
            {latestSessionCompleted ? (
              <Link className={styles.navItem} href={insightsHref}>
                <SidebarIcon type="hire" />
                {copy.insights}
              </Link>
            ) : (
              <button type="button" className={`${styles.navItem} ${styles.navButton} ${styles.navItemDisabled}`} disabled>
                <SidebarIcon type="hire" />
                {copy.insights}
              </button>
            )}
            <span className={styles.navGroupTitle}>{copy.sidebarTools}</span>
            <Link className={`${styles.navItem} ${styles.navItemActive}`} href="/history">
              <SidebarIcon type="memory" />
              {copy.historyNav}
            </Link>
            <Link className={styles.navItem} href="/help">
              <SidebarIcon type="help" />
              {copy.help}
            </Link>
          </nav>
        </div>
      </aside>

      <main className={styles.main}>
        <section className={styles.header}>
          <div>
            <h1>{copy.title}</h1>
            <p>{copy.subtitle}</p>
          </div>
          <div className={styles.headerActions}>
            <div className={styles.themeToggle}>
              <button
                type="button"
                className={`${styles.themeButton} ${theme === "light" ? styles.themeButtonActive : ""}`}
                onClick={() => setTheme("light")}
                aria-label={copy.lightMode}
                title={copy.lightMode}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="12" cy="12" r="4" />
                  <path d="M12 2.5v2.5" />
                  <path d="M12 19v2.5" />
                  <path d="M4.9 4.9 6.7 6.7" />
                  <path d="M17.3 17.3 19.1 19.1" />
                  <path d="M2.5 12H5" />
                  <path d="M19 12h2.5" />
                  <path d="M4.9 19.1 6.7 17.3" />
                  <path d="M17.3 6.7 19.1 4.9" />
                </svg>
              </button>
              <button
                type="button"
                className={`${styles.themeButton} ${theme === "dark" ? styles.themeButtonActive : ""}`}
                onClick={() => setTheme("dark")}
                aria-label={copy.darkMode}
                title={copy.darkMode}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4 7 7 0 0 0 20 14.5Z" />
                </svg>
              </button>
            </div>
            <div className={styles.languageToggle}>
              <button type="button" className={`${styles.languageButton} ${language === "fr" ? styles.languageButtonActive : ""}`} onClick={() => setLanguage("fr")}>
                FR
              </button>
              <button type="button" className={`${styles.languageButton} ${language === "en" ? styles.languageButtonActive : ""}`} onClick={() => setLanguage("en")}>
                EN
              </button>
            </div>
          </div>
        </section>

        <section className={styles.kpiGrid}>
          <article className={`${styles.kpiCard} ${styles.historyKpiCard}`}>
            <div className={styles.kpiTop}>
              <p>{copy.pinnedSessions}</p>
            </div>
            <strong className={`${styles.kpiValue} ${styles.historyKpiValue}`}>{animatedStats.pinned}</strong>
            <span className={`${styles.kpiBadge} ${styles.badgeSoft}`}>{copy.recruiterFavorites}</span>
          </article>

          <article className={`${styles.kpiCard} ${styles.historyKpiCard}`}>
            <div className={styles.kpiTop}>
              <p>{copy.archivedSessions}</p>
            </div>
            <strong className={`${styles.kpiValue} ${styles.historyKpiValue}`}>{animatedStats.archived}</strong>
            <span className={`${styles.kpiBadge} ${styles.badgeSoft}`}>{copy.archivedHint}</span>
          </article>
        </section>

        <section className={styles.historyHeroGrid}>
          <button
            type="button"
            className={`${styles.panelCard} ${styles.historyLeadCard} ${styles.historyLeadButton}`}
            onClick={() => (latestSession?.session_id ? router.push(`/?session=${encodeURIComponent(latestSession.session_id)}`) : router.push("/"))}
          >
            <div className={styles.panelHead}>
              <h3>{copy.recentActivity}</h3>
              <span className={styles.legendPill}>{copy.title}</span>
            </div>

            <div className={styles.historyLeadBody}>
              <div className={styles.historyLeadContent}>
                <strong>{latestSession?.title || copy.noRecentSession}</strong>
                <p>
                  {latestSession
                    ? `${latestSession.candidate_name || copy.noRecentCandidate} • ${latestSession.preview || copy.noRecentSessionDesc}`
                    : copy.noRecentSessionDesc}
                </p>
                {latestSession && latestSessionDateLabel ? (
                  <p className={styles.historyLeadDate}>{latestSessionDateLabel}</p>
                ) : null}
              </div>
            </div>
          </button>
        </section>

        <section className={styles.historyContentGrid}>
          <article className={`${styles.panelCard} ${styles.historySidebarPanel}`}>
            <SessionHistorySidebar
              activeSessionId=""
              sessions={historySessions}
              loading={historyLoading}
              error={historyError}
              open
              standalone
              searchValue={historySearch}
              onSearchChange={setHistorySearch}
              onCreateSession={() => router.push("/")}
              onOpenSession={(targetSessionId) => router.push(`/?session=${encodeURIComponent(targetSessionId)}`)}
              onRenameSession={(targetSessionId, currentTitle) => {
                setHistoryDialog({
                  mode: "rename",
                  sessionId: targetSessionId,
                  title: currentTitle,
                  value: currentTitle,
                });
              }}
              onTogglePinned={async (targetSessionId, nextPinned) => {
                try {
                  await updateSessionMeta(targetSessionId, { pinned: nextPinned });
                } catch (error) {
                  setHistoryError((error as Error).message);
                }
              }}
              onToggleArchived={async (targetSessionId, nextArchived) => {
                try {
                  await updateSessionMeta(targetSessionId, { archived: nextArchived });
                } catch (error) {
                  setHistoryError((error as Error).message);
                }
              }}
              onDeleteSessions={(targetSessions) => {
                if (!targetSessions.length) return;
                setHistoryDialog({
                  mode: "delete",
                  sessionIds: targetSessions.map((session) => session.session_id),
                  titles: targetSessions.map((session) => session.title || copy.noRecentSession),
                });
              }}
              onToggle={() => router.push("/")}
              copy={{
                hideHistory: copy.close,
                showHistory: copy.historyNav,
                brandSubtitle: copy.historyBrandSubtitle,
                closePanel: copy.close,
                newInterview: copy.newInterview,
                searchChats: copy.searchChats,
                score: copy.score,
                all: copy.all,
                archived: copy.archived,
                recents: copy.recents,
                showActive: copy.showActive,
                showArchived: copy.showArchived,
                loadingHistory: copy.loadingHistory,
                noMatchingConversation: copy.noMatchingConversation,
                noArchivedConversation: copy.noArchivedConversation,
                noSavedConversation: copy.noSavedConversation,
                openHistoryFallback: copy.openHistoryFallback,
                conversationActions: copy.conversationActions,
                rename: copy.rename,
                pin: copy.pin,
                unpin: copy.unpin,
                archive: copy.archive,
                unarchive: copy.unarchive,
                delete: copy.delete,
                select: copy.select,
                cancelSelection: copy.cancelSelection,
                deleteSelection: copy.deleteSelection,
                selectedLabel: copy.selectedLabel,
                selectConversation: copy.selectConversation,
                pinned: copy.pinned,
                today: copy.today,
                yesterday: copy.yesterday,
                previous7Days: copy.previous7Days,
                previous30Days: copy.previous30Days,
                older: copy.older,
              }}
            />
          </article>
        </section>
      </main>

      <HistoryActionDialog
        open={Boolean(historyDialog)}
        mode={historyDialog?.mode === "delete" ? "delete" : "rename"}
        value={historyDialog?.mode === "rename" ? historyDialog.value : ""}
        title={
          historyDialog?.mode === "delete"
            ? historyDialog.sessionIds.length > 1
              ? copy.deleteSelectedTitle
              : copy.deleteTitle
            : copy.renameTitle
        }
        description={
          historyDialog?.mode === "delete"
            ? historyDialog.sessionIds.length > 1
              ? `${historyDialog.sessionIds.length} ${copy.deleteSelectedDescription}`
              : `"${historyDialog.titles[0] || copy.noRecentSession}" ${copy.deleteDescription}`
            : copy.renameDescription
        }
        confirmLabel={historyDialog?.mode === "delete" ? copy.delete : copy.save}
        inputLabel={copy.newTitle}
        inputPlaceholder={copy.conversationName}
        cancelLabel={copy.cancel}
        busyLabel={copy.pleaseWait}
        closeLabel={copy.close}
        busy={historyDialogBusy}
        onValueChange={(value) => {
          setHistoryDialog((current) =>
            current?.mode === "rename"
              ? {
                  ...current,
                  value,
                }
              : current
          );
        }}
        onClose={() => {
          if (historyDialogBusy) return;
          setHistoryDialog(null);
        }}
        onConfirm={async () => {
          if (!historyDialog) return;
          setHistoryDialogBusy(true);
          try {
            if (historyDialog.mode === "rename") {
              await updateSessionMeta(historyDialog.sessionId, { title: historyDialog.value });
            } else {
              await deleteSessionHistories(historyDialog.sessionIds);
            }
            setHistoryDialog(null);
          } catch (error) {
            setHistoryError((error as Error).message);
          } finally {
            setHistoryDialogBusy(false);
          }
        }}
      />
    </div>
  );
}
