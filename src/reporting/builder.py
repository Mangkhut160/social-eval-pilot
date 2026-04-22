from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from src.knowledge.loader import load_framework
from src.models.evaluation import DimensionScore, EvaluationTask
from src.models.paper import Paper
from src.models.reliability import ReliabilityResult
from src.models.review import ExpertReview, ReviewComment
from src.reporting.charts import generate_radar_chart_png


# Terminal precheck statuses that stop scoring
TERMINAL_PRECHECK_STATUSES = {"reject"}
DEFAULT_FRAMEWORK_PATH = "configs/frameworks/law-v2.5-20260422.yaml"


def _normalize_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_normalize_text_list(item))
        return items
    text = str(value).strip()
    return [text] if text else []


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _normalize_limit_rules(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _build_model_label_map(
    task: EvaluationTask, score_rows: list[DimensionScore]
) -> dict[str, str]:
    ordered_models: list[str] = []
    seen: set[str] = set()

    if task.provider_names:
        try:
            provider_names = json.loads(task.provider_names)
        except json.JSONDecodeError:
            provider_names = [
                name.strip() for name in task.provider_names.split(",") if name.strip()
            ]
        if isinstance(provider_names, list):
            for raw_name in provider_names:
                model_name = str(raw_name).strip()
                if not model_name or model_name in seen:
                    continue
                seen.add(model_name)
                ordered_models.append(model_name)

    for score in score_rows:
        if score.model_name in seen:
            continue
        seen.add(score.model_name)
        ordered_models.append(score.model_name)

    return {
        model_name: f"模型{index}"
        for index, model_name in enumerate(ordered_models, start=1)
    }


def _build_precheck_payload(
    task: EvaluationTask, model_label_map: dict[str, str], precheck_result: object
) -> dict | None:
    if not isinstance(precheck_result, dict):
        return None

    normalized = dict(precheck_result)
    consensus = normalized.get("consensus")
    if not isinstance(consensus, dict):
        consensus = {
            "status": normalized.get("status"),
            "issues": _normalize_text_list(normalized.get("issues")),
            "recommendation": normalized.get("recommendation"),
            "evidence_quotes": _normalize_text_list(normalized.get("evidence_quotes")),
            "review_flags": _normalize_text_list(normalized.get("review_flags")),
        }
    else:
        consensus = {
            **consensus,
            "issues": _normalize_text_list(consensus.get("issues")),
            "evidence_quotes": _normalize_text_list(consensus.get("evidence_quotes")),
            "review_flags": _normalize_text_list(consensus.get("review_flags")),
        }
    normalized["consensus"] = consensus

    per_model_entries = normalized.get("per_model")
    if isinstance(per_model_entries, list):
        normalized["per_model"] = [
            {
                **entry,
                "display_label": model_label_map.get(
                    str(entry.get("model_name", "")).strip(),
                    str(entry.get("model_name", "")).strip() or f"模型{index}",
                ),
                "issues": _normalize_text_list(entry.get("issues")),
                "evidence_quotes": _normalize_text_list(entry.get("evidence_quotes")),
                "review_flags": _normalize_text_list(entry.get("review_flags")),
            }
            for index, entry in enumerate(per_model_entries, start=1)
            if isinstance(entry, dict)
        ]

    normalized["issues"] = _normalize_text_list(normalized.get("issues"))
    normalized["evidence_quotes"] = _normalize_text_list(
        normalized.get("evidence_quotes")
    )
    normalized["review_flags"] = _normalize_text_list(normalized.get("review_flags"))
    return normalized


def _build_per_model_entry(
    score: DimensionScore, display_label: str | None
) -> dict[str, Any]:
    payload = (
        score.structured_payload if isinstance(score.structured_payload, dict) else {}
    )
    summary = payload.get("summary")
    core_judgment = payload.get("core_judgment")
    score_rationale = payload.get("score_rationale")
    analysis = payload.get("analysis")

    return {
        "model_name": score.model_name,
        "display_label": display_label or score.model_name,
        "dimension": payload.get("dimension") or score.dimension_key,
        "score": payload.get("score", score.score),
        "band": payload.get("band"),
        "summary": summary,
        "core_judgment": core_judgment or analysis or score.analysis,
        "score_rationale": score_rationale,
        "analysis": analysis or score.analysis,
        "evidence_quotes": _normalize_text_list(
            payload.get("evidence_quotes") or score.evidence_quotes
        ),
        "strengths": _normalize_text_list(payload.get("strengths")),
        "weaknesses": _normalize_text_list(payload.get("weaknesses")),
        "limit_rule_triggered": _normalize_limit_rules(
            payload.get("limit_rule_triggered")
        ),
        "boundary_note": payload.get("boundary_note"),
        "review_flags": _normalize_text_list(payload.get("review_flags")),
    }


def _build_consensus_payload(
    reliability: ReliabilityResult | None,
    per_model_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_quotes = _dedupe_preserve_order(
        [quote for entry in per_model_entries for quote in entry["evidence_quotes"]]
    )
    summaries = _dedupe_preserve_order(
        [
            text
            for entry in per_model_entries
            for text in _normalize_text_list(entry.get("summary"))
        ]
    )
    core_judgments = _dedupe_preserve_order(
        [
            text
            for entry in per_model_entries
            for text in _normalize_text_list(entry.get("core_judgment"))
        ]
    )
    score_rationales = _dedupe_preserve_order(
        [
            text
            for entry in per_model_entries
            for text in _normalize_text_list(entry.get("score_rationale"))
        ]
    )
    strengths = _dedupe_preserve_order(
        [text for entry in per_model_entries for text in entry["strengths"]]
    )
    weaknesses = _dedupe_preserve_order(
        [text for entry in per_model_entries for text in entry["weaknesses"]]
    )
    review_flags = _dedupe_preserve_order(
        [text for entry in per_model_entries for text in entry["review_flags"]]
    )
    band_distribution: dict[str, int] = {}
    limit_rules: list[dict[str, Any]] = []
    seen_limit_rule_keys: set[tuple[tuple[str, str], ...]] = set()
    for entry in per_model_entries:
        band = entry.get("band")
        if isinstance(band, str) and band.strip():
            band_distribution[band] = band_distribution.get(band, 0) + 1
        for rule in entry["limit_rule_triggered"]:
            normalized_key = tuple(
                sorted((str(key), str(value)) for key, value in rule.items())
            )
            if normalized_key in seen_limit_rule_keys:
                continue
            seen_limit_rule_keys.add(normalized_key)
            limit_rules.append(rule)

    return {
        "mean_score": reliability.mean_score if reliability else 0.0,
        "std_score": reliability.std_score if reliability else 0.0,
        "is_high_confidence": reliability.is_high_confidence if reliability else True,
        "summary": "；".join(summaries) if summaries else None,
        "core_judgment": "；".join(core_judgments) if core_judgments else None,
        "score_rationale": "\n".join(score_rationales) if score_rationales else None,
        "evidence_quotes": evidence_quotes,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "review_flags": review_flags,
        "limit_rule_triggered": limit_rules,
        "band_distribution": band_distribution,
    }


def build_internal_report(db: Session, task: EvaluationTask, paper: Paper) -> dict:
    framework = load_framework(task.framework_path or DEFAULT_FRAMEWORK_PATH)
    score_rows = (
        db.query(DimensionScore)
        .filter(DimensionScore.task_id == task.id)
        .order_by(DimensionScore.created_at.asc(), DimensionScore.model_name.asc())
        .all()
    )
    reliability_rows = {
        row.dimension_key: row
        for row in db.query(ReliabilityResult)
        .filter(ReliabilityResult.task_id == task.id)
        .all()
    }
    review_rows = db.query(ExpertReview).filter(ExpertReview.task_id == task.id).all()
    review_ids = [review.id for review in review_rows]
    comments_by_review: dict[str, list[ReviewComment]] = defaultdict(list)
    if review_ids:
        comment_rows = (
            db.query(ReviewComment)
            .filter(ReviewComment.review_id.in_(review_ids))
            .all()
        )
        for comment in comment_rows:
            comments_by_review[comment.review_id].append(comment)

    scores_by_dimension: dict[str, list[DimensionScore]] = defaultdict(list)
    for score in score_rows:
        scores_by_dimension[score.dimension_key].append(score)
    model_label_map = _build_model_label_map(task, score_rows)

    # Check if precheck terminated scoring (reject)
    is_terminal_precheck = paper.precheck_status in TERMINAL_PRECHECK_STATUSES

    dimensions = []
    weighted_total = 0.0
    radar_labels: list[str] = []
    radar_values: list[float] = []
    precheck_payload = _build_precheck_payload(
        task, model_label_map, paper.precheck_result
    )

    if not is_terminal_precheck:
        for dimension in framework.dimensions:
            reliability = reliability_rows.get(dimension.key)
            dimension_scores = scores_by_dimension.get(dimension.key, [])
            mean_score = reliability.mean_score if reliability else 0.0
            weighted_total += mean_score * dimension.weight
            radar_labels.append(dimension.name_en)
            radar_values.append(mean_score)
            per_model_entries = [
                _build_per_model_entry(score, model_label_map.get(score.model_name))
                for score in dimension_scores
            ]
            consensus = _build_consensus_payload(reliability, per_model_entries)
            dimensions.append(
                {
                    "key": dimension.key,
                    "name_zh": dimension.name_zh,
                    "name_en": dimension.name_en,
                    "weight": dimension.weight,
                    "ai": {
                        "model_scores": reliability.model_scores if reliability else {},
                        "evidence_quotes": [
                            entry["evidence_quotes"] for entry in per_model_entries
                        ],
                        "analysis": [
                            entry["analysis"]
                            for entry in per_model_entries
                            if entry.get("analysis")
                        ],
                    },
                    "consensus": consensus,
                    "per_model": per_model_entries,
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
                "completed_at": review.completed_at.isoformat()
                if review.completed_at
                else None,
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
        "precheck_result": precheck_payload,
        "is_terminal_precheck": is_terminal_precheck,
        "weighted_total": round(weighted_total, 2),
        "radar_chart": {
            "labels": radar_labels,
            "values": radar_values,
            "image_png_bytes": generate_radar_chart_png(radar_labels, radar_values),
        },
        "dimensions": dimensions,
        "expert_reviews": expert_reviews,
    }
