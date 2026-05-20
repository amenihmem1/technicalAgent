from __future__ import annotations

import io
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Pattern

from interview_ai.cv.contact_utils import (
    EMAIL_OCR_PATTERN,
    EMAIL_PATTERN,
    GITHUB_PATTERN,
    LINKEDIN_PATTERN,
    PHONE_PATTERN,
    normalize_contact_search_text,
)
from interview_ai.cv.ocr_extractor import extract_image_text_with_ocr, extract_pdf_text_with_ocr


@dataclass(frozen=True)
class CandidateInfo:
    name: str
    headline: str
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    top_skills: list[str] = field(default_factory=list)
    experiences: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    confidence: dict[str, float] = field(default_factory=dict)
    overall_confidence: float = 0.0
    text_preview: str = ""
    source_filename: str = ""


SKILL_PATTERNS = frozenset(
    {
        "python",
        "django",
        "fastapi",
        "flask",
        "react",
        "angular",
        "vue",
        "javascript",
        "typescript",
        "node",
        "java",
        "spring",
        "spring boot",
        "php",
        "laravel",
        "sql",
        "mysql",
        "postgresql",
        "mongodb",
        "html",
        "css",
        "docker",
        "kubernetes",
        "aws",
        "azure",
        "git",
        "github actions",
        "jenkins",
        "rest",
        "api",
        "websockets",
        "agile",
        "scrum",
        "devops",
        "ci/cd",
        "terraform",
        "ansible",
    }
)

HEADLINE_HINTS = frozenset(
    {
        "analyst",
        "analyste",
        "developpeur",
        "developpeuse",
        "developer",
        "ingenieur",
        "engineer",
        "full stack",
        "fullstack",
        "frontend",
        "back-end",
        "backend",
        "software",
        "web",
        "mobile",
        "data",
        "dev",
        "architecte",
        "finance",
        "financial",
        "tax",
        "taxation",
        "compliance",
    }
)

COMMON_REJECT_MARKERS = frozenset(
    {
        "langages:",
        "frontend:",
        "frontend :",
        "backend:",
        "backend :",
        "bases de donnees",
        "base de donnees",
        "database",
        "competences techniques",
        "skills",
    }
)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
NAME_WORD_PATTERN = re.compile(r"[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'-]+")
EXPERIENCE_SECTION_START_RE = re.compile(
    r"^(exp[ée]riences?\s+professionnelles?|professional\s+experiences?|experience|parcou[ru]s?\s+professionnel)\b",
    re.IGNORECASE,
)
EXPERIENCE_SECTION_STOP_RE = re.compile(
    r"^(comp[ée]tences|skills|formations?|education|langues|languages?|projets?|projects?|experience\s+associative|interets?|hobbies)\b",
    re.IGNORECASE,
)
PROJECT_SECTION_START_RE = re.compile(
    r"^(projets?\s+acad[ée]miques?|projets?|projects?)\b",
    re.IGNORECASE,
)
PROJECT_SECTION_STOP_RE = re.compile(
    r"^(a\s+propos|about|formations?|education|comp[ée]tences|skills|langues|certifications?|experience\s+associative|interets?|hobbies)\b",
    re.IGNORECASE,
)
SECTION_HEADER_RE = re.compile(
    r"^(contact|formation|formations|education|competences|comp[ée]tences|skills|langues|languages|certifications?|"
    r"interets?|hobbies|experience\s+associative|exp[ée]riences?\s+professionnelles?|parcou[ru]s?\s+professionnel|"
    r"professional\s+experiences?|projets?\s+acad[ée]miques?|projets?|projects?)\b.*$",
    re.IGNORECASE,
)
PROJECT_CONTENT_MARKERS = (
    "projet",
    "application",
    "plateforme",
    "dashboard",
    "systeme",
    "solution",
    "chatbot",
    "module",
    "microservices",
    "developpement",
    "conception",
    "implementation",
)
EXPERIENCE_CONTENT_MARKERS = (
    "stage",
    "developer",
    "developpeur",
    "développeur",
    "engineer",
    "ingenieur",
    "ingénieur",
    "societe",
    "société",
    "entreprise",
    "fullstack",
    "full stack",
    "base de donnees",
    "base de données",
)
ROLE_LABEL_PATTERNS = (
    re.compile(r"\bsenior\s+finance\s+analyst\b", re.IGNORECASE),
    re.compile(r"\bsenior\s+financial\s+analyst\b", re.IGNORECASE),
    re.compile(r"\bjunior\s+financial\s+analyst\b", re.IGNORECASE),
    re.compile(r"\bfinancial\s+analyst\b", re.IGNORECASE),
    re.compile(r"\banalyste\s+financier(?:e)?\s+senior\b", re.IGNORECASE),
    re.compile(r"\banalyste\s+financier(?:e)?\b", re.IGNORECASE),
    re.compile(r"\bfull[-\s]*stack\s+web\s+developer\b", re.IGNORECASE),
    re.compile(r"\bfull[-\s]*stack\s+developer\b", re.IGNORECASE),
    re.compile(r"\bjunior\s+web\s+developer\b", re.IGNORECASE),
    re.compile(r"\bweb\s+developer\b", re.IGNORECASE),
    re.compile(r"\bd[ée]veloppeur\s+full\s*stack\b", re.IGNORECASE),
    re.compile(r"\bd[ée]veloppeur\s+fullstack\b", re.IGNORECASE),
    re.compile(r"\bd[ée]veloppeur\s+de\s+base\s*de\s+donn[ée]es\b", re.IGNORECASE),
    re.compile(r"\bd[ée]veloppeur\b", re.IGNORECASE),
    re.compile(r"\bchef\s+de\s+partie\b", re.IGNORECASE),
    re.compile(r"\bc(?:hef|lef)\s+d[ec]\s+parti[ei][ec]?\b", re.IGNORECASE),
    re.compile(r"\bcuisinier\b", re.IGNORECASE),
    re.compile(r"\btraductrice\s+stagiaire\b", re.IGNORECASE),
    re.compile(r"\bassistante\s+de\s+direction\s+stagiaire\b", re.IGNORECASE),
    re.compile(r"\b(?:stag[eé]|stage)\s+job\s+[ée]tudia\w*\b", re.IGNORECASE),
    re.compile(r"\b[ée]tudiante?\s+en\s+cycle\s+d[' ]?ingenieur\b", re.IGNORECASE),
    re.compile(r"\b[ée]tudiante?\s+en\s+ing[ée]nierie\s+informatique\b", re.IGNORECASE),
)
DATE_CHUNK_RE = re.compile(
    r"\b(?:\d{2}[/-]\d{4}|\d{4}|\d{2}/\d{4}\s*[~-]\s*\d{2}/\d{4}|"
    r"janvier|fevrier|février|mars|avril|mai|juin|juillet|aout|août|septembre|octobre|novembre|decembre|décembre|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|actuel|present)\b",
    re.IGNORECASE,
)
COMPANY_CONTEXT_HINTS = (
    "hotel",
    "hôtel",
    "restaurant",
    "société",
    "societe",
    "services",
    "solutions",
    "steg",
    "edf",
    "paris",
    "tunis",
    "biarritz",
    "monastir",
    "medenine",
)
EXPERIENCE_SUMMARY_REJECT_MARKERS = (
    "ans d'exp",
    "years of exp",
    "je suis en mesure",
    "je peux",
    "confirme en accueil",
)
EXPERIENCE_CONTEXT_BREAK_MARKERS = (
    " prepar",
    " confection",
    " assurer",
    " garantir",
    " organise",
    " accueil",
    " gestion",
    " service",
)
PROJECT_REJECT_MARKERS = (
    "a propos",
    "actuellement a la recherche",
    "au sein d'une equipe dynamique",
    "competences",
    "frameworks",
    "langages de programmation",
    "outils devops",
    "methodologies",
    "technologies utilisees",
)
TITLE_LOWERCASE_WORDS = frozenset({"de", "du", "des", "en", "et", "la", "le", "les", "d"})
TITLE_SPECIAL_CASING = {
    "aws": "AWS",
    "ci/cd": "CI/CD",
    "devops": "DevOps",
    "full-stack": "Full-Stack",
    "fullstack": "FullStack",
    "github": "GitHub",
    "hr": "HR",
    "qa": "QA",
    "sap": "SAP",
    "ui/ux": "UI/UX",
}
INLINE_STRIP_CHARS = " -|,;:"
SECTION_LINE_STRIP_CHARS = " -|*"
HEADER_TITLE_START_TOKENS = frozenset(
    {
        "analyst",
        "analyste",
        "compliance",
        "developer",
        "developpeur",
        "developpeuse",
        "engineer",
        "finance",
        "financial",
        "ingenieur",
        "junior",
        "lead",
        "principal",
        "senior",
        "tax",
        "taxation",
    }
)
TEXT_ARTIFACT_REPLACEMENTS = (
    ("Ã©", "é"),
    ("Ã¨", "è"),
    ("Ãª", "ê"),
    ("Ã«", "ë"),
    ("Ã€", "À"),
    ("Ã ", "à"),
    ("Ã¢", "â"),
    ("Ã®", "î"),
    ("Ã¯", "ï"),
    ("Ã´", "ô"),
    ("Ã¶", "ö"),
    ("Ã¹", "ù"),
    ("Ã»", "û"),
    ("Ã¼", "ü"),
    ("Ã§", "ç"),
    ("Å“", "œ"),
    ("Å’", "Œ"),
    ("â€™", "'"),
    ("â€˜", "'"),
    ("â€œ", '"'),
    ("â€", '"'),
    ("â€“", "–"),
    ("â€”", "—"),
    ("Â", ""),
)


def extract_text_from_cv(filename: str, raw: bytes, *, logger: logging.Logger | None = None) -> str:
    suffix = Path(filename).suffix.lower()

    try:
        if suffix == ".pdf":
            extracted = _extract_pdf_text(raw)
            if _is_meaningful_text(extracted):
                return extracted
            return extract_pdf_text_with_ocr(raw)

        if suffix in IMAGE_SUFFIXES:
            return extract_image_text_with_ocr(raw)

        if suffix in {".doc", ".docx"}:
            from docx import Document

            doc = Document(io.BytesIO(raw))
            return "\n".join(paragraph.text for paragraph in doc.paragraphs)

        return raw.decode("utf-8", errors="replace")
    except Exception as exc:
        if logger is not None:
            logger.exception("Echec extraction %s", filename)
        raise ValueError(f"Impossible d'extraire le texte de {filename}") from exc


def normalize_cv_text(text: str) -> str:
    text = _normalize_text_artifacts(text)
    text = text.replace("\u25a0", "-").replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_text_artifacts(text: str) -> str:
    normalized = str(text or "")
    for source, target in TEXT_ARTIFACT_REPLACEMENTS:
        normalized = normalized.replace(source, target)
    return normalized


def _clean_inline_text(text: str, *, strip_chars: str = INLINE_STRIP_CHARS) -> str:
    return " ".join(str(text).split()).strip(strip_chars)


def _normalize_inline_text(text: str, *, strip_chars: str = INLINE_STRIP_CHARS) -> str:
    return _normalize_text_artifacts(_clean_inline_text(text, strip_chars=strip_chars))


def _fold_ascii_text(text: str) -> str:
    normalized = _normalize_text_artifacts(text)
    folded = unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")
    return folded.lower()


def _extract_pdf_text(raw: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


def _is_meaningful_text(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 40:
        return False
    alnum_count = sum(char.isalnum() for char in stripped)
    return alnum_count >= 24


def extract_candidate_info(text: str, filename: str) -> CandidateInfo:
    text = _normalize_text_artifacts(text)
    lines = [_clean_inline_text(line, strip_chars=SECTION_LINE_STRIP_CHARS) for line in text.splitlines() if line.strip()]
    contact_text = normalize_contact_search_text(text)
    experiences = _extract_experiences(text)
    header_name, header_headline = _extract_header_identity(lines)
    name = header_name or _guess_name(lines)
    headline = header_headline or _guess_headline(lines, experiences)
    email = _extract_email(contact_text)
    phone = _extract_phone(contact_text)
    linkedin = _extract_social_link(contact_text, provider="linkedin")
    github = _extract_social_link(contact_text, provider="github")
    top_skills = _extract_top_skills(text)
    projects = _extract_projects(text)
    confidence = _build_field_confidence(
        text=text,
        name=name,
        headline=headline,
        email=email,
        phone=phone,
        linkedin=linkedin,
        github=github,
        top_skills=top_skills,
        experiences=experiences,
        projects=projects,
    )

    return CandidateInfo(
        name=name,
        headline=headline,
        email=email,
        phone=phone,
        linkedin=linkedin,
        github=github,
        top_skills=top_skills,
        experiences=experiences,
        projects=projects,
        confidence=confidence,
        overall_confidence=_compute_overall_confidence(confidence),
        text_preview=(text[:600] + "...") if len(text) > 600 else text,
        source_filename=filename,
    )


def _extract_first(pattern: Pattern[str], text: str) -> str:
    match = pattern.search(text)
    return match.group(0).strip() if match else ""


def _build_field_confidence(
    *,
    text: str,
    name: str,
    headline: str,
    email: str,
    phone: str,
    linkedin: str,
    github: str,
    top_skills: list[str],
    experiences: list[str],
    projects: list[str],
) -> dict[str, float]:
    return {
        "name": _score_name_confidence(name),
        "headline": _score_headline_confidence(headline),
        "email": _score_email_confidence(email),
        "phone": _score_phone_confidence(phone),
        "linkedin": _score_social_confidence(linkedin, provider="linkedin"),
        "github": _score_social_confidence(github, provider="github"),
        "top_skills": _score_list_confidence(top_skills, ideal_count=5, min_item_length=2),
        "experiences": _score_list_confidence(experiences, ideal_count=2, min_item_length=8),
        "projects": _score_list_confidence(projects, ideal_count=2, min_item_length=12),
        "text_quality": _score_text_quality(text),
    }


def _compute_overall_confidence(confidence: dict[str, float]) -> float:
    weights = {
        "name": 1.2,
        "headline": 1.0,
        "email": 0.9,
        "phone": 0.8,
        "linkedin": 0.4,
        "github": 0.3,
        "top_skills": 0.6,
        "experiences": 1.1,
        "projects": 0.5,
        "text_quality": 1.2,
    }
    weighted_sum = 0.0
    total_weight = 0.0
    for key, value in confidence.items():
        weight = weights.get(key, 1.0)
        weighted_sum += max(0.0, min(1.0, float(value))) * weight
        total_weight += weight
    if total_weight <= 0:
        return 0.0
    return round(weighted_sum / total_weight, 3)


def _score_name_confidence(name: str) -> float:
    cleaned = " ".join(str(name or "").split()).strip()
    if not cleaned:
        return 0.0
    if any(char.isdigit() for char in cleaned):
        return 0.2

    words = re.findall(r"[A-Za-zÀ-ÿ'-]+", cleaned)
    if not (2 <= len(words) <= 4):
        return 0.35

    score = 0.7
    if all(word[:1].isupper() for word in words):
        score += 0.15
    if len(cleaned) <= 32:
        score += 0.1
    if any(token.lower() in {"profil", "experience", "réalisations", "realisations"} for token in words):
        score -= 0.4
    return max(0.0, min(1.0, round(score, 3)))


def _score_headline_confidence(headline: str) -> float:
    cleaned = " ".join(str(headline or "").split()).strip()
    if not cleaned:
        return 0.0
    lowered = cleaned.lower()
    score = 0.45
    if any(hint in lowered for hint in HEADLINE_HINTS):
        score += 0.35
    if 2 <= len(cleaned.split()) <= 8:
        score += 0.15
    if len(cleaned) > 90:
        score -= 0.25
    if any(marker in lowered for marker in ("profil", "expérience", "experience", "réalisations", "realisations")):
        score -= 0.2
    return max(0.0, min(1.0, round(score, 3)))


def _score_email_confidence(email: str) -> float:
    cleaned = str(email or "").strip()
    if not cleaned:
        return 0.0
    score = 0.55 if EMAIL_PATTERN.fullmatch(cleaned) else 0.3
    local_part, _, domain = cleaned.partition("@")
    if "." in domain:
        score += 0.15
    if any(char.isdigit() for char in local_part[:1]):
        score -= 0.2
    if domain.lower() in {"gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "email.fr", "email.com"}:
        score += 0.1
    if _looks_like_template_email(cleaned):
        score = 0.0
    return max(0.0, min(1.0, round(score, 3)))


def _score_phone_confidence(phone: str) -> float:
    cleaned = str(phone or "").strip()
    if not cleaned:
        return 0.0
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 8:
        return 0.15
    score = 0.45
    if cleaned.startswith("+") or cleaned.startswith("00"):
        score += 0.2
    if len(digits) in {8, 9, 10, 11, 12, 13}:
        score += 0.2
    if " " in cleaned or "-" in cleaned or "." in cleaned:
        score += 0.1
    if _looks_like_year_span(cleaned):
        score = 0.0
    return max(0.0, min(1.0, round(score, 3)))


def _score_social_confidence(url: str, *, provider: str) -> float:
    cleaned = str(url or "").strip()
    if not cleaned:
        return 0.0
    pattern = LINKEDIN_PATTERN if provider == "linkedin" else GITHUB_PATTERN
    score = 0.4
    if pattern.fullmatch(cleaned):
        score += 0.45
    if cleaned.startswith("https://"):
        score += 0.1
    return max(0.0, min(1.0, round(score, 3)))


def _score_list_confidence(items: list[str], *, ideal_count: int, min_item_length: int) -> float:
    cleaned_items = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned_items:
        return 0.0
    usable = [item for item in cleaned_items if len(item) >= min_item_length]
    if not usable:
        return 0.15
    count_score = min(1.0, len(usable) / max(1, ideal_count))
    avg_length = sum(len(item) for item in usable) / len(usable)
    length_score = 1.0 if avg_length >= min_item_length * 2 else max(0.4, avg_length / (min_item_length * 2))
    return round(max(0.0, min(1.0, (count_score * 0.6) + (length_score * 0.4))), 3)


def _score_text_quality(text: str) -> float:
    stripped = str(text or "").strip()
    if not stripped:
        return 0.0
    alnum_count = sum(char.isalnum() for char in stripped)
    line_count = len([line for line in stripped.splitlines() if line.strip()])
    score = 0.2
    if alnum_count >= 200:
        score += 0.35
    elif alnum_count >= 80:
        score += 0.2
    if line_count >= 8:
        score += 0.2
    if EMAIL_PATTERN.search(stripped):
        score += 0.1
    if PHONE_PATTERN.search(stripped):
        score += 0.1
    if any(marker in stripped.lower() for marker in ("experience", "expérience", "skills", "compétences", "formation")):
        score += 0.1
    return max(0.0, min(1.0, round(score, 3)))


def _extract_header_identity(lines: list[str]) -> tuple[str, str]:
    if not lines:
        return "", ""

    header = _normalize_text_artifacts(lines[0])
    header = re.sub(EMAIL_PATTERN, " ", header)
    header = re.sub(PHONE_PATTERN, " ", header)
    header = re.sub(r"\blinkedin\.com\b.*$", " ", header, flags=re.IGNORECASE)
    header = re.sub(r"\bwww\.[^\s]+\b", " ", header, flags=re.IGNORECASE)
    header = re.sub(r"\b\d+\s+ans\b", " ", header, flags=re.IGNORECASE)
    header = re.sub(r"\b[A-Z][a-zA-ZÀ-ÿ-]+,\s*[A-Z][a-zA-ZÀ-ÿ-]+\b", " ", header)
    header = re.sub(r"\s+", " ", header).strip(INLINE_STRIP_CHARS)
    if not header:
        return "", ""

    tokens = header.split()
    name_tokens: list[str] = []
    split_index = 0
    for index, token in enumerate(tokens):
        lower_token = token.lower()
        if len(name_tokens) >= 2 and (lower_token in HEADER_TITLE_START_TOKENS or lower_token in HEADLINE_HINTS):
            break
        if not re.fullmatch(r"[A-Za-zÀ-ÿ'-]+", token):
            break
        if token[0].isupper() or token.isupper():
            name_tokens.append(token)
            split_index = index + 1
            if len(name_tokens) == 4:
                break
            continue
        break

    if len(name_tokens) < 2:
        return "", ""

    name = _format_display_title(" ".join(name_tokens))
    headline = _format_display_title(" ".join(tokens[split_index:])) if split_index < len(tokens) else ""
    if headline and not any(hint in headline.lower() for hint in HEADLINE_HINTS):
        headline = ""
    return name, headline


def _extract_email(text: str) -> str:
    for line in text.splitlines():
        if "@" not in line:
            continue
        joined = re.search(
            r"([A-Za-z0-9._%+-]+)\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
            line,
            re.IGNORECASE,
        )
        if joined:
            return _normalize_email_candidate(f"{joined.group(1)}{joined.group(2)}")

    exact = _extract_first(EMAIL_PATTERN, text)
    if exact:
        return _normalize_email_candidate(exact)

    match = EMAIL_OCR_PATTERN.search(text)
    if not match:
        return ""

    candidate = re.sub(r"\s+", "", match.group(0)).strip(".,;:|")
    return _normalize_email_candidate(candidate)


def _normalize_email_candidate(candidate: str) -> str:
    cleaned = candidate.strip(".,;:|")
    if "@" not in cleaned:
        return cleaned

    local_part, domain = cleaned.split("@", 1)
    if len(local_part) >= 2 and local_part[0].isdigit() and local_part[1].isalpha() and sum(char.isdigit() for char in local_part) == 1:
        local_part = local_part[1:]

    domain = {
        "gnal.com": "gmail.com",
        "gmai1.com": "gmail.com",
        "gmaiI.com": "gmail.com",
    }.get(domain.lower(), domain)
    normalized = f"{local_part}@{domain}"
    return "" if _looks_like_template_email(normalized) else normalized


def _looks_like_template_email(email: str) -> bool:
    if "@" not in email:
        return False
    local_part, domain = email.lower().split("@", 1)
    local_part = re.sub(r"^\d+", "", local_part)
    generic_locals = {"help", "support", "contact", "hello", "info"}
    template_domains = {"enhancv.com"}
    return local_part in generic_locals and domain in template_domains


def _extract_phone(text: str) -> str:
    best_candidate = ""
    best_score = float("-inf")

    for match in PHONE_PATTERN.finditer(text):
        candidate = match.group(0).strip()
        digits = re.sub(r"\D", "", candidate)
        if len(digits) < 8 or len(digits) > 15:
            continue
        if _looks_like_year_span(candidate):
            continue

        normalized = candidate
        if candidate.startswith("00"):
            normalized = "+" + digits[2:]
        elif candidate.startswith("+"):
            normalized = "+" + digits

        score = _score_phone_candidate(candidate, digits)
        if score > best_score:
            best_candidate = normalized
            best_score = score

    return best_candidate


def _looks_like_year_span(candidate: str) -> bool:
    parts = [part for part in re.split(r"\D+", candidate) if part]
    if len(parts) != 2 or not all(len(part) == 4 for part in parts):
        return False
    return all(1900 <= int(part) <= 2099 for part in parts)


def _score_phone_candidate(candidate: str, digits: str) -> float:
    score = float(len(digits))
    compact = candidate.replace(" ", "")

    if candidate.startswith("+") or candidate.startswith("00"):
        score += 4.0
    elif digits.startswith("0"):
        score += 3.0

    if " " in candidate or "-" in candidate or "." in candidate:
        score += 1.5

    if compact.count("[") or compact.count("]") or compact.count("(") or compact.count(")"):
        score -= 1.5

    if digits == digits[0] * len(digits):
        score -= 6.0

    return score


def _normalize_social_compact_line(compact: str, *, provider: str) -> str:
    if provider == "linkedin":
        compact = compact.replace("wwwlinkedin", "www.linkedin")
        compact = compact.replace("linkedincom", "linkedin.com")
        compact = compact.replace("linkedin.comlin", "linkedin.com/in/")
        compact = compact.replace("linkedin.comin", "linkedin.com/in/")
        compact = compact.replace("comlin", ".com/in/")
        return compact.replace("linkedin.com/in/in/", "linkedin.com/in/")

    compact = compact.replace("wwwgithub", "www.github")
    compact = compact.replace("githubcom", "github.com/")
    return compact.replace("github.com//", "github.com/")


def _extract_social_link(text: str, *, provider: str) -> str:
    pattern = LINKEDIN_PATTERN if provider == "linkedin" else GITHUB_PATTERN
    exact = _extract_first(pattern, text)
    if exact:
        return exact if exact.startswith("http") else f"https://{exact}"

    keyword = provider.lower()
    social_lines = [line for line in text.splitlines() if keyword in line.lower()]

    for line in social_lines:
        compact = re.sub(r"[^A-Za-z0-9._:/-]+", "", line)
        compact = _normalize_social_compact_line(compact, provider=provider)

        if provider == "linkedin":
            match = re.search(r"(?:www\.)?linkedin\.com/in/[A-Za-z0-9_-]+", compact, re.IGNORECASE)
        else:
            match = re.search(r"(?:www\.)?github\.com/[A-Za-z0-9_-]+", compact, re.IGNORECASE)

        if not match:
            continue

        candidate = match.group(0).rstrip("./-")
        return candidate if candidate.startswith("http") else f"https://{candidate}"

    return ""


def _guess_name(lines: list[str]) -> str:
    best_candidate = ""
    best_score = float("-inf")

    for line in lines[:12]:
        if "@" in line or any(char.isdigit() for char in line):
            continue

        candidate = _clean_inline_text(line)
        if not candidate or len(candidate) > 60:
            continue
        if any(symbol in candidate for symbol in (".", "!", "?", "/", "\\", "(", ")")):
            continue

        lower = candidate.lower()
        if any(hint in lower for hint in HEADLINE_HINTS):
            continue
        if any(
            token in lower
            for token in (
                "profil",
                "profile",
                "summary",
                "contact",
                "formation",
                "education",
                "experience",
                "expérience",
                "compétences",
                "competences",
                "skills",
                "languages",
                "langues",
                "certifications",
            )
        ):
            continue

        words = NAME_WORD_PATTERN.findall(candidate)
        if not (2 <= len(words) <= 4):
            continue

        score = 0.0
        if candidate == candidate.upper():
            score += 4.0
        if all(word[:1].isupper() for word in words):
            score += 2.0
        if len(words) == 2:
            score += 1.5
        score -= max(0, len(candidate) - 28) * 0.05

        if score > best_score:
            best_candidate = " ".join(words)
            best_score = score

    if best_candidate:
        return best_candidate

    if lines:
        first_line_words = NAME_WORD_PATTERN.findall(lines[0])
        candidate_words: list[str] = []
        for word in first_line_words[:6]:
            lower = word.lower()
            if lower in HEADLINE_HINTS or lower in {"etudiante", "etudiant", "étudiante", "étudiant", "cycle", "en"}:
                break
            candidate_words.append(word)
            if len(candidate_words) == 4:
                break
        if 2 <= len(candidate_words) <= 4:
            return " ".join(candidate_words)

    for line in lines[:8]:
        if "@" in line or len(line) > 70 or any(char.isdigit() for char in line):
            continue

        candidate = _clean_inline_text(line)
        if not candidate:
            continue

        lower = candidate.lower()
        if any(hint in lower for hint in HEADLINE_HINTS):
            continue

        # Accept common CV name formats such as "Ameni HMEM" or "AMENI HMEM".
        raw_words = re.findall(r"[A-ZÀ-Ÿ][A-Za-zÀ-ÿ'-]+", candidate)
        if 2 <= len(raw_words) <= 4 and all(word[0].isupper() for word in raw_words):
            return " ".join(raw_words)

        upper_words = re.findall(r"[A-ZÀ-Ÿ][A-ZÀ-Ÿ'-]{1,}", candidate)
        if 2 <= len(upper_words) <= 4 and candidate == candidate.upper() and len(candidate) <= 40:
            return " ".join(word.capitalize() for word in upper_words)

    return ""


def _guess_headline(lines: list[str], experiences: list[str] | None = None) -> str:
    headline_hints = HEADLINE_HINTS | {"etudiante", "etudiant", "étudiante", "étudiant", "ingenieur", "ingénieur", "cycle"}
    intro_markers = (" animée ", " animee ", " actuellement ", " passionnee ", " passionnée ")

    for line in lines[:8]:
        label = _extract_role_label(line)
        if label and "job" in label.lower():
            return label

    for line in lines[:6]:
        label = _extract_role_label(line)
        if label:
            return label

    for line in lines[:15]:
        segments = [segment.strip(INLINE_STRIP_CHARS) for segment in re.split(r"[;\|]", line) if segment.strip()]
        for segment in segments or [line]:
            candidate = _clean_inline_text(segment, strip_chars=" ")
            lower = candidate.lower()

            if not candidate:
                continue

            first_line_words = NAME_WORD_PATTERN.findall(candidate)
            if len(first_line_words) >= 2:
                prefix = " ".join(first_line_words[:2])
                if candidate.startswith(prefix):
                    remainder = candidate[len(prefix):].strip(" -|,;:")
                    if remainder:
                        candidate = _clean_inline_text(remainder)
                        lower = candidate.lower()

            for marker in intro_markers:
                marker_index = lower.find(marker)
                if marker_index > 0:
                    candidate = candidate[:marker_index].strip(INLINE_STRIP_CHARS)
                    lower = candidate.lower()
                    break

            if not candidate or len(candidate) > 110:
                continue
            if any(marker in lower for marker in COMMON_REJECT_MARKERS):
                continue
            if ":" in candidate and "," in candidate:
                continue
            if candidate.count(",") >= 2:
                continue
            if any(hint in lower for hint in headline_hints):
                return _format_display_title(candidate)

    for experience in experiences or []:
        label = _extract_role_label(experience)
        if label:
            return label

    return ""


def _extract_top_skills(text: str) -> list[str]:
    norm = text.lower().replace("node.js", "node").replace("apis", "api")
    counts: dict[str, int] = {}

    for skill in SKILL_PATTERNS:
        count = len(re.findall(r"\b" + re.escape(skill) + r"\b", norm))
        if count:
            counts[skill] = count

    return [skill for skill, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))][:10]


def _extract_experiences(text: str) -> list[str]:
    lines = _extract_section_lines(
        text,
        start_re=EXPERIENCE_SECTION_START_RE,
        stop_re=EXPERIENCE_SECTION_STOP_RE,
    )
    cleaned = _extract_structured_experiences(lines)
    if len(cleaned) < 2:
        fallback_lines = [_clean_inline_text(item) for item in text.splitlines() if item.strip()]
        cleaned.extend(_extract_structured_experiences(fallback_lines))
    return _merge_experience_duplicates(_dedupe_preserve_order(cleaned))[:6]


def _extract_projects(text: str) -> list[str]:
    reject_markers = COMMON_REJECT_MARKERS | {"competences", "langues"}
    lines = _extract_section_lines(
        text,
        start_re=PROJECT_SECTION_START_RE,
        stop_re=PROJECT_SECTION_STOP_RE,
    )
    projects = _collect_section_items(
        lines,
        content_markers=PROJECT_CONTENT_MARKERS,
        reject_markers=reject_markers,
        min_length=24,
        max_length=220,
        block_project_reject_markers=True,
    )

    if not projects:
        flat_text = " ".join(text.split())
        for sentence in re.split(r"(?<=[\.\!\?])\s+", flat_text):
            lower = sentence.lower()
            if any(marker in lower for marker in reject_markers):
                continue
            if any(marker in lower for marker in PROJECT_REJECT_MARKERS):
                continue
            if any(word in lower for word in PROJECT_CONTENT_MARKERS):
                cleaned = sentence.strip()[:140]
                if len(cleaned) >= 24:
                    projects.append(cleaned)

    return _dedupe_preserve_order(projects)[:8]


def _extract_section_lines(
    text: str,
    *,
    start_re: Pattern[str],
    stop_re: Pattern[str],
) -> list[str]:
    cleaned_lines = [_clean_inline_text(line, strip_chars=SECTION_LINE_STRIP_CHARS) for line in text.splitlines() if line.strip()]
    lines: list[str] = []
    capturing = False

    for line in cleaned_lines:
        lower = line.lower()

        start_match = start_re.match(lower)
        if not capturing and start_match:
            capturing = True
            remainder = line[start_match.end():].strip(" -|,:;")
            if remainder:
                lines.append(remainder)
            continue

        if not capturing:
            continue

        if stop_re.match(lower) or (SECTION_HEADER_RE.match(line) and not start_re.match(lower)):
            break

        lines.append(line)

    return lines


def _collect_section_items(
    lines: list[str],
    *,
    content_markers: tuple[str, ...],
    reject_markers: frozenset[str] | set[str],
    min_length: int,
    max_length: int,
    block_project_reject_markers: bool,
) -> list[str]:
    items: list[str] = []

    for line in lines:
        lower = line.lower()
        if len(line) < min_length:
            continue
        if any(marker in lower for marker in reject_markers):
            continue
        if block_project_reject_markers and any(marker in lower for marker in PROJECT_REJECT_MARKERS):
            continue
        if not any(marker in lower for marker in content_markers):
            continue

        candidate = line[:max_length].strip(" -|,;:")
        if candidate:
            items.append(candidate)

        if len(line) > max_length:
            for sentence in re.split(r"(?<=[\.\!\?])\s+", line):
                cleaned = sentence.strip(" -|,;:")
                lowered = cleaned.lower()
                if len(cleaned) < min_length:
                    continue
                if any(marker in lowered for marker in reject_markers):
                    continue
                if block_project_reject_markers and any(marker in lowered for marker in PROJECT_REJECT_MARKERS):
                    continue
                if any(marker in lowered for marker in content_markers):
                    items.append(cleaned[:max_length])

    return items


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_items: list[str] = []
    for item in items:
        key = re.sub(r"\s+", " ", item).strip(" -|,;:.").lower()
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item.strip())
    return unique_items


def _merge_experience_duplicates(experiences: list[str]) -> list[str]:
    merged: list[str] = []
    seen_by_label: dict[str, int] = {}

    for item in experiences:
        label = _extract_role_label(item)
        if not label:
            merged.append(item)
            continue

        key = label.lower()
        existing_index = seen_by_label.get(key)
        if existing_index is None:
            seen_by_label[key] = len(merged)
            merged.append(item)
            continue

        existing = merged[existing_index]
        existing_has_context = "|" in existing
        current_has_context = "|" in item
        if current_has_context and (not existing_has_context or len(item) < len(existing)):
            merged[existing_index] = item

    return merged


def _extract_structured_experiences(lines: list[str]) -> list[str]:
    experiences: list[str] = []
    for index, raw_line in enumerate(lines):
        line = _clean_inline_text(raw_line)
        if len(line) < 8:
            continue
        lower = line.lower()
        if any(token in lower for token in ("contact", "github", "linkedin", "langue", "skills", "compétences", "competences")):
            continue
        if any(marker in lower for marker in EXPERIENCE_SUMMARY_REJECT_MARKERS) and not DATE_CHUNK_RE.search(line):
            continue

        label = _extract_role_label(line)
        if not label:
            continue
        if "job" in label.lower() and not DATE_CHUNK_RE.search(line):
            continue

        context_parts: list[str] = []
        compact_line = _compact_experience_context(_normalize_experience_line(line), label)
        if compact_line and compact_line.lower() != label.lower():
            context_parts.append(compact_line)

        for offset in (1, 2):
            if index + offset >= len(lines):
                break
            neighbor = _clean_inline_text(lines[index + offset])
            if len(neighbor) < 6:
                continue
            neighbor_lower = neighbor.lower()
            if _extract_role_label(neighbor):
                break
            if SECTION_HEADER_RE.match(neighbor):
                break
            if any(hint in neighbor_lower for hint in COMPANY_CONTEXT_HINTS) or DATE_CHUNK_RE.search(neighbor):
                context_parts.append(_compact_experience_context(_normalize_experience_line(neighbor), label))
                break

        snippet = label
        if context_parts:
            for part in context_parts:
                if part and label.lower() not in part.lower():
                    snippet = f"{label} | {part}"
                    break
        experiences.append(snippet[:220].strip())

    return experiences


def _extract_role_label(text: str) -> str:
    candidate = _normalize_inline_text(text)
    if not candidate:
        return ""

    compact = _normalize_experience_line(candidate)
    for pattern in ROLE_LABEL_PATTERNS:
        match = pattern.search(compact)
        if match:
            label = match.group(0).strip(INLINE_STRIP_CHARS)
            return _clean_role_label(label)

    dated_label = _extract_role_from_dated_heading(compact)
    if dated_label:
        return _clean_role_label(dated_label)

    return ""


def _extract_role_from_dated_heading(text: str) -> str:
    candidate = _normalize_inline_text(text)
    if not candidate or not DATE_CHUNK_RE.search(candidate):
        return ""

    parts = [part.strip(" -|,;:") for part in re.split(r"\s+[–—-]\s+", candidate) if part.strip(" -|,;:")]
    if len(parts) < 2:
        return ""

    first_part = parts[0]
    first_lower = first_part.lower()
    normalized_first_lower = (
        first_lower.replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("ë", "e")
        .replace("-", " ")
    )
    if any(token in first_lower for token in ("profil", "profile", "poste de", "recherche")):
        return ""
    if len(first_part) > 70 or any(char.isdigit() for char in first_part):
        return ""
    if not any(hint in normalized_first_lower for hint in HEADLINE_HINTS):
        return ""

    return first_part


def _normalize_experience_line(text: str) -> str:
    candidate = _normalize_inline_text(text)
    candidate = re.sub(r"^(?:parcou[ru]s?\s+professionnel|exp[ée]riences?\s+professionnelles?)\s*", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"^\d{2}[/-]\d{4}\s*[~-]?\s*", "", candidate)
    candidate = re.sub(r"^(?:mars|avril|mai|juin|juillet|janvier|février|fevrier|août|aout|septembre|octobre|novembre|décembre|decembre)\s+\d{4}\s*", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"([A-Za-z])Chef\b", r"\1 Chef", candidate)
    candidate = candidate.replace(" dc ", " de ").replace(" dC ", " de ").replace(" d¢ ", " de ")
    candidate = candidate.replace("Clef de partic", "Chef de partie").replace("clef de partic", "chef de partie")
    candidate = re.sub(r"\s+", " ", candidate)
    return candidate.strip(INLINE_STRIP_CHARS)


def _compact_experience_context(text: str, label: str) -> str:
    candidate = text.strip(INLINE_STRIP_CHARS)
    if not candidate:
        return ""

    candidate = re.sub(re.escape(label), "", candidate, count=1, flags=re.IGNORECASE).strip(INLINE_STRIP_CHARS)
    candidate = re.sub(r"^(?:actuel|present|actuelle)\s*", "", candidate, flags=re.IGNORECASE).strip(INLINE_STRIP_CHARS)
    if not candidate:
        return label

    lowered = candidate.lower()
    cut_positions = [lowered.find(marker) for marker in EXPERIENCE_CONTEXT_BREAK_MARKERS if lowered.find(marker) > 0]
    if cut_positions:
        candidate = candidate[: min(cut_positions)].strip(INLINE_STRIP_CHARS)

    candidate = re.split(r"[.!?]", candidate, maxsplit=1)[0].strip(INLINE_STRIP_CHARS)
    words = candidate.split()
    if len(words) > 8:
        candidate = " ".join(words[:8]).strip(INLINE_STRIP_CHARS)

    return f"{label} | {candidate}" if candidate else label


def _clean_role_label(label: str) -> str:
    cleaned = _clean_inline_text(label)
    if not cleaned:
        return ""

    lowered = cleaned.lower()
    ascii_lowered = (
        lowered.replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("ë", "e")
        .replace("Ã©", "e")
        .replace("Ã¨", "e")
        .replace("Ãª", "e")
        .replace("Ã«", "e")
    )
    if "stage" in ascii_lowered and "job" in ascii_lowered and "etudia" in ascii_lowered:
        return "Stage Job Etudiant"

    words = cleaned.split()
    normalized_words: list[str] = []
    for word in words:
        if word.isupper():
            normalized_words.append(word.capitalize())
        elif len(word) > 1 and word[0].islower() and any(char.isupper() for char in word[1:]):
            normalized_words.append(word[0].upper() + word[1:])
        else:
            normalized_words.append(word)

    cleaned = " ".join(normalized_words)
    replacements = {
        "Full stack": "Full-Stack",
        "Full Stack": "Full-Stack",
        "fullstack": "FullStack",
        "Chef de partic": "Chef de partie",
        "Stagiaire": "stagiaire",
        "De": "de",
        "En": "en",
        "Et": "et",
        "Web developer": "Web Developer",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)

    return _format_display_title(cleaned)


def _format_display_title(text: str) -> str:
    normalized_text = _normalize_inline_text(text)
    tokens = [token for token in normalized_text.split(" ") if token]
    if not tokens:
        return ""

    formatted_tokens: list[str] = []
    for index, token in enumerate(tokens):
        formatted_tokens.append(_format_title_token(token, index=index))

    return " ".join(formatted_tokens)


def _format_title_token(token: str, *, index: int) -> str:
    token = _normalize_text_artifacts(token)
    lower = token.lower()
    if lower in TITLE_SPECIAL_CASING:
        return TITLE_SPECIAL_CASING[lower]
    if lower in TITLE_LOWERCASE_WORDS and index > 0:
        return lower
    if token.isupper() and len(token) <= 4:
        return token
    if "-" in token:
        parts = [part for part in token.split("-")]
        return "-".join(_format_title_token(part, index=0) if part else part for part in parts)
    if "/" in token and lower in TITLE_SPECIAL_CASING:
        return TITLE_SPECIAL_CASING[lower]
    if len(token) > 1:
        return token[0].upper() + token[1:].lower()
    return token.upper()
