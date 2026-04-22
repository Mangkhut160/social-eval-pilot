from alembic.config import Config

from src.core.config import Settings


def test_configure_alembic_database_url_prefers_runtime_settings() -> None:
    from src.core.alembic_config import configure_alembic_database_url

    runtime_settings = Settings(
        _env_file=None,
        database_url="postgresql://socialeval:socialeval@postgres:5432/socialeval",
    )
    config = Config()
    config.set_main_option("sqlalchemy.url", "postgresql://socialeval:socialeval@localhost:5432/socialeval")

    configure_alembic_database_url(config, runtime_settings)

    assert config.get_main_option("sqlalchemy.url") == runtime_settings.database_url
