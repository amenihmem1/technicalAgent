"use client";

import { RefObject, useEffect } from "react";
import { FilesetResolver, ImageSegmenter, type MPMask } from "@mediapipe/tasks-vision";

const WASM_BASE = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision/wasm";
const SEGMENTER_MODEL_PATH =
  "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter_landscape/float16/latest/selfie_segmenter_landscape.tflite";
const SEGMENTATION_INTERVAL_MS = 90;

let imageSegmenterPromise: Promise<ImageSegmenter> | null = null;

async function getImageSegmenter() {
  if (!imageSegmenterPromise) {
    imageSegmenterPromise = (async () => {
      const vision = await FilesetResolver.forVisionTasks(WASM_BASE);
      return ImageSegmenter.createFromOptions(vision, {
        baseOptions: { modelAssetPath: SEGMENTER_MODEL_PATH },
        runningMode: "VIDEO",
        outputConfidenceMasks: true,
        outputCategoryMask: false,
      });
    })();
  }

  return imageSegmenterPromise;
}

function drawSourceFrame(context: CanvasRenderingContext2D, video: HTMLVideoElement, width: number, height: number) {
  context.save();
  context.drawImage(video, 0, 0, width, height);
  context.restore();
}

function drawBlurredFrame(context: CanvasRenderingContext2D, video: HTMLVideoElement, width: number, height: number) {
  context.save();
  context.filter = "blur(18px) saturate(0.96) brightness(0.92)";
  context.drawImage(video, 0, 0, width, height);
  context.restore();
}

function roundRect(context: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number) {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.lineTo(x + width - radius, y);
  context.quadraticCurveTo(x + width, y, x + width, y + radius);
  context.lineTo(x + width, y + height - radius);
  context.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  context.lineTo(x + radius, y + height);
  context.quadraticCurveTo(x, y + height, x, y + height - radius);
  context.lineTo(x, y + radius);
  context.quadraticCurveTo(x, y, x + radius, y);
  context.closePath();
}

function buildMaskCanvas(mask: MPMask, scratchCanvas: HTMLCanvasElement) {
  const width = mask.width;
  const height = mask.height;
  if (!width || !height) return null;

  if (scratchCanvas.width !== width || scratchCanvas.height !== height) {
    scratchCanvas.width = width;
    scratchCanvas.height = height;
  }

  const context = scratchCanvas.getContext("2d");
  if (!context) return null;

  const confidence = mask.getAsFloat32Array();
  const imageData = context.createImageData(width, height);

  for (let index = 0; index < confidence.length; index += 1) {
    const alpha = Math.max(0, Math.min(255, Math.round(confidence[index] * 255)));
    const pixelIndex = index * 4;
    imageData.data[pixelIndex] = 255;
    imageData.data[pixelIndex + 1] = 255;
    imageData.data[pixelIndex + 2] = 255;
    imageData.data[pixelIndex + 3] = alpha;
  }

  context.putImageData(imageData, 0, 0);
  return scratchCanvas;
}

function fillRoundedRect(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
  fillStyle: string | CanvasGradient
) {
  context.save();
  context.fillStyle = fillStyle;
  roundRect(context, x, y, width, height, radius);
  context.fill();
  context.restore();
}

function drawOfficeBackground(context: CanvasRenderingContext2D, width: number, height: number) {
  const wallGradient = context.createLinearGradient(0, 0, 0, height);
  wallGradient.addColorStop(0, "#f7f0ff");
  wallGradient.addColorStop(0.48, "#f4ecff");
  wallGradient.addColorStop(1, "#eadff7");
  fillRoundedRect(context, 0, 0, width, height, 0, wallGradient);

  const glow = context.createRadialGradient(width * 0.5, height * 0.18, 12, width * 0.5, height * 0.18, width * 0.62);
  glow.addColorStop(0, "rgba(255,255,255,0.86)");
  glow.addColorStop(1, "rgba(255,255,255,0)");
  context.fillStyle = glow;
  context.fillRect(0, 0, width, height);

  fillRoundedRect(context, width * 0.12, height * 0.14, width * 0.76, height * 0.46, 22, "rgba(255,255,255,0.5)");
  fillRoundedRect(context, width * 0.18, height * 0.19, width * 0.22, height * 0.03, 999, "rgba(201,167,235,0.6)");
  fillRoundedRect(context, width * 0.18, height * 0.25, width * 0.18, height * 0.025, 999, "rgba(215,188,243,0.58)");
  fillRoundedRect(context, width * 0.58, height * 0.28, width * 0.18, height * 0.22, 18, "rgba(255,255,255,0.55)");
  fillRoundedRect(context, width * 0.22, height * 0.7, width * 0.56, height * 0.15, 22, "rgba(255,255,255,0.42)");
  fillRoundedRect(context, width * 0.26, height * 0.76, width * 0.28, height * 0.028, 999, "rgba(205,169,242,0.5)");
  fillRoundedRect(context, width * 0.58, height * 0.76, width * 0.13, height * 0.028, 999, "rgba(219,199,243,0.48)");

  context.fillStyle = "rgba(195,229,211,0.62)";
  context.beginPath();
  context.ellipse(width * 0.18, height * 0.82, width * 0.035, height * 0.09, -0.3, 0, Math.PI * 2);
  context.fill();
  context.beginPath();
  context.ellipse(width * 0.22, height * 0.84, width * 0.045, height * 0.12, 0.26, 0, Math.PI * 2);
  context.fill();
}

function drawMeetingBackground(context: CanvasRenderingContext2D, width: number, height: number) {
  const wallGradient = context.createLinearGradient(0, 0, width, height);
  wallGradient.addColorStop(0, "#eef3fb");
  wallGradient.addColorStop(0.5, "#e6ecf8");
  wallGradient.addColorStop(1, "#dce4f3");
  fillRoundedRect(context, 0, 0, width, height, 0, wallGradient);

  const panelGradient = context.createLinearGradient(width * 0.15, height * 0.14, width * 0.85, height * 0.44);
  panelGradient.addColorStop(0, "rgba(255,255,255,0.88)");
  panelGradient.addColorStop(1, "rgba(244,248,255,0.66)");
  fillRoundedRect(context, width * 0.14, height * 0.14, width * 0.72, height * 0.3, 24, panelGradient);

  fillRoundedRect(context, width * 0.2, height * 0.22, width * 0.2, height * 0.026, 999, "rgba(155,186,233,0.65)");
  fillRoundedRect(context, width * 0.2, height * 0.28, width * 0.3, height * 0.024, 999, "rgba(181,204,238,0.58)");
  fillRoundedRect(context, width * 0.2, height * 0.34, width * 0.17, height * 0.024, 999, "rgba(190,214,243,0.56)");

  fillRoundedRect(context, width * 0.24, height * 0.66, width * 0.52, height * 0.16, 34, "rgba(255,255,255,0.62)");
  fillRoundedRect(context, width * 0.26, height * 0.71, width * 0.48, height * 0.034, 999, "rgba(181,204,238,0.36)");
  fillRoundedRect(context, width * 0.31, height * 0.79, width * 0.14, height * 0.026, 999, "rgba(204,220,246,0.5)");
  fillRoundedRect(context, width * 0.56, height * 0.79, width * 0.12, height * 0.026, 999, "rgba(204,220,246,0.5)");

  context.strokeStyle = "rgba(169,190,226,0.34)";
  context.lineWidth = 2;
  context.beginPath();
  context.moveTo(width * 0.78, height * 0.17);
  context.lineTo(width * 0.78, height * 0.48);
  context.stroke();
}

function drawMinimalBackground(context: CanvasRenderingContext2D, width: number, height: number) {
  const baseGradient = context.createLinearGradient(0, 0, width, height);
  baseGradient.addColorStop(0, "#fbf7f2");
  baseGradient.addColorStop(0.56, "#f4eee6");
  baseGradient.addColorStop(1, "#ebe1d7");
  fillRoundedRect(context, 0, 0, width, height, 0, baseGradient);

  const aura = context.createRadialGradient(width * 0.22, height * 0.16, 8, width * 0.22, height * 0.16, width * 0.42);
  aura.addColorStop(0, "rgba(255,255,255,0.76)");
  aura.addColorStop(1, "rgba(255,255,255,0)");
  context.fillStyle = aura;
  context.fillRect(0, 0, width, height);

  fillRoundedRect(context, width * 0.13, height * 0.16, width * 0.74, height * 0.52, 26, "rgba(255,255,255,0.36)");
  fillRoundedRect(context, width * 0.24, height * 0.73, width * 0.52, height * 0.1, 999, "rgba(255,255,255,0.42)");
  fillRoundedRect(context, width * 0.3, height * 0.27, width * 0.25, height * 0.02, 999, "rgba(210,190,163,0.5)");
  fillRoundedRect(context, width * 0.3, height * 0.33, width * 0.18, height * 0.02, 999, "rgba(224,205,177,0.48)");

  context.fillStyle = "rgba(198,176,145,0.36)";
  context.beginPath();
  context.arc(width * 0.72, height * 0.26, width * 0.06, 0, Math.PI * 2);
  context.fill();
  context.beginPath();
  context.arc(width * 0.73, height * 0.26, width * 0.032, 0, Math.PI * 2);
  context.fillStyle = "rgba(255,255,255,0.26)";
  context.fill();
}

function drawPresetBackground(
  context: CanvasRenderingContext2D,
  preset: "office" | "meeting" | "minimal",
  width: number,
  height: number
) {
  if (preset === "meeting") {
    drawMeetingBackground(context, width, height);
    return;
  }

  if (preset === "minimal") {
    drawMinimalBackground(context, width, height);
    return;
  }

  drawOfficeBackground(context, width, height);
}

export function useCandidateBackgroundBlur(
  videoRef: RefObject<HTMLVideoElement>,
  canvasRef: RefObject<HTMLCanvasElement>,
  mode: "blur" | "background" | null,
  backgroundPreset: "office" | "meeting" | "minimal" = "office"
) {
  useEffect(() => {
    if (!mode) {
      const canvas = canvasRef.current;
      const context = canvas?.getContext("2d");
      if (canvas && context) {
        context.clearRect(0, 0, canvas.width, canvas.height);
      }
      return;
    }

    let cancelled = false;
    let frameId = 0;
    let lastSegmentedAt = 0;
    const scratchCanvas = document.createElement("canvas");

    const run = async () => {
      try {
        const segmenter = await getImageSegmenter();
        if (cancelled) return;

        const tick = () => {
          if (cancelled) return;

          const video = videoRef.current;
          const canvas = canvasRef.current;
          const context = canvas?.getContext("2d");
          const now = performance.now();

          if (
            !video ||
            !canvas ||
            !context ||
            video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA ||
            video.videoWidth <= 0 ||
            video.videoHeight <= 0
          ) {
            frameId = window.requestAnimationFrame(tick);
            return;
          }

          if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
          }

          if (now - lastSegmentedAt < SEGMENTATION_INTERVAL_MS) {
            frameId = window.requestAnimationFrame(tick);
            return;
          }

          lastSegmentedAt = now;

          let result = null;
          try {
            result = segmenter.segmentForVideo(video, now);
            const mask = result.confidenceMasks?.[0];
            const maskCanvas = mask ? buildMaskCanvas(mask, scratchCanvas) : null;

            if (!maskCanvas) {
              context.clearRect(0, 0, canvas.width, canvas.height);
              drawSourceFrame(context, video, canvas.width, canvas.height);
              frameId = window.requestAnimationFrame(tick);
              return;
            }

            context.clearRect(0, 0, canvas.width, canvas.height);
            if (mode === "background") {
              drawPresetBackground(context, backgroundPreset, canvas.width, canvas.height);
            } else {
              drawBlurredFrame(context, video, canvas.width, canvas.height);
            }
            context.globalCompositeOperation = "destination-out";
            context.drawImage(maskCanvas, 0, 0, canvas.width, canvas.height);
            context.globalCompositeOperation = "destination-over";
            drawSourceFrame(context, video, canvas.width, canvas.height);
            context.globalCompositeOperation = "source-over";
          } catch {
            context.clearRect(0, 0, canvas.width, canvas.height);
            drawSourceFrame(context, video, canvas.width, canvas.height);
          } finally {
            result?.close();
          }

          frameId = window.requestAnimationFrame(tick);
        };

        frameId = window.requestAnimationFrame(tick);
      } catch {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        const context = canvas?.getContext("2d");
        if (video && canvas && context && video.videoWidth > 0 && video.videoHeight > 0) {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          context.clearRect(0, 0, canvas.width, canvas.height);
          drawSourceFrame(context, video, canvas.width, canvas.height);
        }
      }
    };

    void run();

    return () => {
      cancelled = true;
      if (frameId) {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, [backgroundPreset, canvasRef, mode, videoRef]);
}
