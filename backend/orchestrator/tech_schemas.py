from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

Phase = Literal["QUESTION_1", "QUESTION_2", "QUESTION_3", "QUESTION_4", "FINAL"]


class SkillEvidence(BaseModel):
    level: int = Field(ge=0, le=5)
    evidence: str = ""


class ScorePartial(BaseModel):
    question_score: int = Field(ge=0, le=5)


class FinalReport(BaseModel):
    score_total: int = Field(ge=0, le=100)
    competencies: ScorePartial
    strengths: List[str] = Field(default_factory=list)
    improvement_points: List[str] = Field(default_factory=list)
    dimension_actions: Dict[str, str] = Field(default_factory=dict)
    risks: List[str] = Field(default_factory=list)
    visual_signals: List[str] = Field(default_factory=list)
    visual_flags: List[str] = Field(default_factory=list)
    visual_metrics: Dict[str, Any] = Field(default_factory=dict)
    confidence_note: str = ""
    audio_signals: List[str] = Field(default_factory=list)
    audio_flags: List[str] = Field(default_factory=list)
    audio_metrics: Dict[str, Any] = Field(default_factory=dict)
    audio_confidence_note: str = ""
    recommendations: List[str] = Field(default_factory=list)
    advice: List[str] = Field(default_factory=list)
    summary: str = ""


class TechAgentOutput(BaseModel):
    say: str
    phase: Phase
    question_index: int = Field(ge=1, le=10)
    notes: List[str] = Field(default_factory=list)

    score_partial: ScorePartial

    final_report: Optional[FinalReport] = None
