from __future__ import annotations

from collections.abc import Callable
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from services.common.runtime import build_app


RouteMatcher = Callable[[str, str], bool]


def _is_session_detail(path: str) -> bool:
    if not path.startswith("/tech/sessions/"):
        return False
    suffix = path.removeprefix("/tech/sessions/").strip("/")
    return bool(suffix) and "/" not in suffix


def _is_session_action(path: str, actions: set[str]) -> bool:
    if not path.startswith("/tech/sessions/"):
        return False
    parts = path.strip("/").split("/")
    return len(parts) == 4 and parts[0] == "tech" and parts[1] == "sessions" and parts[3] in actions


def _interview_route(method: str, path: str) -> bool:
    if path == "/health":
        return True
    if method == "GET" and path == "/tech/sessions":
        return True
    if method == "GET" and _is_session_detail(path):
        return True
    if method == "DELETE" and _is_session_detail(path):
        return True
    if method == "PATCH" and _is_session_action(path, {"meta", "preferences"}):
        return True
    if method == "POST" and _is_session_action(path, {"message", "cv", "docs", "finalize"}):
        return True
    return False


def _media_route(method: str, path: str) -> bool:
    if path in {"/health", "/tech/stt", "/tech/tts"}:
        return True
    return method == "POST" and _is_session_action(path, {"audio", "vision", "proctoring"})


def _websocket_route(service_name: str, path: str) -> bool:
    if service_name == "media":
        return path == "/ws/tech/stt/{session_id}"
    if service_name == "interview":
        return path == "/ws/tech/{session_id}"
    return False


MATCHERS: dict[str, RouteMatcher] = {
    "interview": _interview_route,
    "media": _media_route,
}


def _filter_routes(app: FastAPI, service_name: str, matcher: RouteMatcher) -> None:
    filtered_routes = []
    for route in app.router.routes:
        path = str(getattr(route, "path", "") or "").rstrip("/") or "/"
        methods = getattr(route, "methods", None)
        if methods is None:
            if _websocket_route(service_name, path):
                filtered_routes.append(route)
            continue
        if any(matcher(str(method).upper(), path) for method in methods):
            filtered_routes.append(route)
    app.router.routes = filtered_routes


def create_service_app(service_name: str) -> FastAPI:
    runtime_service = "all" if service_name == "media" else service_name
    app = build_app(service_name=runtime_service)
    app.title = f"Technique Agent {service_name.title()} Service"
    matcher = MATCHERS[service_name]
    _filter_routes(app, service_name, matcher)

    @app.middleware("http")
    async def enforce_service_boundary(request: Request, call_next):
        path = request.url.path.rstrip("/") or "/"
        method = request.method.upper()
        if not matcher(method, path):
            return JSONResponse(
                status_code=404,
                content={
                    "detail": "Route is not exposed by this microservice.",
                    "service": service_name,
                },
            )
        return await call_next(request)

    return app

