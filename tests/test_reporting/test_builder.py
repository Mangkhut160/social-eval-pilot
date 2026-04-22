from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import src.models  # noqa: F401
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.database import Base
from src.models.evaluation import DimensionScore, EvaluationTask
from src.models.paper import Paper
from src.models.reliability import ReliabilityResult
from src.reporting.builder import build_internal_report
from src.reporting.public_filter import build_public_report


@contextmanager
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
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


def test_internal_report_includes_per_model_comparison_view(tmp_path: Path) -> None:
    with db_session(tmp_path) as db:
        paper = Paper(
            id="paper-1",
            title="测试论文",
            original_filename="paper.txt",
            file_type="txt",
            file_path="/tmp/paper.txt",
            status="completed",
            precheck_status="pass",
            uploaded_by="user-1",
        )
        task = EvaluationTask(
            id="task-1",
            paper_id=paper.id,
            framework_id="2.4.0",
            framework_path="configs/frameworks/law-v2.4-20260422.yaml",
            provider_names=json.dumps(["mock-a", "mock-b", "mock-c"], ensure_ascii=False),
            status="completed",
        )
        db.add(paper)
        db.add(task)
        db.commit()

        db.add(
            ReliabilityResult(
                task_id=task.id,
                dimension_key="problem_originality",
                mean_score=82,
                std_score=2,
                is_high_confidence=True,
                model_scores={"mock-a": 80, "mock-b": 82, "mock-c": 84},
            )
        )
        for model_name, score in [("mock-a", 80), ("mock-b", 82), ("mock-c", 84)]:
            db.add(
                DimensionScore(
                    task_id=task.id,
                    dimension_key="problem_originality",
                    model_name=model_name,
                    score=score,
                    evidence_quotes=[f"{model_name} 引文"],
                    analysis=f"{model_name} analysis",
                    structured_payload={
                        "dimension": "problem_originality",
                        "score": score,
                        "band": "good",
                        "summary": f"{model_name} summary",
                        "core_judgment": f"{model_name} judgment",
                        "score_rationale": f"{model_name} rationale",
                        "evidence_quotes": [f"{model_name} 引文"],
                        "strengths": ["优势"],
                        "weaknesses": ["不足"],
                        "limit_rule_triggered": [],
                        "boundary_note": "边界说明",
                        "review_flags": ["none"],
                    },
                )
            )
        db.commit()

        report = build_internal_report(db, task, paper)

        dimension = report["dimensions"][0]
        assert dimension["consensus"]["mean_score"] == 82
        assert len(dimension["per_model"]) == 3
        assert dimension["per_model"][0]["model_name"] == "mock-a"
        assert dimension["per_model"][0]["summary"] == "mock-a summary"
        assert dimension["per_model"][0]["core_judgment"] == "mock-a judgment"


def test_public_report_hides_per_model_comparison_view(tmp_path: Path) -> None:
    with db_session(tmp_path) as db:
        paper = Paper(
            id="paper-1",
            title="测试论文",
            original_filename="paper.txt",
            file_type="txt",
            file_path="/tmp/paper.txt",
            status="completed",
            precheck_status="pass",
            uploaded_by="user-1",
        )
        task = EvaluationTask(
            id="task-1",
            paper_id=paper.id,
            framework_id="2.4.0",
            framework_path="configs/frameworks/law-v2.4-20260422.yaml",
            provider_names=json.dumps(["mock-a", "mock-b", "mock-c"], ensure_ascii=False),
            status="completed",
        )
        db.add(paper)
        db.add(task)
        db.commit()

        db.add(
            ReliabilityResult(
                task_id=task.id,
                dimension_key="problem_originality",
                mean_score=82,
                std_score=2,
                is_high_confidence=True,
                model_scores={"mock-a": 80, "mock-b": 82, "mock-c": 84},
            )
        )
        db.add(
            DimensionScore(
                task_id=task.id,
                dimension_key="problem_originality",
                model_name="mock-a",
                score=80,
                evidence_quotes=["mock-a 引文"],
                analysis="mock-a analysis",
                structured_payload={
                    "dimension": "problem_originality",
                    "score": 80,
                    "band": "good",
                    "summary": "mock-a summary",
                    "core_judgment": "mock-a judgment",
                    "score_rationale": "mock-a rationale",
                    "evidence_quotes": ["mock-a 引文"],
                    "strengths": ["优势"],
                    "weaknesses": ["不足"],
                    "limit_rule_triggered": [],
                    "boundary_note": "边界说明",
                    "review_flags": ["none"],
                },
            )
        )
        db.commit()

        internal_report = build_internal_report(db, task, paper)
        public_report = build_public_report(internal_report)

        assert "per_model" not in public_report["dimensions"][0]
        assert public_report["dimensions"][0]["consensus"]["mean_score"] == 82


def test_internal_report_exposes_precheck_per_model_and_public_report_hides_it(tmp_path: Path) -> None:
    with db_session(tmp_path) as db:
        paper = Paper(
            id="paper-1",
            title="测试论文",
            original_filename="paper.txt",
            file_type="txt",
            file_path="/tmp/paper.txt",
            status="completed",
            precheck_status="conditional_pass",
            precheck_result={
                "status": "conditional_pass",
                "issues": ["引注存在核验风险"],
                "recommendation": "继续评分并人工复核",
                "review_flags": ["citation_risk"],
                "evidence_quotes": ["脚注与文末参考文献不一致"],
                "consensus": {
                    "status": "conditional_pass",
                    "issues": ["引注存在核验风险"],
                    "recommendation": "继续评分并人工复核",
                    "review_flags": ["citation_risk"],
                    "evidence_quotes": ["脚注与文末参考文献不一致"],
                },
                "per_model": [
                    {
                        "model_name": "mock-a",
                        "status": "manual_review",
                        "issues": ["mock-a issue"],
                        "review_flags": ["citation_risk"],
                        "recommendation": "先核验再看",
                        "evidence_quotes": ["mock-a quote"],
                    },
                    {
                        "model_name": "mock-b",
                        "status": "pass",
                        "issues": [],
                        "review_flags": ["none"],
                        "recommendation": "可继续",
                        "evidence_quotes": [],
                    },
                ],
            },
            uploaded_by="user-1",
        )
        task = EvaluationTask(
            id="task-1",
            paper_id=paper.id,
            framework_id="2.5.0",
            framework_path="configs/frameworks/law-v2.5-20260422.yaml",
            provider_names=json.dumps(["mock-a", "mock-b"], ensure_ascii=False),
            status="completed",
            manual_review_requested=True,
        )
        db.add(paper)
        db.add(task)
        db.commit()

        internal_report = build_internal_report(db, task, paper)
        public_report = build_public_report(internal_report)

        assert internal_report["precheck_result"]["status"] == "conditional_pass"
        assert internal_report["precheck_result"]["per_model"][0]["display_label"] == "模型1"
        assert internal_report["precheck_result"]["per_model"][0]["model_name"] == "mock-a"
        assert "per_model" not in public_report["precheck_result"]
        assert public_report["precheck_result"]["consensus"]["status"] == "conditional_pass"
