from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from src.api.routers import admin, auth, health, papers, reports, reviews, users
from src.core.config import Settings, settings
from src.core.email import send_review_assignment_email
from src.core.logging import setup_logging
from src.tasks.evaluation_task import dispatch_evaluation_task


def create_app(*, app_settings: Settings | None = None) -> FastAPI:
    runtime_settings = app_settings or settings
    setup_logging()
    app = FastAPI(title="文科论文评价系统 API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=runtime_settings.secret_key,
        same_site="lax",
        session_cookie="socialeval_session",
        https_only=runtime_settings.secure_session_cookie,
        domain=runtime_settings.cookie_domain,
    )
    app.state.settings = runtime_settings
    app.state.pipeline_runner = None
    app.state.task_dispatcher = dispatch_evaluation_task
    app.state.email_sender = send_review_assignment_email
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(users.router, prefix="/api/users", tags=["users"])
    app.include_router(papers.router, prefix="/api/papers", tags=["papers"])
    app.include_router(reports.router, prefix="/api/papers", tags=["reports"])
    app.include_router(reviews.router, prefix="/api/reviews", tags=["reviews"])
    app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
    return app


app = create_app()
