import asyncio
import time
from sqlalchemy.orm import Session

from src.evaluation.providers.base import BaseProvider
from src.evaluation.schemas import DimensionResult
from src.knowledge.schemas import Dimension
from src.ingestion.schemas import ProcessedPaper
from src.evaluation.prompt_builder import build_prompt
from src.evaluation.call_logger import log_call


async def _call_with_timing(
    provider: BaseProvider, prompt: str, retry_attempts: int = 3
) -> tuple[DimensionResult | Exception, float, str]:
    start = time.time()
    last_error: Exception | None = None
    for _ in range(retry_attempts):
        try:
            result = await provider.evaluate_dimension(prompt)
            return result, start, prompt
        except Exception as exc:  # pragma: no cover - covered by retry behavior in integration tests
            last_error = exc
    return last_error or RuntimeError("Unknown evaluation failure"), start, prompt


async def evaluate_dimension_concurrent(
    providers: list[BaseProvider],
    dimension: Dimension,
    paper: ProcessedPaper,
    task_id: str,
    db: Session,
) -> list[DimensionResult]:
    """并发调用所有 Provider 评估单个维度，记录每次调用日志，返回成功结果列表"""
    prompt = build_prompt(dimension, paper)
    raw_results = await asyncio.gather(
        *[_call_with_timing(p, prompt) for p in providers],
        return_exceptions=False,
    )
    results = []
    for (outcome, start_time, used_prompt), provider in zip(raw_results, providers):
        response_text = (
            outcome.model_dump_json()
            if isinstance(outcome, DimensionResult)
            else str(outcome)
        )
        log_call(
            db,
            task_id,
            provider.model_name,
            dimension.key,
            used_prompt,
            response_text,
            start_time,
        )
        if isinstance(outcome, DimensionResult):
            results.append(outcome)
    return results
