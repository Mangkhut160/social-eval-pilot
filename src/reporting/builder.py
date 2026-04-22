from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from src.knowledge.loader import load_framework
from src.models.evaluation import DimensionScore, EvaluationTask
from src.models.paper import Paper
from src.models.reliability import ReliabilityResult
from src.models.review import ExpertReview, ReviewComment
from src.reporting.charts import generate_radar_chart_base64


# Terminal precheck statuses that stop scoring
TERMINAL_PRECHECK_STATUSES = {"reject", "manual_review"}


def build_internal_report(db: Session, task: EvaluationTask, paper: Paper) -> dict:
    framework = load_framework(task.framework_path or "configs/frameworks/law-v2.3-20260421.yaml")
    score_rows = db.query(DimensionScore).filter(DimensionScore.task_id == task.id).all()
    reliability_rows = {
        row.dimension_key: row
        for row in db.query(ReliabilityResult).filter(ReliabilityResult.task_id == task.id).all()
    }
    review_rows = db.query(ExpertReview).filter(ExpertReview.task_id == task.id).all()
    review_ids = [review.id for review in review_rows]
    comments_by_review: dict[str, list[ReviewComment]] = defaultdict(list)
    if review_ids:
        comment_rows = db.query(ReviewComment).filter(ReviewComment.review_id.in_(review_ids)).all()
        for comment in comment_rows:
            comments_by_review[comment.review_id].append(comment)

    scores_by_dimension: dict[str, list[DimensionScore]] = defaultdict(list)
    for score in score_rows:
        scores_by_dimension[score.dimension_key].append(score)

    # Check if precheck terminated scoring (reject or manual_review)
    is_terminal_precheck = paper.precheck_status in TERMINAL_PRECHECK_STATUSES

    dimensions = []
    weighted_total = 0.0
    radar_labels: list[str] = []
    radar_values: list[float] = []

    for dimension in framework.dimensions:
        reliability = reliability_rows.get(dimension.key)
        dimension_scores = scores_by_dimension.get(dimension.key, [])
        mean_score = reliability.mean_score if reliability else 0.0
        weighted_total += mean_score * dimension.weight
        radar_labels.append(dimension.name_en)
        radar_values.append(mean_score)
        dimensions.append(
            {
                "key": dimension.key,
                "name_zh": dimension.name_zh,
                "name_en": dimension.name_en,
                "weight": dimension.weight,
                "ai": {
                    "mean_score": mean_score,
                    "std_score": reliability.std_score if reliability else 0.0,
                    "is_high_confidence": reliability.is_high_confidence if reliability else True,
                    "model_scores": reliability.model_scores if reliability else {},
                    "evidence_quotes": [
                        score.evidence_quotes for score in dimension_scores if score.evidence_quotes
                    ],
                    "analysis": [
                        score.analysis for score in dimension_scores if score.analysis
                    ],
                },
            }
        )

    expert_reviews = []
    for review in review_rows:
        expert_reviews.append(
            {
                "review_id": review.id,
                "expert_id": review.expert_id,
                "status": review.status,
                "version": review.version,
                "completed_at": review.completed_at.isoformat() if review.completed_at else None,
                "comments": [
                    {
                        "dimension_key": comment.dimension_key,
                        "ai_score": comment.ai_score,
                        "expert_score": comment.expert_score,
                        "reason": comment.reason,
                    }
                    for comment in comments_by_review.get(review.id, [])
                ],
            }
        )

    return {
        "report_type": "internal",
        "paper_id": paper.id,
        "task_id": task.id,
        "paper_title": paper.title or paper.original_filename,
        "precheck_status": paper.precheck_status,
        "precheck_result": paper.precheck_result,
        "is_terminal_precheck": is_terminal_precheck,
        "weighted_total": round(weighted_total, 2),
        "radar_chart": {
            "labels": radar_labels,
            "values": radar_values,
            "image_base64": generate_radar_chart_base64(radar_labels, radar_values),
        },
        "dimensions": dimensions,
        "expert_reviews": expert_reviews,
    }
