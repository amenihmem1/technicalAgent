from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from core.config import load_settings
from core.factories import build_emotion_analyzer
from vision.emotion import emotion_analysis_to_dict


def _str_to_bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _optional_float(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def _build_frame_hint(args: argparse.Namespace) -> dict[str, Any]:
    hint: dict[str, Any] = {}

    if args.face_detected is not None:
        hint["face_detected"] = _str_to_bool(args.face_detected)
    if args.centered is not None:
        hint["centered"] = _str_to_bool(args.centered)
    if args.looking_forward is not None:
        hint["looking_forward"] = _str_to_bool(args.looking_forward)
    if args.expression:
        hint["expression"] = args.expression.strip()
    if args.posture:
        hint["posture"] = args.posture.strip()
    if args.face_count is not None:
        hint["face_count"] = max(0, int(args.face_count))

    face_box_values = {
        "left": _optional_float(args.face_box_left),
        "top": _optional_float(args.face_box_top),
        "right": _optional_float(args.face_box_right),
        "bottom": _optional_float(args.face_box_bottom),
    }
    if all(value is not None for value in face_box_values.values()):
        hint["face_box"] = face_box_values

    return hint


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the custom live emotion analyzer on one image file.",
    )
    parser.add_argument("images", nargs="+", help="Path(s) to JPG/PNG/WebP image(s) to analyze.")
    parser.add_argument(
        "--raw-model-only",
        action="store_true",
        help="Return the raw model label without uncertainty calibration.",
    )
    parser.add_argument(
        "--allow-unverified",
        action="store_true",
        help="Allow running even if model behavior validation fails.",
    )
    parser.add_argument("--face-detected", choices=("true", "false"))
    parser.add_argument("--centered", choices=("true", "false"))
    parser.add_argument("--looking-forward", choices=("true", "false"))
    parser.add_argument("--expression", default="")
    parser.add_argument("--posture", default="")
    parser.add_argument("--face-count", type=int)
    parser.add_argument("--face-box-left")
    parser.add_argument("--face-box-top")
    parser.add_argument("--face-box-right")
    parser.add_argument("--face-box-bottom")
    args = parser.parse_args()

    if args.raw_model_only:
        os.environ["CUSTOM_EMOTION_RAW_MODEL_ONLY"] = "true"
    if args.allow_unverified:
        os.environ["CUSTOM_EMOTION_ALLOW_UNVERIFIED"] = "true"

    image_paths = [Path(image).expanduser() for image in args.images]
    missing = [path for path in image_paths if not path.exists() or not path.is_file()]
    if missing:
        raise SystemExit(f"Image introuvable: {missing[0]}")

    settings = load_settings()
    analyzer = build_emotion_analyzer(settings)
    frame_hint = _build_frame_hint(args) or None
    results = []
    for image_path in image_paths:
        result = analyzer.analyze_image_bytes(
            image_path.read_bytes(),
            frame_hint=frame_hint,
        )
        results.append(
            {
                "image": str(image_path),
                "analysis": emotion_analysis_to_dict(result),
            }
        )

    payload: Any = results[0] if len(results) == 1 else results
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
