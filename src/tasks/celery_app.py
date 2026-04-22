from celery import Celery

from src.core.config import settings
from src.core.logging import setup_logging

setup_logging()

celery_app = Celery(
    "socialeval",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.task_ignore_result = True
celery_app.conf.task_acks_late = True
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.worker_prefetch_multiplier = 1
