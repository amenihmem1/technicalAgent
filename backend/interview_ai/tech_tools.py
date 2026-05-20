from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Callable

from langchain_core.tools import StructuredTool

from interview_ai.prompts import (
    build_cv_anchor_terms,
    build_cv_summary,
    extract_relevant_phrase,
    normalize_cv_profile,
    select_behavior_anchor,
)
from interview_ai.scoring import infer_competencies_from_interview as infer_scores_payload
from interview_ai.scoring import score_interview_turn as score_turn_payload
from reporting.insights_builder import generate_insights_advice_text as generate_insights_payload
from reporting.report_builder import generate_final_report_text as generate_report_payload


@dataclass(slots=True)
class LangChainToolbox:
    context: StructuredTool
    cv_relevance: StructuredTool
    question_history_check: StructuredTool
    phase_strategy: StructuredTool
    turn_scoring: StructuredTool
    scoring: StructuredTool
    report: StructuredTool
    insights: StructuredTool


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _extract_candidate_facts(
    profile: dict[str, Any],
    current_text: str,
    recent_turns: list[dict[str, Any]],
) -> list[str]:
    facts: list[str] = []
    seen: set[str] = set()

    def add_fact(value: str) -> None:
        cleaned = _clean_text(value)
        if not cleaned:
            return
        lowered = cleaned.lower()
        if lowered in seen:
            return
        seen.add(lowered)
        facts.append(cleaned[:140])

    headline = _clean_text(profile.get("headline"))
    if headline:
        add_fact(f"Poste cible: {headline}")

    for skill in profile.get("top_skills", [])[:4]:
        cleaned = _clean_text(skill)
        if cleaned:
            add_fact(f"Competence CV: {cleaned}")

    for experience in profile.get("experiences", [])[:2]:
        cleaned = _clean_text(experience)
        if cleaned:
            add_fact(f"Experience CV: {cleaned}")

    for project in profile.get("projects", [])[:3]:
        cleaned = _clean_text(project)
        if cleaned:
            add_fact(f"Experience citee: {cleaned}")

    focus = extract_relevant_phrase(current_text)
    if focus:
        add_fact(f"Derniere reponse: {focus}")

    for turn in recent_turns[-3:]:
        if not isinstance(turn, dict):
            continue
        answer = _clean_text(turn.get("candidate_text", ""))
        if answer:
            add_fact(f"Historique candidat: {answer[:120]}")

    return facts[:8]


def build_technical_toolbox(
    *,
    request_json: Callable[..., dict[str, Any]],
    normalize_scores: Callable[[Any], dict[str, int]],
) -> LangChainToolbox:
    def prepare_interview_context(
        candidate_name: str,
        phase: str,
        current_text: str,
        cv_profile: dict[str, Any],
        rag_context: list[str],
        recent_turns: list[dict[str, Any]],
        session_id: str = "",
    ) -> dict[str, Any]:
        profile = normalize_cv_profile(cv_profile)
        recent_answers = [
            _clean_text(turn.get("candidate_text", ""))
            for turn in recent_turns[-3:]
            if isinstance(turn, dict)
        ]
        history_preview = " | ".join(answer[:120] for answer in recent_answers if answer[:120]) or "Aucun historique"
        anchors = build_cv_anchor_terms(profile, rag_context)
        best_anchor = select_behavior_anchor(
            profile,
            rag_context=rag_context,
            recent_turns=recent_turns,
            current_text=current_text,
            session_id=session_id,
        )
        if best_anchor:
            anchors = [best_anchor, *[anchor for anchor in anchors if anchor.lower() != best_anchor.lower()]]
        candidate_facts = _extract_candidate_facts(profile, current_text, recent_turns)
        return {
            "candidate_name": candidate_name.strip() or str(profile.get("candidate_name", "")).strip(),
            "phase": str(phase).strip().upper(),
            "cv_summary": build_cv_summary(profile),
            "anchors": anchors,
            "best_anchor": best_anchor,
            "focus_phrase": extract_relevant_phrase(current_text),
            "history_preview": history_preview,
            "candidate_facts": candidate_facts,
        }

    def cv_relevance(
        phase: str,
        current_text: str,
        cv_profile: dict[str, Any],
        rag_context: list[str],
        recent_turns: list[dict[str, Any]] | None = None,
        session_id: str = "",
    ) -> dict[str, Any]:
        profile = normalize_cv_profile(cv_profile)
        anchors = build_cv_anchor_terms(profile, rag_context)
        focus = extract_relevant_phrase(current_text)
        best_anchor = select_behavior_anchor(
            profile,
            rag_context=rag_context,
            recent_turns=recent_turns,
            current_text=current_text,
            session_id=session_id,
        )
        if best_anchor:
            anchors = [best_anchor, *[anchor for anchor in anchors if anchor.lower() != best_anchor.lower()]]
        return {
            "phase": _clean_text(phase).upper(),
            "best_anchor": best_anchor,
            "anchor_candidates": anchors[:5],
            "focus_phrase": focus,
            "grounding_advice": (
                f"Ancre la prochaine question sur '{best_anchor}'." if best_anchor else
                "Reste large et fidele au CV sans inventer de contexte."
            ),
        }

    def question_history_check(
        recent_turns: list[dict[str, Any]],
        proposed_question: str = "",
    ) -> dict[str, Any]:
        previous_questions = [
            _clean_text(turn.get("say", ""))
            for turn in recent_turns[-5:]
            if isinstance(turn, dict)
        ]
        normalized_proposed = _clean_text(proposed_question).lower()
        max_similarity = 0.0
        closest_question = ""
        for question in previous_questions:
            similarity = SequenceMatcher(None, normalized_proposed, question.lower()).ratio() if normalized_proposed else 0.0
            if similarity > max_similarity:
                max_similarity = similarity
                closest_question = question
        recent_topics = []
        for question in previous_questions:
            short = question[:90]
            if short:
                recent_topics.append(short)
        return {
            "recent_questions": recent_topics,
            "closest_question": closest_question,
            "max_similarity": round(max_similarity, 3),
            "avoid_repetition": bool(max_similarity >= 0.72) if normalized_proposed else False,
            "history_advice": (
                "Change clairement d'angle par rapport aux questions deja posees."
                if previous_questions else
                "Aucune repetition a eviter pour l'instant."
            ),
        }

    def phase_strategy(
        phase: str,
        current_text: str,
        recent_turns: list[dict[str, Any]],
        cv_profile: dict[str, Any],
    ) -> dict[str, Any]:
        profile = normalize_cv_profile(cv_profile)
        headline = _clean_text(profile.get("headline"))
        focus = extract_relevant_phrase(current_text)
        phase_name = _clean_text(phase).upper()
        if phase_name.startswith("QUESTION_"):
            question_index = int(phase_name.split("_")[-1] or 1)
            strategies = {
                1: {
                    "goal": "saluer le candidat par son nom puis poser une seule question technique personnalisee a partir du CV",
                    "natural_style": "bonjour + nom, puis question CV claire et concrete",
                    "avoid": "pas de question cours en QUESTION_1, pas de question RH, pas de techno inventee",
                },
                2: {
                    "goal": "poser une question technique strictement sur le cours",
                    "natural_style": "question cours claire, orientee comprehension ou application",
                    "avoid": "pas de question CV, pas de repetition de la premiere question, pas de generique vide",
                },
                3: {
                    "goal": "creuser les choix techniques, le debugging ou les compromis",
                    "natural_style": "question d'approfondissement technique, precise mais naturelle",
                    "avoid": "pas de sujet deconnecte du contexte, pas de question generique",
                },
                4: {
                    "goal": "terminer par une question de consolidation, recul ou mise en situation",
                    "natural_style": "question finale technique, utile pour verifier la maitrise",
                    "avoid": "pas de repetiton, pas d'invention, pas de sortie du contexte",
                },
            }
            payload = strategies.get(question_index, strategies[2]).copy()
            payload["phase"] = phase_name
            payload["headline"] = headline
            payload["focus_phrase"] = focus
            payload["turn_count"] = len(recent_turns)
            return payload

        strategies = {
            "QUESTION_1": {
                "goal": "saluer le candidat par son nom puis poser une seule question technique personnalisee a partir du CV",
                "natural_style": "bonjour + nom, puis question CV claire et concrete",
                "avoid": "pas de question cours en QUESTION_1, pas de question RH, pas de techno inventee",
            },
            "QUESTION_2": {
                "goal": "poser une question technique strictement sur le cours",
                "natural_style": "question cours claire, orientee comprehension ou application",
                "avoid": "pas de question CV, pas de repetition de la premiere question, pas de generique vide",
            },
            "QUESTION_3": {
                "goal": "creuser les choix techniques, le debugging ou les compromis",
                "natural_style": "question d'approfondissement technique, precise mais naturelle",
                "avoid": "pas de sujet deconnecte du contexte, pas de question generique",
            },
            "QUESTION_4": {
                "goal": "terminer par une question de consolidation, recul ou mise en situation",
                "natural_style": "question finale technique, utile pour verifier la maitrise",
                "avoid": "pas de repetiton, pas d'invention, pas de sortie du contexte",
            },
            "FINAL": {
                "goal": "clore et produire le rapport final",
                "natural_style": "aucune question supplementaire",
                "avoid": "say doit rester vide",
            },
        }
        payload = strategies.get(phase_name, strategies["QUESTION_2"]).copy()
        payload["phase"] = phase_name
        payload["headline"] = headline
        payload["focus_phrase"] = focus
        payload["turn_count"] = len(recent_turns)
        return payload

    def infer_interview_scores(
        cv_profile: dict[str, Any],
        turns: list[dict[str, Any]],
        response_language: str = "fr",
    ) -> dict[str, int]:
        return infer_scores_payload(
            request_json=request_json,
            normalize_scores=normalize_scores,
            cv_profile=cv_profile,
            turns=turns,
            response_language=response_language,
        )

    def score_single_turn(
        cv_profile: dict[str, Any],
        recent_turns: list[dict[str, Any]],
        question: str,
        answer: str,
        question_phase: str,
        response_language: str = "fr",
    ) -> dict[str, Any]:
        return score_turn_payload(
            request_json=request_json,
            normalize_scores=normalize_scores,
            cv_profile=cv_profile,
            recent_turns=recent_turns,
            question=question,
            answer=answer,
            question_phase=question_phase,
            response_language=response_language,
        )

    def build_final_report(
        competencies: dict[str, int],
        strengths: list[str],
        improvement_points: list[str],
        visual_context: dict[str, Any],
        audio_context: dict[str, Any],
        cv_profile: dict[str, Any],
        turns: list[dict[str, Any]],
        response_language: str = "fr",
    ) -> dict[str, Any]:
        return generate_report_payload(
            request_json=request_json,
            competencies=competencies,
            strengths=strengths,
            improvement_points=improvement_points,
            visual_context=visual_context,
            audio_context=audio_context,
            cv_profile=cv_profile,
            turns=turns,
            response_language=response_language,
        )

    def build_candidate_insights(
        visual_context: dict[str, Any],
        audio_context: dict[str, Any],
        stress_context: dict[str, Any],
        response_language: str = "fr",
    ) -> dict[str, Any]:
        return generate_insights_payload(
            request_json=request_json,
            visual_context=visual_context,
            audio_context=audio_context,
            stress_context=stress_context,
            response_language=response_language,
        )

    return LangChainToolbox(
        context=StructuredTool.from_function(
            func=prepare_interview_context,
            name="prepare_interview_context",
            description="Prepare un contexte structure pour l'entretien technique a partir du CV, du contexte RAG et des derniers tours candidat.",
        ),
        cv_relevance=StructuredTool.from_function(
            func=cv_relevance,
            name="cv_relevance",
            description="Evalue l'ancrage le plus pertinent entre CV, contexte RAG et derniere reponse candidat.",
        ),
        question_history_check=StructuredTool.from_function(
            func=question_history_check,
            name="question_history_check",
            description="Verifie les questions recentes pour limiter les repetitions et suggerer un nouvel angle.",
        ),
        phase_strategy=StructuredTool.from_function(
            func=phase_strategy,
            name="phase_strategy",
            description="Retourne l'objectif de la question technique courante, le style attendu et les interdits selon l'index d'entretien.",
        ),
        turn_scoring=StructuredTool.from_function(
            func=score_single_turn,
            name="score_single_turn",
            description="Calcule la note d'examen d'un seul tour candidat avec score_partial.question_score.",
        ),
        scoring=StructuredTool.from_function(
            func=infer_interview_scores,
            name="infer_interview_scores",
            description="Recalcule les scores techniques: architecture, optimisation, debugging et comprehension IA/LLM.",
        ),
        report=StructuredTool.from_function(
            func=build_final_report,
            name="build_final_report",
            description="Genere le payload JSON du rapport technique final a partir des signaux d'entretien.",
        ),
        insights=StructuredTool.from_function(
            func=build_candidate_insights,
            name="build_candidate_insights",
            description="Genere le payload JSON des insights visuels, vocaux et emotionnels du candidat.",
        ),
    )
