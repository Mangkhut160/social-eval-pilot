from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.database import engine
from src.core.object_storage import get_storage_backend
from src.core.redis_client import get_redis_client
from src.models.evaluation import EvaluationTask
from src.tasks.celery_app import celery_app


router = APIRouter()


def check_database_health() -> tuple[bool, str]:
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        return True, "ok"
    except Exception as exc:  # pragma: no cover - exercised through route tests
        return False, str(exc)


def check_redis_health() -> tuple[bool, str]:
    try:
        client = get_redis_client()
        try:
            client.ping()
        finally:
            client.close()
        return True, "ok"
    except Exception as exc:  # pragma: no cover - exercised through route tests
        return False, str(exc)


def check_storage_health() -> tuple[bool, str]:
    try:
        backend = get_storage_backend()
        if hasattr(backend, "client") and hasattr(backend, "bucket"):
            backend.client.head_bucket(Bucket=backend.bucket)
            probe_key = f"healthchecks/{uuid4().hex}.txt"
            stored = backend.put_bytes(
                key=probe_key,
                content=b"ok",
                content_type="text/plain",
            )
            payload = backend.get_bytes(stored.location)
            if payload != b"ok":
                raise RuntimeError("s3 probe readback mismatch")
            backend.delete(stored.location)
            return True, "ok (s3 probe)"

        probe_key = f"healthchecks/{uuid4().hex}.txt"
        stored = backend.put_bytes(
            key=probe_key,
            content=b"ok",
            content_type="text/plain",
        )
        backend.delete(stored.location)
        return True, "ok (local probe)"
    except Exception as exc:  # pragma: no cover - exercised through route tests
        return False, str(exc)


def check_task_queue_health(db: Session) -> tuple[bool, dict | str]:
    try:
        statuses = ["pending", "processing", "reviewing", "recovering"]
        counts = {
            status: db.query(EvaluationTask).filter(EvaluationTask.status == status).count()
            for status in statuses
        }
        inspector = celery_app.control.inspect(timeout=1.0)
        ping = inspector.ping() if inspector is not None else None
        if not ping:
            return False, {
                "counts": counts,
                "workers": [],
                "worker_detail": "no workers responded to celery ping",
            }
        return True, {
            "counts": counts,
            "workers": sorted(ping.keys()),
        }
    except Exception as exc:  # pragma: no cover - exercised through route tests
        return False, str(exc)


@router.get("/health")
def healthcheck(db: Session = Depends(get_db)):
    database_ok, database_detail = check_database_health()
    redis_ok, redis_detail = check_redis_health()
    storage_ok, storage_detail = check_storage_health()
    queue_ok, queue_detail = check_task_queue_health(db)
    overall_ok = database_ok and redis_ok and storage_ok and queue_ok

    return JSONResponse(
        status_code=200 if overall_ok else 503,
        content={
            "status": "ok" if overall_ok else "degraded",
            "service": "socialeval",
            "checks": {
                "database": {"status": "ok" if database_ok else "error", "detail": database_detail},
                "redis": {"status": "ok" if redis_ok else "error", "detail": redis_detail},
                "storage": {"status": "ok" if storage_ok else "error", "detail": storage_detail},
                "task_queue": {"status": "ok" if queue_ok else "error", "detail": queue_detail},
            },
        },
    )
