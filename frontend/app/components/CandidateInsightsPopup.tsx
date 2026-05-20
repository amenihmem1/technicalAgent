"use client";

import { useEffect, useState } from "react";

type InsightsContext = {
  metrics?: Record<string, any>;
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

type InsightsAdviceContext = {
  thank_you?: string;
  summary?: string[];
  strengths?: string[];
  improvement_points?: string[];
  improvements?: string[];
  next_steps?: string[];
  closing?: string;
};

export type CandidateInsightsPayload = {
  response_language?: string;
  visual_context?: InsightsContext | null;
  audio_context?: InsightsContext | null;
  stress_context?: StressContext | null;
  insights_advice?: InsightsAdviceContext | null;
};

type CandidateInsightsPopupProps = {
  open: boolean;
  loading: boolean;
  error: string;
  candidateName: string;
  payload: CandidateInsightsPayload | null;
  onClose: () => void;
  variant?: "modal" | "inline";
  showHeader?: boolean;
};

type InsightsTab = "visual" | "audio" | "emotion" | "advice";

type IconKind =
  | "visual"
  | "audio"
  | "emotion"
  | "object"
  | "presence"
  | "focus"
  | "enthusiasm"
  | "neutrality"
  | "speech"
  | "energy"
  | "pause"
  | "fillers"
  | "spark"
  | "stress"
  | "advice";

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function getStressShortLabel(factor: StressFactor, isEnglish: boolean) {
  const source = String(factor.key || factor.label || "").toLowerCase();
  if (source.includes("visual")) return isEnglish ? "Visual" : "Visuel";
  if (source.includes("vocal") || source.includes("voice")) return isEnglish ? "Vocal" : "Vocal";
  if (source.includes("pause")) return isEnglish ? "Pauses" : "Pauses";
  if (source.includes("filler") || source.includes("hesit")) return isEnglish ? "Fillers" : "Hesitations";
  const label = String(factor.label || "").trim();
  return label ? label.split(/\s+/).slice(0, 2).join(" ") : isEnglish ? "Signal" : "Signal";
}

function getStressSeriesVisual(
  factor: { key?: string; label?: string },
  isEnglish: boolean,
): { icon: IconKind; tone: "visual" | "vocal" | "pauses" | "hesitations"; displayLabel: string } {
  const source = `${String(factor.key || "")} ${String(factor.label || "")}`.toLowerCase();
  if (source.includes("visual")) {
    return { icon: "visual", tone: "visual", displayLabel: isEnglish ? "Visual" : "Visuel" };
  }
  if (source.includes("vocal") || source.includes("voice")) {
    return { icon: "audio", tone: "vocal", displayLabel: "Vocal" };
  }
  if (source.includes("pause")) {
    return { icon: "pause", tone: "pauses", displayLabel: "Pauses" };
  }
  if (source.includes("hesit") || source.includes("filler")) {
    return {
      icon: "fillers",
      tone: "hesitations",
      displayLabel: isEnglish ? "Hesitations" : "Hesitations",
    };
  }
  return {
    icon: "spark",
    tone: "visual",
    displayLabel: getStressShortLabel(factor as StressFactor, isEnglish),
  };
}

function InsightIcon({ kind }: { kind: IconKind }) {
  switch (kind) {
    case "visual":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M2.8 12s3.5-5 9.2-5s9.2 5 9.2 5s-3.5 5-9.2 5s-9.2-5-9.2-5Z" />
          <path d="M12 9.3a2.7 2.7 0 1 0 0 5.4a2.7 2.7 0 0 0 0-5.4Z" />
        </svg>
      );
    case "audio":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 9v6" />
          <path d="M9 6v12" />
          <path d="M13 4v16" />
          <path d="M17 7v10" />
          <path d="M21 9v6" />
        </svg>
      );
    case "emotion":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3.5c4.7 0 7.5 3.5 7.5 8.5s-3 8.5-7.5 8.5S4.5 17 4.5 12s2.8-8.5 7.5-8.5Z" />
          <path d="M9.2 10.6h.01" />
          <path d="M14.8 10.6h.01" />
          <path d="M9.5 15c1.5 1 3.5 1 5 0" />
        </svg>
      );
    case "object":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M6.5 7.5 12 4.5l5.5 3v6L12 16.5l-5.5-3Z" />
          <path d="M6.5 7.5 12 10.5l5.5-3" />
          <path d="M12 10.5v6" />
          <path d="M5 17.5h14" />
        </svg>
      );
    case "presence":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 4.2a3 3 0 1 0 0 6a3 3 0 0 0 0-6Z" />
          <path d="M6.5 19a5.5 5.5 0 0 1 11 0" />
        </svg>
      );
    case "focus":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 9V5h4" />
          <path d="M20 9V5h-4" />
          <path d="M4 15v4h4" />
          <path d="M20 15v4h-4" />
          <path d="M9.5 12h5" />
        </svg>
      );
    case "enthusiasm":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="m12 3l1.8 4.8L19 9.2l-4 3.2l1.4 5.2L12 14.8l-4.4 2.8l1.4-5.2l-4-3.2l5.2-1.4Z" />
        </svg>
      );
    case "neutrality":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3.5c4.6 0 7.5 3.3 7.5 8.5s-3 8.5-7.5 8.5S4.5 17.2 4.5 12S7.4 3.5 12 3.5Z" />
          <path d="M9.3 10.7h.01" />
          <path d="M14.7 10.7h.01" />
          <path d="M9.4 14.8h5.2" />
        </svg>
      );
    case "speech":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 4a3 3 0 0 1 3 3v4a3 3 0 0 1-6 0V7a3 3 0 0 1 3-3Z" />
          <path d="M6.5 10.5a5.5 5.5 0 1 0 11 0" />
          <path d="M12 16v4" />
        </svg>
      );
    case "energy":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M13 2L6 13h4l-1 9l7-11h-4l1-9Z" />
        </svg>
      );
    case "pause":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M8 5v14" />
          <path d="M16 5v14" />
        </svg>
      );
    case "fillers":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3.5c4.8 0 8.5 3.5 8.5 8s-3.7 8-8.5 8c-1.2 0-2.3-.2-3.3-.7L4 20l1.4-4.1A7.7 7.7 0 0 1 3.5 11.5c0-4.5 3.7-8 8.5-8Z" />
          <path d="M8.6 11.6h.01" />
          <path d="M12 11.6h.01" />
          <path d="M15.4 11.6h.01" />
        </svg>
      );
    case "spark":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="m12 2l1.5 4.5L18 8l-4.5 1.5L12 14l-1.5-4.5L6 8l4.5-1.5Z" />
          <path d="m18.5 14l.8 2.2L21.5 17l-2.2.8L18.5 20l-.8-2.2l-2.2-.8l2.2-.8Z" />
        </svg>
      );
    case "stress":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3.8c4.7 0 7.7 3.3 7.7 8.2c0 4.8-3 8.2-7.7 8.2S4.3 16.8 4.3 12c0-4.9 3-8.2 7.7-8.2Z" />
          <path d="M8.4 12.3h2.1l1.3-2.2l1.8 4l1.2-1.8h1.8" />
        </svg>
      );
    case "advice":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 20.2s-6.8-3.9-6.8-10a3.8 3.8 0 0 1 6.8-2.2a3.8 3.8 0 0 1 6.8 2.2c0 6.1-6.8 10-6.8 10Z" />
          <path d="M9.2 11.4h.01" />
          <path d="M14.8 11.4h.01" />
          <path d="M9.6 14.6c1.4 1 3.4 1 4.8 0" />
        </svg>
      );
  }
}

function Gauge({
  label,
  value,
  tone,
  details = [],
}: {
  label: string;
  value: number;
  tone: "neutral" | "engaged" | "tension";
  details?: Array<{ label: string; value: number; note?: string }>;
}) {
  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const targetValue = clampPercent(value);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setProgress(1);
      return;
    }

    let frameId = 0;
    let startTime: number | null = null;
    const duration = 1100;

    const tick = (timestamp: number) => {
      if (startTime == null) {
        startTime = timestamp;
      }
      const nextProgress = Math.min(1, (timestamp - startTime) / duration);
      setProgress(nextProgress);
      if (nextProgress < 1) {
        frameId = window.requestAnimationFrame(tick);
      }
    };

    frameId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frameId);
  }, [targetValue]);

  const animatedValue = clampPercent(targetValue * progress);
  const strokeOffset = circumference - (animatedValue / 100) * circumference;

  return (
    <div className={`candidate-insights-gauge is-${tone}`} tabIndex={details.length ? 0 : -1}>
      <svg viewBox="0 0 88 88" aria-hidden="true">
        <circle className="candidate-insights-gauge-track" cx="44" cy="44" r={radius} />
        <circle
          className="candidate-insights-gauge-progress"
          cx="44"
          cy="44"
          r={radius}
          strokeDasharray={circumference}
          strokeDashoffset={strokeOffset}
        />
      </svg>
      <span className="candidate-insights-gauge-value">{animatedValue}%</span>
      <span className="candidate-insights-gauge-label">{label}</span>
      {details.length ? (
        <div className="candidate-insights-gauge-tooltip" role="tooltip">
          <strong>{label}</strong>
          <div className="candidate-insights-gauge-tooltip-list">
            {details.map((item) => (
              <div key={`${label}-${item.label}`} className="candidate-insights-gauge-tooltip-row">
                <span>{item.label}</span>
                <strong>{clampPercent(item.value)}%</strong>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function formatAnimatedNumber(rawValue: string, progress: number) {
  const usesComma = rawValue.includes(",");
  const normalized = rawValue.replace(",", ".");
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) {
    return rawValue;
  }
  const decimalPart = normalized.split(".")[1];
  const decimals = decimalPart ? decimalPart.length : 0;
  const animatedValue = parsed * progress;
  const formatted = decimals > 0 ? animatedValue.toFixed(decimals) : String(Math.round(animatedValue));
  return usesComma ? formatted.replace(".", ",") : formatted;
}

function buildSmoothCurvePath(points: Array<{ x: number; y: number }>) {
  if (!points.length) return "";
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;

  let path = `M ${points[0].x} ${points[0].y}`;
  for (let index = 0; index < points.length - 1; index += 1) {
    const current = points[index];
    const next = points[index + 1];
    const controlX = (current.x + next.x) / 2;
    path += ` C ${controlX} ${current.y}, ${controlX} ${next.y}, ${next.x} ${next.y}`;
  }
  return path;
}

function AnimatedNumberText({
  text,
  className,
  as = "span",
}: {
  text: string;
  className?: string;
  as?: "span" | "strong";
}) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setProgress(1);
      return;
    }

    let frameId = 0;
    let startTime: number | null = null;
    const duration = 900;

    const tick = (timestamp: number) => {
      if (startTime == null) {
        startTime = timestamp;
      }
      const nextProgress = Math.min(1, (timestamp - startTime) / duration);
      setProgress(nextProgress);
      if (nextProgress < 1) {
        frameId = window.requestAnimationFrame(tick);
      }
    };

    frameId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frameId);
  }, [text]);

  const parts = text.split(/(\d+(?:[.,]\d+)?)/g).filter((part) => part.length > 0);
  const content = parts.map((part, index) => {
    if (/^\d+(?:[.,]\d+)?$/.test(part)) {
      return <span key={`${text}-${index}`}>{formatAnimatedNumber(part, progress)}</span>;
    }
    return <span key={`${text}-${index}`}>{part}</span>;
  });

  if (as === "strong") {
    return <strong className={className}>{content}</strong>;
  }
  return <span className={className}>{content}</span>;
}

function buildAudioWavePoints(baseValue: number) {
  const normalized = Math.max(18, Math.min(82, baseValue));
  const offsets = [0, 10, -6, 14, -10, -2, 12, -4, 8];
  return offsets.map((offset, index) => {
    const x = 6 + (index / (offsets.length - 1)) * 88;
    const y = Math.max(16, Math.min(60, 44 - ((normalized - 50) * 0.22 + offset)));
    return { x, y };
  });
}

function buildWavePath(points: Array<{ x: number; y: number }>) {
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
}

function AudioMiniCard({
  label,
  value,
  meta,
  tone,
  trendValue,
  icon,
}: {
  label: string;
  value: string;
  meta: string;
  tone: "green" | "purple" | "pink" | "gold";
  trendValue: number;
  icon: Exclude<IconKind, "visual" | "audio" | "emotion" | "spark">;
}) {
  const wavePath = buildWavePath(buildAudioWavePoints(trendValue));

  return (
    <article className={`candidate-insights-audio-mini-card is-${tone}`}>
      <div className="candidate-insights-audio-mini-top">
        <div className="candidate-insights-audio-mini-head">
          <span className="candidate-insights-audio-mini-icon" aria-hidden="true">
            <InsightIcon kind={icon} />
          </span>
          <span className="candidate-insights-audio-mini-label">{label}</span>
        </div>
        <div className="candidate-insights-audio-mini-wave" aria-hidden="true">
          <svg viewBox="0 0 100 64" preserveAspectRatio="none">
            <path d={wavePath} className="candidate-insights-audio-mini-wave-line" />
          </svg>
        </div>
      </div>
      <div className="candidate-insights-audio-mini-bottom">
        <AnimatedNumberText text={value} className="candidate-insights-audio-mini-value" as="strong" />
        <AnimatedNumberText text={meta} className="candidate-insights-audio-mini-meta" />
      </div>
    </article>
  );
}

function MetricCard({
  label,
  value,
  meta,
  icon,
  tone = "default",
}: {
  label: string;
  value: string;
  meta: string;
  icon: Exclude<IconKind, "visual" | "audio" | "emotion" | "spark">;
  tone?: "default" | "warm" | "cool";
}) {
  return (
    <article className={`candidate-insights-metric-card is-${tone}`}>
      <div className="candidate-insights-metric-head">
        <span className="candidate-insights-metric-icon" aria-hidden="true">
          <InsightIcon kind={icon} />
        </span>
        <span className="candidate-insights-metric-label">{label}</span>
      </div>
      <AnimatedNumberText text={value} className="candidate-insights-metric-value" as="strong" />
      <AnimatedNumberText text={meta} className="candidate-insights-metric-meta" />
    </article>
  );
}

function formatFlag(flag: string, isEnglish: boolean) {
  const labels: Record<string, [string, string]> = {
    analyse_visuelle_insuffisante: ["Visual sample is limited", "Echantillonnage visuel limite"],
    faible_expressivite: ["Low expressiveness", "Expressivite faible"],
    engagement_visuel_irregulier: ["Uneven visual engagement", "Engagement visuel inegal"],
    analyse_visuelle_peu_fiable: ["Visual reliability reduced", "Fiabilite visuelle reduite"],
    tension_apparente_moderee: ["Moderate apparent tension", "Tension apparente moderee"],
    tension_apparente_legere: ["Light apparent tension", "Tension apparente legere"],
    expressivite_positive: ["Positive expressiveness", "Expressivite positive"],
    enthousiasme_visuel_positif: ["Positive visual enthusiasm", "Enthousiasme visuel positif"],
    enthousiasme_visuel_mesure: ["Measured visual enthusiasm", "Enthousiasme visuel mesure"],
    presence_professionnelle_stable: ["Stable professional presence", "Presence professionnelle stable"],
    sobriete_visuelle_mais_motivation_a_croiser: ["Reserved visual style", "Sobriete visuelle a croiser"],
    analyse_vocale_insuffisante: ["Audio sample is limited", "Echantillonnage vocal limite"],
    debit_rapide: ["Fast speech pace", "Debit rapide"],
    debit_mesure: ["Measured speech pace", "Debit mesure"],
    pauses_marquees: ["Marked pauses", "Pauses marquees"],
    hesitations_verbales: ["Verbal hesitations", "Hesitations verbales"],
    energie_vocale_limitee: ["Contained vocal energy", "Energie vocale contenue"],
    delivery_vocal_stable: ["Stable vocal delivery", "Delivery vocale stable"],
    enthousiasme_vocal_soutenu: ["Sustained vocal enthusiasm", "Enthousiasme vocal soutenu"],
    enthousiasme_vocal_mesure: ["Measured vocal enthusiasm", "Enthousiasme vocal mesure"],
    tension_vocale_apparente: ["Apparent vocal tension", "Tension vocale apparente"],
  };

  const pair = labels[flag];
  if (pair) {
    return isEnglish ? pair[0] : pair[1];
  }
  return flag.split("_").join(" ");
}

function formatHesitationLevel(level: string, isEnglish: boolean) {
  const normalized = String(level || "").trim().toLowerCase();
  if (normalized === "noticeable") {
    return isEnglish ? "noticeable" : "marquees";
  }
  if (normalized === "moderate") {
    return isEnglish ? "moderate" : "moderees";
  }
  if (normalized === "light") {
    return isEnglish ? "light" : "legeres";
  }
  return isEnglish ? "low" : "faibles";
}

function normalizeTextList(items?: string[]) {
  return Array.isArray(items) ? items.map((item) => String(item || "").trim()).filter(Boolean) : [];
}

function getEmotionEmoji(key: string) {
  switch (key) {
    case "happy":
      return "\u{1F60A}";
    case "neutral":
      return "\u{1F610}";
    case "angry":
      return "\u{1F620}";
    case "sad":
      return "\u{1F614}";
    case "surprise":
      return "\u{1F632}";
    default:
      return "";
  }
}

function pickTopItems(items: string[]): string[] {
  const seen = new Set<string>();
  const picked: string[] = [];
  for (const item of items) {
    const value = String(item || "").trim();
    if (!value || seen.has(value)) continue;
    seen.add(value);
    picked.push(value);
    if (picked.length >= 3) break;
  }
  return picked;
}

function buildAdviceContent({
  isEnglish,
  candidateName,
  insightsAdvice,
}: {
  isEnglish: boolean;
  candidateName: string;
  insightsAdvice: InsightsAdviceContext | null | undefined;
}) {
  const llmThankYou = String(insightsAdvice?.thank_you || "").trim();
  const llmSummary = normalizeTextList(insightsAdvice?.summary);
  const llmStrengths = normalizeTextList(insightsAdvice?.strengths);
  const llmImprovements = normalizeTextList(insightsAdvice?.improvements);
  const llmNextSteps = normalizeTextList(insightsAdvice?.next_steps);
  const llmClosing = String(insightsAdvice?.closing || "").trim();
  const llmImprovementItems = llmImprovements.length
    ? llmImprovements
    : normalizeTextList(insightsAdvice?.improvement_points);
  const hasLlmAdvice = Boolean(
    llmThankYou ||
      llmSummary.length ||
      llmStrengths.length ||
      llmImprovementItems.length ||
      llmNextSteps.length ||
      llmClosing,
  );

  return {
    available: hasLlmAdvice,
    unavailableMessage: isEnglish
      ? "LLM coaching advice is unavailable for this session."
      : "Les conseils LLM sont indisponibles pour cette session.",
    thankYou: llmThankYou,
    summary: pickTopItems(llmSummary),
    strengths: pickTopItems(llmStrengths),
    improvements: pickTopItems(llmImprovementItems),
    nextSteps: pickTopItems(llmNextSteps),
    closing: llmClosing,
  };
}

export function CandidateInsightsPopup({
  open,
  loading,
  error,
  candidateName,
  payload,
  onClose,
  variant = "modal",
  showHeader = true,
}: CandidateInsightsPopupProps) {
  const [activeTab, setActiveTab] = useState<InsightsTab>("visual");
  const isInline = variant === "inline";

  useEffect(() => {
    if (open || isInline) {
      setActiveTab("visual");
    }
  }, [open, isInline]);

  if (!isInline && !open) {
    return null;
  }

  const isEnglish = (payload?.response_language || "fr").toLowerCase() === "en";
  const visualMetrics = payload?.visual_context?.metrics || {};
  const audioMetrics = payload?.audio_context?.metrics || {};
  const stressContext = payload?.stress_context || {};
  const insightsAdvice = payload?.insights_advice || null;
  const visualFlags = payload?.visual_context?.heuristic_flags || [];
  const audioFlags = payload?.audio_context?.heuristic_flags || [];
  const audioUtteranceCount = Number(audioMetrics?.utterance_count || 0);
  const audioSampleLimited = audioFlags.includes("analyse_vocale_insuffisante") || audioUtteranceCount <= 1;
  const allFlags = [...visualFlags, ...audioFlags].slice(0, 6);
  const providerMetricsMap = visualMetrics?.provider_metrics || {};
  const preferredProviderOrder = ["custom"];
  const providerEntries = [
    ...preferredProviderOrder
      .filter((key) => providerMetricsMap?.[key])
      .map((key) => [key, providerMetricsMap[key]] as const),
    ...Object.entries(providerMetricsMap || {}).filter(([key]) => !preferredProviderOrder.includes(key)),
  ];
  const getProviderLabel = (providerKey: string) => {
    if (providerKey === "custom") return isEnglish ? "Custom model" : "Modele personnalise";
    return providerKey.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  };

  const providerNeutrality = Math.max(
    0,
    ...providerEntries.map(([, metrics]) => Number((metrics as { neutral_pct?: number })?.neutral_pct || 0)),
  );
  const providerTension = Math.max(
    0,
    ...providerEntries.map(([, metrics]) => Number((metrics as { tension_pct?: number })?.tension_pct || 0)),
  );
  const vocalTensionBoost = audioFlags.includes("tension_vocale_apparente") ? 18 : 0;
  const vocalEnthusiasmBoost = audioFlags.includes("enthousiasme_vocal_soutenu")
    ? 12
    : audioFlags.includes("enthousiasme_vocal_mesure")
      ? 6
      : 0;

  const apparentNeutrality = clampPercent(
    Number(visualMetrics?.neutral_pct || 0) * 0.7 + providerNeutrality * 0.3,
  );
  const apparentEngagement = clampPercent(
    Number(visualMetrics?.visual_enthusiasm_pct || 0) * 0.5 +
      Number(audioMetrics?.volume_score_avg || 0) * 0.25 +
      Number(visualMetrics?.engaged_pct || 0) * 0.15 +
      Number(audioMetrics?.pitch_variation_hz_avg || 0) * 0.4 +
      vocalEnthusiasmBoost,
  );
  const apparentTension =
    typeof stressContext?.score === "number"
      ? clampPercent(stressContext.score)
      : clampPercent(providerTension * 0.82 + vocalTensionBoost);
  const stressFactors = (
    Array.isArray(stressContext?.factors) ? stressContext.factors : []
  )
    .filter((factor) => {
      if (!audioSampleLimited) {
        return true;
      }
      const source = `${String(factor?.key || "")} ${String(factor?.label || "")}`.toLowerCase();
      return source.includes("visual");
    })
    .slice(0, 4);
  const stressChartSeries = stressFactors.map((factor) => ({
    key: String(factor.key || factor.label || ""),
    label: String(factor.label || factor.key || "-"),
    shortLabel: getStressShortLabel(factor, isEnglish),
    detail: String(factor.detail || ""),
    value: clampPercent(Number(factor.value || 0)),
    ...getStressSeriesVisual(factor, isEnglish),
  }));
  const stressChartWidth = 384;
  const stressChartHeight = 152;
  const stressChartPaddingX = 24;
  const stressChartPaddingTop = 22;
  const stressChartPaddingBottom = 16;
  const stressChartPlotHeight = stressChartHeight - stressChartPaddingTop - stressChartPaddingBottom;
  const stressChartStep =
    stressChartSeries.length > 1
      ? (stressChartWidth - stressChartPaddingX * 2) / (stressChartSeries.length - 1)
      : 0;
  const stressChartPoints = stressChartSeries.map((factor, index) => ({
    ...factor,
    x: stressChartPaddingX + stressChartStep * index,
    y: stressChartPaddingTop + ((100 - factor.value) / 100) * stressChartPlotHeight,
  }));
  const stressLinePath = buildSmoothCurvePath(stressChartPoints);
  const stressAreaPath = stressChartPoints.length
    ? [
        `M ${stressChartPoints[0].x} ${stressChartHeight - stressChartPaddingBottom}`,
        stressLinePath.replace(/^M [^ ]+ [^ ]+/, `L ${stressChartPoints[0].x} ${stressChartPoints[0].y}`),
        `L ${stressChartPoints[stressChartPoints.length - 1].x} ${stressChartHeight - stressChartPaddingBottom}`,
        "Z",
      ].join(" ")
    : "";
  const lowSilenceSupport = clampPercent(100 - Number(audioMetrics?.silence_pct_avg || 0));
  const pitchVariationSupport = clampPercent(Number(audioMetrics?.pitch_variation_hz_avg || 0) * 2);
  const dominantHesitation = String(audioMetrics?.dominant_hesitation || "").trim().toLowerCase();
  const hesitationBase =
    dominantHesitation === "noticeable"
      ? 24
      : dominantHesitation === "moderate"
        ? 12
        : dominantHesitation === "light"
          ? 4
          : 0;
  const hesitationScore = clampPercent(
    Number(audioMetrics?.silence_pct_avg || 0) * 1.15 +
      Number(audioMetrics?.pause_count_avg || 0) * 4 +
      hesitationBase,
  );
  const hesitationMeta = `${formatHesitationLevel(dominantHesitation, isEnglish)}${
    Number(audioMetrics?.pause_count_avg || 0) > 0
      ? ` · ${Number(audioMetrics?.pause_count_avg || 0)} ${isEnglish ? "avg" : "moy."}`
      : ""
  }`;

  const neutralityDetails = [
    {
      label: isEnglish ? "Visual neutrality" : "Neutralite visuelle",
      value: Number(visualMetrics?.neutral_pct || 0),
    },
    ...providerEntries.slice(0, 2).map(([providerKey, metrics]) => ({
      label: getProviderLabel(providerKey),
      value: Number((metrics as { neutral_pct?: number })?.neutral_pct || 0),
    })),
  ];

  const engagementDetails = [
    {
      label: isEnglish ? "Visual enthusiasm" : "Enthousiasme visuel",
      value: Number(visualMetrics?.visual_enthusiasm_pct || 0),
    },
    ...(audioSampleLimited
      ? []
      : [
          {
            label: isEnglish ? "Vocal energy" : "Energie vocale",
            value: Number(audioMetrics?.volume_score_avg || 0),
          },
          {
            label: isEnglish ? "Low silence" : "Peu de silences",
            value: lowSilenceSupport,
          },
          {
            label: isEnglish ? "Tone variation" : "Variation du ton",
            value: pitchVariationSupport,
          },
        ]),
  ];

  const tensionDetails =
    stressFactors.length > 0
      ? stressFactors.map((factor) => ({
          label: String(factor.label || factor.key || "-"),
          value: Number(factor.value || 0),
          note: String(factor.detail || ""),
        }))
      : [
          ...providerEntries.slice(0, 2).map(([providerKey, metrics]) => ({
            label: `${getProviderLabel(providerKey)} ${isEnglish ? "tension" : "tension"}`,
            value: Number((metrics as { tension_pct?: number })?.tension_pct || 0),
          })),
          {
            label: isEnglish ? "Vocal tension cue" : "Indice vocal",
            value: vocalTensionBoost,
          },
        ];

  const emotionalReading =
    String(stressContext?.summary || "") ||
    (apparentTension >= 55
      ? isEnglish
        ? "Some apparent tension cues emerge and should stay secondary to verbal content."
        : "Quelques signes apparents de tension emergent et doivent rester secondaires au verbal."
      : apparentEngagement >= 60
        ? isEnglish
          ? "Engagement appears positive overall, with visual and vocal energy staying present."
          : "L'engagement parait positif dans l'ensemble, avec une energie visuelle et vocale bien presente."
        : isEnglish
          ? "This remains a secondary signal that should be cross-checked with the candidate's verbal content."
          : "Ce signal reste secondaire et doit etre croise avec le contenu verbal du candidat.");

  const visualSignals = (payload?.visual_context?.signals || []).slice(0, 2);
  const audioSignals = (payload?.audio_context?.signals || []).slice(0, 2);
  const detectedObjects = Array.isArray(visualMetrics?.detected_objects)
    ? visualMetrics.detected_objects
        .map((item: any) => ({
          label: String(item?.label || "").trim(),
          count: Number(item?.count || 0),
          confidence: Number(item?.avg_confidence || 0),
        }))
        .filter((item) => item.label && item.count > 0)
        .slice(0, 6)
    : [];
  const objectTotal = Number(visualMetrics?.detected_object_total || 0);
  const objectSampleCount = Number(visualMetrics?.object_sample_count || 0);
  const rawEmotionBreakdown =
    visualMetrics?.model_emotion_breakdown ||
    visualMetrics?.raw_emotion_breakdown ||
    visualMetrics?.emotion_breakdown ||
    {};
  const rawEmotionBreakdownAvailable = Boolean(
    visualMetrics?.model_emotion_breakdown_available ||
    visualMetrics?.raw_emotion_breakdown_available ||
    visualMetrics?.emotion_breakdown_available,
  );
  const emotionCards = [
    {
      key: "happy",
      emoji: "😊",
      label: "happy",
      raw: rawEmotionBreakdownAvailable ? Number(rawEmotionBreakdown?.happy || 0) : null,
    },
    {
      key: "neutral",
      emoji: "😐",
      label: "neutral",
      raw: rawEmotionBreakdownAvailable ? Number(rawEmotionBreakdown?.neutral || 0) : null,
    },
    {
      key: "angry",
      emoji: "😠",
      label: "angry",
      raw: rawEmotionBreakdownAvailable ? Number(rawEmotionBreakdown?.angry || 0) : null,
    },
    {
      key: "sad",
      emoji: "😔",
      label: "sad",
      raw: rawEmotionBreakdownAvailable ? Number(rawEmotionBreakdown?.sad || 0) : null,
    },
    {
      key: "surprise",
      emoji: "😲",
      label: "surprise",
      raw: rawEmotionBreakdownAvailable ? Number(rawEmotionBreakdown?.surprise || 0) : null,
    },
  ];
  const dominantRawEmotion = rawEmotionBreakdownAvailable
    ? emotionCards.reduce((best, current) => ((current.raw ?? -1) > (best.raw ?? -1) ? current : best))
    : null;
  const overviewPills = [
    {
      label: isEnglish ? "Vocal signals" : "Signaux vocaux",
      value: audioSampleLimited ? (isEnglish ? "limited" : "limites") : String(audioSignals.length),
    },
    {
      label: isEnglish ? "Stress band" : "Niveau de stress",
      value: String(stressContext?.band || (isEnglish ? "secondary" : "secondaire")),
    },
    {
      label: isEnglish ? "Dominant cue" : "Signal dominant",
      value: rawEmotionBreakdownAvailable
        ? `${getEmotionEmoji(String(dominantRawEmotion?.key || ""))} ${String(dominantRawEmotion?.label || "-")}`.trim()
        : (isEnglish ? "Not captured" : "Non capture"),
    },
  ];
  const emotionComparisonNote = isEnglish
    ? rawEmotionBreakdownAvailable
      ? `Dominant emotion: ${dominantRawEmotion?.label}.`
      : "No emotion distribution was captured."
    : rawEmotionBreakdownAvailable
      ? `Emotion dominante : ${dominantRawEmotion?.label}.`
      : "Aucune distribution emotionnelle n'a ete capturee.";

  const visualLead = visualSignals[0] || (isEnglish ? "Visual presence remained stable overall." : "La presence visuelle est restee stable dans l'ensemble.");
  const audioLead =
    audioSignals[0] ||
    (audioSampleLimited
      ? (isEnglish
        ? "No usable vocal metrics were consolidated for this session."
        : "Aucune metrique vocale exploitable n'a pu etre consolidee pour cette session.")
      : (isEnglish
        ? "Vocal delivery stayed readable across the interview."
        : "La lecture vocale est restee lisible sur l'ensemble de l'entretien."));
  const insightsSubtitle = isInline
    ? (isEnglish
      ? `A focused view of visual, vocal, and careful emotional cues for ${candidateName || "the candidate"}.`
      : `Vue dediee aux signaux visuels, vocaux et a la lecture emotionnelle prudente pour ${candidateName || "le candidat"}.`)
    : (isEnglish
      ? "A view of visual, vocal, and careful emotional cues."
      : "Une vue des signaux visuels, vocaux et de la lecture emotionnelle prudente.");
  const showInlineSummary = isInline && !showHeader;
  const showAllSections = showInlineSummary;
  const adviceContent = buildAdviceContent({
    isEnglish,
    candidateName,
    insightsAdvice,
  });
  const content = (
    <section
      className={`candidate-insights-popup ${isInline ? "is-inline" : ""}`}
      role={isInline ? "region" : "dialog"}
      aria-modal={isInline ? undefined : true}
      aria-label={isEnglish ? "Candidate insights dashboard" : "Tableau de bord d'analyse candidat"}
      onClick={isInline ? undefined : (event) => event.stopPropagation()}
    >
        {showHeader ? (
          <header className={`candidate-insights-topbar ${isInline ? "is-inline-hero" : ""}`}>
            <div className={`candidate-insights-title-wrap ${isInline ? "is-inline-hero" : ""}`}>
              <span className="candidate-insights-kicker">{candidateName || "Candidate"}</span>
              <h3 className="candidate-insights-title">
                {isEnglish ? "Live candidate insights" : "Insights live du candidat"}
              </h3>
              <p className="candidate-insights-subtitle">
                {insightsSubtitle}
              </p>
              <div className="candidate-insights-meta-strip" aria-label={isEnglish ? "Insights summary" : "Resume des insights"}>
                {overviewPills.map((item) => (
                  <div key={item.label} className="candidate-insights-meta-pill">
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                  </div>
                ))}
              </div>
              <div className="candidate-insights-tabs" role="tablist" aria-label={isEnglish ? "Insights sections" : "Sections des insights"}>
                <button
                  type="button"
                  className={`candidate-insights-tab ${activeTab === "visual" ? "is-active" : ""}`}
                  role="tab"
                  aria-selected={activeTab === "visual"}
                  onClick={() => setActiveTab("visual")}
                >
                  <span className="candidate-insights-tab-icon" aria-hidden="true">
                    <InsightIcon kind="visual" />
                  </span>
                  {isEnglish ? "Visual dashboard" : "Tableau de bord visuel"}
                </button>
                <button
                  type="button"
                  className={`candidate-insights-tab ${activeTab === "audio" ? "is-active" : ""}`}
                  role="tab"
                  aria-selected={activeTab === "audio"}
                  onClick={() => setActiveTab("audio")}
                >
                  <span className="candidate-insights-tab-icon" aria-hidden="true">
                    <InsightIcon kind="audio" />
                  </span>
                  {isEnglish ? "Vocal dashboard" : "Tableau de bord vocal"}
                </button>
                <button
                  type="button"
                  className={`candidate-insights-tab ${activeTab === "emotion" ? "is-active" : ""}`}
                  role="tab"
                  aria-selected={activeTab === "emotion"}
                  onClick={() => setActiveTab("emotion")}
                >
                  <span className="candidate-insights-tab-icon" aria-hidden="true">
                    <InsightIcon kind="emotion" />
                  </span>
                  {isEnglish ? "Emotional reading" : "Lecture emotionnelle"}
                </button>
                <button
                  type="button"
                  className={`candidate-insights-tab ${activeTab === "advice" ? "is-active" : ""}`}
                  role="tab"
                  aria-selected={activeTab === "advice"}
                  onClick={() => setActiveTab("advice")}
                >
                  <span className="candidate-insights-tab-icon" aria-hidden="true">
                    <InsightIcon kind="advice" />
                  </span>
                  {isEnglish ? "Advice" : "Conseils"}
                </button>
              </div>
            </div>
            {!isInline ? (
              <button type="button" className="candidate-insights-close" onClick={onClose} aria-label="Close insights">
                <span aria-hidden="true">x</span>
              </button>
            ) : null}
          </header>
        ) : null}

        {showInlineSummary ? (
          <div className="candidate-insights-inline-summary">
            <div className="candidate-insights-meta-strip" aria-label={isEnglish ? "Insights summary" : "Resume des insights"}>
              {overviewPills.map((item) => (
                <div key={item.label} className="candidate-insights-meta-pill">
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>
            
          </div>
        ) : null}

        {loading ? (
          <div className="candidate-insights-state is-loading">
            <span className="candidate-insights-loader" aria-hidden="true" />
            <span>{isEnglish ? "Refreshing live dashboard..." : "Actualisation du dashboard live..."}</span>
          </div>
        ) : error ? (
          <div className="candidate-insights-state is-error">{error}</div>
        ) : (
          <div className="candidate-insights-body">
            {showAllSections || activeTab === "visual" ? (
              <section className="candidate-insights-panel is-visual">
                <div className="candidate-insights-panel-head">
                  <div className="candidate-insights-panel-title-row">
                    <span className="candidate-insights-panel-badge" aria-hidden="true">
                      <InsightIcon kind="visual" />
                    </span>
                    <span className="candidate-insights-panel-kicker">
                      {isEnglish ? "Visual dashboard" : "Tableau de bord visuel"}
                    </span>
                  </div>
                  <span className="candidate-insights-confidence">
                    {String(payload?.visual_context?.confidence_note || visualMetrics?.confidence_note || "")}
                  </span>
                </div>

                <div className="candidate-insights-lead is-visual">
                  <span className="candidate-insights-lead-icon" aria-hidden="true">
                    <InsightIcon kind="spark" />
                  </span>
                  <div>
                    <strong>{isEnglish ? " visual read" : "Lecture visuelle"}</strong>
                    <p>{visualLead}</p>
                  </div>
                </div>

                <div className="candidate-insights-visual-summary">
                  <div className="candidate-insights-metrics-grid">
                    <MetricCard
                      label={isEnglish ? "Presence" : "Presence"}
                      value={`${Number(visualMetrics?.face_detected_pct || 0)}%`}
                      meta=""
                      icon="presence"
                      tone="warm"
                    />
                    <MetricCard
                      label="Focus"
                      value={`${Number(visualMetrics?.looking_forward_pct || 0)}%`}
                      meta={
                        isEnglish
                          ? `Framing ${Number(visualMetrics?.centered_pct || 0)}%`
                          : `Cadrage ${Number(visualMetrics?.centered_pct || 0)}%`
                      }
                      icon="focus"
                      tone="cool"
                    />
                    <MetricCard
                      label={isEnglish ? "Enthusiasm" : "Enthousiasme"}
                      value={`${Number(visualMetrics?.visual_enthusiasm_pct || 0)}%`}
                      meta={String(visualMetrics?.visual_enthusiasm_bucket || "-")}
                      icon="enthusiasm"
                      tone="warm"
                    />
                    <MetricCard
                      label={isEnglish ? "Neutrality" : "Neutralite"}
                      value={`${Number(visualMetrics?.neutral_pct || 0)}%`}
                      meta={`${isEnglish ? "Smiles" : "Sourires"}: ${Number(visualMetrics?.smile_count || 0)}`}
                      icon="neutrality"
                      tone="cool"
                    />
                  </div>

                  <div className="candidate-insights-bars">
                    <div className="candidate-insights-bar-row">
                      <span>{isEnglish ? "Stable posture" : "Posture stable"}</span>
                      <strong>{Number(visualMetrics?.stable_posture_pct || 0)}%</strong>
                      <div className="candidate-insights-bar">
                        <span style={{ width: `${clampPercent(Number(visualMetrics?.stable_posture_pct || 0))}%` }} />
                      </div>
                    </div>
                    <div className="candidate-insights-bar-row">
                      <span>{isEnglish ? "Framing" : "Cadrage"}</span>
                      <strong>{Number(visualMetrics?.centered_pct || 0)}%</strong>
                      <div className="candidate-insights-bar">
                        <span style={{ width: `${clampPercent(Number(visualMetrics?.centered_pct || 0))}%` }} />
                      </div>
                    </div>
                    <div className="candidate-insights-bar-row">
                      <span>{isEnglish ? "Smiles" : "Sourires"}</span>
                      <strong>{Number(visualMetrics?.smile_pct || 0)}%</strong>
                      <div className="candidate-insights-bar">
                        <span style={{ width: `${clampPercent(Number(visualMetrics?.smile_pct || 0))}%` }} />
                      </div>
                    </div>
                  </div>
                </div>

                {visualSignals.length ? (
                  <div className="candidate-insights-highlights">
                    {visualSignals.map((signal) => (
                      <span key={signal} className="candidate-insights-highlight-chip">
                        <span className="candidate-insights-chip-icon" aria-hidden="true">
                          <InsightIcon kind="spark" />
                        </span>
                        {signal}
                      </span>
                    ))}
                  </div>
                ) : null}

                <div className="candidate-insights-objects">
                  <div className="candidate-insights-objects-head">
                    <span className="candidate-insights-panel-badge" aria-hidden="true">
                      <InsightIcon kind="object" />
                    </span>
                    <div>
                      <strong>{isEnglish ? "Objects detected" : "Objets detectes"}</strong>
                      <span>
                        {detectedObjects.length
                          ? (isEnglish
                            ? `${objectTotal} total detections across ${objectSampleCount || 1} frames`
                            : `${objectTotal} detections au total sur ${objectSampleCount || 1} images`)
                          : (isEnglish ? "No object detected during the interview" : "Aucun objet detecte pendant l'entretien")}
                      </span>
                    </div>
                  </div>
                  {detectedObjects.length ? (
                    <div className="candidate-insights-object-grid">
                      {detectedObjects.map((item) => (
                        <article className="candidate-insights-object-card" key={item.label}>
                          <span className="candidate-insights-object-icon" aria-hidden="true">
                            <InsightIcon kind="object" />
                          </span>
                          <div>
                            <strong>{item.label}</strong>
                            <span>
                              {isEnglish ? `${item.count} times` : `${item.count} fois`}
                              {item.confidence ? ` · ${clampPercent(item.confidence)}%` : ""}
                            </span>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : null}
                </div>
              </section>
            ) : null}

            {showAllSections || activeTab === "audio" ? (
              <section className="candidate-insights-panel is-audio">
                <div className="candidate-insights-panel-head">
                  <div className="candidate-insights-panel-title-row">
                    <span className="candidate-insights-panel-badge" aria-hidden="true">
                      <InsightIcon kind="audio" />
                    </span>
                    <span className="candidate-insights-panel-kicker">
                      {isEnglish ? "Vocal dashboard" : "Tableau de bord vocal"}
                    </span>
                  </div>
                  <span className="candidate-insights-confidence">
                    {String(payload?.audio_context?.confidence_note || audioMetrics?.confidence_note || "")}
                  </span>
                </div>

                <div className="candidate-insights-lead is-audio">
                  <span className="candidate-insights-lead-icon" aria-hidden="true">
                    <InsightIcon kind="spark" />
                  </span>
                  <div>
                    <strong>{isEnglish ? "vocal read" : "Lecture vocale"}</strong>
                    <p>{audioLead}</p>
                  </div>
                </div>

                {audioSampleLimited ? (
                  <div className="candidate-insights-state">
                    {isEnglish
                      ? "No reliable vocal metrics are available for this session yet. Pace, energy, pauses, and pitch are therefore hidden instead of shown as zeros."
                      : "Aucune metrique vocale fiable n'est disponible pour cette session. Le debit, l'energie, les pauses et le pitch sont donc masques au lieu d'etre affiches a zero."}
                  </div>
                ) : (
                  <>
                    <div className="candidate-insights-audio-metrics-grid">
                      <AudioMiniCard
                        label={isEnglish ? "Speech rate" : "Debit"}
                        value={String(Number(audioMetrics?.speech_rate_wpm_avg || 0))}
                        meta="wpm"
                        tone="green"
                        trendValue={Number(audioMetrics?.speech_rate_wpm_avg || 0) * 0.7}
                        icon="speech"
                      />
                      <AudioMiniCard
                        label={isEnglish ? "Energy" : "Energie"}
                        value={`${Number(audioMetrics?.volume_score_avg || 0)}%`}
                        meta={String(audioMetrics?.dominant_energy || "-")}
                        tone="purple"
                        trendValue={Number(audioMetrics?.volume_score_avg || 0)}
                        icon="energy"
                      />
                      <AudioMiniCard
                        label="Pauses"
                        value={`${Number(audioMetrics?.silence_pct_avg || 0)}%`}
                        meta={`${Number(audioMetrics?.pause_count_avg || 0)} ${isEnglish ? "avg" : "moy."}`}
                        tone="pink"
                        trendValue={100 - Number(audioMetrics?.silence_pct_avg || 0) * 1.8}
                        icon="pause"
                      />
                      <AudioMiniCard
                        label={isEnglish ? "Hesitations" : "Hesitations"}
                        value={`${hesitationScore}%`}
                        meta={hesitationMeta}
                        tone="gold"
                        trendValue={100 - hesitationScore * 0.45}
                        icon="fillers"
                      />
                    </div>

                    <div className="candidate-insights-audio-line">
                      <span>{isEnglish ? "Average pitch" : "Pitch moyen"}</span>
                      <strong>{Number(audioMetrics?.pitch_hz_avg || 0)} Hz</strong>
                    </div>
                  </>
                )}

                {audioSignals.length && !audioSampleLimited ? (
                  <div className="candidate-insights-highlights">
                    {audioSignals.map((signal) => (
                      <span key={signal} className="candidate-insights-highlight-chip">
                        <span className="candidate-insights-chip-icon" aria-hidden="true">
                          <InsightIcon kind="spark" />
                        </span>
                        {signal}
                      </span>
                    ))}
                  </div>
                ) : null}
              </section>
            ) : null}

            {showAllSections || activeTab === "emotion" ? (
              <section className="candidate-insights-panel is-emotion">
                <div className="candidate-insights-panel-head">
                  <div className="candidate-insights-panel-title-row">
                    <span className="candidate-insights-panel-badge" aria-hidden="true">
                      <InsightIcon kind="emotion" />
                    </span>
                    <span className="candidate-insights-panel-kicker">
                      {isEnglish ? "Emotional reading" : "Lecture emotionnelle"}
                    </span>
                  </div>
                  <span className="candidate-insights-panel-note">
                    {isEnglish ? "Secondary cue" : "Signal secondaire"}
                  </span>
                </div>

                <div className="candidate-insights-lead is-emotion">
                  <span className="candidate-insights-lead-icon" aria-hidden="true">
                    <InsightIcon kind="spark" />
                  </span>
                  <div>
                    <strong>{isEnglish ? "Cross-signal reading" : "Lecture croisee"}</strong>
                    <p>{emotionalReading}</p>
                  </div>
                </div>

                <div className="candidate-insights-gauges">
                  <Gauge
                    label={isEnglish ? "Apparent neutrality" : "Neutralite apparente"}
                    value={apparentNeutrality}
                    tone="neutral"
                    details={neutralityDetails}
                  />
                  <Gauge
                    label={isEnglish ? "Apparent engagement" : "Engagement apparent"}
                    value={apparentEngagement}
                    tone="engaged"
                    details={engagementDetails}
                  />
                  <Gauge
                    label={isEnglish ? "Apparent tension" : "Tension apparente"}
                    value={apparentTension}
                    tone="tension"
                    details={tensionDetails}
                  />
                </div>

                <div className="candidate-insights-emotion-layout">
                  <div className="candidate-insights-stress">
                    <div className="candidate-insights-stress-head">
                      <div className="candidate-insights-stress-copy">
                        <span className="candidate-insights-stress-badge" aria-hidden="true">
                          <InsightIcon kind="stress" />
                        </span>
                        <div>
                          <strong>{isEnglish ? "Apparent stress score" : "Score de stress apparent"}</strong>
                          <p>
                            {String(stressContext?.confidence_note || "") ||
                              (isEnglish
                                ? "Built from visual and vocal cues only."
                                : "Construit uniquement a partir des indices visuels et vocaux.")}
                          </p>
                        </div>
                      </div>
                      <div className="candidate-insights-stress-score">
                        <strong>{apparentTension}%</strong>
                        <span>{String(stressContext?.band || (isEnglish ? "secondary" : "secondaire"))}</span>
                      </div>
                    </div>

                    {stressFactors.length ? (
                      <div className="candidate-insights-stress-chart">
                        <div className="candidate-insights-stress-curve">
                          <svg
                            viewBox={`0 0 ${stressChartWidth} ${stressChartHeight}`}
                            className="candidate-insights-stress-curve-svg"
                            aria-hidden="true"
                          >
                            {[0, 25, 50, 75, 100].map((tick) => {
                              const y =
                                stressChartPaddingTop + ((100 - tick) / 100) * stressChartPlotHeight;
                              return (
                                <g key={tick}>
                                  <line
                                    x1={stressChartPaddingX}
                                    y1={y}
                                    x2={stressChartWidth - stressChartPaddingX}
                                    y2={y}
                                    className="candidate-insights-stress-grid-line"
                                  />
                                  <text x={4} y={y + 4} className="candidate-insights-stress-grid-label">
                                    {tick}
                                  </text>
                                </g>
                              );
                            })}
                            {stressChartPoints.map((point) => (
                              <line
                                key={`${point.key}-guide`}
                                x1={point.x}
                                y1={stressChartPaddingTop}
                                x2={point.x}
                                y2={stressChartHeight - stressChartPaddingBottom}
                                className="candidate-insights-stress-grid-guide"
                              />
                            ))}
                            {stressAreaPath ? <path d={stressAreaPath} className="candidate-insights-stress-area" /> : null}
                            {stressLinePath ? <path d={stressLinePath} className="candidate-insights-stress-line" /> : null}
                            {stressChartPoints.map((point) => (
                              <g key={point.key} className="candidate-insights-stress-point-group">
                                <title>{`${point.label}: ${point.value}%`}</title>
                                <line
                                  x1={point.x}
                                  y1={point.y}
                                  x2={point.x}
                                  y2={stressChartHeight - stressChartPaddingBottom}
                                  className="candidate-insights-stress-point-drop"
                                />
                                <rect
                                  x={point.x - 16}
                                  y={Math.max(4, point.y - 28)}
                                  width="32"
                                  height="20"
                                  rx="8"
                                  className="candidate-insights-stress-value-pill"
                                />
                                <text
                                  x={point.x}
                                  y={Math.max(17, point.y - 15)}
                                  className="candidate-insights-stress-value-text"
                                >
                                  {point.value}
                                </text>
                                <circle cx={point.x} cy={point.y} r="4.75" className="candidate-insights-stress-point" />
                              </g>
                            ))}
                          </svg>
                        </div>
                        <div className="candidate-insights-stress-metrics">
                          {stressChartPoints.map((point) => (
                            <div key={`${point.key}-metric`} className={`candidate-insights-stress-metric is-${point.tone}`}>
                              <span className="candidate-insights-stress-metric-icon" aria-hidden="true">
                                <InsightIcon kind={point.icon} />
                              </span>
                              <span className="candidate-insights-stress-metric-label">{point.displayLabel}</span>
                              <strong className="candidate-insights-stress-metric-value">
                                {point.value}
                                <span>/100</span>
                              </strong>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>

                  <div className="candidate-insights-emotions">
                    <article className="candidate-insights-emotion-shell is-summary">
                      <div className="candidate-insights-emotions-head">
                        <strong>{isEnglish ? "Dominant emotion" : "Emotion dominante"}</strong>
                      </div>
                      <div className="candidate-insights-emotion-summary-card">
                        <span className="candidate-insights-emotion-summary-label">
                          {isEnglish ? "Main signal" : "Signal principal"}
                        </span>
                        <strong className="candidate-insights-emotion-summary-value">
                          {rawEmotionBreakdownAvailable
                            ? `${getEmotionEmoji(String(dominantRawEmotion?.key || ""))} ${String(dominantRawEmotion?.label || "-")}`.trim()
                            : "--"}
                        </strong>
                        <span className="candidate-insights-emotion-summary-score">
                          {rawEmotionBreakdownAvailable && dominantRawEmotion?.raw != null
                            ? `${clampPercent(dominantRawEmotion.raw)}%`
                            : "--"}
                        </span>
                        <p className="candidate-insights-emotions-note">{emotionComparisonNote}</p>
                      </div>
                    </article>

                    <article className="candidate-insights-emotion-shell is-breakdown">
                      <div className="candidate-insights-emotions-head">
                        <strong>{isEnglish ? "Emotion scores" : "Scores emotions"}</strong>
                      </div>
                      <div className="candidate-insights-emotion-grid">
                        {emotionCards.map((item) => (
                          <article
                            key={item.key}
                            className={`candidate-insights-emotion-card ${
                              dominantRawEmotion?.key === item.key ? "is-dominant" : ""
                            }`}
                          >
                            <span className="candidate-insights-emotion-emoji" aria-hidden="true">
                              {getEmotionEmoji(item.key) || item.emoji}
                            </span>
                            <span className="candidate-insights-emotion-label">{item.label}</span>
                            <strong className="candidate-insights-emotion-value">
                              {item.raw == null ? "--" : `${clampPercent(item.raw)}%`}
                            </strong>
                          </article>
                        ))}
                      </div>
                    </article>
                  </div>
                </div>

                {allFlags.length ? (
                  <div className="candidate-insights-flags">
                    {allFlags.map((flag) => (
                      <span key={flag} className="candidate-insights-flag">
                        <span className="candidate-insights-chip-icon" aria-hidden="true">
                          <InsightIcon kind="spark" />
                        </span>
                        {formatFlag(flag, isEnglish)}
                      </span>
                    ))}
                  </div>
                ) : null}
              </section>
            ) : null}

            {showAllSections || activeTab === "advice" ? (
              <section className="candidate-insights-panel is-advice">
                <div className="candidate-insights-panel-head">
                  <div className="candidate-insights-panel-title-row">
                    <span className="candidate-insights-panel-badge" aria-hidden="true">
                      <InsightIcon kind="advice" />
                    </span>
                    <span className="candidate-insights-panel-kicker">
                      {isEnglish ? "Advice" : "Conseils"}
                    </span>
                  </div>
                  <span className="candidate-insights-panel-note">
                    {isEnglish ? "Coaching tone" : "Ton coaching"}
                  </span>
                </div>

                {adviceContent.available ? (
                  <>
                    <div className="candidate-insights-advice-hero">
                      <div className="candidate-insights-lead is-advice">
                        <span className="candidate-insights-lead-icon" aria-hidden="true">
                          <InsightIcon kind="advice" />
                        </span>
                        <div>
                          <strong>{isEnglish ? "Thank you note" : "Message de remerciement"}</strong>
                          <p>{adviceContent.thankYou}</p>
                        </div>
                      </div>
                      <div className="candidate-insights-coaching-summary">
                        <span className="candidate-insights-coaching-summary-label">
                          {isEnglish ? "Quick coaching snapshot" : "Synthese coaching"}
                        </span>
                        <div className="candidate-insights-coaching-summary-list">
                          {adviceContent.summary.map((item) => (
                            <span key={item} className="candidate-insights-highlight-chip">
                              <span className="candidate-insights-chip-icon" aria-hidden="true">
                                <InsightIcon kind="spark" />
                              </span>
                              {item}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="candidate-insights-coaching-grid">
                      <article className="candidate-insights-coaching-card is-positive">
                        <div className="candidate-insights-coaching-head">
                          <span className="candidate-insights-coaching-icon" aria-hidden="true">
                            <InsightIcon kind="spark" />
                          </span>
                          <div className="candidate-insights-coaching-title">
                            <span className="candidate-insights-coaching-eyebrow">
                              {isEnglish ? "Strengths" : "Points forts"}
                            </span>
                            <strong>{isEnglish ? "What already works" : "Ce qui fonctionne deja"}</strong>
                          </div>
                          <span className="candidate-insights-coaching-count">{adviceContent.strengths.length}</span>
                        </div>
                        <div className="candidate-insights-coaching-list">
                          {adviceContent.strengths.map((item, index) => (
                            <div key={item} className="candidate-insights-coaching-item">
                              <span className="candidate-insights-coaching-step">{String(index + 1).padStart(2, "0")}</span>
                              <p>{item}</p>
                            </div>
                          ))}
                        </div>
                      </article>

                      <article className="candidate-insights-coaching-card is-gentle">
                        <div className="candidate-insights-coaching-head">
                          <span className="candidate-insights-coaching-icon" aria-hidden="true">
                            <InsightIcon kind="focus" />
                          </span>
                          <div className="candidate-insights-coaching-title">
                            <span className="candidate-insights-coaching-eyebrow">
                              {isEnglish ? "Improvements" : "Ameliorations"}
                            </span>
                            <strong>{isEnglish ? "Soft improvements" : "Axes d'amelioration doux"}</strong>
                          </div>
                          <span className="candidate-insights-coaching-count">{adviceContent.improvements.length}</span>
                        </div>
                        <div className="candidate-insights-coaching-list">
                          {adviceContent.improvements.map((item, index) => (
                            <div key={item} className="candidate-insights-coaching-item">
                              <span className="candidate-insights-coaching-step">{String(index + 1).padStart(2, "0")}</span>
                              <p>{item}</p>
                            </div>
                          ))}
                        </div>
                      </article>

                      <article className="candidate-insights-coaching-card is-next">
                        <div className="candidate-insights-coaching-head">
                          <span className="candidate-insights-coaching-icon" aria-hidden="true">
                            <InsightIcon kind="advice" />
                          </span>
                          <div className="candidate-insights-coaching-title">
                            <span className="candidate-insights-coaching-eyebrow">
                              {isEnglish ? "Next steps" : "Prochaines etapes"}
                            </span>
                            <strong>{isEnglish ? "For the next interview" : "Pour le prochain entretien"}</strong>
                          </div>
                          <span className="candidate-insights-coaching-count">{adviceContent.nextSteps.length}</span>
                        </div>
                        <div className="candidate-insights-coaching-list">
                          {adviceContent.nextSteps.map((item, index) => (
                            <div key={item} className="candidate-insights-coaching-item">
                              <span className="candidate-insights-coaching-step">{String(index + 1).padStart(2, "0")}</span>
                              <p>{item}</p>
                            </div>
                          ))}
                        </div>
                      </article>
                    </div>

                    <div className="candidate-insights-coaching-close">
                      <span className="candidate-insights-coaching-close-icon" aria-hidden="true">
                        <InsightIcon kind="advice" />
                      </span>
                      <div className="candidate-insights-coaching-close-copy">
                        <p>{adviceContent.closing}</p>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="candidate-insights-state">{adviceContent.unavailableMessage}</div>
                )}
              </section>
            ) : null}
          </div>
        )}
    </section>
  );

  if (isInline) {
    return <div className="candidate-insights-inline-shell">{content}</div>;
  }

  return (
    <div className="candidate-insights-overlay" onClick={onClose} role="presentation">
      {content}
    </div>
  );
}
