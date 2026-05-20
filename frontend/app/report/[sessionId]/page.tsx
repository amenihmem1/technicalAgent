"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { CSSProperties, useEffect, useMemo, useState } from "react";
import { CandidateInsightsPopup, type CandidateInsightsPayload } from "../../components/CandidateInsightsPopup";
import styles from "./report-dashboard.module.css";
import logoImage from "../../../img/logoS-transparent.png";

type CompetencyScores = {
  question_score?: number;
};

type InsightContext = {
  metrics?: Record<string, number | string | boolean | Record<string, unknown>>;
  signals?: string[];
  heuristic_flags?: string[];
  confidence_note?: string;
};

type StressFactor = {
  key?: string;
  label?: string;
  value?: number;
  detail?: string;
};

type StressContext = {
  score?: number;
  band?: string;
  summary?: string;
  factors?: StressFactor[];
  confidence_note?: string;
};

type InsightsAdvice = {
  thank_you?: string;
  summary?: string[];
  strengths?: string[];
  improvements?: string[];
  next_steps?: string[];
  closing?: string;
};

type SessionReportPayload = {
  session_id?: string;
  updated_at?: string;
  finalized_at?: string;
  interview_status?: string;
  proctoring_events?: Array<{
    time?: string;
    reason?: string;
    message?: string;
    count?: number;
  }>;
  proctoring_alerts_count?: number;
  final_report?: {
    score_total?: number;
    competencies?: CompetencyScores;
    strengths?: string[];
    improvement_points?: string[];
    dimension_actions?: Record<string, string>;
    risks?: string[];
    advice?: string[];
    summary?: string;
    audio_signals?: string[];
    audio_flags?: string[];
    audio_metrics?: Record<string, number | string | boolean>;
    visual_signals?: string[];
    visual_flags?: string[];
    visual_metrics?: Record<string, number | string | boolean | Record<string, unknown>>;
    confidence_note?: string;
    audio_confidence_note?: string;
    proctoring_events?: Array<{
      time?: string;
      reason?: string;
      message?: string;
      count?: number;
    }>;
    proctoring_alerts_count?: number;
  } | null;
  cv_profile?: {
    candidate_name?: string;
    name?: string;
    headline?: string;
    email?: string;
    phone?: string;
    linkedin?: string;
    github?: string;
    top_skills?: string[];
    source_filename?: string;
  } | null;
  turns?: Array<{
    time?: string;
    phase?: string;
    candidate_text?: string;
    say?: string;
    score_partial?: {
      question_score?: number;
    };
  }>;
  visual_context?: InsightContext | null;
  audio_context?: InsightContext | null;
  stress_context?: StressContext | null;
  insights_advice?: InsightsAdvice | null;
};

type KpiCard = {
  label: string;
  value: string;
  tone: "good" | "soft" | "alert";
  helper: string;
};

type Language = "fr" | "en";
type Theme = "light" | "dark";

const LOCAL_ONLY_HOSTNAMES = new Set(["localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"]);
const QR_SHARE_BASE_URL = normalizeBaseUrl(
  process.env.NEXT_PUBLIC_REPORT_SHARE_BASE_URL || process.env.NEXT_PUBLIC_APP_URL || process.env.NEXT_PUBLIC_SITE_URL,
);

function normalizeBaseUrl(value?: string | null) {
  return String(value || "")
    .trim()
    .replace(/\/+$/, "");
}

function isLocalOnlyOrigin(value: string) {
  if (!value) return false;

  try {
    return LOCAL_ONLY_HOSTNAMES.has(new URL(value).hostname.toLowerCase());
  } catch {
    return false;
  }
}

const translations = {
  fr: {
    unavailableReport: "Rapport indisponible",
    backToInterview: "Retour a l'entretien",
    resultsPendingTitle: "Resultats indisponibles pour le moment",
    resultsPendingMessage: "Le candidat doit terminer son entretien avant d'acceder au rapport technique et aux Insights.",
    mainMenu: "Menu principal",
    sidebarWorkspace: "Espace de travail",
    sidebarReports: "Rapports",
    sidebarTools: "Outils",
    analytics: "Analytique",
    reportNav: "Technique",
    interviewNav: "Interview",
    subulMemoryNav: "Memoire Subul",
    historyNav: "Historique",
    detailedReport: "Rapport detaille",
    help: "Help",
    detailedAnalysis: "Analyse detaillee",
    reportTitle: "Rapport technique",
    visualVocalInsights: "Insights Visuels & Vocaux",
    reportSubtitle: "Vue technique consolidee du profil et des competences pour",
    insightsSubtitle: "Vue dediee aux signaux visuels, vocaux et au stress pour",
    sharePdf: "Partager le PDF",
    sharing: "Partage...",
    downloadPdf: "Telecharger le PDF",
    downloadInsightsPdf: "Telecharger le PDF Insights",
    qrPdf: "QR PDF",
    qrInsightsPdf: "QR PDF Insights",
    showQrCode: "Afficher le QR",
    scanQrToOpen: "Scannez pour ouvrir le PDF",
    openPdf: "Ouvrir le PDF",
    qrModalTitle: "Scanner le QR code",
    closeModal: "Fermer",
    qrLocalHint: "Le lien QR doit etre accessible depuis votre telephone. Si le scan ne s'ouvre pas, utilisez le bouton Ouvrir le PDF.",
    preparing: "Preparation...",
    candidateProfile: "Profil candidat",
    reportScore: "Score technique",
    skillsDistribution: "Progression par question",
    topCvSkills: "Notes par question",
    reportSummary: "Recapitulatif technique",
    reportSummarySubtitle: "Lecture des reponses notees pendant l'entretien technique.",
    status: "Statut",
    dimension: "Question",
    score: "Note",
    keySignal: "Reponse candidat",
    recommendedAction: "Question posee",
    progression: "Progression",
    insights: "Insights",
    visualAndVocal: "Visuel & Vocal",
    insightsSubtitleBlock: "Cette partie regroupe uniquement les observations visuelles, vocales et les indicateurs derives.",
    automatedInsights: "Insights automatises",
    visualReading: "Lecture visuelle",
    vocalSignal: "Signal vocal",
    stressReading: "Lecture du stress",
    visualSignals: "Signaux visuels",
    vocalSignals: "Signaux vocaux",
    vocalDashboard: "Tableau de bord vocal",
    vocalConfidence: "Confiance moyenne : les observations vocales reposent sur la capture navigateur et des metriques derivees de la transcription.",
    vocalReading: "Lecture vocale",
    vocalReadingFallback: "Les pauses et silences etaient perceptibles sur plusieurs reponses.",
    pauses: "Pauses",
    hesitations: "Hesitations",
    marked: "marquees",
    pitchAverage: "Pitch moyen",
    steadySignal: "steady",
    hesitationNoteFallback: "Les marqueurs d'hesitation verbale sont restes occasionnels a moderes.",
    average: "moyen",
    finalizedOn: "Session finalisee le",
    total: "Total",
    email: "Email",
    phone: "Telephone",
    linkedin: "LinkedIn",
    github: "GitHub",
    happy: "Happy",
    angry: "Angry",
    sad: "Sad",
    neutral: "Neutral",
    surprise: "Surprise",
    loadingDashboard: "Chargement du rapport technique...",
    candidateFallback: "Candidat",
    profileInReview: "Profil en evaluation",
    unableToLoadReport: "Impossible de charger le rapport technique.",
    shareNativeUnavailable: "Le partage natif du PDF n'est pas disponible dans ce navigateur.",
    pdfUnavailable: "PDF indisponible.",
    scoreGlobalReport: "Score global technique",
    solidProfile: "Profil solide",
    profileToConsolidate: "Profil a consolider",
    averageAnswerScore: "Note moyenne",
    evaluatedQuestions: "Questions evaluees",
    courseExam: "Examen du cours",
    noAnswerCaptured: "Aucune reponse capturee",
    noQuestionCaptured: "Question indisponible",
    answersGradedLikeExam: "Reponses notees comme un examen",
    basedOnCourseQuestions: "Questions basees sur le cours",
    architecture: "Architecture",
    optimization: "Optimisation",
    debugging: "Debugging",
    llmUnderstanding: "IA / LLM",
    clearExpression: "Conception claire",
    goodCollaboration: "Optimisation maitrisee",
    analyticalAbility: "Diagnostic technique",
    engagementToStrengthen: "Concepts IA a approfondir",
    technicalReview: "Lecture technique",
    coherentProfile: "Le profil presente un niveau global coherent et exploitable pour la suite du processus technique.",
    attention: "Attention",
    noMajorAlert: "Aucun signal d'alerte majeur n'a ete detecte, mais la lecture doit rester prudente.",
    recommendation: "Recommandation",
    followupRecommendation: "Prevoir un echange complementaire pour approfondir les points techniques du cours.",
    customEmotionModel: "Modele emotionnel IA",
    visualEmotionProviders: "Moteur emotionnel visuel",
    speechRate: "Debit",
    volumeLabel: "Volume",
    usefulSilence: "Silence utile",
    variation: "Variation",
    faceDetected: "Face detectee",
    centering: "Centrage",
    stablePosture: "Posture stable",
    visualEngagement: "Engagement visuel",
    factor: "Facteur",
    extractedCvPriority: "Priorite extraite du CV",
    stableReading: "Lecture stable sur cette dimension.",
    followupBehaviorQuestion: "Approfondir avec une question comportementale complementaire.",
    visualTitle: "Visuels",
    vocalTitle: "Vocaux",
    noVisualSignal: "Aucun signal visuel notable n'a ete capture.",
    noVocalSignal: "Aucun signal vocal notable n'a ete capture.",
    visualSignalsConsolidated: "signaux consolides",
    vocalIndicators: "indicateurs vocaux",
    indicativeReading: "Lecture indicative",
    observedStress: "Stress observe",
    keyInsights: "Insights cle",
    priorityPoints: "Points prioritaires a retenir",
    insightsLead: "Cette lecture combine les signaux visuels, vocaux et de stress dans un cadre indicatif.",
    proctoringTitle: "Alertes surveillance",
    proctoringSubtitle: "Evenements detectes pendant l'entretien: onglet, fenetre, DevTools ou configuration d'ecrans.",
    proctoringCount: "alertes enregistrees",
    noProctoringAlerts: "Aucune alerte de surveillance enregistree.",
    lightMode: "Clair",
    darkMode: "Sombre",
  },
  en: {
    unavailableReport: "Report unavailable",
    backToInterview: "Back to interview",
    resultsPendingTitle: "Results are not available yet",
    resultsPendingMessage: "The candidate must finish the interview before accessing the technical report and Insights views.",
    mainMenu: "Main menu",
    sidebarWorkspace: "Workspace",
    sidebarReports: "Reports",
    sidebarTools: "Tools",
    analytics: "Analytics",
    reportNav: "Technical",
    interviewNav: "Interview",
    subulMemoryNav: "Subul Memory",
    historyNav: "History",
    detailedReport: "Detailed report",
    help: "Help",
    detailedAnalysis: "Detailed analysis",
    reportTitle: "Technical Report",
    visualVocalInsights: "Visual & Vocal Insights",
    reportSubtitle: "Consolidated technical view of profile and competencies for",
    insightsSubtitle: "Dedicated view of visual, vocal, and stress signals for",
    sharePdf: "Share PDF",
    sharing: "Sharing...",
    downloadPdf: "Download PDF",
    downloadInsightsPdf: "Download Insights PDF",
    qrPdf: "PDF QR",
    qrInsightsPdf: "Insights PDF QR",
    showQrCode: "Show QR code",
    scanQrToOpen: "Scan to open the PDF",
    openPdf: "Open PDF",
    qrModalTitle: "Scan the QR code",
    closeModal: "Close",
    qrLocalHint: "The QR link must be reachable from your phone. If scanning does not open it, use the Open PDF button.",
    preparing: "Preparing...",
    candidateProfile: "Candidate profile",
    reportScore: "Technical Score",
    skillsDistribution: "Question progress",
    topCvSkills: "Grades by question",
    reportSummary: "Technical Summary",
    reportSummarySubtitle: "Review of answers graded during the technical interview.",
    status: "Status",
    dimension: "Question",
    score: "Grade",
    keySignal: "Candidate answer",
    recommendedAction: "Question asked",
    progression: "Progress",
    insights: "Insights",
    visualAndVocal: "Visual & Vocal",
    insightsSubtitleBlock: "This section groups visual, vocal, and derived indicators only.",
    automatedInsights: "Automated insights",
    visualReading: "Visual reading",
    vocalSignal: "Vocal signal",
    stressReading: "Stress reading",
    visualSignals: "Visual signals",
    vocalSignals: "Vocal signals",
    vocalDashboard: "Vocal dashboard",
    vocalConfidence: "Average confidence: vocal observations rely on browser capture and metrics derived from transcription.",
    vocalReading: "Vocal reading",
    vocalReadingFallback: "Pauses and silences were noticeable across several answers.",
    pauses: "Pauses",
    hesitations: "Hesitations",
    marked: "marked",
    pitchAverage: "Average pitch",
    steadySignal: "steady",
    hesitationNoteFallback: "Verbal hesitation markers remained occasional to moderate.",
    average: "avg",
    finalizedOn: "Session finalized on",
    total: "Total",
    email: "Email",
    phone: "Phone",
    linkedin: "LinkedIn",
    github: "GitHub",
    happy: "Happy",
    angry: "Angry",
    sad: "Sad",
    neutral: "Neutral",
    surprise: "Surprise",
    loadingDashboard: "Loading technical report...",
    candidateFallback: "Candidate",
    profileInReview: "Profile under review",
    unableToLoadReport: "Unable to load the technical report.",
    shareNativeUnavailable: "Native PDF sharing is not available in this browser.",
    pdfUnavailable: "PDF unavailable.",
    scoreGlobalReport: "Overall technical score",
    solidProfile: "Strong profile",
    profileToConsolidate: "Profile to strengthen",
    averageAnswerScore: "Average grade",
    evaluatedQuestions: "Questions graded",
    courseExam: "Course exam",
    noAnswerCaptured: "No answer captured",
    noQuestionCaptured: "Question unavailable",
    answersGradedLikeExam: "Answers graded like an exam",
    basedOnCourseQuestions: "Questions based on the course",
    architecture: "Architecture",
    optimization: "Optimization",
    debugging: "Debugging",
    llmUnderstanding: "AI / LLM",
    clearExpression: "Clear design reasoning",
    goodCollaboration: "Optimization control",
    analyticalAbility: "Technical diagnosis",
    engagementToStrengthen: "AI concepts to deepen",
    technicalReview: "Technical reading",
    coherentProfile: "The profile shows a coherent overall level and is usable for the next technical steps.",
    attention: "Attention",
    noMajorAlert: "No major alert signal was detected, but the reading should remain cautious.",
    recommendation: "Recommendation",
    followupRecommendation: "Plan a follow-up exchange to explore the course's technical points in more depth.",
    customEmotionModel: "Custom emotion model",
    visualEmotionProviders: "Visual emotion engine",
    speechRate: "Speech rate",
    volumeLabel: "Volume",
    usefulSilence: "Useful silence",
    variation: "Variation",
    faceDetected: "Face detected",
    centering: "Centering",
    stablePosture: "Stable posture",
    visualEngagement: "Visual engagement",
    factor: "Factor",
    extractedCvPriority: "Priority extracted from CV",
    stableReading: "Stable reading on this dimension.",
    followupBehaviorQuestion: "Follow up with an additional behavioral question.",
    visualTitle: "Visual",
    vocalTitle: "Vocal",
    noVisualSignal: "No notable visual signal was captured.",
    noVocalSignal: "No notable vocal signal was captured.",
    visualSignalsConsolidated: "consolidated signals",
    vocalIndicators: "vocal indicators",
    indicativeReading: "Indicative reading",
    observedStress: "Observed stress",
    keyInsights: "Key insights",
    priorityPoints: "Priority points to retain",
    insightsLead: "This reading combines visual, vocal, and stress signals within an indicative framework.",
    proctoringTitle: "Proctoring alerts",
    proctoringSubtitle: "Events detected during the interview: tab, window, DevTools, or screen setup.",
    proctoringCount: "recorded alerts",
    noProctoringAlerts: "No proctoring alert recorded.",
    lightMode: "Light",
    darkMode: "Dark",
  },
} as const;

const dynamicFrToEnMap = new Map<string, string>([
  ["Étudiante en ingénierie informatique - Développement web et mobile", "Computer engineering student - Web and mobile development"],
  ["Etudiante en ingenierie informatique - Developpement web et mobile", "Computer engineering student - Web and mobile development"],
  ["Le profil presente un niveau global coherent et exploitable pour la suite du processus technique.", "The profile shows a coherent overall level and is usable for the next technical steps."],
  ["Aucun signal d'alerte majeur n'a ete detecte, mais la lecture doit rester prudente.", "No major alert signal was detected, but the reading should remain cautious."],
  ["Prevoir un echange complementaire pour approfondir les points techniques du cours.", "Plan a follow-up exchange to explore the course's technical points in more depth."],
  ["Expression claire", "Clear expression"],
  ["Bonne collaboration", "Good collaboration"],
  ["Capacite d'analyse", "Analytical ability"],
  ["Engagement a renforcer", "Engagement to strengthen"],
  ["Lecture stable sur cette dimension.", "Stable reading on this dimension."],
  ["Approfondir avec une question comportementale complementaire.", "Follow up with an additional behavioral question."],
  ["Aucun signal visuel notable n'a ete capture.", "No notable visual signal was captured."],
  ["Aucun signal vocal notable n'a ete capture.", "No notable vocal signal was captured."],
  ["Lecture indicative", "Indicative reading"],
  ["Profil solide", "Strong profile"],
  ["Profil a consolider", "Profile to strengthen"],
  ["Architecture solide", "Strong architecture"],
  ["Optimisation solide", "Strong optimization"],
  ["Diagnostic technique solide", "Strong technical diagnosis"],
]);

function translateDynamicText(text: string | undefined, language: Language) {
  const raw = String(text || "").trim();
  if (!raw || language === "fr") return raw;

  let translated = dynamicFrToEnMap.get(raw) || raw;
  const replacements: Array<[string, string]> = [
    ["Taux", "Rate"],
    ["taux", "rate"],
    ["service", "service"],
    ["Equipe", "Team"],
    ["equipe", "team"],
    ["visuelle", "visual"],
    ["visuel", "visual"],
    ["vocaux", "vocal"],
    ["vocal", "vocal"],
    ["stress", "stress"],
    ["architecture", "architecture"],
    ["optimisation", "optimization"],
    ["collaboration", "collaboration"],
    ["analyse", "analysis"],
    ["recommandation", "recommendation"],
    ["alerte", "alert"],
    ["majoritairement", "mostly"],
    ["neutre", "neutral"],
    ["exprime", "expresses"],
    ["faible", "low"],
    ["eleve", "high"],
    ["modere", "moderate"],
    ["absence", "absence"],
    ["absentéisme", "absenteeism"],
  ];

  for (const [from, to] of replacements) {
    translated = translated.split(from).join(to);
  }

  return translated;
}

const dynamicTranslationPairsV2: Array<[string, string]> = [
  ["Etudiante en ingenierie informatique - Developpement web et mobile", "Computer engineering student - Web and mobile development"],
  ["Le profil presente un niveau global coherent et exploitable pour la suite du processus technique.", "The profile shows a coherent overall level and is usable for the next technical steps."],
  ["Aucun signal d'alerte majeur n'a ete detecte, mais la lecture doit rester prudente.", "No major alert signal was detected, but the reading should remain cautious."],
  ["Prevoir un echange complementaire pour approfondir les points techniques du cours.", "Plan a follow-up exchange to explore the course's technical points in more depth."],
  ["Expression claire", "Clear expression"],
  ["Bonne collaboration", "Good collaboration"],
  ["Capacite d'analyse", "Analytical ability"],
  ["Engagement a renforcer", "Engagement to strengthen"],
  ["Lecture stable sur cette dimension.", "Stable reading on this dimension."],
  ["Approfondir avec une question comportementale complementaire.", "Follow up with an additional behavioral question."],
  ["Aucun signal visuel notable n'a ete capture.", "No notable visual signal was captured."],
  ["Aucun signal vocal notable n'a ete capture.", "No notable vocal signal was captured."],
  ["Lecture indicative", "Indicative reading"],
  ["Profil solide", "Strong profile"],
  ["Profil a consolider", "Profile to strengthen"],
  ["Architecture solide", "Strong architecture"],
  ["Optimisation solide", "Strong optimization"],
  ["Diagnostic technique solide", "Strong technical diagnosis"],
  ["Merci d'avoir partage ces observations detaillees.", "Thank you for sharing these detailed observations."],
  ["Merci d'avoir partage votre experience avec nous.", "Thank you for sharing your experience with us."],
  ["La presence visuelle a ete stable et bien cadree tout au long de l'entretien.", "Visual presence remained stable and well framed throughout the interview."],
  ["Votre presence visuelle a ete stable et bien cadree, montrant une bonne connexion avec l'ecran.", "Your visual presence remained stable and well framed, showing a good connection with the screen."],
  ["Le stress apparent reste limite dans l'ensemble, avec une expression plutot maitrisee.", "Observed stress remained limited overall, with fairly controlled expression."],
  ["Pratiquer des exercices de respiration pour soutenir un debit de parole fluide.", "Practice breathing exercises to support a fluid speaking pace."],
  ["Preparez des points cles a l'avance pour guider votre discours et reduire les pauses involontaires.", "Prepare key talking points in advance to guide your speech and reduce unintended pauses."],
  ["Le debit de parole a paru mesure, autour de 87.3 mots par minute.", "The speaking pace appeared measured, around 87.3 words per minute."],
  ["Les pauses et silences etaient perceptibles sur plusieurs reponses.", "Pauses and silences were noticeable across several answers."],
  ["Les marqueurs d'hesitation verbale sont restes occasionnels a moderates (0 fillers detectes).", "Verbal hesitation markers remained occasional to moderate (0 fillers detected)."],
  ["L'enthousiasme vocal a paru present mais mesure.", "Vocal enthusiasm seemed present but measured."],
];

function normalizeDynamicKeyV2(text: string) {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[’']/g, "'")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

const dynamicFrToEnMapV2 = new Map<string, string>(
  dynamicTranslationPairsV2.map(([fr, en]) => [normalizeDynamicKeyV2(fr), en])
);

const dynamicEnToFrMapV2 = new Map<string, string>(
  dynamicTranslationPairsV2.map(([fr, en]) => [normalizeDynamicKeyV2(en), fr])
);

function applyTextReplacementsV2(text: string, replacements: Array<[string, string]>) {
  let next = text;
  for (const [from, to] of replacements) {
    next = next.split(from).join(to);
  }
  return next;
}

function translateDynamicTextV2(text: string | undefined, language: Language) {
  const raw = String(text || "").trim();
  if (!raw) return raw;

  if (language === "en") {
    const exact = dynamicFrToEnMapV2.get(normalizeDynamicKeyV2(raw));
    if (exact) return exact;

    return applyTextReplacementsV2(raw, [
      ["Merci d’avoir partagé ces observations détaillées.", "Thank you for sharing these detailed observations."],
      ["Merci d'avoir partage ces observations detaillees.", "Thank you for sharing these detailed observations."],
      ["Merci d’avoir partagé votre expérience avec nous.", "Thank you for sharing your experience with us."],
      ["Merci d'avoir partage votre experience avec nous.", "Thank you for sharing your experience with us."],
      ["Votre présence visuelle a été stable et bien cadrée, montrant une bonne connexion avec l’écran.", "Your visual presence remained stable and well framed, showing a good connection with the screen."],
      ["Votre presence visuelle a ete stable et bien cadree, montrant une bonne connexion avec l'ecran.", "Your visual presence remained stable and well framed, showing a good connection with the screen."],
      ["Préparez des points clés à l’avance pour guider votre discours et réduire les pauses involontaires.", "Prepare key talking points in advance to guide your speech and reduce unintended pauses."],
      ["Preparez des points cles a l'avance pour guider votre discours et reduire les pauses involontaires.", "Prepare key talking points in advance to guide your speech and reduce unintended pauses."],
      ["L'enthousiasme vocal a paru présent mais mesuré.", "Vocal enthusiasm seemed present but measured."],
      ["L'enthousiasme vocal a paru present mais mesure.", "Vocal enthusiasm seemed present but measured."],
      ["présence visuelle", "visual presence"],
      ["presence visuelle", "visual presence"],
      ["entretien", "interview"],
      ["débit de parole", "speaking pace"],
      ["debit de parole", "speaking pace"],
      ["mots par minute", "words per minute"],
      ["pauses et silences", "pauses and silences"],
      ["réponses", "answers"],
      ["reponses", "answers"],
      ["hésitation verbale", "verbal hesitation"],
      ["hesitation verbale", "verbal hesitation"],
      ["détectés", "detected"],
      ["detectes", "detected"],
      ["Le stress apparent reste", "Observed stress remained"],
      ["Pratiquer des exercices de respiration", "Practice breathing exercises"],
      ["pour soutenir", "to support"],
      ["fluide", "fluid"],
      ["Taux", "Rate"],
      ["taux", "rate"],
      ["Equipe", "Team"],
      ["equipe", "team"],
      ["équipe", "team"],
      ["visuelle", "visual"],
      ["visuel", "visual"],
      ["vocaux", "vocal"],
      ["vocal", "vocal"],
      ["stress", "stress"],
      ["architecture", "architecture"],
      ["optimisation", "optimization"],
      ["collaboration", "collaboration"],
      ["analyse", "analysis"],
      ["recommandation", "recommendation"],
      ["alerte", "alert"],
      ["majoritairement", "mostly"],
      ["neutre", "neutral"],
      ["exprime", "expresses"],
      ["faible", "low"],
      ["eleve", "high"],
      ["élevé", "high"],
      ["modere", "moderate"],
      ["modéré", "moderate"],
      ["absence", "absence"],
      ["absentéisme", "absenteeism"],
      ["absenteisme", "absenteeism"],
    ]);
  }

  const exact = dynamicEnToFrMapV2.get(normalizeDynamicKeyV2(raw));
  if (exact) return exact;

  return applyTextReplacementsV2(raw, [
    ["Thank you for sharing these detailed observations.", "Merci d’avoir partagé ces observations détaillées."],
    ["Thank you for sharing your experience with us.", "Merci d'avoir partage votre experience avec nous."],
    ["Visual presence remained stable and well framed throughout the interview.", "La présence visuelle a été stable et bien cadrée tout au long de l’entretien."],
    ["Your visual presence remained stable and well framed, showing a good connection with the screen.", "Votre presence visuelle a ete stable et bien cadree, montrant une bonne connexion avec l'ecran."],
    ["Observed stress remained limited overall, with fairly controlled expression.", "Le stress apparent reste limité dans l’ensemble, avec une expression plutôt maîtrisée."],
    ["Practice breathing exercises to support a fluid speaking pace.", "Pratiquer des exercices de respiration pour soutenir un débit de parole fluide."],
    ["Prepare key talking points in advance to guide your speech and reduce unintended pauses.", "Preparez des points cles a l'avance pour guider votre discours et reduire les pauses involontaires."],
    ["The speaking pace appeared measured, around 87.3 words per minute.", "Le débit de parole a paru mesuré, autour de 87.3 mots par minute."],
    ["Pauses and silences were noticeable across several answers.", "Les pauses et silences étaient perceptibles sur plusieurs réponses."],
    ["Verbal hesitation markers remained occasional to moderate (0 fillers detected).", "Les marqueurs d’hésitation verbale sont restés occasionnels à modérés (0 fillers détectés)."],
    ["Vocal enthusiasm seemed present but measured.", "L'enthousiasme vocal a paru present mais mesure."],
    ["speaking pace", "débit de parole"],
    ["words per minute", "mots par minute"],
    ["pauses and silences", "pauses et silences"],
    ["answers", "réponses"],
    ["verbal hesitation", "hésitation verbale"],
    ["detected", "détectés"],
    ["Strong profile", "Profil solide"],
    ["Profile to strengthen", "Profil a consolider"],
    ["Clear expression", "Expression claire"],
    ["Good collaboration", "Bonne collaboration"],
    ["Analytical ability", "Capacite d'analyse"],
    ["Engagement to strengthen", "Engagement a renforcer"],
    ["Stable reading on this dimension.", "Lecture stable sur cette dimension."],
    ["Follow up with an additional behavioral question.", "Approfondir avec une question comportementale complementaire."],
    ["No notable visual signal was captured.", "Aucun signal visuel notable n'a ete capture."],
    ["No notable vocal signal was captured.", "Aucun signal vocal notable n'a ete capture."],
    ["Indicative reading", "Lecture indicative"],
    ["Strong architecture", "Architecture solide"],
    ["Strong optimization", "Optimisation solide"],
    ["Strong technical diagnosis", "Diagnostic technique solide"],
  ]);
}

const competencyMeta = [
  { key: "question_score", labelKey: "averageAnswerScore", color: "#2563eb" },
] as const;

function clamp(value: number, min = 0, max = 100) {
  return Math.min(max, Math.max(min, value));
}

function formatScore(value: number, suffix = "/5") {
  return `${Number.isFinite(value) ? value.toFixed(1).replace(".0", "") : "0"}${suffix}`;
}

function formatPercent(value: number) {
  return `${clamp(value).toFixed(value % 1 === 0 ? 0 : 1)}%`;
}

function formatDate(value?: string, language: Language = "fr") {
  if (!value) return language === "fr" ? "Non finalise" : "Not finalized";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return language === "fr" ? "Date indisponible" : "Date unavailable";
  return new Intl.DateTimeFormat(language === "fr" ? "fr-FR" : "en-US", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function wordsCount(text?: string) {
  return String(text || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean).length;
}

function splitIntoSentences(text?: string) {
  return String(text || "")
    .split(/(?<=[.!?])\s+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function toneFromScore(value: number): KpiCard["tone"] {
  if (value >= 75) return "good";
  if (value >= 45) return "soft";
  return "alert";
}

function normalizeSpeechRate(value: number) {
  return clamp(((value - 80) / 80) * 100);
}

function normalizePitchVariation(value: number) {
  return clamp((value / 70) * 100);
}

function normalizeSilence(value: number) {
  return clamp(100 - value);
}

function normalizeHesitation(metrics: Record<string, number | string | boolean>) {
  const density = Number(metrics.filler_density_pct || 0);
  const pauseCount = Number(metrics.pause_count_avg || 0);
  const label = String(metrics.dominant_hesitation || "").toLowerCase();
  const labelWeight = label === "noticeable" ? 28 : label === "moderate" ? 16 : 0;
  return clamp(density * 12 + pauseCount * 4 + labelWeight);
}

function donutGradient(values: Array<{ value: number; color: string }>) {
  const total = values.reduce((sum, item) => sum + item.value, 0) || 1;
  let current = 0;
  const segments = values.map((item) => {
    const from = (current / total) * 360;
    current += item.value;
    const to = (current / total) * 360;
    return `${item.color} ${from}deg ${to}deg`;
  });
  return `conic-gradient(${segments.join(", ")})`;
}

function normalizeStressFactorDetail(detail: string | undefined, copy: (typeof translations)[Language]) {
  const rawDetail = String(detail || "").trim();
  const normalizedDetail = rawDetail.toLowerCase();

  if (
    normalizedDetail === "custom model" ||
    normalizedDetail === "custom emotion model" ||
    normalizedDetail === "modele personnalise" ||
    normalizedDetail === "modele emotionnel ia"
  ) {
    return copy.customEmotionModel;
  }

  if (
    normalizedDetail === "visual emotion providers" ||
    normalizedDetail === "visual emotion engine" ||
    normalizedDetail === "fournisseurs emotion visuelle" ||
    normalizedDetail === "moteur emotionnel visuel"
  ) {
    return copy.visualEmotionProviders;
  }

  return rawDetail;
}

function polarToCartesian(centerX: number, centerY: number, radius: number, angleInDegrees: number) {
  const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180;
  return {
    x: centerX + radius * Math.cos(angleInRadians),
    y: centerY + radius * Math.sin(angleInRadians),
  };
}

function donutSegmentPath(centerX: number, centerY: number, outerRadius: number, innerRadius: number, startAngle: number, endAngle: number) {
  const outerStart = polarToCartesian(centerX, centerY, outerRadius, startAngle);
  const outerEnd = polarToCartesian(centerX, centerY, outerRadius, endAngle);
  const innerEnd = polarToCartesian(centerX, centerY, innerRadius, endAngle);
  const innerStart = polarToCartesian(centerX, centerY, innerRadius, startAngle);
  const largeArcFlag = endAngle - startAngle > 180 ? 1 : 0;

  return [
    `M ${outerStart.x} ${outerStart.y}`,
    `A ${outerRadius} ${outerRadius} 0 ${largeArcFlag} 1 ${outerEnd.x} ${outerEnd.y}`,
    `L ${innerEnd.x} ${innerEnd.y}`,
    `A ${innerRadius} ${innerRadius} 0 ${largeArcFlag} 0 ${innerStart.x} ${innerStart.y}`,
    "Z",
  ].join(" ");
}

function CardIcon({ tone }: { tone?: "good" | "soft" | "alert" }) {
  return (
    <span className={`${styles.cardIcon} ${tone ? styles[`cardIcon${tone[0].toUpperCase()}${tone.slice(1)}`] : ""}`}>
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3v18" />
        <path d="M5 10.5 12 3l7 7.5" />
        <path d="M7 14h10" />
      </svg>
    </span>
  );
}

function SidebarIcon({ type }: { type: "dashboard" | "hire" | "file" | "help" | "settings" | "interview" | "memory" }) {
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
  if (type === "settings") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 8.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Z" />
        <path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a2 2 0 0 1-4 0v-.2a1 1 0 0 0-.7-.9 1 1 0 0 0-1.1.2l-.1.1a2 2 0 0 1-2.8-2.8l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a2 2 0 0 1 0-4h.2a1 1 0 0 0 .9-.7 1 1 0 0 0-.2-1.1l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1 1 0 0 0 1.1.2 1 1 0 0 0 .6-.9V4a2 2 0 0 1 4 0v.2a1 1 0 0 0 .7.9 1 1 0 0 0 1.1-.2l.1-.1a2 2 0 0 1 2.8 2.8l-.1.1a1 1 0 0 0-.2 1.1 1 1 0 0 0 .9.6H20a2 2 0 0 1 0 4h-.2a1 1 0 0 0-.9.7Z" />
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

function InsightToneIcon({ tone }: { tone: "visual" | "audio" | "stress" | "summary" | "signals" }) {
  if (tone === "audio") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M6 13h2" />
        <path d="M10 9h2" />
        <path d="M14 6h2" />
        <path d="M18 9h1" />
        <path d="M10 14h2" />
        <path d="M14 14h2" />
        <path d="M18 14h1" />
      </svg>
    );
  }
  if (tone === "stress") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 5c-3.4 0-6 2.7-6 6.1 0 4.4 6 8.9 6 8.9s6-4.5 6-8.9C18 7.7 15.4 5 12 5Z" />
        <path d="M12 8.2v5.2" />
        <path d="M12 16.6v.2" />
      </svg>
    );
  }
  if (tone === "summary") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M6 7h12" />
        <path d="M6 12h8" />
        <path d="M6 17h10" />
      </svg>
    );
  }
  if (tone === "signals") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 15.5 9 11l3 2.5L19 7" />
        <path d="M15 7h4v4" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 12c2-3.2 4.7-4.8 8-4.8s6 1.6 8 4.8c-2 3.2-4.7 4.8-8 4.8S6 15.2 4 12Z" />
      <circle cx="12" cy="12" r="2.2" />
    </svg>
  );
}

export default function ReportDashboardPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const rawSessionId = params?.sessionId;
  const sessionId = typeof rawSessionId === "string" ? rawSessionId : Array.isArray(rawSessionId) ? rawSessionId[0] : "";
  const [activeView, setActiveView] = useState<"report" | "insights">("report");
  const [payload, setPayload] = useState<SessionReportPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [downloadingInsightsPdf, setDownloadingInsightsPdf] = useState(false);
  const [sharingPdf, setSharingPdf] = useState(false);
  const [sharingInsightsPdf, setSharingInsightsPdf] = useState(false);
  const [hoveredCompetencyIndex, setHoveredCompetencyIndex] = useState<number | null>(null);
  const [language, setLanguage] = useState<Language>("fr");
  const [theme, setTheme] = useState<Theme>("light");
  const [browserOrigin, setBrowserOrigin] = useState("");
  const [isQrModalOpen, setIsQrModalOpen] = useState(false);

  useEffect(() => {
    setActiveView(searchParams.get("view") === "insights" ? "insights" : "report");
  }, [searchParams]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedTheme = window.localStorage.getItem("report-dashboard-theme");
    if (storedTheme === "light" || storedTheme === "dark") {
      setTheme(storedTheme);
      return;
    }

    if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      setTheme("dark");
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("report-dashboard-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setBrowserOrigin(window.location.origin);
  }, []);

  useEffect(() => {
    if (!isQrModalOpen || typeof window === "undefined") return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsQrModalOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isQrModalOpen]);

  useEffect(() => {
    if (!sessionId) return;

    const loadReport = async () => {
      setLoading(true);
      setError("");
      try {
        const query = new URLSearchParams({ language });
        if (activeView === "insights") {
          query.set("include_insights", "1");
        }
        const res = await fetch(`/api/tech/session/${encodeURIComponent(sessionId)}?${query.toString()}`, {
          method: "GET",
          cache: "no-store",
        });
        const data = (await res.json()) as SessionReportPayload & { error?: string; detail?: string };
        if (!res.ok) {
          throw new Error(data?.detail || data?.error || translations.fr.unableToLoadReport);
        }
        setPayload(data);
      } catch (loadError) {
        setError((loadError as Error).message);
      } finally {
        setLoading(false);
      }
    };

    void loadReport();
  }, [sessionId, language, activeView]);

  useEffect(() => {
    const reportUnlockedStatus = payload?.interview_status === "finalized" && Boolean(payload?.final_report || null);
    if (!reportUnlockedStatus && activeView !== "report") {
      setActiveView("report");
    }
  }, [payload, activeView]);

  const finalReport = payload?.final_report || null;
  const copy = translations[language];
  const tDyn = (text?: string) => translateDynamicTextV2(text, language);
  const rawDyn = (text?: string) => String(text || "").trim();
  const effectiveTheme: Theme = theme;
  const shareOrigin = QR_SHARE_BASE_URL || browserOrigin;
  const qrNeedsPublicOrigin = !QR_SHARE_BASE_URL && isLocalOnlyOrigin(browserOrigin);
  const reportUnlocked = payload?.interview_status === "finalized" && Boolean(finalReport);
  const reportPdfViewUrl = sessionId && shareOrigin ? `${shareOrigin}/report/${encodeURIComponent(sessionId)}/pdf` : "";
  const insightsPdfViewUrl =
    sessionId && shareOrigin
      ? `${shareOrigin}/report/${encodeURIComponent(sessionId)}/insights-pdf?language=${encodeURIComponent(language)}`
      : "";
  const activePdfViewUrl = activeView === "insights" ? insightsPdfViewUrl : reportPdfViewUrl;
  const activeQrLabel = activeView === "insights" ? copy.qrInsightsPdf : copy.qrPdf;
  const activeQrImageUrl = activePdfViewUrl
    ? `https://api.qrserver.com/v1/create-qr-code/?size=512x512&margin=16&data=${encodeURIComponent(activePdfViewUrl)}`
    : "";
  const liveInsightsPayload: CandidateInsightsPayload | null = payload
    ? {
        response_language: language,
        visual_context: payload.visual_context || null,
        audio_context: payload.audio_context || null,
        stress_context: payload.stress_context || null,
        insights_advice: payload.insights_advice || null,
      }
    : null;
  const proctoringEvents = (payload?.proctoring_events || finalReport?.proctoring_events || []).filter(
    (event) => event && (event.message || event.reason)
  );
  const proctoringAlertCount = Number(
    payload?.proctoring_alerts_count ?? finalReport?.proctoring_alerts_count ?? proctoringEvents.length
  );
  const candidateName =
    String(payload?.cv_profile?.candidate_name || payload?.cv_profile?.name || copy.candidateFallback).trim() || copy.candidateFallback;
  const candidateHeadline = tDyn(String(payload?.cv_profile?.headline || copy.profileInReview).trim()) || copy.profileInReview;
  const finalizedLabel = formatDate(payload?.finalized_at || payload?.updated_at, language);
  const rawSummarySentences = splitIntoSentences(String(finalReport?.summary || ""));
  const contactItems = [
    {
      label: copy.email,
      value: String(payload?.cv_profile?.email || "").trim(),
      href: String(payload?.cv_profile?.email || "").trim()
        ? `mailto:${String(payload?.cv_profile?.email || "").trim()}`
        : "",
    },
    {
      label: copy.phone,
      value: String(payload?.cv_profile?.phone || "").trim(),
      href: String(payload?.cv_profile?.phone || "").trim()
        ? `tel:${String(payload?.cv_profile?.phone || "").trim()}`
        : "",
    },
    {
      label: copy.linkedin,
      value: String(payload?.cv_profile?.linkedin || "").trim(),
      href: String(payload?.cv_profile?.linkedin || "").trim()
        ? `https://${String(payload?.cv_profile?.linkedin || "").trim().replace(/^https?:\/\//, "")}`
        : "",
    },
    {
      label: copy.github,
      value: String(payload?.cv_profile?.github || "").trim(),
      href: String(payload?.cv_profile?.github || "").trim()
        ? `https://${String(payload?.cv_profile?.github || "").trim().replace(/^https?:\/\//, "")}`
        : "",
    },
  ].filter((item) => item.value);

  const stressScore = clamp(Number(payload?.stress_context?.score || 0));
  const audioMetrics = (finalReport?.audio_metrics || payload?.audio_context?.metrics || {}) as Record<string, number>;
  const visualMetricsSource = (payload?.visual_context?.metrics || finalReport?.visual_metrics || {}) as Record<string, unknown>;
  const visualMetrics = visualMetricsSource as Record<string, number>;
  const turns = payload?.turns || [];

  const questionRows = useMemo(() => {
    const fallbackAverage =
      Number(finalReport?.competencies?.question_score || 0) ||
      clamp(Number(finalReport?.score_total || 0) / 20, 0, 5);

    const rows = turns
      .map((turn, turnIndex) => {
        if (turnIndex === 0) return null;

        const previousTurn = turns[turnIndex - 1];
        const question = rawDyn(previousTurn?.say);
        const answer = rawDyn(turn.candidate_text);

        if (!question || !answer) return null;

        const rawScore = Number(turn.score_partial?.question_score);
        const score = Number.isFinite(rawScore) ? clamp(rawScore, 0, 5) : 0;

        return {
          dimension: "",
          question,
          answer,
          score,
          scoreLabel: formatScore(score),
          progress: clamp(score * 20),
          tone: toneFromScore(score * 20),
        };
      })
      .filter((row): row is NonNullable<typeof row> => Boolean(row))
      .map((row, index) => ({ ...row, dimension: `Q${index + 1}` }));

    const shouldUseFallbackScore = rows.length > 0 && rows.every((row) => row.score === 0) && fallbackAverage > 0;
    if (shouldUseFallbackScore) {
      return rows.map((row) => ({
        ...row,
        score: fallbackAverage,
        scoreLabel: formatScore(fallbackAverage),
        progress: clamp(fallbackAverage * 20),
        tone: toneFromScore(fallbackAverage * 20),
      }));
    }

    if (rows.length > 0) return rows;

    return [
      {
        dimension: "Q1",
        question: rawDyn(finalReport?.advice?.[0]) || copy.noQuestionCaptured,
        answer: rawDyn(finalReport?.summary) || copy.noAnswerCaptured,
        score: Number.isFinite(fallbackAverage) ? clamp(fallbackAverage, 0, 5) : 0,
        scoreLabel: formatScore(Number.isFinite(fallbackAverage) ? clamp(fallbackAverage, 0, 5) : 0),
        progress: clamp((Number.isFinite(fallbackAverage) ? fallbackAverage : 0) * 20),
        tone: toneFromScore((Number.isFinite(fallbackAverage) ? fallbackAverage : 0) * 20),
      },
    ];
  }, [copy, finalReport, turns]);

  const averageQuestionScore = questionRows.reduce((sum, item) => sum + item.score, 0) / Math.max(questionRows.length, 1);

  const competencyCards = useMemo(() => {
    const rawValue = Number.isFinite(averageQuestionScore) ? averageQuestionScore : 0;
    return competencyMeta.map((item) => ({
      ...item,
      label: copy[item.labelKey],
      rawValue,
      scaled: clamp(rawValue * 20),
    }));
  }, [averageQuestionScore, copy]);

  const totalScore = Number(finalReport?.score_total || clamp(averageQuestionScore * 20) || 0);

  const kpis: KpiCard[] = [
    {
      label: copy.scoreGlobalReport,
      value: `${Math.round(totalScore)}/100`,
      helper: totalScore >= 75 ? copy.solidProfile : copy.profileToConsolidate,
      tone: toneFromScore(totalScore),
    },
    {
      label: copy.averageAnswerScore,
      value: formatScore(averageQuestionScore || 0),
      helper: copy.answersGradedLikeExam,
      tone: toneFromScore((averageQuestionScore || 0) * 20),
    },
    {
      label: copy.evaluatedQuestions,
      value: `${questionRows.length}`,
      helper: copy.basedOnCourseQuestions,
      tone: questionRows.length > 0 ? "good" : "alert",
    },
    {
      label: copy.courseExam,
      value: payload?.interview_status || "finalized",
      helper: copy.basedOnCourseQuestions,
      tone: toneFromScore(totalScore),
    },
  ];

  const insightsItems = [
    {
      label: copy.technicalReview,
      text:
        rawDyn(payload?.insights_advice?.summary?.[0]) ||
        rawDyn(rawSummarySentences[0]) ||
        copy.coherentProfile,
    },
    {
      label: copy.attention,
      text:
        rawDyn(payload?.stress_context?.summary) ||
        rawDyn(payload?.audio_context?.signals?.[0]) ||
        rawDyn(finalReport?.audio_signals?.[0]) ||
        copy.noMajorAlert,
    },
    {
      label: copy.recommendation,
      text:
        rawDyn(payload?.insights_advice?.next_steps?.[0]) ||
        rawDyn(finalReport?.advice?.[0]) ||
        copy.followupRecommendation,
    },
  ];

  const audioBars = [
    {
      label: copy.speechRate,
      value: normalizeSpeechRate(Number(audioMetrics.speech_rate_wpm_avg || 0)),
      detail: `${Math.round(Number(audioMetrics.speech_rate_wpm_avg || 0))} wpm`,
    },
    {
      label: copy.volumeLabel,
      value: clamp(Number(audioMetrics.volume_score_avg || 0)),
      detail: `${Math.round(Number(audioMetrics.volume_score_avg || 0))}/100`,
    },
    {
      label: copy.usefulSilence,
      value: normalizeSilence(Number(audioMetrics.silence_pct_avg || 0)),
      detail: `${Math.round(Number(audioMetrics.silence_pct_avg || 0))}%`,
    },
    {
      label: copy.variation,
      value: normalizePitchVariation(Number(audioMetrics.pitch_variation_hz_avg || 0)),
      detail: `${Math.round(Number(audioMetrics.pitch_variation_hz_avg || 0))} Hz`,
    },
  ];

  const visualBars = [
    {
      label: copy.faceDetected,
      value: clamp(Number(visualMetrics.face_detected_pct || 0)),
      detail: `${Math.round(Number(visualMetrics.face_detected_pct || 0))}%`,
    },
    {
      label: copy.centering,
      value: clamp(Number(visualMetrics.centered_pct || 0)),
      detail: `${Math.round(Number(visualMetrics.centered_pct || 0))}%`,
    },
    {
      label: copy.stablePosture,
      value: clamp(Number(visualMetrics.stable_posture_pct || 0)),
      detail: `${Math.round(Number(visualMetrics.stable_posture_pct || 0))}%`,
    },
    {
      label: copy.visualEngagement,
      value: clamp(Number(visualMetrics.visual_enthusiasm_pct || visualMetrics.engaged_pct || 0)),
      detail: `${Math.round(Number(visualMetrics.visual_enthusiasm_pct || visualMetrics.engaged_pct || 0))}%`,
    },
  ];

  const stressFactors =
    payload?.stress_context?.factors?.map((item) => ({
      label: rawDyn(String(item.label || item.key || copy.factor)) || copy.factor,
      value: clamp(Number(item.value || 0)),
      detail: normalizeStressFactorDetail(String(item.detail || ""), copy),
    })) || [];

  const emotionBreakdown = (
    visualMetricsSource.model_emotion_breakdown ||
    visualMetricsSource.emotion_breakdown ||
    visualMetricsSource.raw_emotion_breakdown ||
    {}
  ) as Record<string, number>;
  const visualEmotionCards = [
    { key: "happy", emoji: "😊", label: copy.happy },
    { key: "angry", emoji: "😠", label: copy.angry },
    { key: "sad", emoji: "😢", label: copy.sad },
    { key: "neutral", emoji: "😐", label: copy.neutral },
    { key: "surprise", emoji: "😲", label: copy.surprise },
  ].map((item) => ({
    ...item,
    value: Math.round(Number(emotionBreakdown[item.key] || 0)),
  }));

  const skillBars = questionRows.map((item) => ({
      label: item.dimension,
      value: item.progress,
  }));

  const visualAverage = Math.round(visualBars.reduce((sum, item) => sum + item.value, 0) / Math.max(visualBars.length, 1));
  const audioAverage = Math.round(audioBars.reduce((sum, item) => sum + item.value, 0) / Math.max(audioBars.length, 1));
  const audioSignals = (payload?.audio_context?.signals || finalReport?.audio_signals || [copy.noVocalSignal]).map((item) => rawDyn(item) || copy.noVocalSignal);
  const stressAverage = Math.round(
    stressFactors.reduce((sum, item) => sum + item.value, 0) / Math.max(stressFactors.length, 1)
  );
  const insightOverviewCards = [
    {
      label: copy.visualReading,
      value: `${visualAverage}%`,
      helper: `${visualBars.length} ${copy.visualSignalsConsolidated}`,
      tone: "visual",
    },
    {
      label: copy.vocalSignal,
      value: `${audioAverage}%`,
      helper: `${audioBars.length} ${copy.vocalIndicators}`,
      tone: "audio",
    },
    {
      label: copy.observedStress,
      value: `${stressAverage}%`,
      helper: rawDyn(String(payload?.stress_context?.band || copy.indicativeReading)) || copy.indicativeReading,
      tone: "stress",
    },
    {
      label: copy.keyInsights,
      value: `${insightsItems.length}`,
      helper: copy.priorityPoints,
      tone: "summary",
    },
  ] as const;

  const donutSegments = useMemo(() => {
    let currentAngle = 0;

    return competencyCards.map((item) => {
      const rawValue = item.rawValue || 0;
      const percent = clamp(item.scaled || rawValue * 20);
      const sweep = (percent / 100) * 359.99;
      const startAngle = currentAngle;
      const endAngle = currentAngle + sweep;
      currentAngle = endAngle;

      return {
        ...item,
        rawValue,
        percent: Math.round(percent),
        path: donutSegmentPath(100, 100, 72, 36, startAngle, endAngle),
      };
    });
  }, [competencyCards]);

  const activeCompetency = hoveredCompetencyIndex !== null ? donutSegments[hoveredCompetencyIndex] : null;

  const detailRows = questionRows.map((item) => ({
    dimension: item.dimension,
    score: item.scoreLabel,
    signal: item.answer,
    action: item.question,
    progress: item.progress,
    tone: item.tone,
  }));

  const insightSignalRows = [
    {
      title: copy.visualTitle,
      items:
        (payload?.visual_context?.signals || finalReport?.visual_signals || [copy.noVisualSignal]).map((item) => rawDyn(item) || copy.noVisualSignal),
    },
    {
      title: copy.vocalTitle,
      items: audioSignals,
    },
  ];

  const downloadPdf = async () => {
    if (!sessionId || downloadingPdf) return;
    setDownloadingPdf(true);
    try {
      const res = await fetch(`/api/tech/session/${encodeURIComponent(sessionId)}/report`, {
        method: "GET",
      });
      if (!res.ok) {
        const raw = await res.text();
        throw new Error(raw || copy.pdfUnavailable);
      }

      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const fileNameMatch = disposition.match(/filename=\"?([^"]+)\"?/i);
      const fileName = fileNameMatch?.[1] || `${sessionId}-technical-report.pdf`;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (downloadError) {
      setError((downloadError as Error).message);
    } finally {
      setDownloadingPdf(false);
    }
  };

  const downloadInsightsPdf = async () => {
    if (!sessionId || downloadingInsightsPdf) return;
    setDownloadingInsightsPdf(true);
    try {
      const res = await fetch(`/api/tech/session/${encodeURIComponent(sessionId)}/insights-report?language=${encodeURIComponent(language)}`, {
        method: "GET",
      });
      if (!res.ok) {
        const raw = await res.text();
        throw new Error(raw || copy.pdfUnavailable);
      }

      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const fileNameMatch = disposition.match(/filename=\"?([^"]+)\"?/i);
      const fileName = fileNameMatch?.[1] || `${sessionId}-insights-visuels-vocaux.pdf`;
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (downloadError) {
      setError((downloadError as Error).message);
    } finally {
      setDownloadingInsightsPdf(false);
    }
  };

  const sharePdfNative = async () => {
    if (!sessionId || sharingPdf) return;
    setSharingPdf(true);
    setError("");

    try {
      const res = await fetch(`/api/tech/session/${encodeURIComponent(sessionId)}/report`, {
        method: "GET",
      });
      if (!res.ok) {
        const raw = await res.text();
        throw new Error(raw || copy.pdfUnavailable);
      }

      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const fileNameMatch = disposition.match(/filename=\"?([^"]+)\"?/i);
      const fileName = fileNameMatch?.[1] || `${sessionId}-technical-report.pdf`;
      const pdfFile = new File([blob], fileName, { type: "application/pdf" });

      if (typeof navigator !== "undefined" && navigator.canShare && navigator.canShare({ files: [pdfFile] })) {
        await navigator.share({
          title: `${copy.reportTitle} - ${candidateName}`,
          text: `${copy.reportTitle} ${candidateName}`,
          files: [pdfFile],
        });
        return;
      }

      throw new Error(copy.shareNativeUnavailable);
    } catch (shareError) {
      setError((shareError as Error).message);
    } finally {
      setSharingPdf(false);
    }
  };

  const shareInsightsPdfNative = async () => {
    if (!sessionId || sharingInsightsPdf) return;
    setSharingInsightsPdf(true);
    setError("");

    try {
      const res = await fetch(`/api/tech/session/${encodeURIComponent(sessionId)}/insights-report?language=${encodeURIComponent(language)}`, {
        method: "GET",
      });
      if (!res.ok) {
        const raw = await res.text();
        throw new Error(raw || copy.pdfUnavailable);
      }

      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const fileNameMatch = disposition.match(/filename=\"?([^"]+)\"?/i);
      const fileName = fileNameMatch?.[1] || `${sessionId}-insights-visuels-vocaux.pdf`;
      const pdfFile = new File([blob], fileName, { type: "application/pdf" });

      if (typeof navigator !== "undefined" && navigator.canShare && navigator.canShare({ files: [pdfFile] })) {
        await navigator.share({
          title: `${copy.visualVocalInsights} - ${candidateName}`,
          text: `${copy.visualVocalInsights} ${candidateName}`,
          files: [pdfFile],
        });
        return;
      }

      throw new Error(copy.shareNativeUnavailable);
    } catch (shareError) {
      setError((shareError as Error).message);
    } finally {
      setSharingInsightsPdf(false);
    }
  };

  if (loading) {
    return (
      <div className={`${styles.shell} ${theme === "dark" ? styles.themeDark : styles.themeLight}`}>
        <aside className={styles.sidebar}>
          <div className={styles.brand}>SUBUL</div>
        </aside>
        <main className={styles.main}>
          <section className={styles.loadingStage} aria-label={copy.loadingDashboard}>
            <div className={styles.loadingOrbital} aria-hidden="true">
              <div className={styles.loadingGlow} />
              <div className={styles.loadingRingPrimary} />
              <div className={styles.loadingRingSecondary} />
              <div className={styles.loadingRingTertiary} />
              <span className={`${styles.loadingPulseDot} ${styles.loadingPulseDotOne}`} />
              <span className={`${styles.loadingPulseDot} ${styles.loadingPulseDotTwo}`} />
              <span className={`${styles.loadingPulseDot} ${styles.loadingPulseDotThree}`} />
              <div className={styles.loadingCore}>
                <span className={styles.loadingCoreWord}>SUBUL</span>
              </div>
            </div>
            <div className={styles.loadingCard}>
              <div className={styles.loadingEyebrow}>SUBUL TECH</div>
              <h1 className={styles.loadingTitle}>{copy.loadingDashboard}</h1>
              <div className={styles.loadingTrack} aria-hidden="true">
                <span className={styles.loadingTrackFill} />
              </div>
            </div>
          </section>
        </main>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`${styles.shell} ${theme === "dark" ? styles.themeDark : styles.themeLight}`}>
        <aside className={styles.sidebar}>
          <div className={styles.brand}>SUBUL</div>
        </aside>
        <main className={styles.main}>
          <div className={styles.errorCard}>
            <h1>{copy.unavailableReport}</h1>
            <p>{tDyn(error) || error}</p>
            <div className={styles.headerActions}>
              <Link href="/" className={styles.ghostButton}>{copy.backToInterview}</Link>
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (!reportUnlocked) {
    return (
      <div className={`${styles.shell} ${theme === "dark" ? styles.themeDark : styles.themeLight}`}>
        <aside className={styles.sidebar}>
          <div className={styles.brand}>SUBUL</div>
        </aside>
        <main className={styles.main}>
          <div className={styles.errorCard}>
            <h1>{copy.resultsPendingTitle}</h1>
            <p>{copy.resultsPendingMessage}</p>
            <div className={styles.headerActions}>
              <Link href={`/?session=${encodeURIComponent(sessionId)}`} className={styles.ghostButton}>
                {copy.backToInterview}
              </Link>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className={`${styles.shell} ${effectiveTheme === "dark" ? styles.themeDark : styles.themeLight}`}>
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
              {copy.interviewNav}
            </Link>
            <Link className={styles.navItem} href="/dashboard">
              <SidebarIcon type="dashboard" />
              {copy.analytics}
            </Link>
            <span className={styles.navGroupTitle}>{copy.sidebarReports}</span>
            <button
              type="button"
              className={`${styles.navItem} ${styles.navButton} ${reportUnlocked && activeView === "report" ? styles.navItemActive : ""} ${!reportUnlocked ? styles.navItemDisabled : ""}`}
              onClick={() => setActiveView("report")}
              disabled={!reportUnlocked}
            >
              <SidebarIcon type="dashboard" />
              {copy.reportNav}
            </button>
            <button
              type="button"
              className={`${styles.navItem} ${styles.navButton} ${reportUnlocked && activeView === "insights" ? styles.navItemActive : ""} ${!reportUnlocked ? styles.navItemDisabled : ""}`}
              onClick={() => setActiveView("insights")}
              disabled={!reportUnlocked}
            >
              <SidebarIcon type="hire" />
              {copy.insights}
            </button>
            <span className={styles.navGroupTitle}>{copy.sidebarTools}</span>
            <Link className={styles.navItem} href="/history">
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

      <main className={styles.main} id="dashboard">
       

        <section
          className={styles.header}
          id="report-view"
        >
          {activeView === "insights" ? (
            <div>
              <h1>{copy.visualVocalInsights}</h1>
              <p>
                {copy.insightsSubtitle} <strong>{candidateName}</strong>.
              </p>
            </div>
          ) : (
            <div>
              <h1>{copy.reportTitle}</h1>
              <p>
                {copy.reportSubtitle} <strong>{candidateName}</strong>.
              </p>
            </div>
          )}

          <div className={styles.headerActions}>
            <div className={styles.themeToggle}>
              <button
                type="button"
                className={`${styles.themeButton} ${effectiveTheme === "light" ? styles.themeButtonActive : ""}`}
                onClick={() => setTheme("light")}
                aria-label={copy.lightMode}
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
                className={`${styles.themeButton} ${effectiveTheme === "dark" ? styles.themeButtonActive : ""}`}
                onClick={() => setTheme("dark")}
                aria-label={copy.darkMode}
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
            {activePdfViewUrl ? (
              <button
                type="button"
                className={styles.qrTrigger}
                onClick={() => setIsQrModalOpen(true)}
                aria-haspopup="dialog"
                aria-label={`${copy.showQrCode} - ${activeQrLabel}`}
                title={`${copy.showQrCode} - ${activeQrLabel}`}
              >
                <span className={styles.qrTriggerIcon} aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <path d="M4 4h6v6H4z" />
                    <path d="M14 4h6v6h-6z" />
                    <path d="M4 14h6v6H4z" />
                    <path d="M15 15h1" />
                    <path d="M18 15h2v2" />
                    <path d="M14 18h2" />
                    <path d="M17 18h3v2" />
                    <path d="M15 20h1" />
                  </svg>
                </span>
              </button>
            ) : null}
            {activeView === "report" ? (
              <button
                type="button"
                className={`${styles.socialButton} ${styles.headerIconButton}`}
                onClick={sharePdfNative}
                disabled={!sessionId || sharingPdf}
                aria-label={sharingPdf ? copy.sharing : copy.sharePdf}
                title={sharingPdf ? copy.sharing : copy.sharePdf}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="18" cy="5" r="2.5" />
                  <circle cx="6" cy="12" r="2.5" />
                  <circle cx="18" cy="19" r="2.5" />
                  <path d="M8.3 10.9 15.7 6.1" />
                  <path d="M8.3 13.1 15.7 17.9" />
                </svg>
              </button>
            ) : null}
            {activeView === "insights" ? (
              <button
                type="button"
                className={`${styles.socialButton} ${styles.headerIconButton}`}
                onClick={shareInsightsPdfNative}
                disabled={!sessionId || sharingInsightsPdf}
                aria-label={sharingInsightsPdf ? copy.sharing : copy.sharePdf}
                title={sharingInsightsPdf ? copy.sharing : copy.sharePdf}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="18" cy="5" r="2.5" />
                  <circle cx="6" cy="12" r="2.5" />
                  <circle cx="18" cy="19" r="2.5" />
                  <path d="M8.3 10.9 15.7 6.1" />
                  <path d="M8.3 13.1 15.7 17.9" />
                </svg>
              </button>
            ) : null}
            {activeView === "report" ? (
              <button
                type="button"
                className={`${styles.primaryButton} ${styles.headerIconButton}`}
                onClick={downloadPdf}
                disabled={!finalReport || downloadingPdf}
                aria-label={downloadingPdf ? copy.preparing : copy.downloadPdf}
                title={downloadingPdf ? copy.preparing : copy.downloadPdf}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 4v10" />
                  <path d="M8.5 10.5 12 14l3.5-3.5" />
                  <path d="M5 18v1a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-1" />
                </svg>
              </button>
            ) : null}
            {activeView === "insights" ? (
              <button
                type="button"
                className={`${styles.primaryButton} ${styles.headerIconButton}`}
                onClick={downloadInsightsPdf}
                disabled={!finalReport || downloadingInsightsPdf}
                aria-label={downloadingInsightsPdf ? copy.preparing : copy.downloadInsightsPdf}
                title={downloadingInsightsPdf ? copy.preparing : copy.downloadInsightsPdf}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 4v10" />
                  <path d="M8.5 10.5 12 14l3.5-3.5" />
                  <path d="M5 18v1a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-1" />
                </svg>
              </button>
            ) : null}
          </div>
        </section>

        {activeView === "report" ? (
        <section className={`${styles.sectionBlock} ${styles.rhSection}`}>
          

          <section className={styles.profileHeroCard}>
            <div className={styles.profileHeroTop}>
              <div>
                <span className={styles.profileHeroKicker}>{copy.candidateProfile}</span>
                <h3 className={styles.profileHeroName}>{candidateName}</h3>
                <p className={styles.profileHeroRole}>{candidateHeadline}</p>
              </div>
              <div className={styles.profileHeroBadge}>
                <span>{copy.reportScore}</span>
                <strong>{Math.round(totalScore)}/100</strong>
              </div>
            </div>

            {contactItems.length > 0 ? (
              <div className={styles.profileHeroContacts}>
                {contactItems.map((item) => (
                  <a key={item.label} className={styles.profileHeroContact} href={item.href} target="_blank" rel="noreferrer">
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                  </a>
                ))}
              </div>
            ) : null}
          </section>

          <section className={styles.kpiGrid}>
            {kpis.map((item) => (
              <article key={item.label} className={styles.kpiCard}>
                <div className={styles.kpiTop}>
                  <p>{item.label}</p>
                  <CardIcon tone={item.tone} />
                </div>
                <strong className={styles.kpiValue}>{item.value}</strong>
                <span className={`${styles.kpiBadge} ${styles[`badge${item.tone[0].toUpperCase()}${item.tone.slice(1)}`]}`}>
                  {item.helper}
                </span>
              </article>
            ))}
          </section>

          <section className={`${styles.panelCard} ${styles.proctoringCard}`}>
            <div className={styles.panelHead}>
              <div>
                <h3>{copy.proctoringTitle}</h3>
                <p>{copy.proctoringSubtitle}</p>
              </div>
              <span className={`${styles.legendPill} ${proctoringAlertCount > 0 ? styles.proctoringPillAlert : ""}`}>
                {proctoringAlertCount} {copy.proctoringCount}
              </span>
            </div>
            {proctoringEvents.length ? (
              <div className={styles.proctoringList}>
                {proctoringEvents.map((event, index) => (
                  <div className={styles.proctoringItem} key={`${event.time || event.reason || "event"}-${index}`}>
                    <div className={styles.proctoringItemIcon}>
                      <svg viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                      </svg>
                    </div>
                    <div className={styles.proctoringItemContent}>
                      <strong>{event.message || `${copy.proctoringTitle} ${event.count || index + 1}`}</strong>
                      <span>{formatDate(event.time, language)} · {event.reason || "unknown"}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className={styles.dashboardEmptyState}>{copy.noProctoringAlerts}</div>
            )}
          </section>

          <section className={styles.analyticsGrid}>
            <article className={`${styles.panelCard} ${styles.donutFeatureCard}`}>
              <div className={styles.panelHead}>
                <h3>{copy.skillsDistribution}</h3>
              </div>
              <div className={styles.donutSection}>
                <div className={styles.donutRing}>
                  <svg className={styles.donutSvg} viewBox="0 0 200 200" aria-hidden="true">
                    <circle className={styles.donutTrackBase} cx="100" cy="100" r="72" />
                    {donutSegments.map((item, index) => (
                      <path
                        key={item.label}
                        d={item.path}
                        className={`${styles.donutSegment} ${hoveredCompetencyIndex === index ? styles.donutSegmentActive : ""}`}
                        style={{ ["--segment-color" as keyof CSSProperties]: item.color } as CSSProperties}
                        onMouseEnter={() => setHoveredCompetencyIndex(index)}
                        onMouseLeave={() => setHoveredCompetencyIndex(null)}
                      />
                    ))}
                  </svg>
                  <div className={styles.donutCenter}>
                    <strong>{activeCompetency ? formatScore(activeCompetency.rawValue || 0) : `${Math.round(totalScore)}/100`}</strong>
                    <span>{activeCompetency ? activeCompetency.label : copy.total}</span>
                  </div>
                </div>
                <div className={styles.legendList}>
                  {donutSegments.map((item, index) => (
                    <button
                      key={item.label}
                      type="button"
                      className={`${styles.legendItem} ${hoveredCompetencyIndex === index ? styles.legendItemActive : ""}`}
                      onMouseEnter={() => setHoveredCompetencyIndex(index)}
                      onMouseLeave={() => setHoveredCompetencyIndex(null)}
                    >
                      <span className={styles.legendSwatch} style={{ background: item.color }} />
                      <span>
                        {item.label} ({formatScore(item.rawValue || 0)}) - {formatPercent(item.scaled)}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </article>

            <article className={`${styles.panelCard} ${styles.skillsFeatureCard}`}>
              <div className={styles.panelHead}>
                <h3>{copy.topCvSkills}</h3>
              </div>
              <div className={styles.metricBars}>
                {skillBars.map((item) => (
                  <div key={item.label} className={styles.metricBarRow}>
                    <div className={styles.metricBarLabel}>
                      <span>{item.label}</span>
                      <small>{formatPercent(item.value)}</small>
                    </div>
                    <div className={styles.metricTrack}>
                      <span style={{ width: `${item.value}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </section>
          <section className={styles.tableCard} id="table">
            <div className={styles.tableHead}>
              <div>
                <h3>{copy.reportSummary}</h3>
                <p>{copy.reportSummarySubtitle}</p>
              </div>
              <div className={styles.tableActions}>
                <span className={styles.metaPill}>{copy.status}: {payload?.interview_status || "finalized"}</span>
              </div>
            </div>

            <div className={styles.tableWrap}>
              <table>
                <thead>
                  <tr>
                    <th>{copy.dimension}</th>
                    <th>{copy.score}</th>
                    <th>{copy.keySignal}</th>
                    <th>{copy.recommendedAction}</th>
                  </tr>
                </thead>
                <tbody>
                  {detailRows.map((row) => (
                    <tr key={row.dimension}>
                      <td>
                        <div className={styles.dimensionCell}>
                          <span
                            className={`${styles.dimensionIcon} ${styles[`dimension${row.tone[0].toUpperCase()}${row.tone.slice(1)}`]}`}
                          >
                            <svg viewBox="0 0 24 24" aria-hidden="true">
                              <path d="M6 12h12" />
                              <path d="M12 6v12" />
                            </svg>
                          </span>
                          <strong>{row.dimension}</strong>
                        </div>
                      </td>
                      <td>
                        <span className={styles.scorePill}>{row.score}</span>
                      </td>
                      <td>{row.signal}</td>
                      <td>{row.action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </section>
        ) : null}

        {activeView === "insights" ? (
          <section className={styles.sectionBlock} id="insights" data-insights-theme={effectiveTheme}>
            <CandidateInsightsPopup
              variant="inline"
              open
              loading={loading}
              error=""
              candidateName={candidateName}
              payload={liveInsightsPayload}
              onClose={() => undefined}
              showHeader={false}
            />
          </section>
        ) : null}

      </main>

      {isQrModalOpen && activePdfViewUrl ? (
        <div className={styles.qrModalOverlay} onClick={() => setIsQrModalOpen(false)} role="presentation">
          <div
            className={styles.qrModalCard}
            role="dialog"
            aria-modal="true"
            aria-label={copy.qrModalTitle}
            onClick={(event) => event.stopPropagation()}
          >
            <div className={styles.qrModalHeader}>
              <div className={styles.qrModalTitle}>
                <span className={styles.qrCardLabel}>{activeQrLabel}</span>
                <h2>{copy.qrModalTitle}</h2>
                <p>{copy.scanQrToOpen}</p>
              </div>
              <button
                type="button"
                className={styles.qrModalClose}
                onClick={() => setIsQrModalOpen(false)}
                aria-label={copy.closeModal}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6 6 18 18" />
                  <path d="M18 6 6 18" />
                </svg>
              </button>
            </div>
            <div className={styles.qrModalBody}>
              {activeQrImageUrl ? (
                <img className={styles.qrModalImage} src={activeQrImageUrl} alt={copy.scanQrToOpen} loading="lazy" />
              ) : null}
              {qrNeedsPublicOrigin ? <p className={styles.qrHint}>{copy.qrLocalHint}</p> : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
