from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.evaluation import EvaluationTask
from src.models.paper import Paper
from src.models.report import Report
from src.reporting.builder import build_internal_report
from src.reporting.public_filter import build_public_report


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
        .filter(Report.task_id == task_id, Report.report_type == report_type, Report.is_current.is_(True))
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

    report = Report(
        task_id=task_id,
        paper_id=paper_id,
        version=latest_version + 1,
        report_type=report_type,
        is_current=True,
        weighted_total=weighted_total,
        report_data=report_data,
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
        .filter(Report.task_id == task_id, Report.report_type == report_type, Report.is_current.is_(True))
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
