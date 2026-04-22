from src.reliability.schemas import ReliabilityReport


def needs_expert_review(report: ReliabilityReport) -> bool:
    """根据可靠性报告判断是否需要专家复核（低置信度则需要）"""
    return not report.is_high_confidence


def summarize_reliability(reports: list[ReliabilityReport]) -> dict:
    """汇总所有维度的可靠性状态"""
    low_confidence = [r for r in reports if not r.is_high_confidence]
    return {
        "total_dimensions": len(reports),
        "high_confidence_count": len(reports) - len(low_confidence),
        "low_confidence_count": len(low_confidence),
        "low_confidence_dimensions": [r.dimension_key for r in low_confidence],
        "overall_high_confidence": len(low_confidence) == 0,
    }
