from __future__ import annotations


ALLOWED_TASK_TRANSITIONS = {
    "pending": {"processing", "closed"},
    "processing": {"completed", "reviewing", "recovering", "closed"},
    "reviewing": {"completed", "recovering", "closed"},
    "recovering": {"processing", "closed"},
    "completed": {"reviewing", "closed"},
    "closed": set(),
}


def ensure_valid_task_transition(current_status: str, new_status: str) -> None:
    allowed = ALLOWED_TASK_TRANSITIONS.get(current_status, set())
    if new_status not in allowed and current_status != new_status:
        raise ValueError(f"Illegal task status transition: {current_status} -> {new_status}")
