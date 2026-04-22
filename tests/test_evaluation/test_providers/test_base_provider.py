import pytest
from src.evaluation.providers.base import BaseProvider
from src.evaluation.schemas import DimensionResult


class MockProvider(BaseProvider):
    model_name = "mock-model"

    async def evaluate_dimension(self, prompt: str) -> DimensionResult:
        return DimensionResult(
            dimension="test_dim",
            score=75,
            evidence_quotes=["引用片段一", "引用片段二"],
            analysis="这是测试分析文字",
            model_name=self.model_name,
        )


@pytest.mark.asyncio
async def test_mock_provider_returns_dimension_result():
    provider = MockProvider()
    result = await provider.evaluate_dimension("test prompt")
    assert result.score == 75
    assert result.model_name == "mock-model"
    assert isinstance(result.evidence_quotes, list)
    assert len(result.evidence_quotes) == 2


@pytest.mark.asyncio
async def test_mock_provider_result_has_required_fields():
    provider = MockProvider()
    result = await provider.evaluate_dimension("another prompt")
    assert result.dimension == "test_dim"
    assert result.analysis != ""
    assert 0 <= result.score <= 100


def test_dimension_result_model():
    result = DimensionResult(
        dimension="problem_originality",
        score=85,
        evidence_quotes=["evidence 1"],
        analysis="good paper",
        model_name="gpt-4o",
    )
    assert result.dimension == "problem_originality"
    assert result.score == 85
