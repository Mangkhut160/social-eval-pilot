from datetime import datetime

from pydantic import BaseModel


class AdminTaskActionResponse(BaseModel):
    task_id: str
    task_status: str
    paper_status: str


class BatchStatusResponse(BaseModel):
    batch_id: str
    total: int
    completed: int
    failed: int


class AdminTaskListItemResponse(BaseModel):
    task_id: str
    paper_id: str
    paper_title: str | None = None
    paper_filename: str
    task_status: str
    paper_status: str
    failure_stage: str | None = None
    failure_detail: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminTaskListResponse(BaseModel):
    items: list[AdminTaskListItemResponse]


class AuditLogListItemResponse(BaseModel):
    id: str
    actor_id: str | None = None
    actor_email: str | None = None
    object_type: str
    object_id: str
    action: str
    result: str
    details: dict | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogListItemResponse]


class AdminRecentFailureResponse(BaseModel):
    task_id: str
    paper_id: str
    failure_stage: str | None = None
    failure_detail: str | None = None
    updated_at: datetime


class AdminOperationsOverviewResponse(BaseModel):
    generated_at: datetime
    task_counts: dict[str, int]
    recent_failures: list[AdminRecentFailureResponse]
    pending_reviews: int
    dependencies: dict[str, dict[str, str]]
