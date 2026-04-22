from __future__ import annotations

from pydantic import BaseModel


class EvaluationConfigResponse(BaseModel):
    selected_models: list[str]
    evaluation_rounds: int


class ModelOptionResponse(BaseModel):
    name: str
    label: str
    source: str


class PaperOptionsResponse(BaseModel):
    model_options: list[ModelOptionResponse]
    default_selected_models: list[str]
    max_selected_models: int
    default_rounds: int
    min_rounds: int
    max_rounds: int


class PaperTaskResponse(BaseModel):
    batch_id: str | None = None
    paper_id: str
    task_id: str
    paper_status: str
    task_status: str


class PaperStatusResponse(BaseModel):
    paper_id: str
    task_id: str
    paper_status: str
    task_status: str
    precheck_status: str | None
    failure_stage: str | None
    failure_detail: str | None
    reliability_summary: dict | None
    evaluation_config: EvaluationConfigResponse | None = None


class BatchPaperTaskResponse(BaseModel):
    batch_id: str
    total: int
    items: list[PaperTaskResponse]


class PaperListItemResponse(BaseModel):
    paper_id: str
    title: str | None
    original_filename: str
    paper_status: str
    precheck_status: str | None


class PaperListResponse(BaseModel):
    items: list[PaperListItemResponse]
