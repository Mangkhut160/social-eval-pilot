from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.core.config import Settings
from src.evaluation.schemas import DimensionResult
from src.models.evaluation import AICallLog, DimensionScore
from src.models.paper import Paper
from src.models.report import Report, ReportExport
from src.models.reliability import ReliabilityResult
from tests.test_api.conftest import create_user


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
            "issues": [] if self.precheck_status == "pass" else ["写作规范性不足"],
            "recommendation": "continue" if self.precheck_status == "pass" else "reject",
        }


def _install_sync_pipeline(client: TestClient, providers: list[FakeProvider]) -> None:
    from src.evaluation.orchestrator import run_evaluation_pipeline

    async def pipeline_runner(task_id: str, db: Session) -> None:
        await run_evaluation_pipeline(
            task_id,
            db,
            provider_factory=lambda _: providers,
        )

    client.app.state.pipeline_runner = pipeline_runner


def _login(client: TestClient, email: str, password: str = "secret123") -> None:
    login_response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200


def _login_submitter(client: TestClient, db_session: Session) -> None:
    create_user(
        db_session,
        email="submitter@example.com",
        role="submitter",
        display_name="Submitter",
    )
    _login(client, "submitter@example.com")


def test_upload_txt_file_runs_pipeline_and_persists_results(
    client: TestClient, db_session: Session
) -> None:
    _login_submitter(client, db_session)
    _install_sync_pipeline(
        client,
        [
            FakeProvider("mock-a", 80),
            FakeProvider("mock-b", 82),
            FakeProvider("mock-c", 84),
        ],
    )

    upload_response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "摘要\n正文内容\n参考文献\n[1] 文献".encode("utf-8"), "text/plain")},
        data={"provider_names": "mock-a,mock-b,mock-c"},
    )
    assert upload_response.status_code == 202

    payload = upload_response.json()
    status_response = client.get(f"/api/papers/{payload['paper_id']}/status")
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["paper_status"] == "pending"
    assert body["task_status"] == "pending"
    assert body["precheck_status"] is None
    assert body["reliability_summary"] is None
    assert db_session.query(DimensionScore).count() == 0
    assert db_session.query(ReliabilityResult).count() == 0

    start_response = client.post(f"/api/papers/{payload['paper_id']}/start")
    assert start_response.status_code == 202

    status_response = client.get(f"/api/papers/{payload['paper_id']}/status")
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["paper_status"] == "completed"
    assert body["task_status"] == "completed"
    assert body["precheck_status"] == "pass"
    assert body["reliability_summary"]["total_dimensions"] == 6
    assert body["reliability_summary"]["overall_high_confidence"] is True

    assert db_session.query(DimensionScore).count() == 18
    assert db_session.query(ReliabilityResult).count() == 6


def test_precheck_reject_short_circuits_dimension_scoring(
    client: TestClient, db_session: Session
) -> None:
    _login_submitter(client, db_session)
    _install_sync_pipeline(
        client,
        [
            FakeProvider("mock-a", 10, precheck_status="reject"),
            FakeProvider("mock-b", 20, precheck_status="reject"),
            FakeProvider("mock-c", 30, precheck_status="reject"),
        ],
    )

    upload_response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "正文".encode("utf-8"), "text/plain")},
        data={"provider_names": "mock-a,mock-b,mock-c"},
    )
    assert upload_response.status_code == 202

    payload = upload_response.json()
    start_response = client.post(f"/api/papers/{payload['paper_id']}/start")
    assert start_response.status_code == 202

    status_response = client.get(f"/api/papers/{payload['paper_id']}/status")
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["precheck_status"] == "reject"
    assert body["task_status"] == "completed"
    assert body["reliability_summary"] is None
    assert db_session.query(DimensionScore).count() == 0


def test_upload_rejects_unsupported_file_type(
    client: TestClient, db_session: Session
) -> None:
    _login_submitter(client, db_session)

    response = client.post(
        "/api/papers",
        files={"file": ("paper.doc", b"binary", "application/msword")},
    )

    assert response.status_code == 400


def test_submitter_cannot_read_another_submitters_paper_status(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter-a@example.com", role="submitter")
    create_user(db_session, email="submitter-b@example.com", role="submitter")

    _login(client, "submitter-a@example.com")
    upload_response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "正文内容".encode("utf-8"), "text/plain")},
        data={"provider_names": "mock-a,mock-b"},
    )
    assert upload_response.status_code == 202
    paper_id = upload_response.json()["paper_id"]

    client.cookies.clear()
    _login(client, "submitter-b@example.com")
    status_response = client.get(f"/api/papers/{paper_id}/status")

    assert status_response.status_code == 403


def test_batch_upload_returns_multiple_tasks(
    client: TestClient, db_session: Session
) -> None:
    _login_submitter(client, db_session)
    _install_sync_pipeline(
        client,
        [
            FakeProvider("mock-a", 75),
            FakeProvider("mock-b", 78),
            FakeProvider("mock-c", 81),
        ],
    )

    response = client.post(
        "/api/papers/batch",
        files=[
            ("files", ("one.txt", "正文一".encode("utf-8"), "text/plain")),
            ("files", ("two.txt", "正文二".encode("utf-8"), "text/plain")),
        ],
        data={"provider_names": "mock-a,mock-b,mock-c"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert {item["task_status"] for item in body["items"]} == {"pending"}


def test_batch_status_requires_batch_owner_or_staff_role(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter-a@example.com", role="submitter")
    create_user(db_session, email="submitter-b@example.com", role="submitter")

    _login(client, "submitter-a@example.com")
    batch_response = client.post(
        "/api/papers/batch",
        files=[
            ("files", ("one.txt", "正文一".encode("utf-8"), "text/plain")),
            ("files", ("two.txt", "正文二".encode("utf-8"), "text/plain")),
        ],
        data={"provider_names": "mock-a,mock-b"},
    )
    assert batch_response.status_code == 202
    batch_id = batch_response.json()["batch_id"]

    client.cookies.clear()
    _login(client, "submitter-b@example.com")
    status_response = client.get(f"/api/papers/batch/{batch_id}/status")

    assert status_response.status_code == 403


def test_paper_options_expose_model_choices_and_round_bounds(monkeypatch, client: TestClient) -> None:
    from src.api.routers import papers

    monkeypatch.setattr(
        papers,
        "settings",
        Settings(
            _env_file=None,
            default_provider_names="z-ai/glm-5.1,qwen/qwen3.6-plus,openai/gpt-5.4",
            zenmux_api_key="test-key",
            max_concurrent_models=3,
        ),
        raising=False,
    )

    response = client.get("/api/papers/options")

    assert response.status_code == 200
    body = response.json()
    assert body["default_selected_models"] == [
        "z-ai/glm-5.1",
        "qwen/qwen3.6-plus",
        "openai/gpt-5.4",
    ]
    assert body["default_rounds"] == 1
    assert body["min_rounds"] == 1
    assert body["max_rounds"] == 5
    assert body["max_selected_models"] == 3
    assert {item["name"] for item in body["model_options"]} >= {
        "z-ai/glm-5.1",
        "qwen/qwen3.6-plus",
        "openai/gpt-5.4",
    }


def test_upload_persists_selected_models_and_rounds_for_status_and_report(
    client: TestClient, db_session: Session
) -> None:
    _login_submitter(client, db_session)
    _install_sync_pipeline(
        client,
        [
            FakeProvider("mock-a", 80),
            FakeProvider("mock-b", 82),
        ],
    )

    upload_response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "摘要\n正文内容\n参考文献\n[1] 文献".encode("utf-8"), "text/plain")},
        data={"provider_names": "mock-a,mock-b", "evaluation_rounds": "3"},
    )
    assert upload_response.status_code == 202

    payload = upload_response.json()
    pending_status_response = client.get(f"/api/papers/{payload['paper_id']}/status")
    assert pending_status_response.status_code == 200
    assert pending_status_response.json()["task_status"] == "pending"

    start_response = client.post(f"/api/papers/{payload['paper_id']}/start")
    assert start_response.status_code == 202

    status_response = client.get(f"/api/papers/{payload['paper_id']}/status")
    assert status_response.status_code == 200
    assert status_response.json()["evaluation_config"] == {
        "selected_models": ["mock-a", "mock-b"],
        "evaluation_rounds": 3,
    }

    report_response = client.get(f"/api/papers/{payload['paper_id']}/report")
    assert report_response.status_code == 200
    assert report_response.json()["evaluation_config"] == {
        "selected_models": ["mock-a", "mock-b"],
        "evaluation_rounds": 3,
    }


def test_upload_rejects_rounds_above_pilot_limit(
    client: TestClient, db_session: Session
) -> None:
    _login_submitter(client, db_session)

    response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "正文内容".encode("utf-8"), "text/plain")},
        data={"provider_names": "mock-a,mock-b", "evaluation_rounds": "6"},
    )

    assert response.status_code == 400


def test_submitter_starts_pending_paper_only_once(
    client: TestClient, db_session: Session
) -> None:
    _login_submitter(client, db_session)
    _install_sync_pipeline(
        client,
        [
            FakeProvider("mock-a", 80),
            FakeProvider("mock-b", 82),
        ],
    )

    upload_response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "摘要\n正文内容".encode("utf-8"), "text/plain")},
        data={"provider_names": "mock-a,mock-b"},
    )
    assert upload_response.status_code == 202

    payload = upload_response.json()
    start_response = client.post(f"/api/papers/{payload['paper_id']}/start")
    assert start_response.status_code == 202

    duplicate_start_response = client.post(f"/api/papers/{payload['paper_id']}/start")
    assert duplicate_start_response.status_code == 409


def test_paper_status_requires_expert_assignment_for_expert_access(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")
    create_user(db_session, email="editor@example.com", role="editor")
    assigned_expert = create_user(db_session, email="expert-assigned@example.com", role="expert")
    create_user(db_session, email="expert-unassigned@example.com", role="expert")
    client.app.state.email_sender = lambda **kwargs: None
    _install_sync_pipeline(
        client,
        [
            FakeProvider("mock-a", 45),
            FakeProvider("mock-b", 70),
            FakeProvider("mock-c", 95),
        ],
    )

    _login(client, "submitter@example.com")
    upload_response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "正文内容".encode("utf-8"), "text/plain")},
        data={"provider_names": "mock-a,mock-b,mock-c"},
    )
    assert upload_response.status_code == 202
    payload = upload_response.json()
    start_response = client.post(f"/api/papers/{payload['paper_id']}/start")
    assert start_response.status_code == 202

    client.cookies.clear()
    _login(client, "editor@example.com")
    assign_response = client.post(
        f"/api/reviews/{payload['task_id']}/assign",
        json={"expert_ids": [assigned_expert.id]},
    )
    assert assign_response.status_code == 201

    client.cookies.clear()
    _login(client, "expert-unassigned@example.com")
    unassigned_status_response = client.get(f"/api/papers/{payload['paper_id']}/status")
    assert unassigned_status_response.status_code == 403

    client.cookies.clear()
    _login(client, "expert-assigned@example.com")
    assigned_status_response = client.get(f"/api/papers/{payload['paper_id']}/status")
    assert assigned_status_response.status_code == 200


def test_multiple_rounds_aggregate_dimension_scores_but_keep_round_level_ai_logs(
    client: TestClient, db_session: Session
) -> None:
    _login_submitter(client, db_session)
    _install_sync_pipeline(
        client,
        [
            FakeProvider("mock-a", 80),
            FakeProvider("mock-b", 82),
        ],
    )

    upload_response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "摘要\n正文内容\n参考文献\n[1] 文献".encode("utf-8"), "text/plain")},
        data={"provider_names": "mock-a,mock-b", "evaluation_rounds": "3"},
    )
    assert upload_response.status_code == 202

    start_response = client.post(f"/api/papers/{upload_response.json()['paper_id']}/start")
    assert start_response.status_code == 202

    assert db_session.query(DimensionScore).count() == 12
    assert db_session.query(AICallLog).count() == 37


def test_submitter_can_delete_completed_paper_and_uploaded_artifacts(
    client: TestClient, db_session: Session
) -> None:
    _login_submitter(client, db_session)
    _install_sync_pipeline(
        client,
        [
            FakeProvider("mock-a", 80),
            FakeProvider("mock-b", 82),
            FakeProvider("mock-c", 84),
        ],
    )

    upload_response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "摘要\n正文内容\n参考文献\n[1] 文献".encode("utf-8"), "text/plain")},
        data={"provider_names": "mock-a,mock-b,mock-c"},
    )
    assert upload_response.status_code == 202

    payload = upload_response.json()
    start_response = client.post(f"/api/papers/{payload['paper_id']}/start")
    assert start_response.status_code == 202

    paper = db_session.get(Paper, payload["paper_id"])
    assert paper is not None
    assert paper.file_path is not None

    export_response = client.get(
        f"/api/papers/{payload['paper_id']}/report/export",
        params={"format": "json", "report_type": "public"},
    )
    assert export_response.status_code == 200
    assert db_session.query(ReportExport).count() == 1

    delete_response = client.delete(f"/api/papers/{payload['paper_id']}")
    assert delete_response.status_code == 204

    assert not Path(paper.file_path).exists()
    assert db_session.get(Paper, payload["paper_id"]) is None
    assert db_session.query(Report).count() == 0
    assert db_session.query(ReportExport).count() == 0


def test_parse_provider_names_uses_settings_default_when_absent(monkeypatch) -> None:
    from src.api.routers import papers

    monkeypatch.setattr(
        papers,
        "settings",
        Settings(
            _env_file=None,
            default_provider_names="z-ai/glm-5.1,qwen/qwen3.6-plus,openai/gpt-5.4",
        ),
        raising=False,
    )

    assert papers._parse_provider_names(None) == [
        "z-ai/glm-5.1",
        "qwen/qwen3.6-plus",
        "openai/gpt-5.4",
    ]
