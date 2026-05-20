"use client";

import { RefObject, useEffect, useRef, useState } from "react";

import type { CandidateFaceAnalysis } from "../../lib/faceAnalysis";

const REPORT_CAPTURE_INTERVAL_MS = 3000;
const REPORT_CAPTURE_JPEG_QUALITY = 0.9;
const OBJECT_DETECTION_MIN_SCORE = 0.45;
const EXTERNAL_OBJECT_DETECTION_MIN_SCORE = 0.25;
const OBJECT_DETECTION_MAX_ITEMS = 12;
const MIN_FACE_BOX_WIDTH = 0.16;
const MIN_FACE_BOX_HEIGHT = 0.2;
const MIN_FACE_BOX_AREA = 0.055;
const PREFERRED_OFFCENTER_FACE_BOX_AREA = 0.11;
const MIN_SUBMIT_FACE_BOX_AREA = 0.025;
const MODEL_EMOTION_LABELS = ["happy", "neutral", "sad", "angry", "surprise"] as const;
const IGNORED_OBJECT_LABELS = new Set(["person", "remote"]);

export type LiveEmotionLabel = (typeof MODEL_EMOTION_LABELS)[number];

export type LiveEmotionAnalysis = {
  status: "idle" | "waiting" | "loading" | "ready" | "error";
  provider: string;
  summary: string;
  dominantEmotion: LiveEmotionLabel | "";
  confidence: number | null;
  stressSignal: number | null;
  probabilities: Record<LiveEmotionLabel, number>;
  updatedAt: string;
  error?: string;
};

const EMPTY_PROBABILITIES: Record<LiveEmotionLabel, number> = {
  happy: 0,
  neutral: 0,
  sad: 0,
  angry: 0,
  surprise: 0,
};

export const idleLiveEmotionAnalysis: LiveEmotionAnalysis = {
  status: "idle",
  provider: "custom",
  summary: "Emotion model idle.",
  dominantEmotion: "",
  confidence: null,
  stressSignal: null,
  probabilities: { ...EMPTY_PROBABILITIES },
  updatedAt: "",
};

type VisionProviderPayload = {
  provider?: string;
  ready?: boolean;
  summary?: string;
  label?: string;
  confidence?: number | null;
  metadata?: {
    raw_emotion?: Record<string, number>;
    raw_predictions?: Array<{ label?: string; score?: number }>;
    labels?: string[];
    reason?: string;
  } | null;
};

type VisionRouteResponse = {
  providers?: VisionProviderPayload[];
  detail?: string;
  error?: string;
};

type DetectedObject = {
  label: string;
  score: number;
};

type ExternalDetectedObject = {
  label: string;
  confidence?: number;
  score?: number;
};

type ObjectDetector = {
  detect: (input: HTMLVideoElement | HTMLCanvasElement | HTMLImageElement) => Promise<Array<{ class: string; score: number }>>;
};

let objectDetectorPromise: Promise<ObjectDetector | null> | null = null;

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

async function getObjectDetector() {
  if (!objectDetectorPromise) {
    objectDetectorPromise = (async () => {
      try {
        await import("@tensorflow/tfjs");
        const cocoSsd = await import("@tensorflow-models/coco-ssd");
        return await cocoSsd.load({ base: "lite_mobilenet_v2" });
      } catch {
        return null;
      }
    })();
  }
  return objectDetectorPromise;
}

async function detectFrameObjects(video: HTMLVideoElement): Promise<DetectedObject[]> {
  const detector = await getObjectDetector();
  if (!detector) return [];
  try {
    const predictions = await detector.detect(video);
    return predictions
      .filter((item) => item.score >= OBJECT_DETECTION_MIN_SCORE)
      .filter((item) => !IGNORED_OBJECT_LABELS.has(String(item.class || "").trim().toLowerCase()))
      .slice(0, OBJECT_DETECTION_MAX_ITEMS)
      .map((item) => ({
        label: String(item.class || "").trim().toLowerCase(),
        score: clampPercent(item.score * 100),
      }))
      .filter((item) => item.label);
  } catch {
    return [];
  }
}

function normalizeExternalDetectedObjects(items: ExternalDetectedObject[] | undefined): DetectedObject[] {
  if (!Array.isArray(items)) return [];

  return items
    .map((item) => {
      const label = String(item?.label || "").trim().toLowerCase();
      const rawScore = Number(item?.score ?? item?.confidence ?? 0);
      const score = rawScore <= 1 ? rawScore * 100 : rawScore;
      return {
        label,
        score: clampPercent(score),
      };
    })
    .filter((item) => item.label && !IGNORED_OBJECT_LABELS.has(item.label) && item.score >= EXTERNAL_OBJECT_DETECTION_MIN_SCORE * 100)
    .slice(0, OBJECT_DETECTION_MAX_ITEMS);
}

function canonicalEmotionLabel(rawLabel: string): LiveEmotionLabel | "" {
  const normalized = rawLabel.trim().toLowerCase().replace(/[_-]+/g, " ");
  if (!normalized) {
    return "";
  }

  const aliases: Record<string, LiveEmotionLabel> = {
    joy: "happy",
    smile: "happy",
    smiling: "happy",
    calm: "neutral",
    anger: "angry",
    sadness: "sad",
    surprised: "surprise",
  };
  const canonical = aliases[normalized] ?? normalized;
  return MODEL_EMOTION_LABELS.includes(canonical as LiveEmotionLabel) ? (canonical as LiveEmotionLabel) : "";
}

function createProbabilityMap() {
  return { ...EMPTY_PROBABILITIES };
}

function computeStressSignal(probabilities: Record<LiveEmotionLabel, number>) {
  const weightedScore =
    probabilities.angry * 0.92 +
    probabilities.sad * 0.56 +
    probabilities.surprise * 0.38 +
    probabilities.neutral * 0.12 -
    probabilities.happy * 0.28;

  return clampPercent(weightedScore);
}

function pickDominantEmotion(probabilities: Record<LiveEmotionLabel, number>) {
  return MODEL_EMOTION_LABELS.reduce((best, label) =>
    probabilities[label] > probabilities[best] ? label : best
  , MODEL_EMOTION_LABELS[0]);
}

function normalizeConfidence(rawConfidence: number | null | undefined, fallbackPct: number) {
  if (typeof rawConfidence === "number" && Number.isFinite(rawConfidence)) {
    return clampPercent(rawConfidence <= 1 ? rawConfidence * 100 : rawConfidence);
  }
  return clampPercent(fallbackPct);
}

function parseProbabilityPayload(provider: VisionProviderPayload | null) {
  const probabilities = createProbabilityMap();
  const rawEmotion = provider?.metadata?.raw_emotion;

  if (rawEmotion && typeof rawEmotion === "object") {
    for (const [label, value] of Object.entries(rawEmotion)) {
      const canonical = canonicalEmotionLabel(label);
      if (!canonical || !Number.isFinite(value)) {
        continue;
      }
      probabilities[canonical] = clampPercent(Number(value));
    }
    return probabilities;
  }

  const rawPredictions = Array.isArray(provider?.metadata?.raw_predictions) ? provider?.metadata?.raw_predictions : [];
  for (const item of rawPredictions) {
    const canonical = canonicalEmotionLabel(String(item?.label || ""));
    const score = Number(item?.score);
    if (!canonical || !Number.isFinite(score)) {
      continue;
    }
    probabilities[canonical] = clampPercent(score <= 1 ? score * 100 : score);
  }

  return probabilities;
}

function buildLiveEmotionAnalysis(payload: VisionRouteResponse): LiveEmotionAnalysis {
  const providers = Array.isArray(payload.providers) ? payload.providers : [];
  const provider =
    providers.find((item) => String(item?.provider || "").toLowerCase() === "custom") ??
    providers.find((item) => item && item.provider) ??
    null;

  if (!provider) {
    return {
      ...idleLiveEmotionAnalysis,
      status: "waiting",
      summary: "Waiting for the custom emotion model.",
    };
  }

  if (!provider.ready) {
    return {
      ...idleLiveEmotionAnalysis,
      status: "error",
      provider: provider.provider || "custom",
      summary: provider.summary || "Emotion model unavailable for the latest frame.",
      error: String(provider.metadata?.reason || payload.detail || payload.error || ""),
    };
  }

  const probabilities = parseProbabilityPayload(provider);
  const reportedLabel = canonicalEmotionLabel(String(provider.label || ""));
  const dominantEmotion = reportedLabel || pickDominantEmotion(probabilities);
  const confidence = normalizeConfidence(provider.confidence, probabilities[dominantEmotion]);

  return {
    status: "ready",
    provider: provider.provider || "custom",
    summary: provider.summary || "Emotion model updated.",
    dominantEmotion,
    confidence,
    stressSignal: computeStressSignal(probabilities),
    probabilities,
    updatedAt: new Date().toISOString(),
  };
}

async function captureFrameBlob(video: HTMLVideoElement) {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const context = canvas.getContext("2d");
  if (!context) {
    return null;
  }
  context.drawImage(video, 0, 0, canvas.width, canvas.height);

  return await new Promise<Blob | null>((resolve) => {
    canvas.toBlob((blob) => resolve(blob), "image/jpeg", REPORT_CAPTURE_JPEG_QUALITY);
  });
}

function isEmotionReadyFrame(analysis: CandidateFaceAnalysis) {
  if (!analysis.faceDetected || analysis.multipleFaces || analysis.faceCount !== 1 || !analysis.faceBox) {
    return false;
  }

  const faceWidth = Math.max(0, analysis.faceBox.right - analysis.faceBox.left);
  const faceHeight = Math.max(0, analysis.faceBox.bottom - analysis.faceBox.top);
  const faceArea = faceWidth * faceHeight;

  if (faceWidth < MIN_FACE_BOX_WIDTH || faceHeight < MIN_FACE_BOX_HEIGHT || faceArea < MIN_FACE_BOX_AREA) {
    return false;
  }

  if (!analysis.lookingForward) {
    return false;
  }

  if (!analysis.centered && faceArea < PREFERRED_OFFCENTER_FACE_BOX_AREA) {
    return false;
  }

  return true;
}

function isEmotionSubmittableFrame(analysis: CandidateFaceAnalysis) {
  if (!analysis.faceDetected || analysis.multipleFaces || analysis.faceCount !== 1) {
    return false;
  }

  if (!analysis.faceBox) {
    return true;
  }

  const faceWidth = Math.max(0, analysis.faceBox.right - analysis.faceBox.left);
  const faceHeight = Math.max(0, analysis.faceBox.bottom - analysis.faceBox.top);
  return faceWidth * faceHeight >= MIN_SUBMIT_FACE_BOX_AREA;
}

export function useCandidateVisionReportCapture(
  videoRef: RefObject<HTMLVideoElement>,
  enabled: boolean,
  sessionId: string,
  analysis: CandidateFaceAnalysis,
  externalDetections: ExternalDetectedObject[] = []
) {
  const latestAnalysisRef = useRef(analysis);
  const latestDetectionsRef = useRef(externalDetections);
  const [liveEmotion, setLiveEmotion] = useState<LiveEmotionAnalysis>(idleLiveEmotionAnalysis);

  useEffect(() => {
    latestAnalysisRef.current = analysis;
  }, [analysis]);

  useEffect(() => {
    latestDetectionsRef.current = externalDetections;
  }, [externalDetections]);

  useEffect(() => {
    if (!enabled || !sessionId) {
      setLiveEmotion(idleLiveEmotionAnalysis);
      return;
    }

    let cancelled = false;
    let inFlight = false;
    let timerId = 0;

    setLiveEmotion((current) =>
      current.status === "ready"
        ? current
        : {
            ...idleLiveEmotionAnalysis,
            status: "waiting",
            summary: "Waiting for one clear forward-facing frame.",
          }
    );

    const submitSnapshot = async () => {
      const currentAnalysis = latestAnalysisRef.current;
      if (cancelled || inFlight) {
        return;
      }

      const emotionReadyFrame = isEmotionReadyFrame(currentAnalysis);
      if (!emotionReadyFrame) {
        setLiveEmotion((current) =>
          current.status === "ready"
            ? current
            : {
                ...current,
                status: "waiting",
                summary: "Waiting for one clear forward-facing frame.",
              }
        );
      }

      const video = videoRef.current;
      if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || video.videoWidth <= 0 || video.videoHeight <= 0) {
        return;
      }

      const blob = await captureFrameBlob(video);
      if (!blob || cancelled) {
        return;
      }
      const externalObjects = normalizeExternalDetectedObjects(latestDetectionsRef.current);
      const detectedObjects = externalObjects.length ? externalObjects : await detectFrameObjects(video);
      if (!emotionReadyFrame && !isEmotionSubmittableFrame(currentAnalysis) && !detectedObjects.length) {
        return;
      }

      inFlight = true;
      try {
        setLiveEmotion((current) =>
          current.status === "ready"
            ? current
            : {
                ...current,
                status: "loading",
                summary: "Analyzing live emotion...",
              }
        );

        const body = new FormData();
        body.append("file", new File([blob], "candidate-frame.jpg", { type: "image/jpeg" }));
        body.append("face_detected", String(currentAnalysis.faceDetected));
        body.append("centered", String(currentAnalysis.centered));
        body.append("looking_forward", String(currentAnalysis.lookingForward));
        body.append("expression", currentAnalysis.expression);
        body.append("posture", currentAnalysis.posture);
        body.append("face_count", String(currentAnalysis.faceCount));
        body.append("objects", JSON.stringify(detectedObjects));
        if (currentAnalysis.faceBox) {
          body.append("face_box_left", String(currentAnalysis.faceBox.left));
          body.append("face_box_top", String(currentAnalysis.faceBox.top));
          body.append("face_box_right", String(currentAnalysis.faceBox.right));
          body.append("face_box_bottom", String(currentAnalysis.faceBox.bottom));
        }

        const res = await fetch(`/api/tech/session/${encodeURIComponent(sessionId)}/vision`, {
          method: "POST",
          body,
        });

        const raw = await res.text();
        let payload: VisionRouteResponse = {};

        try {
          payload = raw ? (JSON.parse(raw) as VisionRouteResponse) : {};
        } catch {
          payload = { error: raw || "Unable to parse live emotion payload." };
        }

        if (!res.ok) {
          throw new Error(payload.detail || payload.error || "Unable to analyze live emotion.");
        }

        if (!cancelled) {
          setLiveEmotion(buildLiveEmotionAnalysis(payload));
        }
      } catch {
        if (!cancelled) {
          setLiveEmotion((current) =>
            current.status === "ready"
              ? current
              : {
                  ...idleLiveEmotionAnalysis,
                  status: "error",
                  summary: "Live emotion analysis is temporarily unavailable.",
                }
          );
        }
      } finally {
        inFlight = false;
      }
    };

    const schedule = () => {
      timerId = window.setInterval(() => {
        void submitSnapshot();
      }, REPORT_CAPTURE_INTERVAL_MS);
    };

    void submitSnapshot();
    schedule();

    return () => {
      cancelled = true;
      if (timerId) {
        window.clearInterval(timerId);
      }
    };
  }, [
    enabled,
    sessionId,
    videoRef,
  ]);

  return liveEmotion;
}
