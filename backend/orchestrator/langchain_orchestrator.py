from __future__ import annotations

import logging
import time

from orchestrator.tech_schemas import TechAgentOutput
from orchestrator.tech_workflow_support import (
    TechnicalWorkflowSupport,
    is_clarification_request,
    normalize_score_partial,
)

logger = logging.getLogger(__name__)


class LangChainTechOrchestrator(TechnicalWorkflowSupport):
    """Linear LangChain-only runtime for the technical interview agent."""

    def handle_candidate_text(
        self,
        session_id: str,
        text: str,
        candidate_name: str = "Candidate",
    ) -> TechAgentOutput:
        session = self._get_or_create_session(session_id)
        clean_text = str(text or "").strip()

        if session.final_report is not None:
            return self._build_final_output(session)

        if is_clarification_request(clean_text):
            rephrased = self._build_rephrase_output(
                session,
                text=clean_text,
                candidate_name=candidate_name,
            )
            if rephrased is not None:
                return rephrased

        if len(session.turns) >= session.interview_max_questions:
            return self._finalize_interview(session, clean_text)

        current_phase = self._current_phase(session)
        rag_context, rag_duration_ms = self._retrieve_rag_context(
            session_id=session_id,
            query=clean_text,
            top_k=2,
            phase=current_phase,
        )

        llm_start = time.perf_counter()
        raw_result = self.intelligence.generate(
            text=clean_text,
            candidate_name=candidate_name,
            session_id=session_id,
            session_state=self._build_llm_session_state(
                session,
                text=clean_text,
                current_phase=current_phase,
                rag_context=rag_context,
            ),
        )
        llm_duration_ms = (time.perf_counter() - llm_start) * 1000

        output = self._validate_generated_output(
            raw_result=raw_result,
            current_phase=current_phase,
            question_index=session.last_question_index + 1,
            log_label="via LangChain",
        )

        if output.phase == "FINAL":
            latest_scores = normalize_score_partial(output.score_partial)
            return self._finalize_interview(session, clean_text, latest_scores)

        persist_start = time.perf_counter()
        self._save_turn(session, clean_text, output)
        persist_duration_ms = (time.perf_counter() - persist_start) * 1000

        logger.info(
            "Tour technique LangChain | session=%s | phase=%s | rag=%.0fms | llm=%.0fms | persist=%.0fms | say=%d chars",
            session_id,
            output.phase,
            float(rag_duration_ms or 0.0),
            float(llm_duration_ms or 0.0),
            float(persist_duration_ms or 0.0),
            len(output.say or ""),
        )

        if output.say:
            self.tts.speak(output.say)
        return output
