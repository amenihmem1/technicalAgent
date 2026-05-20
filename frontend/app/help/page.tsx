"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { SessionHistoryEntry, SessionHistoryResponse } from "../../lib/sessionHistory";
import styles from "../report/[sessionId]/report-dashboard.module.css";
import logoImage from "../../img/logoS-transparent.png";

type Language = "fr" | "en";
type Theme = "light" | "dark";
type SupportMessage = {
  role: "bot" | "user";
  text: string;
};

function HelpFeatureIcon({
  type,
}: {
  type:
    | "upload"
    | "start"
    | "report"
    | "history"
    | "spark"
    | "check"
    | "compass"
    | "shield"
    | "chart";
}) {
  if (type === "upload") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 16V5" />
        <path d="m7.5 9.5 4.5-4.5 4.5 4.5" />
        <path d="M5 19h14" />
      </svg>
    );
  }
  if (type === "start") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M8 6.5v11l8-5.5Z" />
      </svg>
    );
  }
  if (type === "report") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
        <path d="M14 3v5h5" />
        <path d="M9 13h6" />
        <path d="M9 17h4" />
      </svg>
    );
  }
  if (type === "history") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 12a8 8 0 1 0 2.3-5.7" />
        <path d="M4 4v4h4" />
        <path d="M12 8v4l2.5 1.5" />
      </svg>
    );
  }
  if (type === "check") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m5 12.5 4.2 4.2L19 7" />
      </svg>
    );
  }
  if (type === "compass") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z" />
        <path d="m14.8 9.2-2 5.6-5.6 2 2-5.6 5.6-2Z" />
      </svg>
    );
  }
  if (type === "shield") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3 6 5.5v5.7c0 4 2.6 7.7 6 8.8 3.4-1.1 6-4.8 6-8.8V5.5Z" />
        <path d="m9.5 12 1.7 1.7 3.3-3.3" />
      </svg>
    );
  }
  if (type === "chart") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 19V9" />
        <path d="M12 19V5" />
        <path d="M19 19v-7" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3 14.7 8.5 21 9.3l-4.5 4.3 1.1 6.1L12 16.8 6.4 19.7l1.1-6.1L3 9.3l6.3-.8Z" />
    </svg>
  );
}

function SidebarIcon({ type }: { type: "dashboard" | "hire" | "help" | "interview" | "memory" }) {
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

const helpTranslations = {
  fr: {
    mainMenu: "Menu principal",
    sidebarWorkspace: "Espace de travail",
    sidebarReports: "Rapports",
    sidebarTools: "Outils",
    analytics: "Analytique",
    interview: "Interview",
    hr: "Technique",
    insights: "Insights",
    history: "Historique",
    help: "Help",
    lightMode: "Clair",
    darkMode: "Sombre",
    title: "Centre d'aide",
    subtitle:
      "Retrouvez ici le parcours ideal pour lancer un entretien technique base sur les cours, ouvrir le rapport note et exploiter l'historique candidat.",
    quickStart: "Demarrage rapide",
    quickStartHint: "Les 4 etapes les plus utiles pour utiliser l'application.",
    quickStartLabel: "Etape",
    uploadCv: "Cours depuis Subul",
    uploadCvHint: "Le cours associe au candidat dans Subul est utilise pour guider les questions techniques.",
    launchInterview: "Lancer l'entretien",
    launchInterviewHint: "Envoyez un premier message ou ouvrez le micro pour parler, puis refermez-le pour lancer la transcription.",
    openReports: "Ouvrir les rapports",
    openReportsHint: "Le rapport technique devient accessible une fois la session finalisee.",
    reviewHistory: "Consulter l'historique",
    reviewHistoryHint: "Retrouvez les entretiens precedents, les scores et les conversations epinglees.",
    workflowTitle: "Workflow recommande",
    workflowSubtitle: "Un chemin simple pour ne rien oublier pendant une session.",
    workflowOneTitle: "1. Recuperer le cours Subul",
    workflowOneText: "L'agent utilise le cours associe au candidat dans Subul pour preparer les questions de l'entretien.",
    workflowTwoTitle: "2. Mener l'echange",
    workflowTwoText: "En mode micro, ouvrez le micro pour parler puis refermez-le quand vous avez termine afin de lancer la transcription.",
    workflowThreeTitle: "3. Finaliser la session",
    workflowThreeText: "Terminez l'entretien depuis le panneau de controle afin de generer le rapport complet.",
    workflowFourTitle: "4. Explorer les resultats",
    workflowFourText: "Ouvrez Technique et Historique pour relire les questions, les reponses et les notes obtenues.",
    workflowCardTitle: "Parcours recommande",
    navigationTitle: "Que contient chaque page ?",
    navigationSubtitle: "Resume rapide des sections disponibles dans le menu.",
    navInterviewTitle: "Interview",
    navInterviewText: "Page de conduite d'entretien avec contexte candidat, transcription et micro.",
    navHrTitle: "Technique",
    navHrText: "Rapport technique avec score global, notes par question et recapitulatif d'examen.",
    navHistoryTitle: "Historique",
    navHistoryText: "Liste des sessions, recherche, archivage, epinglage et reprise rapide.",
    tipsTitle: "Bonnes pratiques",
    tipsSubtitle: "Quelques reperes pour des sessions plus fluides.",
    unlockTitle: "Ce qui debloque les rapports",
    unlockSubtitle: "Le rapport technique s'active lorsque le cycle de session est complet.",
    unlockOneTitle: "Cours Subul detecte",
    unlockOneText: "Le cours associe au candidat est disponible pour guider les questions de l'entretien.",
    unlockTwoTitle: "Entretien mene",
    unlockTwoText: "Les questions et les reponses du candidat alimentent la notation.",
    unlockThreeTitle: "Session finalisee",
    unlockThreeText: "Le rapport complet devient disponible avec le score global et les notes par question.",
    tipOne: "Verifier que le candidat est bien associe au bon cours dans Subul garantit des questions liees au bon support.",
    tipTwo: "Finaliser proprement la session est necessaire pour debloquer le rapport technique.",
    tipThree: "L'historique est utile pour retrouver les sessions actives, les rapports completes et les favoris.",
    tipFour: "En mode micro, cliquez une premiere fois pour enregistrer votre reponse puis une seconde fois pour arreter et envoyer la transcription.",
    supportTitle: "Support rapide",
    supportSubtitle: "Posez une question ou utilisez les raccourcis pour resoudre les problemes frequents.",
    supportWelcome: "Bonjour, je peux vous aider avec le cours, l'entretien, les questions, le rapport technique et la notation.",
    supportPlaceholder: "Exemple: comment le cours est-il utilise ?",
    supportSend: "Envoyer",
    supportFallback: "Je n'ai pas trouve une reponse exacte. Verifiez que le candidat est associe au bon cours dans Subul, lancez l'entretien, puis finalisez la session pour ouvrir le rapport technique.",
    faqCourseQuestion: "Comment le cours est-il utilise ?",
    faqCourseAnswer: "Le cours vient de Subul selon le parcours ou le cours associe au candidat. L'agent pose ensuite des questions basees sur ce contenu.",
    faqBackendQuestion: "Comment demarrer l'entretien ?",
    faqBackendAnswer: "Ouvrez la page Interview, preparez le cours, puis envoyez le premier message ou utilisez le micro pour commencer.",
    faqFrontendQuestion: "Comment terminer l'entretien ?",
    faqFrontendAnswer: "Quand les questions sont terminees, finalisez la session depuis l'interface. Le rapport technique sera alors disponible.",
    faqQuestionQuestion: "Pourquoi les questions ne suivent pas le cours ?",
    faqQuestionAnswer: "Verifiez que le candidat est associe au bon cours dans Subul et que le contenu du cours est lisible par l'application.",
    faqReportQuestion: "Pourquoi le rapport n'apparait pas ?",
    faqReportAnswer: "Le rapport s'affiche apres finalisation de la session. Terminez l'entretien, puis ouvrez la page Technique depuis le menu ou l'historique.",
    faqScoreQuestion: "Comment fonctionne la note ?",
    faqScoreAnswer: "Chaque reponse est notee sur 5 comme dans un examen. Le score global sur 100 est calcule a partir des notes obtenues.",
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
    history: "History",
    help: "Help",
    lightMode: "Light",
    darkMode: "Dark",
    title: "Help Center",
    subtitle:
      "Find the ideal flow to launch a course-based technical interview, open the graded report, and make the most of candidate history.",
    quickStart: "Quick start",
    quickStartHint: "The 4 most useful steps to use the application.",
    quickStartLabel: "Step",
    uploadCv: "Course from Subul",
    uploadCvHint: "The course associated with the candidate in Subul is used to guide technical questions.",
    launchInterview: "Start the interview",
    launchInterviewHint: "Send a first message or open the microphone to speak, then close it to trigger transcription.",
    openReports: "Open reports",
    openReportsHint: "The technical report becomes available once the session is finalized.",
    reviewHistory: "Review history",
    reviewHistoryHint: "Find previous interviews, scores, and pinned conversations.",
    workflowTitle: "Recommended workflow",
    workflowSubtitle: "A simple path to avoid missing anything during a session.",
    workflowOneTitle: "1. Retrieve the Subul course",
    workflowOneText: "The agent uses the course associated with the candidate in Subul to prepare interview questions.",
    workflowTwoTitle: "2. Run the exchange",
    workflowTwoText: "In microphone mode, open the mic to speak, then close it when you are done to trigger transcription.",
    workflowThreeTitle: "3. Finalize the session",
    workflowThreeText: "End the interview from the control panel to generate the complete report.",
    workflowFourTitle: "4. Explore the results",
    workflowFourText: "Open Technical and History to revisit questions, answers, and grades.",
    workflowCardTitle: "Recommended journey",
    navigationTitle: "What does each page contain?",
    navigationSubtitle: "Quick summary of the sections available in the menu.",
    navInterviewTitle: "Interview",
    navInterviewText: "Interview workspace with candidate context, transcript, and microphone.",
    navHrTitle: "Technical",
    navHrText: "Technical report with overall score, per-question grades, and exam summary.",
    navHistoryTitle: "History",
    navHistoryText: "Session list, search, archive, pinning, and quick resume.",
    tipsTitle: "Best practices",
    tipsSubtitle: "A few simple cues for smoother sessions.",
    unlockTitle: "What unlocks reports",
    unlockSubtitle: "The technical report activates once the session cycle is complete.",
    unlockOneTitle: "Subul course detected",
    unlockOneText: "The course associated with the candidate is available to guide interview questions.",
    unlockTwoTitle: "Interview completed",
    unlockTwoText: "The candidate's questions and answers feed the grading.",
    unlockThreeTitle: "Session finalized",
    unlockThreeText: "The full report becomes available with the overall score and per-question grades.",
    tipOne: "Checking that the candidate is linked to the right course in Subul ensures questions use the right material.",
    tipTwo: "Properly finalizing the session is required to unlock the technical report.",
    tipThree: "History is useful for finding active sessions, completed reports, and favorites.",
    tipFour: "In microphone mode, click once to record your answer, then click again to stop and send the transcription.",
    supportTitle: "Quick support",
    supportSubtitle: "Ask a question or use shortcuts to solve common issues.",
    supportWelcome: "Hello, I can help with the course, interview, questions, technical report, and grading.",
    supportPlaceholder: "Example: how is the course used?",
    supportSend: "Send",
    supportFallback: "I could not find an exact answer. Check that the candidate is linked to the right course in Subul, run the interview, then finalize the session to open the technical report.",
    faqCourseQuestion: "How is the course used?",
    faqCourseAnswer: "The course comes from Subul based on the candidate's path or associated course. The agent then asks questions grounded in that content.",
    faqBackendQuestion: "How do I start the interview?",
    faqBackendAnswer: "Open the Interview page, prepare the course, then send the first message or use the microphone to begin.",
    faqFrontendQuestion: "How do I finish the interview?",
    faqFrontendAnswer: "When the questions are complete, finalize the session from the interface. The technical report will then become available.",
    faqQuestionQuestion: "Why are questions not following the course?",
    faqQuestionAnswer: "Check that the candidate is linked to the right course in Subul and that the course content is readable by the application.",
    faqReportQuestion: "Why is the report missing?",
    faqReportAnswer: "The report appears after session finalization. End the interview, then open Technical from the menu or history.",
    faqScoreQuestion: "How does grading work?",
    faqScoreAnswer: "Each answer is graded out of 5 like an exam. The overall score out of 100 is calculated from the obtained grades.",
  },
} as const;

export default function HelpPage() {
  const [language, setLanguage] = useState<Language>("fr");
  const [theme, setTheme] = useState<Theme>("light");
  const [historySessions, setHistorySessions] = useState<SessionHistoryEntry[]>([]);
  const [supportMessages, setSupportMessages] = useState<SupportMessage[]>([]);
  const [supportInput, setSupportInput] = useState("");
  const [supportOpen, setSupportOpen] = useState(true);

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

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const res = await fetch("/api/tech/sessions?limit=80", { method: "GET", cache: "no-store" });
        const data = (await res.json()) as SessionHistoryResponse & { error?: string };
        if (!res.ok) {
          return;
        }
        setHistorySessions(Array.isArray(data?.sessions) ? data.sessions : []);
      } catch {
        // Keep the help page usable even if history is temporarily unavailable.
      }
    };

    void loadHistory();
  }, []);

  const copy = helpTranslations[language];
  const latestSessionId = historySessions[0]?.session_id || "";
  const latestSessionCompleted = historySessions[0]?.status === "completed";
  const reportHref = latestSessionId ? `/report/${encodeURIComponent(latestSessionId)}?view=report` : "/";
  const insightsHref = latestSessionId ? `/report/${encodeURIComponent(latestSessionId)}?view=insights` : "/";

  const quickStartCards = [
    { title: copy.uploadCv, helper: copy.uploadCvHint, icon: "upload" as const },
    { title: copy.launchInterview, helper: copy.launchInterviewHint, icon: "start" as const },
    { title: copy.openReports, helper: copy.openReportsHint, icon: "report" as const },
    { title: copy.reviewHistory, helper: copy.reviewHistoryHint, icon: "history" as const },
  ];

  const workflowItems = [
    { title: copy.workflowOneTitle, text: copy.workflowOneText },
    { title: copy.workflowTwoTitle, text: copy.workflowTwoText },
    { title: copy.workflowThreeTitle, text: copy.workflowThreeText },
    { title: copy.workflowFourTitle, text: copy.workflowFourText },
  ];

  const navigationItems = [
    { title: copy.navInterviewTitle, text: copy.navInterviewText, icon: "compass" as const },
    { title: copy.navHrTitle, text: copy.navHrText, icon: "chart" as const },
    { title: copy.navHistoryTitle, text: copy.navHistoryText, icon: "history" as const },
  ];

  const tips = [copy.tipOne, copy.tipTwo, copy.tipThree, copy.tipFour];
  const unlockItems = [
    { title: copy.unlockOneTitle, text: copy.unlockOneText },
    { title: copy.unlockTwoTitle, text: copy.unlockTwoText },
    { title: copy.unlockThreeTitle, text: copy.unlockThreeText },
  ];
  const supportFaq = [
    { question: copy.faqCourseQuestion, answer: copy.faqCourseAnswer, keywords: ["cours", "course", "subul", "parcours", "associe", "associated"] },
    { question: copy.faqBackendQuestion, answer: copy.faqBackendAnswer, keywords: ["demarrer", "start", "commencer", "interview", "entretien"] },
    { question: copy.faqFrontendQuestion, answer: copy.faqFrontendAnswer, keywords: ["terminer", "finish", "finaliser", "finalize"] },
    { question: copy.faqQuestionQuestion, answer: copy.faqQuestionAnswer, keywords: ["question", "cours", "course", "correspond"] },
    { question: copy.faqReportQuestion, answer: copy.faqReportAnswer, keywords: ["rapport", "report", "technique", "final"] },
    { question: copy.faqScoreQuestion, answer: copy.faqScoreAnswer, keywords: ["note", "score", "grade", "evaluation"] },
  ];
  const visibleSupportMessages = [{ role: "bot" as const, text: copy.supportWelcome }, ...supportMessages];

  const answerSupportQuestion = (question: string, directAnswer?: string) => {
    const cleanedQuestion = question.trim();
    if (!cleanedQuestion) return;

    const normalizedQuestion = cleanedQuestion.toLowerCase();
    const matchedFaq =
      directAnswer ||
      supportFaq.find((item) => item.keywords.some((keyword) => normalizedQuestion.includes(keyword)))?.answer ||
      copy.supportFallback;

    setSupportMessages((current) => [
      ...current,
      { role: "user", text: cleanedQuestion },
      { role: "bot", text: matchedFaq },
    ]);
    setSupportInput("");
  };

  return (
    <div className={`${styles.shell} ${theme === "dark" ? styles.themeDark : styles.themeLight}`}>
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
            <Link className={styles.navItem} href="/history">
              <SidebarIcon type="memory" />
              {copy.history}
            </Link>
            <Link className={`${styles.navItem} ${styles.navItemActive}`} href="/help">
              <SidebarIcon type="help" />
              {copy.help}
            </Link>
          </nav>
        </div>
      </aside>

      <main className={`${styles.main} ${styles.helpMain}`}>
        <section className={styles.helpHero}>
          <div className={styles.helpHeroMain}>
            <div className={styles.helpHeroCopy}>
              <h1>{copy.title}</h1>
              <p>{copy.subtitle}</p>
            </div>
          </div>

          <div className={styles.helpHeroControls}>
            <div className={`${styles.themeToggle} ${styles.compactToggle}`}>
              <button
                type="button"
                className={`${styles.themeButton} ${styles.compactToggleButton} ${theme === "light" ? styles.themeButtonActive : ""}`}
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
                className={`${styles.themeButton} ${styles.compactToggleButton} ${theme === "dark" ? styles.themeButtonActive : ""}`}
                onClick={() => setTheme("dark")}
                aria-label={copy.darkMode}
                title={copy.darkMode}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4 7 7 0 0 0 20 14.5Z" />
                </svg>
              </button>
            </div>
            <div className={`${styles.languageToggle} ${styles.compactToggle}`}>
              <button
                type="button"
                className={`${styles.languageButton} ${styles.compactToggleButton} ${language === "fr" ? styles.languageButtonActive : ""}`}
                onClick={() => setLanguage("fr")}
              >
                FR
              </button>
              <button
                type="button"
                className={`${styles.languageButton} ${styles.compactToggleButton} ${language === "en" ? styles.languageButtonActive : ""}`}
                onClick={() => setLanguage("en")}
              >
                EN
              </button>
            </div>
          </div>
        </section>

        <section className={styles.helpFeatureGrid}>
          {quickStartCards.map((item, index) => (
            <article key={item.title} className={styles.helpFeatureCard}>
              <div className={styles.helpFeatureTop}>
                <span className={styles.helpFeatureIcon}>
                  <HelpFeatureIcon type={item.icon} />
                </span>
                <span className={styles.helpFeatureStep}>
                  {copy.quickStartLabel} {index + 1}
                </span>
              </div>
              <strong className={styles.helpFeatureTitle}>{item.title}</strong>
              <p className={styles.helpFeatureText}>{item.helper}</p>
              <span className={styles.helpFeatureGlow} aria-hidden="true" />
            </article>
          ))}
        </section>

        <section className={`${styles.supportChatSection} ${supportOpen ? styles.supportChatSectionOpen : styles.supportChatSectionClosed}`}>
          <article className={styles.supportChatCard}>
            <div className={styles.helpSectionHeader}>
              <div className={styles.supportHeaderRow}>
                <div>
                  <h2>{copy.supportTitle}</h2>
                  <p>{copy.supportSubtitle}</p>
                </div>
                <button
                  type="button"
                  className={styles.supportToggleButton}
                  onClick={() => setSupportOpen((current) => !current)}
                  aria-expanded={supportOpen}
                  aria-label={supportOpen ? "Masquer le support" : "Ouvrir le support"}
                  title={supportOpen ? "Masquer le support" : "Ouvrir le support"}
                >
                  {supportOpen ? (
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M6 12h12" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M12 6v12" />
                      <path d="M6 12h12" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {supportOpen ? (
            <div className={styles.supportChatShell}>
              <div className={styles.supportQuickActions}>
                {supportFaq.map((item) => (
                  <button
                    key={item.question}
                    type="button"
                    className={styles.supportQuickButton}
                    onClick={() => answerSupportQuestion(item.question, item.answer)}
                  >
                    {item.question}
                  </button>
                ))}
              </div>

              <div className={styles.supportMessages} aria-live="polite">
                {visibleSupportMessages.map((message, index) => (
                  <div
                    key={`${message.role}-${index}-${message.text}`}
                    className={`${styles.supportMessageRow} ${message.role === "user" ? styles.supportMessageRowUser : ""}`}
                  >
                    {message.role === "bot" ? (
                      <span className={styles.supportAvatar} aria-hidden="true">
                        <HelpFeatureIcon type="spark" />
                      </span>
                    ) : null}
                    <div className={`${styles.supportBubble} ${message.role === "user" ? styles.supportBubbleUser : styles.supportBubbleBot}`}>
                      {message.text}
                    </div>
                  </div>
                ))}
              </div>

              <form
                className={styles.supportForm}
                onSubmit={(event) => {
                  event.preventDefault();
                  answerSupportQuestion(supportInput);
                }}
              >
                <input
                  value={supportInput}
                  onChange={(event) => setSupportInput(event.target.value)}
                  placeholder={copy.supportPlaceholder}
                  className={styles.supportInput}
                />
                <button type="submit" className={styles.supportSendButton}>
                  {copy.supportSend}
                </button>
              </form>
            </div>
            ) : null}
          </article>
        </section>

        <section className={styles.helpGrid}>
          <article className={styles.helpSection}>
            <div className={styles.helpSectionHeader}>
              <h2>{copy.workflowCardTitle}</h2>
              <p>{copy.workflowSubtitle}</p>
            </div>
            <div className={styles.helpTimeline}>
              {workflowItems.map((item, index) => (
                <div key={item.title} className={styles.helpTimelineItem}>
                  <span className={styles.helpTimelineIndex}>0{index + 1}</span>
                  <div className={styles.helpTimelineBody}>
                    <strong>{item.title}</strong>
                    <p>{item.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className={styles.helpSection}>
            <div className={styles.helpSectionHeader}>
              <h2>{copy.unlockTitle}</h2>
              <p>{copy.unlockSubtitle}</p>
            </div>
            <div className={styles.helpList}>
              {unlockItems.map((item) => (
                <div key={item.title} className={styles.helpListItem}>
                  <div className={styles.helpInlineTitle}>
                    <span className={styles.helpInlineIcon}>
                      <HelpFeatureIcon type="check" />
                    </span>
                    <strong>{item.title}</strong>
                  </div>
                  <p>{item.text}</p>
                </div>
              ))}
            </div>
          </article>
        </section>

        <section className={styles.helpGrid}>
          <article className={styles.helpSection}>
            <div className={styles.helpSectionHeader}>
              <h2>{copy.navigationTitle}</h2>
              <p>{copy.navigationSubtitle}</p>
            </div>
            <div className={styles.helpNavGrid}>
              {navigationItems.map((item) => (
                <div key={item.title} className={styles.helpNavCard}>
                  <span className={styles.helpNavIcon}>
                    <HelpFeatureIcon type={item.icon} />
                  </span>
                  <strong>{item.title}</strong>
                  <p>{item.text}</p>
                </div>
              ))}
            </div>
          </article>

          <article className={styles.helpSection}>
            <div className={styles.helpSectionHeader}>
              <h2>{copy.tipsTitle}</h2>
              <p>{copy.tipsSubtitle}</p>
            </div>
            <div className={styles.helpList}>
              {tips.map((item) => (
                <div key={item} className={styles.helpListItem}>
                  <div className={styles.helpInlineTitle}>
                    <span className={styles.helpInlineIcon}>
                      <HelpFeatureIcon type="spark" />
                    </span>
                    <strong>{copy.tipsTitle}</strong>
                  </div>
                  <p>{item}</p>
                </div>
              ))}
            </div>
          </article>
        </section>

      </main>
    </div>
  );
}


