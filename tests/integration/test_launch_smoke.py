from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient
from passlib.context import CryptContext
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import src.models  # noqa: F401
from src.core.database import Base, get_db
from src.evaluation.schemas import DimensionResult
from src.models.user import User


PWD_CONTEXT = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


@dataclass
class FakeProvider:
    model_name: str
    score: int
    precheck_status: str = "pass"

    async def evaluate_dimension(self, prompt: str) -> DimensionResult:
        return DimensionResult(
            dimension="placeholder",
            score=self.score,
            evidence_quotes=["引文"],
            analysis=f"{self.model_name} analysis",
            model_name=self.model_name,
        )

    async def generate_json_response(self, prompt: str) -> dict:
        return {
            "status": self.precheck_status,
            "issues": [],
            "recommendation": "continue",
        }


def create_user(
    db_session: Session,
    *,
    email: str,
    password: str = "secret123",
    role: str = "submitter",
    is_active: bool = True,
    display_name: str | None = None,
) -> User:
    user = User(
        email=email,
        hashed_password=PWD_CONTEXT.hash(password),
        role=role,
        is_active=is_active,
        display_name=display_name,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@contextmanager
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = testing_session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_launch_smoke_flow(tmp_path: Path) -> None:
    from src.api.main import create_app
    from src.evaluation.orchestrator import run_evaluation_pipeline

    with db_session(tmp_path) as db:
        app = create_app()

        def override_get_db() -> Generator[Session, None, None]:
            try:
                yield db
            finally:
                db.rollback()

        async def pipeline_runner(task_id: str, db_session: Session) -> None:
            await run_evaluation_pipeline(
                task_id,
                db_session,
                provider_factory=lambda _: [
                    FakeProvider("mock-a", 60),
                    FakeProvider("mock-b", 80),
                    FakeProvider("mock-c", 95),
                ],
            )

        app.dependency_overrides[get_db] = override_get_db
        app.state.pipeline_runner = pipeline_runner

        create_user(db, email="submitter@example.com", role="submitter", display_name="Submitter")
        create_user(db, email="editor@example.com", role="editor", display_name="Editor")

        with TestClient(app) as client:
            login_response = client.post(
                "/api/auth/login",
                json={"email": "submitter@example.com", "password": "secret123"},
            )
            assert login_response.status_code == 200

            upload_response = client.post(
                "/api/papers",
                files={"file": ("paper.txt", "摘要\n正文内容\n参考文献\n[1] 文献".encode("utf-8"), "text/plain")},
                data={"provider_names": "mock-a,mock-b,mock-c"},
            )
            assert upload_response.status_code == 202
            payload = upload_response.json()
            start_response = client.post(f"/api/papers/{payload['paper_id']}/start")
            assert start_response.status_code == 202

            status_response = client.get(f"/api/papers/{payload['paper_id']}/status")
            assert status_response.status_code == 200
            assert status_response.json()["task_status"] == "completed"

            public_report = client.get(f"/api/papers/{payload['paper_id']}/report")
            assert public_report.status_code == 200
            assert "weighted_total" in public_report.json()

            client.cookies.clear()
            editor_login = client.post(
                "/api/auth/login",
                json={"email": "editor@example.com", "password": "secret123"},
            )
            assert editor_login.status_code == 200

            internal_report = client.get(f"/api/papers/{payload['paper_id']}/internal-report")
            assert internal_report.status_code == 200

            review_queue = client.get("/api/reviews/queue")
            assert review_queue.status_code == 200
            assert review_queue.json()["items"][0]["paper_id"] == payload["paper_id"]
