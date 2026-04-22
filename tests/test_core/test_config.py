from src.core.config import Settings


def test_settings_parse_default_provider_names_and_zenmux_config() -> None:
    runtime_settings = Settings(
        _env_file=None,
        default_provider_names="z-ai/glm-5.1, qwen/qwen3.6-plus , openai/gpt-5.4",
        zenmux_base_url="https://zenmux.ai/api/v1",
        zenmux_api_key="test-key",
    )

    assert runtime_settings.default_provider_name_list == [
        "z-ai/glm-5.1",
        "qwen/qwen3.6-plus",
        "openai/gpt-5.4",
    ]
    assert runtime_settings.zenmux_base_url == "https://zenmux.ai/api/v1"
    assert runtime_settings.zenmux_api_key == "test-key"


def test_settings_default_provider_names_fall_back_to_legacy_trio() -> None:
    runtime_settings = Settings(
        _env_file=None,
        default_provider_names="",
    )

    assert runtime_settings.default_provider_name_list == [
        "openai",
        "anthropic",
        "deepseek",
    ]
