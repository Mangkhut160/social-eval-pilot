from __future__ import annotations

import inspect

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.auth.dependencies import require_roles
from src.api.routers.health import (
    check_database_health,
    check_redis_health,
    check_storage_health,
    check_task_queue_health,
)
from src.api.schemas.admin import (
    AdminOperationsOverviewResponse,
    AdminRecentFailureResponse,
    AdminTaskActionResponse,
    AdminTaskListItemResponse,
    AdminTaskListResponse,
    AuditLogListItemResponse,
    AuditLogListResponse,
)
from src.core.audit import list_audit_logs, record_audit_log
from src.core.database import get_db
from src.core.state_machine import ensure_valid_task_transition
from src.core.time import utc_now
from src.models.audit import AuditLog
from src.models.evaluation import EvaluationTask
from src.models.paper import Paper
from src.models.review import ExpertReview
from src.models.user import User

router = APIRouter()


TASK_STATUSES = ["pending", "processing", "reviewing", "recovering", "completed", "closed"]


async def _dispatch_retry(request: Request, db: Session, task_id: str) -> None:
    pipeline_runner = getattr(request.app.state, "pipeline_runner", None)
    if pipeline_runner is not None:
        result = pipeline_runner(task_id, db)
        if inspect.isawaitable(result):
            await result
        return
    task_dispatcher = getattr(request.app.state, "task_dispatcher", None)
    if task_dispatcher is None:
        raise RuntimeError("No task dispatcher configured")
    task_dispatcher(task_id)


def _load_task_and_paper(db: Session, task_id: str) -> tuple[EvaluationTask, Paper]:
    task = db.get(EvaluationTask, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    paper = db.get(Paper, task.paper_id)
    if paper is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")
    return task, paper


@router.get("/tasks", response_model=AdminTaskListResponse)
def list_recovery_tasks(
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> AdminTaskListResponse:
    rows = (
        db.query(EvaluationTask, Paper)
        .join(Paper, Paper.id == EvaluationTask.paper_id)
        .filter(EvaluationTask.status == "recovering")
        .order_by(EvaluationTask.updated_at.desc())
        .all()
    )
    return AdminTaskListResponse(
        items=[
            AdminTaskListItemResponse(
                task_id=task.id,
                paper_id=paper.id,
                paper_title=paper.title,
                paper_filename=paper.original_filename,
                task_status=task.status,
                paper_status=paper.status,
                failure_stage=task.failure_stage,
                failure_detail=task.failure_detail,
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
            for task, paper in rows
        ]
    )


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_admin_audit_logs(
    action: str | None = Query(default=None),
    object_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    logs = list_audit_logs(db, action=action, object_type=object_type, limit=limit)
    actor_ids = {log.actor_id for log in logs if log.actor_id}
    users_by_id = {}
    if actor_ids:
        users = db.query(User).filter(User.id.in_(actor_ids)).all()
        users_by_id = {user.id: user for user in users}
    return AuditLogListResponse(
        items=[
            _audit_log_response(log, users_by_id.get(log.actor_id))
            for log in logs
        ]
    )


def _audit_log_response(log: AuditLog, actor: User | None) -> AuditLogListItemResponse:
    return AuditLogListItemResponse(
        id=log.id,
        actor_id=log.actor_id,
        actor_email=actor.email if actor is not None else None,
        object_type=log.object_type,
        object_id=log.object_id,
        action=log.action,
        result=log.result,
        details=log.details,
        created_at=log.created_at,
    )


def build_dependency_status(db: Session) -> dict[str, dict[str, str]]:
    database_ok, database_detail = check_database_health()
    redis_ok, redis_detail = check_redis_health()
    storage_ok, storage_detail = check_storage_health()
    queue_ok, queue_detail = check_task_queue_health(db)
    if isinstance(queue_detail, dict):
        counts = queue_detail.get("counts", {})
        count_summary = ",".join(
            f"{status}={counts.get(status, 0)}"
            for status in ("pending", "processing", "reviewing", "recovering")
        )
        workers = queue_detail.get("workers", [])
        worker_count = len(workers) if isinstance(workers, list) else 0
        worker_detail = queue_detail.get("worker_detail")
        queue_text = f"workers={worker_count}; {count_summary}"
        if worker_detail:
            queue_text = f"{queue_text}; {worker_detail}"
    else:
        queue_text = str(queue_detail)
    return {
        "database": {"status": "ok" if database_ok else "error", "detail": database_detail},
        "redis": {"status": "ok" if redis_ok else "error", "detail": redis_detail},
        "storage": {"status": "ok" if storage_ok else "error", "detail": storage_detail},
        "task_queue": {"status": "ok" if queue_ok else "error", "detail": queue_text},
    }


def _task_counts(db: Session) -> dict[str, int]:
    counts = {status: 0 for status in TASK_STATUSES}
    rows = db.query(EvaluationTask.status, func.count(EvaluationTask.id)).group_by(EvaluationTask.status).all()
    total = 0
    for status, count in rows:
        total += int(count)
        if status in counts:
            counts[status] = int(count)
    counts["total"] = total
    return counts


def _recent_failures(db: Session, *, limit: int = 10) -> list[AdminRecentFailureResponse]:
    rows = (
        db.query(EvaluationTask)
        .filter(EvaluationTask.failure_detail.isnot(None))
        .order_by(EvaluationTask.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [
        AdminRecentFailureResponse(
            task_id=task.id,
            paper_id=task.paper_id,
            failure_stage=task.failure_stage,
            failure_detail=task.failure_detail,
            updated_at=task.updated_at,
        )
        for task in rows
    ]


@router.get("/operations/overview", response_model=AdminOperationsOverviewResponse)
def operations_overview(
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> AdminOperationsOverviewResponse:
    pending_reviews = db.query(ExpertReview).filter(ExpertReview.status == "pending").count()
    return AdminOperationsOverviewResponse(
        generated_at=utc_now(),
        task_counts=_task_counts(db),
        recent_failures=_recent_failures(db),
        pending_reviews=pending_reviews,
        dependencies=build_dependency_status(db),
    )


@router.post("/tasks/{task_id}/retry", response_model=AdminTaskActionResponse)
async def retry_task(
    task_id: str,
    request: Request,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> AdminTaskActionResponse:
    task, paper = _load_task_and_paper(db, task_id)
    ensure_valid_task_transition(task.status, "processing")
    task.status = "processing"
    paper.status = "processing"
    task.failure_detail = None
    task.failure_stage = None
    db.add(task)
    db.add(paper)
    db.commit()
    await _dispatch_retry(request, db, task.id)
    db.refresh(task)
    db.refresh(paper)
    record_audit_log(
        db,
        actor_id=current_user.id,
        object_type="evaluation_task",
        object_id=task.id,
        action="retry_task",
        result=task.status,
        details={"paper_id": paper.id},
    )
    return AdminTaskActionResponse(task_id=task.id, task_status=task.status, paper_status=paper.status)


@router.post("/tasks/{task_id}/close", response_model=AdminTaskActionResponse)
def close_task(
    task_id: str,
    current_user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> AdminTaskActionResponse:
    task, paper = _load_task_and_paper(db, task_id)
    ensure_valid_task_transition(task.status, "closed")
    task.status = "closed"
    paper.status = "closed"
    db.add(task)
    db.add(paper)
    db.commit()
    record_audit_log(
        db,
        actor_id=current_user.id,
        object_type="evaluation_task",
        object_id=task.id,
        action="close_task",
        result="closed",
        details={"paper_id": paper.id},
    )
    return AdminTaskActionResponse(task_id=task.id, task_status=task.status, paper_status=paper.status)
