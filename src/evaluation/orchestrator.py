from __future__ import annotations

import json

from sqlalchemy.orm import Session

from src.core.state_machine import ensure_valid_task_transition
from src.evaluation.concurrent_evaluator import evaluate_dimension_concurrent
from src.evaluation.precheck import run_precheck
from src.evaluation.providers.factory import create_providers
from src.ingestion.preprocessor import process_file
from src.knowledge.loader import load_framework
from src.models.evaluation import DimensionScore, EvaluationTask
from src.models.paper import Paper
from src.models.reliability import ReliabilityResult
from src.reporting.versioning import generate_reports_for_task
from src.reliability.calculator import calculate_reliability
from src.reliability.threshold_checker import summarize_reliability


async def run_evaluation_pipeline(
    task_id: str,
    db: Session,
    *,
    provider_factory=create_providers,
) -> dict:
    task = db.get(EvaluationTask, task_id)
    if task is None:
        raise ValueError(f"EvaluationTask {task_id} not found")

    paper = db.get(Paper, task.paper_id)
    if paper is None or not paper.file_path:
        raise ValueError(f"Paper for task {task_id} not found or missing file")

    framework = load_framework(task.framework_path or "configs/frameworks/law-v2.3-20260421.yaml")
    provider_names = json.loads(task.provider_names or '["openai","anthropic","deepseek"]')
    providers = provider_factory(provider_names)
    if not providers:
        raise ValueError("No providers configured")

    task.status = "processing"
    task.failure_stage = None
    task.failure_detail = None
    paper.status = "processing"
    db.add(task)
    db.add(paper)
    db.commit()

    try:
        processed_paper = process_file(paper.file_path)
        precheck = await run_precheck(
            providers[0],
            framework,
            processed_paper,
            task.id,
            db,
        )
        paper.precheck_status = precheck.status
        paper.precheck_result = precheck.model_dump()
        db.add(paper)
        db.commit()

        # Terminal precheck statuses that stop scoring
        if precheck.status == "reject":
            ensure_valid_task_transition(task.status, "completed")
            task.status = "completed"
            paper.status = "completed"
            db.add(task)
            db.add(paper)
            db.commit()
            generate_reports_for_task(db, task.id)
            return {
                "task_status": task.status,
                "paper_status": paper.status,
                "precheck_status": paper.precheck_status,
                "reliability_summary": None,
            }

        if precheck.status == "manual_review":
            ensure_valid_task_transition(task.status, "reviewing")
            task.status = "reviewing"
            task.manual_review_requested = True
            paper.status = "reviewing"
            db.add(task)
            db.add(paper)
            db.commit()
            generate_reports_for_task(db, task.id)
            return {
                "task_status": task.status,
                "paper_status": paper.status,
                "precheck_status": paper.precheck_status,
                "reliability_summary": None,
            }

        # "pass" and "conditional_pass" continue to scoring
        reliability_reports = []
        for dimension in framework.dimensions:
            results = await evaluate_dimension_concurrent(
                providers,
                dimension,
                processed_paper,
                task.id,
                db,
            )
            if not results:
                raise ValueError(f"No successful results for dimension {dimension.key}")

            for result in results:
                db.add(
                    DimensionScore(
                        task_id=task.id,
                        dimension_key=dimension.key,
                        model_name=result.model_name,
                        score=result.score,
                        evidence_quotes=result.evidence_quotes,
                        analysis=result.analysis,
                    )
                )

            report = calculate_reliability(
                dimension.key,
                results,
                std_threshold=framework.std_threshold,
            )
            reliability_reports.append(report)
            db.add(
                ReliabilityResult(
                    task_id=task.id,
                    dimension_key=dimension.key,
                    mean_score=report.mean,
                    std_score=report.std,
                    is_high_confidence=report.is_high_confidence,
                    model_scores=report.model_scores,
                )
            )
            db.commit()

        summary = summarize_reliability(reliability_reports)
        ensure_valid_task_transition(task.status, "completed")
        task.status = "completed"
        paper.status = "completed"
        db.add(task)
        db.add(paper)
        db.commit()
        generate_reports_for_task(db, task.id)
        return {
            "task_status": task.status,
            "paper_status": paper.status,
            "precheck_status": paper.precheck_status,
            "reliability_summary": summary,
        }
    except Exception as exc:
        ensure_valid_task_transition(task.status, "recovering")
        task.status = "recovering"
        task.failure_stage = "evaluation"
        task.failure_detail = str(exc)
        paper.status = "recovering"
        db.add(task)
        db.add(paper)
        db.commit()
        raise
