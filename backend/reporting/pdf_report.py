from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from core.paths import REPORTS_DIR, sanitize_storage_name
from interview_ai.constants import SKILL_KEYS
from reporting.report_labels import REPORT_LABELS


PAGE_MARGIN = 42
CONTENT_WIDTH = A4[0] - (PAGE_MARGIN * 2)

COLOR_INK = colors.HexColor("#1E1A2B")
COLOR_MUTED = colors.HexColor("#6F687C")
COLOR_BORDER = colors.HexColor("#ECE7F2")
COLOR_BORDER_STRONG = colors.HexColor("#DDD5E7")
COLOR_PANEL = colors.HexColor("#FAF9FC")
COLOR_PANEL_ALT = colors.HexColor("#FFFFFF")
COLOR_PANEL_SOFT = colors.HexColor("#FFFFFF")
COLOR_ACCENT = colors.HexColor("#6756E8")
COLOR_ACCENT_SOFT = colors.HexColor("#EFECFF")
COLOR_INFO = colors.HexColor("#6756E8")
COLOR_INFO_SOFT = colors.HexColor("#F3F0FF")
COLOR_MAGENTA = colors.HexColor("#6756E8")
COLOR_MAGENTA_SOFT = colors.HexColor("#F3F0FF")
COLOR_WARN = colors.HexColor("#B49353")
COLOR_WARN_SOFT = colors.HexColor("#FFF4E0")
COLOR_DANGER = colors.HexColor("#F43F5E")
COLOR_DANGER_SOFT = colors.HexColor("#FFE4EA")
COLOR_GOLD = colors.HexColor("#6756E8")
COLOR_GOLD_SOFT = colors.HexColor("#EFECFF")
COLOR_HEADER = colors.HexColor("#FFFFFF")
COLOR_HEADER_TEXT = COLOR_INK
COLOR_HEADER_MUTED = COLOR_MUTED
COLOR_SHADOW = colors.HexColor("#F7F3FB")
COLOR_RH_PRIMARY = colors.HexColor("#147D78")
COLOR_RH_PRIMARY_SOFT = colors.HexColor("#EEF6F5")
COLOR_RH_SURFACE = colors.HexColor("#F7F9FC")
COLOR_RH_BORDER = colors.HexColor("#D7E1EE")
COLOR_RH_LINE = colors.HexColor("#D9E3EF")


def _safe_name(session_id: str) -> str:
    return sanitize_storage_name(session_id)


def _normalize_items(value: Any, fallback: str) -> List[str]:
    items = [str(item).strip() for item in (value or []) if str(item).strip()]
    return items or [fallback]


def _normalize_percent(value: Any) -> int:
    try:
        return max(0, min(100, int(round(float(value or 0)))))
    except (TypeError, ValueError):
        return 0


def _format_datetime(value: str, language: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return raw

    if language == "fr":
        months = {
            1: "janv.",
            2: "fevr.",
            3: "mars",
            4: "avr.",
            5: "mai",
            6: "juin",
            7: "juil.",
            8: "aout",
            9: "sept.",
            10: "oct.",
            11: "nov.",
            12: "dec.",
        }
        return f"{parsed.day:02d} {months[parsed.month]} {parsed.year} - {parsed:%H:%M}"
    return parsed.strftime("%b %d, %Y - %H:%M")


def _truncate_to_width(
    c: canvas.Canvas,
    text: str,
    width: float,
    *,
    font_name: str = "Helvetica",
    font_size: int = 10,
) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    c.setFont(font_name, font_size)
    if c.stringWidth(value, font_name, font_size) <= width:
        return value

    ellipsis = "..."
    trimmed = value
    while trimmed and c.stringWidth(trimmed + ellipsis, font_name, font_size) > width:
        trimmed = trimmed[:-1]
    return (trimmed.rstrip() + ellipsis) if trimmed else ellipsis


def _draw_wrapped_limited(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    *,
    font_name: str = "Helvetica",
    font_size: int = 10,
    line_height: float = 14,
    max_lines: int = 2,
) -> float:
    lines = _wrap_lines(c, text, width, font_name=font_name, font_size=font_size)
    if max_lines > 0 and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _truncate_to_width(
            c,
            lines[-1],
            width,
            font_name=font_name,
            font_size=font_size,
        )
    c.setFont(font_name, font_size)
    for line in lines:
        c.drawString(x, y, line)
        y -= line_height
    return y


def _draw_panel_frame(
    c: canvas.Canvas,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    fill: colors.Color = COLOR_PANEL_ALT,
    accent: colors.Color | None = None,
) -> None:
    radius = 14
    c.setFillColor(fill)
    c.roundRect(x, y - height, width, height, radius, fill=1, stroke=0)
    c.setStrokeColor(COLOR_BORDER_STRONG)
    c.roundRect(x, y - height, width, height, radius, fill=0, stroke=1)


def _score_color(score: int) -> colors.Color:
    if score >= 4:
        return COLOR_ACCENT
    if score >= 3:
        return COLOR_WARN
    return COLOR_DANGER


def _score_label(score: int, labels: Dict[str, Any]) -> str:
    if score >= 4:
        return labels["score_labels"]["strong"]
    if score >= 3:
        return labels["score_labels"]["correct"]
    if score >= 1:
        return labels["score_labels"]["improve"]
    return labels["score_labels"]["confirm"]


def _wrap_lines(
    c: canvas.Canvas,
    text: str,
    width: float,
    *,
    font_name: str = "Helvetica",
    font_size: int = 10,
) -> List[str]:
    c.setFont(font_name, font_size)
    words = (text or "").split()
    if not words:
        return []

    lines: List[str] = []
    line = ""
    for word in words:
        candidate = (line + " " + word).strip()
        if c.stringWidth(candidate, font_name, font_size) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = word
    if line:
        lines.append(line)
    return lines


def _estimate_wrapped_height(
    c: canvas.Canvas,
    text: str,
    width: float,
    *,
    font_name: str = "Helvetica",
    font_size: int = 10,
    line_height: float = 14,
) -> float:
    lines = _wrap_lines(c, text, width, font_name=font_name, font_size=font_size)
    return max(line_height, len(lines) * line_height) if lines else line_height


def _estimate_bullets_height(
    c: canvas.Canvas,
    items: List[str],
    width: float,
    *,
    font_name: str = "Helvetica",
    font_size: int = 10,
    line_height: float = 14,
) -> float:
    text_width = width - 16
    total = 0.0
    for item in items:
        total += _estimate_wrapped_height(
            c,
            item,
            text_width,
            font_name=font_name,
            font_size=font_size,
            line_height=line_height,
        ) + 4
    return total


def _draw_wrapped(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    *,
    font_name: str = "Helvetica",
    font_size: int = 10,
    line_height: float = 14,
) -> float:
    lines = _wrap_lines(c, text, width, font_name=font_name, font_size=font_size)
    c.setFont(font_name, font_size)
    for line in lines:
        c.drawString(x, y, line)
        y -= line_height
    return y


def _draw_bullets(
    c: canvas.Canvas,
    items: List[str],
    x: float,
    y: float,
    width: float,
    *,
    bullet_color: colors.Color = COLOR_ACCENT,
) -> float:
    bullet_radius = 2.4
    text_x = x + 16
    for item in items:
        c.setFillColor(bullet_color)
        c.circle(x + 6, y - 3.2, bullet_radius, fill=1, stroke=0)
        c.setFillColor(COLOR_INK)
        y = _draw_wrapped(c, item, text_x, y, width - (text_x - x))
        y -= 4
    return y


def _ensure_space(c: canvas.Canvas, y: float, needed: float) -> float:
    if y >= PAGE_MARGIN + needed:
        return y
    c.showPage()
    return A4[1] - PAGE_MARGIN


def _draw_footer(c: canvas.Canvas, footer_title: str) -> None:
    footer_y = PAGE_MARGIN - 10
    c.setStrokeColor(COLOR_BORDER_STRONG)
    c.line(PAGE_MARGIN, footer_y + 16, A4[0] - PAGE_MARGIN, footer_y + 16)
    c.setFillColor(COLOR_MUTED)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(PAGE_MARGIN, footer_y, "SUBUL Technical Agent")
    c.setFont("Helvetica", 8)
    c.drawString(PAGE_MARGIN + 90, footer_y, footer_title)
    c.drawRightString(A4[0] - PAGE_MARGIN, footer_y, f"Page {c.getPageNumber()}")


def _draw_header(
    c: canvas.Canvas,
    session_id: str,
    updated_at: str,
    candidate_name: str,
    headline: str,
    labels: Dict[str, Any],
) -> float:
    y = A4[1] - PAGE_MARGIN
    report_language = "en" if labels["candidate_fallback"] == REPORT_LABELS["en"]["candidate_fallback"] else "fr"
    formatted_date = _format_datetime(updated_at, report_language)
    header_height = 120
    _draw_panel_frame(
        c,
        x=PAGE_MARGIN,
        y=y,
        width=CONTENT_WIDTH,
        height=header_height,
        fill=COLOR_HEADER,
        accent=COLOR_ACCENT,
    )

    _draw_pill(c, x=PAGE_MARGIN + 18, y=y - 10, text="SUBUL", fill=COLOR_ACCENT_SOFT, ink=COLOR_ACCENT)

    c.setFillColor(COLOR_HEADER_TEXT)
    _draw_wrapped_limited(
        c,
        labels["report_title"],
        PAGE_MARGIN + 18,
        y - 34,
        270,
        font_name="Helvetica-Bold",
        font_size=20,
        line_height=21,
        max_lines=2,
    )
    c.setFillColor(COLOR_HEADER_MUTED)
    c.setFont("Helvetica", 10)
    c.drawString(PAGE_MARGIN + 18, y - 60, labels["report_subtitle"])

    c.setFillColor(COLOR_HEADER_MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(PAGE_MARGIN + 18, y - 84, f"{labels['date']} : {formatted_date or updated_at}")

    panel_x = A4[0] - 252
    panel_y = y - 14
    _draw_panel_frame(
        c,
        x=panel_x,
        y=panel_y,
        width=192,
        height=72,
        fill=colors.white,
        accent=COLOR_ACCENT,
    )
    c.setFillColor(COLOR_INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(panel_x + 14, panel_y - 22, candidate_name or labels["candidate_fallback"])
    c.setFillColor(COLOR_MUTED)
    _draw_wrapped_limited(
        c,
        headline or labels["profile_fallback"],
        panel_x + 14,
        panel_y - 38,
        164,
        font_name="Helvetica",
        font_size=8,
        line_height=11,
        max_lines=2,
    )

    return y - header_height - 18


def _draw_score_card(c: canvas.Canvas, report: Dict[str, Any], x: float, y: float, width: float, labels: Dict[str, Any]) -> float:
    score_total = int(report.get("score_total", 0) or 0)
    score_band = max(1, round(score_total / 20))
    score_accent = _score_color(score_band)
    _draw_panel_frame(c, x=x, y=y, width=width, height=96, fill=COLOR_PANEL_SOFT, accent=score_accent)

    c.setFillColor(COLOR_MUTED)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 16, y - 22, labels["overall_score"])
    c.setFillColor(COLOR_INK)
    c.setFont("Helvetica-Bold", 28)
    c.drawString(x + 16, y - 54, f"{score_total}/100")
    c.setFont("Helvetica", 9)
    c.setFillColor(COLOR_MUTED)
    c.drawString(x + 16, y - 72, labels["score_caption"])

    bar_x = x + 186
    bar_y = y - 46
    bar_w = width - 206
    c.setFillColor(COLOR_PANEL)
    c.roundRect(bar_x, bar_y, bar_w, 12, 6, fill=1, stroke=0)
    c.setFillColor(score_accent)
    c.roundRect(bar_x, bar_y, max(12, bar_w * max(0, min(100, score_total)) / 100), 12, 6, fill=1, stroke=0)
    _draw_pill(
        c,
        x=bar_x,
        y=y - 72,
        text=_score_label(score_band, labels),
        fill=COLOR_GOLD_SOFT if score_total >= 80 else COLOR_ACCENT_SOFT,
        ink=COLOR_GOLD if score_total >= 80 else score_accent,
    )
    return y - 112


def _draw_section_title(c: canvas.Canvas, title: str, x: float, y: float) -> float:
    c.setFillColor(COLOR_INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x, y - 6, title)
    return y - 22


def _draw_pill(
    c: canvas.Canvas,
    *,
    x: float,
    y: float,
    text: str,
    fill: colors.Color,
    ink: colors.Color = COLOR_INK,
) -> float:
    width = max(48, c.stringWidth(text, "Helvetica-Bold", 8) + 18)
    c.setFillColor(fill)
    c.roundRect(x, y - 14, width, 16, 8, fill=1, stroke=0)
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 9, y - 8, text)
    return width


def _draw_profile_block(c: canvas.Canvas, payload: Dict[str, Any], x: float, y: float, width: float, labels: Dict[str, Any]) -> float:
    profile = payload.get("cv_profile") or {}
    skills = [str(item).strip() for item in (profile.get("top_skills") or []) if str(item).strip()]
    skills_text = _truncate_to_width(
        c,
        ", ".join(skills[:5]) or labels["stacks_fallback"],
        152,
        font_name="Helvetica",
        font_size=9,
    )

    _draw_panel_frame(c, x=x, y=y, width=width, height=78, fill=COLOR_PANEL_ALT, accent=COLOR_ACCENT)

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(COLOR_INK)
    c.drawString(x + 14, y - 22, labels["profile_overview"])
    c.setFont("Helvetica", 9)
    c.setFillColor(COLOR_MUTED)
    c.drawString(x + 14, y - 42, f"{labels['questions_handled']} : {len(payload.get('turns') or [])}")

    c.setFillColor(COLOR_PANEL_SOFT)
    c.roundRect(x + width - 188, y - 58, 174, 42, 12, fill=1, stroke=0)
    c.setStrokeColor(COLOR_BORDER)
    c.roundRect(x + width - 188, y - 58, 174, 42, 12, fill=0, stroke=1)
    c.setFillColor(COLOR_ACCENT)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + width - 172, y - 30, labels["stacks_skills"])
    c.setFillColor(COLOR_MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(x + width - 172, y - 44, skills_text)
    return y - 92


def _draw_bullet_panel(
    c: canvas.Canvas,
    *,
    title: str,
    items: List[str],
    x: float,
    y: float,
    width: float,
    fill: colors.Color,
    bullet_color: colors.Color,
) -> float:
    panel_height = 38 + _estimate_bullets_height(c, items, width - 32)
    _draw_panel_frame(c, x=x, y=y, width=width, height=panel_height, fill=fill, accent=bullet_color)
    c.setFillColor(COLOR_INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x + 16, y - 22, title)
    return _draw_bullets(c, items, x + 16, y - 42, width - 32, bullet_color=bullet_color)


def _draw_text_panel(
    c: canvas.Canvas,
    *,
    text: str,
    x: float,
    y: float,
    width: float,
    font_size: int = 10,
    line_height: float = 15,
) -> float:
    panel_height = 34 + _estimate_wrapped_height(
        c,
        text,
        width - 32,
        font_size=font_size,
        line_height=line_height,
    )
    _draw_panel_frame(c, x=x, y=y, width=width, height=panel_height, fill=COLOR_PANEL_SOFT, accent=COLOR_ACCENT)
    c.setFillColor(COLOR_INK)
    return _draw_wrapped(
        c,
        text,
        x + 16,
        y - 24,
        width - 32,
        font_size=font_size,
        line_height=line_height,
    )


def _draw_competency_table(c: canvas.Canvas, report: Dict[str, Any], x: float, y: float, width: float, labels: Dict[str, Any]) -> float:
    competency_labels = labels["competencies"]
    comp = report.get("competencies", {}) or {}
    row_h = 32
    panel_h = row_h * 4 + 24

    _draw_panel_frame(c, x=x, y=y, width=width, height=panel_h, fill=COLOR_PANEL_SOFT, accent=COLOR_INFO)

    current_y = y - 26
    for key in SKILL_KEYS:
        score = int(comp.get(key, 0) or 0)
        score_text = f"{score}/5"
        score_label = _score_label(score, labels)
        score_color = _score_color(score)
        c.setFillColor(COLOR_INK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 16, current_y, competency_labels[key])

        c.setFillColor(COLOR_PANEL)
        c.roundRect(x + 158, current_y - 8, 184, 10, 5, fill=1, stroke=0)
        c.setFillColor(score_color)
        c.roundRect(x + 158, current_y - 8, 184 * score / 5, 10, 5, fill=1, stroke=0)

        score_pill_w = max(28, c.stringWidth(score_text, "Helvetica-Bold", 8) + 16)
        score_pill_x = x + width - 112
        c.setFillColor(COLOR_ACCENT_SOFT if score >= 4 else COLOR_WARN_SOFT if score >= 3 else COLOR_DANGER_SOFT)
        c.roundRect(score_pill_x, current_y - 12, score_pill_w, 16, 8, fill=1, stroke=0)
        c.setFillColor(score_color)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(score_pill_x + score_pill_w / 2, current_y - 6, score_text)

        c.setFillColor(COLOR_MUTED)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(score_pill_x + score_pill_w + 10, current_y - 6, score_label)
        current_y -= row_h
    return y - panel_h - 14


def _draw_stat_card(
    c: canvas.Canvas,
    *,
    x: float,
    y: float,
    width: float,
    title: str,
    value: str,
    caption: str,
    accent: colors.Color,
    fill: colors.Color,
) -> float:
    _draw_panel_frame(c, x=x, y=y, width=width, height=92, fill=fill, accent=accent)

    c.setFillColor(COLOR_MUTED)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x + 14, y - 22, title)

    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 25)
    c.drawString(x + 14, y - 52, value)

    c.setFillColor(COLOR_MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(x + 14, y - 70, caption)
    return y - 104


def _draw_metric_panel(
    c: canvas.Canvas,
    *,
    title: str,
    metrics: List[Dict[str, str | int]],
    x: float,
    y: float,
    width: float,
    accent: colors.Color,
) -> float:
    row_height = 30
    panel_height = 44 + max(1, len(metrics)) * row_height
    _draw_panel_frame(c, x=x, y=y, width=width, height=panel_height, fill=colors.white, accent=accent)

    c.setFillColor(COLOR_INK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x + 16, y - 22, title)

    current_y = y - 50
    bar_x = x + 136
    bar_w = max(92, width - 216)
    for item in metrics:
        value = _normalize_percent(item.get("value"))
        detail = str(item.get("detail", f"{value}%"))
        c.setFillColor(COLOR_MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(x + 16, current_y, str(item.get("label", "")))

        c.setFillColor(COLOR_PANEL)
        c.roundRect(bar_x, current_y - 6, bar_w, 8, 4, fill=1, stroke=0)
        c.setFillColor(accent)
        c.roundRect(bar_x, current_y - 6, max(10, bar_w * value / 100), 8, 4, fill=1, stroke=0)

        pill_width = max(34, c.stringWidth(detail, "Helvetica-Bold", 8) + 18)
        pill_x = x + width - 16 - pill_width
        c.setFillColor(COLOR_ACCENT_SOFT if accent == COLOR_ACCENT else COLOR_WARN_SOFT)
        c.roundRect(pill_x, current_y - 11, pill_width, 16, 8, fill=1, stroke=0)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(pill_x + pill_width / 2, current_y - 5, detail)
        current_y -= row_height

    return y - panel_height - 14


def _draw_tag_panel(
    c: canvas.Canvas,
    *,
    title: str,
    tags: List[str],
    x: float,
    y: float,
    width: float,
    fill: colors.Color,
    accent: colors.Color,
) -> float:
    line_y = y - 40
    cursor_x = x + 16
    row_height = 28
    total_rows = 1
    max_width = x + width - 16

    widths: List[float] = []
    for tag in tags:
        widths.append(max(64, c.stringWidth(tag, "Helvetica-Bold", 8) + 22))

    for tag_width in widths:
        if cursor_x + tag_width > max_width:
            total_rows += 1
            cursor_x = x + 14
            line_y -= row_height
        cursor_x += tag_width + 8

    panel_height = 52 + total_rows * row_height
    _draw_panel_frame(c, x=x, y=y, width=width, height=panel_height, fill=fill, accent=accent)

    c.setFillColor(COLOR_INK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x + 16, y - 22, title)

    cursor_x = x + 16
    line_y = y - 40
    for tag, tag_width in zip(tags, widths):
        if cursor_x + tag_width > max_width:
            cursor_x = x + 16
            line_y -= row_height
        c.setFillColor(COLOR_ACCENT_SOFT)
        c.roundRect(cursor_x, line_y - 12, tag_width, 18, 9, fill=1, stroke=0)
        c.setStrokeColor(accent)
        c.roundRect(cursor_x, line_y - 12, tag_width, 18, 9, fill=0, stroke=1)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(cursor_x + 11, line_y - 5, tag)
        cursor_x += tag_width + 8

    return y - panel_height - 14


def _draw_note_panel(
    c: canvas.Canvas,
    *,
    title: str,
    text: str,
    x: float,
    y: float,
    width: float,
    accent: colors.Color = COLOR_ACCENT,
) -> float:
    normalized_text = text.strip()
    if normalized_text.lower().startswith("note de confiance :"):
        normalized_text = normalized_text.split(":", 1)[1].strip()
    if normalized_text.lower().startswith("confidence note:"):
        normalized_text = normalized_text.split(":", 1)[1].strip()

    panel_height = 42 + _estimate_wrapped_height(
        c,
        normalized_text,
        width - 32,
        font_size=9,
        line_height=15,
    )
    _draw_panel_frame(c, x=x, y=y, width=width, height=panel_height, fill=COLOR_PANEL_SOFT, accent=accent)
    c.setFillColor(COLOR_INK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x + 16, y - 22, title)
    c.setFillColor(COLOR_MUTED)
    return _draw_wrapped(
        c,
        normalized_text,
        x + 16,
        y - 46,
        width - 32,
        font_size=9,
        line_height=15,
    )


def _draw_report_header(
    c: canvas.Canvas,
    session_id: str,
    updated_at: str,
    candidate_name: str,
    headline: str,
    labels: Dict[str, Any],
) -> float:
    y = A4[1] - PAGE_MARGIN

    c.setFillColor(COLOR_INK)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(PAGE_MARGIN, y - 6, labels["report_title"])

    c.setFillColor(COLOR_MUTED)
    c.setFont("Helvetica", 11)
    c.drawString(PAGE_MARGIN, y - 28, labels["report_subtitle"])

    card_width = 228
    card_height = 52
    card_x = PAGE_MARGIN + CONTENT_WIDTH - card_width
    card_y = y - 14
    c.setFillColor(COLOR_RH_SURFACE)
    c.roundRect(card_x, card_y - card_height, card_width, card_height, 14, fill=1, stroke=0)
    c.setFillColor(COLOR_INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(card_x + 14, card_y - 18, candidate_name or labels["candidate_fallback"])
    c.setFillColor(COLOR_MUTED)
    _draw_wrapped_limited(
        c,
        headline or labels["profile_fallback"],
        card_x + 14,
        card_y - 34,
        card_width - 28,
        font_name="Helvetica",
        font_size=8,
        line_height=10,
        max_lines=2,
    )

    separator_y = y - 64
    c.setStrokeColor(COLOR_RH_LINE)
    c.line(PAGE_MARGIN, separator_y, PAGE_MARGIN + CONTENT_WIDTH, separator_y)

    c.setFillColor(COLOR_MUTED)
    c.setFont("Helvetica", 10)
    session_text = _truncate_to_width(
        c,
        f"{labels['session']} : {session_id}",
        230,
        font_name="Helvetica",
        font_size=10,
    )
    c.drawString(PAGE_MARGIN, separator_y - 22, session_text)
    c.drawString(PAGE_MARGIN + 260, separator_y - 22, f"{labels['date']} : {updated_at}")
    return y - 94


def _draw_report_score_card(c: canvas.Canvas, report: Dict[str, Any], x: float, y: float, width: float, labels: Dict[str, Any]) -> float:
    score_total = int(report.get("score_total", 0) or 0)
    c.setFillColor(COLOR_RH_SURFACE)
    c.roundRect(x, y - 108, width, 108, 16, fill=1, stroke=0)

    c.setFillColor(COLOR_MUTED)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x + 18, y - 24, labels["overall_score"])

    c.setFillColor(COLOR_INK)
    c.setFont("Helvetica-Bold", 28)
    c.drawString(x + 18, y - 60, f"{score_total}/100")

    c.setFillColor(COLOR_MUTED)
    c.setFont("Helvetica", 10)
    c.drawString(x + 18, y - 82, labels["score_caption"])

    bar_x = x + 156
    bar_y = y - 52
    bar_w = width - 178
    c.setFillColor(colors.white)
    c.roundRect(bar_x, bar_y, bar_w, 12, 6, fill=1, stroke=0)
    c.setFillColor(COLOR_RH_PRIMARY)
    c.roundRect(bar_x, bar_y, max(12, bar_w * max(0, min(100, score_total)) / 100), 12, 6, fill=1, stroke=0)
    return y - 126


def _draw_report_profile_block(c: canvas.Canvas, payload: Dict[str, Any], x: float, y: float, width: float, labels: Dict[str, Any]) -> float:
    profile = payload.get("cv_profile") or {}
    skills = [str(item).strip() for item in (profile.get("top_skills") or []) if str(item).strip()]
    skills_text = _truncate_to_width(
        c,
        ", ".join(skills[:5]) or labels["stacks_fallback"],
        170,
        font_name="Helvetica",
        font_size=9,
    )

    c.setFillColor(colors.white)
    c.roundRect(x, y - 88, width, 88, 16, fill=1, stroke=0)
    c.setStrokeColor(COLOR_RH_BORDER)
    c.roundRect(x, y - 88, width, 88, 16, fill=0, stroke=1)

    c.setFillColor(COLOR_INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x + 18, y - 26, labels["profile_overview"])

    c.setFillColor(COLOR_MUTED)
    c.setFont("Helvetica", 10)
    c.drawString(x + 18, y - 52, f"{labels['questions_handled']} : {len(payload.get('turns') or [])}")

    skill_card_w = 210
    skill_card_x = x + width - skill_card_w - 18
    c.setFillColor(COLOR_RH_SURFACE)
    c.roundRect(skill_card_x, y - 64, skill_card_w, 44, 12, fill=1, stroke=0)
    c.setFillColor(COLOR_MUTED)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(skill_card_x + 16, y - 38, labels["stacks_skills"])
    c.setFont("Helvetica", 9)
    c.drawString(skill_card_x + 16, y - 54, skills_text)
    return y - 104


def _draw_report_competency_table(c: canvas.Canvas, report: Dict[str, Any], x: float, y: float, width: float, labels: Dict[str, Any]) -> float:
    competency_labels = labels["competencies"]
    comp = report.get("competencies", {}) or {}
    row_h = 34
    panel_h = row_h * 4 + 24

    c.setFillColor(colors.white)
    c.roundRect(x, y - panel_h, width, panel_h, 16, fill=1, stroke=0)
    c.setStrokeColor(COLOR_RH_BORDER)
    c.roundRect(x, y - panel_h, width, panel_h, 16, fill=0, stroke=1)

    current_y = y - 26
    for key in SKILL_KEYS:
        score = int(comp.get(key, 0) or 0)
        score_color = COLOR_RH_PRIMARY if score >= 4 else COLOR_WARN if score >= 3 else COLOR_DANGER

        c.setFillColor(COLOR_INK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 16, current_y, competency_labels[key])

        bar_x = x + 170
        bar_w = 190
        c.setFillColor(colors.white)
        c.setStrokeColor(COLOR_RH_BORDER)
        c.roundRect(bar_x, current_y - 9, bar_w, 12, 6, fill=1, stroke=1)
        c.setFillColor(score_color)
        c.setStrokeColor(score_color)
        c.roundRect(bar_x, current_y - 9, max(12, bar_w * score / 5), 12, 6, fill=1, stroke=0)

        c.setFillColor(COLOR_MUTED)
        c.setFont("Helvetica", 10)
        c.drawString(x + width - 138, current_y, f"{score}/5")
        c.drawString(x + width - 78, current_y, _score_label(score, labels))
        current_y -= row_h

    return y - panel_h - 14


def _extract_question_grade_rows(payload: Dict[str, Any], report: Dict[str, Any]) -> List[Dict[str, Any]]:
    turns = payload.get("turns") or []
    if not isinstance(turns, list):
        return []

    fallback_score = 0.0
    competencies = report.get("competencies") or {}
    try:
        fallback_score = float(competencies.get("question_score") or 0)
    except (TypeError, ValueError):
        fallback_score = 0.0
    if not fallback_score:
        try:
            fallback_score = max(0.0, min(5.0, float(report.get("score_total") or 0) / 20.0))
        except (TypeError, ValueError):
            fallback_score = 0.0

    rows: List[Dict[str, Any]] = []
    for turn_index, turn in enumerate(turns):
        if not isinstance(turn, dict):
            continue
        answer = str(turn.get("candidate_text") or "").strip()
        previous_turn = turns[turn_index - 1] if turn_index > 0 and isinstance(turns[turn_index - 1], dict) else {}
        question = str(previous_turn.get("say") or "").strip()
        if not answer or not question:
            continue

        score_payload = turn.get("score_partial") if isinstance(turn.get("score_partial"), dict) else {}
        try:
            score = float(score_payload.get("question_score"))
        except (TypeError, ValueError):
            score = 0.0
        if not (0 <= score <= 5):
            score = 0.0

        rows.append(
            {
                "label": f"Q{len(rows) + 1}",
                "question": question,
                "score": score,
                "percent": max(0, min(100, int(round(score * 20)))),
            }
        )

    if rows and all(float(row["score"]) == 0 for row in rows) and fallback_score > 0:
        for row in rows:
            row["score"] = fallback_score
            row["percent"] = max(0, min(100, int(round(fallback_score * 20))))
    return rows[:10]


def _draw_question_grades_table(
    c: canvas.Canvas,
    rows: List[Dict[str, Any]],
    x: float,
    y: float,
    width: float,
    labels: Dict[str, Any],
) -> float:
    if not rows:
        return y

    row_h = 40
    panel_h = 20 + row_h * len(rows)
    c.setFillColor(colors.white)
    c.roundRect(x, y - panel_h, width, panel_h, 16, fill=1, stroke=0)
    c.setStrokeColor(COLOR_RH_BORDER)
    c.roundRect(x, y - panel_h, width, panel_h, 16, fill=0, stroke=1)

    current_y = y - 24
    bar_x = x + width - 190
    bar_w = 112
    for row in rows:
        score = max(0.0, min(5.0, float(row.get("score") or 0)))
        percent = max(0, min(100, int(row.get("percent") or round(score * 20))))
        score_color = COLOR_RH_PRIMARY if score >= 4 else COLOR_WARN if score >= 3 else COLOR_DANGER

        c.setFillColor(COLOR_ACCENT_SOFT)
        c.roundRect(x + 14, current_y - 12, 34, 18, 9, fill=1, stroke=0)
        c.setFillColor(COLOR_ACCENT)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(x + 31, current_y - 6, str(row.get("label") or labels["question_fallback"]))

        c.setFillColor(COLOR_INK)
        _draw_wrapped_limited(
            c,
            str(row.get("question") or labels["question_fallback"]),
            x + 58,
            current_y,
            bar_x - x - 72,
            font_name="Helvetica",
            font_size=8,
            line_height=10,
            max_lines=2,
        )

        c.setFillColor(COLOR_RH_SURFACE)
        c.roundRect(bar_x, current_y - 8, bar_w, 10, 5, fill=1, stroke=0)
        c.setFillColor(score_color)
        c.roundRect(bar_x, current_y - 8, max(8, bar_w * percent / 100), 10, 5, fill=1, stroke=0)

        c.setFillColor(score_color)
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(x + width - 16, current_y - 1, f"{score:.1f}".rstrip("0").rstrip(".") + "/5")

        current_y -= row_h

    return y - panel_h - 14


def _resolve_report_language(payload: Dict[str, Any], report: Dict[str, Any]) -> str:
    language = str(payload.get("response_language", "")).strip().lower()
    if language in {"fr", "en"}:
        return language
    summary = str(report.get("summary", "")).strip().lower()
    if any(marker in summary for marker in ("the candidate", "overall", "strengths", "architecture", "debugging")):
        return "en"
    return "fr"


def build_candidate_report_pdf(session_id: str, payload: Dict[str, Any], output_dir: str | Path | None = None) -> Path:
    out_dir = Path(output_dir) if output_dir is not None else REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_safe_name(session_id)}.pdf"

    report = payload.get("final_report") or {}
    profile = payload.get("cv_profile") or {}
    updated_at = payload.get("updated_at") or datetime.utcnow().isoformat() + "Z"
    report_language = _resolve_report_language(payload, report)
    labels = REPORT_LABELS[report_language]

    candidate_name = str(profile.get("candidate_name", "")).strip() or labels["candidate_fallback"]
    headline = str(profile.get("headline", "")).strip() or labels["profile_fallback"]
    strengths = _normalize_items(report.get("strengths"), labels["balanced_profile"])
    improvements = _normalize_items(report.get("improvement_points") or report.get("risks"), labels["progress_axes"])
    advice = _normalize_items(report.get("advice"), labels["advice_fallback"])
    summary = str(report.get("summary", "") or labels["summary_fallback"]).strip()
    question_grade_rows = _extract_question_grade_rows(payload, report)

    c = canvas.Canvas(str(out_path), pagesize=A4)
    y = _draw_report_header(c, session_id, updated_at, candidate_name, headline, labels)
    y = _draw_report_score_card(c, report, PAGE_MARGIN, y, CONTENT_WIDTH, labels)
    y = _draw_report_profile_block(c, payload, PAGE_MARGIN, y, CONTENT_WIDTH, labels)

    y = _draw_section_title(c, labels["observed_competencies"], PAGE_MARGIN, y)
    y = _draw_report_competency_table(c, report, PAGE_MARGIN, y, CONTENT_WIDTH, labels)
    if question_grade_rows:
        y = _ensure_space(c, y, 40 + len(question_grade_rows) * 40)
        y = _draw_section_title(c, labels["question_grades"], PAGE_MARGIN, y)
        y = _draw_question_grades_table(c, question_grade_rows, PAGE_MARGIN, y, CONTENT_WIDTH, labels)

    left_w = (CONTENT_WIDTH - 12) / 2
    right_x = PAGE_MARGIN + left_w + 12
    review_panel_height = max(
        34 + _estimate_bullets_height(c, strengths[:3], left_w - 28),
        34 + _estimate_bullets_height(c, improvements[:3], left_w - 28),
    )

    y = _ensure_space(c, y, review_panel_height + 40)
    y = _draw_section_title(c, labels["technical_review"], PAGE_MARGIN, y)

    top_y = y
    y_left = _draw_bullet_panel(
        c,
        title=labels["strengths"],
        items=strengths[:3],
        x=PAGE_MARGIN,
        y=top_y,
        width=left_w,
        fill=COLOR_PANEL_SOFT,
        bullet_color=COLOR_ACCENT,
    )
    y_right = _draw_bullet_panel(
        c,
        title=labels["improvements"],
        items=improvements[:3],
        x=right_x,
        y=top_y,
        width=left_w,
        fill=COLOR_PANEL_SOFT,
        bullet_color=COLOR_WARN,
    )

    y = min(y_left, y_right) - 16
    advice_height = _estimate_bullets_height(c, advice, CONTENT_WIDTH) + 28
    y = _ensure_space(c, y, advice_height + 24)
    y = _draw_section_title(c, labels["advice"], PAGE_MARGIN, y)
    y = _draw_bullet_panel(
        c,
        title=labels["advice"],
        items=advice,
        x=PAGE_MARGIN,
        y=y,
        width=CONTENT_WIDTH,
        fill=COLOR_PANEL_SOFT,
        bullet_color=COLOR_WARN,
    ) - 4

    summary_height = _estimate_wrapped_height(c, summary, CONTENT_WIDTH - 28, line_height=15) + 50
    y = _ensure_space(c, y, summary_height + 24)
    y = _draw_section_title(c, labels["summary"], PAGE_MARGIN, y)
    _draw_note_panel(
        c,
        title=labels["summary"],
        text=summary,
        x=PAGE_MARGIN,
        y=y,
        width=CONTENT_WIDTH,
        accent=COLOR_ACCENT,
    )

    _draw_footer(c, labels["report_title"])
    c.save()
    return out_path


def build_candidate_insights_pdf(session_id: str, payload: Dict[str, Any], output_dir: str | Path | None = None) -> Path:
    out_dir = Path(output_dir) if output_dir is not None else REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_safe_name(session_id)}-insights.pdf"

    report = payload.get("final_report") or {}
    profile = payload.get("cv_profile") or {}
    updated_at = payload.get("updated_at") or datetime.utcnow().isoformat() + "Z"
    report_language = _resolve_report_language(payload, report)
    labels = REPORT_LABELS[report_language]

    candidate_name = str(profile.get("candidate_name", "")).strip() or labels["candidate_fallback"]
    headline = str(profile.get("headline", "")).strip() or labels["profile_fallback"]
    visual_context = payload.get("visual_context") or {}
    audio_context = payload.get("audio_context") or {}
    stress_context = payload.get("stress_context") or {}
    insights_advice = payload.get("insights_advice") or {}

    visual_metrics = visual_context.get("metrics") or report.get("visual_metrics") or {}
    audio_metrics = audio_context.get("metrics") or report.get("audio_metrics") or {}
    visual_signals = _normalize_items(visual_context.get("signals") or report.get("visual_signals"), labels["no_visual_signal"])
    audio_signals = _normalize_items(audio_context.get("signals") or report.get("audio_signals"), labels["no_audio_signal"])
    insights_items = _normalize_items(
        insights_advice.get("summary") or insights_advice.get("next_steps") or report.get("advice"),
        labels["insights_fallback"],
    )
    stress_summary = str(stress_context.get("summary") or labels["stress_fallback"]).strip()
    confidence_parts = [
        str(visual_context.get("confidence_note") or "").strip(),
        str(audio_context.get("confidence_note") or report.get("audio_confidence_note") or "").strip(),
        str(stress_context.get("confidence_note") or "").strip(),
    ]
    confidence_notes = [item for item in confidence_parts if item]

    visual_average = round(
        (
            _normalize_percent(visual_metrics.get("face_detected_pct"))
            + _normalize_percent(visual_metrics.get("centered_pct"))
            + _normalize_percent(visual_metrics.get("stable_posture_pct"))
            + _normalize_percent(visual_metrics.get("visual_enthusiasm_pct") or visual_metrics.get("engaged_pct"))
        )
        / 4
    )
    audio_average = round(
        (
            _normalize_percent(audio_metrics.get("volume_score_avg"))
            + _normalize_percent(audio_metrics.get("silence_pct_avg"))
            + _normalize_percent(audio_metrics.get("pitch_variation_hz_avg"))
            + _normalize_percent(audio_metrics.get("speech_rate_wpm_avg"))
        )
        / 4
    )
    stress_score = _normalize_percent(stress_context.get("score"))

    visual_metric_rows = [
        {"label": labels["face_detected"], "value": _normalize_percent(visual_metrics.get("face_detected_pct")), "detail": f"{_normalize_percent(visual_metrics.get('face_detected_pct'))}%"},
        {"label": labels["centering"], "value": _normalize_percent(visual_metrics.get("centered_pct")), "detail": f"{_normalize_percent(visual_metrics.get('centered_pct'))}%"},
        {"label": labels["stable_posture"], "value": _normalize_percent(visual_metrics.get("stable_posture_pct")), "detail": f"{_normalize_percent(visual_metrics.get('stable_posture_pct'))}%"},
        {"label": labels["visual_engagement"], "value": _normalize_percent(visual_metrics.get("visual_enthusiasm_pct") or visual_metrics.get("engaged_pct")), "detail": f"{_normalize_percent(visual_metrics.get('visual_enthusiasm_pct') or visual_metrics.get('engaged_pct'))}%"},
    ]
    audio_metric_rows = [
        {"label": labels["speech_rate"], "value": _normalize_percent(audio_metrics.get("speech_rate_wpm_avg")), "detail": f"{_normalize_percent(audio_metrics.get('speech_rate_wpm_avg'))}"},
        {"label": labels["volume"], "value": _normalize_percent(audio_metrics.get("volume_score_avg")), "detail": f"{_normalize_percent(audio_metrics.get('volume_score_avg'))}%"},
        {"label": labels["useful_silence"], "value": _normalize_percent(audio_metrics.get("silence_pct_avg")), "detail": f"{_normalize_percent(audio_metrics.get('silence_pct_avg'))}%"},
        {"label": labels["variation"], "value": _normalize_percent(audio_metrics.get("pitch_variation_hz_avg")), "detail": f"{_normalize_percent(audio_metrics.get('pitch_variation_hz_avg'))}"},
    ]

    emotion_breakdown = (
        visual_metrics.get("model_emotion_breakdown")
        or visual_metrics.get("emotion_breakdown")
        or visual_metrics.get("raw_emotion_breakdown")
        or {}
    )
    emotion_labels = labels["emotion_labels"]
    emotion_tags = [
        f"{emotion_labels[key]} {_normalize_percent(emotion_breakdown.get(key))}%"
        for key in ("happy", "angry", "sad", "neutral", "surprise")
    ]

    c = canvas.Canvas(str(out_path), pagesize=A4)
    original_title = labels["report_title"]
    original_subtitle = labels["report_subtitle"]
    labels["report_title"] = labels["insights_report_title"]
    labels["report_subtitle"] = labels["insights_report_subtitle"]
    y = _draw_header(c, session_id, updated_at, candidate_name, headline, labels)
    labels["report_title"] = original_title
    labels["report_subtitle"] = original_subtitle

    y = _draw_section_title(c, labels["insights_overview"], PAGE_MARGIN, y)
    stat_width = (CONTENT_WIDTH - 24) / 3
    top_y = y
    y_a = _draw_stat_card(
        c,
        x=PAGE_MARGIN,
        y=top_y,
        width=stat_width,
        title=labels["visual_score"],
        value=f"{visual_average}%",
        caption=labels["average_caption"],
        accent=COLOR_ACCENT,
        fill=COLOR_PANEL_SOFT,
    )
    y_b = _draw_stat_card(
        c,
        x=PAGE_MARGIN + stat_width + 12,
        y=top_y,
        width=stat_width,
        title=labels["audio_score"],
        value=f"{audio_average}%",
        caption=labels["average_caption"],
        accent=COLOR_ACCENT,
        fill=COLOR_PANEL_SOFT,
    )
    y_c = _draw_stat_card(
        c,
        x=PAGE_MARGIN + (stat_width + 12) * 2,
        y=top_y,
        width=stat_width,
        title=labels["stress_score"],
        value=f"{stress_score}%",
        caption=labels["stress_caption"],
        accent=COLOR_WARN,
        fill=COLOR_PANEL_SOFT,
    )
    y = min(y_a, y_b, y_c)

    highlights_height = 34 + _estimate_bullets_height(c, insights_items[:4], CONTENT_WIDTH - 28)
    y = _ensure_space(c, y, highlights_height + 24)
    y = _draw_section_title(c, labels["insights_highlights"], PAGE_MARGIN, y)
    y = _draw_bullet_panel(
        c,
        title=labels["insights_highlights"],
        items=insights_items[:4],
        x=PAGE_MARGIN,
        y=y,
        width=CONTENT_WIDTH,
        fill=COLOR_PANEL_SOFT,
        bullet_color=COLOR_ACCENT,
    ) - 4

    left_w = (CONTENT_WIDTH - 12) / 2
    right_x = PAGE_MARGIN + left_w + 12
    y = _ensure_space(c, y, 220)
    top_y = y
    y_left = _draw_bullet_panel(
        c,
        title=labels["visual_signals_title"],
        items=visual_signals[:5],
        x=PAGE_MARGIN,
        y=top_y,
        width=left_w,
        fill=COLOR_PANEL_SOFT,
        bullet_color=COLOR_ACCENT,
    )
    y_right = _draw_bullet_panel(
        c,
        title=labels["audio_signals_title"],
        items=audio_signals[:5],
        x=right_x,
        y=top_y,
        width=left_w,
        fill=COLOR_PANEL_SOFT,
        bullet_color=COLOR_ACCENT,
    )
    y = min(y_left, y_right) - 4

    stress_height = 28 + _estimate_wrapped_height(c, stress_summary, CONTENT_WIDTH - 28, line_height=15)
    y = _ensure_space(c, y, stress_height + 24)
    y = _draw_section_title(c, labels["stress_summary_title"], PAGE_MARGIN, y)
    y = _draw_text_panel(c, text=stress_summary, x=PAGE_MARGIN, y=y, width=CONTENT_WIDTH, font_size=10, line_height=15) - 4

    y = _ensure_space(c, y, 250)
    top_y = y
    y_left = _draw_metric_panel(
        c,
        title=labels["visual_metrics_title"],
        metrics=visual_metric_rows,
        x=PAGE_MARGIN,
        y=top_y,
        width=left_w,
        accent=COLOR_INFO,
    )
    y_right = _draw_metric_panel(
        c,
        title=labels["audio_metrics_title"],
        metrics=audio_metric_rows,
        x=right_x,
        y=top_y,
        width=left_w,
        accent=COLOR_ACCENT,
    )
    y = min(y_left, y_right) - 4

    y = _ensure_space(c, y, 120)
    top_y = y
    y_left = _draw_tag_panel(
        c,
        title=labels["emotion_breakdown_title"],
        tags=emotion_tags,
        x=PAGE_MARGIN,
        y=top_y,
        width=left_w,
        fill=COLOR_PANEL_SOFT,
        accent=COLOR_ACCENT,
    )
    info_text = " ".join(confidence_notes) if confidence_notes else labels["metrics_fallback"]
    y_right = _draw_note_panel(
        c,
        title=labels["confidence_note"],
        text=info_text,
        x=right_x,
        y=top_y,
        width=left_w,
    )
    y = min(y_left, y_right)

    _draw_footer(c, labels["insights_report_title"])
    c.save()
    return out_path

