from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from src.evaluation.providers.zenmux_provider import ZENMUX_MODEL_OPTIONS
from src.evaluation.schemas import DimensionResult

DEFAULT_EVALUATION_ROUNDS = 1
MIN_EVALUATION_ROUNDS = 1
MAX_EVALUATION_ROUNDS = 5


@dataclass(frozen=True)
class EvaluationTaskConfig:
    selected_models: list[str]
    evaluation_rounds: int = DEFAULT_EVALUATION_ROUNDS

    def as_dict(self) -> dict[str, Any]:
        return {
            "selected_models": list(self.selected_models),
            "evaluation_rounds": self.evaluation_rounds,
        }


def normalize_selected_models(selected_models: list[str]) -> list[str]:
    unique_models: list[str] = []
    seen: set[str] = set()
    for raw_name in selected_models:
        name = raw_name.strip()
        if not name or name in seen:
            continue
        unique_models.append(name)
        seen.add(name)
    if not unique_models:
        raise ValueError("At least one evaluation model must be selected")
    return unique_models


def validate_evaluation_rounds(evaluation_rounds: int) -> int:
    if evaluation_rounds < MIN_EVALUATION_ROUNDS or evaluation_rounds > MAX_EVALUATION_ROUNDS:
        raise ValueError(
            f"Evaluation rounds must be between {MIN_EVALUATION_ROUNDS} and {MAX_EVALUATION_ROUNDS}"
        )
    return evaluation_rounds


def validate_selected_model_limit(selected_models: list[str], max_selected_models: int) -> list[str]:
    normalized = normalize_selected_models(selected_models)
    if len(normalized) > max_selected_models:
        raise ValueError(f"At most {max_selected_models} evaluation models may be selected")
    return normalized


def serialize_task_config(selected_models: list[str], evaluation_rounds: int) -> str:
    config = EvaluationTaskConfig(
        selected_models=normalize_selected_models(selected_models),
        evaluation_rounds=validate_evaluation_rounds(evaluation_rounds),
    )
    return json.dumps(
        {
            "selected_provider_names": config.selected_models,
            "evaluation_rounds": config.evaluation_rounds,
        },
        ensure_ascii=False,
    )


def parse_task_config(
    raw_provider_names: str | None,
    default_selected_models: list[str],
) -> EvaluationTaskConfig:
    fallback_models = normalize_selected_models(default_selected_models)
    if not raw_provider_names:
        return EvaluationTaskConfig(selected_models=fallback_models)

    normalized = raw_provider_names.strip()
    payload: Any
    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError:
        payload = [name.strip() for name in normalized.split(",") if name.strip()]

    if isinstance(payload, list):
        return EvaluationTaskConfig(
            selected_models=normalize_selected_models([str(item) for item in payload]),
            evaluation_rounds=DEFAULT_EVALUATION_ROUNDS,
        )

    if isinstance(payload, dict):
        raw_models = payload.get("selected_provider_names") or payload.get("selected_models")
        if raw_models is None:
            selected_models = fallback_models
        elif isinstance(raw_models, str):
            selected_models = normalize_selected_models(
                [name.strip() for name in raw_models.split(",") if name.strip()]
            )
        else:
            selected_models = normalize_selected_models([str(item) for item in raw_models])
        raw_rounds = payload.get("evaluation_rounds", DEFAULT_EVALUATION_ROUNDS)
        try:
            evaluation_rounds = int(raw_rounds)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid evaluation rounds value") from exc
        return EvaluationTaskConfig(
            selected_models=selected_models,
            evaluation_rounds=validate_evaluation_rounds(evaluation_rounds),
        )

    raise ValueError("Unsupported task configuration payload")


def build_model_options(
    default_selected_models: list[str],
    *,
    zenmux_enabled: bool,
    openai_enabled: bool,
    anthropic_enabled: bool,
    deepseek_enabled: bool,
) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    seen: set[str] = set()

    def add_option(name: str, source: str) -> None:
        if not name or name in seen:
            return
        seen.add(name)
        options.append({"name": name, "label": name, "source": source})

    for model_name in default_selected_models:
        add_option(model_name, _infer_option_source(model_name))

    if zenmux_enabled:
        for model_name in ZENMUX_MODEL_OPTIONS:
            add_option(model_name, "zenmux")

    if openai_enabled:
        add_option("openai", "native")
    if anthropic_enabled:
        add_option("anthropic", "native")
    if deepseek_enabled:
        add_option("deepseek", "native")

    return options


def aggregate_results_across_rounds(results: list[DimensionResult]) -> list[DimensionResult]:
    grouped_results: dict[str, list[DimensionResult]] = defaultdict(list)
    for result in results:
        grouped_results[result.model_name].append(result)

    aggregated_results: list[DimensionResult] = []
    for model_name, model_results in grouped_results.items():
        flattened_quotes: list[str] = []
        seen_quotes: set[str] = set()
        analyses: list[str] = []
        for index, result in enumerate(model_results, start=1):
            for quote in result.evidence_quotes:
                if quote not in seen_quotes:
                    seen_quotes.add(quote)
                    flattened_quotes.append(quote)
            analyses.append(f"Round {index}: {result.analysis}")

        aggregated_results.append(
            DimensionResult(
                dimension=model_results[-1].dimension,
                score=round(sum(item.score for item in model_results) / len(model_results)),
                evidence_quotes=flattened_quotes,
                analysis="\n\n".join(analyses),
                model_name=model_name,
            )
        )

    return aggregated_results


def _infer_option_source(model_name: str) -> str:
    if model_name in ZENMUX_MODEL_OPTIONS:
        return "zenmux"
    return "native"
