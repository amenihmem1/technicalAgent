from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def require_cv_uploaded_for_message(state: Any) -> None:
    if not bool(getattr(state, "cv_uploaded", False)):
        raise HTTPException(
            status_code=400,
            detail="Le candidat doit telecharger son CV avant de commencer l'entretien technique.",
        )
