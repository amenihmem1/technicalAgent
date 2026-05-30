from fastapi import FastAPI

from services.common.service_app import create_service_app


def build_interview_app() -> FastAPI:
    return create_service_app("interview")

