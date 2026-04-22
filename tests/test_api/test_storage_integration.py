from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.core.object_storage import StoredObject
from src.evaluation.schemas import DimensionResult
from src.models.paper import Paper
from tests.test_api.conftest import create_user


class FakeRemoteStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> StoredObject:
        location = f"s3://socialeval-test/{key}"
        self.objects[location] = content
        return StoredObject(location=location, key=key)

    def get_bytes(self, location: str) -> bytes:
        return self.objects[location]


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


def _login_submitter(client: TestClient, db_session: Session) -> None:
    create_user(
        db_session,
        email="submitter@example.com",
        role="submitter",
        display_name="Submitter",
    )
    login_response = client.post(
        "/api/auth/login",
        json={"email": "submitter@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200


def test_remote_storage_upload_still_runs_pipeline(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    from src.evaluation.orchestrator import run_evaluation_pipeline

    fake_storage = FakeRemoteStorage()

    monkeypatch.setattr("src.core.storage.get_storage_backend", lambda: fake_storage)
    monkeypatch.setattr(
        "src.core.storage.get_backend_for_location",
        lambda location: fake_storage if location.startswith("s3://") else None,
    )

    async def pipeline_runner(task_id: str, db: Session) -> None:
        await run_evaluation_pipeline(
            task_id,
            db,
            provider_factory=lambda _: [
                FakeProvider("mock-a", 80),
                FakeProvider("mock-b", 82),
                FakeProvider("mock-c", 84),
            ],
        )

    client.app.state.pipeline_runner = pipeline_runner
    _login_submitter(client, db_session)

    response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "摘要\n正文内容\n参考文献\n[1] 文献".encode("utf-8"), "text/plain")},
        data={"provider_names": "mock-a,mock-b,mock-c"},
    )

    assert response.status_code == 202
    payload = response.json()
    paper = db_session.get(Paper, payload["paper_id"])
    assert paper is not None
    assert paper.file_path.startswith("s3://socialeval-test/uploads/")
    start_response = client.post(f"/api/papers/{payload['paper_id']}/start")
    assert start_response.status_code == 202

    status_response = client.get(f"/api/papers/{payload['paper_id']}/status")
    assert status_response.status_code == 200
    assert status_response.json()["task_status"] == "completed"
