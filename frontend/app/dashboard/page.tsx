"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { SessionHistoryEntry, SessionHistoryResponse, getSessionHistoryAnchorMs } from "../../lib/sessionHistory";
import styles from "./dashboard.module.css";
import layoutStyles from "../report/[sessionId]/report-dashboard.module.css";
import logoImage from "../../img/logoS-transparent.png";

type Language = "fr" | "en";
type Theme = "light" | "dark";
type RangeDays = 7 | 14 | 30;

type DashboardSessionPayload = {
  final_report?: {
    audio_metrics?: Record<string, number | string | boolean>;
    audio_signals?: string[];
  } | null;
  audio_context?: {
    metrics?: Record<string, number | string | boolean>;
    signals?: string[];
  } | null;
  visual_observations?: VisualObservations | null;
  proctoring_events?: Array<{ reason?: string; message?: string; time?: string; count?: number }>;
};

type VoiceAudioItem = {
  session: SessionHistoryEntry;
  metrics: Record<string, number | string | boolean>;
  signals: string[];
};

type VisualObservations = {
  sample_count?: number;
  smile_count?: number;
  expressions?: Record<string, number>;
  providers?: Record<string, {
    metadata?: {
      raw_emotion?: Record<string, number>;
    };
  }>;
};

type VisualItem = {
  session: SessionHistoryEntry;
  observations: VisualObservations;
};

type EmotionItem = {
  key: "happy" | "neutral" | "surprise" | "sad" | "angry";
  label: string;
  count: number;
  percentage: number;
};

type EmotionLabels = {
  smile: string;
  neutral: string;
  surprise: string;
  sadness: string;
  tension: string;
};

type TimelineItem = {
  date: string;
  interviews: number;
  scored: number;
  average_score: number | null;
};

const copy = {
  fr: {
    mainMenu: "Menu principal",
    sidebarWorkspace: "Espace de travail",
    sidebarReports: "Rapports",
    sidebarTools: "Outils",
    interview: "Interview",
    dashboard: "Analytique",
    technical: "Technique",
    insights: "Insights",
    history: "Historique",
    help: "Help",
    lightMode: "Mode clair",
    darkMode: "Mode sombre",
    launchInterview: "Lancer entretien",
    title: "Dashboard analytique",
    subtitle: "Vue globale sur les entretiens techniques, les scores, l'activite et les signaux vocaux.",
    totalInterviews: "Entretiens",
    completedInterviews: "Entretiens termines",
    averageScore: "Score moyen",
    completionRate: "Taux de completion",
    completed: "termines",
    active: "actifs",
    scored: "scores disponibles",
    alerts: "alertes",
    overview: "Vue analytique",
    scoreDistribution: "Repartition des scores",
    emotions: "Emotions detectees",
    smile: "Sourire",
    neutral: "Neutre",
    surprise: "Surprise",
    sadness: "Tristesse",
    tension: "Tension",
    analyticsReading: "Lecture analytique",
    reviewNeeded: "A surveiller",
    dashboardInsight: "Ces indicateurs donnent une lecture rapide de la qualite des entretiens finalises et des axes a consolider.",
    technicalSignals: "Signaux techniques",
    technicalDimensions: "Dimensions techniques",
    voiceAnalytics: "Analyse vocale",
    voiceSignal: "Signal vocal",
    voiceSamples: "echantillons",
    speechRate: "Debit",
    vocalEnergy: "Energie",
    silence: "Silence",
    pitch: "Pitch",
    pauses: "Pauses",
    voiceNote: "Moyennes consolidees depuis les captures vocales des entretiens finalises.",
    noVoiceData: "Aucune metrique vocale exploitable pour cette periode.",
    activity: "Activite entretiens",
    scoredActivity: "Entretiens scores",
    lastDays: "Periode",
    range7: "7 jours",
    range14: "14 jours",
    range30: "30 jours",
    loading: "Chargement du dashboard technique...",
    unable: "Impossible de charger le dashboard technique.",
    noData: "Aucune session disponible pour le moment.",
    proctoringAlerts: "Alertes surveillance",
    proctoringNote: "Repartition des alertes enregistrees pendant les entretiens (memes types que l'app RH).",
    noProctoringAlerts: "Aucune alerte enregistree",
  },
  en: {
    mainMenu: "Main menu",
    sidebarWorkspace: "Workspace",
    sidebarReports: "Reports",
    sidebarTools: "Tools",
    interview: "Interview",
    dashboard: "Analytics",
    technical: "Technical",
    insights: "Insights",
    history: "History",
    help: "Help",
    lightMode: "Light mode",
    darkMode: "Dark mode",
    launchInterview: "Start interview",
    title: "Technical analytics dashboard",
    subtitle: "Global view of technical interviews, scores, activity, and vocal signals.",
    totalInterviews: "Interviews",
    completedInterviews: "Completed interviews",
    averageScore: "Average score",
    completionRate: "Completion rate",
    completed: "completed",
    active: "active",
    scored: "scores available",
    alerts: "alerts",
    overview: "Analytics overview",
    scoreDistribution: "Score distribution",
    emotions: "Detected emotions",
    smile: "Smile",
    neutral: "Neutral",
    surprise: "Surprise",
    sadness: "Sadness",
    tension: "Tension",
    analyticsReading: "Analytics reading",
    reviewNeeded: "To monitor",
    dashboardInsight: "These indicators give a quick reading of finalized interview quality and areas to improve.",
    technicalSignals: "Technical signals",
    technicalDimensions: "Technical dimensions",
    voiceAnalytics: "Voice analytics",
    voiceSignal: "Voice signal",
    voiceSamples: "samples",
    speechRate: "Pace",
    vocalEnergy: "Energy",
    silence: "Silence",
    pitch: "Pitch",
    pauses: "Pauses",
    voiceNote: "Averages consolidated from captured interview voice metrics.",
    noVoiceData: "No usable voice metrics for this period.",
    activity: "Interview activity",
    scoredActivity: "Scored interviews",
    lastDays: "Range",
    range7: "7 days",
    range14: "14 days",
    range30: "30 days",
    loading: "Loading technical dashboard...",
    unable: "Unable to load technical dashboard.",
    noData: "No sessions available yet.",
    proctoringAlerts: "Proctoring alerts",
    proctoringNote: "Distribution of alerts recorded during interviews (same types as the HR app).",
    noProctoringAlerts: "No recorded alert",
  },
} as const;

function SidebarIcon({ type }: { type: "interview" | "dashboard" | "hire" | "history" | "help" }) {
  if (type === "interview") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 6h10a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3h-6l-4 3v-3H7a3 3 0 0 1-3-3V9a3 3 0 0 1 3-3Z" />
        <path d="M9 11h6" />
        <path d="M9 14h4" />
      </svg>
    );
  }
  if (type === "history") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9 5.5A2.5 2.5 0 0 1 11.5 3h1A2.5 2.5 0 0 1 15 5.5V6h1.5A2.5 2.5 0 0 1 19 8.5v9a2.5 2.5 0 0 1-2.5 2.5h-9A2.5 2.5 0 0 1 5 17.5v-9A2.5 2.5 0 0 1 7.5 6H9Z" />
        <path d="M9 6h6" />
        <path d="M12 10v4" />
        <path d="M10 12h4" />
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

function MetricIcon({ type }: { type: "interviews" | "completed" | "score" | "acceptance" }) {
  if (type === "completed") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 12.5 9.2 17 19 7" />
        <path d="M4.5 5.5h15v13h-15Z" />
      </svg>
    );
  }
  if (type === "score") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3.5 14.8 9l6.1.9-4.4 4.3 1 6.1-5.5-2.9-5.5 2.9 1-6.1L3.1 9l6.1-.9Z" />
      </svg>
    );
  }
  if (type === "acceptance") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4.5 19.5h15" />
        <path d="M6.5 16.5v-5" />
        <path d="M12 16.5v-9" />
        <path d="M17.5 16.5v-12" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 6h10a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V9a3 3 0 0 1 3-3Z" />
      <path d="M8 12h8" />
      <path d="M8 15h5" />
    </svg>
  );
}

function VoiceIcon({ type }: { type: "pace" | "energy" | "silence" | "pitch" }) {
  if (type === "energy") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M13 2 5 13h6l-1 9 8-12h-6Z" />
      </svg>
    );
  }
  if (type === "silence") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 12h2" />
        <path d="M10 7v10" />
        <path d="M14 9v6" />
        <path d="M18 11v2" />
      </svg>
    );
  }
  if (type === "pitch") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 16c2.5 0 2.5-8 5-8s2.5 8 5 8 2.5-8 6-8" />
        <path d="M4 20h16" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 12h3" />
      <path d="M10 12h9" />
      <path d="M7 8h10" />
      <path d="M7 16h10" />
    </svg>
  );
}

const emotionColors: Record<EmotionItem["key"], string> = {
  happy: "#18b8a8",
  neutral: "#8558f2",
  surprise: "#1da6df",
  sad: "#72809a",
  angry: "#e84aa4",
};

function EmotionTooltipIcon({ type }: { type: EmotionItem["key"] }) {
  if (type === "happy") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="8" />
        <path d="M8.5 10h.01" />
        <path d="M15.5 10h.01" />
        <path d="M8.5 14.2c1.8 2 5.2 2 7 0" />
      </svg>
    );
  }
  if (type === "sad") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="8" />
        <path d="M8.5 10h.01" />
        <path d="M15.5 10h.01" />
        <path d="M8.7 16c1.7-1.7 4.9-1.7 6.6 0" />
      </svg>
    );
  }
  if (type === "surprise") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="8" />
        <path d="M8.5 10h.01" />
        <path d="M15.5 10h.01" />
        <circle cx="12" cy="15" r="1.9" />
      </svg>
    );
  }
  if (type === "angry") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="8" />
        <path d="M7.8 9.2 10 10" />
        <path d="M16.2 9.2 14 10" />
        <path d="M9 16h6" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="8" />
      <path d="M8.5 10h.01" />
      <path d="M15.5 10h.01" />
      <path d="M9 15h6" />
    </svg>
  );
}

function clamp(value: number, min = 0, max = 100) {
  return Math.min(max, Math.max(min, value));
}

function pct(value: number, max: number) {
  if (!Number.isFinite(value) || !Number.isFinite(max) || max <= 0) return 0;
  return Math.max(3, Math.min(100, Math.round((value / max) * 100)));
}

function average(values: number[]) {
  const cleanValues = values.filter((value) => Number.isFinite(value));
  return cleanValues.length ? Math.round(cleanValues.reduce((sum, value) => sum + value, 0) / cleanValues.length) : 0;
}

function normalizeSpeechRate(value: number) {
  return clamp(((value - 80) / 80) * 100);
}

function formatShortDate(value: string) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(5);
  return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" });
}

function getSessionTime(session: SessionHistoryEntry) {
  return getSessionHistoryAnchorMs(session);
}

function buildLinePoints(values: Array<number | null>, width = 640, height = 210, padding = 24) {
  const numericValues = values.map((value) => (typeof value === "number" && Number.isFinite(value) ? value : 0));
  const maxValue = Math.max(1, ...numericValues);
  const step = values.length > 1 ? (width - padding * 2) / (values.length - 1) : 0;
  return numericValues.map((value, index) => {
    const x = padding + step * index;
    const y = height - padding - (value / maxValue) * (height - padding * 2);
    return { x, y, value };
  });
}

function smoothLinePath(points: Array<{ x: number; y: number }>) {
  if (!points.length) return "";
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  return points
    .map((point, index) => {
      if (index === 0) return `M ${point.x} ${point.y}`;
      const previous = points[index - 1];
      const controlX = (previous.x + point.x) / 2;
      return `C ${controlX} ${previous.y}, ${controlX} ${point.y}, ${point.x} ${point.y}`;
    })
    .join(" ");
}

function AnimatedNumber({ value, suffix = "" }: { value: number; suffix?: string }) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const target = Number.isFinite(value) ? value : 0;
    const duration = 900;
    const start = performance.now();
    let frameId = 0;
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(Math.round(target * eased));
      if (progress < 1) frameId = window.requestAnimationFrame(tick);
    };

    frameId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frameId);
  }, [value]);

  return <>{displayValue}{suffix}</>;
}

function buildTimeline(sessions: SessionHistoryEntry[], rangeDays: RangeDays): TimelineItem[] {
  const latestTime =
    sessions.reduce((latest, session) => {
      const time = getSessionTime(session);
      return Number.isFinite(time) ? Math.max(latest, time) : latest;
    }, 0) || Date.now();
  const endDate = new Date(latestTime);
  endDate.setHours(23, 59, 59, 999);
  const startDate = new Date(endDate);
  startDate.setDate(startDate.getDate() - (rangeDays - 1));
  startDate.setHours(0, 0, 0, 0);

  const buckets = Array.from({ length: rangeDays }, (_, index) => {
    const date = new Date(startDate);
    date.setDate(startDate.getDate() + index);
    return {
      date: date.toISOString().slice(0, 10),
      interviews: 0,
      scores: [] as number[],
    };
  });
  const bucketByDate = new Map(buckets.map((bucket) => [bucket.date, bucket]));

  sessions.forEach((session) => {
    const time = getSessionTime(session);
    if (!Number.isFinite(time) || time < startDate.getTime() || time > endDate.getTime()) return;
    const date = new Date(time).toISOString().slice(0, 10);
    const bucket = bucketByDate.get(date);
    if (!bucket) return;
    bucket.interviews += 1;
    if (typeof session.score_total === "number") bucket.scores.push(session.score_total);
  });

  return buckets.map((bucket) => ({
    date: bucket.date,
    interviews: bucket.interviews,
    scored: bucket.scores.length,
    average_score: bucket.scores.length ? average(bucket.scores) : null,
  }));
}

function buildVoiceTimeline(audioItems: VoiceAudioItem[], rangeDays: RangeDays) {
  const timeline = buildTimeline(audioItems.map((item) => item.session), rangeDays).map((item) => ({
    ...item,
    samples: 0,
    volume_score_avg: null as number | null,
  }));
  const bucketByDate = new Map(timeline.map((item) => [item.date, { item, volumes: [] as number[] }]));

  audioItems.forEach(({ session, metrics }) => {
    const date = new Date(getSessionTime(session)).toISOString().slice(0, 10);
    const bucket = bucketByDate.get(date);
    if (!bucket) return;
    const volume = Number(metrics.volume_score_avg || 0);
    if (Number.isFinite(volume) && volume > 0) bucket.volumes.push(clamp(volume));
  });

  return timeline.map((item) => {
    const volumes = bucketByDate.get(item.date)?.volumes || [];
    return {
      date: item.date,
      samples: volumes.length,
      volume_score_avg: volumes.length ? average(volumes) : null,
    };
  });
}

function buildScoreDistribution(sessions: SessionHistoryEntry[]) {
  const groups = [
    { label: "0-39", min: 0, max: 39, count: 0 },
    { label: "40-59", min: 40, max: 59, count: 0 },
    { label: "60-79", min: 60, max: 79, count: 0 },
    { label: "80-89", min: 80, max: 89, count: 0 },
    { label: "90-100", min: 90, max: 100, count: 0 },
  ];
  sessions.forEach((session) => {
    if (typeof session.score_total !== "number") return;
    const score = clamp(session.score_total);
    groups.find((group) => score >= group.min && score <= group.max)!.count += 1;
  });
  return groups.map(({ label, count }) => ({ label, count }));
}

function addEmotionValue(target: Record<EmotionItem["key"], number>, rawKey: string, value: number) {
  if (!Number.isFinite(value) || value <= 0) return;
  const key = rawKey.toLowerCase();
  if (key === "happy" || key === "smile" || key === "smiling" || key === "joy") target.happy += value;
  if (key === "neutral" || key === "calm") target.neutral += value;
  if (key === "surprise" || key === "surprised") target.surprise += value;
  if (key === "sad" || key === "sadness") target.sad += value;
  if (key === "angry" || key === "anger" || key === "disgust" || key === "tension") target.angry += value;
}

function buildEmotionDistribution(visualItems: VisualItem[], labels: EmotionLabels): EmotionItem[] {
  const totals: Record<EmotionItem["key"], number> = {
    happy: 0,
    neutral: 0,
    surprise: 0,
    sad: 0,
    angry: 0,
  };

  visualItems.forEach(({ observations }) => {
    Object.values(observations.providers || {}).forEach((provider) => {
      Object.entries(provider.metadata?.raw_emotion || {}).forEach(([key, value]) => {
        addEmotionValue(totals, key, Number(value));
      });
    });

    Object.entries(observations.expressions || {}).forEach(([key, value]) => {
      addEmotionValue(totals, key, Number(value));
    });

    addEmotionValue(totals, "smiling", Number(observations.smile_count || 0));
  });

  const total = Object.values(totals).reduce((sum, value) => sum + value, 0);
  const items: Array<{ key: EmotionItem["key"]; label: string }> = [
    { key: "happy", label: labels.smile },
    { key: "neutral", label: labels.neutral },
    { key: "surprise", label: labels.surprise },
    { key: "sad", label: labels.sadness },
    { key: "angry", label: labels.tension },
  ];

  return items.map((item) => ({
    ...item,
    count: Math.round(totals[item.key]),
    percentage: total > 0 ? Math.round((totals[item.key] / total) * 100) : 0,
  }));
}

function buildConicGradient(items: EmotionItem[]) {
  let cursor = 0;
  const segments = items
    .filter((item) => item.percentage > 0)
    .map((item) => {
      const start = cursor;
      cursor += item.percentage;
      return `${emotionColors[item.key]} ${start}% ${cursor}%`;
    });
  return segments.length
    ? `conic-gradient(${segments.join(", ")})`
    : "conic-gradient(#18b8a8 0% 28%, #8558f2 28% 60%, #1da6df 60% 72%, #72809a 72% 86%, #e84aa4 86% 100%)";
}

type ProctoringDistKey = "visibilitychange" | "blur" | "window_resize" | "devtools" | "multiple_screens" | "other";

type ProctoringDistItem = {
  key: ProctoringDistKey;
  label: string;
  count: number;
  percentage: number;
};

const proctoringColors: Record<ProctoringDistKey, string> = {
  visibilitychange: "#ef4444",
  blur: "#f59e0b",
  window_resize: "#0ea5e9",
  devtools: "#8b5cf6",
  multiple_screens: "#14b8a6",
  other: "#94a3b8",
};

const PROCTORING_ORDER: ProctoringDistKey[] = [
  "visibilitychange",
  "blur",
  "window_resize",
  "devtools",
  "multiple_screens",
  "other",
];

function normalizeProctoringReason(raw: string): ProctoringDistKey {
  const r = raw.trim().toLowerCase();
  if (r === "hidden" || r === "visibilitychange" || r === "visibility_change") return "visibilitychange";
  if (r === "blur") return "blur";
  if (r === "resize" || r === "window_resize" || r === "window-resize" || r === "window resize") return "window_resize";
  if (r === "devtools") return "devtools";
  if (r === "multiple-screens" || r === "multiple_screens" || r === "multiple screens") return "multiple_screens";
  return "other";
}

function buildProctoringAlertDistribution(events: Array<{ reason?: string }>, language: Language): ProctoringDistItem[] {
  const counts: Partial<Record<ProctoringDistKey, number>> = {};
  for (const ev of events) {
    const key = normalizeProctoringReason(String(ev.reason || ""));
    counts[key] = (counts[key] || 0) + 1;
  }
  const total = PROCTORING_ORDER.reduce((sum, key) => sum + (counts[key] || 0), 0);
  if (!total) return [];

  const labelFor = (key: ProctoringDistKey): string => {
    const labels: Record<ProctoringDistKey, { fr: string; en: string }> = {
      visibilitychange: { fr: "Changement d'onglet", en: "Tab change" },
      blur: { fr: "Perte de focus", en: "Focus lost" },
      window_resize: { fr: "Reduction de fenetre", en: "Window resize" },
      devtools: { fr: "DevTools", en: "DevTools" },
      multiple_screens: { fr: "Plusieurs ecrans", en: "Multiple screens" },
      other: { fr: "Autre", en: "Other" },
    };
    return labels[key][language];
  };

  return PROCTORING_ORDER.filter((key) => (counts[key] || 0) > 0).map((key) => ({
    key,
    label: labelFor(key),
    count: counts[key] || 0,
    percentage: Math.round(((counts[key] || 0) / total) * 100),
  }));
}

function buildAlertConicGradient(items: ProctoringDistItem[]) {
  let cursor = 0;
  const segments = items
    .filter((item) => item.percentage > 0)
    .map((item) => {
      const start = cursor;
      cursor += item.percentage;
      return `${proctoringColors[item.key]} ${start}% ${cursor}%`;
    });
  return segments.length ? `conic-gradient(${segments.join(", ")})` : "conic-gradient(#e2e8f0 0% 100%)";
}

export default function DashboardPage() {
  const [language, setLanguage] = useState<Language>("fr");
  const [theme, setTheme] = useState<Theme>("light");
  const [rangeDays, setRangeDays] = useState<RangeDays>(7);
  const [sessions, setSessions] = useState<SessionHistoryEntry[]>([]);
  const [voiceItems, setVoiceItems] = useState<VoiceAudioItem[]>([]);
  const [visualItems, setVisualItems] = useState<VisualItem[]>([]);
  const [hoveredEmotionKey, setHoveredEmotionKey] = useState<EmotionItem["key"] | null>(null);
  const [hoveredProctoringKey, setHoveredProctoringKey] = useState<ProctoringDistKey | null>(null);
  const [proctoringEvents, setProctoringEvents] = useState<Array<{ reason?: string }>>([]);
  const [hoveredActivityIndex, setHoveredActivityIndex] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const t = copy[language];

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedLanguage = window.localStorage.getItem("dashboard-language");
    if (storedLanguage === "fr" || storedLanguage === "en") setLanguage(storedLanguage);
    const storedTheme = window.localStorage.getItem("dashboard-theme") || window.localStorage.getItem("report-dashboard-theme");
    if (storedTheme === "light" || storedTheme === "dark") setTheme(storedTheme);
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") window.localStorage.setItem("dashboard-language", language);
  }, [language]);

  useEffect(() => {
    if (typeof window !== "undefined") window.localStorage.setItem("dashboard-theme", theme);
  }, [theme]);

  useEffect(() => {
    const loadDashboard = async () => {
      setLoading(true);
      setError("");
      setProctoringEvents([]);
      try {
        const res = await fetch("/api/tech/sessions?limit=200", { method: "GET", cache: "no-store" });
        const data = (await res.json()) as SessionHistoryResponse & { error?: string };
        if (!res.ok) {
          setError(data?.error || t.unable);
          return;
        }
        const loadedSessions = Array.isArray(data?.sessions) ? data.sessions : [];
        setSessions(loadedSessions);

        const recentSessions = loadedSessions.slice(0, 60);
        const payloads = await Promise.allSettled(
          recentSessions.map(async (session) => {
            const sessionRes = await fetch(`/api/tech/session/${encodeURIComponent(session.session_id)}?language=${encodeURIComponent(language)}`, {
              method: "GET",
              cache: "no-store",
            });
            if (!sessionRes.ok) return null;
            return { session, payload: (await sessionRes.json()) as DashboardSessionPayload };
          })
        );
        const collectedProctoring: Array<{ reason?: string }> = [];
        for (const result of payloads) {
          if (result.status !== "fulfilled" || !result.value) continue;
          const list = result.value.payload.proctoring_events;
          if (!Array.isArray(list)) continue;
          for (const ev of list) {
            if (ev && typeof ev === "object") collectedProctoring.push({ reason: String((ev as { reason?: string }).reason || "") });
          }
        }
        setProctoringEvents(collectedProctoring);
        const audioItems = payloads
          .filter((result): result is PromiseFulfilledResult<{ session: SessionHistoryEntry; payload: DashboardSessionPayload } | null> => result.status === "fulfilled")
          .map((result) => result.value)
          .filter((item): item is { session: SessionHistoryEntry; payload: DashboardSessionPayload } => Boolean(item))
          .map(({ session, payload }) => {
            const metrics = (payload.final_report?.audio_metrics || payload.audio_context?.metrics || {}) as Record<string, number | string | boolean>;
            const signals = payload.audio_context?.signals || payload.final_report?.audio_signals || [];
            return { session, metrics, signals };
          })
          .filter(({ metrics }) => Object.keys(metrics).length > 0);
        setVoiceItems(audioItems);
        const visualPayloadItems = payloads
          .filter((result): result is PromiseFulfilledResult<{ session: SessionHistoryEntry; payload: DashboardSessionPayload } | null> => result.status === "fulfilled")
          .map((result) => result.value)
          .filter((item): item is { session: SessionHistoryEntry; payload: DashboardSessionPayload } => Boolean(item))
          .map(({ session, payload }) => ({ session, observations: payload.visual_observations || {} }))
          .filter(({ observations }) => Number(observations.sample_count || 0) > 0 || Object.keys(observations.expressions || {}).length > 0);
        setVisualItems(visualPayloadItems);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    };

    void loadDashboard();
  }, [language, t.unable]);

  const stats = useMemo(() => {
    const completed = sessions.filter((session) => session.status === "completed").length;
    const active = sessions.filter((session) => session.status !== "completed").length;
    const scoredSessions = sessions.filter((session) => typeof session.score_total === "number");
    const averageScore = scoredSessions.length ? average(scoredSessions.map((session) => Number(session.score_total))) : null;
    const completionRate = sessions.length ? Math.round((completed / sessions.length) * 100) : 0;
    const alertCount = sessions.reduce((sum, session) => sum + Number(session.proctoring_alerts_count || 0), 0);
    return { completed, active, scored: scoredSessions.length, averageScore, completionRate, alertCount };
  }, [sessions]);

  const scoreDistribution = useMemo(() => buildScoreDistribution(sessions), [sessions]);
  const maxScoreDistribution = useMemo(() => Math.max(1, ...scoreDistribution.map((item) => item.count)), [scoreDistribution]);
  const emotionItems = useMemo(() => buildEmotionDistribution(visualItems, t), [t, visualItems]);
  const emotionGradient = useMemo(() => buildConicGradient(emotionItems), [emotionItems]);
  const activeEmotion = useMemo(
    () => emotionItems.find((item) => item.key === hoveredEmotionKey) || emotionItems.find((item) => item.percentage > 0) || emotionItems[2],
    [emotionItems, hoveredEmotionKey]
  );
  const proctoringItems = useMemo(() => buildProctoringAlertDistribution(proctoringEvents, language), [proctoringEvents, language]);
  const proctoringGradient = useMemo(() => buildAlertConicGradient(proctoringItems), [proctoringItems]);
  const activeProctoring = useMemo(
    () =>
      proctoringItems.find((item) => item.key === hoveredProctoringKey) ||
      proctoringItems.find((item) => item.count > 0) ||
      proctoringItems[0],
    [hoveredProctoringKey, proctoringItems]
  );
  const timelineItems = useMemo(() => buildTimeline(sessions, rangeDays), [rangeDays, sessions]);
  const activityValues = useMemo(() => timelineItems.map((item) => item.scored), [timelineItems]);
  const activityPoints = useMemo(() => buildLinePoints(activityValues), [activityValues]);
  const activitySmoothPath = smoothLinePath(activityPoints);
  const activityAreaPath = activityPoints.length
    ? `${activitySmoothPath} L ${activityPoints[activityPoints.length - 1].x} 210 L ${activityPoints[0].x} 210 Z`
    : "";
  const hoveredActivity =
    hoveredActivityIndex !== null && timelineItems[hoveredActivityIndex] && activityPoints[hoveredActivityIndex]
      ? { item: timelineItems[hoveredActivityIndex], point: activityPoints[hoveredActivityIndex] }
      : null;

  const voiceTimelineItems = useMemo(() => buildVoiceTimeline(voiceItems, rangeDays), [rangeDays, voiceItems]);
  const voiceVolumes = voiceItems.map(({ metrics }) => Number(metrics.volume_score_avg || 0)).filter((value) => Number.isFinite(value) && value > 0);
  const voiceSpeechRates = voiceItems.map(({ metrics }) => Number(metrics.speech_rate_wpm_avg || 0)).filter((value) => Number.isFinite(value) && value > 0);
  const voiceSilences = voiceItems.map(({ metrics }) => Number(metrics.silence_pct_avg || 0)).filter((value) => Number.isFinite(value));
  const voicePitches = voiceItems.map(({ metrics }) => Number(metrics.pitch_variation_hz_avg || metrics.pitch_hz_avg || 0)).filter((value) => Number.isFinite(value) && value > 0);
  const voicePauseRates = voiceItems.map(({ metrics }) => Number(metrics.pause_rate_per_min_avg || metrics.pause_count_avg || 0)).filter((value) => Number.isFinite(value));
  const voiceSummary = {
    samples: voiceItems.length,
    speechRate: average(voiceSpeechRates),
    volume: average(voiceVolumes),
    silence: average(voiceSilences),
    pitch: average(voicePitches),
    pauseRate: voicePauseRates.length
      ? Number((voicePauseRates.reduce((sum, value) => sum + value, 0) / voicePauseRates.length).toFixed(1))
      : 0,
  };
  const voiceYAxisMax = Math.max(20, Math.ceil(Math.max(1, ...voiceTimelineItems.map((item) => item.volume_score_avg || 0)) / 10) * 10);
  const signalRows = [
    { label: t.completedInterviews, count: stats.completed, max: Math.max(1, sessions.length) },
    { label: t.active, count: stats.active, max: Math.max(1, sessions.length) },
    { label: t.scored, count: stats.scored, max: Math.max(1, sessions.length) },
    { label: t.alerts, count: stats.alertCount, max: Math.max(1, stats.alertCount, sessions.length) },
  ];
  return (
    <div
      className={`${layoutStyles.shell} ${theme === "dark" ? layoutStyles.themeDark : layoutStyles.themeLight} ${
        theme === "dark" ? styles.dashboardThemeDark : styles.dashboardThemeLight
      }`}
    >
      <aside className={layoutStyles.sidebar}>
        <div className={layoutStyles.sidebarTop}>
          <Image className={layoutStyles.logoImage} src={logoImage} alt="SUBUL" priority />
        </div>

        <div className={layoutStyles.menuBlock}>
          <p className={layoutStyles.menuTitle}>{t.mainMenu}</p>
          <nav className={layoutStyles.nav}>
            <span className={layoutStyles.navGroupTitle}>{t.sidebarWorkspace}</span>
            <Link className={layoutStyles.navItem} href="/">
              <SidebarIcon type="interview" />
              {t.interview}
            </Link>
            <Link className={`${layoutStyles.navItem} ${layoutStyles.navItemActive}`} href="/dashboard">
              <SidebarIcon type="dashboard" />
              {t.dashboard}
            </Link>
            <span className={layoutStyles.navGroupTitle}>{t.sidebarReports}</span>
            <button type="button" className={`${layoutStyles.navItem} ${layoutStyles.navButton} ${layoutStyles.navItemDisabled}`} disabled>
              <SidebarIcon type="dashboard" />
              {t.technical}
            </button>
            <button type="button" className={`${layoutStyles.navItem} ${layoutStyles.navButton} ${layoutStyles.navItemDisabled}`} disabled>
              <SidebarIcon type="hire" />
              {t.insights}
            </button>
            <span className={layoutStyles.navGroupTitle}>{t.sidebarTools}</span>
            <Link className={layoutStyles.navItem} href="/history">
              <SidebarIcon type="history" />
              {t.history}
            </Link>
            <Link className={layoutStyles.navItem} href="/help">
              <SidebarIcon type="help" />
              {t.help}
            </Link>
          </nav>
        </div>
      </aside>

      <main className={styles.main}>
        <section className={styles.header}>
          <div>
            <h1>{t.title}</h1>
            <p>{t.subtitle}</p>
          </div>
          <div className={styles.headerActions}>
            <Link className={layoutStyles.primaryButton} href="/">
              <SidebarIcon type="interview" />
              {t.launchInterview}
            </Link>
            <div className={styles.themeToggle}>
              <button type="button" className={`${styles.themeButton} ${theme === "light" ? styles.themeButtonActive : ""}`} onClick={() => setTheme("light")} aria-label={t.lightMode}>
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
              <button type="button" className={`${styles.themeButton} ${theme === "dark" ? styles.themeButtonActive : ""}`} onClick={() => setTheme("dark")} aria-label={t.darkMode}>
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4 7 7 0 0 0 20 14.5Z" />
                </svg>
              </button>
            </div>
            <div className={styles.languageToggle}>
              <button type="button" className={`${styles.languageButton} ${language === "fr" ? styles.languageButtonActive : ""}`} onClick={() => setLanguage("fr")}>FR</button>
              <button type="button" className={`${styles.languageButton} ${language === "en" ? styles.languageButtonActive : ""}`} onClick={() => setLanguage("en")}>EN</button>
            </div>
          </div>
        </section>

        {error ? <section className={styles.card}>{error}</section> : null}
        {loading ? <section className={styles.card}>{t.loading}</section> : null}

        {!loading && !error ? (
          sessions.length ? (
            <>
              <section className={styles.kpiGrid}>
                <article className={styles.kpiCard}>
                  <span className={styles.kpiIcon}><MetricIcon type="interviews" /></span>
                  <div>
                    <span>{t.totalInterviews}</span>
                    <strong><AnimatedNumber value={sessions.length} /></strong>
                    <small><AnimatedNumber value={stats.active} /> {t.active}</small>
                  </div>
                </article>
                <article className={styles.kpiCard}>
                  <span className={styles.kpiIcon}><MetricIcon type="completed" /></span>
                  <div>
                    <span>{t.completedInterviews}</span>
                    <strong><AnimatedNumber value={stats.completed} /></strong>
                    <small><AnimatedNumber value={stats.completionRate} suffix="%" /> {t.completed}</small>
                  </div>
                </article>
                <article className={styles.kpiCard}>
                  <span className={styles.kpiIcon}><MetricIcon type="score" /></span>
                  <div>
                    <span>{t.averageScore}</span>
                    <strong>{stats.averageScore !== null ? <><AnimatedNumber value={stats.averageScore} />/100</> : "--"}</strong>
                    <small><AnimatedNumber value={stats.scored} /> {t.scored}</small>
                  </div>
                </article>
                <article className={styles.kpiCard}>
                  <span className={styles.kpiIcon}><MetricIcon type="acceptance" /></span>
                  <div>
                    <span>{t.completionRate}</span>
                    <strong><AnimatedNumber value={stats.completionRate} suffix="%" /></strong>
                    <small><AnimatedNumber value={stats.alertCount} /> {t.alerts}</small>
                  </div>
                </article>
              </section>

              <h2 className={styles.sectionTitle}>{t.overview}</h2>

              <section className={styles.insightGrid}>
                <article className={styles.card}>
                  <div className={styles.cardHead}>
                    <h2>{t.scoreDistribution}</h2>
                    <span className={styles.pill}><AnimatedNumber value={stats.scored} /> {t.scored}</span>
                  </div>
                  <div className={styles.scoreHistogram}>
                    {scoreDistribution.map((item) => (
                      <div className={styles.scoreColumn} key={item.label}>
                        <strong><AnimatedNumber value={item.count} /></strong>
                        <div className={styles.scoreColumnTrack}>
                          <span style={{ height: `${pct(item.count, maxScoreDistribution)}%` }} />
                        </div>
                        <small>{item.label}</small>
                      </div>
                    ))}
                  </div>
                </article>

                <article className={styles.card}>
                  <div className={styles.cardHead}>
                    <h2>{t.analyticsReading}</h2>
                    <span className={styles.pill}>AI</span>
                  </div>
                  <div className={styles.customerDistribution}>
                    <div className={styles.distributionRow}>
                      <div><span>{t.completionRate}</span><strong><AnimatedNumber value={stats.completionRate} suffix="%" /></strong></div>
                      <div className={styles.distributionTrack}><span style={{ width: `${stats.completionRate}%` }} /></div>
                    </div>
                    <div className={styles.distributionRow}>
                      <div><span>{t.averageScore}</span><strong>{stats.averageScore ?? "--"}/100</strong></div>
                      <div className={styles.distributionTrack}><span style={{ width: `${stats.averageScore ?? 0}%` }} /></div>
                    </div>
                    <div className={styles.distributionFooter}>
                      <span>{t.reviewNeeded}</span>
                      <strong><AnimatedNumber value={stats.alertCount} /></strong>
                    </div>
                  </div>
                  <p className={styles.readingText}>{t.dashboardInsight}</p>
                </article>

                <article className={styles.card}>
                  <div className={styles.cardHead}>
                    <h2>{t.technicalSignals}</h2>
                    <span className={styles.pill}>Tech</span>
                  </div>
                  <div className={styles.bars}>
                    {signalRows.map((item) => (
                      <div className={styles.barRow} key={item.label}>
                        <div className={styles.barMeta}>
                          <span>{item.label}</span>
                          <strong><AnimatedNumber value={item.count} /></strong>
                        </div>
                        <div className={styles.barTrack}>
                          <span style={{ width: `${pct(item.count, item.max)}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </article>
              </section>

              <section className={styles.grid}>
                <article className={`${styles.card} ${styles.emotionCard}`}>
                  <div className={styles.cardHead}>
                    <h2>{t.emotions}</h2>
                    <span className={styles.pill}>Vision</span>
                  </div>
                  <div className={styles.donutPanel}>
                    <div className={styles.donutChart} style={{ background: emotionGradient }}>
                      <svg className={styles.donutSvg} viewBox="0 0 120 120" aria-label={t.emotions}>
                        <circle className={styles.donutBase} cx="60" cy="60" r="42" pathLength="100" />
                        {emotionItems.reduce(
                          (segments, item) => {
                            const start = segments.offset;
                            segments.nodes.push(
                              <circle
                                className={styles.donutSegment}
                                cx="60"
                                cy="60"
                                r="42"
                                pathLength="100"
                                stroke={emotionColors[item.key]}
                                strokeDasharray={`${Math.max(item.percentage, 0.2)} ${100 - Math.max(item.percentage, 0.2)}`}
                                strokeDashoffset={-start}
                                onMouseEnter={() => setHoveredEmotionKey(item.key)}
                                onMouseLeave={() => setHoveredEmotionKey(null)}
                                onFocus={() => setHoveredEmotionKey(item.key)}
                                onBlur={() => setHoveredEmotionKey(null)}
                                tabIndex={0}
                                role="img"
                                aria-label={`${item.label} ${item.percentage}%`}
                                key={item.key}
                              />
                            );
                            segments.offset += item.percentage;
                            return segments;
                          },
                          { offset: 0, nodes: [] as ReactNode[] }
                        ).nodes}
                      </svg>
                      <div className={styles.donutCenter}>
                        <strong>{activeEmotion?.percentage ?? 0}%</strong>
                        <span>{activeEmotion?.label || "--"}</span>
                      </div>
                      {hoveredEmotionKey && activeEmotion ? (
                        <div className={styles.emotionTooltip} role="status">
                          <EmotionTooltipIcon type={activeEmotion.key} />
                          <strong>{activeEmotion.percentage}%</strong>
                        </div>
                      ) : null}
                    </div>
                    <div className={styles.donutLegend}>
                      {emotionItems.map((item) => (
                        <div
                          className={styles.donutLegendItem}
                          onMouseEnter={() => setHoveredEmotionKey(item.key)}
                          onMouseLeave={() => setHoveredEmotionKey(null)}
                          onFocus={() => setHoveredEmotionKey(item.key)}
                          onBlur={() => setHoveredEmotionKey(null)}
                          tabIndex={0}
                          key={item.key}
                        >
                          <i style={{ background: emotionColors[item.key] }} />
                          <span>{item.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </article>

                <article className={`${styles.card} ${styles.emotionCard}`}>
                  <div className={styles.cardHead}>
                    <div>
                      <h2>{t.proctoringAlerts}</h2>
                      <p className={styles.cardHeadNote}>{t.proctoringNote}</p>
                    </div>
                    <span className={styles.pill}>Tech</span>
                  </div>
                  <div className={styles.donutPanel}>
                    <div className={styles.donutChart} style={{ background: proctoringGradient }}>
                      {proctoringItems.length ? (
                        <svg className={styles.donutSvg} viewBox="0 0 120 120" aria-label={t.proctoringAlerts}>
                          <circle className={styles.donutBase} cx="60" cy="60" r="42" pathLength="100" />
                          {proctoringItems.reduce(
                            (segments, item) => {
                              const start = segments.offset;
                              segments.nodes.push(
                                <circle
                                  className={styles.donutSegment}
                                  cx="60"
                                  cy="60"
                                  r="42"
                                  pathLength="100"
                                  stroke={proctoringColors[item.key]}
                                  strokeDasharray={`${Math.max(item.percentage, 0.2)} ${100 - Math.max(item.percentage, 0.2)}`}
                                  strokeDashoffset={-start}
                                  onMouseEnter={() => setHoveredProctoringKey(item.key)}
                                  onMouseLeave={() => setHoveredProctoringKey(null)}
                                  onFocus={() => setHoveredProctoringKey(item.key)}
                                  onBlur={() => setHoveredProctoringKey(null)}
                                  tabIndex={0}
                                  role="img"
                                  aria-label={`${item.label} ${item.percentage}%`}
                                  key={item.key}
                                />
                              );
                              segments.offset += item.percentage;
                              return segments;
                            },
                            { offset: 0, nodes: [] as ReactNode[] }
                          ).nodes}
                        </svg>
                      ) : null}
                      <div className={styles.donutCenter}>
                        <strong>{activeProctoring?.percentage ?? 0}%</strong>
                        <span>{activeProctoring?.label || t.noProctoringAlerts}</span>
                      </div>
                    </div>
                    <div className={styles.donutLegend}>
                      {proctoringItems.map((item) => (
                        <div
                          className={styles.donutLegendItem}
                          onMouseEnter={() => setHoveredProctoringKey(item.key)}
                          onMouseLeave={() => setHoveredProctoringKey(null)}
                          onFocus={() => setHoveredProctoringKey(item.key)}
                          onBlur={() => setHoveredProctoringKey(null)}
                          tabIndex={0}
                          key={item.key}
                        >
                          <i style={{ background: proctoringColors[item.key] }} />
                          <span>
                            {item.label} ({item.count})
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </article>
              </section>

              <section className={`${styles.card} ${styles.voiceCard}`}>
                <div className={styles.cardHead}>
                  <div>
                    <h2>{t.voiceAnalytics}</h2>
                    <p>{t.voiceNote}</p>
                  </div>
                  <div className={styles.voiceHeadActions}>
                    <select
                      className={styles.rangeSelect}
                      value={rangeDays}
                      onChange={(event) => setRangeDays(Number(event.target.value) as RangeDays)}
                      aria-label={t.lastDays}
                    >
                      <option value={7}>{t.range7}</option>
                      <option value={14}>{t.range14}</option>
                      <option value={30}>{t.range30}</option>
                    </select>
                    <span className={styles.pill}>
                      {voiceSummary.samples} {t.voiceSamples}
                    </span>
                  </div>
                </div>

                {voiceSummary.samples > 0 ? (
                  <div className={styles.voiceLayout}>
                    <div className={styles.voiceKpis}>
                      <div className={styles.voiceKpi}>
                        <div className={styles.voiceKpiTop}>
                          <span className={styles.voiceKpiIcon}><VoiceIcon type="pace" /></span>
                          <span>{t.speechRate}</span>
                        </div>
                        <strong>{voiceSummary.speechRate ?? "--"}</strong>
                        <small>wpm</small>
                      </div>
                      <div className={styles.voiceKpi}>
                        <div className={styles.voiceKpiTop}>
                          <span className={styles.voiceKpiIcon}><VoiceIcon type="energy" /></span>
                          <span>{t.vocalEnergy}</span>
                        </div>
                        <strong>{voiceSummary.volume ?? "--"}%</strong>
                        <small>{t.voiceSignal}</small>
                      </div>
                      <div className={styles.voiceKpi}>
                        <div className={styles.voiceKpiTop}>
                          <span className={styles.voiceKpiIcon}><VoiceIcon type="silence" /></span>
                          <span>{t.silence}</span>
                        </div>
                        <strong>{voiceSummary.silence ?? "--"}%</strong>
                        <small>{t.pauses} {voiceSummary.pauseRate ?? "--"}/min</small>
                      </div>
                      <div className={styles.voiceKpi}>
                        <div className={styles.voiceKpiTop}>
                          <span className={styles.voiceKpiIcon}><VoiceIcon type="pitch" /></span>
                          <span>{t.pitch}</span>
                        </div>
                        <strong>{voiceSummary.pitch ?? "--"}</strong>
                        <small>Hz</small>
                      </div>
                    </div>

                    <div className={styles.voiceChart}>
                      <div className={styles.voiceBarChart} role="img" aria-label={t.voiceAnalytics}>
                        <div className={styles.voiceYAxis}>
                          {[voiceYAxisMax, Math.round(voiceYAxisMax * 0.75), Math.round(voiceYAxisMax * 0.5), Math.round(voiceYAxisMax * 0.25), 0].map((tick) => (
                            <span key={tick}>{tick}</span>
                          ))}
                        </div>
                        <div
                          className={styles.voicePlot}
                          style={{ "--voice-day-count": voiceTimelineItems.length } as React.CSSProperties}
                        >
                          {[0, 1, 2, 3, 4].map((line) => (
                            <span className={styles.voiceGridLine} style={{ top: `${line * 25}%` }} key={line} />
                          ))}
                          {voiceTimelineItems.map((item, index) => {
                            const value = item.volume_score_avg ?? 0;
                            const height = Math.max(2, Math.min(100, (value / voiceYAxisMax) * 100));
                            return (
                              <div className={styles.voiceBarColumn} key={item.date}>
                                <div className={styles.voiceBarWrap}>
                                  <span className={styles.voiceBarTooltip}>
                                    <strong>{formatShortDate(item.date)}</strong>
                                    {t.vocalEnergy}: {item.volume_score_avg !== null ? `${item.volume_score_avg}%` : "--"}
                                  </span>
                                  <span
                                    className={`${styles.voiceBar} ${styles[`voiceBarTone${(index % 6) + 1}` as keyof typeof styles]}`}
                                    style={{ height: `${height}%` }}
                                  />
                                </div>
                                <small>{formatShortDate(item.date)}</small>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                    <div className={styles.voiceLegend}>
                      <span><i className={styles.voiceLegendVolume} />{t.vocalEnergy}</span>
                      <span><i className={styles.voiceLegendSpeech} />{t.speechRate}: {voiceSummary.speechRate ?? "--"} wpm</span>
                    </div>
                  </div>
                ) : (
                  <div className={styles.voiceEmpty}>{t.noVoiceData}</div>
                )}
              </section>

              <section className={`${styles.card} ${styles.activityCard}`}>
                <div className={styles.cardHead}>
                  <div>
                    <h2>{t.activity}</h2>
                    <p>{t.lastDays}</p>
                  </div>
                  <div className={styles.legendInline}>
                    <select className={styles.rangeSelect} value={rangeDays} onChange={(event) => setRangeDays(Number(event.target.value) as RangeDays)} aria-label={t.lastDays}>
                      <option value={7}>{t.range7}</option>
                      <option value={14}>{t.range14}</option>
                      <option value={30}>{t.range30}</option>
                    </select>
                    <span><i className={styles.dotPrimary} />{t.scoredActivity}</span>
                  </div>
                </div>
                <div className={styles.lineChart} style={{ "--activity-day-count": timelineItems.length } as CSSProperties}>
                  <svg viewBox="0 0 640 250" role="img" aria-label={t.activity}>
                    <defs>
                      <linearGradient id="activityArea" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.22" />
                        <stop offset="100%" stopColor="#d946ef" stopOpacity="0.04" />
                      </linearGradient>
                      <linearGradient id="activityStroke" x1="0" x2="1" y1="0" y2="0">
                        <stop offset="0%" stopColor="#14b8a6" />
                        <stop offset="48%" stopColor="#d946ef" />
                        <stop offset="100%" stopColor="#7c3aed" />
                      </linearGradient>
                    </defs>
                    {[46, 88, 130, 172, 214].map((y) => (
                      <line className={styles.chartGuide} x1="24" x2="616" y1={y} y2={y} key={y} />
                    ))}
                    {activityAreaPath ? <path className={styles.chartArea} d={activityAreaPath} /> : null}
                    <path className={styles.chartLinePrimaryGlow} d={activitySmoothPath} />
                    <path className={styles.chartLinePrimary} d={activitySmoothPath} />
                    {activityPoints.map((point, index) =>
                      activityValues[index] > 0 ? (
                        <g key={`a-${index}`}>
                          <circle
                            className={styles.chartDotPrimary}
                            cx={point.x}
                            cy={point.y}
                            r="7"
                            tabIndex={0}
                            onMouseEnter={() => setHoveredActivityIndex(index)}
                            onMouseLeave={() => setHoveredActivityIndex(null)}
                            onFocus={() => setHoveredActivityIndex(index)}
                            onBlur={() => setHoveredActivityIndex(null)}
                          />
                        </g>
                      ) : null
                    )}
                    {timelineItems.map((item, index) => {
                      const x = activityPoints[index]?.x || 24;
                      return (
                        <g className={styles.chartLabelGroup} key={item.date}>
                          <rect x={x - 23} y="226" width="46" height="20" rx="10" />
                          <text className={styles.chartLabel} x={x} y="240" textAnchor="middle">
                            {formatShortDate(item.date)}
                          </text>
                        </g>
                      );
                    })}
                    {hoveredActivity ? (
                      <g className={styles.chartTooltipSvg} transform={`translate(${hoveredActivity.point.x} ${hoveredActivity.point.y})`}>
                        <rect x="-66" y="-54" width="132" height="42" rx="10" />
                        <text x="0" y="-36" textAnchor="middle">
                          {formatShortDate(hoveredActivity.item.date)}
                        </text>
                        <text x="0" y="-20" textAnchor="middle">
                          {hoveredActivity.item.average_score !== null ? `Score ${hoveredActivity.item.average_score}/100` : "Score --/100"}
                        </text>
                      </g>
                    ) : null}
                  </svg>
                </div>
              </section>
            </>
          ) : (
            <section className={styles.card}>{t.noData}</section>
          )
        ) : null}
      </main>
    </div>
  );
}
