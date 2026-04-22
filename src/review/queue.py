from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from src.models.evaluation import EvaluationTask
from src.models.paper import Paper
from src.models.reliability import ReliabilityResult
from src.models.review import ExpertReview
from src.models.user import User


def list_review_queue(db: Session) -> list[dict]:
    queued_tasks = []
    tasks = db.query(EvaluationTask).all()
    task_ids = [task.id for task in tasks]
    reviews_by_task: dict[str, list[ExpertReview]] = defaultdict(list)
    if task_ids:
        review_rows = db.query(ExpertReview).filter(ExpertReview.task_id.in_(task_ids)).all()
        for review in review_rows:
            reviews_by_task[review.task_id].append(review)
    expert_ids = sorted(
        {
            review.expert_id
            for reviews in reviews_by_task.values()
            for review in reviews
        }
    )
    experts_by_id = {
        expert.id: expert
        for expert in db.query(User).filter(User.id.in_(expert_ids)).all()
    } if expert_ids else {}
    for task in tasks:
        low_confidence_rows = (
            db.query(ReliabilityResult)
            .filter(ReliabilityResult.task_id == task.id, ReliabilityResult.is_high_confidence.is_(False))
            .all()
        )
        if not low_confidence_rows and not task.manual_review_requested and task.status != "reviewing":
            continue
        paper = db.get(Paper, task.paper_id)
        active_reviews = [
            review for review in reviews_by_task.get(task.id, []) if review.status != "returned"
        ]
        review_reasons: list[str] = []
        if task.manual_review_requested:
            review_reasons.append("precheck_flagged")
        if low_confidence_rows:
            review_reasons.append("low_confidence")
        queued_tasks.append(
            {
                "task_id": task.id,
                "paper_id": task.paper_id,
                "paper_title": (paper.title if paper else None),
                "paper_status": paper.status if paper else None,
                "task_status": task.status,
                "low_confidence_dimensions": [row.dimension_key for row in low_confidence_rows],
                "review_reasons": review_reasons,
                "needs_assignment": len(active_reviews) == 0,
                "assigned_reviews": [
                    {
                        "review_id": review.id,
                        "expert_id": review.expert_id,
                        "expert_email": experts_by_id[review.expert_id].email,
                        "expert_display_name": experts_by_id[review.expert_id].display_name,
                        "status": review.status,
                        "completed_at": review.completed_at.isoformat()
                        if review.completed_at
                        else None,
                    }
                    for review in active_reviews
                    if review.expert_id in experts_by_id
                ],
            }
        )
    return queued_tasks
