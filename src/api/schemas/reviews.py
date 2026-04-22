from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewQueueItem(BaseModel):
    task_id: str
    paper_id: str
    paper_title: str | None
    paper_status: str | None
    task_status: str
    low_confidence_dimensions: list[str]
    review_reasons: list[str] = Field(default_factory=list)
    needs_assignment: bool
    assigned_reviews: list["AssignedReviewSummary"]


class AssignedReviewSummary(BaseModel):
    review_id: str
    expert_id: str
    expert_email: str
    expert_display_name: str | None
    status: str
    completed_at: str | None


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]


class AssignExpertsRequest(BaseModel):
    expert_ids: list[str] = Field(min_length=1)


class AssignExpertsResponse(BaseModel):
    assigned_count: int
    review_ids: list[str]


class MyReviewItem(BaseModel):
    review_id: str
    task_id: str
    paper_id: str
    paper_title: str | None
    status: str


class MyReviewsResponse(BaseModel):
    items: list[MyReviewItem]


class ReviewCommentInput(BaseModel):
    dimension_key: str
    ai_score: float
    expert_score: float
    reason: str


class SubmitReviewRequest(BaseModel):
    comments: list[ReviewCommentInput]


class SubmitReviewResponse(BaseModel):
    review_id: str
    status: str
