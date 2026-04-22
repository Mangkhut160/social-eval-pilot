from __future__ import annotations

import asyncio
import math
import time

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.evaluation.call_logger import log_call
from src.evaluation.prompt_builder import build_precheck_prompt
from src.evaluation.providers.base import BaseProvider
from src.ingestion.schemas import ProcessedPaper
from src.knowledge.schemas import Framework


class PrecheckResult(BaseModel):
    status: str
    issues: list[str] = Field(default_factory=list)
    recommendation: str = ""
    evidence_quotes: list[str] = Field(default_factory=list)  # v2.3: evidence for issues
    review_flags: list[str] = Field(default_factory=list)  # v2.3: flags triggering manual review


class PrecheckModelResult(PrecheckResult):
    model_name: str
    display_label: str | None = None


class AggregatedPrecheckResult(PrecheckResult):
    consensus: dict = Field(default_factory=dict)
    per_model: list[PrecheckModelResult] = Field(default_factory=list)
    decision_rule: str = "2_of_3_blocking_consensus"
    blocking_vote_count: int = 0
    total_models: int = 0


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _normalize_status(value: str) -> str:
    if value in {"pass", "conditional_pass", "manual_review", "reject"}:
        return value
    return "conditional_pass"


def _normalize_review_flags(value: list[str]) -> list[str]:
    normalized = _dedupe_preserve_order([flag for flag in value if flag and flag.strip()])
    non_none = [flag for flag in normalized if flag != "none"]
    return non_none or ["none"]


def _is_soft_flag(result: PrecheckModelResult) -> bool:
    if result.status in {"conditional_pass", "manual_review", "reject"}:
        return True
    return bool(result.issues or any(flag != "none" for flag in result.review_flags))


def _build_recommendation(status: str, results: list[PrecheckModelResult]) -> str:
    if status == "reject":
        for result in results:
            if result.status == "reject" and result.recommendation.strip():
                return result.recommendation.strip()
        return "预检多数模型认为稿件当前不可评，建议修订后重新提交。"

    if status == "conditional_pass":
        for result in results:
            if result.status in {"conditional_pass", "manual_review", "reject"} and result.recommendation.strip():
                return result.recommendation.strip()
        return "继续六维评分，并进入人工复核。"

    for result in results:
        if result.recommendation.strip():
            return result.recommendation.strip()
    return "继续六维评分。"


def aggregate_precheck_results(results: list[PrecheckModelResult]) -> AggregatedPrecheckResult:
    if not results:
        raise ValueError("No precheck results to aggregate")

    normalized_results = [
        PrecheckModelResult(
            model_name=result.model_name,
            display_label=result.display_label,
            status=_normalize_status(result.status),
            issues=_dedupe_preserve_order(result.issues),
            recommendation=result.recommendation.strip(),
            evidence_quotes=_dedupe_preserve_order(result.evidence_quotes),
            review_flags=_normalize_review_flags(result.review_flags),
        )
        for result in results
    ]
    total_models = len(normalized_results)
    blocking_vote_count = sum(result.status == "reject" for result in normalized_results)
    blocking_threshold = math.ceil(total_models * 2 / 3)

    aggregated_issues = _dedupe_preserve_order(
        [issue for result in normalized_results for issue in result.issues]
    )
    aggregated_evidence = _dedupe_preserve_order(
        [quote for result in normalized_results for quote in result.evidence_quotes]
    )
    aggregated_flags = _normalize_review_flags(
        [flag for result in normalized_results for flag in result.review_flags]
    )

    if blocking_vote_count >= blocking_threshold:
        status = "reject"
    elif any(_is_soft_flag(result) for result in normalized_results):
        status = "conditional_pass"
    else:
        status = "pass"

    recommendation = _build_recommendation(status, normalized_results)
    consensus = {
        "status": status,
        "issues": aggregated_issues,
        "recommendation": recommendation,
        "evidence_quotes": aggregated_evidence,
        "review_flags": aggregated_flags,
        "blocking_vote_count": blocking_vote_count,
        "total_models": total_models,
    }

    return AggregatedPrecheckResult(
        status=status,
        issues=aggregated_issues,
        recommendation=recommendation,
        evidence_quotes=aggregated_evidence,
        review_flags=aggregated_flags,
        consensus=consensus,
        per_model=normalized_results,
        decision_rule="2_of_3_blocking_consensus",
        blocking_vote_count=blocking_vote_count,
        total_models=total_models,
    )


async def _call_precheck_with_timing(
    provider: BaseProvider,
    prompt: str,
    retry_attempts: int = 3,
) -> tuple[PrecheckResult | Exception, float, str]:
    start = time.time()
    last_error: Exception | None = None

    for _ in range(retry_attempts):
        try:
            payload = await provider.generate_json_response(prompt)
            return PrecheckResult(**payload), start, prompt
        except Exception as exc:
            last_error = exc

    return last_error or RuntimeError("Precheck failed"), start, prompt


async def run_precheck(
    provider: BaseProvider,
    framework: Framework,
    paper: ProcessedPaper,
    task_id: str,
    db: Session,
    retry_attempts: int = 3,
) -> PrecheckResult:
    prompt = build_precheck_prompt(framework, paper)
    outcome, start, used_prompt = await _call_precheck_with_timing(
        provider,
        prompt,
        retry_attempts=retry_attempts,
    )

    response_text = outcome.model_dump_json() if isinstance(outcome, PrecheckResult) else str(outcome)
    log_call(
        db,
        task_id,
        provider.model_name,
        "__precheck__",
        used_prompt,
        response_text,
        start,
    )
    if isinstance(outcome, PrecheckResult):
        return outcome
    raise outcome


async def run_precheck_concurrent(
    providers: list[BaseProvider],
    framework: Framework,
    paper: ProcessedPaper,
    task_id: str,
    db: Session,
    retry_attempts: int = 3,
) -> AggregatedPrecheckResult:
    prompt = build_precheck_prompt(framework, paper)
    raw_results = await asyncio.gather(
        *[_call_precheck_with_timing(provider, prompt, retry_attempts=retry_attempts) for provider in providers],
        return_exceptions=False,
    )

    successful_results: list[PrecheckModelResult] = []
    last_error: Exception | None = None
    for (outcome, start_time, used_prompt), provider in zip(raw_results, providers):
        response_text = outcome.model_dump_json() if isinstance(outcome, PrecheckResult) else str(outcome)
        log_call(
            db,
            task_id,
            provider.model_name,
            "__precheck__",
            used_prompt,
            response_text,
            start_time,
        )
        if isinstance(outcome, PrecheckResult):
            successful_results.append(
                PrecheckModelResult(
                    model_name=provider.model_name,
                    status=outcome.status,
                    issues=outcome.issues,
                    recommendation=outcome.recommendation,
                    evidence_quotes=outcome.evidence_quotes,
                    review_flags=outcome.review_flags,
                )
            )
        else:
            last_error = outcome

    if not successful_results:
        raise last_error or RuntimeError("Precheck failed")

    return aggregate_precheck_results(successful_results)
