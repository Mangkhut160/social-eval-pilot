from __future__ import annotations

import asyncio
from email.message import EmailMessage

import aiosmtplib

from src.core.config import settings
from src.core.logging import logger


def _build_review_assignment_message(
    *,
    expert_email: str,
    task_id: str,
    paper_title: str,
    summary: str,
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"[SocialEval] Review assignment for task {task_id}"
    message["From"] = settings.smtp_from
    message["To"] = expert_email
    message.set_content(
        "\n".join(
            [
                "A SocialEval review task has been assigned to you.",
                f"Task ID: {task_id}",
                f"Paper title: {paper_title}",
                "",
                summary,
            ]
        )
    )
    return message


async def _send_email_message(message: EmailMessage) -> None:
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST is not configured")
    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_port == 587,
        use_tls=settings.smtp_port == 465,
    )


def send_review_assignment_email(
    *,
    expert_email: str,
    task_id: str,
    paper_title: str,
    summary: str,
) -> None:
    message = _build_review_assignment_message(
        expert_email=expert_email,
        task_id=task_id,
        paper_title=paper_title,
        summary=summary,
    )
    logger.info(
        "review_assignment_email",
        extra={
            "expert_email": expert_email,
            "task_id": task_id,
            "paper_title": paper_title,
            "summary": summary,
        },
    )
    asyncio.run(_send_email_message(message))
