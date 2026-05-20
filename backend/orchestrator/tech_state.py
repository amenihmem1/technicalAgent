from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


PhaseType = Literal["QUESTION_1", "QUESTION_2", "QUESTION_3", "QUESTION_4", "FINAL"]


@dataclass
class TechSessionState:
    session_id: str
    interview_max_questions: int = 4
    last_question_index: int = 0
    turns: list[dict[str, Any]] = field(default_factory=list)
    final_report: dict[str, Any] | None = None
    cv_profile: dict[str, Any] = field(default_factory=dict)
    cv_uploaded: bool = False
    documents: list[dict[str, Any]] = field(default_factory=list)
    response_language: Literal["fr", "en", ""] = ""
    audio_observations: dict[str, Any] = field(default_factory=dict)
    visual_observations: dict[str, Any] = field(default_factory=dict)
    interview_status: Literal["draft", "active", "finalized"] = "draft"
    finalized_at: str = ""
    finalized_by: str = ""
    preferred_input_mode: Literal["text", "voice", "mixed"] = "voice"
    cached_insights: dict[str, Any] = field(default_factory=dict)
    proctoring_events: list[dict[str, Any]] = field(default_factory=list)
