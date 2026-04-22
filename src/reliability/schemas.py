from pydantic import BaseModel


class ReliabilityReport(BaseModel):
    dimension_key: str
    mean: float
    std: float
    is_high_confidence: bool
    model_scores: dict[str, float]
