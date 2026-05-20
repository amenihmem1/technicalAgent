from __future__ import annotations

import logging
import time
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from orchestrator.tech_schemas import TechAgentOutput
from orchestrator.tech_state import PhaseType, TechSessionState
from orchestrator.tech_workflow_support import (
    FALLBACK_RETRY_MESSAGE,
    TechnicalWorkflowSupport,
    is_clarification_request,
    normalize_score_partial,
)

logger = logging.getLogger(__name__)


class TechnicalWorkflowState(TypedDict, total=False):
    session_id: str
    text: str
    candidate_name: str
    session: TechSessionState
    current_phase: PhaseType
    rag_context: list[str]
    rag_duration_ms: float
    llm_duration_ms: float
    persist_duration_ms: float
    output_payload: dict[str, Any]
    should_finalize: bool
    should_clarify: bool
    generated_output: TechAgentOutput
    final_output: TechAgentOutput
    latest_scores: dict[str, int] | None
    response_language: Literal["fr", "en"]


class LangGraphTechOrchestrator(TechnicalWorkflowSupport):
    """LangGraph-backed technical workflow that preserves the current public API."""

    def __init__(self, intelligence, tts, session_store=None, cv_rag_store=None, course_dir=None):
        super().__init__(
            intelligence=intelligence,
            tts=tts,
            session_store=session_store,
            cv_rag_store=cv_rag_store,
            course_dir=course_dir,
        )
        self._graph = self._build_graph()

    @staticmethod
    def _can_rephrase(session: TechSessionState) -> bool:
        if not session.turns:
            return False
        last_turn = session.turns[-1] if isinstance(session.turns[-1], dict) else {}
        question = str(last_turn.get("say", "") or "").strip()
        phase = str(last_turn.get("phase", "") or "").strip().upper()
        return bool(question and phase in TechnicalWorkflowSupport.PHASE_SEQUENCE)

    def _build_graph(self):
        workflow = StateGraph(TechnicalWorkflowState)
        workflow.add_node("load_session", self._node_load_session)
        workflow.add_node("return_existing_final", self._node_return_existing_final)
        workflow.add_node("rephrase", self._node_rephrase)
        workflow.add_node("retrieve_context", self._node_retrieve_context)
        workflow.add_node("generate_payload", self._node_generate_payload)
        workflow.add_node("validate_output", self._node_validate_output)
        workflow.add_node("persist_turn", self._node_persist_turn)
        workflow.add_node("speak_turn", self._node_speak_turn)
        workflow.add_node("ensure_final_report", self._node_ensure_final_report)
        workflow.add_node("build_final_output", self._node_build_final_output)
        workflow.add_node("speak_final_output", self._node_speak_final_output)

        workflow.add_edge(START, "load_session")
        workflow.add_conditional_edges(
            "load_session",
            self._route_after_load,
            {
                "return_existing_final": "return_existing_final",
                "rephrase": "rephrase",
                "retrieve_context": "retrieve_context",
                "ensure_final_report": "ensure_final_report",
            },
        )
        workflow.add_edge("retrieve_context", "generate_payload")
        workflow.add_edge("generate_payload", "validate_output")
        workflow.add_conditional_edges(
            "validate_output",
            self._route_after_validation,
            {
                "persist_turn": "persist_turn",
                "ensure_final_report": "ensure_final_report",
            },
        )
        workflow.add_conditional_edges(
            "persist_turn",
            self._route_after_persist,
            {
                "speak_turn": "speak_turn",
                "end": END,
            },
        )
        workflow.add_edge("ensure_final_report", "build_final_output")
        workflow.add_conditional_edges(
            "build_final_output",
            self._route_after_build_final_output,
            {
                "speak_final_output": "speak_final_output",
                "end": END,
            },
        )
        workflow.add_edge("return_existing_final", END)
        workflow.add_edge("rephrase", END)
        workflow.add_edge("speak_turn", END)
        workflow.add_edge("speak_final_output", END)
        return workflow.compile()

    def _node_load_session(self, state: TechnicalWorkflowState) -> TechnicalWorkflowState:
        session = self._get_or_create_session(state["session_id"])
        text = str(state.get("text", "") or "")
        return {
            "session": session,
            "current_phase": self._current_phase(session),
            "should_clarify": bool(self._can_rephrase(session) and is_clarification_request(text)),
            "should_finalize": len(session.turns) >= session.interview_max_questions,
        }

    @staticmethod
    def _route_after_load(state: TechnicalWorkflowState) -> str:
        session = state["session"]
        if session.final_report is not None:
            return "return_existing_final"
        if state.get("should_clarify"):
            return "rephrase"
        if state.get("should_finalize"):
            return "ensure_final_report"
        return "retrieve_context"

    def _node_return_existing_final(self, state: TechnicalWorkflowState) -> TechnicalWorkflowState:
        return {"final_output": self._build_final_output(state["session"])}

    def _node_rephrase(self, state: TechnicalWorkflowState) -> TechnicalWorkflowState:
        output = self._build_rephrase_output(
            state["session"],
            text=state["text"],
            candidate_name=state["candidate_name"],
        )
        if output is None:
            output = self._fallback_output(
                say=FALLBACK_RETRY_MESSAGE,
                phase=state["current_phase"],
                question_index=state["session"].last_question_index + 1,
                notes=["Reformulation indisponible"],
            )
        return {"final_output": output}

    def _node_retrieve_context(self, state: TechnicalWorkflowState) -> TechnicalWorkflowState:
        rag_context, rag_duration_ms = self._retrieve_rag_context(
            session_id=state["session_id"],
            query=state["text"],
            top_k=2,
            phase=state.get("current_phase", ""),
        )
        return {
            "current_phase": self._current_phase(state["session"]),
            "rag_context": rag_context,
            "rag_duration_ms": rag_duration_ms,
        }

    def _node_generate_payload(self, state: TechnicalWorkflowState) -> TechnicalWorkflowState:
        llm_start = time.perf_counter()
        current_phase = state["current_phase"]
        result = self.intelligence.generate(
            text=state["text"],
            candidate_name=state["candidate_name"],
            session_id=state["session_id"],
            session_state=self._build_llm_session_state(
                state["session"],
                text=state["text"],
                current_phase=current_phase,
                rag_context=state.get("rag_context", []),
            ),
        )
        return {
            "output_payload": result if isinstance(result, dict) else {},
            "llm_duration_ms": (time.perf_counter() - llm_start) * 1000,
        }

    def _node_validate_output(self, state: TechnicalWorkflowState) -> TechnicalWorkflowState:
        current_phase = state["current_phase"]
        output = self._validate_generated_output(
            raw_result=state.get("output_payload", {}),
            current_phase=current_phase,
            question_index=state["session"].last_question_index + 1,
            log_label="via LangGraph",
        )

        latest_scores = normalize_score_partial(output.score_partial) if output.phase == "FINAL" else None
        return {
            "generated_output": output,
            "latest_scores": latest_scores,
        }

    @staticmethod
    def _route_after_validation(state: TechnicalWorkflowState) -> str:
        output = state["generated_output"]
        return "ensure_final_report" if output.phase == "FINAL" else "persist_turn"

    @staticmethod
    def _route_after_persist(state: TechnicalWorkflowState) -> str:
        output = state["generated_output"]
        return "speak_turn" if output.say else "end"

    def _node_persist_turn(self, state: TechnicalWorkflowState) -> TechnicalWorkflowState:
        output = state["generated_output"]
        persist_start = time.perf_counter()
        self._save_turn(state["session"], state["text"], output)
        persist_duration = (time.perf_counter() - persist_start) * 1000

        logger.info(
            "Tour technique LangGraph | session=%s | phase=%s | rag=%.0fms | llm=%.0fms | persist=%.0fms | say=%d chars",
            state["session_id"],
            output.phase,
            float(state.get("rag_duration_ms", 0.0) or 0.0),
            float(state.get("llm_duration_ms", 0.0) or 0.0),
            persist_duration,
            len(output.say or ""),
        )
        return {
            "persist_duration_ms": persist_duration,
            "final_output": output,
        }

    def _node_speak_turn(self, state: TechnicalWorkflowState) -> TechnicalWorkflowState:
        output = state["generated_output"]
        if output.say:
            self.tts.speak(output.say)
        return {"final_output": output}

    def _node_ensure_final_report(self, state: TechnicalWorkflowState) -> TechnicalWorkflowState:
        session = state["session"]
        latest_text = state.get("text", "")
        response_language = self._resolve_language(session, latest_text)
        self._ensure_final_report(session, state.get("latest_scores"))
        logger.info(
            "Tour technique LangGraph | session=%s | phase=FINAL | rag=%.0fms | llm=%.0fms | final_report=yes",
            state["session_id"],
            float(state.get("rag_duration_ms", 0.0) or 0.0),
            float(state.get("llm_duration_ms", 0.0) or 0.0),
        )
        return {"response_language": response_language}

    def _node_build_final_output(self, state: TechnicalWorkflowState) -> TechnicalWorkflowState:
        session = state["session"]
        response_language = state.get("response_language", "fr")
        output = self._build_final_agent_output(
            session,
            lang=response_language,
        )
        self._save_turn(session, state.get("text", ""), output)
        self._persist_session(session)
        return {"final_output": output}

    @staticmethod
    def _route_after_build_final_output(state: TechnicalWorkflowState) -> str:
        output = state["final_output"]
        return "speak_final_output" if output.say else "end"

    def _node_speak_final_output(self, state: TechnicalWorkflowState) -> TechnicalWorkflowState:
        output = state["final_output"]
        if output.say:
            self.tts.speak(output.say)
        return {"final_output": output}

    def handle_candidate_text(
        self,
        session_id: str,
        text: str,
        candidate_name: str = "Candidat",
    ) -> TechAgentOutput:
        state = self._graph.invoke(
            {
                "session_id": session_id,
                "text": text,
                "candidate_name": candidate_name,
            }
        )
        output = state.get("final_output")
        if isinstance(output, TechAgentOutput):
            return output
        raise RuntimeError("LangGraph workflow completed without producing a TechAgentOutput.")
