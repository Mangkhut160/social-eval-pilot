import json
import anthropic
from src.evaluation.providers.base import BaseProvider
from src.evaluation.schemas import DimensionResult
from src.core.config import settings
from src.core.exceptions import ProviderCallError


class AnthropicProvider(BaseProvider):
    model_name = "claude-sonnet-4-6"

    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def generate_json_response(self, prompt: str) -> dict:
        try:
            response = await self._client.messages.create(
                model=self.model_name,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            # 从 text block 中解析 JSON
            content_text = response.content[0].text
            # 尝试提取 JSON（可能被 markdown 包裹）
            if "```json" in content_text:
                content_text = content_text.split("```json")[1].split("```")[0].strip()
            elif "```" in content_text:
                content_text = content_text.split("```")[1].split("```")[0].strip()
            return json.loads(content_text)
        except Exception as e:
            raise ProviderCallError(self.model_name, str(e)) from e

    async def evaluate_dimension(self, prompt: str) -> DimensionResult:
        data = await self.generate_json_response(prompt)
        return DimensionResult(**data, model_name=self.model_name)
