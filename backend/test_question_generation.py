#!/usr/bin/env python3
"""
Test script to generate example LLM questions from the current course material.

Usage:
    python test_question_generation.py

This script demonstrates how to:
1. Load course files from backend/data/course
2. Initialize the LLM intelligence provider
3. Generate a test technical question grounded in the course context
"""

import sys
from pathlib import Path

OK = "[OK]"
ERROR = "[ERROR]"
WARN = "[WARN]"
QUESTION = "[QUESTION]"
SEPARATOR = "-" * 80

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import load_settings
from core.factories import build_intelligence
from interview_ai.cv.profile_extractor import normalize_cv_text
from interview_ai.prompts import build_generation_messages


def _safe_text(value) -> str:
    text = str(value)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def _extract_pdf_text_for_test(raw: bytes) -> str:
    import io

    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            text = "\n".join((page.extract_text() or "") for page in pdf.pages)
        if text.strip():
            return text
    except Exception:
        pass

    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        raise ValueError("Impossible d'extraire le texte du PDF pour le test") from exc


def _extract_course_text_for_test(path: Path) -> str:
    raw = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return normalize_cv_text(_extract_pdf_text_for_test(raw))
    if suffix in {".txt", ".md"}:
        return normalize_cv_text(raw.decode("utf-8", errors="replace"))
    if suffix in {".doc", ".docx"}:
        from docx import Document
        import io

        doc = Document(io.BytesIO(raw))
        return normalize_cv_text("\n".join(paragraph.text for paragraph in doc.paragraphs))
    raise ValueError(f"Format non supporte pour le test: {path.suffix}")


def create_test_cv_profile():
    """Create a realistic CV profile for testing."""
    return {
        "candidate_name": "Jean Dupont",
        "headline": "Machine Learning Engineer - Python & Deep Learning",
        "email": "jean.dupont@example.com",
        "phone": "+33 6 12 34 56 78",
        "github": "https://github.com/jeandupont",
        "top_skills": [
            "Python",
            "TensorFlow",
            "PyTorch",
            "NLP",
            "Computer Vision",
            "FastAPI",
            "Docker",
        ],
        "experiences": [
            "3 years at TechCorp building ML pipelines for recommendation systems",
            "2 years at StartupAI working on NLP models for text classification",
        ],
        "projects": [
            "Built a CNN-based image classification system achieving 98% accuracy",
            "Developed a distributed training framework for large language models",
        ],
        "text_preview": "Senior ML Engineer with expertise in Deep Learning, NLP, and Computer Vision",
        "overall_confidence": 0.85,
    }


def _chunk_course_text(text: str, *, chunk_size: int = 700, limit: int = 8) -> list[str]:
    paragraphs = [item.strip() for item in text.split("\n\n") if len(item.strip()) >= 60]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = paragraph[:chunk_size].strip()
        if len(chunks) >= limit:
            break
    if current and len(chunks) < limit:
        chunks.append(current)
    return chunks[:limit]


def load_course_context() -> tuple[list[str], list[str]]:
    """Load course material from backend/data/course."""
    course_dir = Path(__file__).parent / "data" / "course"
    supported_suffixes = {".pdf", ".txt", ".md", ".doc", ".docx", ".png", ".jpg", ".jpeg", ".webp"}
    files = sorted(path for path in course_dir.iterdir() if path.is_file() and path.suffix.lower() in supported_suffixes)
    if not files:
        raise FileNotFoundError(f"No course file found in {course_dir}")

    chunks: list[str] = []
    filenames: list[str] = []
    for path in files:
        text = _extract_course_text_for_test(path)
        file_chunks = _chunk_course_text(text)
        if file_chunks:
            filenames.append(path.name)
            chunks.extend([f"[{path.name}] {chunk}" for chunk in file_chunks])

    if not chunks:
        raise ValueError(f"No readable course text found in {course_dir}")
    return chunks[:10], filenames


def test_question_generation(session_id: str, course_context: list[str], course_files: list[str], phase: str = "QUESTION_1", lang: str = "fr"):
    """
    Test the question generation pipeline.

    Args:
        session_id: The session ID to use
        phase: The interview phase (QUESTION_1, QUESTION_2, QUESTION_3, QUESTION_4, FINAL)
        lang: Language for question generation ('fr' for French, 'en' for English)
    """
    print(f"\n{'=' * 80}")
    print(f"Question Generation Test - Phase: {phase}")
    print(f"{'=' * 80}\n")

    print("[1] Loading configuration...")
    try:
        settings = load_settings()
    except Exception as e:
        print(f"{WARN} Could not load settings from .env: {e}")
        print("    Proceeding with defaults...\n")
        settings = None

    print("[2] Initializing LLM provider...")
    try:
        intelligence = build_intelligence(settings)
        llm_healthcheck = intelligence.healthcheck()
        if llm_healthcheck.get("ok"):
            print(f"{OK} LLM Provider: {_safe_text(llm_healthcheck.get('provider'))}")
            print(f"  Model: {_safe_text(llm_healthcheck.get('model'))}")
            print(f"  Endpoint: {_safe_text(llm_healthcheck.get('base_url'))}\n")
        else:
            print(f"{ERROR} LLM Provider unreachable: {_safe_text(llm_healthcheck.get('error'))}\n")
            return
    except Exception as e:
        print(f"{ERROR} Failed to initialize LLM: {_safe_text(e)}\n")
        return

    print("[3] Preparing test data...")
    cv_profile = create_test_cv_profile()
    rag_context = course_context
    candidate_name = cv_profile["candidate_name"]

    print(f"  Candidate: {candidate_name}")
    print(f"  Skills: {', '.join(cv_profile['top_skills'][:3])}...")
    print(f"  Course files: {', '.join(course_files)}")
    print(f"  Course context chunks: {len(rag_context)} extracts from current course\n")

    print("[4] Building LLM prompt...")
    _messages = build_generation_messages(
        session_id=session_id,
        candidate_name=candidate_name,
        phase=phase,
        lang=lang,
        text="Je suis pret pour commencer l'examen sur ce cours.",
        recent_turns=[
            {
                "phase": "QUESTION_1",
                "question_index": 0,
                "say": "Parlez-moi de votre experience avec le machine learning en general.",
                "answer": "J'ai travaille sur plusieurs projets de ML, notamment en NLP et computer vision.",
                "score_partial": {},
            }
        ] if phase != "QUESTION_1" else [],
        cv_profile=cv_profile,
        rag_context=rag_context,
    )

    print("  System prompt prepared")
    print("  User context prepared\n")

    print("[5] Calling LLM to generate question...")
    print("  Waiting for response...\n")

    try:
        result = intelligence.generate(
            text="Je suis pret pour commencer l'examen sur ce cours.",
            candidate_name=candidate_name,
            session_id=session_id,
            session_state={
                "phase": phase,
                "cv_profile": cv_profile,
                "cv_context": rag_context,
                "recent_turns": [
                    {
                        "phase": "QUESTION_1",
                        "question_index": 0,
                        "say": "Parlez-moi de votre experience avec le machine learning en general.",
                        "answer": "J'ai travaille sur plusieurs projets de ML, notamment en NLP et computer vision.",
                    }
                ] if phase != "QUESTION_1" else [],
                "response_language": lang,
            },
        )

        print(f"{'=' * 80}")
        print("Generated Question Result")
        print(f"{'=' * 80}\n")

        if result.get("say"):
            print(f"{QUESTION} {_safe_text(result['say'])}\n")
        else:
            print(f"{ERROR} No question generated\n")

        print("Details:")
        print(f"  Phase: {_safe_text(result.get('phase', 'N/A'))}")
        print(f"  Question Index: {_safe_text(result.get('question_index', 'N/A'))}")
        score = (result.get("score_partial") or {}).get("question_score", 0)
        print(f"  Question score: {_safe_text(score)}/5")
        print(f"  Notes: {_safe_text(result.get('notes', []))}")

        if result.get("final_report"):
            print("  Final Report Generated: Yes")

        return result

    except Exception as e:
        print(f"{ERROR} Error calling LLM: {_safe_text(e)}")
        print(f"  Type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Run the test suite."""
    print("\n" + "=" * 80)
    print("TECHNICAL INTERVIEW QUESTION GENERATOR - Current Course Test")
    print("=" * 80)

    try:
        course_context, course_files = load_course_context()
        print(f"{OK} Loaded course files: {_safe_text(course_files)}")
        print(f"  Extracts: {len(course_context)}\n")
    except Exception as e:
        print(f"{ERROR} Failed to load course material: {_safe_text(e)}\n")
        return

    session_id = "course-test-" + "-".join(Path(name).stem for name in course_files[:2])
    phases = ["QUESTION_1", "QUESTION_2", "QUESTION_3"]

    for idx, phase in enumerate(phases, 1):
        print(f"\n{SEPARATOR}")
        print(f"Test {idx}/{len(phases)}: {phase}")
        print(SEPARATOR)

        result = test_question_generation(
            session_id=session_id,
            course_context=course_context,
            course_files=course_files,
            phase=phase,
            lang="fr",
        )

        if result:
            print(f"\n{OK} Test {idx} completed successfully")
        else:
            print(f"\n{ERROR} Test {idx} failed")

        if idx < len(phases) and sys.stdin.isatty():
            input("\nPress Enter to continue to the next test...")

    print(f"\n{'=' * 80}")
    print("Test Suite Completed")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
