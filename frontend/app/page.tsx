"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useRef, useState } from "react";
import { CandidateTile } from "./components/CandidateTile";
import { ControlPanel } from "./components/ControlPanel";
import { InterviewerVoiceCard } from "./components/InterviewerVoiceCard";
import { InterviewFeedPanel } from "./components/InterviewFeedPanel";
import { MeetingHeader } from "./components/MeetingHeader";
import { createFeedItem, FeedItem, formatElapsed, InterviewerUtterance } from "../lib/interview";
import {
  fetchSession,
  finalizeInterviewSession,
  recordProctoringEvent,
  updatePreferredInputMode,
} from "../lib/techSessionApi";
import {
  buildFeedFromTurns,
  computeElapsedFromTurns,
  createSessionId,
  normalizeInputMode,
  type InputMode,
} from "../lib/sessionRuntime";
import { SessionHistoryResponse } from "../lib/sessionHistory";
import styles from "./report/[sessionId]/report-dashboard.module.css";
import logoImage from "../img/logoS-transparent.png";
type Language = "fr" | "en";
type Theme = "light" | "dark";
type ApiPayload = Record<string, any>;
/** Aligned with ai-agent `useInterviewWarnings` reasons (stored on the session). */
type ProctoringReason =
  | "visibilitychange"
  | "blur"
  | "window_resize"
  | "devtools"
  | "multiple_screens"
  | "screenshot_attempt";
type ProctoringToast = {
  message: string;
  typeLabel: string;
};
type AudioObservationPayload = {
  duration_seconds: number;
  word_count: number;
  filler_count: number;
  speech_rate_wpm: number;
  volume_score: number;
  silence_ratio: number;
  pause_count: number;
  pitch_hz: number;
  pitch_variation_hz: number;
  energy_label: string;
  pace_label: string;
  hesitation_label: string;
};

type BrowserSpeechRecognitionResult = {
  isFinal: boolean;
  0: {
    transcript: string;
  };
};

type BrowserSpeechRecognitionEvent = Event & {
  resultIndex: number;
  results: ArrayLike<BrowserSpeechRecognitionResult>;
};

type BrowserSpeechRecognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: BrowserSpeechRecognitionEvent) => void) | null;
  onerror: ((event: Event & { error?: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

const LIVE_STT_SAMPLE_RATE = 16000;
const LIVE_STT_WORKLET_PATH = "/audio/live-stt-processor.js";
const VOICE_ACTIVITY_START_MIN_RMS = 0.0055;
const VOICE_ACTIVITY_CONTINUE_MIN_RMS = 0.0032;
const VOICE_ACTIVITY_START_MULTIPLIER = 2.4;
const VOICE_ACTIVITY_CONTINUE_MULTIPLIER = 1.4;
const VOICE_ACTIVITY_RESET_MARGIN = 0.0022;
const VOICE_SILENCE_MS = 950;
const VOICE_PREROLL_MS = 500;
const VOICE_MAX_UTTERANCE_MS = 9000;
const MIN_PAUSE_SECONDS = 0.28;

const FILLER_WORDS: Record<Language, string[]> = {
  fr: ["euh", "heu", "hum", "ben", "bah", "genre", "du coup"],
  en: ["uh", "um", "erm", "hmm", "like", "you know", "i mean"],
};
function downsampleTo16k(samples: Float32Array, inputSampleRate: number) {
  if (!samples.length) {
    return new Float32Array(0);
  }
  if (inputSampleRate === LIVE_STT_SAMPLE_RATE) {
    return samples;
  }

  const ratio = inputSampleRate / LIVE_STT_SAMPLE_RATE;
  const outputLength = Math.max(1, Math.round(samples.length / ratio));
  const output = new Float32Array(outputLength);
  let inputIndex = 0;

  for (let outputIndex = 0; outputIndex < outputLength; outputIndex += 1) {
    const nextInputIndex = Math.min(samples.length, Math.round((outputIndex + 1) * ratio));
    let sum = 0;
    let count = 0;

    while (inputIndex < nextInputIndex) {
      sum += samples[inputIndex];
      inputIndex += 1;
      count += 1;
    }

    output[outputIndex] = count > 0 ? sum / count : samples[Math.min(samples.length - 1, inputIndex)] || 0;
  }

  return output;
}

function formatLiveSttErrorDetail(detail: unknown) {
  if (typeof detail !== "string") {
    return "Live STT unavailable";
  }

  const raw = detail.trim();
  if (!raw) {
    return "Live STT unavailable";
  }

  if (raw.toLowerCase().includes("keepalive ping timeout")) {
    return "Microphone stream timed out. Retry the microphone.";
  }

  const dictMatch = raw.match(/'message':\s*'([^']+)'/);
  if (dictMatch?.[1]) {
    return dictMatch[1];
  }

  return raw;
}

function getBrowserSpeechRecognitionCtor() {
  if (typeof window === "undefined") {
    return null;
  }

  const speechApi = (
    window as Window & {
      SpeechRecognition?: new () => BrowserSpeechRecognition;
      webkitSpeechRecognition?: new () => BrowserSpeechRecognition;
    }
  );

  return speechApi.SpeechRecognition || speechApi.webkitSpeechRecognition || null;
}

function normalizeTranscriptToken(token: string) {
  return token.replace(/^[\s.,;:!?()[\]{}"'`]+|[\s.,;:!?()[\]{}"'`]+$/g, "").toLowerCase();
}

function mergeTranscriptText(existing: string, incoming: string) {
  const left = existing.trim().replace(/\s+/g, " ");
  const right = incoming.trim().replace(/\s+/g, " ");

  if (!left) return right;
  if (!right) return left;
  if (right.toLowerCase().startsWith(left.toLowerCase())) return right;
  if (left.toLowerCase().startsWith(right.toLowerCase())) return left;

  const leftWords = left.split(" ");
  const rightWords = right.split(" ");
  const maxOverlap = Math.min(leftWords.length, rightWords.length);

  for (let overlap = maxOverlap; overlap > 0; overlap -= 1) {
    const leftTail = leftWords.slice(-overlap).map(normalizeTranscriptToken);
    const rightHead = rightWords.slice(0, overlap).map(normalizeTranscriptToken);
    if (leftTail.join(" ") && leftTail.join(" ") === rightHead.join(" ")) {
      return [...leftWords, ...rightWords.slice(overlap)].join(" ").trim();
    }
  }

  return `${left} ${right}`.trim();
}

function isUsableTranscript(text: string) {
  const normalized = text.trim();
  if (!normalized || normalized.toLowerCase() === "listening") {
    return false;
  }
  return normalized.split(/\s+/).filter(Boolean).length >= 2;
}

function concatAudioChunks(chunks: Float32Array[]) {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const merged = new Float32Array(totalLength);
  let offset = 0;

  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }

  return merged;
}

function encodeWav(samples: Float32Array, sampleRate: number) {
  const pcm = new Int16Array(samples.length);
  for (let index = 0; index < samples.length; index += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[index] || 0));
    pcm[index] = clamped < 0 ? Math.round(clamped * 0x8000) : Math.round(clamped * 0x7fff);
  }

  const buffer = new ArrayBuffer(44 + pcm.length * 2);
  const view = new DataView(buffer);
  let offset = 0;

  const writeString = (value: string) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
    offset += value.length;
  };

  writeString("RIFF");
  view.setUint32(offset, 36 + pcm.length * 2, true);
  offset += 4;
  writeString("WAVE");
  writeString("fmt ");
  view.setUint32(offset, 16, true);
  offset += 4;
  view.setUint16(offset, 1, true);
  offset += 2;
  view.setUint16(offset, 1, true);
  offset += 2;
  view.setUint32(offset, sampleRate, true);
  offset += 4;
  view.setUint32(offset, sampleRate * 2, true);
  offset += 4;
  view.setUint16(offset, 2, true);
  offset += 2;
  view.setUint16(offset, 16, true);
  offset += 2;
  writeString("data");
  view.setUint32(offset, pcm.length * 2, true);
  offset += 4;

  for (let index = 0; index < pcm.length; index += 1) {
    view.setInt16(offset, pcm[index], true);
    offset += 2;
  }

  return new Blob([buffer], { type: "audio/wav" });
}

function clampNumber(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.min(max, Math.max(min, value));
}

function countTranscriptWords(text: string) {
  const matches = text.match(/[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*/g);
  return matches?.length ?? 0;
}

function countFillerWords(text: string, language: Language) {
  const normalized = ` ${text.toLowerCase().replace(/\s+/g, " ").trim()} `;
  if (!normalized.trim()) {
    return 0;
  }

  return FILLER_WORDS[language].reduce((count, filler) => {
    const escaped = filler.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s+");
    const matches = normalized.match(new RegExp(`(^|\\s)${escaped}(?=\\s|$)`, "g"));
    return count + (matches?.length ?? 0);
  }, 0);
}

function estimatePitchStats(samples: Float32Array, sampleRate: number, activityThreshold: number) {
  if (!samples.length || sampleRate <= 0) {
    return { pitchHz: 0, pitchVariationHz: 0 };
  }

  const frameSize = Math.max(512, Math.round(sampleRate * 0.05));
  const hopSize = Math.max(256, Math.round(sampleRate * 0.025));
  const minLag = Math.max(2, Math.floor(sampleRate / 320));
  const maxLag = Math.max(minLag + 2, Math.floor(sampleRate / 75));
  const pitches: number[] = [];

  for (let start = 0; start + frameSize <= samples.length; start += hopSize) {
    let mean = 0;
    for (let index = 0; index < frameSize; index += 1) {
      mean += samples[start + index] || 0;
    }
    mean /= frameSize;

    const centered = new Float32Array(frameSize);
    let energy = 0;
    for (let index = 0; index < frameSize; index += 1) {
      const value = (samples[start + index] || 0) - mean;
      centered[index] = value;
      energy += value * value;
    }

    const rms = Math.sqrt(energy / frameSize);
    if (rms < activityThreshold) {
      continue;
    }

    let bestLag = 0;
    let bestCorrelation = 0;
    for (let lag = minLag; lag <= maxLag; lag += 1) {
      let correlation = 0;
      for (let index = 0; index < frameSize - lag; index += 1) {
        correlation += centered[index] * centered[index + lag];
      }
      if (correlation > bestCorrelation) {
        bestCorrelation = correlation;
        bestLag = lag;
      }
    }

    if (bestLag <= 0 || energy <= 1e-6) {
      continue;
    }

    const normalizedCorrelation = bestCorrelation / energy;
    if (normalizedCorrelation >= 0.3) {
      pitches.push(sampleRate / bestLag);
    }
  }

  if (!pitches.length) {
    return { pitchHz: 0, pitchVariationHz: 0 };
  }

  const averagePitch = pitches.reduce((sum, pitch) => sum + pitch, 0) / pitches.length;
  const variance =
    pitches.reduce((sum, pitch) => sum + (pitch - averagePitch) * (pitch - averagePitch), 0) / pitches.length;

  return {
    pitchHz: Math.round(averagePitch * 10) / 10,
    pitchVariationHz: Math.round(Math.sqrt(variance) * 10) / 10,
  };
}

function analyzeCapturedUtterance(samples: Float32Array, sampleRate: number, transcript: string, language: Language) {
  const durationSeconds = sampleRate > 0 ? samples.length / sampleRate : 0;
  const wordCount = countTranscriptWords(transcript);
  const fillerCount = countFillerWords(transcript, language);

  if (!samples.length || sampleRate <= 0 || durationSeconds <= 0) {
    return {
      duration_seconds: 0,
      word_count: wordCount,
      filler_count: fillerCount,
      speech_rate_wpm: 0,
      volume_score: 0,
      silence_ratio: 0,
      pause_count: 0,
      pitch_hz: 0,
      pitch_variation_hz: 0,
      energy_label: "",
      pace_label: "",
      hesitation_label: "",
    } satisfies AudioObservationPayload;
  }

  let totalEnergy = 0;
  for (let index = 0; index < samples.length; index += 1) {
    const value = samples[index] || 0;
    totalEnergy += value * value;
  }
  const globalRms = Math.sqrt(totalEnergy / samples.length);

  const frameSize = Math.max(256, Math.round(sampleRate * 0.05));
  const hopSize = Math.max(128, Math.round(sampleRate * 0.02));
  const frameDurationSeconds = hopSize / sampleRate;
  const frameRmsValues: number[] = [];

  for (let start = 0; start < samples.length; start += hopSize) {
    const end = Math.min(samples.length, start + frameSize);
    if (end <= start) {
      continue;
    }
    let frameEnergy = 0;
    for (let index = start; index < end; index += 1) {
      const value = samples[index] || 0;
      frameEnergy += value * value;
    }
    frameRmsValues.push(Math.sqrt(frameEnergy / (end - start)));
  }

  const silenceThreshold = Math.max(VOICE_ACTIVITY_CONTINUE_MIN_RMS, globalRms * 0.35);
  const silentFrames = frameRmsValues.filter((value) => value < silenceThreshold).length;
  const silenceRatio = frameRmsValues.length ? silentFrames / frameRmsValues.length : 0;

  let pauseCount = 0;
  let silentRun = 0;
  for (const frameRms of frameRmsValues) {
    if (frameRms < silenceThreshold) {
      silentRun += 1;
      continue;
    }
    if (silentRun * frameDurationSeconds >= MIN_PAUSE_SECONDS) {
      pauseCount += 1;
    }
    silentRun = 0;
  }
  if (silentRun * frameDurationSeconds >= MIN_PAUSE_SECONDS) {
    pauseCount += 1;
  }

  const speechRateWpm = durationSeconds > 0 ? Math.round(((wordCount * 60) / durationSeconds) * 10) / 10 : 0;
  const volumeScore = Math.round(clampNumber(((globalRms - 0.01) / 0.08) * 100, 0, 100));
  const { pitchHz, pitchVariationHz } = estimatePitchStats(samples, sampleRate, silenceThreshold);
  const fillerDensityPct = wordCount > 0 ? (fillerCount / wordCount) * 100 : 0;

  const energyLabel =
    volumeScore >= 66 ? "elevated" : volumeScore >= 40 ? "steady" : volumeScore > 0 ? "limited" : "";
  const paceLabel = speechRateWpm >= 170 ? "fast" : speechRateWpm > 0 && speechRateWpm <= 105 ? "measured" : "steady";
  const hesitationLabel =
    fillerDensityPct >= 4 || pauseCount >= 6 || silenceRatio >= 0.3
      ? "noticeable"
      : fillerDensityPct >= 1.5 || pauseCount >= 3 || silenceRatio >= 0.18
        ? "moderate"
        : "light";

  return {
    duration_seconds: Math.round(durationSeconds * 100) / 100,
    word_count: wordCount,
    filler_count: fillerCount,
    speech_rate_wpm: speechRateWpm,
    volume_score: volumeScore,
    silence_ratio: Math.round(silenceRatio * 1000) / 1000,
    pause_count: pauseCount,
    pitch_hz: pitchHz,
    pitch_variation_hz: pitchVariationHz,
    energy_label: energyLabel,
    pace_label: paceLabel,
    hesitation_label: hesitationLabel,
  } satisfies AudioObservationPayload;
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

const interviewTranslations = {
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
    history: "Historique",
    help: "Help",
    lightMode: "Clair",
    darkMode: "Sombre",
    interviewTitle: "Interview",
    meetingHeaderTitle: "Assistant d'entretien technique",
    meetingHeaderSubtitle:"Un espace de travail raffine pour lancer les entretiens techniques, suivre chaque echange et finaliser le rapport candidat avec clarte.",
    session: "Session",
    ended: "Terminee",
    running: "En cours",
    active: "Active",
    finalizedByUser: "Finalisee par l'utilisateur",
    interviewStarted: "Entretien demarre",
    waitingLaunch: "En attente de lancement",
    resume: "CV",
    uploaded: "Telecharge",
    notUploaded: "Non telecharge",
    fileSelected: "Fichier selectionne",
    uploadCvToStart: "Telechargez un CV pour commencer",
    report: "Rapport",
    available: "Disponible",
    inProgress: "En cours",
    readyForDownload: "Pret au telechargement",
    generatedAtEnd: "Genere a la fin",
    timer: "Chrono",
    finalDuration: "Duree finale",
    liveInterviewClock: "Entretien en direct",
    startsAtFirstReply: "Demarre a la premiere reponse",
    interviewFeedTitle: "Flux d'entretien",
    interviewFeedSubtitle: "Transcription en direct de la conversation avec la candidate.",
    messageCountSingular: "message",
    messageCountPlural: "messages",
    readyToBegin: "Pret a commencer",
    interviewEndedMessage: "Entretien termine",
    interviewEndedDescription: "La session a ete fermee depuis les controles de la candidate.",
    interviewReadyDescription: "Telechargez un CV, puis envoyez le premier message pour lancer l'entretien.",
    liveTranscriptLabel: "Transcription en direct",
    candidateMessage: "Message candidate",
    interviewEndedPlaceholder: "Entretien termine. Rechargez la page pour demarrer une nouvelle session.",
    voiceModePlaceholder: "Mode micro actif. Les reponses se font uniquement a la voix.",
    interviewDefaultPlaceholder: "Bonjour, je suis prete pour l'entretien.",
    sendingMessage: "Envoi du message",
    sendMessage: "Envoyer le message",
    roleYou: "Vous",
    roleInterviewer: "Interviewer",
    roleSystem: "Systeme",
    controlPanel: "Panneau de controle",
    controlSubtitle: "Telechargez le CV, terminez l'entretien, puis ouvrez le rapport technique.",
    dragResume: "Glissez votre CV ou une image scannee ici pour commencer",
    fileTypes: "PDF, DOC, DOCX, TXT, PNG, JPG ou WEBP",
    browseFiles: "Parcourir",
    noFileSelected: "Aucun fichier selectionne",
    uploadCv: "Telecharger le CV",
    uploading: "Telechargement...",
    cvUploaded: "CV telecharge",
    readyToUpload: "Pret a telecharger",
    waitingForCv: "En attente du CV",
    opening: "Ouverture...",
    openReportDashboard: "Ouvrir le rapport technique",
    footer: "SUBUL | Shaping the Digital Future Together",
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
    history: "History",
    help: "Help",
    lightMode: "Light",
    darkMode: "Dark",
    interviewTitle: "Interview",
    meetingHeaderTitle: "Technical Interview Assistant",
    meetingHeaderSubtitle:
      "A refined workspace to launch technical interviews, follow each exchange, and finalize the candidate report with clarity.",
    session: "Session",
    ended: "Ended",
    running: "Running",
    active: "Active",
    finalizedByUser: "Finalized by user",
    interviewStarted: "Interview started",
    waitingLaunch: "Waiting for launch",
    resume: "Resume",
    uploaded: "Uploaded",
    notUploaded: "Not uploaded",
    fileSelected: "File selected",
    uploadCvToStart: "Upload a CV to start",
    report: "Report",
    available: "Available",
    inProgress: "In progress",
    readyForDownload: "Ready for download",
    generatedAtEnd: "Generated at the end",
    timer: "Timer",
    finalDuration: "Final duration",
    liveInterviewClock: "Live interview clock",
    startsAtFirstReply: "Starts at first reply",
    interviewFeedTitle: "Interview Feed",
    interviewFeedSubtitle: "Live transcript of the conversation with the candidate.",
    messageCountSingular: "message",
    messageCountPlural: "messages",
    readyToBegin: "Ready to begin",
    interviewEndedMessage: "Interview ended",
    interviewEndedDescription: "The session was closed from the candidate controls.",
    interviewReadyDescription: "Upload a resume, then send the first message to launch the interview.",
    liveTranscriptLabel: "Live transcript",
    candidateMessage: "Candidate Message",
    interviewEndedPlaceholder: "Interview ended. Reload the page to start a new session.",
    voiceModePlaceholder: "Microphone mode is active. Responses are voice-only in this workspace.",
    interviewDefaultPlaceholder: "Hello, I am ready for the interview.",
    sendingMessage: "Sending message",
    sendMessage: "Send message",
    roleYou: "You",
    roleInterviewer: "Interviewer",
    roleSystem: "System",
    controlPanel: "Control panel",
    controlSubtitle: "Upload the CV, complete the interview, then open the technical report.",
    dragResume: "Drag your resume or a scanned image here to begin",
    fileTypes: "PDF, DOC, DOCX, TXT, PNG, JPG or WEBP",
    browseFiles: "Browse files",
    noFileSelected: "No file selected",
    uploadCv: "Upload CV",
    uploading: "Uploading...",
    cvUploaded: "CV uploaded",
    readyToUpload: "Ready to upload",
    waitingForCv: "Waiting for CV",
    opening: "Opening...",
    openReportDashboard: "Open Technical Report",
    footer: "SUBUL | Shaping the Digital Future Together",
  },
} as const;

async function readApiPayload(res: Response): Promise<ApiPayload> {
  const raw = await res.text();
  if (!raw.trim()) {
    return {};
  }

  try {
    return JSON.parse(raw) as ApiPayload;
  } catch {
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("text/html") || raw.trimStart().startsWith("<!DOCTYPE")) {
      return {
        error: res.ok
          ? "The server returned an HTML page instead of JSON."
          : `API route unavailable or failed (${res.status}).`,
      };
    }

    return { error: raw };
  }
}

function getProctoringReasonLabel(reason: ProctoringReason, language: Language) {
  const labels: Record<ProctoringReason, { fr: string; en: string }> = {
    visibilitychange: {
      fr: "changement d'onglet",
      en: "tab change",
    },
    blur: {
      fr: "perte de focus",
      en: "window focus lost",
    },
    window_resize: {
      fr: "reduction de fenetre",
      en: "window resize",
    },
    devtools: {
      fr: "ouverture probable des DevTools",
      en: "probable DevTools opening",
    },
    multiple_screens: {
      fr: "plusieurs ecrans",
      en: "multiple screens",
    },
    screenshot_attempt: {
      fr: "tentative de capture",
      en: "screenshot attempt",
    },
  };

  return labels[reason][language];
}

function hasDevToolsLikeGap() {
  if (typeof window === "undefined") {
    return false;
  }

  const widthGap = Math.max(0, window.outerWidth - window.innerWidth);
  const heightGap = Math.max(0, window.outerHeight - window.innerHeight);
  return widthGap > 180 || heightGap > 180;
}

function isWindowReduced() {
  if (typeof window === "undefined") {
    return false;
  }

  const screenWidth = window.screen?.availWidth || window.screen?.width || 0;
  const screenHeight = window.screen?.availHeight || window.screen?.height || 0;
  if (!screenWidth || !screenHeight) {
    return false;
  }

  return window.outerWidth < screenWidth * 0.82 || window.outerHeight < screenHeight * 0.82;
}

function hasMultipleScreensSignal() {
  if (typeof window === "undefined") {
    return false;
  }

  const screenWithExtension = window.screen as Screen & { isExtended?: boolean };
  if (screenWithExtension.isExtended === true) {
    return true;
  }

  const screenWidth = window.screen?.availWidth || window.screen?.width || 0;
  const screenHeight = window.screen?.availHeight || window.screen?.height || 0;
  const screenLeft = window.screenLeft ?? window.screenX ?? 0;
  const screenTop = window.screenTop ?? window.screenY ?? 0;

  return Boolean(
    screenWidth &&
      screenHeight &&
      (screenLeft < -40 || screenTop < -40 || screenLeft > screenWidth + 40 || screenTop > screenHeight + 40)
  );
}

function HomePageContent() {
  const router = useRouter();
  const [proctoringToast, setProctoringToast] = useState<ProctoringToast | null>(null);
  const [captureShieldVisible, setCaptureShieldVisible] = useState(false);
  const searchParams = useSearchParams();
  const [language, setLanguage] = useState<Language>("fr");
  const [theme, setTheme] = useState<Theme>("light");
  const [sessionId, setSessionId] = useState(() => createSessionId());
  const [candidateName, setCandidateName] = useState("Candidate");
  const [candidateText, setCandidateText] = useState("");
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [persistedCvLabel, setPersistedCvLabel] = useState("");
  const [cvUploaded, setCvUploaded] = useState(false);
  const [loadingCv, setLoadingCv] = useState(false);
  const [downloadingReport, setDownloadingReport] = useState(false);
  const [sending, setSending] = useState(false);
  const [inputMode, setInputMode] = useState<InputMode>("voice");
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [cameraOn, setCameraOn] = useState(false);
  const [micListening, setMicListening] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [interviewerSpeaking, setInterviewerSpeaking] = useState(false);
  const [interviewerUtterance, setInterviewerUtterance] = useState<InterviewerUtterance | null>(null);
  const [finalReportReady, setFinalReportReady] = useState(false);
  const [interviewEnded, setInterviewEnded] = useState(false);
  const [interviewStartedAt, setInterviewStartedAt] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);
  const feedEndRef = useRef<HTMLDivElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const liveTranscriptRef = useRef("");
  const sendingRef = useRef(false);
  const micSocketRef = useRef<WebSocket | null>(null);
  const micAudioContextRef = useRef<AudioContext | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaRecorderChunksRef = useRef<Blob[]>([]);
  const mediaRecorderMimeTypeRef = useRef("audio/webm");
  const micWorkletNodeRef = useRef<AudioWorkletNode | null>(null);
  const micProcessorNodeRef = useRef<ScriptProcessorNode | null>(null);
  const micSourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const micSinkNodeRef = useRef<GainNode | null>(null);
  const micClosingRef = useRef(false);
  const micMuteRef = useRef(false);
  const micSpeechTimerRef = useRef<number | null>(null);
  const micFinalizeUtteranceRef = useRef<(() => Promise<void>) | null>(null);
  const micRollingChunksRef = useRef<Array<{ samples: Float32Array; at: number }>>([]);
  const micUtteranceChunksRef = useRef<Array<{ samples: Float32Array; at: number }>>([]);
  const micUtteranceActiveRef = useRef(false);
  const micUtteranceStartedAtRef = useRef<number | null>(null);
  const micNoiseFloorRef = useRef(0.002);
  const browserSpeechRecognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const browserSpeechTranscriptRef = useRef("");
  const pendingVisibleProctoringToastRef = useRef<ProctoringToast | null>(null);
  const browserSpeechInterimRef = useRef("");
  const liveFinalBufferRef = useRef("");
  const liveSubmitTimerRef = useRef<number | null>(null);
  const micKeepAliveTimerRef = useRef<number | null>(null);
  const lastMicChunkSentAtRef = useRef(0);
  const focusViolationCountRef = useRef(0);
  const lastFocusViolationAtRef = useRef(0);
  const captureShieldTimerRef = useRef<number | null>(null);
  const lastProctoringByReasonRef = useRef<Partial<Record<ProctoringReason, number>>>({});

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
    micMuteRef.current = sending || interviewerSpeaking;
    if (sending || interviewerSpeaking) {
      resetLiveAutoSubmitState();
      if (micSpeechTimerRef.current !== null && typeof window !== "undefined") {
        window.clearTimeout(micSpeechTimerRef.current);
        micSpeechTimerRef.current = null;
      }
      micUtteranceActiveRef.current = false;
      micUtteranceChunksRef.current = [];
      clearLiveTranscript();
    }
  }, [sending, interviewerSpeaking]);

  useEffect(() => {
    sendingRef.current = sending;
  }, [sending]);

  const showProctoringToast = (toast: ProctoringToast) => {
    setProctoringToast(toast);
  };

  const pushFeed = (role: FeedItem["role"], text: string) => {
    setFeed((prev) => [...prev.slice(-59), createFeedItem(role, text)]);
  };

  useEffect(() => {
    const interviewActive =
      interviewStartedAt !== null && !interviewEnded && !finalReportReady;
    if (!interviewActive || typeof window === "undefined") {
      return;
    }

    const showCaptureShield = () => {
      setCaptureShieldVisible(true);
      if (captureShieldTimerRef.current !== null) {
        window.clearTimeout(captureShieldTimerRef.current);
      }
      captureShieldTimerRef.current = window.setTimeout(() => {
        setCaptureShieldVisible(false);
        captureShieldTimerRef.current = null;
      }, 1800);
    };

    const reportProctoringViolation = (reason: ProctoringReason) => {
      const now = Date.now();
      const lastForReason = lastProctoringByReasonRef.current[reason] || 0;

      if (now - lastForReason < 5000 || now - lastFocusViolationAtRef.current < 900) {
        return;
      }

      lastFocusViolationAtRef.current = now;
      lastProctoringByReasonRef.current[reason] = now;
      focusViolationCountRef.current += 1;

      const count = focusViolationCountRef.current;
      const reasonLabel = getProctoringReasonLabel(reason, language);
      const message =
        language === "fr"
          ? `Alerte surveillance ${count}: ${reasonLabel} detecte pendant l'entretien.`
          : `Proctoring alert ${count}: ${reasonLabel} detected during the interview.`;
      const toast = { message, typeLabel: reasonLabel };

      showProctoringToast(toast);
      if (document.hidden) {
        pendingVisibleProctoringToastRef.current = toast;
      }

      void recordProctoringEvent(sessionId, {
        reason,
        message,
        count,
        time: new Date(now).toISOString(),
      }).catch((error) => {
        console.warn("Proctoring alert persistence failed", error);
      });
    };

    const inspectWindowState = () => {
      if (hasDevToolsLikeGap()) {
        reportProctoringViolation("devtools");
        return;
      }

      if (isWindowReduced()) {
        reportProctoringViolation("window_resize");
      }
    };

    const inspectScreenState = () => {
      if (hasMultipleScreensSignal()) {
        reportProctoringViolation("multiple_screens");
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden) {
        reportProctoringViolation("visibilitychange");
        return;
      }

      if (pendingVisibleProctoringToastRef.current) {
        showProctoringToast(pendingVisibleProctoringToastRef.current);
        pendingVisibleProctoringToastRef.current = null;
      }
    };

    const handleWindowBlur = () => {
      showCaptureShield();
      reportProctoringViolation("blur");
    };

    const handleWindowResize = () => {
      inspectWindowState();
      inspectScreenState();
    };

    const handleWindowFocus = () => {
      inspectWindowState();
      inspectScreenState();
    };

    const handleCaptureBlocked = (event: Event) => {
      event.preventDefault();
      event.stopPropagation();
      showCaptureShield();
      reportProctoringViolation("screenshot_attempt");
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase();
      const isPrintScreen = event.key === "PrintScreen" || event.code === "PrintScreen";
      const isPrintShortcut = (event.ctrlKey || event.metaKey) && key === "p";
      const isSaveShortcut = (event.ctrlKey || event.metaKey) && key === "s";
      const isWindowsSnipShortcut = event.metaKey && event.shiftKey && key === "s";

      if (isPrintScreen || isPrintShortcut || isSaveShortcut || isWindowsSnipShortcut) {
        handleCaptureBlocked(event);
      }
    };

    const handleBeforePrint = (event: Event) => {
      handleCaptureBlocked(event);
    };

    inspectWindowState();
    inspectScreenState();
    document.addEventListener("visibilitychange", handleVisibilityChange);
    document.addEventListener("keydown", handleKeyDown, true);
    document.addEventListener("contextmenu", handleCaptureBlocked, true);
    document.addEventListener("copy", handleCaptureBlocked, true);
    document.addEventListener("cut", handleCaptureBlocked, true);
    document.addEventListener("dragstart", handleCaptureBlocked, true);
    window.addEventListener("beforeprint", handleBeforePrint);
    window.addEventListener("blur", handleWindowBlur);
    window.addEventListener("resize", handleWindowResize);
    window.addEventListener("focus", handleWindowFocus);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      document.removeEventListener("keydown", handleKeyDown, true);
      document.removeEventListener("contextmenu", handleCaptureBlocked, true);
      document.removeEventListener("copy", handleCaptureBlocked, true);
      document.removeEventListener("cut", handleCaptureBlocked, true);
      document.removeEventListener("dragstart", handleCaptureBlocked, true);
      window.removeEventListener("beforeprint", handleBeforePrint);
      window.removeEventListener("blur", handleWindowBlur);
      window.removeEventListener("resize", handleWindowResize);
      window.removeEventListener("focus", handleWindowFocus);
      if (captureShieldTimerRef.current !== null) {
        window.clearTimeout(captureShieldTimerRef.current);
        captureShieldTimerRef.current = null;
      }
      setCaptureShieldVisible(false);
    };
  }, [finalReportReady, interviewEnded, interviewStartedAt, language, sessionId]);

  const stopCurrentVoice = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.remove();
      audioRef.current = null;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    setInterviewerSpeaking(false);
  };

  const clearLiveTranscript = () => {
    liveTranscriptRef.current = "";
    setLiveTranscript("");
  };

  const resetLiveAutoSubmitState = () => {
    if (liveSubmitTimerRef.current !== null && typeof window !== "undefined") {
      window.clearTimeout(liveSubmitTimerRef.current);
    }
    liveSubmitTimerRef.current = null;
  };

  const getPendingLiveTranscriptText = () => {
    const buffered = liveFinalBufferRef.current.trim();
    const interim = liveTranscriptRef.current.trim();
    if (buffered) {
      return buffered;
    }
    return interim;
  };

  const resetBrowserSpeechTranscript = () => {
    browserSpeechTranscriptRef.current = "";
    browserSpeechInterimRef.current = "";
  };

  const stopBrowserSpeechRecognitionImmediately = () => {
    const recognition = browserSpeechRecognitionRef.current;
    browserSpeechRecognitionRef.current = null;
    if (!recognition) {
      resetBrowserSpeechTranscript();
      return;
    }
    recognition.onresult = null;
    recognition.onerror = null;
    recognition.onend = null;
    try {
      recognition.abort();
    } catch {
      // noop
    }
    resetBrowserSpeechTranscript();
  };

  const stopBrowserSpeechRecognition = async () => {
    const recognition = browserSpeechRecognitionRef.current;
    if (!recognition || typeof window === "undefined") {
      return mergeTranscriptText(browserSpeechTranscriptRef.current, browserSpeechInterimRef.current).trim();
    }

    return await new Promise<string>((resolve) => {
      let settled = false;
      const finish = () => {
        if (settled) {
          return;
        }
        settled = true;
        const transcript = mergeTranscriptText(browserSpeechTranscriptRef.current, browserSpeechInterimRef.current).trim();
        browserSpeechRecognitionRef.current = null;
        resetBrowserSpeechTranscript();
        resolve(transcript);
      };

      const timerId = window.setTimeout(() => {
        try {
          recognition.abort();
        } catch {
          // noop
        }
        finish();
      }, 1500);

      recognition.onend = () => {
        window.clearTimeout(timerId);
        finish();
      };

      try {
        recognition.stop();
      } catch {
        window.clearTimeout(timerId);
        finish();
      }
    });
  };

  const stopMediaRecorder = async () => {
    const recorder = mediaRecorderRef.current;
    mediaRecorderRef.current = null;

    if (!recorder) {
      const chunks = mediaRecorderChunksRef.current;
      mediaRecorderChunksRef.current = [];
      return chunks.length ? new Blob(chunks, { type: mediaRecorderMimeTypeRef.current || "audio/webm" }) : null;
    }

    return await new Promise<Blob | null>((resolve) => {
      const finalize = () => {
        recorder.ondataavailable = null;
        recorder.onstop = null;
        recorder.onerror = null;
        const chunks = mediaRecorderChunksRef.current;
        mediaRecorderChunksRef.current = [];
        resolve(chunks.length ? new Blob(chunks, { type: mediaRecorderMimeTypeRef.current || recorder.mimeType || "audio/webm" }) : null);
      };

      recorder.onstop = finalize;
      recorder.onerror = finalize;

      if (recorder.state === "inactive") {
        finalize();
        return;
      }

      try {
        recorder.stop();
      } catch {
        finalize();
      }
    });
  };

  const disposeLiveMic = () => {
    micClosingRef.current = true;
    resetLiveAutoSubmitState();

    if (micSpeechTimerRef.current !== null && typeof window !== "undefined") {
      window.clearTimeout(micSpeechTimerRef.current);
      micSpeechTimerRef.current = null;
    }

    if (micKeepAliveTimerRef.current !== null && typeof window !== "undefined") {
      window.clearInterval(micKeepAliveTimerRef.current);
      micKeepAliveTimerRef.current = null;
    }

    micFinalizeUtteranceRef.current = null;
    micUtteranceActiveRef.current = false;
    micUtteranceStartedAtRef.current = null;
    micRollingChunksRef.current = [];
    micUtteranceChunksRef.current = [];
    micNoiseFloorRef.current = 0.002;
    stopBrowserSpeechRecognitionImmediately();
    mediaRecorderChunksRef.current = [];

    if (mediaRecorderRef.current) {
      const recorder = mediaRecorderRef.current;
      mediaRecorderRef.current = null;
      recorder.ondataavailable = null;
      recorder.onstop = null;
      recorder.onerror = null;
      if (recorder.state !== "inactive") {
        try {
          recorder.stop();
        } catch {
          // noop
        }
      }
    }

    if (micWorkletNodeRef.current) {
      micWorkletNodeRef.current.port.onmessage = null;
      try {
        micWorkletNodeRef.current.disconnect();
      } catch {
        // noop
      }
      micWorkletNodeRef.current = null;
    }

    if (micProcessorNodeRef.current) {
      micProcessorNodeRef.current.onaudioprocess = null;
      try {
        micProcessorNodeRef.current.disconnect();
      } catch {
        // noop
      }
      micProcessorNodeRef.current = null;
    }

    if (micSourceNodeRef.current) {
      try {
        micSourceNodeRef.current.disconnect();
      } catch {
        // noop
      }
      micSourceNodeRef.current = null;
    }

    if (micSinkNodeRef.current) {
      try {
        micSinkNodeRef.current.disconnect();
      } catch {
        // noop
      }
      micSinkNodeRef.current = null;
    }

    if (micSocketRef.current) {
      const socket = micSocketRef.current;
      micSocketRef.current = null;
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        try {
          socket.close(1000, "microphone-stopped");
        } catch {
          // noop
        }
      }
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (micAudioContextRef.current) {
      const audioContext = micAudioContextRef.current;
      micAudioContextRef.current = null;
      void audioContext.close().catch(() => undefined);
    }

    clearLiveTranscript();
    liveFinalBufferRef.current = "";
    setMicListening(false);
    micMuteRef.current = false;
  };

  const stopCamera = () => {
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach((track) => track.stop());
      cameraStreamRef.current = null;
    }
    setCameraOn(false);
  };

  const startCamera = async () => {
    if (interviewEnded || cameraOn) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      pushFeed("system", "Camera error: this browser does not support camera access.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: "user",
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      cameraStreamRef.current = stream;
      setCameraOn(true);
    } catch (error) {
      pushFeed("system", `Camera error: ${(error as Error).message}`);
    }
  };

  const toggleCamera = async () => {
    if (interviewEnded) return;
    if (cameraOn) {
      stopCamera();
      return;
    }
    await startCamera();
  };

  const cleanupActiveMedia = () => {
    disposeLiveMic();
    stopCamera();
    stopCurrentVoice();
    setMicListening(false);
    setInterviewerUtterance(null);
  };

  const resetToFreshSession = (nextSessionId = createSessionId()) => {
    cleanupActiveMedia();
    setSessionId(nextSessionId);
    setCandidateName("Candidate");
    setCandidateText("");
    setCvFile(null);
    setPersistedCvLabel("");
    setCvUploaded(false);
    setLoadingCv(false);
    setDownloadingReport(false);
    setSending(false);
    setInputMode("voice");
    setFinalReportReady(false);
    setInterviewEnded(false);
    setInterviewStartedAt(null);
    setElapsedSeconds(0);
    setFeed([]);
  };

  const loadHistory = async () => {
    try {
      const res = await fetch("/api/tech/sessions?limit=80", { method: "GET", cache: "no-store" });
      await res.json();
    } catch (error) {
      console.warn("History refresh failed", error);
    }
  };

  const handleInputModeChange = async (nextMode: InputMode, options?: { persist?: boolean }) => {
    const normalizedMode = nextMode === "voice" ? "voice" : normalizeInputMode("voice");
    setInputMode(normalizedMode);

    if (options?.persist === false) {
      return;
    }

    try {
      const { res, data } = await updatePreferredInputMode(sessionId, normalizedMode);
      if (!res.ok) {
        throw new Error(data?.detail || data?.error || "Unable to save the input mode.");
      }
    } catch (error) {
      pushFeed("system", `Mode error: ${(error as Error).message}`);
    }
  };

  const hydrateSession = async (targetSessionId: string) => {
    try {
      const { res, data } = await fetchSession(targetSessionId);
      if (!res.ok) {
        pushFeed("system", `Unable to load session: ${data?.detail || data?.error || "unknown error"}`);
        return;
      }

      cleanupActiveMedia();

      const turns = Array.isArray(data?.turns) ? data.turns : [];
      const hasFinalReport = Boolean(data?.final_report);
      const startedAt = turns[0]?.time ? new Date(turns[0].time) : null;

      setSessionId(targetSessionId);
      setCandidateName(
        String(data?.cv_profile?.candidate_name || data?.cv_profile?.name || "Candidate").trim() || "Candidate"
      );
      setCandidateText("");
      setCvFile(null);
      setPersistedCvLabel(String(data?.cv_profile?.source_filename || "").trim());
      setCvUploaded(Boolean(data?.cv_uploaded));
      setLoadingCv(false);
      setDownloadingReport(false);
      setSending(false);
      setInputMode("voice");
      setFinalReportReady(hasFinalReport);
      setInterviewEnded(hasFinalReport);
      setInterviewStartedAt(
        !hasFinalReport && startedAt && !Number.isNaN(startedAt.getTime()) ? startedAt.getTime() : null
      );
      setElapsedSeconds(computeElapsedFromTurns(turns));
      setFeed(buildFeedFromTurns(turns, data?.final_report?.summary));
    } catch (error) {
      pushFeed("system", `Unable to load session: ${(error as Error).message}`);
    }
  };

  const playAudioBlob = async (blob: Blob) => {
    if (!blob.size) {
      pushFeed("system", "Voice error: empty audio payload.");
      return;
    }

    stopCurrentVoice();

    const url = URL.createObjectURL(blob);
    audioUrlRef.current = url;
    const audio = new Audio(url);
    audio.preload = "auto";
    audio.setAttribute("playsinline", "true");
    audio.style.display = "none";
    document.body.appendChild(audio);
    audioRef.current = audio;
    setInterviewerSpeaking(true);
    audio.onended = () => {
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
      audio.remove();
      audioRef.current = null;
      setInterviewerSpeaking(false);
    };
    audio.onerror = () => {
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
      audio.remove();
      audioRef.current = null;
      setInterviewerSpeaking(false);
    };
    await audio.play();
  };

  const speakFallbackAudio = (text: string, audioBase64?: string, audioMimeType?: string) => {
    if (!voiceEnabled || typeof window === "undefined") return;
    void (async () => {
      try {
        if (audioBase64) {
          const binary = atob(audioBase64);
          const bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i += 1) {
            bytes[i] = binary.charCodeAt(i);
          }
          await playAudioBlob(new Blob([bytes], { type: audioMimeType || "audio/wav" }));
          return;
        }

        const res = await fetch("/api/tech/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        });
        if (!res.ok) {
          const raw = await res.text();
          pushFeed("system", `Voice error: ${raw || "TTS unavailable"}`);
          return;
        }

        const blob = await res.blob();
        await playAudioBlob(blob);
      } catch (error) {
        const message = (error as Error)?.message || "";
        if (message.includes("play() request was interrupted") || message.includes("The play() request was interrupted")) {
          return;
        }
        if (message.includes("NotAllowedError") || message.toLowerCase().includes("not allowed")) {
          pushFeed("system", "Voice error: the browser blocked audio playback. Click once on the page, then try again.");
          return;
        }
        pushFeed("system", `Voice error: ${message}`);
      }
    })();
  };

  const submitCandidateText = async (text: string, options?: { stopMicAfterSend?: boolean }) => {
    const clean = text.trim();
    if (!clean) return;
    if (!cvUploaded) {
      pushFeed("system", language === "fr" ? "Veuillez telecharger le CV avant de commencer l'entretien." : "Upload the CV before starting the interview.");
      return;
    }
    if (interviewEnded) {
      pushFeed("system", "The interview has already been ended. Reload the page to start a new session.");
      return;
    }
    resetLiveAutoSubmitState();
    clearLiveTranscript();
    liveFinalBufferRef.current = "";
    setSending(true);
    pushFeed("you", `[${candidateName || "Candidate"}]: ${clean}`);
    setCandidateText("");

    try {
      const res = await fetch(`/api/tech/session/${encodeURIComponent(sessionId)}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: clean, candidate_name: candidateName || "Candidate" }),
      });
      const data = await readApiPayload(res);
      if (!res.ok) {
        pushFeed("system", `Message error: ${data?.detail || data?.error || "unknown error"}`);
        return;
      }
      if (data?.error || data?.detail) {
        pushFeed("system", `Message error: ${data.detail || data.error}`);
        return;
      }
      if (data?.say) {
        if (interviewStartedAt === null) {
          setInterviewStartedAt(Date.now());
          setElapsedSeconds(0);
        }
        pushFeed("interviewer", `[${copy.roleInterviewer}]: ${data.say}`);
        setInterviewerUtterance({
          id: Date.now(),
          text: data.say,
          audioBase64: data?.audio_base64,
          audioMimeType: data?.audio_mime_type,
        });
      }
      if (data?.final_report) {
        if (data.final_report.summary) {
          pushFeed("system", `Final report: ${data.final_report.summary}`);
        } else {
          pushFeed("system", "Final report is ready for download.");
        }
        setFinalReportReady(true);
        setInterviewEnded(true);
      }
      void loadHistory();
    } catch (error) {
      pushFeed("system", `Message error: ${(error as Error).message}`);
    } finally {
      setSending(false);
      if (options?.stopMicAfterSend) {
        disposeLiveMic();
      }
    }
  };

  const recordCandidateAudioObservation = async (payload: AudioObservationPayload) => {
    if (payload.word_count <= 0 || payload.duration_seconds <= 0) {
      return;
    }

    const res = await fetch(`/api/tech/session/${encodeURIComponent(sessionId)}/audio`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(String(data?.detail || data?.error || "Unable to store audio observations."));
    }
  };

  const collectPendingMicObservationSamples = () => {
    const audioContext = micAudioContextRef.current;
    const chunks = micUtteranceChunksRef.current.map((entry) => entry.samples);
    if (!audioContext || !chunks.length) {
      return null;
    }

    const merged = concatAudioChunks(chunks);
    if (!merged.length) {
      return null;
    }

    return downsampleTo16k(merged, audioContext.sampleRate);
  };

  const buildAndRecordAudioObservation = async (transcript: string, samples?: Float32Array | null) => {
    if (!samples || !samples.length) {
      return;
    }

    const observationPayload = analyzeCapturedUtterance(samples, LIVE_STT_SAMPLE_RATE, transcript, language);
    await recordCandidateAudioObservation(observationPayload);
  };

  const transcribeRecordedUtterance = async (
    blob: Blob,
    samples?: Float32Array | null,
    options?: { fallbackTranscript?: string }
  ) => {
    if (!blob.size) {
      return;
    }

    const form = new FormData();
    const isWav = (blob.type || "").toLowerCase().includes("wav");
    form.append(
      "file",
      new File([blob], `utterance-${Date.now()}.${isWav ? "wav" : "webm"}`, { type: blob.type || (isWav ? "audio/wav" : "audio/webm") })
    );
    form.append("language", language);

    try {
      const res = await fetch("/api/tech/stt", {
        method: "POST",
        body: form,
      });
      const data = await res.json();
      if (!res.ok) {
        const fallbackTranscript = String(options?.fallbackTranscript || "").trim();
        if (isUsableTranscript(fallbackTranscript)) {
          pushFeed(
            "system",
            language === "fr"
              ? "Deepgram a mis trop de temps; utilisation de la transcription navigateur."
              : "Deepgram timed out; using the browser transcript."
          );
          if (samples && samples.length) {
            void buildAndRecordAudioObservation(fallbackTranscript, samples).catch((audioObservationError) => {
              console.warn("Audio observation upload failed", audioObservationError);
            });
          }
          await submitCandidateText(fallbackTranscript);
          return;
        }
        pushFeed("system", `Microphone error: ${data?.detail || data?.error || "STT unavailable"}`);
        return;
      }
      const text = String(data?.text || "").trim();
      if (!text) {
        return;
      }
      if (samples && samples.length) {
        void buildAndRecordAudioObservation(text, samples).catch((audioObservationError) => {
          console.warn("Audio observation upload failed", audioObservationError);
        });
      }
      await submitCandidateText(text);
    } catch (error) {
      const fallbackTranscript = String(options?.fallbackTranscript || "").trim();
      if (isUsableTranscript(fallbackTranscript)) {
        pushFeed(
          "system",
          language === "fr"
            ? "Transcription serveur indisponible; utilisation de la transcription navigateur."
            : "Server transcription is unavailable; using the browser transcript."
        );
        if (samples && samples.length) {
          void buildAndRecordAudioObservation(fallbackTranscript, samples).catch((audioObservationError) => {
            console.warn("Audio observation upload failed", audioObservationError);
          });
        }
        await submitCandidateText(fallbackTranscript);
        return;
      }
      pushFeed("system", `Microphone error: ${(error as Error).message}`);
    }
  };

  const startMic = async () => {
    if (micListening) return;
    if (!cvUploaded) {
      pushFeed("system", language === "fr" ? "Veuillez telecharger le CV avant de commencer l'entretien." : "Upload the CV before starting the interview.");
      return;
    }
    if (inputMode === "text") {
      await handleInputModeChange("voice");
    }
    const AudioContextCtor =
      typeof window === "undefined"
        ? undefined
        : window.AudioContext ||
          (window as Window & typeof globalThis & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    try {
      micClosingRef.current = false;
      clearLiveTranscript();

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;
      mediaRecorderChunksRef.current = [];

      if (typeof MediaRecorder !== "undefined") {
        try {
          const preferredMimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
            ? "audio/webm;codecs=opus"
            : "audio/webm";
          const recorder = new MediaRecorder(stream, preferredMimeType ? { mimeType: preferredMimeType } : undefined);
          mediaRecorderMimeTypeRef.current = recorder.mimeType || preferredMimeType || "audio/webm";
          recorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) {
              mediaRecorderChunksRef.current.push(event.data);
            }
          };
          recorder.start();
          mediaRecorderRef.current = recorder;
        } catch {
          mediaRecorderRef.current = null;
          mediaRecorderChunksRef.current = [];
        }
      }

      if (typeof window === "undefined" || !AudioContextCtor) {
        throw new Error("Live microphone streaming is not supported in this browser.");
      }

      const audioContext = new AudioContextCtor();
      micAudioContextRef.current = audioContext;
      await audioContext.resume();

      const source = audioContext.createMediaStreamSource(stream);
      const processorNode = audioContext.createScriptProcessor(2048, 1, 1);
      const sink = audioContext.createGain();
      sink.gain.value = 0;

      micSourceNodeRef.current = source;
      micProcessorNodeRef.current = processorNode;
      micSinkNodeRef.current = sink;

      micRollingChunksRef.current = [];
      micUtteranceChunksRef.current = [];
      micUtteranceActiveRef.current = true;
      micUtteranceStartedAtRef.current = null;
      micNoiseFloorRef.current = 0.002;
      liveFinalBufferRef.current = "";
      liveTranscriptRef.current = "listening";
      setLiveTranscript("listening");
      resetBrowserSpeechTranscript();

      micFinalizeUtteranceRef.current = async () => {
        if (!micUtteranceActiveRef.current) {
          return;
        }
        micUtteranceActiveRef.current = false;
        micUtteranceStartedAtRef.current = null;

        const chunks = micUtteranceChunksRef.current.map((entry) => entry.samples);
        micUtteranceChunksRef.current = [];
        clearLiveTranscript();

        const merged = concatAudioChunks(chunks);
        if (!merged.length || micMuteRef.current || sendingRef.current || interviewEnded) {
          return;
        }

        const fallbackTranscript = mergeTranscriptText(
          browserSpeechTranscriptRef.current,
          browserSpeechInterimRef.current
        ).trim();
        const wavSamples = downsampleTo16k(merged, audioContext.sampleRate);
        if (isUsableTranscript(fallbackTranscript)) {
          clearLiveTranscript();
          resetBrowserSpeechTranscript();
          if (wavSamples && wavSamples.length) {
            void buildAndRecordAudioObservation(fallbackTranscript, wavSamples).catch((audioObservationError) => {
              console.warn("Audio observation upload failed", audioObservationError);
            });
          }
          await submitCandidateText(fallbackTranscript);
          return;
        }
        const blob = encodeWav(wavSamples, LIVE_STT_SAMPLE_RATE);
        await transcribeRecordedUtterance(blob, wavSamples, { fallbackTranscript });
      };

      processorNode.onaudioprocess = (event) => {
        if (micMuteRef.current || sendingRef.current || interviewerSpeaking) {
          return;
        }
        const samples = new Float32Array(event.inputBuffer.getChannelData(0));
        if (!samples.length) {
          return;
        }
        const audioChunk = new Float32Array(samples);
        const entry = { samples: audioChunk, at: Date.now() };
        if (micUtteranceActiveRef.current) {
          micUtteranceChunksRef.current.push(entry);
        }
      };

      micSocketRef.current = null;
      lastMicChunkSentAtRef.current = Date.now();

      source.connect(processorNode);
      processorNode.connect(sink);
      sink.connect(audioContext.destination);

      const BrowserSpeechRecognitionCtor = getBrowserSpeechRecognitionCtor();
      if (BrowserSpeechRecognitionCtor) {
        try {
          const recognition = new BrowserSpeechRecognitionCtor();
          recognition.lang = language === "en" ? "en-US" : "fr-FR";
          recognition.continuous = true;
          recognition.interimResults = true;
          recognition.onresult = (event) => {
            let finalTranscript = browserSpeechTranscriptRef.current;
            let interimTranscript = "";

            for (let index = event.resultIndex; index < event.results.length; index += 1) {
              const result = event.results[index];
              const transcript = String(result?.[0]?.transcript || "").trim();
              if (!transcript) {
                continue;
              }
              if (result.isFinal) {
                finalTranscript = mergeTranscriptText(finalTranscript, transcript);
              } else {
                interimTranscript = transcript;
              }
            }

            browserSpeechTranscriptRef.current = finalTranscript.trim();
            browserSpeechInterimRef.current = interimTranscript.trim();
            const displayTranscript = mergeTranscriptText(
              browserSpeechTranscriptRef.current,
              browserSpeechInterimRef.current
            ).trim();
            liveTranscriptRef.current = displayTranscript || "listening";
            setLiveTranscript(displayTranscript || "listening");
          };
          recognition.onerror = () => {
            // Leave audio capture fallback active if browser speech recognition fails.
          };
          recognition.onend = () => {
            if (browserSpeechRecognitionRef.current === recognition) {
              browserSpeechRecognitionRef.current = null;
            }
          };
          recognition.start();
          browserSpeechRecognitionRef.current = recognition;
        } catch {
          browserSpeechRecognitionRef.current = null;
          resetBrowserSpeechTranscript();
        }
      }

      setMicListening(true);
    } catch (error) {
      const msg = (error as Error)?.message || "";
      if (msg.toLowerCase().includes("denied") || msg.toLowerCase().includes("permission")) {
        disposeLiveMic();
        pushFeed("system", "Microphone access was denied. Enable it in your browser permissions.");
        return;
      }
      disposeLiveMic();
      pushFeed("system", `Unable to start the microphone: ${msg || "unknown error"}`);
    }
  };

  const stopMic = async (options?: { submitPending?: boolean }) => {
    const browserTranscript = options?.submitPending === false ? "" : await stopBrowserSpeechRecognition();
    const recordedBlob = options?.submitPending === false ? null : await stopMediaRecorder();
    if (browserTranscript && !sendingRef.current && !interviewEnded) {
      const pendingSamples = collectPendingMicObservationSamples();
      disposeLiveMic();
      if (pendingSamples?.length) {
        void buildAndRecordAudioObservation(browserTranscript, pendingSamples).catch((audioObservationError) => {
          console.warn("Audio observation upload failed", audioObservationError);
        });
      }
      await submitCandidateText(browserTranscript);
      return;
    }

    if (recordedBlob && recordedBlob.size > 0 && !sendingRef.current && !interviewEnded) {
      const pendingSamples = collectPendingMicObservationSamples();
      disposeLiveMic();
      await transcribeRecordedUtterance(recordedBlob, pendingSamples, { fallbackTranscript: browserTranscript });
      return;
    }

    const shouldSubmitRecordedUtterance = options?.submitPending !== false && Boolean(micFinalizeUtteranceRef.current);

    if (shouldSubmitRecordedUtterance) {
      await micFinalizeUtteranceRef.current?.();
    }
    disposeLiveMic();
  };

  const toggleMic = async () => {
    if (interviewEnded) return;
    if (micListening) {
      await stopMic();
      return;
    }
    await startMic();
  };

  const handleEndInterview = async () => {
    if (interviewEnded) return;

    setSending(true);

    if (interviewStartedAt !== null) {
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - interviewStartedAt) / 1000)));
      setInterviewStartedAt(null);
    }

    if (micListening) {
      await stopMic();
    } else {
      disposeLiveMic();
    }
    stopCamera();
    stopCurrentVoice();
    setCandidateText("");
    setInterviewerUtterance(null);
    setMicListening(false);

    try {
      const { res, data } = await finalizeInterviewSession(sessionId, inputMode);
      if (!res.ok) {
        throw new Error(data?.detail || data?.error || "Unable to finalize the interview.");
      }

      if (data?.say) {
        pushFeed("interviewer", `[${copy.roleInterviewer}]: ${data.say}`);
        setInterviewerUtterance({
          id: Date.now(),
          text: data.say,
          audioBase64: data?.audio_base64,
          audioMimeType: data?.audio_mime_type,
        });
      }

      if (data?.final_report?.summary) {
        pushFeed("system", `Final report: ${data.final_report.summary}`);
      } else {
        pushFeed("system", "Final report is ready for download.");
      }

      setFinalReportReady(true);
      setInterviewEnded(true);
      void loadHistory();
    } catch (error) {
      pushFeed("system", `Finalize error: ${(error as Error).message}`);
    } finally {
      setSending(false);
    }
  };

  const onUploadCv = async () => {
    if (!cvFile) {
      pushFeed("system", "Choose a resume file before uploading.");
      return;
    }
    setLoadingCv(true);
    try {
      const body = new FormData();
      body.append("file", cvFile);
      const res = await fetch(`/api/tech/session/${encodeURIComponent(sessionId)}/cv`, {
        method: "POST",
        body,
      });
      const data = await res.json();
      if (!res.ok) {
        pushFeed("system", `Resume upload failed: ${data?.detail || data?.error || "unknown error"}`);
        return;
      }
      setCvUploaded(true);
      setPersistedCvLabel(String(data?.profile?.source_filename || data?.filename || cvFile.name || "").trim());
      setFinalReportReady(false);
      const name = data?.profile?.candidate_name ? ` (${data.profile.candidate_name})` : "";
      if (data?.profile?.candidate_name) {
        setCandidateName(String(data.profile.candidate_name));
      }
      pushFeed("system", `Resume uploaded: ${data.filename}${name}`);
      void loadHistory();
    } catch (error) {
      pushFeed("system", `Resume upload failed: ${(error as Error).message}`);
    } finally {
      setLoadingCv(false);
    }
  };

  const onSendMessage = async (event: FormEvent) => {
    event.preventDefault();
    await submitCandidateText(candidateText);
  };

  const onDownloadReport = async () => {
    if (!sessionId.trim() || downloadingReport) return;
    setDownloadingReport(true);
    router.push(`/report/${encodeURIComponent(sessionId)}`);
  };

  useEffect(() => {
    void loadHistory();
  }, []);

  useEffect(() => {
    const targetSessionId = searchParams.get("session");
    if (!targetSessionId || targetSessionId === sessionId) return;
    void hydrateSession(targetSessionId);
  }, [searchParams]);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [feed, liveTranscript]);

  useEffect(() => {
    return () => {
      cleanupActiveMedia();
    };
  }, []);

  useEffect(() => {
    if (interviewStartedAt === null) return;
    const interval = window.setInterval(() => {
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - interviewStartedAt) / 1000)));
    }, 1000);
    return () => window.clearInterval(interval);
  }, [interviewStartedAt]);

  const copy = interviewTranslations[language];
  const selectedCvLabel = cvFile?.name || persistedCvLabel || copy.noFileSelected;
  const interviewTimeLabel = interviewStartedAt === null && !interviewEnded ? "--:--" : formatElapsed(elapsedSeconds);
  const reportHref = `/report/${encodeURIComponent(sessionId)}?view=report`;
  const insightsHref = `/report/${encodeURIComponent(sessionId)}?view=insights`;
  const reportNavigationEnabled = finalReportReady || interviewEnded;
  const insightsAvailable = reportNavigationEnabled;

  return (
    <div
      className={`${styles.shell} ${theme === "dark" ? styles.themeDark : styles.themeLight}`}
      data-theme={theme}
    >
      <aside className={styles.sidebar}>
        <div className={styles.sidebarTop}>
          <Image className={styles.logoImage} src={logoImage} alt="SUBUL" priority />
        </div>

        <div className={styles.menuBlock}>
          <p className={styles.menuTitle}>{copy.mainMenu}</p>
          <nav className={styles.nav}>
            <span className={styles.navGroupTitle}>{copy.sidebarWorkspace}</span>
            <Link className={`${styles.navItem} ${styles.navItemActive}`} href="/">
              <SidebarIcon type="interview" />
              {copy.interview}
            </Link>
            <Link className={styles.navItem} href="/dashboard">
              <SidebarIcon type="dashboard" />
              {copy.analytics}
            </Link>
            <span className={styles.navGroupTitle}>{copy.sidebarReports}</span>
            {reportNavigationEnabled ? (
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
            {insightsAvailable ? (
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
            <Link className={styles.navItem} href="/help">
              <SidebarIcon type="help" />
              {copy.help}
            </Link>
          </nav>
        </div>
      </aside>

      <main className={styles.main}>
        <div className="workspace-shell">
          <section className="meeting-shell">
            <MeetingHeader
              cvFileSelected={Boolean(cvFile) || Boolean(persistedCvLabel)}
              cvUploaded={cvUploaded}
              controls={
                <>
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
                </>
              }
              finalReportReady={finalReportReady}
              inputMode={inputMode}
              interviewEnded={interviewEnded}
              interviewStarted={interviewStartedAt !== null}
              interviewTimeLabel={interviewTimeLabel}
              copy={{
                title: copy.meetingHeaderTitle,
                subtitle: copy.meetingHeaderSubtitle,
                session: copy.session,
                ended: copy.ended,
                running: copy.running,
                active: copy.active,
                finalizedByUser: copy.finalizedByUser,
                interviewStarted: copy.interviewStarted,
                waitingLaunch: copy.waitingLaunch,
                resume: copy.resume,
                uploaded: copy.uploaded,
                notUploaded: copy.notUploaded,
                fileSelected: copy.fileSelected,
                uploadCvToStart: copy.uploadCvToStart,
                report: copy.report,
                available: copy.available,
                inProgress: copy.inProgress,
                readyForDownload: copy.readyForDownload,
                generatedAtEnd: copy.generatedAtEnd,
                timer: copy.timer,
                finalDuration: copy.finalDuration,
                liveInterviewClock: copy.liveInterviewClock,
                startsAtFirstReply: copy.startsAtFirstReply,
              }}
            />

            <section className="stage">
              <InterviewFeedPanel
                candidateText={candidateText}
                copy={{
                  title: copy.interviewFeedTitle,
                  subtitle: copy.interviewFeedSubtitle,
                  messageCountSingular: copy.messageCountSingular,
                  messageCountPlural: copy.messageCountPlural,
                  readyToBegin: copy.readyToBegin,
                  interviewEnded: copy.interviewEndedMessage,
                  interviewEndedDescription: copy.interviewEndedDescription,
                  readyDescription: copy.interviewReadyDescription,
                  liveTranscript: copy.liveTranscriptLabel,
                  candidateMessage: copy.candidateMessage,
                  endedPlaceholder: copy.interviewEndedPlaceholder,
                  voicePlaceholder: copy.voiceModePlaceholder,
                  defaultPlaceholder: copy.interviewDefaultPlaceholder,
                  cvRequiredPlaceholder: copy.uploadCvToStart,
                  sendingMessage: copy.sendingMessage,
                  sendMessage: copy.sendMessage,
                  roleYou: copy.roleYou,
                  roleInterviewer: copy.roleInterviewer,
                  roleSystem: copy.roleSystem,
                }}
                cvUploaded={cvUploaded}
                inputMode={inputMode}
                interviewEnded={interviewEnded}
                feedEndRef={feedEndRef}
                feed={feed}
                interviewActive={interviewStartedAt !== null && !finalReportReady}
                liveTranscript={liveTranscript}
                onCandidateTextChange={setCandidateText}
                onSendMessage={onSendMessage}
                sending={sending}
              />

              <section className="meeting-grid">
                <CandidateTile
                  candidateName={candidateName}
                  cameraEnabled={cameraOn}
                  cameraStream={cameraStreamRef.current}
                  cvUploaded={cvUploaded}
                  inputMode={inputMode}
                  interviewActive={interviewStartedAt !== null && !interviewEnded}
                  interviewEnded={interviewEnded}
                  insightsAvailable={interviewStartedAt !== null || finalReportReady || interviewEnded}
                  micListening={micListening}
                  onEndCall={handleEndInterview}
                  onToggleCamera={toggleCamera}
                  onToggleMic={toggleMic}
                  sessionId={sessionId}
                  sending={sending}
                />

                <article className={`tile interviewer-tile ${interviewerSpeaking ? "speaking" : ""}`}>
                  <span className="tile-badge">{copy.roleInterviewer}</span>
                  <InterviewerVoiceCard
                    utterance={interviewerUtterance}
                    voiceEnabled={voiceEnabled}
                    onAudioUtterance={(utterance) => {
                      speakFallbackAudio(utterance.text, utterance.audioBase64, utterance.audioMimeType);
                    }}
                  />
                </article>
              </section>
            </section>

            <ControlPanel
              cvUploaded={cvUploaded}
              downloadingReport={downloadingReport}
              finalReportReady={finalReportReady}
              loadingCv={loadingCv}
              onDownloadReport={onDownloadReport}
              onSelectCv={(file) => {
                setCvFile(file);
                if (file) {
                  setPersistedCvLabel(file.name);
                }
              }}
              onUploadCv={onUploadCv}
              selectedCvLabel={selectedCvLabel}
              copy={{
                kicker: copy.controlPanel,
                subtitle: copy.controlSubtitle,
                dragResume: copy.dragResume,
                fileTypes: copy.fileTypes,
                browseFiles: copy.browseFiles,
                noFileSelected: copy.noFileSelected,
                uploadCv: copy.uploadCv,
                uploading: copy.uploading,
                cvUploaded: copy.cvUploaded,
                readyToUpload: copy.readyToUpload,
                waitingForCv: copy.waitingForCv,
                opening: copy.opening,
                openReportDashboard: copy.openReportDashboard,
              }}
            />

            <footer className="footer-tip">{copy.footer}</footer>
          </section>
        </div>
        {captureShieldVisible && (
          <div className="capture-shield" role="alert" aria-live="assertive">
            <strong>{language === "fr" ? "Capture interdite" : "Capture blocked"}</strong>
            <span>
              {language === "fr"
                ? "Les captures, impressions et copies sont bloquees pendant l'entretien."
                : "Screenshots, printing and copying are blocked during the interview."}
            </span>
          </div>
        )}
        {proctoringToast && (
          <div className="proctoring-toast" role="status" aria-live="polite">
            <div className="proctoring-toast-copy">
              <strong>
                {language === "fr"
                  ? ` ${proctoringToast.typeLabel}`
                  : ` ${proctoringToast.typeLabel}`}
              </strong>
              <span>{proctoringToast.message}</span>
            </div>
            <button
              type="button"
              className="proctoring-toast-close"
              aria-label={language === "fr" ? "Fermer l'alerte" : "Close alert"}
              onClick={() => {
                pendingVisibleProctoringToastRef.current = null;
                setProctoringToast(null);
              }}
            >
              x
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={null}>
      <HomePageContent />
    </Suspense>
  );
}
