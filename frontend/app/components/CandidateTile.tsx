"use client";

import { useEffect, useRef, useState } from "react";
import type { ObjectDetection as CocoSsdModel } from "@tensorflow-models/coco-ssd";
import { useCandidateFaceAnalysis } from "../hooks/useCandidateFaceAnalysis";
import {
  idleLiveEmotionAnalysis,
  useCandidateVisionReportCapture,
  type LiveEmotionLabel,
} from "../hooks/useCandidateVisionReportCapture";
import { useCandidateBackgroundBlur } from "../hooks/useCandidateBackgroundBlur";
import type { InputMode } from "../../lib/sessionRuntime";

type CandidateTileProps = {
  cameraEnabled: boolean;
  cameraStream: MediaStream | null;
  candidateName: string;
  cvUploaded: boolean;
  inputMode: InputMode;
  interviewActive: boolean;
  interviewEnded: boolean;
  insightsAvailable: boolean;
  micListening: boolean;
  onEndCall: () => Promise<void>;
  onToggleCamera: () => Promise<void>;
  onToggleMic: () => Promise<void>;
  sessionId: string;
  sending: boolean;
};

export type ObjectDetectionBox = {
  id: string;
  label: string;
  confidence: number;
  x: number;
  y: number;
  width: number;
  height: number;
};

const LIVE_EMOTION_ORDER: LiveEmotionLabel[] = ["happy", "neutral", "sad", "angry", "surprise"];

function formatLiveEmotionLabel(value: LiveEmotionLabel | "") {
  if (!value) {
    return "Waiting";
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function CandidateDetectionLayer({ detections }: { detections: ObjectDetectionBox[] }) {
  return (
    <div className="candidate-detection-layer" aria-hidden="true">
      {detections
        .filter((detection: ObjectDetectionBox) => detection.label !== "remote")
        .map((detection: ObjectDetectionBox) => (
          <span
            key={detection.id}
            className="candidate-detection-box"
            style={{
              left: `${detection.x}%`,
              top: `${detection.y}%`,
              width: `${detection.width}%`,
              height: `${detection.height}%`,
            }}
          >
            <span className="candidate-detection-label">{detection.label}</span>
          </span>
        ))}
    </div>
  );
}

export function CandidateTile({
  cameraEnabled,
  cameraStream,
  candidateName,
  cvUploaded,
  inputMode,
  interviewActive,
  interviewEnded,
  insightsAvailable,
  micListening,
  onEndCall,
  onToggleCamera,
  onToggleMic,
  sessionId,
  sending,
}: CandidateTileProps) {
  const sourceVideoRef = useRef<HTMLVideoElement | null>(null);
  const previewVideoRef = useRef<HTMLVideoElement | null>(null);
  const blurCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const [cameraSceneMode, setCameraSceneMode] = useState<"normal" | "blur" | "background">("normal");
  const [backgroundPreset, setBackgroundPreset] = useState<"office" | "meeting" | "minimal">("office");
  const [objectDetections, setObjectDetections] = useState<ObjectDetectionBox[]>([]);
  const objectDetectionModelRef = useRef<CocoSsdModel | null>(null);

  const liveVisionEnabled = cameraEnabled && Boolean(cameraStream) && !interviewEnded;
  const analysis = useCandidateFaceAnalysis(sourceVideoRef, liveVisionEnabled);
  const liveEmotion = useCandidateVisionReportCapture(sourceVideoRef, liveVisionEnabled, sessionId, analysis, objectDetections);
  useCandidateBackgroundBlur(
    sourceVideoRef,
    blurCanvasRef,
    cameraEnabled && cameraSceneMode !== "normal" ? cameraSceneMode : null,
    backgroundPreset
  );

  const displayName = candidateName || "Candidate";
  const idleNote = micListening
    ? "Microphone active. You can keep speaking or enable the camera for live visual signals."
    : inputMode === "text"
      ? "Mode texte actif. Passez en mixte ou micro pour repondre oralement."
      : "";
  const displayedLiveEmotion = liveEmotion.status === "ready" ? liveEmotion : idleLiveEmotionAnalysis;

  useEffect(() => {
    const attachStream = (node: HTMLVideoElement | null) => {
      if (!node) return;
      node.srcObject = cameraStream;
      if (cameraStream) {
        void node.play().catch(() => undefined);
      }
    };

    attachStream(sourceVideoRef.current);
    attachStream(previewVideoRef.current);

    return () => {
      if (sourceVideoRef.current) sourceVideoRef.current.srcObject = null;
      if (previewVideoRef.current) previewVideoRef.current.srcObject = null;
    };
  }, [cameraSceneMode, cameraStream]);

  useEffect(() => {
    if (cameraEnabled) return;
    setCameraSceneMode("normal");
  }, [cameraEnabled]);

  useEffect(() => {
    if (!cameraEnabled || !cameraStream) {
      setObjectDetections([]);
      return;
    }

    let cancelled = false;
    let timeoutId: number | null = null;

    const scheduleNextDetection = (delay = 450) => {
      if (cancelled) return;
      timeoutId = window.setTimeout(() => {
        void detectObjects();
      }, delay);
    };

    const mapPredictionToDetection = (
      prediction: { bbox: [number, number, number, number]; class: string; score: number },
      index: number
    ): ObjectDetectionBox | null => {
      const sourceVideo = sourceVideoRef.current;
      const previewVideo = previewVideoRef.current;
      const blurCanvas = blurCanvasRef.current;
      const target: HTMLVideoElement | HTMLCanvasElement | null = cameraSceneMode === "normal" ? previewVideo : blurCanvas;
      if (!sourceVideo || sourceVideo.readyState < 2 || !sourceVideo.videoWidth || !sourceVideo.videoHeight || !target) {
        return null;
      }

      const containerWidth = target.clientWidth || sourceVideo.videoWidth;
      const containerHeight = target.clientHeight || sourceVideo.videoHeight;
      const scale = Math.max(containerWidth / sourceVideo.videoWidth, containerHeight / sourceVideo.videoHeight);
      const renderedWidth = sourceVideo.videoWidth * scale;
      const renderedHeight = sourceVideo.videoHeight * scale;
      const offsetX = (containerWidth - renderedWidth) / 2;
      const offsetY = (containerHeight - renderedHeight) / 2;
      const [sourceX, sourceY, sourceWidth, sourceHeight] = prediction.bbox;
      const displayedX = offsetX + sourceX * scale;
      const displayedY = offsetY + sourceY * scale;
      const displayedWidth = sourceWidth * scale;
      const displayedHeight = sourceHeight * scale;
      const mirroredX = containerWidth - displayedX - displayedWidth;
      const clippedX = Math.max(0, Math.min(containerWidth, mirroredX));
      const clippedY = Math.max(0, Math.min(containerHeight, displayedY));
      const clippedRight = Math.max(0, Math.min(containerWidth, mirroredX + displayedWidth));
      const clippedBottom = Math.max(0, Math.min(containerHeight, displayedY + displayedHeight));
      const width = clippedRight - clippedX;
      const height = clippedBottom - clippedY;

      if (width <= 2 || height <= 2) {
        return null;
      }

      return {
        id: `${prediction.class}-${index}`,
        label: prediction.class,
        confidence: prediction.score,
        x: (clippedX / containerWidth) * 100,
        y: (clippedY / containerHeight) * 100,
        width: (width / containerWidth) * 100,
        height: (height / containerHeight) * 100,
      };
    };

    const loadModel = async () => {
      if (objectDetectionModelRef.current) {
        return objectDetectionModelRef.current;
      }

      const [, cocoSsd] = await Promise.all([import("@tensorflow/tfjs"), import("@tensorflow-models/coco-ssd")]);
      const model = await cocoSsd.load({ base: "mobilenet_v2" });
      objectDetectionModelRef.current = model;
      return model;
    };

    const detectObjects = async () => {
      const video = sourceVideoRef.current;
      if (cancelled || !video || video.readyState < 2 || !video.videoWidth || !video.videoHeight) {
        scheduleNextDetection(180);
        return;
      }

      try {
        const model = await loadModel();
        if (cancelled) return;
        const predictions = await model.detect(video, 10, 0.25);
        if (cancelled) return;
        setObjectDetections(
          predictions
            .map(mapPredictionToDetection)
            .filter((detection): detection is ObjectDetectionBox => Boolean(detection))
        );
      } catch {
        if (!cancelled) {
          setObjectDetections([]);
        }
        return;
      }

      scheduleNextDetection();
    };

    void detectObjects();
    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [cameraEnabled, cameraSceneMode, cameraStream]);

  return (
    <article className={`tile candidate-tile ${cameraEnabled ? "camera-on" : ""} ${micListening ? "speaking" : ""}`}>
      <div className="tile-ambient tile-ambient-candidate" aria-hidden="true" />
      <span className="tile-badge">{displayName}</span>

      {cameraEnabled ? (
        <div className="candidate-preview-stage">
          <div className={`candidate-camera-shell is-${cameraSceneMode}`}>

            <video ref={sourceVideoRef} className="candidate-camera-source" autoPlay playsInline muted aria-hidden="true" />

            {/* Camera mode selector */}
            <div className="candidate-camera-modebar" aria-label="Camera background mode">
              <button
                type="button"
                className={`candidate-camera-mode ${cameraSceneMode === "normal" ? "is-active" : ""}`}
                onClick={() => setCameraSceneMode("normal")}
                aria-pressed={cameraSceneMode === "normal"}
              >
                Normal
              </button>
              <button
                type="button"
                className={`candidate-camera-mode ${cameraSceneMode === "blur" ? "is-active" : ""}`}
                onClick={() => setCameraSceneMode("blur")}
                aria-pressed={cameraSceneMode === "blur"}
              >
                Flou
              </button>
              <button
                type="button"
                className={`candidate-camera-mode ${cameraSceneMode === "background" ? "is-active" : ""}`}
                onClick={() => setCameraSceneMode("background")}
                aria-pressed={cameraSceneMode === "background"}
              >
                Fond
              </button>
            </div>

            {/* Background preset selector */}
            {cameraSceneMode === "background" ? (
              <div className="candidate-camera-background-bar" aria-label="Background presets">
                <button
                  type="button"
                  className={`candidate-camera-background-chip ${backgroundPreset === "office" ? "is-active" : ""}`}
                  onClick={() => setBackgroundPreset("office")}
                  aria-pressed={backgroundPreset === "office"}
                >
                  Violet
                </button>
                <button
                  type="button"
                  className={`candidate-camera-background-chip ${backgroundPreset === "meeting" ? "is-active" : ""}`}
                  onClick={() => setBackgroundPreset("meeting")}
                  aria-pressed={backgroundPreset === "meeting"}
                >
                  Bleu
                </button>
                <button
                  type="button"
                  className={`candidate-camera-background-chip ${backgroundPreset === "minimal" ? "is-active" : ""}`}
                  onClick={() => setBackgroundPreset("minimal")}
                  aria-pressed={backgroundPreset === "minimal"}
                >
                  Beige
                </button>
              </div>
            ) : null}

            {/* Display canvas when filters are active, otherwise show detection layer */}
            {cameraSceneMode === "normal" ? (
              <>
                <video ref={previewVideoRef} className="candidate-camera-preview" autoPlay playsInline muted />
                <CandidateDetectionLayer detections={objectDetections} />
              </>
            ) : (
              <div className="candidate-camera-stage">
                <canvas
                  ref={blurCanvasRef}
                  className="candidate-camera-preview candidate-camera-preview-canvas"
                  aria-label={`Camera preview with ${cameraSceneMode} effect`}
                />
                <CandidateDetectionLayer detections={objectDetections} />
                <span className="candidate-camera-blur-frame" aria-hidden="true" />
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="candidate-idle-shell">
          <div className="candidate-idle-stage">
            <span className="candidate-idle-orbit candidate-idle-orbit-a" aria-hidden="true" />
            <span className="candidate-idle-orbit candidate-idle-orbit-b" aria-hidden="true" />
            <span className="candidate-initial">{(displayName.slice(0, 1) || "S").toUpperCase()}</span>
          </div>
        </div>
      )}

      {cameraEnabled ? (
        <div className="candidate-analysis" aria-live={liveVisionEnabled ? "polite" : undefined}>
          <div className="candidate-analysis-header">
            <div className="candidate-analysis-copy">
              <span className="candidate-analysis-live">
                <span className="candidate-analysis-dot" aria-hidden="true" />
                {interviewEnded ? "Last analysis" : "Live analysis"}
              </span>
              <span className="candidate-analysis-caption">
                {interviewEnded ? "Face analysis stopped at the end of the interview." : analysis.message}
              </span>
            </div>
          </div>

          <div className="candidate-analysis-pills">
            <span className={`candidate-analysis-pill is-${analysis.faceDetected ? "good" : "bad"}`}>
              {analysis.faceDetected ? "Face detected" : "No face"}
            </span>
            <span className={`candidate-analysis-pill is-${analysis.lookingForward ? "good" : "warn"}`}>
              {analysis.multipleFaces ? "Multiple faces" : analysis.lookingForward ? "Looking forward" : "Looking away"}
            </span>
            <span className={`candidate-analysis-pill is-${analysis.centered ? "good" : "warn"}`}>
              {analysis.centered ? "Centered" : "Off-center"}
            </span>
          </div>

          <div className={`candidate-emotion-live is-${displayedLiveEmotion.dominantEmotion || "idle"}`}>
            <div className="candidate-emotion-live-header">
              <div className="candidate-emotion-live-copy">
                <span className="candidate-emotion-live-kicker">Emotion</span>
                <strong className="candidate-emotion-live-title">
                  {liveEmotion.status === "ready" ? formatLiveEmotionLabel(liveEmotion.dominantEmotion) : "Waiting ..."}
                </strong>
              </div>
              <div className="candidate-emotion-live-metrics">
                <span className="candidate-emotion-live-confidence">
                  {liveEmotion.confidence != null ? `${liveEmotion.confidence}% conf.` : "--"}
                </span>
                <span className="candidate-emotion-live-stress">
                  Stress {liveEmotion.stressSignal != null ? `${liveEmotion.stressSignal}%` : "--"}
                </span>
              </div>
            </div>
            <span className="candidate-emotion-live-summary">{liveEmotion.summary}</span>
            <div className="candidate-emotion-live-bars" aria-label="Live emotion probabilities">
              {LIVE_EMOTION_ORDER.map((label) => {
                const value = liveEmotion.probabilities[label];
                return (
                  <div key={label} className="candidate-emotion-live-bar">
                    <span className="candidate-emotion-live-bar-label">{formatLiveEmotionLabel(label)}</span>
                    <span className="candidate-emotion-live-bar-track" aria-hidden="true">
                      <span className={`candidate-emotion-live-bar-fill is-${label}`} style={{ width: `${value}%` }} />
                    </span>
                    <strong className="candidate-emotion-live-bar-value">{value}%</strong>
                  </div>
                );
              })}
            </div>
          </div>

        </div>
      ) : null}

      <div className="candidate-controls" aria-label="Candidate controls">
        <button
          type="button"
          className={`candidate-control camera-toggle ${cameraEnabled ? "active" : ""}`}
          aria-label={cameraEnabled ? "Stop camera" : "Start camera"}
          aria-pressed={cameraEnabled}
          disabled={sending || interviewEnded}
          onClick={() => {
            void onToggleCamera();
          }}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h7A2.5 2.5 0 0 1 16 8.5v7A2.5 2.5 0 0 1 13.5 18h-7A2.5 2.5 0 0 1 4 15.5Z" />
            <path d="m16 10 4-2.5v9L16 14" />
          </svg>
        </button>
        <button
          type="button"
          className={`candidate-control mic-toggle ${micListening ? "active" : ""}`}
          aria-label={!cvUploaded ? "Upload a CV before starting the microphone" : micListening ? "Stop microphone" : "Start microphone"}
          aria-pressed={micListening}
          disabled={!cvUploaded || sending || interviewEnded}
          onClick={onToggleMic}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 4a3 3 0 0 1 3 3v4a3 3 0 0 1-6 0V7a3 3 0 0 1 3-3Z" />
            <path d="M6.5 10.5a5.5 5.5 0 1 0 11 0" />
            <path d="M12 16v4" />
          </svg>
        </button>
        <button
          type="button"
          className="candidate-control end-call"
          aria-label={interviewEnded ? "Interview already ended" : "End interview"}
          disabled={interviewEnded}
          onClick={() => {
            void onEndCall();
          }}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M5 15c3-3 11-3 14 0" />
            <path d="M8 13l-2 3" />
            <path d="M16 13l2 3" />
          </svg>
        </button>
      </div>

    </article>
  );
}
