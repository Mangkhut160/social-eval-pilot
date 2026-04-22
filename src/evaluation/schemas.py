from pydantic import BaseModel, Field


class DimensionResult(BaseModel):
    dimension: str
    score: int  # 0-100
    evidence_quotes: list[str] = Field(default_factory=list)
    analysis: str | None = None
    model_name: str

    # v2.4 structured contract fields
    band: str | None = None
    summary: str | None = None
    core_judgment: str | None = None
    score_rationale: str | None = None

    # v2.3 optional fields for enhanced output
    strengths: list[str] | None = None
    weaknesses: list[str] | None = None
    limit_rule_triggered: list[dict] | None = None
    boundary_note: str | None = None
    review_flags: list[str] | None = None
