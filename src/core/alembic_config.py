from __future__ import annotations

from alembic.config import Config

from src.core.config import Settings


def configure_alembic_database_url(config: Config, runtime_settings: Settings) -> None:
    config.set_main_option("sqlalchemy.url", runtime_settings.database_url)
