from __future__ import annotations

import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.core.object_storage import get_storage_backend
from src.models.evaluation import EvaluationTask
from src.models.paper import Paper
from src.models.report import Report
from src.reporting.builder import build_internal_report
from src.reporting.public_filter import build_public_report


def _save_radar_chart_png(report_data: dict, report_id: str) -> dict:
    radar_chart = report_data.get("radar_chart")
    if not isinstance(radar_chart, dict):
        return report_data
    png_bytes = radar_chart.pop("image_png_bytes", None)
    if isinstance(png_bytes, bytes) and png_bytes:
        storage = get_storage_backend()
        key = f"charts/{report_id}-radar-chart.png"
        stored = storage.put_bytes(key=key, content=png_bytes, content_type="image/png")
        radar_chart["image_path"] = stored.location
    report_data["radar_chart"] = radar_chart
    return report_data


def _create_report_snapshot(
    db: Session,
    *,
    task_id: str,
    paper_id: str,
    report_type: str,
    report_data: dict,
    weighted_total: float,
) -> Report:
    current_reports = (
        db.query(Report)
        .filter(
            Report.task_id == task_id,
            Report.report_type == report_type,
            Report.is_current.is_(True),
        )
        .all()
    )
    for current in current_reports:
        current.is_current = False
        db.add(current)

    latest_version = (
        db.query(func.max(Report.version))
        .filter(Report.task_id == task_id, Report.report_type == report_type)
        .scalar()
    ) or 0
    report_id = str(uuid.uuid4())
    sanitized_report_data = _save_radar_chart_png(report_data, report_id)

    report = Report(
        id=report_id,
        task_id=task_id,
        paper_id=paper_id,
        version=latest_version + 1,
        report_type=report_type,
        is_current=True,
        weighted_total=weighted_total,
        report_data=sanitized_report_data,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def generate_reports_for_task(db: Session, task_id: str) -> dict[str, Report]:
    task = db.get(EvaluationTask, task_id)
    if task is None:
        raise ValueError(f"Task {task_id} not found")
    paper = db.get(Paper, task.paper_id)
    if paper is None:
        raise ValueError(f"Paper for task {task_id} not found")

    internal_report = build_internal_report(db, task, paper)
    public_report = build_public_report(internal_report)

    internal_snapshot = _create_report_snapshot(
        db,
        task_id=task.id,
        paper_id=paper.id,
        report_type="internal",
        report_data=internal_report,
        weighted_total=internal_report["weighted_total"],
    )

    public_snapshot = _create_report_snapshot(
        db,
        task_id=task.id,
        paper_id=paper.id,
        report_type="public",
        report_data=public_report,
        weighted_total=public_report["weighted_total"],
    )

    return {"internal": internal_snapshot, "public": public_snapshot}


def list_report_history(db: Session, task_id: str, report_type: str) -> list[Report]:
    return (
        db.query(Report)
        .filter(Report.task_id == task_id, Report.report_type == report_type)
        .order_by(Report.version.desc(), Report.created_at.desc())
        .all()
    )


def get_current_report(db: Session, task_id: str, report_type: str) -> Report:
    report = (
        db.query(Report)
        .filter(
            Report.task_id == task_id,
            Report.report_type == report_type,
            Report.is_current.is_(True),
        )
        .first()
    )
    if report is not None:
        return report

    task = db.get(EvaluationTask, task_id)
    if task is None:
        raise ValueError(f"Task {task_id} not found")
    if task.status not in {"completed", "reviewing"}:
        raise ValueError(f"Report unavailable while task status is {task.status}")
    return generate_reports_for_task(db, task_id)[report_type]


def get_report_by_version(
    db: Session, task_id: str, report_type: str, version: int | None = None
) -> Report:
    if version is None:
        return get_current_report(db, task_id, report_type)

    report = (
        db.query(Report)
        .filter(
            Report.task_id == task_id,
            Report.report_type == report_type,
            Report.version == version,
        )
        .first()
    )
    if report is not None:
        return report
    raise ValueError(f"Report version {version} not found for task {task_id}")
