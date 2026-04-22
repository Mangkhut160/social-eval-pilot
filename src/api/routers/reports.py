from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.auth.dependencies import get_current_user
from src.api.schemas.reports import ReportHistoryItemResponse, ReportHistoryResponse
from src.core.audit import record_audit_log
from src.core.config import settings
from src.core.database import get_db
from src.evaluation.task_config import parse_task_config
from src.models.evaluation import EvaluationTask
from src.models.paper import Paper
from src.models.report import Report
from src.models.review import ExpertReview
from src.models.user import User
from src.reporting.charts import generate_radar_chart_base64
from src.reporting.exporters import export_report_json, export_report_pdf, persist_report_export
from src.reporting.public_filter import build_public_report
from src.reporting.versioning import get_report_by_version, list_report_history

router = APIRouter()
REPORT_READY_STATUSES = {"completed", "reviewing"}


def _normalize_text_items(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_normalize_text_items(item))
        return items
    text = str(value).strip()
    return [text] if text else []


def _normalized_dimensions(report_data: dict) -> list[dict] | None:
    dimensions = report_data.get("dimensions")
    if not isinstance(dimensions, list):
        return None

    normalized_dimensions: list[dict] = []
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            normalized_dimensions.append(dimension)
            continue

        normalized_dimension = dict(dimension)
        ai_payload = normalized_dimension.get("ai")
        if isinstance(ai_payload, dict):
            normalized_ai = dict(ai_payload)
            if "evidence_quotes" in normalized_ai:
                normalized_ai["evidence_quotes"] = _normalize_text_items(
                    normalized_ai.get("evidence_quotes")
                )
            if "analysis" in normalized_ai:
                normalized_ai["analysis"] = _normalize_text_items(normalized_ai.get("analysis"))
            normalized_dimension["ai"] = normalized_ai

        normalized_dimensions.append(normalized_dimension)

    return normalized_dimensions


def _normalized_radar_chart(report_data: dict) -> dict | None:
    radar_chart = report_data.get("radar_chart")
    if not isinstance(radar_chart, dict):
        return None

    dimensions = report_data.get("dimensions", [])
    dimension_label_map: dict[str, str] = {}
    fallback_labels: list[str] = []
    if isinstance(dimensions, list):
        for dimension in dimensions:
            if not isinstance(dimension, dict):
                continue
            zh_label = str(dimension.get("name_zh", "")).strip()
            if not zh_label:
                continue
            fallback_labels.append(zh_label)
            dimension_label_map[zh_label] = zh_label
            en_label = str(dimension.get("name_en", "")).strip()
            if en_label:
                dimension_label_map[en_label] = zh_label

    raw_labels = radar_chart.get("labels", [])
    normalized_labels: list[str] = []
    if isinstance(raw_labels, list):
        normalized_labels = [
            dimension_label_map.get(str(label), str(label))
            for label in raw_labels
            if str(label).strip()
        ]
    if not normalized_labels:
        normalized_labels = fallback_labels

    raw_values = radar_chart.get("values", [])
    normalized_values: list[float] = []
    if isinstance(raw_values, list):
        normalized_values = [float(value) for value in raw_values]

    image_base64 = radar_chart.get("image_base64")
    if normalized_labels and normalized_values and (
        radar_chart.get("labels") != normalized_labels or not image_base64
    ):
        image_base64 = generate_radar_chart_base64(normalized_labels, normalized_values)

    return {
        "labels": normalized_labels,
        "values": normalized_values,
        "image_base64": image_base64,
    }


def _build_expected_public_report_data(db: Session, task_id: str, version: int) -> dict | None:
    internal_report = (
        db.query(Report)
        .filter(
            Report.task_id == task_id,
            Report.report_type == "internal",
            Report.version == version,
        )
        .first()
    )
    if internal_report is None:
        return None

    internal_data = dict(internal_report.report_data)
    normalized_dimensions = _normalized_dimensions(internal_data)
    if normalized_dimensions is not None:
        internal_data["dimensions"] = normalized_dimensions

    if internal_data.get("precheck_status") != "reject":
        normalized_radar = _normalized_radar_chart(internal_data)
        if normalized_radar is not None:
            internal_data["radar_chart"] = normalized_radar

    return build_public_report(internal_data)


def _load_paper_and_task(db: Session, paper_id: str) -> tuple[Paper, EvaluationTask]:
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
    return paper, task


def _expert_has_assignment(db: Session, task_id: str, expert_id: str) -> bool:
    return (
        db.query(ExpertReview.id)
        .filter(ExpertReview.task_id == task_id, ExpertReview.expert_id == expert_id)
        .first()
        is not None
    )


def _ensure_public_access(
    db: Session,
    current_user: User,
    paper: Paper,
    task: EvaluationTask,
) -> None:
    if current_user.role in {"admin", "editor"}:
        return
    if current_user.role == "submitter" and paper.uploaded_by == current_user.id:
        return
    if current_user.role == "expert" and _expert_has_assignment(db, task.id, current_user.id):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _ensure_internal_access(db: Session, current_user: User, task: EvaluationTask) -> None:
    if current_user.role in {"admin", "editor"}:
        return
    if current_user.role == "expert" and _expert_has_assignment(db, task.id, current_user.id):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _ensure_report_available(
    db: Session,
    task: EvaluationTask,
    *,
    report_type: str,
    version: int | None = None,
) -> None:
    if task.status in REPORT_READY_STATUSES:
        return

    query = db.query(Report.id).filter(Report.task_id == task.id, Report.report_type == report_type)
    if version is None:
        query = query.filter(Report.is_current.is_(True))
    else:
        query = query.filter(Report.version == version)
    if query.first() is not None:
        return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Report is unavailable until evaluation finishes",
    )


def _hydrate_report_snapshot(
    db: Session,
    task: EvaluationTask,
    report: Report,
    paper: Paper | None = None,
) -> dict:
    report_data = dict(report.report_data)
    is_dirty = False

    normalized_dimensions = _normalized_dimensions(report_data)
    if normalized_dimensions is not None and report_data.get("dimensions") != normalized_dimensions:
        report_data["dimensions"] = normalized_dimensions
        is_dirty = True

    if "evaluation_config" in report_data:
        pass
    else:
        report_data["evaluation_config"] = parse_task_config(
            task.provider_names,
            settings.default_provider_name_list,
        ).as_dict()
        is_dirty = True

    paper_record = paper or db.get(Paper, report.paper_id)
    if paper_record is not None and paper_record.precheck_status is not None:
        if report_data.get("precheck_status") != paper_record.precheck_status:
            report_data["precheck_status"] = paper_record.precheck_status
            is_dirty = True
        if report_data.get("precheck_result") != paper_record.precheck_result:
            report_data["precheck_result"] = paper_record.precheck_result
            is_dirty = True

        if paper_record.precheck_status == "reject":
            if report_data.get("weighted_total") != 0.0:
                report_data["weighted_total"] = 0.0
                is_dirty = True
            if report_data.get("dimensions") != []:
                report_data["dimensions"] = []
                is_dirty = True
            reject_radar = {
                "labels": [],
                "values": [],
                "image_base64": None,
            }
            if report_data.get("radar_chart") != reject_radar:
                report_data["radar_chart"] = reject_radar
                is_dirty = True
            if report.weighted_total != 0.0:
                report.weighted_total = 0.0
                is_dirty = True
        else:
            normalized_radar = _normalized_radar_chart(report_data)
            if normalized_radar is not None and report_data.get("radar_chart") != normalized_radar:
                report_data["radar_chart"] = normalized_radar
                is_dirty = True
    else:
        normalized_radar = _normalized_radar_chart(report_data)
        if normalized_radar is not None and report_data.get("radar_chart") != normalized_radar:
            report_data["radar_chart"] = normalized_radar
            is_dirty = True

    if report.report_type == "public":
        expected_public = _build_expected_public_report_data(db, task.id, report.version)
        if expected_public is not None and report_data != expected_public:
            report_data = expected_public
            is_dirty = True
        if report.weighted_total != float(report_data.get("weighted_total", report.weighted_total)):
            report.weighted_total = float(report_data.get("weighted_total", report.weighted_total))
            is_dirty = True

    if is_dirty:
        report.report_data = report_data
        db.add(report)
        db.commit()
        db.refresh(report)
    return dict(report.report_data)


@router.get("/{paper_id}/report")
def get_public_report(
    paper_id: str,
    version: int | None = Query(default=None, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    paper, task = _load_paper_and_task(db, paper_id)
    _ensure_public_access(db, current_user, paper, task)
    _ensure_report_available(db, task, report_type="public", version=version)
    try:
        report = get_report_by_version(db, task.id, "public", version)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _hydrate_report_snapshot(db, task, report, paper)


@router.get("/{paper_id}/internal-report")
def get_internal_report(
    paper_id: str,
    version: int | None = Query(default=None, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _, task = _load_paper_and_task(db, paper_id)
    _ensure_internal_access(db, current_user, task)
    _ensure_report_available(db, task, report_type="internal", version=version)
    try:
        report = get_report_by_version(db, task.id, "internal", version)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    report_data = _hydrate_report_snapshot(db, task, report)
    record_audit_log(
        db,
        actor_id=current_user.id,
        object_type="report",
        object_id=report.id,
        action="internal_report_access",
        result="success",
        details={"paper_id": paper_id, "report_type": "internal"},
    )
    return report_data


@router.get("/{paper_id}/report/history", response_model=ReportHistoryResponse)
def get_report_history(
    paper_id: str,
    report_type: str = Query("public", pattern="^(public|internal)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportHistoryResponse:
    paper, task = _load_paper_and_task(db, paper_id)
    if report_type == "internal":
        _ensure_internal_access(db, current_user, task)
    else:
        _ensure_public_access(db, current_user, paper, task)

    reports = list_report_history(db, task.id, report_type)
    items: list[ReportHistoryItemResponse] = []
    for report in reports:
        hydrated = _hydrate_report_snapshot(db, task, report, paper)
        items.append(
            ReportHistoryItemResponse(
                report_id=report.id,
                report_type=report.report_type,
                version=report.version,
                is_current=report.is_current,
                weighted_total=report.weighted_total,
                precheck_status=hydrated.get("precheck_status"),
                created_at=report.created_at.isoformat(),
                available_export_formats=["json", "pdf"],
            )
        )
    return ReportHistoryResponse(
        items=items
    )


@router.get("/{paper_id}/report/export")
def export_report(
    paper_id: str,
    format: str = Query(..., pattern="^(json|pdf)$"),
    report_type: str = Query("public", pattern="^(public|internal)$"),
    version: int | None = Query(default=None, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    paper, task = _load_paper_and_task(db, paper_id)
    if report_type == "internal":
        _ensure_internal_access(db, current_user, task)
    else:
        _ensure_public_access(db, current_user, paper, task)
    _ensure_report_available(db, task, report_type=report_type, version=version)

    try:
        report = get_report_by_version(db, task.id, report_type, version)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    _hydrate_report_snapshot(db, task, report)
    if format == "json":
        content = export_report_json(report)
        persist_report_export(db, report=report, export_type="json", content=content)
        return JSONResponse(content=report.report_data)

    content = export_report_pdf(report)
    persist_report_export(db, report=report, export_type="pdf", content=content)
    return Response(content=content, media_type="application/pdf")
