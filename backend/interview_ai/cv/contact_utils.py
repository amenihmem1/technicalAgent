from __future__ import annotations

import re

EMAIL_PATTERN = re.compile(r"[\w\.-]+@[\w\.-]+\.\w{2,}", re.IGNORECASE)
EMAIL_OCR_PATTERN = re.compile(
    r"[A-Za-z0-9._%+-]+(?:\s+[A-Za-z0-9._%+-]+)?@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    re.IGNORECASE,
)
PHONE_PATTERN = re.compile(r"(?:\+|00)?\d[\d\s().-]{7,}\d")
LINKEDIN_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[^\s|]+", re.IGNORECASE)
GITHUB_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[^\s|]+", re.IGNORECASE)

_CONTACT_NORMALIZATIONS = (
    ("wwwlinkedin", "www.linkedin"),
    ("linkedin com", "linkedin.com"),
    ("linkedincom", "linkedin.com"),
    ("github com", "github.com"),
    ("githubcom", "github.com"),
    ("wwwgithub", "www.github"),
    ("comlin", ".com/in/"),
    ("linkedin.comlin", "linkedin.com/in/"),
    ("linkedin.com/in/in/", "linkedin.com/in/"),
    ("github.com/", " github.com/"),
    ("linkedin.com/", " linkedin.com/"),
)


def normalize_contact_search_text(text: str) -> str:
    normalized = text.replace("\r", "\n")
    normalized = re.sub(r"\s+", " ", normalized)
    for source, target in _CONTACT_NORMALIZATIONS:
        normalized = normalized.replace(source, target)
    return normalized
