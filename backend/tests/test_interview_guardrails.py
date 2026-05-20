import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from orchestrator.guardrails import require_cv_uploaded_for_message
from interview_ai.llm_provider import StructuredInterviewIntelligence
from interview_ai.prompts import build_generation_messages, detect_response_language
from interview_ai.scoring import _heuristic_question_answer_score


class DummyInterviewIntelligence(StructuredInterviewIntelligence):
    def __init__(self):
        pass


CV_PROFILE = {
    "candidate_name": "Ahmed BEN Youssef",
    "headline": "Full-stack developer",
    "top_skills": ["React", "FastAPI", "PostgreSQL"],
    "projects": ["Dashboard RH avec React et FastAPI"],
    "experiences": ["Stage developpeur web"],
}

COURSE_CONTEXT = [
    "La blockchain contient des blocs relies par le hash du bloc precedent. "
    "Les noeuds valident les transactions et le consensus evite une autorite centrale.",
    "Bitcoin compare la rarete mathematique avec la flexibilite des monnaies fiat.",
]


class CvUploadSecurityTests(unittest.TestCase):
    def test_message_is_blocked_before_cv_upload(self):
        with self.assertRaises(HTTPException) as raised:
            require_cv_uploaded_for_message(SimpleNamespace(cv_uploaded=False))

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("CV", raised.exception.detail)

    def test_message_is_allowed_after_cv_upload(self):
        require_cv_uploaded_for_message(SimpleNamespace(cv_uploaded=True))


class InterviewQuestionGuardrailTests(unittest.TestCase):
    def setUp(self):
        self.intelligence = DummyInterviewIntelligence()

    def test_french_candidate_message_keeps_french_interview_language(self):
        self.assertEqual(detect_response_language("je suis prete de commencer"), "fr")

    def test_rejects_english_question_in_french_session(self):
        with self.assertRaisesRegex(ValueError, "anglais"):
            self.intelligence._validate_technical_question(
                question="What is a block in a blockchain?",
                recent_turns=[],
                phase="QUESTION_2",
                expected_language="fr",
                cv_profile=CV_PROFILE,
                cv_context=COURSE_CONTEXT,
            )

    def test_rejects_placeholder_question(self):
        with self.assertRaisesRegex(ValueError, "placeholder"):
            self.intelligence._validate_technical_question(
                question="Une seule question technique ?",
                recent_turns=[],
                phase="QUESTION_2",
                expected_language="fr",
                cv_profile=CV_PROFILE,
                cv_context=COURSE_CONTEXT,
            )

    def test_question_one_must_be_personalized_from_cv(self):
        question = self.intelligence._validate_technical_question(
            question=(
                "Bonjour Ahmed BEN Youssef, dans votre CV vous mentionnez React "
                "et un dashboard RH. Quel choix technique concret avez-vous fait ?"
            ),
            recent_turns=[],
            phase="QUESTION_1",
            expected_language="fr",
            cv_profile=CV_PROFILE,
            cv_context=COURSE_CONTEXT,
        )

        self.assertTrue(question.startswith("Bonjour Ahmed"))
        self.assertIn("React", question)

    def test_course_questions_do_not_accept_cv_topics_after_question_one(self):
        with self.assertRaisesRegex(ValueError, "contexte|cours"):
            self.intelligence._validate_technical_question(
                question="Bonjour Ahmed, pouvez-vous expliquer votre projet React du CV ?",
                recent_turns=[],
                phase="QUESTION_2",
                expected_language="fr",
                cv_profile=CV_PROFILE,
                cv_context=COURSE_CONTEXT,
            )

    def test_course_question_is_accepted_after_question_one(self):
        question = self.intelligence._validate_technical_question(
            question=(
                "Comment un bloc utilise-t-il le hash du bloc precedent "
                "pour securiser la blockchain ?"
            ),
            recent_turns=[],
            phase="QUESTION_2",
            expected_language="fr",
            cv_profile=CV_PROFILE,
            cv_context=COURSE_CONTEXT,
        )

        self.assertIn("blockchain", question.lower())

    def test_fallback_first_question_uses_candidate_name_and_cv(self):
        question = self.intelligence._build_cv_grounded_fallback_question(
            lang="fr",
            cv_profile=CV_PROFILE,
            cv_context=COURSE_CONTEXT,
            recent_turns=[],
        )

        self.assertTrue(question.startswith("Bonjour Ahmed BEN Youssef"))
        self.assertIn("CV", question)

    def test_fallback_course_question_avoids_cv_after_first_question(self):
        question = self.intelligence._build_course_grounded_fallback_question(
            lang="fr",
            phase="QUESTION_3",
            cv_context=COURSE_CONTEXT,
            recent_turns=[],
        )

        self.assertNotIn("React", question)
        self.assertNotIn("CV", question)
        self.assertIn("bloc", question.lower())

    def test_prompt_rules_lock_one_cv_question_then_three_course_questions(self):
        q1_messages = build_generation_messages(
            session_id="unit",
            candidate_name="Ahmed BEN Youssef",
            phase="QUESTION_1",
            lang="fr",
            text="je suis pret de commencer",
            recent_turns=[],
            cv_profile=CV_PROFILE,
            rag_context=COURSE_CONTEXT,
        )
        q2_messages = build_generation_messages(
            session_id="unit",
            candidate_name="Ahmed BEN Youssef",
            phase="QUESTION_2",
            lang="fr",
            text="reponse candidat",
            recent_turns=[],
            cv_profile=CV_PROFILE,
            rag_context=COURSE_CONTEXT,
        )

        q1_prompt = " ".join(message["content"] for message in q1_messages)
        q2_prompt = " ".join(message["content"] for message in q2_messages)

        self.assertIn("QUESTION_1: commence par Bonjour + nom du candidat", q1_prompt)
        self.assertIn("question technique sur le CV", q1_prompt)
        self.assertIn("strictement sur le contenu du cours", q2_prompt)
        self.assertNotIn("Every interview question must be about the CV", q2_prompt)


class ScoringGuardrailTests(unittest.TestCase):
    def test_blockchain_answer_with_core_concepts_scores_at_least_three(self):
        score = _heuristic_question_answer_score(
            "Qu'est-ce qu'un bloc dans la blockchain et quel role joue-t-il ?",
            (
                "Un bloc contient des transactions, son propre hash et le hash du bloc precedent. "
                "Si on modifie une transaction, le hachage change, la chaine devient incoherente "
                "et les noeuds du reseau refusent le bloc pendant la validation."
            ),
        )

        self.assertGreaterEqual(score, 3)


if __name__ == "__main__":
    unittest.main()
