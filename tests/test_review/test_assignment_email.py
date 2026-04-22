from __future__ import annotations

import pytest

from src.core import email as email_module


def test_send_review_assignment_email_builds_and_sends_message(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_send_message(message):
        captured["message"] = message

    monkeypatch.setattr(email_module.settings, "smtp_host", "smtp.socialeval.example")
    monkeypatch.setattr(email_module.settings, "smtp_port", 587)
    monkeypatch.setattr(email_module.settings, "smtp_user", "mailer")
    monkeypatch.setattr(email_module.settings, "smtp_password", "secret")
    monkeypatch.setattr(email_module.settings, "smtp_from", "noreply@socialeval.example")
    monkeypatch.setattr(email_module, "_send_email_message", fake_send_message)

    email_module.send_review_assignment_email(
        expert_email="expert@example.com",
        task_id="task-123",
        paper_title="A Legal Paper",
        summary="Please review this submission.",
    )

    message = captured["message"]
    assert message["To"] == "expert@example.com"
    assert message["From"] == "noreply@socialeval.example"
    assert "task-123" in message["Subject"]
    assert "A Legal Paper" in message.get_content()


def test_send_review_assignment_email_surfaces_delivery_failures(monkeypatch) -> None:
    async def failing_send_message(message):
        raise RuntimeError("smtp unavailable")

    monkeypatch.setattr(email_module.settings, "smtp_host", "smtp.socialeval.example")
    monkeypatch.setattr(email_module.settings, "smtp_from", "noreply@socialeval.example")
    monkeypatch.setattr(email_module, "_send_email_message", failing_send_message)

    with pytest.raises(RuntimeError, match="smtp unavailable"):
        email_module.send_review_assignment_email(
            expert_email="expert@example.com",
            task_id="task-123",
            paper_title="A Legal Paper",
            summary="Please review this submission.",
        )
