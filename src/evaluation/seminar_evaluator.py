import asyncio
from dataclasses import dataclass, field
from src.evaluation.providers.base import BaseProvider
from src.evaluation.schemas import DimensionResult
from src.knowledge.schemas import Dimension
from src.ingestion.schemas import ProcessedPaper
from src.evaluation.prompt_builder import build_prompt

CONVERGENCE_THRESHOLD = 3.0  # 分数变化小于此值视为收敛
MAX_ROUNDS = 5


@dataclass
class SeminarResult:
    dimension_key: str
    final_score: float
    converged: bool
    rounds: int
    round_scores: list[float] = field(default_factory=list)


async def run_seminar(
    providers: list[BaseProvider],
    dimension: Dimension,
    paper: ProcessedPaper,
) -> SeminarResult:
    """多轮研讨评估：收敛（连续两轮均值变化 < 阈值）或达到上限后终止"""
    prompt = build_prompt(dimension, paper)
    round_scores: list[float] = []

    for round_num in range(1, MAX_ROUNDS + 1):
        tasks = [p.evaluate_dimension(prompt) for p in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid = [r for r in results if isinstance(r, DimensionResult)]
        if not valid:
            break
        avg = sum(r.score for r in valid) / len(valid)
        round_scores.append(avg)

        # 收敛判断：连续两轮变化 < CONVERGENCE_THRESHOLD
        if len(round_scores) >= 2:
            delta = abs(round_scores[-1] - round_scores[-2])
            if delta < CONVERGENCE_THRESHOLD:
                return SeminarResult(
                    dimension_key=dimension.key,
                    final_score=avg,
                    converged=True,
                    rounds=round_num,
                    round_scores=round_scores,
                )

    return SeminarResult(
        dimension_key=dimension.key,
        final_score=round_scores[-1] if round_scores else 0.0,
        converged=False,
        rounds=len(round_scores),
        round_scores=round_scores,
    )
