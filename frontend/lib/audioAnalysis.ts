"use client";

export type CandidateAudioMetrics = {
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

const FILLER_PATTERN = /\b(euh+|hum+|uh+|um+|erm+)\b/gi;
const SILENCE_RMS_THRESHOLD = 0.012;
const MIN_PAUSE_FRAMES = 3;

function countWords(text: string) {
  return (text.trim().match(/\b[\p{L}\p{N}'’-]+\b/gu) || []).length;
}

function countFillers(text: string) {
  return (text.match(FILLER_PATTERN) || []).length;
}

function computeRms(values: Float32Array) {
  let sum = 0;
  for (let index = 0; index < values.length; index += 1) {
    const sample = values[index];
    sum += sample * sample;
  }
  return Math.sqrt(sum / Math.max(1, values.length));
}

function estimatePitch(window: Float32Array, sampleRate: number) {
  const rms = computeRms(window);
  if (rms < 0.01) {
    return 0;
  }

  const minLag = Math.floor(sampleRate / 320);
  const maxLag = Math.floor(sampleRate / 80);
  let bestLag = 0;
  let bestScore = 0;

  for (let lag = minLag; lag <= maxLag; lag += 1) {
    let correlation = 0;
    for (let index = 0; index < window.length - lag; index += 1) {
      correlation += window[index] * window[index + lag];
    }
    if (correlation > bestScore) {
      bestScore = correlation;
      bestLag = lag;
    }
  }

  if (!bestLag) {
    return 0;
  }
  return sampleRate / bestLag;
}

function summarizeBuckets(volumeScore: number, speechRateWpm: number, fillerCount: number, silenceRatio: number) {
  const energy_label = volumeScore >= 55 ? "elevated" : volumeScore >= 32 ? "steady" : "contained";
  const pace_label = speechRateWpm >= 170 ? "fast" : speechRateWpm > 0 && speechRateWpm <= 105 ? "measured" : "steady";
  const hesitation_label =
    fillerCount >= 4 || silenceRatio >= 0.22 ? "noticeable" : fillerCount >= 2 || silenceRatio >= 0.14 ? "moderate" : "light";

  return { energy_label, pace_label, hesitation_label };
}

export async function analyzeRecordedAudio(blob: Blob, transcript: string): Promise<CandidateAudioMetrics> {
  const metrics: CandidateAudioMetrics = {
    duration_seconds: 0,
    word_count: countWords(transcript),
    filler_count: countFillers(transcript),
    speech_rate_wpm: 0,
    volume_score: 0,
    silence_ratio: 0,
    pause_count: 0,
    pitch_hz: 0,
    pitch_variation_hz: 0,
    energy_label: "",
    pace_label: "",
    hesitation_label: "",
  };

  if (typeof window === "undefined") {
    return metrics;
  }

  try {
    const arrayBuffer = await blob.arrayBuffer();
    const audioContext = new window.AudioContext();
    try {
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer.slice(0));
      const channel = audioBuffer.getChannelData(0);
      const frameSize = Math.max(1024, Math.floor(audioBuffer.sampleRate * 0.08));
      const frameCount = Math.max(1, Math.floor(channel.length / frameSize));
      let rmsTotal = 0;
      let silentFrames = 0;
      let pauseCount = 0;
      let silentRunFrames = 0;
      let insidePause = false;
      const pitchValues: number[] = [];

      for (let frame = 0; frame < frameCount; frame += 1) {
        const start = frame * frameSize;
        const slice = channel.slice(start, Math.min(channel.length, start + frameSize));
        if (!slice.length) {
          continue;
        }
        const rms = computeRms(slice);
        rmsTotal += rms;
        const isSilent = rms < SILENCE_RMS_THRESHOLD;
        if (isSilent) {
          silentFrames += 1;
          silentRunFrames += 1;
          // Count a pause only once the silence is sustained for ~240 ms.
          if (!insidePause && silentRunFrames >= MIN_PAUSE_FRAMES) {
            pauseCount += 1;
            insidePause = true;
          }
        } else {
          silentRunFrames = 0;
          insidePause = false;
        }

        const pitch = estimatePitch(slice, audioBuffer.sampleRate);
        if (pitch >= 80 && pitch <= 320) {
          pitchValues.push(pitch);
        }
      }

      metrics.duration_seconds = Number(audioBuffer.duration.toFixed(2));
      const meanRms = rmsTotal / Math.max(1, frameCount);
      metrics.volume_score = Math.max(0, Math.min(100, Math.round(meanRms * 1500)));
      metrics.silence_ratio = Number((silentFrames / Math.max(1, frameCount)).toFixed(3));
      metrics.pause_count = pauseCount;
      if (pitchValues.length) {
        const avgPitch = pitchValues.reduce((sum, value) => sum + value, 0) / pitchValues.length;
        const variance =
          pitchValues.reduce((sum, value) => sum + (value - avgPitch) * (value - avgPitch), 0) / pitchValues.length;
        metrics.pitch_hz = Number(avgPitch.toFixed(1));
        metrics.pitch_variation_hz = Number(Math.sqrt(variance).toFixed(1));
      }
    } finally {
      await audioContext.close();
    }
  } catch {
    // Keep transcript-derived metrics even if browser audio decoding fails.
  }

  if (metrics.duration_seconds > 0 && metrics.word_count > 0) {
    metrics.speech_rate_wpm = Number(((metrics.word_count / metrics.duration_seconds) * 60).toFixed(1));
  }

  const buckets = summarizeBuckets(
    metrics.volume_score,
    metrics.speech_rate_wpm,
    metrics.filler_count,
    metrics.silence_ratio
  );
  metrics.energy_label = buckets.energy_label;
  metrics.pace_label = buckets.pace_label;
  metrics.hesitation_label = buckets.hesitation_label;
  return metrics;
}
