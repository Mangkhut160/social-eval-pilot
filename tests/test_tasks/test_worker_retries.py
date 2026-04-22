from __future__ import annotations

from src.tasks.evaluation_task import dispatch_evaluation_task, run_evaluation_task


def test_run_evaluation_task_declares_retry_policy() -> None:
    assert run_evaluation_task.autoretry_for == (Exception,)
    assert run_evaluation_task.retry_backoff is True
    assert run_evaluation_task.retry_kwargs == {"max_retries": 3}


def test_dispatch_evaluation_task_enqueues_task(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_delay(task_id: str) -> None:
        captured["task_id"] = task_id

    monkeypatch.setattr(run_evaluation_task, "delay", fake_delay)

    dispatch_evaluation_task("task-123")

    assert captured["task_id"] == "task-123"
