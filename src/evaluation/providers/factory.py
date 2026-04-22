from src.evaluation.providers.base import BaseProvider
from src.evaluation.providers.openai_provider import OpenAIProvider
from src.evaluation.providers.anthropic_provider import AnthropicProvider
from src.evaluation.providers.deepseek_provider import DeepSeekProvider
from src.evaluation.providers.zenmux_provider import ZENMUX_MODEL_OPTIONS, ZenmuxProvider

_PROVIDER_MAP: dict[str, type[BaseProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "deepseek": DeepSeekProvider,
}


def create_providers(names: list[str]) -> list[BaseProvider]:
    providers = []
    for name in names:
        cls = _PROVIDER_MAP.get(name)
        if cls is not None:
            providers.append(cls())
            continue
        if name in ZENMUX_MODEL_OPTIONS:
            providers.append(ZenmuxProvider(name))
            continue
        raise ValueError(f"未知 Provider：{name}")
    return providers
