from __future__ import annotations

import json
from typing import Any

import openai

from src.core.config import DEFAULT_ZENMUX_BASE_URL, settings
from src.core.exceptions import ProviderCallError
from src.evaluation.providers.base import BaseProvider
from src.evaluation.schemas import DimensionResult


ZENMUX_MODEL_OPTIONS: dict[str, dict[str, Any]] = {
    "anthropic/claude-sonnet-4.6": {},
    "moonshotai/kimi-k2.6": {"temperature": 1},
    "openai/gpt-5.4": {},
    "google/gemini-3.1-pro-preview": {},
}


def _extract_json_payload(content: str) -> dict[str, Any]:
    normalized = content.strip()
    if "```json" in normalized:
        normalized = normalized.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in normalized:
        normalized = normalized.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        start = normalized.find("{")
        end = normalized.rfind("}")
        if start == -1 or end == -1 or start >= end:
            raise
        return json.loads(normalized[start : end + 1])


class ZenmuxProvider(BaseProvider):
    def __init__(self, model_name: str):
        if model_name not in ZENMUX_MODEL_OPTIONS:
            raise ValueError(f"Unsupported Zenmux model: {model_name}")
        self.model_name = model_name
        self._request_options = dict(ZENMUX_MODEL_OPTIONS[model_name])
        self._client: openai.AsyncOpenAI | None = None

    def _get_client(self) -> openai.AsyncOpenAI:
        if self._client is not None:
            return self._client
        if not settings.zenmux_api_key:
            raise ProviderCallError(self.model_name, "ZENMUX_API_KEY is not configured")
        self._client = openai.AsyncOpenAI(
            api_key=settings.zenmux_api_key,
            base_url=(settings.zenmux_base_url or DEFAULT_ZENMUX_BASE_URL).rstrip("/"),
        )
        return self._client

    async def generate_json_response(self, prompt: str) -> dict:
        try:
            response = await self._get_client().chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                **self._request_options,
            )
            content = response.choices[0].message.content or ""
            return _extract_json_payload(content)
        except Exception as exc:
            raise ProviderCallError(self.model_name, str(exc)) from exc

    async def evaluate_dimension(self, prompt: str) -> DimensionResult:
        data = await self.generate_json_response(prompt)
        return DimensionResult(**data, model_name=self.model_name)
