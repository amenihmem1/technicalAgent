from abc import ABC, abstractmethod
from typing import Dict, Any


class LLMRateLimitError(RuntimeError):
    """Raised when the upstream LLM provider rejects a request due to quota limits."""


class Intelligence(ABC):
    """
    Interface abstraite pour tous les moteurs d'intelligence (LLM).
    Tous les agents d'entretien et moteurs d'analyse doivent utiliser une implementation de cette classe.
    """

    @abstractmethod
    def generate(
        self,
        *,
        text: str,
        candidate_name: str,
        session_id: str,
        session_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Genere la reponse de l'agent sous forme de dictionnaire structure.

        Retourne obligatoirement :
        {
            "say": str,
            "phase": str,
            "question_index": int,
            "skills": dict,
            "score_partial": dict,
            "notes": list[str],
            "final_report": dict | None
        }
        """
        pass

    @abstractmethod
    def infer_competencies_from_interview(
        self,
        *,
        cv_profile: Dict[str, Any],
        turns: list[Dict[str, Any]],
        response_language: str = "fr",
    ) -> Dict[str, int]:
        """
        Re-evalue les competences a partir de l'historique complet d'entretien.
        """
        pass

    @abstractmethod
    def score_interview_turn(
        self,
        *,
        cv_profile: Dict[str, Any],
        recent_turns: list[Dict[str, Any]],
        question: str,
        answer: str,
        question_phase: str,
        response_language: str = "fr",
    ) -> Dict[str, Any]:
        """
        Evalue un seul tour d'entretien et retourne au minimum :
        {
            "score_partial": {...},
            "skills": {...}
        }
        """
        pass

    @abstractmethod
    def generate_final_report_text(
        self,
        *,
        competencies: Dict[str, int],
        strengths: list[str],
        improvement_points: list[str],
        visual_context: Dict[str, Any],
        audio_context: Dict[str, Any],
        cv_profile: Dict[str, Any],
        turns: list[Dict[str, Any]],
        response_language: str = "fr",
    ) -> Dict[str, Any]:
        """
        Genere le texte du rapport technique final sous forme de JSON structure.
        """
        pass

    @abstractmethod
    def generate_insights_advice(
        self,
        *,
        visual_context: Dict[str, Any],
        audio_context: Dict[str, Any],
        stress_context: Dict[str, Any],
        response_language: str = "fr",
    ) -> Dict[str, Any]:
        """
        Genere une synthese de conseils bienveillants dediee aux insights
        visuels, vocaux et emotionnels, sans reutiliser le rapport technique final.
        """
        pass
