import json
import openai  # DeepSeek 使用 OpenAI 兼容接口
from src.evaluation.providers.base import BaseProvider
from src.evaluation.schemas import DimensionResult
from src.core.config import settings
from src.core.exceptions import ProviderCallError


class DeepSeekProvider(BaseProvider):
    model_name = "deepseek-chat"
    BASE_URL = "https://api.deepseek.com/v1"

    def __init__(self):
        self._client = openai.AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=self.BASE_URL,
        )

    async def generate_json_response(self, prompt: str) -> dict:
        try:
            response = await self._client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            raise ProviderCallError(self.model_name, str(e)) from e

    async def evaluate_dimension(self, prompt: str) -> DimensionResult:
        data = await self.generate_json_response(prompt)
        return DimensionResult(**data, model_name=self.model_name)
