from __future__ import annotations

import inspect
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from src.api.schemas.admin import BatchStatusResponse
from src.api.auth.dependencies import get_current_user
from src.api.schemas.papers import (
    BatchPaperTaskResponse,
    ModelOptionResponse,
    PaperListItemResponse,
    PaperListResponse,
    PaperOptionsResponse,
    PaperStatusResponse,
    PaperTaskResponse,
)
from src.core.database import get_db
from src.core.storage import save_upload_file, validate_upload_filename
from src.knowledge.loader import load_framework
from src.models.batch import BatchTask
from src.models.evaluation import EvaluationTask
from src.models.paper import Paper
from src.models.reliability import ReliabilityResult
from src.reliability.threshold_checker import summarize_reliability
from src.models.user import User

router = APIRouter()

DEFAULT_FRAMEWORK_PATH = "configs/frameworks/law-v2.5-20260422.yaml"


def _parse_provider_names(provider_names: str | None) -> list[str]:
    if not provider_names:
        return ["openai", "anthropic", "deepseek"]
    return [name.strip() for name in provider_names.split(",") if name.strip()]


def _create_task_record(
    db: Session,
    *,
    paper: Paper,
    framework_path: str,
    provider_names: list[str],
    batch_id: str | None = None,
) -> EvaluationTask:
    framework = load_framework(framework_path)
    task = EvaluationTask(
        paper_id=paper.id,
        batch_id=batch_id,
        framework_id=framework.version,
        framework_path=framework_path,
        provider_names=json.dumps(provider_names, ensure_ascii=False),
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


async def _dispatch_pipeline(
    request: Request,
    db: Session,
    task_id: str,
) -> None:
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


async def _create_paper_and_task(
    request: Request,
    db: Session,
    file: UploadFile,
    current_user: User,
    *,
    framework_path: str,
    provider_names: list[str],
    batch_id: str | None = None,
) -> PaperTaskResponse:
    try:
        ext = validate_upload_filename(file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    paper = Paper(
        original_filename=file.filename or "upload",
        file_type=ext,
        status="pending",
        uploaded_by=current_user.id,
        title=Path(file.filename or "upload").stem,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    file_path = await save_upload_file(file, paper.id)
    paper.file_path = str(file_path)
    db.add(paper)
    db.commit()
    db.refresh(paper)

    task = _create_task_record(
        db,
        paper=paper,
        framework_path=framework_path,
        provider_names=provider_names,
        batch_id=batch_id,
    )
    await _dispatch_pipeline(request, db, task.id)
    db.refresh(paper)
    db.refresh(task)
    return PaperTaskResponse(
        batch_id=batch_id,
        paper_id=paper.id,
        task_id=task.id,
        paper_status=paper.status,
        task_status=task.status,
    )


@router.post("", response_model=PaperTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_paper(
    request: Request,
    file: UploadFile = File(...),
    framework_path: str = Form(DEFAULT_FRAMEWORK_PATH),
    provider_names: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaperTaskResponse:
    return await _create_paper_and_task(
        request,
        db,
        file,
        current_user,
        framework_path=framework_path,
        provider_names=_parse_provider_names(provider_names),
    )


@router.get("/options", response_model=PaperOptionsResponse)
def get_paper_options(
    _: User = Depends(get_current_user),
) -> PaperOptionsResponse:
    return PaperOptionsResponse(
        model_options=[
            ModelOptionResponse(name="z-ai/glm-5.1", label="GLM 5.1", source="zenmux"),
            ModelOptionResponse(name="moonshotai/kimi-k2.6", label="Kimi K2.6", source="zenmux"),
            ModelOptionResponse(name="openai/gpt-5.4", label="GPT 5.4", source="zenmux"),
            ModelOptionResponse(name="google/gemini-3.1-pro-preview", label="Gemini 3.1 Pro", source="zenmux"),
        ],
        default_selected_models=["z-ai/glm-5.1", "moonshotai/kimi-k2.6", "openai/gpt-5.4", "google/gemini-3.1-pro-preview"],
        max_selected_models=4,
        default_rounds=1,
        min_rounds=1,
        max_rounds=3,
    )


@router.get("", response_model=PaperListResponse)
def list_papers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaperListResponse:
    query = db.query(Paper)
    if current_user.role == "submitter":
        query = query.filter(Paper.uploaded_by == current_user.id)
    papers = query.order_by(Paper.created_at.desc()).all()
    return PaperListResponse(
        items=[
            PaperListItemResponse(
                paper_id=paper.id,
                title=paper.title,
                original_filename=paper.original_filename,
                paper_status=paper.status,
                precheck_status=paper.precheck_status,
            )
            for paper in papers
        ]
    )


@router.post("/batch", response_model=BatchPaperTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def batch_upload_papers(
    request: Request,
    files: list[UploadFile] = File(...),
    framework_path: str = Form(DEFAULT_FRAMEWORK_PATH),
    provider_names: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchPaperTaskResponse:
    batch = BatchTask(total=len(files))
    db.add(batch)
    db.commit()
    db.refresh(batch)
    items = []
    parsed_provider_names = _parse_provider_names(provider_names)
    for file in files:
        items.append(
            await _create_paper_and_task(
                request,
                db,
                file,
                current_user,
                framework_path=framework_path,
                provider_names=parsed_provider_names,
                batch_id=batch.id,
            )
        )
    return BatchPaperTaskResponse(batch_id=batch.id, total=len(items), items=items)


@router.get("/{paper_id}/status", response_model=PaperStatusResponse)
def get_paper_status(
    paper_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaperStatusResponse:
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")

    task = (
        db.query(EvaluationTask)
        .filter(EvaluationTask.paper_id == paper.id)
        .order_by(EvaluationTask.created_at.desc())
        .first()
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    reliability_rows = db.query(ReliabilityResult).filter(ReliabilityResult.task_id == task.id).all()
    reliability_summary = None
    if reliability_rows:
        reliability_summary = summarize_reliability(
            [
                type(
                    "ReliabilityRowAdapter",
                    (),
                    {
                        "dimension_key": row.dimension_key,
                        "is_high_confidence": row.is_high_confidence,
                    },
                )()
                for row in reliability_rows
            ]
        )

    return PaperStatusResponse(
        paper_id=paper.id,
        task_id=task.id,
        paper_status=paper.status,
        task_status=task.status,
        precheck_status=paper.precheck_status,
        failure_stage=task.failure_stage,
        failure_detail=task.failure_detail,
        reliability_summary=reliability_summary,
    )


@router.get("/batch/{batch_id}/status", response_model=BatchStatusResponse)
def get_batch_status(
    batch_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchStatusResponse:
    batch = db.get(BatchTask, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    tasks = db.query(EvaluationTask).filter(EvaluationTask.batch_id == batch.id).all()
    completed = sum(1 for task in tasks if task.status == "completed")
    failed = sum(1 for task in tasks if task.status == "recovering")
    return BatchStatusResponse(
        batch_id=batch.id,
        total=batch.total,
        completed=completed,
        failed=failed,
    )
