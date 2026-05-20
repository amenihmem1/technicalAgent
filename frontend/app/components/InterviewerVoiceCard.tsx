"use client";

import { useEffect, useRef } from "react";

type InterviewerUtterance = {
  id: number;
  text: string;
  audioBase64?: string;
  audioMimeType?: string;
};

type InterviewerVoiceCardProps = {
  utterance: InterviewerUtterance | null;
  voiceEnabled: boolean;
  onAudioUtterance?: (utterance: InterviewerUtterance) => void;
};

export function InterviewerVoiceCard({
  utterance,
  voiceEnabled,
  onAudioUtterance,
}: InterviewerVoiceCardProps) {
  const lastUtteranceIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (!utterance || !utterance.text.trim()) {
      return;
    }
    if (lastUtteranceIdRef.current === utterance.id) {
      return;
    }

    lastUtteranceIdRef.current = utterance.id;

    if (voiceEnabled) {
      onAudioUtterance?.(utterance);
    }
  }, [onAudioUtterance, utterance, voiceEnabled]);

  return <div className="interviewer-voice-shell interviewer-runtime-shell" aria-live="polite" />;
}
