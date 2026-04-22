from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Dimension(BaseModel):
    key: str
    name_zh: str
    name_en: str
    weight: float
    prompt_template: str

    model_config = ConfigDict(extra="allow")


class FrameworkMetadata(BaseModel):
    name: str
    version: str
    discipline: str
    source: str | None = None
    created: str | None = None
    changelog: str | None = None

    model_config = ConfigDict(extra="allow")


class PrecheckCriterion(BaseModel):
    key: str
    name_zh: str
    description: str
    pass_required: bool = True

    model_config = ConfigDict(extra="allow")


class PrecheckConfig(BaseModel):
    name: str
    description: str
    criteria: list[PrecheckCriterion]
    prompt_template: str

    model_config = ConfigDict(extra="allow")


class ScoringStructure(BaseModel):
    total_max: int
    description: str

    model_config = ConfigDict(extra="allow")


class EvaluationChainStep(BaseModel):
    dimension: str
    reason: str

    model_config = ConfigDict(extra="allow")


class EvaluationChain(BaseModel):
    description: str
    sequence: list[EvaluationChainStep] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class DiscriminationLevel(BaseModel):
    level: str
    threshold: int
    confidence: str | None = None
    action: str

    model_config = ConfigDict(extra="allow")


class DiscriminationThreshold(BaseModel):
    description: str
    levels: list[DiscriminationLevel] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class TriggerRule(BaseModel):
    condition: str
    action: str | None = None
    dimension: str | None = None

    model_config = ConfigDict(extra="allow")


class ExpertReviewTriggers(BaseModel):
    dimension_triggers: list[TriggerRule] = Field(default_factory=list)
    overall_triggers: list[TriggerRule] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class Anchor(BaseModel):
    paper: str
    source: str | None = None
    reason: str | None = None
    type: str | None = None

    model_config = ConfigDict(extra="allow")


class Anchors(BaseModel):
    positive: list[Anchor] = Field(default_factory=list)
    negative: list[Anchor] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class Framework(BaseModel):
    name: str
    discipline: str
    version: str
    std_threshold: float
    dimensions: list[Dimension]
    metadata: FrameworkMetadata | None = None
    precheck: PrecheckConfig | None = None
    scoring_structure: ScoringStructure | None = None
    evaluation_chain: EvaluationChain | None = None
    discrimination_threshold: DiscriminationThreshold | None = None
    expert_review_triggers: ExpertReviewTriggers | None = None
    anchors: Anchors | None = None
    raw_config: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")
