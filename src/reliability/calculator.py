import statistics
from src.evaluation.schemas import DimensionResult
from src.reliability.schemas import ReliabilityReport


def calculate_reliability(
    dimension_key: str,
    results: list[DimensionResult],
    std_threshold: float = 5.0,
) -> ReliabilityReport:
    if not results:
        raise ValueError(f"维度 {dimension_key} 无评估结果")
    scores = [r.score for r in results]
    mean = statistics.mean(scores)
    std = statistics.stdev(scores) if len(scores) > 1 else 0.0
    is_high_confidence = std <= std_threshold
    return ReliabilityReport(
        dimension_key=dimension_key,
        mean=mean,
        std=std,
        is_high_confidence=is_high_confidence,
        model_scores={r.model_name: r.score for r in results},
    )
