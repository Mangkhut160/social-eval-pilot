import pytest

from src.evaluation.providers.factory import create_providers


def test_create_providers_supports_verified_zenmux_models() -> None:
    providers = create_providers(
        [
            "z-ai/glm-5.1",
            "qwen/qwen3.6-plus",
            "openai/gpt-5.4",
        ]
    )

    assert [provider.model_name for provider in providers] == [
        "z-ai/glm-5.1",
        "qwen/qwen3.6-plus",
        "openai/gpt-5.4",
    ]


def test_create_providers_rejects_unknown_provider_name() -> None:
    with pytest.raises(ValueError, match="未知 Provider"):
        create_providers(["unknown-provider"])
