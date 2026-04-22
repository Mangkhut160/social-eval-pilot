from __future__ import annotations

import json
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_SECRET_KEY = "change-me-in-production"
DEFAULT_ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
DEFAULT_PUBLIC_BASE_URL = "http://localhost:5173"
DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_PROVIDER_NAMES = ["openai", "anthropic", "deepseek"]
DEFAULT_ZENMUX_BASE_URL = "https://zenmux.ai/api/v1"


class Settings(BaseSettings):
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql://socialeval:socialeval@localhost:5432/socialeval"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = DEFAULT_SECRET_KEY
    allowed_origins: str = ""
    session_cookie_secure: bool | None = None
    session_cookie_domain: str | None = None
    public_base_url: str = DEFAULT_PUBLIC_BASE_URL
    api_base_url: str = DEFAULT_API_BASE_URL
    default_provider_names: str = ",".join(DEFAULT_PROVIDER_NAMES)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    zenmux_base_url: str = DEFAULT_ZENMUX_BASE_URL
    zenmux_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@socialeval.local"
    object_storage_backend: str = "local"
    object_storage_endpoint: str = ""
    object_storage_region: str = ""
    object_storage_bucket: str = ""
    object_storage_access_key: str = ""
    object_storage_secret_key: str = ""
    object_storage_prefix: str = "socialeval"
    max_concurrent_models: int = 3
    default_std_threshold: float = 5.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> str:
        if value in (None, "", []):
            return ""
        if isinstance(value, list):
            return ",".join(item.strip() for item in value if isinstance(item, str) and item.strip())
        if isinstance(value, str):
            return value.strip()
        raise ValueError("ALLOWED_ORIGINS must be a string or list of strings")

    @field_validator("default_provider_names", mode="before")
    @classmethod
    def parse_default_provider_names(cls, value: object) -> str:
        if value in (None, "", []):
            return ""
        if isinstance(value, list):
            return ",".join(item.strip() for item in value if isinstance(item, str) and item.strip())
        if isinstance(value, str):
            return value.strip()
        raise ValueError("DEFAULT_PROVIDER_NAMES must be a string or list of strings")

    @model_validator(mode="after")
    def validate_production_requirements(self) -> "Settings":
        if self.app_env == "production":
            if self.secret_key == DEFAULT_SECRET_KEY:
                raise ValueError("SECRET_KEY must be changed in production")
            if not self.allowed_origins:
                raise ValueError("ALLOWED_ORIGINS must be configured in production")
        return self

    @property
    def cors_allowed_origins(self) -> list[str]:
        if self.allowed_origins:
            stripped = self.allowed_origins.strip()
            if stripped.startswith("["):
                loaded = json.loads(stripped)
                if not isinstance(loaded, list):
                    raise ValueError("ALLOWED_ORIGINS must decode to a list")
                return [item.strip() for item in loaded if isinstance(item, str) and item.strip()]
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return list(DEFAULT_ALLOWED_ORIGINS)

    @property
    def secure_session_cookie(self) -> bool:
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.app_env == "production"

    @property
    def default_provider_name_list(self) -> list[str]:
        if self.default_provider_names:
            stripped = self.default_provider_names.strip()
            if stripped.startswith("["):
                loaded = json.loads(stripped)
                if not isinstance(loaded, list):
                    raise ValueError("DEFAULT_PROVIDER_NAMES must decode to a list")
                return [item.strip() for item in loaded if isinstance(item, str) and item.strip()]
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return list(DEFAULT_PROVIDER_NAMES)

    @property
    def cookie_domain(self) -> str | None:
        if not self.session_cookie_domain:
            return None
        return self.session_cookie_domain


settings = Settings()
