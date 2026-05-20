"use client";

import type { InputMode } from "../../lib/sessionRuntime";

type InputModeSelectorProps = {
  disabled?: boolean;
  value: InputMode;
  onChange: (value: InputMode) => void;
};

const OPTIONS: Array<{ value: InputMode; label: string; description: string }> = [
  { value: "voice", label: "Micro", description: "Reponses uniquement au micro." },
];

export function InputModeSelector({ disabled = false, value, onChange }: InputModeSelectorProps) {
  return (
    <div className="input-mode-selector" aria-label="Interview input mode">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`input-mode-chip ${value === option.value ? "is-active" : ""}`}
          onClick={() => onChange(option.value)}
          disabled={disabled}
          aria-pressed={value === option.value}
          title={option.description}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
