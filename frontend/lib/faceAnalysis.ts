"use client";

import { FaceLandmarker, FaceLandmarkerResult, FilesetResolver, NormalizedLandmark } from "@mediapipe/tasks-vision";

export type CandidateExpression = "neutral" | "smiling" | "speaking" | "attentive" | "unavailable";
export type CandidatePosture = "stable" | "slightly turned" | "tilted" | "unavailable";
export type CandidateFaceBox = {
  left: number;
  top: number;
  right: number;
  bottom: number;
};

export type CandidateFaceAnalysis = {
  status: "idle" | "loading" | "ready" | "error";
  faceDetected: boolean;
  multipleFaces: boolean;
  faceCount: number;
  faceBox: CandidateFaceBox | null;
  centered: boolean;
  lookingForward: boolean;
  expression: CandidateExpression;
  posture: CandidatePosture;
  message: string;
  error?: string;
};

export const idleFaceAnalysis: CandidateFaceAnalysis = {
  status: "idle",
  faceDetected: false,
  multipleFaces: false,
  faceCount: 0,
  faceBox: null,
  centered: false,
  lookingForward: false,
  expression: "unavailable",
  posture: "unavailable",
  message: "Camera analysis is idle.",
};

const WASM_BASE = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision/wasm";
const MODEL_ASSET_PATH =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

let faceLandmarkerPromise: Promise<FaceLandmarker> | null = null;

function averagePoint(points: NormalizedLandmark[]) {
  if (!points.length) {
    return { x: 0, y: 0 };
  }

  const total = points.reduce(
    (acc, point) => {
      acc.x += point.x;
      acc.y += point.y;
      return acc;
    },
    { x: 0, y: 0 }
  );

  return { x: total.x / points.length, y: total.y / points.length };
}

function safeRatio(numerator: number, denominator: number) {
  if (!Number.isFinite(denominator) || denominator <= 0) return 0;
  return numerator / denominator;
}

function getBlendshapeScore(result: FaceLandmarkerResult, name: string) {
  const categories = result.faceBlendshapes?.[0]?.categories ?? [];
  return categories.find((category) => category.categoryName === name)?.score ?? 0;
}

function deriveExpression(result: FaceLandmarkerResult): CandidateExpression {
  const smileScore = (getBlendshapeScore(result, "mouthSmileLeft") + getBlendshapeScore(result, "mouthSmileRight")) / 2;
  const jawOpen = getBlendshapeScore(result, "jawOpen");
  const browInnerUp = getBlendshapeScore(result, "browInnerUp");

  if (smileScore >= 0.42) return "smiling";
  if (jawOpen >= 0.32) return "speaking";
  if (browInnerUp >= 0.35) return "attentive";
  return "neutral";
}

function derivePosture(rollRatio: number, turnRatio: number): CandidatePosture {
  if (turnRatio >= 0.24) return "slightly turned";
  if (rollRatio >= 0.1) return "tilted";
  return "stable";
}

export function summarizeFaceResult(result: FaceLandmarkerResult): CandidateFaceAnalysis {
  const faceCount = result.faceLandmarks.length;
  if (!faceCount) {
    return {
      status: "ready",
      faceDetected: false,
      multipleFaces: false,
      faceCount: 0,
      faceBox: null,
      centered: false,
      lookingForward: false,
      expression: "unavailable",
      posture: "unavailable",
      message: "No face detected. Move into frame for live analysis.",
    };
  }

  const landmarks = result.faceLandmarks[0];
  const xs = landmarks.map((point) => point.x);
  const ys = landmarks.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;

  const leftEye = averagePoint([landmarks[33], landmarks[133]].filter(Boolean));
  const rightEye = averagePoint([landmarks[362], landmarks[263]].filter(Boolean));
  const mouth = averagePoint([landmarks[61], landmarks[291]].filter(Boolean));
  const nose = landmarks[1] ?? averagePoint([leftEye, rightEye, mouth] as NormalizedLandmark[]);

  const eyeDistance = Math.abs(rightEye.x - leftEye.x);
  const eyeMidX = (leftEye.x + rightEye.x) / 2;
  const rollRatio = safeRatio(Math.abs(leftEye.y - rightEye.y), eyeDistance);
  const turnRatio = safeRatio(Math.abs(nose.x - eyeMidX), eyeDistance);
  const centered = Math.abs(centerX - 0.5) <= 0.14 && Math.abs(centerY - 0.48) <= 0.18;
  const lookingForward = turnRatio <= 0.18;
  const multipleFaces = faceCount > 1;
  const expression = deriveExpression(result);
  const posture = derivePosture(rollRatio, turnRatio);
  const faceBox = {
    left: Math.max(0, Math.min(1, minX)),
    top: Math.max(0, Math.min(1, minY)),
    right: Math.max(0, Math.min(1, maxX)),
    bottom: Math.max(0, Math.min(1, maxY)),
  };

  const message = multipleFaces
    ? "Multiple faces detected. Keep only one candidate in frame."
    : centered && lookingForward
      ? "Face analysis looks stable."
      : "Adjust framing for a cleaner interview view.";

  return {
    status: "ready",
    faceDetected: true,
    multipleFaces,
    faceCount,
    faceBox,
    centered,
    lookingForward,
    expression,
    posture,
    message,
  };
}

export async function getFaceLandmarker() {
  if (!faceLandmarkerPromise) {
    faceLandmarkerPromise = (async () => {
      const vision = await FilesetResolver.forVisionTasks(WASM_BASE);
      return FaceLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: MODEL_ASSET_PATH },
        runningMode: "VIDEO",
        numFaces: 2,
        minFaceDetectionConfidence: 0.55,
        minFacePresenceConfidence: 0.55,
        minTrackingConfidence: 0.55,
        outputFaceBlendshapes: true,
      });
    })();
  }

  return faceLandmarkerPromise;
}
