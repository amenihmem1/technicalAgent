from __future__ import annotations

import unicodedata
from typing import Any, Sequence


def _normalize_history_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(normalized.split())


def _format_session_title(profile: dict[str, Any], turns: list[dict[str, Any]], session_id: str) -> str:
    headline = str(profile.get("headline", "") or "").strip()
    name = str(profile.get("candidate_name", "") or profile.get("name", "") or "").strip()
    if headline:
        return headline
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        question = str(turn.get("say", "") or "").strip()
        if question:
            compact = " ".join(question.split())
            return compact[:72] + ("..." if len(compact) > 72 else "")
    if name:
        return f"Entretien technique - {name}"
    return session_id


def normalize_history_title(value: str | None) -> str:
    title = " ".join(str(value or "").split()).strip()
    return title[:120]


def _build_history_preview(payload: dict[str, Any], turns: list[dict[str, Any]]) -> str:
    report = payload.get("final_report")
    if isinstance(report, dict):
        summary = str(report.get("summary", "") or "").strip()
        if summary:
            return summary[:140] + ("..." if len(summary) > 140 else "")

    for turn in reversed(turns):
        if not isinstance(turn, dict):
            continue
        answer = str(turn.get("candidate_text", "") or "").strip()
        if answer:
            return answer[:140] + ("..." if len(answer) > 140 else "")
    return ""


def build_candidate_history_key(profile: dict[str, Any], session_id: str) -> str:
    email = _normalize_history_text(profile.get("email", ""))
    linkedin = _normalize_history_text(profile.get("linkedin", ""))
    github = _normalize_history_text(profile.get("github", ""))
    candidate_name = _normalize_history_text(profile.get("candidate_name") or profile.get("name") or "")
    headline = _normalize_history_text(profile.get("headline", ""))

    if email:
        return f"email:{email}"
    if linkedin:
        return f"linkedin:{linkedin}"
    if github:
        return f"github:{github}"
    if candidate_name:
        return f"name:{candidate_name}:{headline}"
    return f"session:{session_id}"


def _session_history_anchor_at(payload: dict[str, Any], turns: Sequence[Any], updated_at: str) -> str:
    finalized = str(payload.get("finalized_at", "") or "").strip()
    if finalized:
        return finalized
    for turn in turns:
        if isinstance(turn, dict) and str(turn.get("time", "") or "").strip():
            return str(turn.get("time", "") or "").strip()
    created = str(payload.get("created_at", "") or "").strip()
    if created:
        return created
    return str(updated_at or "").strip()


def build_session_history_item(payload: dict[str, Any]) -> dict[str, Any] | None:
    session_id = str(payload.get("session_id", "") or "").strip()
    if not session_id:
        return None

    profile = payload.get("cv_profile")
    profile = profile if isinstance(profile, dict) else {}
    turns = payload.get("turns")
    turns = turns if isinstance(turns, list) else []
    report = payload.get("final_report")
    report = report if isinstance(report, dict) else None
    history_meta = payload.get("history_meta")
    history_meta = history_meta if isinstance(history_meta, dict) else {}

    updated_at = str(payload.get("updated_at", "") or "").strip()
    if not updated_at:
        for turn in reversed(turns):
            if isinstance(turn, dict) and str(turn.get("time", "") or "").strip():
                updated_at = str(turn.get("time", "") or "").strip()
                break

    history_at = _session_history_anchor_at(payload, turns, updated_at)
    score_total = report.get("score_total") if isinstance(report, dict) else None
    score_total = int(score_total) if isinstance(score_total, (int, float)) else None

    candidate_name = str(profile.get("candidate_name") or profile.get("name") or "").strip() or "Candidate"
    candidate_key = build_candidate_history_key(profile, session_id)
    completed = report is not None
    started = bool(turns) or bool(payload.get("cv_uploaded")) or bool(payload.get("documents"))
    title_override = normalize_history_title(history_meta.get("title"))

    return {
        "session_id": session_id,
        "candidate_key": candidate_key,
        "candidate_name": candidate_name,
        "headline": str(profile.get("headline", "") or "").strip(),
        "updated_at": updated_at,
        "created_at": str(payload.get("created_at", "") or "").strip(),
        "history_at": history_at,
        "finalized_at": str(payload.get("finalized_at", "") or "").strip(),
        "turns_count": len(turns),
        "score_total": score_total,
        "status": "completed" if completed else "active" if started else "draft",
        "title": title_override or _format_session_title(profile, turns, session_id),
        "preview": _build_history_preview(payload, turns),
        "response_language": str(payload.get("response_language", "") or "").strip().lower() or "fr",
        "pinned": bool(history_meta.get("pinned", False)),
        "archived": bool(history_meta.get("archived", False)),
        "title_customized": bool(title_override),
        "proctoring_alerts_count": len(payload.get("proctoring_events", []))
        if isinstance(payload.get("proctoring_events"), list)
        else 0,
    }


def _build_progression_payload(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    scored_sessions = [session for session in sessions if isinstance(session.get("score_total"), int)]
    latest_score = scored_sessions[0]["score_total"] if scored_sessions else None
    previous_score = scored_sessions[1]["score_total"] if len(scored_sessions) > 1 else None
    delta = (latest_score - previous_score) if isinstance(latest_score, int) and isinstance(previous_score, int) else None

    if delta is None:
        label = "first_completed_session" if latest_score is not None else "no_completed_session"
    elif delta > 0:
        label = "improving"
    elif delta < 0:
        label = "declining"
    else:
        label = "stable"

    return {
        "latest_score": latest_score,
        "previous_score": previous_score,
        "delta": delta,
        "label": label,
    }


def build_candidate_history_groups(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    sessions: list[dict[str, Any]] = []

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        session = build_session_history_item(payload)
        if session is None:
            continue
        sessions.append(session)
        key = session["candidate_key"]
        group = grouped.get(key)
        if group is None:
            group = {
                "candidate_key": key,
                "candidate_name": session["candidate_name"],
                "headline": session["headline"],
                "latest_updated_at": session["updated_at"],
                "sessions": [],
            }
            grouped[key] = group

        if session["updated_at"] > str(group.get("latest_updated_at", "") or ""):
            group["latest_updated_at"] = session["updated_at"]
        if not str(group.get("headline", "") or "").strip() and session["headline"]:
            group["headline"] = session["headline"]
        if group.get("candidate_name") == "Candidate" and session["candidate_name"] != "Candidate":
            group["candidate_name"] = session["candidate_name"]
        group["sessions"].append(session)

    candidates: list[dict[str, Any]] = []
    for group in grouped.values():
        group_sessions = sorted(
            group["sessions"],
            key=lambda item: str(item.get("updated_at", "") or ""),
            reverse=True,
        )
        group["sessions"] = group_sessions
        group["sessions_count"] = len(group_sessions)
        group["progression"] = _build_progression_payload(group_sessions)
        candidates.append(group)

    candidates.sort(key=lambda item: str(item.get("latest_updated_at", "") or ""), reverse=True)
    sorted_sessions = sorted(
        sessions,
        key=lambda item: (
            1 if bool(item.get("pinned")) else 0,
            str(item.get("updated_at", "") or ""),
        ),
        reverse=True,
    )
    return {
        "candidates": candidates,
        "sessions": sorted_sessions,
        "total_candidates": len(candidates),
        "total_sessions": sum(int(candidate.get("sessions_count", 0) or 0) for candidate in candidates),
    }
