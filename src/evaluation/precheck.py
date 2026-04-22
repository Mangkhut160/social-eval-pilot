from __future__ import annotations

import time

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.evaluation.call_logger import log_call
from src.evaluation.prompt_builder import build_precheck_prompt
from src.evaluation.providers.base import BaseProvider
from src.ingestion.schemas import ProcessedPaper
from src.knowledge.schemas import Framework


class PrecheckResult(BaseModel):
    status: str
    issues: list[str] = []
    recommendation: str = ""
    evidence_quotes: list[str] = []  # v2.3: evidence for issues
    review_flags: list[str] = []  # v2.3: flags triggering manual review


async def run_precheck(
    provider: BaseProvider,
    framework: Framework,
    paper: ProcessedPaper,
    task_id: str,
    db: Session,
    retry_attempts: int = 3,
) -> PrecheckResult:
    prompt = build_precheck_prompt(framework, paper)
    start = time.time()
    last_error: Exception | None = None

    for _ in range(retry_attempts):
        try:
            payload = await provider.generate_json_response(prompt)
            log_call(
                db,
                task_id,
                provider.model_name,
                "__precheck__",
                prompt,
                str(payload),
                start,
            )
            return PrecheckResult(**payload)
        except Exception as exc:
            last_error = exc

    log_call(
        db,
        task_id,
        provider.model_name,
        "__precheck__",
        prompt,
        str(last_error),
        start,
    )
    raise last_error or RuntimeError("Precheck failed")
