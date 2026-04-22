from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.api.routers import admin as admin_module
from src.models.evaluation import EvaluationTask
from src.models.paper import Paper
from src.models.review import ExpertReview
from tests.test_api.conftest import create_user
from tests.test_api.test_papers_router import FakeProvider, _install_sync_pipeline


def _login(client: TestClient, email: str, password: str = "secret123") -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


def _safe_runner_with_providers(client: TestClient, providers: list[FakeProvider]) -> None:
    from src.evaluation.orchestrator import run_evaluation_pipeline

    async def runner(task_id: str, db: Session) -> None:
        try:
            await run_evaluation_pipeline(task_id, db, provider_factory=lambda _: providers)
        except Exception:
            pass

    client.app.state.pipeline_runner = runner


def test_internal_report_access_creates_audit_log(
    client: TestClient, db_session: Session
) -> None:
    from src.models.audit import AuditLog

    create_user(db_session, email="submitter@example.com", role="submitter")
    create_user(db_session, email="editor@example.com", role="editor")

    _login(client, "submitter@example.com")
    _install_sync_pipeline(client, [FakeProvider("mock-a", 80), FakeProvider("mock-b", 82), FakeProvider("mock-c", 84)])
    upload_response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "正文".encode("utf-8"), "text/plain")},
        data={"provider_names": "mock-a,mock-b,mock-c"},
    )
    assert upload_response.status_code == 202
    paper_id = upload_response.json()["paper_id"]
    start_response = client.post(f"/api/papers/{paper_id}/start")
    assert start_response.status_code == 202

    client.cookies.clear()
    _login(client, "editor@example.com")
    report_response = client.get(f"/api/papers/{paper_id}/internal-report")
    assert report_response.status_code == 200

    audit_logs = db_session.query(AuditLog).all()
    assert audit_logs[0].action == "internal_report_access"


def test_admin_can_retry_failed_task_and_close_task(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")
    create_user(db_session, email="admin@example.com", role="admin")

    class FailingProvider(FakeProvider):
        async def evaluate_dimension(self, prompt: str):
            raise RuntimeError("provider failure")

        async def generate_json_response(self, prompt: str) -> dict:
            return {"status": "pass", "issues": [], "recommendation": "continue"}

    _login(client, "submitter@example.com")
    _safe_runner_with_providers(client, [FailingProvider("mock-a", 0), FailingProvider("mock-b", 0), FailingProvider("mock-c", 0)])
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
    assert status_response.json()["task_status"] == "recovering"

    client.cookies.clear()
    _login(client, "admin@example.com")
    _install_sync_pipeline(client, [FakeProvider("mock-a", 75), FakeProvider("mock-b", 78), FakeProvider("mock-c", 81)])
    retry_response = client.post(f"/api/admin/tasks/{payload['task_id']}/retry")
    assert retry_response.status_code == 200
    assert retry_response.json()["task_status"] == "completed"

    close_response = client.post(f"/api/admin/tasks/{payload['task_id']}/close")
    assert close_response.status_code == 200
    assert close_response.json()["task_status"] == "closed"


def test_admin_can_list_recovery_tasks_with_paper_context(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")
    create_user(db_session, email="admin@example.com", role="admin")

    class FailingProvider(FakeProvider):
        async def evaluate_dimension(self, prompt: str):
            raise RuntimeError("provider failure")

        async def generate_json_response(self, prompt: str) -> dict:
            return {"status": "pass", "issues": [], "recommendation": "continue"}

    _login(client, "submitter@example.com")
    _safe_runner_with_providers(client, [FailingProvider("mock-a", 0), FailingProvider("mock-b", 0), FailingProvider("mock-c", 0)])
    upload_response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "正文".encode("utf-8"), "text/plain")},
        data={"provider_names": "mock-a,mock-b,mock-c"},
    )
    assert upload_response.status_code == 202
    payload = upload_response.json()
    start_response = client.post(f"/api/papers/{payload['paper_id']}/start")
    assert start_response.status_code == 202

    client.cookies.clear()
    _login(client, "admin@example.com")
    tasks_response = client.get("/api/admin/tasks")
    assert tasks_response.status_code == 200
    items = tasks_response.json()["items"]
    assert len(items) >= 1

    matching = [item for item in items if item["task_id"] == payload["task_id"]]
    assert len(matching) == 1
    listed_task = matching[0]
    assert listed_task["task_status"] == "recovering"
    assert listed_task["paper_id"] == payload["paper_id"]
    assert listed_task["paper_filename"] == "paper.txt"
    assert listed_task["failure_stage"] is not None
    assert listed_task["failure_detail"] is not None


def test_admin_can_list_audit_logs(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")
    create_user(db_session, email="admin@example.com", role="admin")

    class FailingProvider(FakeProvider):
        async def evaluate_dimension(self, prompt: str):
            raise RuntimeError("provider failure")

        async def generate_json_response(self, prompt: str) -> dict:
            return {"status": "pass", "issues": [], "recommendation": "continue"}

    _login(client, "submitter@example.com")
    _safe_runner_with_providers(client, [FailingProvider("mock-a", 0), FailingProvider("mock-b", 0), FailingProvider("mock-c", 0)])
    upload_response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "正文".encode("utf-8"), "text/plain")},
        data={"provider_names": "mock-a,mock-b,mock-c"},
    )
    assert upload_response.status_code == 202
    payload = upload_response.json()
    start_response = client.post(f"/api/papers/{payload['paper_id']}/start")
    assert start_response.status_code == 202

    client.cookies.clear()
    _login(client, "admin@example.com")
    _install_sync_pipeline(client, [FakeProvider("mock-a", 75), FakeProvider("mock-b", 78), FakeProvider("mock-c", 81)])
    retry_response = client.post(f"/api/admin/tasks/{payload['task_id']}/retry")
    assert retry_response.status_code == 200
    close_response = client.post(f"/api/admin/tasks/{payload['task_id']}/close")
    assert close_response.status_code == 200

    audit_response = client.get("/api/admin/audit-logs")
    assert audit_response.status_code == 200
    items = audit_response.json()["items"]
    assert len(items) >= 2
    actions = {item["action"] for item in items}
    assert "retry_task" in actions
    assert "close_task" in actions


def test_batch_status_aggregates_child_tasks(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")

    _login(client, "submitter@example.com")
    _install_sync_pipeline(client, [FakeProvider("mock-a", 80), FakeProvider("mock-b", 81), FakeProvider("mock-c", 82)])
    batch_response = client.post(
        "/api/papers/batch",
        files=[
            ("files", ("one.txt", "正文一".encode("utf-8"), "text/plain")),
            ("files", ("two.txt", "正文二".encode("utf-8"), "text/plain")),
        ],
        data={"provider_names": "mock-a,mock-b,mock-c"},
    )
    assert batch_response.status_code == 202
    batch_id = batch_response.json()["batch_id"]

    status_response = client.get(f"/api/papers/batch/{batch_id}/status")
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["total"] == 2
    assert body["completed"] == 0
    assert body["failed"] == 0


def test_admin_operations_overview_reports_counts_failures_reviews_and_dependencies(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    submitter = create_user(db_session, email="submitter@example.com", role="submitter")
    create_user(db_session, email="admin@example.com", role="admin")
    expert = create_user(db_session, email="expert@example.com", role="expert")

    paper_recovering = Paper(
        original_filename="recovering.txt",
        file_type="txt",
        status="recovering",
        uploaded_by=submitter.id,
    )
    paper_processing = Paper(
        original_filename="processing.txt",
        file_type="txt",
        status="processing",
        uploaded_by=submitter.id,
    )
    paper_completed = Paper(
        original_filename="completed.txt",
        file_type="txt",
        status="completed",
        uploaded_by=submitter.id,
    )
    db_session.add_all([paper_recovering, paper_processing, paper_completed])
    db_session.flush()

    task_recovering = EvaluationTask(
        paper_id=paper_recovering.id,
        framework_id="framework-a",
        status="recovering",
        failure_stage="aggregation",
        failure_detail="dimension vote failed",
    )
    task_processing = EvaluationTask(
        paper_id=paper_processing.id,
        framework_id="framework-a",
        status="processing",
    )
    task_completed = EvaluationTask(
        paper_id=paper_completed.id,
        framework_id="framework-a",
        status="completed",
    )
    db_session.add_all([task_recovering, task_processing, task_completed])
    db_session.flush()

    review_pending_one = ExpertReview(task_id=task_recovering.id, expert_id=expert.id, status="pending")
    review_pending_two = ExpertReview(task_id=task_processing.id, expert_id=expert.id, status="pending")
    db_session.add_all([review_pending_one, review_pending_two])
    db_session.commit()

    monkeypatch.setattr(
        admin_module,
        "build_dependency_status",
        lambda db: {
            "database": {"status": "ok", "detail": "ok"},
            "redis": {"status": "ok", "detail": "ok"},
            "storage": {"status": "ok", "detail": "ok (local)"},
            "task_queue": {"status": "ok", "detail": "workers=1; pending=0,processing=0,reviewing=0,recovering=0"},
        },
        raising=False,
    )

    client.cookies.clear()
    _login(client, "admin@example.com")
    response = client.get("/api/admin/operations/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_counts"]["total"] == 3
    assert payload["task_counts"]["recovering"] == 1
    assert payload["task_counts"]["processing"] == 1
    assert payload["task_counts"]["completed"] == 1
    assert payload["pending_reviews"] == 2
    assert len(payload["recent_failures"]) == 1
    assert payload["recent_failures"][0]["task_id"] == task_recovering.id
    assert payload["recent_failures"][0]["failure_stage"] == "aggregation"
    assert payload["dependencies"]["storage"]["status"] == "ok"


def test_admin_operations_overview_surfaces_task_queue_dependency_status(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    create_user(db_session, email="admin@example.com", role="admin")
    monkeypatch.setattr(admin_module, "check_database_health", lambda: (True, "ok"))
    monkeypatch.setattr(admin_module, "check_redis_health", lambda: (True, "ok"))
    monkeypatch.setattr(admin_module, "check_storage_health", lambda: (True, "ok (local probe)"))
    monkeypatch.setattr(
        admin_module,
        "check_task_queue_health",
        lambda db: (
            False,
            {
                "counts": {"pending": 0, "processing": 2, "reviewing": 0, "recovering": 0},
                "workers": [],
                "worker_detail": "no workers responded to celery ping",
            },
        ),
    )

    client.cookies.clear()
    _login(client, "admin@example.com")
    response = client.get("/api/admin/operations/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dependencies"]["task_queue"]["status"] == "error"
    assert "no workers responded to celery ping" in payload["dependencies"]["task_queue"]["detail"]
