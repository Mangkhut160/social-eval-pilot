from abc import ABC, abstractmethod
from src.evaluation.schemas import DimensionResult


class BaseProvider(ABC):
    model_name: str

    async def generate_json_response(self, prompt: str) -> dict:
        raise NotImplementedError(f"{self.__class__.__name__} must implement generate_json_response")

    @abstractmethod
    async def evaluate_dimension(self, prompt: str) -> DimensionResult:
        """调用 AI 模型评估单个维度，返回结构化结果"""
