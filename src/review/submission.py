from __future__ import annotations

from sqlalchemy.orm import Session

from src.core.time import utc_now
from src.models.evaluation import EvaluationTask
from src.models.paper import Paper
from src.models.review import ExpertReview, ReviewComment
from src.reporting.versioning import generate_reports_for_task


def submit_expert_review(
    db: Session,
    *,
    review_id: str,
    expert_id: str,
    comments: list[dict],
) -> ExpertReview:
    review = db.get(ExpertReview, review_id)
    if review is None or review.expert_id != expert_id:
        raise ValueError("Review not found")

    db.query(ReviewComment).filter(ReviewComment.review_id == review.id).delete()
    for comment in comments:
        db.add(
            ReviewComment(
                review_id=review.id,
                dimension_key=comment["dimension_key"],
                ai_score=comment["ai_score"],
                expert_score=comment["expert_score"],
                reason=comment["reason"],
            )
        )

    review.status = "submitted"
    review.completed_at = utc_now()
    db.add(review)
    db.commit()
    db.refresh(review)

    task = db.get(EvaluationTask, review.task_id)
    paper = db.get(Paper, task.paper_id) if task else None
    if task is None or paper is None:
        raise ValueError("Review task not found")

    pending_reviews = (
        db.query(ExpertReview)
        .filter(ExpertReview.task_id == task.id, ExpertReview.status != "submitted")
        .count()
    )
    if pending_reviews == 0:
        task.status = "completed"
        task.manual_review_requested = False
        paper.status = "completed"
    else:
        task.status = "reviewing"
        paper.status = "reviewing"

    db.add(task)
    db.add(paper)
    db.commit()
    generate_reports_for_task(db, task.id)
    return review
