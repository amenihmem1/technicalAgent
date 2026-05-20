from __future__ import annotations

import io
import os
from functools import lru_cache

import numpy as np
from interview_ai.cv.contact_utils import (
    EMAIL_OCR_PATTERN,
    EMAIL_PATTERN,
    GITHUB_PATTERN,
    LINKEDIN_PATTERN,
    PHONE_PATTERN,
    normalize_contact_search_text,
)


def extract_pdf_text_with_ocr(raw: bytes) -> str:
    import fitz
    from PIL import Image

    with fitz.open(stream=raw, filetype="pdf") as document:
        pages_text: list[str] = []
        for page in document:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.open(io.BytesIO(pixmap.tobytes("png")))
            page_text = ocr_image(image)
            if page_text:
                pages_text.append(page_text)
    return "\n\n".join(pages_text)


def extract_image_text_with_ocr(raw: bytes) -> str:
    from PIL import Image

    image = Image.open(io.BytesIO(raw))
    return ocr_image(image)


def ocr_image(image: "Image.Image") -> str:
    reader = _get_ocr_reader()
    best_text = ""
    best_score = float("-inf")

    for variant in _build_ocr_variants(image):
        for text, score in _read_ocr_variant_candidates(reader, variant):
            if score > best_score:
                best_text = text
                best_score = score

    return best_text


@lru_cache(maxsize=1)
def _get_ocr_reader():
    import easyocr

    return easyocr.Reader(["fr", "en"], gpu=_ocr_gpu_enabled(), verbose=False)


@lru_cache(maxsize=1)
def _ocr_gpu_enabled() -> bool:
    raw = os.getenv("OCR_USE_GPU", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False

    try:
        import torch
    except Exception:
        return False

    return bool(torch.cuda.is_available())


def _build_ocr_variants(image: "Image.Image") -> list[np.ndarray]:
    import cv2
    from PIL import Image, ImageOps

    prepared = ImageOps.exif_transpose(image).convert("L")
    upscale_factor = 3 if max(prepared.size) < 1400 else 2
    if max(prepared.size) < 2400:
        prepared = prepared.resize(
            (prepared.width * upscale_factor, prepared.height * upscale_factor),
            Image.Resampling.LANCZOS,
        )
    base = np.asarray(ImageOps.autocontrast(prepared))
    cropped = _crop_to_content(base)
    denoised = cv2.fastNlMeansDenoising(cropped, None, 12, 7, 21)
    sharpened = cv2.addWeighted(denoised, 1.6, cv2.GaussianBlur(denoised, (0, 0), 1.2), -0.6, 0)
    otsu = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    adaptive = cv2.adaptiveThreshold(
        sharpened,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    morph = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, np.ones((2, 2), dtype=np.uint8))
    return [cropped, sharpened, otsu, morph]


def _crop_to_content(image_array: np.ndarray) -> np.ndarray:
    import cv2

    if image_array.ndim == 3:
        gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_array

    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = cv2.findNonZero(binary)
    if coords is None:
        return gray

    x, y, w, h = cv2.boundingRect(coords)
    pad_x = max(12, w // 35)
    pad_y = max(12, h // 35)
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(gray.shape[1], x + w + pad_x)
    y1 = min(gray.shape[0], y + h + pad_y)
    cropped = gray[y0:y1, x0:x1]
    return cropped if cropped.size else gray


def _read_ocr_variant_candidates(reader, image_array: np.ndarray) -> list[tuple[str, float]]:
    candidates = [_read_ocr_variant(reader, image_array)]
    line_candidate = _read_ocr_lines(reader, image_array)
    if line_candidate[0].strip():
        candidates.append(line_candidate)
    return candidates


def _read_ocr_variant(reader, image_array: np.ndarray) -> tuple[str, float]:
    results = reader.readtext(image_array, detail=1, paragraph=True)
    fragments: list[str] = []
    confidences: list[float] = []

    for item in results:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        text = str(item[1]).strip()
        confidence = float(item[2] or 0.0) if len(item) >= 3 else 0.65
        if not text:
            continue
        fragments.append(text)
        confidences.append(confidence)

    merged = "\n".join(fragments)
    return merged, _score_ocr_text(merged, confidences)


def _read_ocr_lines(reader, image_array: np.ndarray) -> tuple[str, float]:
    line_images = _extract_line_images(image_array)
    if not line_images:
        return "", float("-inf")

    fragments: list[str] = []
    confidences: list[float] = []

    for line_image in line_images:
        results = reader.readtext(line_image, detail=1, paragraph=False)
        line_parts: list[str] = []
        line_scores: list[float] = []
        for item in results:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            text = str(item[1]).strip()
            confidence = float(item[2] or 0.0) if len(item) >= 3 else 0.65
            if not text:
                continue
            line_parts.append(text)
            line_scores.append(confidence)
        if line_parts:
            fragments.append(" ".join(line_parts))
            confidences.extend(line_scores)

    merged = "\n".join(fragment for fragment in fragments if fragment.strip())
    return merged, _score_ocr_text(merged, confidences)


def _extract_line_images(image_array: np.ndarray) -> list[np.ndarray]:
    import cv2

    gray = image_array if image_array.ndim == 2 else cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    kernel_width = max(20, gray.shape[1] // 18)
    kernel_height = max(2, gray.shape[0] // 140)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_width, kernel_height))
    connected = cv2.dilate(binary, kernel, iterations=1)
    contours, _hierarchy = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes: list[tuple[int, int, int, int]] = []
    min_width = max(80, gray.shape[1] // 6)
    min_height = max(18, gray.shape[0] // 60)
    max_height = max(120, gray.shape[0] // 6)

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w < min_width or h < min_height or h > max_height:
            continue
        boxes.append((x, y, w, h))

    boxes.sort(key=lambda item: (item[1], item[0]))
    line_images: list[np.ndarray] = []
    for x, y, w, h in boxes[:40]:
        pad_x = max(8, w // 40)
        pad_y = max(6, h // 3)
        x0 = max(0, x - pad_x)
        y0 = max(0, y - pad_y)
        x1 = min(gray.shape[1], x + w + pad_x)
        y1 = min(gray.shape[0], y + h + pad_y)
        crop = gray[y0:y1, x0:x1]
        if crop.size:
            line_images.append(crop)

    return line_images


def _score_ocr_text(text: str, confidences: list[float]) -> float:
    stripped = text.strip()
    if not stripped:
        return float("-inf")

    alnum_count = sum(char.isalnum() for char in stripped)
    line_count = max(1, len([line for line in stripped.splitlines() if line.strip()]))
    avg_confidence = (sum(confidences) / len(confidences)) if confidences else 0.0
    keyword_bonus = sum(
        1
        for token in (
            "experience",
            "formation",
            "contact",
            "linkedin",
            "github",
            "skills",
            "competences",
            "projets",
            "projects",
        )
        if token in stripped.lower()
    )
    structure_bonus = 0
    if EMAIL_PATTERN.search(stripped) or EMAIL_OCR_PATTERN.search(stripped):
        structure_bonus += 80
    if PHONE_PATTERN.search(stripped):
        structure_bonus += 55
    if LINKEDIN_PATTERN.search(normalize_contact_search_text(stripped)):
        structure_bonus += 35
    if GITHUB_PATTERN.search(normalize_contact_search_text(stripped)):
        structure_bonus += 35

    return (
        alnum_count
        + (avg_confidence * 140.0)
        + (line_count * 4.0)
        + (keyword_bonus * 18.0)
        + structure_bonus
    )
