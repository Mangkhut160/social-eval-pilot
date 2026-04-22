from __future__ import annotations

from pathlib import Path

import pytest

from src.api import main as main_module
from src.api.routers import health as health_module
from src.core.object_storage import LocalStorageBackend
from src.models.evaluation import EvaluationTask
from src.models.paper import Paper


def test_create_app_initializes_logging(monkeypatch) -> None:
    calls: list[str] = []

    def fake_setup_logging(level: str = "INFO") -> None:
        calls.append(level)

    monkeypatch.setattr(main_module, "setup_logging", fake_setup_logging, raising=False)

    main_module.create_app()

    assert calls == ["INFO"]


def test_health_endpoint_reports_component_checks(client, monkeypatch) -> None:
    monkeypatch.setattr(health_module, "check_database_health", lambda: (True, "ok"))
    monkeypatch.setattr(health_module, "check_redis_health", lambda: (True, "ok"))
    monkeypatch.setattr(health_module, "check_storage_health", lambda: (True, "ok (local)"), raising=False)
    monkeypatch.setattr(
        health_module,
        "check_task_queue_health",
        lambda db: (True, {"pending": 1, "processing": 2, "reviewing": 0, "recovering": 1}),
        raising=False,
    )

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "socialeval",
        "checks": {
            "database": {"status": "ok", "detail": "ok"},
            "redis": {"status": "ok", "detail": "ok"},
            "storage": {"status": "ok", "detail": "ok (local)"},
            "task_queue": {
                "status": "ok",
                "detail": {"pending": 1, "processing": 2, "reviewing": 0, "recovering": 1},
            },
        },
    }


def test_health_endpoint_returns_503_when_dependency_fails(client, monkeypatch) -> None:
    monkeypatch.setattr(health_module, "check_database_health", lambda: (False, "database down"))
    monkeypatch.setattr(health_module, "check_redis_health", lambda: (True, "ok"))
    monkeypatch.setattr(health_module, "check_storage_health", lambda: (True, "ok (local)"), raising=False)
    monkeypatch.setattr(
        health_module,
        "check_task_queue_health",
        lambda db: (True, {"pending": 0, "processing": 0, "reviewing": 0, "recovering": 0}),
        raising=False,
    )

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["database"]["detail"] == "database down"


def test_health_endpoint_returns_503_when_task_queue_check_fails(client, monkeypatch) -> None:
    monkeypatch.setattr(health_module, "check_database_health", lambda: (True, "ok"))
    monkeypatch.setattr(health_module, "check_redis_health", lambda: (True, "ok"))
    monkeypatch.setattr(health_module, "check_storage_health", lambda: (True, "ok (local)"), raising=False)
    monkeypatch.setattr(
        health_module,
        "check_task_queue_health",
        lambda db: (False, "task query failed"),
        raising=False,
    )

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["task_queue"] == {"status": "error", "detail": "task query failed"}


def test_check_storage_health_local_backend_runs_write_delete_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = LocalStorageBackend(root=tmp_path)
    monkeypatch.setattr(health_module, "get_storage_backend", lambda: backend)

    ok, detail = health_module.check_storage_health()

    assert ok is True
    assert detail == "ok (local probe)"


def test_check_storage_health_s3_backend_runs_write_delete_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head_calls: list[str] = []
    put_calls: list[str] = []
    read_locations: list[str] = []
    deleted_locations: list[str] = []

    class FakeClient:
        def head_bucket(self, *, Bucket: str) -> None:  # noqa: N803
            head_calls.append(Bucket)

    class StoredObject:
        def __init__(self, location: str) -> None:
            self.location = location

    class FakeS3Backend:
        bucket = "socialeval-test-bucket"
        client = FakeClient()

        def put_bytes(self, *, key: str, content: bytes, content_type: str | None = None) -> StoredObject:
            put_calls.append(key)
            return StoredObject(f"s3://{self.bucket}/{key}")

        def get_bytes(self, location: str) -> bytes:
            read_locations.append(location)
            return b"ok"

        def delete(self, location: str) -> None:
            deleted_locations.append(location)

    monkeypatch.setattr(health_module, "get_storage_backend", lambda: FakeS3Backend())

    ok, detail = health_module.check_storage_health()

    assert ok is True
    assert detail == "ok (s3 probe)"
    assert head_calls == ["socialeval-test-bucket"]
    assert len(put_calls) == 1
    assert put_calls[0].startswith("healthchecks/")
    assert read_locations == [f"s3://socialeval-test-bucket/{put_calls[0]}"]
    assert deleted_locations == [f"s3://socialeval-test-bucket/{put_calls[0]}"]


def test_check_task_queue_health_includes_counts_and_worker_liveness(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    paper = Paper(original_filename="p.txt", file_type="txt", status="processing", uploaded_by=None)
    db_session.add(paper)
    db_session.flush()
    db_session.add_all(
        [
            EvaluationTask(paper_id=paper.id, framework_id="f", status="pending"),
            EvaluationTask(paper_id=paper.id, framework_id="f", status="processing"),
            EvaluationTask(paper_id=paper.id, framework_id="f", status="recovering"),
        ]
    )
    db_session.commit()

    class FakeInspect:
        def ping(self):
            return {"worker@host": {"ok": "pong"}}

    class FakeControl:
        def inspect(self, timeout: float = 1.0) -> FakeInspect:
            return FakeInspect()

    class FakeCelery:
        control = FakeControl()

    monkeypatch.setattr(health_module, "celery_app", FakeCelery())

    ok, detail = health_module.check_task_queue_health(db_session)

    assert ok is True
    assert detail["counts"] == {"pending": 1, "processing": 1, "reviewing": 0, "recovering": 1}
    assert detail["workers"] == ["worker@host"]


def test_check_task_queue_health_fails_when_no_workers_respond(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeInspect:
        def ping(self):
            return None

    class FakeControl:
        def inspect(self, timeout: float = 1.0) -> FakeInspect:
            return FakeInspect()

    class FakeCelery:
        control = FakeControl()

    monkeypatch.setattr(health_module, "celery_app", FakeCelery())

    ok, detail = health_module.check_task_queue_health(db_session)

    assert ok is False
    assert detail["counts"] == {"pending": 0, "processing": 0, "reviewing": 0, "recovering": 0}
    assert detail["worker_detail"] == "no workers responded to celery ping"
