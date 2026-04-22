from pydantic import BaseModel


class DimensionResult(BaseModel):
    dimension: str
    score: int  # 0-100
    evidence_quotes: list[str]
    analysis: str
    model_name: str

    # v2.3 optional fields for enhanced output
    strengths: list[str] | None = None
    weaknesses: list[str] | None = None
    limit_rule_triggered: list[dict] | None = None
    boundary_note: str | None = None
    review_flags: list[str] | None = None
