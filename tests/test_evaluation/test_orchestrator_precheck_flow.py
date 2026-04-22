from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
import src.models  # noqa: F401
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.database import Base
from src.evaluation.orchestrator import run_evaluation_pipeline
from src.evaluation.schemas import DimensionResult
from src.ingestion.schemas import ProcessedPaper
from src.models.evaluation import DimensionScore, EvaluationTask
from src.models.paper import Paper
from src.models.reliability import ReliabilityResult
from src.review.queue import list_review_queue


@dataclass
class FakeProvider:
    model_name: str
    score: int
    precheck_status: str = "pass"
    precheck_review_flags: list[str] | None = None

    async def evaluate_dimension(self, prompt: str) -> DimensionResult:
        return DimensionResult(
            dimension="placeholder",
            score=self.score,
            evidence_quotes=[f"{self.model_name} 引文"],
            analysis=f"{self.model_name} analysis",
            model_name=self.model_name,
            band="good",
            summary=f"{self.model_name} summary",
            core_judgment=f"{self.model_name} judgment",
            score_rationale=f"{self.model_name} rationale",
            strengths=["优势"],
            weaknesses=["不足"],
            limit_rule_triggered=[],
            boundary_note="边界说明",
            review_flags=["none"],
        )

    async def generate_json_response(self, prompt: str) -> dict:
        return {
            "status": self.precheck_status,
            "issues": [] if self.precheck_status == "pass" else [f"{self.model_name} precheck issue"],
            "recommendation": "continue" if self.precheck_status == "pass" else "needs review",
            "review_flags": self.precheck_review_flags or ["none"],
            "evidence_quotes": [],
        }


@pytest.fixture
def db_session(tmp_path: Path) -> Session:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = testing_session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.mark.asyncio
async def test_conditional_pass_continues_scoring_and_enters_review_queue(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paper = Paper(
        id="paper-1",
        title="测试论文",
        original_filename="paper.txt",
        file_type="txt",
        file_path="/tmp/paper.txt",
        status="pending",
        uploaded_by="user-1",
    )
    task = EvaluationTask(
        id="task-1",
        paper_id=paper.id,
        framework_id="2.5.0",
        framework_path="configs/frameworks/law-v2.5-20260422.yaml",
        provider_names=json.dumps(["mock-a", "mock-b", "mock-c"], ensure_ascii=False),
        status="pending",
    )
    db_session.add(paper)
    db_session.add(task)
    db_session.commit()

    monkeypatch.setattr(
        "src.evaluation.orchestrator.process_file",
        lambda _: ProcessedPaper(full_text="正文", body="正文", structure_status="detected"),
    )
    monkeypatch.setattr("src.evaluation.orchestrator.generate_reports_for_task", lambda db, task_id: {})

    providers = [
        FakeProvider("mock-a", 80, precheck_status="manual_review", precheck_review_flags=["citation_risk"]),
        FakeProvider("mock-b", 82, precheck_status="pass"),
        FakeProvider("mock-c", 84, precheck_status="pass"),
    ]

    result = await run_evaluation_pipeline(
        task.id,
        db_session,
        provider_factory=lambda _: providers,
    )

    db_session.expire_all()
    refreshed_task = db_session.get(EvaluationTask, task.id)
    refreshed_paper = db_session.get(Paper, paper.id)

    assert result["task_status"] == "completed"
    assert result["paper_status"] == "completed"
    assert result["precheck_status"] == "conditional_pass"
    assert refreshed_task is not None
    assert refreshed_task.manual_review_requested is True
    assert refreshed_task.status == "completed"
    assert refreshed_paper is not None
    assert refreshed_paper.precheck_status == "conditional_pass"
    assert db_session.query(DimensionScore).filter(DimensionScore.task_id == task.id).count() == 18
    assert db_session.query(ReliabilityResult).filter(ReliabilityResult.task_id == task.id).count() == 6

    queued = list_review_queue(db_session)
    assert queued[0]["task_id"] == task.id
    assert "precheck_flagged" in queued[0]["review_reasons"]
